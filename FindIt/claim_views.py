"""Member claim tracking, appeals, and persistent notifications."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

from .forms import ClaimForm
from .models import Claim, ClaimEvent, Item


@login_required
def my_claims(request):
    received = request.GET.get('tab') == 'received'
    claims = Claim.objects.filter(item__reported_by=request.user) if received else Claim.objects.filter(claimant=request.user)
    claims = claims.select_related('item', 'claimant').prefetch_related('events').order_by('-updated_at')
    return render(request, 'FindIt/my_claims.html', {
        'page_obj': Paginator(claims, 12).get_page(request.GET.get('page')),
        'received': received,
    })


@login_required
@transaction.atomic
def appeal_claim(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id, claimant=request.user)
    item = get_object_or_404(Item.objects.select_for_update(), pk=claim.item_id)
    claim.refresh_from_db()
    if claim.status != Claim.STATUS_REJECTED or item.is_returned or item.claims.filter(status=Claim.STATUS_APPROVED).exists():
        messages.error(request, 'Only denied claims on available items can be appealed.')
        return redirect('my_claims')
    form = ClaimForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        # Preserve the previous evidence and review before replacing the current submission.
        if not claim.events.exists():
            ClaimEvent.objects.create(claim=claim, recipient=claim.claimant, actor=claim.reviewed_by,
                                      kind='rejected', text=claim.proof_text, read_at=timezone.now())
        claim.proof_text = form.cleaned_data['proof_text']
        if form.cleaned_data.get('proof_image'):
            claim.proof_image = form.cleaned_data['proof_image']
        claim.status = Claim.STATUS_PENDING
        claim.reviewed_by = None
        claim.reviewed_at = None
        claim.verification_code_hash = ''
        claim.verification_code_sent_at = None
        claim.verification_code_expires_at = None
        claim.verification_code_used_at = None
        claim.save()
        item.verification_status = 'CLAIMED'
        item.save(update_fields=['verification_status'])
        ClaimEvent.objects.create(claim=claim, recipient=item.reported_by, actor=request.user,
                                  kind='appealed', text=claim.proof_text)
        messages.success(request, 'Your appeal was sent for review. The reporter has been notified.')
        return redirect('my_claims')
    return render(request, 'FindIt/appeal_claim.html', {'claim': claim, 'form': form})


@login_required
@require_POST
@transaction.atomic
def end_claim(request, claim_id):
    claim = get_object_or_404(Claim, pk=claim_id, claimant=request.user)
    item = get_object_or_404(Item.objects.select_for_update(), pk=claim.item_id)
    claim.refresh_from_db()
    if claim.is_returned or item.is_returned or claim.status == Claim.STATUS_ENDED:
        messages.info(request, 'This claim is already closed.')
        return redirect('my_claims')
    claim.status = Claim.STATUS_ENDED
    claim.verification_code_hash = ''
    claim.verification_code_expires_at = None
    claim.save()
    if not item.claims.filter(status=Claim.STATUS_APPROVED).exists():
        item.verification_status = 'CLAIMED' if item.claims.filter(status=Claim.STATUS_PENDING).exists() else 'FOUND'
        item.save(update_fields=['verification_status'])
    ClaimEvent.objects.create(claim=claim, recipient=item.reported_by, actor=request.user, kind='ended')
    messages.success(request, 'Claim ended. Its history is kept, but it cannot be reopened.')
    return redirect('my_claims')


@login_required
@never_cache
def notifications(request):
    events = request.user.claim_notifications.select_related('claim__item', 'actor')
    return render(request, 'FindIt/notifications.html', {
        'page_obj': Paginator(events, 20).get_page(request.GET.get('page')),
    })


@login_required
@never_cache
def notification_count(request):
    return JsonResponse({'count': request.user.claim_notifications.filter(read_at__isnull=True).count()})


@login_required
@require_POST
def open_notification(request, event_id):
    event = get_object_or_404(ClaimEvent, pk=event_id, recipient=request.user)
    if event.read_at is None:
        event.read_at = timezone.now()
        event.save(update_fields=['read_at'])
    if event.claim.claimant_id == request.user.id:
        return redirect('my_claims')
    return redirect('manage_claims', item_id=event.claim.item_id)


@login_required
@require_POST
def mark_notification_read(request, event_id):
    event = get_object_or_404(ClaimEvent, pk=event_id, recipient=request.user)
    ClaimEvent.objects.filter(pk=event.pk, read_at__isnull=True).update(read_at=timezone.now())
    return redirect('notifications')
