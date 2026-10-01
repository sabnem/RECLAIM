"""HTTP views for reports, claims, messaging, and member accounts."""

import logging
import cloudinary.uploader

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    ClaimForm,
    ItemForm,
    LoginForm,
    MessageForm,
    ReturnVerificationForm,
    UserProfileForm,
    UserRegistrationForm,
    UserReviewForm,
)
from .models import (
    AccountDeletionFeedback,
    Claim,
    ClaimEvent,
    Item,
    ItemCategory,
    Message,
    RecoveredItem,
    ReturnConfirmation,
)
from .otp_delivery import deliver_claim_code, mask_email
from .selectors import return_statistics_for


logger = logging.getLogger(__name__)

def _send_claim_otp_notification(request, claim, verification_code, lead='Claim approved.'):
    """Deliver the code to the claimant and report the outcome without revealing it."""
    delivered, problems = deliver_claim_code(claim, verification_code)
    name = claim.claimant.username
    if delivered:
        channels = [f'email ({mask_email(claim.claimant.email)})' if channel == 'email' else channel for channel in delivered]
        messages.success(request, f'{lead} Verification code sent to {name} by {" and ".join(channels)}.')
    else:
        messages.warning(
            request,
            f'{lead} The verification code could not be delivered to {name}. They can request a new '
            'code from My claims after updating their email or phone number.',
        )
    if problems and (request.user.is_superuser or settings.DEBUG):
        messages.info(request, 'Delivery notes: ' + '; '.join(problems) + '.')


@login_required
@require_POST
@transaction.atomic
def submit_claim(request, item_id):

    item = get_object_or_404(Item.objects.select_for_update(), id=item_id)

    if item.reported_by == request.user:
        messages.error(request, 'You cannot claim an item that you reported yourself.')
        return redirect('item_detail', item_id=item.id)

    if item.is_returned or item.verification_status == 'RETURNED':
        messages.error(request, 'This item has already been returned.')
        return redirect('item_detail', item_id=item.id)

    existing_approved = Claim.objects.filter(item=item, claimant=request.user).exists()
    if existing_approved:
        messages.info(request, 'You already have a claim for this item. Manage it from My claims.')
        return redirect('my_claims')

    form = ClaimForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'Please provide a valid proof message before submitting your claim.')
        return redirect('item_detail', item_id=item.id)

    claim, created = Claim.objects.get_or_create(item=item, claimant=request.user, defaults={
        'proof_text': form.cleaned_data['proof_text'],
        'proof_image': form.cleaned_data.get('proof_image'),
    })
    claim.proof_text = form.cleaned_data['proof_text']
    if form.cleaned_data.get('proof_image'):
        claim.proof_image = form.cleaned_data['proof_image']
    if claim.status != Claim.STATUS_APPROVED:
        claim.status = Claim.STATUS_PENDING
        claim.reviewed_by = None
        claim.reviewed_at = None
        claim.verification_code_hash = ''
        claim.verification_code_sent_at = None
        claim.verification_code_expires_at = None
        claim.verification_code_used_at = None
        claim.returned_at = None
        claim.is_returned = False
    claim.full_clean()
    claim.save()

    ClaimEvent.objects.create(claim=claim, recipient=item.reported_by, actor=request.user,
                              kind='submitted', text=claim.proof_text)

    if item.verification_status == 'FOUND':
        item.verification_status = 'CLAIMED'
        item.save(update_fields=['verification_status'])

    messages.success(request, 'Your ownership claim has been submitted for review.')
    return redirect('item_detail', item_id=item.id)


@login_required
@require_POST
@transaction.atomic
def review_claim(request, claim_id):

    claim = get_object_or_404(Claim, id=claim_id)
    item = get_object_or_404(Item.objects.select_for_update(), id=claim.item_id)
    claim.refresh_from_db()
    if request.user != item.reported_by and not request.user.is_superuser:
        messages.error(request, 'Only the finder or an administrator can review this claim.')
        return redirect('item_detail', item_id=item.id)

    action = request.POST.get('action')
    if claim.status != Claim.STATUS_PENDING or item.is_returned:
        messages.info(request, 'This claim is no longer awaiting review.')
        return redirect('manage_claims', item_id=item.id)
    if action not in {'approve', 'reject'}:
        messages.error(request, 'Invalid claim action.')
        return redirect('item_detail', item_id=item.id)

    if action == 'approve' and item.claims.filter(status=Claim.STATUS_APPROVED).exclude(id=claim.id).exists():
        messages.error(request, 'This item already has an approved claimant.')
        return redirect('item_detail', item_id=item.id)

    claim.reviewed_by = request.user
    claim.reviewed_at = timezone.now()

    if action == 'reject':
        claim.status = Claim.STATUS_REJECTED
        claim.verification_code_hash = ''
        claim.verification_code_sent_at = None
        claim.verification_code_expires_at = None
        claim.verification_code_used_at = None
        claim.is_returned = False
        claim.returned_at = None
        claim.save()
        ClaimEvent.objects.create(claim=claim, recipient=claim.claimant, actor=request.user,
                                  kind='rejected', text=request.POST.get('reason', '').strip()[:2000])
        if not item.claims.filter(status=Claim.STATUS_APPROVED).exists():
            item.verification_status = 'CLAIMED' if item.claims.filter(status=Claim.STATUS_PENDING).exists() else 'FOUND'
            item.save(update_fields=['verification_status'])
        messages.success(request, 'Claim rejected.')
        return redirect('item_detail', item_id=item.id)

    claim.status = Claim.STATUS_APPROVED
    claim.is_returned = False
    claim.returned_at = None
    verification_code = claim.generate_verification_code()
    claim.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'is_returned', 'returned_at', 'updated_at'])
    item.verification_status = 'VERIFIED'
    item.save(update_fields=['verification_status'])
    ClaimEvent.objects.create(claim=claim, recipient=claim.claimant, actor=request.user, kind='approved')
    _send_claim_otp_notification(request, claim, verification_code)
    return redirect('item_detail', item_id=item.id)


@login_required
@require_POST
@transaction.atomic
def mark_item_returned(request, item_id):

    item = get_object_or_404(Item.objects.select_for_update(), id=item_id)
    if request.user != item.reported_by and not request.user.is_superuser:
        messages.error(request, 'Only the finder or an administrator can confirm the return.')
        return redirect('item_detail', item_id=item.id)

    claimant_username = request.POST.get('claimant_username', '').strip()
    verification_code = request.POST.get('verification_code', '').strip()

    if not claimant_username or not verification_code:
        messages.error(request, 'Please enter both the verified claimant username and the verification code.')
        return redirect('item_detail', item_id=item.id)

    claim = get_object_or_404(
        Claim,
        item=item,
        claimant__username__iexact=claimant_username,
        status=Claim.STATUS_APPROVED,
    )

    if item.is_returned or item.verification_status == 'RETURNED' or claim.is_returned:
        messages.error(request, 'This item has already been marked as returned.')
        return redirect('item_detail', item_id=item.id)

    if not claim.verify_code(verification_code):
        messages.error(request, 'The verification code is invalid, expired, or already used.')
        return redirect('item_detail', item_id=item.id)

    claim.mark_returned()
    item.owner = claim.claimant
    item.mark_as_returned(owner=claim.claimant)

    ReturnConfirmation.objects.get_or_create(
        claim=claim,
        defaults={
            'item': item,
            'finder': item.reported_by,
            'claimant': claim.claimant,
            'entered_claimant_username': claimant_username,
            'is_valid': True,
            'confirmed_by': request.user,
        }
    )

    RecoveredItem.objects.get_or_create(
        item=item,
        defaults={
            'owner': claim.claimant,
            'finder': item.reported_by,
            'original_report_date': item.date_reported,
            'location': item.location,
        }
    )

    messages.success(request, f'Item returned successfully to {claim.claimant.username}.')
    return redirect('rate_finder', item_id=item.id)


@login_required
def return_confirmation(request, item_id):
    return redirect('item_detail', item_id=item_id)
# Admin Dashboard view (superuser only)
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    from django.contrib.auth.models import User
    total_users = User.objects.count()
    total_items = Item.objects.count()
    total_messages = Message.objects.count()
    items_found = Item.objects.filter(status='Found').count()
    items_lost = Item.objects.filter(status='Lost').count()
    recent_items = Item.objects.order_by('-date_reported')[:5]
    recent_users = User.objects.order_by('-date_joined')[:5]
    return render(request, 'admin_dashboard.html', {
        'total_users': total_users,
        'total_items': total_items,
        'total_messages': total_messages,
        'items_found': items_found,
        'items_lost': items_lost,
        'recent_items': recent_items,
        'recent_users': recent_users,
    })


# Submit review for reputation system


@login_required
def submit_review(request, user_id):
    reviewed_user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        form = UserReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.reviewed = reviewed_user
            review.save()
            return redirect('profile')
    else:
        form = UserReviewForm()
    return render(request, 'FindIt/submit_review.html', {'form': form, 'reviewed_user': reviewed_user})

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. Please log in.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'FindIt/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid username or password')
    else:
        form = LoginForm()
    return render(request, 'FindIt/login.html', {'form': form})

def user_logout(request):
    logout(request)
    return redirect('home')

def home(request):
    return render(request, 'FindIt/home.html')

def report_item(request):
    is_authenticated = request.user.is_authenticated
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.reported_by = request.user
            item.save()
            messages.success(request, 'Item reported successfully!')
            return redirect('home')
    else:
        form = ItemForm() if is_authenticated else None
    return render(request, 'FindIt/report_item.html', {
        'form': form,
        'is_authenticated': is_authenticated,
    })

def item_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')

    # Exclude items that have been recovered (confirmed returns)
    recovered_item_ids = RecoveredItem.objects.values_list('item_id', flat=True)
    items = Item.objects.select_related('category').exclude(Q(id__in=recovered_item_ids) | Q(is_returned=True)).order_by('-date_reported')

    if query:
        items = items.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query))
    if category_id:
        items = items.filter(category_id=category_id)
    if status:
        items = items.filter(status=status)
    categories = ItemCategory.objects.all()
    return render(request, 'FindIt/item_list.html', {
        'items': items,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'selected_status': status,
    })

def item_detail(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    claim_form = ClaimForm()
    return_form = ReturnVerificationForm()
    claims = item.claims.select_related('claimant', 'reviewed_by').order_by('-created_at')
    pending_claims = claims.filter(status=Claim.STATUS_PENDING)
    approved_claims = claims.filter(status=Claim.STATUS_APPROVED)
    claimants = approved_claims.values_list('claimant__username', flat=True)
    can_submit_claim = request.user.is_authenticated and request.user != item.reported_by and not item.is_returned
    can_review_claims = request.user.is_authenticated and (request.user == item.reported_by or request.user.is_superuser)
    can_confirm_return = request.user.is_authenticated and (request.user == item.reported_by or request.user.is_superuser) and approved_claims.exists() and not item.is_returned

    has_recovered = RecoveredItem.objects.filter(item=item).exists()

    return render(request, 'FindIt/item_detail.html', {
        'item': item,
        'has_recovered': has_recovered,
        'claims': claims,
        'pending_claims': pending_claims,
        'approved_claims': approved_claims,
        'claimant_usernames': claimants,
        'claim_form': claim_form,
        'return_form': return_form,
        'can_submit_claim': can_submit_claim,
        'own_claim': item.claims.filter(claimant=request.user).first() if request.user.is_authenticated else None,
        'can_review_claims': can_review_claims,
        'can_confirm_return': can_confirm_return,
    })


@login_required
def manage_claims(request, item_id):

    item = get_object_or_404(Item, id=item_id)
    if request.user != item.reported_by and not request.user.is_superuser:
        messages.error(request, 'Only the finder or an administrator can review claims for this item.')
        return redirect('item_detail', item_id=item.id)

    claims = item.claims.select_related('claimant', 'reviewed_by').order_by('-created_at')
    pending_claims = claims.filter(status=Claim.STATUS_PENDING)
    approved_claims = claims.filter(status=Claim.STATUS_APPROVED)
    rejected_claims = claims.filter(status=Claim.STATUS_REJECTED)
    has_recovered = RecoveredItem.objects.filter(item=item).exists()

    return render(request, 'FindIt/manage_claims.html', {
        'item': item,
        'claims': claims,
        'pending_claims': pending_claims,
        'approved_claims': approved_claims,
        'rejected_claims': rejected_claims,
        'has_recovered': has_recovered,
        'claim_count': claims.count(),
        'pending_count': pending_claims.count(),
        'approved_count': approved_claims.count(),
        'rejected_count': rejected_claims.count(),
        'can_confirm_return': request.user.is_authenticated and (request.user == item.reported_by or request.user.is_superuser) and approved_claims.exists() and not item.is_returned,
    })

def contact_item_owner(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    owner_email = item.reported_by.email
    if not owner_email or '@' not in owner_email:
        messages.error(request, "The item owner's email address is missing or invalid. Unable to send message.")
        return redirect('item_detail', item_id=item.id)
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.cleaned_data['message']
            sender = request.user
            try:
                send_mail(
                    subject=f'Lost & Found Inquiry: {item.title}',
                    message=f"Message from {sender.username} ({sender.email}):\n\n{message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[owner_email],
                    fail_silently=False,
                )
                messages.success(request, 'Your message has been sent to the item owner!')
            except Exception as e:
                messages.error(request, f"Failed to send email: {e}")
            return redirect('item_detail', item_id=item.id)
    else:
        form = MessageForm()
    return render(request, 'FindIt/contact_owner.html', {'form': form, 'item': item})


@login_required
def profile_view(request):
    profile = request.user.userprofile
    user = request.user
    reviews = user.received_reviews.select_related('reviewer').order_by('-created_at')
    avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
    return render(request, 'FindIt/profile.html', {
        'profile': profile,
        'user': user,
        'reviews': reviews,
        'avg_rating': avg_rating,
    })

@login_required
def edit_profile(request):
    profile = request.user.userprofile
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile, user=request.user)
    return render(request, 'FindIt/edit_profile.html', {'form': form, 'profile': profile})

@login_required
@require_POST
def upload_profile_picture(request):
    profile = request.user.userprofile
    form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
    if 'profile_picture' in request.FILES:
        profile.profile_picture = request.FILES['profile_picture']
        profile.save()
    return redirect('profile')

@login_required
@require_POST
def remove_profile_picture(request):
    profile = request.user.userprofile
    if profile.profile_picture:
        picture = profile.profile_picture
        try:
            result = cloudinary.uploader.destroy(
                picture.public_id,
                resource_type=picture.resource_type or 'image',
                type=picture.type or 'upload',
                invalidate=True,
            )
        except Exception:
            logger.warning('Cloudinary profile picture removal failed for user %s', request.user.pk)
            messages.error(request, 'Your picture could not be removed right now. Please try again.')
            return redirect('profile')
        if result.get('result') not in {'ok', 'not found'}:
            messages.error(request, 'Your picture could not be removed right now. Please try again.')
            return redirect('profile')
        profile.profile_picture = None
        profile.save(update_fields=['profile_picture'])
        messages.success(request, 'Your profile picture has been removed.')
    return redirect('profile')


@login_required
def delete_account(request):
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        other_reason = request.POST.get('other_reason', '')
        AccountDeletionFeedback.objects.create(
            username=request.user.username,
            email=request.user.email,
            reason=reason,
            other_reason=other_reason
        )
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account has been successfully deleted.')
        return render(request, 'FindIt/delete_account_success.html')
    return render(request, 'FindIt/delete_account_confirm.html')

@login_required
def edit_item_fields(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.user != item.reported_by:
        messages.error(request, 'You do not have permission to edit this item.')
        return redirect('item_detail', item_id=item.id)
    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        location = request.POST.get('location', '').strip()
        photo = request.FILES.get('photo')
        if description:
            item.description = description
        if location:
            item.location = location
        if photo:
            item.photo = photo
        item.save()
        messages.success(request, 'Item updated successfully.')
        return redirect('item_detail', item_id=item.id)
    else:
        messages.error(request, 'Invalid request method.')
        return redirect('item_detail', item_id=item.id)
def terms_and_conditions(request):
    return render(request, 'FindIt/terms_and_conditions.html')

def privacy_policy(request):
    return render(request, 'FindIt/privacy_policy.html')


# My Recovered Items - items that owner got back
@login_required
def my_recovered_items(request):
    recovered_items = RecoveredItem.objects.filter(owner=request.user).select_related('item', 'finder')
    return render(request, 'FindIt/my_recovered_items.html', {
        'recovered_items': recovered_items
    })


# My Returned Items - items that finder returned to owners
@login_required
def my_returned_items(request):
    returned_items = RecoveredItem.objects.filter(finder=request.user).select_related('item', 'owner')
    return render(request, 'FindIt/my_returned_items.html', {
        'returned_items': returned_items
    })


# Rate the finder who returned the item
@login_required
def rate_finder(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    try:
        recovered_item = RecoveredItem.objects.get(item=item, owner=request.user)
    except RecoveredItem.DoesNotExist:
        messages.error(request, 'This item has not been recovered yet.')
        return redirect('item_detail', item_id=item.id)

    # Check if already rated
    if recovered_item.rating:
        messages.info(request, 'You have already rated this return.')
        return redirect('my_recovered_items')

    if request.method == 'POST':
        rating = request.POST.get('rating')
        feedback = request.POST.get('feedback', '').strip()

        if rating:
            recovered_item.rating = int(rating)
            recovered_item.feedback = feedback
            recovered_item.rated_at = timezone.now()
            recovered_item.save()

            # Update finder's reputation score
            if hasattr(recovered_item.finder, 'userprofile'):
                recovered_item.finder.userprofile.update_reputation()

            # Send email notification to finder
            if recovered_item.finder.email and hasattr(recovered_item.finder, 'userprofile') and recovered_item.finder.userprofile.notify_email:
                try:
                    send_mail(
                        subject=f'You received a {rating}-star rating from {request.user.username}!',
                        message=f'''Hi {recovered_item.finder.username},

Great news! {request.user.username} has rated your return of "{item.title}".

Rating: {'⭐' * int(rating)} ({rating}/5 stars)
{f'Feedback: "{feedback}"' if feedback else ''}

Your current reputation score: {recovered_item.finder.userprofile.reputation_score}/5.0
Total returns: {recovered_item.finder.userprofile.total_returns}

Keep up the great work helping others!

View your returned items: {settings.SITE_URL}/my-returned-items/

Best regards,
FindIt Team
''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recovered_item.finder.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    # Log error but don't stop the process
                    logger.exception('Rating notification email failed for recovered item %s', recovered_item.pk)

            messages.success(request, f'Thank you for rating {recovered_item.finder.username}!')
            return redirect('my_recovered_items')
        else:
            messages.error(request, 'Please select a rating.')

    return render(request, 'FindIt/rate_finder.html', {
        'item': item,
        'recovered_item': recovered_item
    })


# Statistics Dashboard for Returns
@login_required
def returns_statistics(request):
    return render(request, 'FindIt/returns_statistics.html', return_statistics_for(request.user))


# Export Recovered Items to PDF
@login_required
def export_recovered_items_pdf(request):
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from io import BytesIO

    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#D97706'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("My Recovered Items Report", title_style))
    elements.append(Spacer(1, 12))

    # User info
    info_style = ParagraphStyle(
        'Info',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12
    )
    elements.append(Paragraph(f"<b>User:</b> {request.user.username}", info_style))
    elements.append(Paragraph(f"<b>Generated:</b> {timezone.now().strftime('%B %d, %Y at %I:%M %p')}", info_style))

    # Get user's recovered items
    recovered_items = RecoveredItem.objects.filter(
        owner=request.user
    ).select_related('item', 'finder').order_by('-recovered_date')

    elements.append(Paragraph(f"<b>Total Recovered Items:</b> {recovered_items.count()}", info_style))
    elements.append(Spacer(1, 20))

    if recovered_items.exists():
        # Create table data
        data = [['Item', 'Finder', 'Date', 'Rating', 'Feedback']]

        for recovered in recovered_items:
            rating_stars = '⭐' * (recovered.rating or 0) if recovered.rating else 'Not rated'
            feedback_text = (recovered.feedback[:50] + '...') if recovered.feedback and len(recovered.feedback) > 50 else (recovered.feedback or 'N/A')

            data.append([
                recovered.item.title[:30],
                recovered.finder.username,
                recovered.recovered_date.strftime('%Y-%m-%d'),
                rating_stars,
                feedback_text
            ])

        # Create table
        table = Table(data, colWidths=[2*inch, 1.2*inch, 1*inch, 1*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D97706')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # Summary statistics
        rated_items = recovered_items.filter(rating__isnull=False)
        if rated_items.exists():
            avg_rating = sum(r.rating for r in rated_items) / rated_items.count()
            elements.append(Paragraph(f"<b>Average Rating Given:</b> {avg_rating:.2f}/5.0 ⭐", info_style))

    else:
        elements.append(Paragraph("No recovered items found.", info_style))

    # Build PDF
    doc.build(elements)

    # Get PDF data
    pdf = buffer.getvalue()
    buffer.close()

    # Create HTTP response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recovered_items_{request.user.username}_{timezone.now().strftime("%Y%m%d")}.pdf"'
    response.write(pdf)

    return response
