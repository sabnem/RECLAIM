from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

# Mark item as returned (owner or superuser only)
@login_required
def mark_item_returned(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.user == item.reported_by or request.user.is_superuser:
        owner_username = request.POST.get('owner_username')
        if owner_username and not item.is_returned:
            try:
                owner_user = User.objects.get(username=owner_username)
                item.owner = owner_user
            except User.DoesNotExist:
                messages.error(request, f"User '{owner_username}' does not exist.")
                return redirect('item_detail', item_id=item.id)
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
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    items = Item.objects.all().order_by('-date_reported')
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
    confirmation = getattr(item, 'return_confirmation', None)
    if not confirmation:
        from .models import ReturnConfirmation
        confirmation = ReturnConfirmation.objects.create(item=item)
    return render(request, 'FindIt/item_detail.html', {
        'item': item,
        'confirmation': confirmation,
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

    # Handle sending a message
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

    # Get all conversations for the sidebar
    conversations = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
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
        active_messages = Message.objects.filter(
            item=item,
            sender__in=[request.user, recipient],
            recipient__in=[request.user, recipient]
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