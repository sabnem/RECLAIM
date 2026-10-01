from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Claim, Item
from .otp_delivery import deliver_claim_code, normalize_phone

AT_SETTINGS = dict(SMS_PROVIDER='africastalking', AFRICASTALKING_USERNAME='reclaim', AFRICASTALKING_API_KEY='key')


def at_response(status_code=101):
    return Mock(status_code=201, json=Mock(return_value={
        'SMSMessageData': {'Recipients': [{'statusCode': status_code, 'status': 'Success' if status_code == 101 else 'InvalidPhoneNumber'}]},
    }))


class OtpDeliveryTests(TestCase):
    def setUp(self):
        self.finder = User.objects.create_user('finder')
        self.claimant = User.objects.create_user('claimant', email='claimant@example.com')
        self.claimant.userprofile.contact_number = '0755 630 639'
        self.claimant.userprofile.save()
        self.item = Item.objects.create(title='Keys', description='Keys', location='Park', status='found', reported_by=self.finder)
        self.claim = Claim.objects.create(item=self.item, claimant=self.claimant, proof_text='Mine')

    def approve(self):
        self.client.force_login(self.finder)
        with patch('FindIt.models.secrets.randbelow', return_value=123456):
            response = self.client.post(reverse('review_claim', args=[self.claim.pk]), {'action': 'approve'}, follow=True)
        return [str(m) for m in get_messages(response.wsgi_request)] + [response.content.decode()]

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone('0755 630 639'), '+255755630639')
        self.assertEqual(normalize_phone('+255 755-630-639'), '+255755630639')
        self.assertEqual(normalize_phone('00255755630639'), '+255755630639')
        self.assertEqual(normalize_phone('255755630639'), '+255755630639')
        self.assertEqual(normalize_phone('755630639'), '+255755630639')
        self.assertEqual(normalize_phone('0712', country_code='254'), None)
        self.assertIsNone(normalize_phone(''))

    def test_email_delivery_never_shows_code_to_finder(self):
        output = self.approve()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('123456', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['claimant@example.com'])
        self.assertFalse(any('123456' in text for text in output))
        self.assertTrue(any('email (cl***@example.com)' in text for text in output))

    def test_failed_delivery_does_not_leak_code(self):
        self.claimant.email = ''
        self.claimant.save()
        output = self.approve()
        self.assertFalse(any('123456' in text for text in output))
        self.assertTrue(any('could not be delivered' in text for text in output))

    @override_settings(**AT_SETTINGS)
    def test_sms_sent_with_africastalking(self):
        with patch('FindIt.otp_delivery.requests.post', return_value=at_response()) as post:
            delivered, problems = deliver_claim_code(self.claim, '654321')
        self.assertEqual(delivered, ['email', 'SMS'])
        self.assertEqual(problems, [])
        _, kwargs = post.call_args
        self.assertEqual(kwargs['data']['to'], '+255755630639')
        self.assertIn('654321', kwargs['data']['message'])
        self.assertEqual(kwargs['headers']['apiKey'], 'key')

    @override_settings(**AT_SETTINGS)
    def test_rejected_sms_is_reported(self):
        with patch('FindIt.otp_delivery.requests.post', return_value=at_response(403)):
            delivered, problems = deliver_claim_code(self.claim, '654321')
        self.assertEqual(delivered, ['email'])
        self.assertIn('the SMS could not be sent', problems)

    @override_settings(SMS_PROVIDER='twilio', TWILIO_ACCOUNT_SID='AC1', TWILIO_AUTH_TOKEN='t', TWILIO_FROM_NUMBER='+15550001111')
    def test_sms_sent_with_twilio(self):
        with patch('FindIt.otp_delivery.requests.post', return_value=Mock(status_code=201)) as post:
            delivered, _ = deliver_claim_code(self.claim, '654321')
        self.assertIn('SMS', delivered)
        self.assertEqual(post.call_args.kwargs['data']['To'], '+255755630639')

    def test_claimant_can_resend_code_with_cooldown(self):
        self.approve()
        self.claim.refresh_from_db()
        old_hash = self.claim.verification_code_hash
        url = reverse('resend_claim_code', args=[self.claim.pk])
        self.client.force_login(self.claimant)
        self.client.post(url)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.verification_code_hash, old_hash)  # cooldown
        Claim.objects.filter(pk=self.claim.pk).update(verification_code_sent_at=timezone.now() - timedelta(minutes=2))
        mail.outbox.clear()
        self.client.post(url)
        self.claim.refresh_from_db()
        self.assertNotEqual(self.claim.verification_code_hash, old_hash)
        self.assertEqual(len(mail.outbox), 1)
        self.client.force_login(self.finder)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 405)
