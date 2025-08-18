from django.contrib.auth.decorators import login_required

# Mark item as returned (owner or superuser only)
@login_required
def mark_item_returned(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.user == item.reported_by or request.user.is_superuser:
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
from django.contrib.auth import authenticate, login, logout
from .forms import UserRegistrationForm, LoginForm, ItemForm, MessageForm
from django.contrib import messages
from .models import Item, ItemCategory, Message
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings

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
    return render(request, 'FindIt/item_detail.html', {'item': item})

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
    messages = request.user.received_messages.select_related('sender', 'item').order_by('-timestamp')
    return render(request, 'FindIt/inbox.html', {'messages': messages})

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
