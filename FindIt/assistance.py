"""NIULIZE FAQ matching adapted for RECLAIM; no external AI requests."""
import json
import re
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AssistanceFAQ, AssistanceRequest


def words(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


def find_best_match(message):
    query = words(message)
    if not query:
        return None
    best, best_score, runner_up = None, 0, 0
    # Complete phrases prevent accidental substring matches such as "hi" in "this".
    for faq in AssistanceFAQ.objects.filter(is_active=True).order_by('-priority', 'title'):
        score = 100 if query == words(faq.title) else 0
        for phrase in faq.keywords.split(','):
            phrase = words(phrase)
            if phrase and f' {phrase} ' in f' {query} ':
                score += 3 * len(phrase.split())
        if score > best_score:
            runner_up = best_score
            best, best_score = faq, score
        else:
            runner_up = max(runner_up, score)
    if best_score < 100 and (best_score == runner_up or (len(query.split()) > 4 and best_score < 6)):
        return None
    return best


def suggest_topics(message, exclude=None):
    """Offer nearby topics without presenting a weak match as an answer."""
    stop = {'i', 'my', 'the', 'a', 'an', 'to', 'is', 'it', 'how', 'do', 'can', 'what', 'and', 'of', 'in', 'on', 'for', 'me'}
    query = set(words(message).split()) - stop
    ranked = []
    for faq in AssistanceFAQ.objects.filter(is_active=True).exclude(pk=exclude).order_by('-priority', 'title'):
        tokens = set(words(faq.title + ' ' + faq.keywords).split()) - stop
        score = sum(max((SequenceMatcher(None, word, token).ratio() for token in tokens), default=0)
                    for word in query if any(SequenceMatcher(None, word, token).ratio() >= .8 for token in tokens))
        ranked.append((score, faq.title))
    ranked.sort(key=lambda row: -row[0])
    return [title for _, title in ranked[:3]]


@require_POST
def assistant_reply(request):
    if len(request.body) > 8192:
        return JsonResponse({'error': 'Please keep your question under 1,000 characters.'}, status=400)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Please send a valid question.'}, status=400)
    message = data.get('message') if isinstance(data, dict) else None
    if not isinstance(message, str) or not message.strip() or len(message) > 1000:
        return JsonResponse({'error': 'Enter a question between 1 and 1,000 characters.'}, status=400)
    faq = find_best_match(message)
    response = faq.response if faq else (
        "I couldn't match that question to a help topic. Try asking about reporting an item, "
        "searching, claims, appeals, notifications, profile pictures, or returning an item. "
        "I provide guidance, but cannot check private records or perform actions for you."
    )
    if not faq:
        response = ('I do not have a confirmed answer to that question. Did you mean one of the topics below? '
                    'You can also request an answer from an administrator.')
    return JsonResponse({'response': response, 'matched': bool(faq),
                         'suggestions': suggest_topics(message, faq.pk if faq else None)})


@require_POST
@transaction.atomic
def request_answer(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Sign in to request an answer.',
                             'login_url': reverse('login') + '?next=' + reverse('assistance_requests')}, status=401)
    if len(request.body) > 8192:
        return JsonResponse({'error': 'Please keep your question under 1,000 characters.'}, status=400)
    try:
        data = json.loads(request.body)
        question = data.get('message') if isinstance(data, dict) else None
    except (ValueError, UnicodeDecodeError):
        question = None
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        return JsonResponse({'error': 'Enter a question between 1 and 1,000 characters.'}, status=400)
    question = question.strip()
    # Serialize submissions per member to make duplicate and rate-limit checks reliable.
    User.objects.select_for_update().get(pk=request.user.pk)
    existing = request.user.assistance_requests.filter(question=question, answer='').first()
    if existing:
        return JsonResponse({'message': 'This question is already awaiting an answer.', 'url': reverse('assistance_requests')})
    if request.user.assistance_requests.filter(created_at__gte=timezone.now()-timedelta(days=1)).count() >= 5:
        return JsonResponse({'error': 'You can send up to five questions per day. Please check your existing requests.'}, status=429)
    AssistanceRequest.objects.create(user=request.user, question=question)
    return JsonResponse({'message': 'Question sent. Check My help requests for the administrator’s answer.',
                         'url': reverse('assistance_requests')}, status=201)


@login_required
def assistance_requests(request):
    requests = request.user.assistance_requests.select_related('answered_by')
    return render(request, 'FindIt/assistance_requests.html', {
        'page_obj': Paginator(requests, 15).get_page(request.GET.get('page')),
    })
