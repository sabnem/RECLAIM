from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

# Mark item as returned (reporter, owner, or superuser only)
@login_required
def mark_item_returned(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    
    # Check if user has permission: reporter, owner, or superuser
    is_reporter = (request.user == item.reported_by)
    is_owner = (item.owner == request.user) if item.owner else False
    is_superuser = request.user.is_superuser
    
    if is_reporter or is_owner or is_superuser:
        owner_username = request.POST.get('owner_username')
        
        # Only reporter can set the owner initially
        if owner_username and not item.is_returned and is_reporter:
            try:
                owner_user = User.objects.get(username=owner_username)
                item.owner = owner_user
                item.is_returned = True
                item.save()
                messages.success(request, f'Item marked as returned. Waiting for {owner_user.username} to confirm.')
                return redirect('item_detail', item_id=item.id)
            except User.DoesNotExist:
                messages.error(request, f"User '{owner_username}' does not exist.")
                return redirect('item_detail', item_id=item.id)
        
        # If owner is confirming, create recovered record
        if is_owner and not is_reporter and not is_superuser:
            # Check if already recovered
            from .models import RecoveredItem
            if RecoveredItem.objects.filter(item=item, owner=request.user).exists():
                messages.info(request, 'You have already confirmed this return.')
                return redirect('my_recovered_items')
            
            # Create RecoveredItem record
            RecoveredItem.objects.create(
                item=item,
                owner=item.owner,
                finder=item.reported_by,
                original_report_date=item.date_reported,
                location=item.location
            )
            
            # Ensure item is marked as returned
            item.is_returned = True
            item.save()
            
            messages.success(request, 'Return confirmed! The item has been moved to your recovered items. Please rate the finder.')
            return redirect('rate_finder', item_id=item.id)
        else:
            # Reporter or superuser can toggle the status
            item.is_returned = not item.is_returned
            item.save()
            
            if item.is_returned:
                messages.success(request, 'Item marked as returned.')
            else:
                messages.success(request, 'Item marked as not returned.')
    else:
        messages.error(request, 'You do not have permission to perform this action.')
    
    return redirect('item_detail', item_id=item.id)
# Context processor to provide unread inbox count to all templates
def unread_inbox_count(request):
    if request.user.is_authenticated:
        return {'unread_inbox_count': request.user.received_messages.filter(is_read=False).count()}
    return {'unread_inbox_count': 0}
# Context processor to provide categories to all templates
from .models import ItemCategory
from .models import ReturnConfirmation, Item
from .forms import ReturnConfirmationForm
def categories_context(request):
    return {'categories': ItemCategory.objects.all()}
from django.contrib.auth.decorators import user_passes_test

# Admin Dashboard view (superuser only)
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    from django.contrib.auth.models import User
    from .models import Item, Message
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
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from .forms import UserRegistrationForm, LoginForm, ItemForm, MessageForm
from django.contrib import messages
from .models import Item, ItemCategory, Message
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings

from .forms import UserReviewForm
from .models import UserReview

# Submit review for reputation system
from django.contrib.auth.decorators import login_required

# Return confirmation view
@login_required
def return_confirmation(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    confirmation, created = ReturnConfirmation.objects.get_or_create(item=item)
    user = request.user
    is_finder = (user == item.reported_by)
    is_owner = (user == item.owner) if hasattr(item, 'owner') else False
    if request.method == 'POST':
        form = ReturnConfirmationForm(request.POST, request.FILES, instance=confirmation)
        if form.is_valid():
            conf = form.save(commit=False)
            if is_finder:
                conf.finder_confirmed = True
            if is_owner:
                conf.owner_confirmed = True
            if conf.is_fully_confirmed():
                conf.confirmed_at = timezone.now()
            conf.save()
            return redirect('item_detail', item_id=item.id)
    else:
        form = ReturnConfirmationForm(instance=confirmation)
    return render(request, 'FindIt/return_confirmation.html', {
        'form': form,
        'item': item,
        'confirmation': confirmation,
        'is_finder': is_finder,
        'is_owner': is_owner,
    })
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
    return redirect('login')

def home(request):
    return render(request, 'FindIt/home.html')

def report_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.reported_by = request.user
            item.save()
            messages.success(request, 'Item reported successfully!')
            return redirect('home')
    else:
        form = ItemForm()
    return render(request, 'FindIt/report_item.html', {'form': form})

def item_list(request):
    from .models import RecoveredItem
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    
    # Exclude items that have been recovered (confirmed returns)
    recovered_item_ids = RecoveredItem.objects.values_list('item_id', flat=True)
    items = Item.objects.exclude(id__in=recovered_item_ids).order_by('-date_reported')
    
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
    from .models import RecoveredItem
    item = get_object_or_404(Item, id=item_id)
    confirmation = getattr(item, 'return_confirmation', None)
    if not confirmation:
        from .models import ReturnConfirmation
        confirmation = ReturnConfirmation.objects.create(item=item)
    
    # Check if item has been recovered
    has_recovered = RecoveredItem.objects.filter(item=item).exists()
    
    return render(request, 'FindIt/item_detail.html', {
        'item': item,
        'confirmation': confirmation,
        'has_recovered': has_recovered,
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

def inbox(request):
    item_id = request.GET.get('item_id')
    recipient_id = request.GET.get('recipient_id')

    # Handle sending a message (fallback for image uploads or non-WebSocket)
    if request.method == 'POST':
        item_id = request.POST.get('item_id') or item_id
        recipient_id = request.POST.get('recipient_id') or recipient_id
        content = request.POST.get('message', '').strip()
        image = request.FILES.get('chat_image')
        if item_id and recipient_id and (content or image):
            item = get_object_or_404(Item, id=item_id)
            recipient = get_object_or_404(User, id=recipient_id)
            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                item=item,
                content=content,
                image=image
            )
            return redirect(f"{request.path}?item_id={item_id}&recipient_id={recipient_id}")

    # Get all conversations for the sidebar (exclude archived messages)
    conversations = Message.objects.filter(
        Q(sender=request.user, deleted_by_sender=False) | 
        Q(recipient=request.user, deleted_by_recipient=False)
    ).select_related('item', 'sender', 'recipient').order_by('-timestamp')

    # Group conversations by (item, other_user)
    convo_dict = {}
    for msg in conversations:
        other_user = msg.recipient if msg.sender == request.user else msg.sender
        key = (msg.item.id, other_user.id)
        if key not in convo_dict or msg.timestamp > convo_dict[key].timestamp:
            convo_dict[key] = msg
    convo_list = list(convo_dict.values())

    # Determine active conversation
    active_conversation = None
    active_messages = []
    if item_id and recipient_id:
        item = get_object_or_404(Item, id=item_id)
        recipient = get_object_or_404(User, id=recipient_id)
        # Filter out archived messages for the active conversation
        active_messages = Message.objects.filter(
            item=item,
            sender__in=[request.user, recipient],
            recipient__in=[request.user, recipient]
        ).filter(
            Q(sender=request.user, deleted_by_sender=False) | 
            Q(recipient=request.user, deleted_by_recipient=False)
        ).order_by('timestamp')
        # For sidebar highlighting
        for msg in convo_list:
            if msg.item.id == int(item_id) and (msg.sender.id == int(recipient_id) or msg.recipient.id == int(recipient_id)):
                active_conversation = msg
                break
        if not active_conversation and active_messages:
            active_conversation = active_messages.last()
    elif convo_list:
        active_conversation = convo_list[0]
        active_messages = Message.objects.filter(
            item=active_conversation.item,
            sender__in=[request.user, active_conversation.sender, active_conversation.recipient],
            recipient__in=[request.user, active_conversation.sender, active_conversation.recipient]
        ).filter(
            Q(sender=request.user, deleted_by_sender=False) | 
            Q(recipient=request.user, deleted_by_recipient=False)
        ).order_by('timestamp')

    # Mark all unread messages as read
    Message.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)

    # Prepare context for template
    sidebar_conversations = []
    for msg in convo_list:
        other_user = msg.recipient if msg.sender == request.user else msg.sender
        # Use userprofile.profile_picture if available
        avatar_url = ''
        if hasattr(other_user, 'userprofile') and other_user.userprofile.profile_picture:
            avatar_url = other_user.userprofile.profile_picture.url
        sidebar_conversations.append({
            'id': f"{msg.item.id}-{other_user.id}",
            'avatar_url': avatar_url,
            'name': other_user.get_full_name() or other_user.username,
            'last_message': msg.content,
            'last_date': msg.timestamp,
            'item_title': msg.item.title,
            'item_image': msg.item.photo.url if msg.item.photo else '',
            'item_price': getattr(msg.item, 'price', ''),
            'other_user_id': other_user.id,
            'item_id': msg.item.id,
        })

    active_convo_data = None
    if active_conversation:
        other_user = active_conversation.recipient if active_conversation.sender == request.user else active_conversation.sender
        avatar_url = ''
        if hasattr(other_user, 'userprofile') and other_user.userprofile.profile_picture:
            avatar_url = other_user.userprofile.profile_picture.url
        active_convo_data = {
            'id': f"{active_conversation.item.id}-{other_user.id}",
            'avatar_url': avatar_url,
            'name': other_user.get_full_name() or other_user.username,
            'item_title': active_conversation.item.title,
            'item_image': active_conversation.item.photo.url if active_conversation.item.photo else '',
            'item_price': getattr(active_conversation.item, 'price', ''),
            'date': active_conversation.timestamp,
            'messages': active_messages,
        }
    # If no messages exist but item_id and recipient_id are provided, show chat UI for new conversation
    elif item_id and recipient_id:
        item = get_object_or_404(Item, id=item_id)
        recipient = get_object_or_404(User, id=recipient_id)
        avatar_url = ''
        if hasattr(recipient, 'userprofile') and recipient.userprofile.profile_picture:
            avatar_url = recipient.userprofile.profile_picture.url
        active_convo_data = {
            'id': f"{item.id}-{recipient.id}",
            'avatar_url': avatar_url,
            'name': recipient.get_full_name() or recipient.username,
            'item_title': item.title,
            'item_image': item.photo.url if item.photo else '',
            'item_price': getattr(item, 'price', ''),
            'date': None,
            'messages': [],
        }

    # Ensure item_id and recipient_id are set for the form
    if (not item_id or not recipient_id) and active_convo_data:
        item_id = active_convo_data['id'].split('-')[0]
        recipient_id = active_convo_data['id'].split('-')[1]

    return render(request, 'FindIt/inbox.html', {
        'conversations': sidebar_conversations,
        'active_conversation': active_convo_data,
        'user': request.user,
        'item_id': item_id,
        'recipient_id': recipient_id,
    })

def send_message(request, item_id, recipient_id):
    item = get_object_or_404(Item, id=item_id)
    recipient = get_object_or_404(User, id=recipient_id)


    # Conversation: all messages between these two users about this item, not deleted for this user
    conversation = Message.objects.filter(
        item=item,
        sender__in=[request.user, recipient],
        recipient__in=[request.user, recipient]
    ).exclude(
        sender=request.user, deleted_by_sender=True
    ).exclude(
        recipient=request.user, deleted_by_recipient=True
    ).order_by('timestamp')

    # Soft clear conversation for this user only
    if request.method == 'POST' and 'clear_conversation' in request.POST:
        # Mark as deleted for this user
        Message.objects.filter(
            item=item,
            sender__in=[request.user, recipient],
            recipient__in=[request.user, recipient]
        ).filter(sender=request.user).update(deleted_by_sender=True)
        Message.objects.filter(
            item=item,
            sender__in=[request.user, recipient],
            recipient__in=[request.user, recipient]
        ).filter(recipient=request.user).update(deleted_by_recipient=True)
        messages.success(request, 'Conversation cleared!')
        return redirect('send_message', item_id=item.id, recipient_id=recipient.id)

    if request.method == 'POST' and 'clear_conversation' not in request.POST:
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                item=item,
                content=form.cleaned_data['message']
            )
            messages.success(request, 'Message sent!')
            return redirect('send_message', item_id=item.id, recipient_id=recipient.id)
    else:
        form = MessageForm()
    return render(request, 'FindIt/send_message.html', {
        'form': form,
        'item': item,
        'recipient': recipient,
        'conversation': conversation,
    })

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import UserProfile
from .forms import UserProfileForm


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
        profile.profile_picture.delete(save=False)
        profile.profile_picture = None
        profile.save()
    return redirect('profile')


from .models import AccountDeletionFeedback
from django.contrib import messages
from django.contrib.auth import logout
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
    from .models import RecoveredItem
    recovered_items = RecoveredItem.objects.filter(owner=request.user).select_related('item', 'finder')
    return render(request, 'FindIt/my_recovered_items.html', {
        'recovered_items': recovered_items
    })


# My Returned Items - items that finder returned to owners
@login_required
def my_returned_items(request):
    from .models import RecoveredItem
    returned_items = RecoveredItem.objects.filter(finder=request.user).select_related('item', 'owner')
    return render(request, 'FindIt/my_returned_items.html', {
        'returned_items': returned_items
    })


# Rate the finder who returned the item
@login_required
def rate_finder(request, item_id):
    from .models import RecoveredItem
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
                    print(f"Email notification failed: {e}")
            
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
    from .models import RecoveredItem
    from django.db.models import Avg, Count, Q
    from datetime import timedelta
    
    # Overall statistics
    total_recovered = RecoveredItem.objects.count()
    total_rated = RecoveredItem.objects.filter(rating__isnull=False).count()
    avg_rating = RecoveredItem.objects.filter(rating__isnull=False).aggregate(Avg('rating'))['rating__avg'] or 0
    
    # User-specific statistics
    user_recovered = RecoveredItem.objects.filter(owner=request.user).count()
    user_returned = RecoveredItem.objects.filter(finder=request.user).count()
    user_avg_rating = RecoveredItem.objects.filter(finder=request.user, rating__isnull=False).aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_recovered = RecoveredItem.objects.filter(recovered_date__gte=thirty_days_ago).count()
    
    # Top finders (users with highest reputation)
    from django.contrib.auth.models import User
    top_finders = UserProfile.objects.filter(
        total_returns__gt=0
    ).select_related('user').order_by('-reputation_score', '-total_returns')[:10]
    
    # Rating distribution
    rating_distribution = {
        '5': RecoveredItem.objects.filter(rating=5).count(),
        '4': RecoveredItem.objects.filter(rating=4).count(),
        '3': RecoveredItem.objects.filter(rating=3).count(),
        '2': RecoveredItem.objects.filter(rating=2).count(),
        '1': RecoveredItem.objects.filter(rating=1).count(),
    }
    
    # Recent recoveries
    recent_recoveries = RecoveredItem.objects.select_related(
        'item', 'owner', 'finder'
    ).order_by('-recovered_date')[:10]
    
    # Monthly statistics (last 6 months)
    from django.db.models.functions import TruncMonth
    monthly_stats = RecoveredItem.objects.filter(
        recovered_date__gte=timezone.now() - timedelta(days=180)
    ).annotate(
        month=TruncMonth('recovered_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    context = {
        'total_recovered': total_recovered,
        'total_rated': total_rated,
        'avg_rating': round(avg_rating, 2),
        'user_recovered': user_recovered,
        'user_returned': user_returned,
        'user_avg_rating': round(user_avg_rating, 2),
        'recent_recovered': recent_recovered,
        'top_finders': top_finders,
        'rating_distribution': rating_distribution,
        'recent_recoveries': recent_recoveries,
        'monthly_stats': monthly_stats,
    }
    
    return render(request, 'FindIt/returns_statistics.html', context)


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
    from .models import RecoveredItem
    
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


@login_required
@require_POST
def clear_conversation(request):
    """Archive conversation - soft delete for current user while preserving for reference"""
    import json
    from django.http import JsonResponse
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        recipient_id = data.get('recipient_id')
        
        if not item_id or not recipient_id:
            return JsonResponse({'success': False, 'error': 'Missing item_id or recipient_id'}, status=400)
        
        item = get_object_or_404(Item, id=item_id)
        recipient = get_object_or_404(User, id=recipient_id)
        
        # Soft delete: Mark messages as deleted for current user only
        # Messages sent by current user
        sender_messages = Message.objects.filter(
            item=item,
            sender=request.user,
            recipient=recipient
        )
        sender_count = sender_messages.update(deleted_by_sender=True)
        
        # Messages received by current user
        recipient_messages = Message.objects.filter(
            item=item,
            sender=recipient,
            recipient=request.user
        )
        recipient_count = recipient_messages.update(deleted_by_recipient=True)
        
        total_archived = sender_count + recipient_count
        
        return JsonResponse({
            'success': True, 
            'message': f'Conversation archived ({total_archived} messages hidden)',
            'archived_count': total_archived
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



