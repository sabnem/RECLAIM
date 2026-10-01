"""Shared navigation data for Django templates."""

from .models import ItemCategory


def categories_context(request):
    return {"categories": ItemCategory.objects.all()}


def unread_inbox_count(request):
    count = 0
    if request.user.is_authenticated:
        count = request.user.received_messages.filter(is_read=False).count()
    return {"unread_inbox_count": count}
