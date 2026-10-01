from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Claim, ClaimEvent, Item, ItemCategory


class ClaimTrackingTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user('reporter', email='reporter@example.com')
        self.claimant = User.objects.create_user('claimant', email='claimant@example.com')
        self.other = User.objects.create_user('other')
        self.item = Item.objects.create(title='Bag', description='Blue bag', location='Library',
            status='found', category=ItemCategory.objects.create(name='Bags'), reported_by=self.reporter)

    def submit(self):
        self.client.force_login(self.claimant)
        self.client.post(reverse('submit_claim', args=[self.item.pk]), {'proof_text': 'My blue bag has initials inside.'})
        return Claim.objects.get(item=self.item)

    def test_submission_notification_and_duplicate_protection(self):
        claim = self.submit()
        event = ClaimEvent.objects.get(kind='submitted')
        self.assertEqual(event.recipient, self.reporter)
        self.client.post(reverse('submit_claim', args=[self.item.pk]), {'proof_text': 'Duplicate'})
        self.assertEqual(ClaimEvent.objects.count(), 1)
        self.assertEqual(Claim.objects.count(), 1)
        self.assertContains(self.client.get(reverse('my_claims')), self.item.title)
        self.client.force_login(self.other)
        self.assertEqual(len(self.client.get(reverse('my_claims')).context['page_obj']), 0)
        self.assertEqual(self.client.post(reverse('open_notification', args=[event.pk])).status_code, 404)
        self.client.force_login(self.reporter)
        self.assertEqual(self.client.get(reverse('notification_count')).json()['count'], 1)
        self.assertContains(self.client.get(reverse('my_claims')+'?tab=received'), self.item.title)
        self.assertRedirects(self.client.post(reverse('open_notification', args=[event.pk])), reverse('manage_claims', args=[self.item.pk]))
        event.refresh_from_db()
        self.assertIsNotNone(event.read_at)

    def test_denial_appeal_and_end_history(self):
        claim = self.submit()
        self.client.force_login(self.reporter)
        self.client.post(reverse('review_claim', args=[claim.pk]), {'action':'reject', 'reason':'Please describe the contents.'})
        self.assertTrue(ClaimEvent.objects.filter(kind='rejected', recipient=self.claimant).exists())
        self.client.force_login(self.claimant)
        self.assertContains(self.client.get(reverse('my_claims')), 'Please describe the contents.')
        self.client.post(reverse('appeal_claim', args=[claim.pk]), {'proof_text':'A notebook with my initials is inside.'})
        claim.refresh_from_db()
        self.assertEqual(claim.status, Claim.STATUS_PENDING)
        self.assertTrue(ClaimEvent.objects.filter(kind='appealed',recipient=self.reporter).exists())
        self.client.post(reverse('end_claim',args=[claim.pk]))
        self.client.post(reverse('appeal_claim',args=[claim.pk]),{'proof_text':'Reopen'})
        self.client.post(reverse('submit_claim',args=[self.item.pk]),{'proof_text':'Reopen'})
        claim.refresh_from_db()
        self.assertEqual(claim.status,Claim.STATUS_ENDED)
        self.assertEqual(ClaimEvent.objects.count(),4)
        self.client.force_login(self.reporter)
        self.client.post(reverse('review_claim',args=[claim.pk]),{'action':'approve'})
        claim.refresh_from_db()
        self.assertEqual(claim.status,Claim.STATUS_ENDED)

    def test_approval_notifies_and_end_invalidates_otp(self):
        claim=self.submit()
        self.client.force_login(self.reporter)
        self.client.post(reverse('review_claim',args=[claim.pk]),{'action':'approve'})
        self.assertTrue(ClaimEvent.objects.filter(kind='approved',recipient=self.claimant).exists())
        self.client.force_login(self.claimant)
        self.client.post(reverse('end_claim',args=[claim.pk]))
        claim.refresh_from_db(); self.item.refresh_from_db()
        self.assertFalse(claim.code_is_active())
        self.assertEqual(self.item.verification_status,'FOUND')

    def test_mark_read_is_private_post_only_and_idempotent(self):
        self.submit()
        event = ClaimEvent.objects.get(kind='submitted')
        url = reverse('mark_notification_read', args=[event.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.reporter)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertContains(self.client.get(reverse('notifications')), 'Mark as read')
        self.assertRedirects(self.client.post(url), reverse('notifications'))
        event.refresh_from_db()
        first_read = event.read_at
        self.client.post(url)
        event.refresh_from_db()
        self.assertEqual(event.read_at, first_read)
        self.assertIsNotNone(first_read)
        response = self.client.get(reverse('notifications'))
        self.assertContains(response, 'claim-read')
        self.assertNotContains(response, 'Mark as read')
        self.assertEqual(self.client.get(reverse('notification_count')).json()['count'], 0)

    def test_permissions_post_only_and_returned_item(self):
        claim=self.submit()
        self.assertEqual(self.client.get(reverse('end_claim',args=[claim.pk])).status_code,405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('end_claim',args=[claim.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('appeal_claim',args=[claim.pk])).status_code,404)
        self.client.force_login(self.claimant)
        self.item.is_returned=True; self.item.save()
        self.client.post(reverse('end_claim',args=[claim.pk]))
        claim.refresh_from_db(); self.assertEqual(claim.status,Claim.STATUS_PENDING)
