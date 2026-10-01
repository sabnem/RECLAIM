"""Deliver claim verification codes to the claimant by email and SMS.

The code is only ever sent to the claimant. It is never shown to the finder or
written to logs, because the finder must receive it from the claimant at handover.
"""

import logging
import re

import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

SMS_TIMEOUT_SECONDS = 15
DEV_EMAIL_BACKENDS = (
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.filebased.EmailBackend',
    'django.core.mail.backends.dummy.EmailBackend',
)


class SmsError(Exception):
    pass


def mask_email(address):
    """er***@gmail.com — enough to recognise the inbox without exposing it."""
    if not address or '@' not in address:
        return ''
    name, domain = address.split('@', 1)
    return f'{name[:2]}***@{domain}'


def email_is_real():
    """False when Django only prints or discards emails (development backends)."""
    return settings.EMAIL_BACKEND not in DEV_EMAIL_BACKENDS


def normalize_phone(number, country_code=None):
    """Return an E.164 number such as +255755630639, or None if it cannot be used.

    Accepts local numbers with a leading 0 (0755 630 639), international ones
    with + or 00, and bare country-code numbers (255755630639).
    """
    country_code = str(country_code or settings.SMS_DEFAULT_COUNTRY_CODE).lstrip('+')
    raw = (number or '').strip()
    digits = re.sub(r'\D', '', raw)
    if not digits:
        return None
    if raw.startswith('+'):
        pass
    elif digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = country_code + digits[1:]
    elif not digits.startswith(country_code):
        digits = country_code + digits
    return f'+{digits}' if 8 <= len(digits) <= 15 else None


def sms_enabled():
    return bool(settings.SMS_PROVIDER)


def send_sms(to, message):
    provider = settings.SMS_PROVIDER
    if provider == 'console':
        # Development only: mirrors Django's console email backend.
        print(f'--- SMS to {to} ---\n{message}\n---', flush=True)
        return
    try:
        if provider == 'africastalking':
            _send_africastalking(to, message)
        elif provider == 'twilio':
            _send_twilio(to, message)
        else:
            raise SmsError(f'Unknown SMS_PROVIDER "{provider}"')
    except requests.RequestException as exc:
        raise SmsError(f'{provider} request failed: {exc.__class__.__name__}') from exc


def _send_africastalking(to, message):
    username = settings.AFRICASTALKING_USERNAME
    if not username or not settings.AFRICASTALKING_API_KEY:
        raise SmsError("Africa's Talking username and API key are required")
    host = 'api.sandbox.africastalking.com' if username == 'sandbox' else 'api.africastalking.com'
    data = {'username': username, 'to': to, 'message': message}
    if settings.AFRICASTALKING_SENDER_ID:
        data['from'] = settings.AFRICASTALKING_SENDER_ID
    response = requests.post(
        f'https://{host}/version1/messaging',
        data=data,
        headers={'apiKey': settings.AFRICASTALKING_API_KEY, 'Accept': 'application/json'},
        timeout=SMS_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise SmsError(f"Africa's Talking returned HTTP {response.status_code}")
    recipients = response.json().get('SMSMessageData', {}).get('Recipients', [])
    # statusCode 100/101/102 = processed/sent/queued.
    accepted = recipients and (recipients[0].get('statusCode') in (100, 101, 102) or recipients[0].get('status') == 'Success')
    if not accepted:
        status = recipients[0].get('status') if recipients else 'no recipients accepted'
        raise SmsError(f"Africa's Talking rejected the message: {status}")


def _send_twilio(to, message):
    sid, token = settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
    if not sid or not token or not (settings.TWILIO_FROM_NUMBER or settings.TWILIO_MESSAGING_SERVICE_SID):
        raise SmsError('Twilio account SID, auth token and a sender are required')
    data = {'To': to, 'Body': message}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        data['MessagingServiceSid'] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        data['From'] = settings.TWILIO_FROM_NUMBER
    response = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
        data=data, auth=(sid, token), timeout=SMS_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise SmsError(f'Twilio returned HTTP {response.status_code}')


def deliver_claim_code(claim, code):
    """Send the code on every configured channel.

    Returns (delivered, problems): channel names that succeeded, and short
    reasons for channels that could not be used. Neither contains the code.
    """
    claimant = claim.claimant
    item_title = claim.item.title
    delivered, problems = [], []

    if claimant.email:
        try:
            send_mail(
                subject=f'Your verification code for {item_title}',
                message=(
                    f'Hello {claimant.username},\n\n'
                    f"Your claim for '{item_title}' was approved.\n"
                    f'Your 6-digit verification code is: {code}\n\n'
                    'Give this code to the finder only when you receive your item. '
                    'It expires in 24 hours and can only be used once.\n\n'
                    'If you did not make this claim, ignore this email.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[claimant.email],
                fail_silently=False,
            )
            delivered.append('email')
            if not email_is_real():
                problems.append('email is using a development backend, so it was only printed on the server')
        except Exception as exc:
            logger.error('Verification email failed for claim %s: %s', claim.id, exc.__class__.__name__)
            problems.append('the email could not be sent')
    else:
        problems.append('the claimant has no email address')

    if sms_enabled():
        profile = getattr(claimant, 'userprofile', None)
        phone = normalize_phone(profile.contact_number if profile else '')
        if not phone:
            problems.append('the claimant has no valid phone number')
        else:
            try:
                send_sms(phone, f'RECLAIM: your verification code for "{item_title[:40]}" is {code}. '
                                'Share it only at handover. Expires in 24h.')
                delivered.append('SMS')
            except SmsError as exc:
                logger.error('Verification SMS failed for claim %s: %s', claim.id, exc)
                problems.append('the SMS could not be sent')

    return delivered, problems
