"""Regression coverage for the application's existing public workflows."""

import json
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Claim, Item, ItemCategory, Message, RecoveredItem, ReturnConfirmation
from .consumers import ChatConsumer
from .selectors import return_statistics_for


class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.finder = User.objects.create_user("finder", email="finder@example.com", password="test-password")
        cls.owner = User.objects.create_user("owner", email="owner@example.com", password="test-password")
        cls.other = User.objects.create_user("other", password="test-password")
        cls.category = ItemCategory.objects.create(name="Electronics")
        cls.item = Item.objects.create(
            title="Blue headphones", description="Found at the library", location="Library",
            category=cls.category, status="found", reported_by=cls.finder,
        )

    def test_public_pages(self):
        for name in ["home", "item_list", "login", "register", "report_item", "privacy_policy", "terms_and_conditions"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_account_pages_require_login(self):
        for name in ["inbox", "profile", "edit_profile", "my_recovered_items", "my_returned_items", "returns_statistics"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_authenticated_pages(self):
        self.client.force_login(self.owner)
        for name in ["inbox", "profile", "edit_profile", "report_item", "my_recovered_items", "my_returned_items", "returns_statistics"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_registration_creates_profile_and_hashes_password(self):
        response = self.client.post(reverse("register"), {
            "username": "new-member", "first_name": "New", "last_name": "Member",
            "email": "new@example.com", "password": "test-password", "contact_number": "0700000000",
        })
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="new-member")
        self.assertTrue(user.check_password("test-password"))
        self.assertEqual(user.userprofile.contact_number, "0700000000")

    def test_login_and_logout(self):
        self.assertRedirects(self.client.post(reverse("login"), {"username": "owner", "password": "test-password"}), reverse("home"))
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("logout")), reverse("home"))

    def test_item_search_and_filters(self):
        response = self.client.get(reverse("item_list"), {"q": "library", "category": self.category.pk, "status": "found"})
        self.assertContains(response, self.item.title)
        response = self.client.get(reverse("item_list"), {"status": "lost"})
        self.assertNotContains(response, self.item.title)

    def test_report_item(self):
        self.client.force_login(self.finder)
        response = self.client.post(reverse("report_item"), {
            "title": "Keys", "description": "Two keys", "location": "Park", "status": "found", "category": self.category.pk,
        })
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(Item.objects.filter(title="Keys", reported_by=self.finder).exists())

    def complete_return(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("submit_claim", args=[self.item.pk]), {"proof_text": "My initials are inside the case."})
        claim = Claim.objects.get(item=self.item, claimant=self.owner)
        self.client.force_login(self.finder)
        with patch("FindIt.models.secrets.randbelow", return_value=123456):
            self.client.post(reverse("review_claim", args=[claim.pk]), {"action": "approve"})
        self.assertTrue(mail.outbox)
        response = self.client.post(reverse("mark_item_returned", args=[self.item.pk]), {
            "claimant_username": self.owner.username, "verification_code": "123456",
        })
        self.assertEqual(response.status_code, 302)
        return claim

    def test_claim_approval_otp_return_and_archives(self):
        claim = self.complete_return()
        claim.refresh_from_db(); self.item.refresh_from_db()
        self.assertTrue(self.item.is_returned)
        self.assertEqual(self.item.owner_id, self.owner.pk)
        self.assertTrue(ReturnConfirmation.objects.filter(claim=claim, is_valid=True).exists())
        self.assertFalse(claim.verify_code("123456"))
        self.assertNotContains(self.client.get(reverse("item_list")), self.item.title)
        self.assertContains(self.client.get(reverse("my_returned_items")), self.item.title)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("my_recovered_items")), self.item.title)

    def test_claim_cannot_be_approved_by_another_user(self):
        claim = Claim.objects.create(item=self.item, claimant=self.owner, proof_text="Proof")
        self.client.force_login(self.other)
        self.client.post(reverse("review_claim", args=[claim.pk]), {"action": "approve"})
        claim.refresh_from_db()
        self.assertEqual(claim.status, Claim.STATUS_PENDING)

    def test_expired_code_is_rejected(self):
        claim = Claim.objects.create(item=self.item, claimant=self.owner, proof_text="Proof")
        code = claim.generate_verification_code()
        claim.verification_code_expires_at = timezone.now() - timedelta(seconds=1)
        claim.save()
        self.assertFalse(claim.verify_code(code))

    def test_rating_statistics_and_pdf(self):
        self.complete_return()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("rate_finder", args=[self.item.pk]), {"rating": "4", "feedback": "Thank you"})
        self.assertEqual(response.status_code, 302)
        self.finder.userprofile.refresh_from_db()
        self.assertEqual(self.finder.userprofile.reputation_score, 4)
        self.assertEqual(self.finder.userprofile.total_returns, 1)
        stats = self.client.get(reverse("returns_statistics"))
        self.assertEqual(stats.context["total_recovered"], 1)
        self.assertEqual(stats.context["avg_rating"], 4)
        self.assertEqual(stats.context["user_recovered"], 1)
        self.assertEqual(stats.context["rating_distribution"]["4"], 1)
        report = self.client.get(reverse("export_recovered_items_pdf"))
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.content.startswith(b"%PDF"))

    def test_message_edit_and_delete_permissions(self):
        message = Message.objects.create(item=self.item, sender=self.finder, recipient=self.owner, content="Hello")
        self.client.force_login(self.other)
        payload = {"message_id": message.pk, "new_content": "Changed"}
        self.assertEqual(self.client.post(reverse("edit_message"), json.dumps(payload), content_type="application/json").status_code, 403)
        self.client.force_login(self.finder)
        self.assertEqual(self.client.post(reverse("edit_message"), json.dumps(payload), content_type="application/json").status_code, 200)
        message.refresh_from_db(); self.assertEqual(message.content, "Changed")
        self.client.force_login(self.owner)
        payload = {"message_id": message.pk, "for_everyone": True}
        self.assertEqual(self.client.post(reverse("delete_message"), json.dumps(payload), content_type="application/json").status_code, 403)
        payload["for_everyone"] = False
        self.assertEqual(self.client.post(reverse("delete_message"), json.dumps(payload), content_type="application/json").status_code, 200)
        message.refresh_from_db()
        self.assertTrue(message.deleted_by_recipient)
        self.assertFalse(message.deleted_by_sender)

    def test_reputation_empty_and_mixed_ratings(self):
        profile = self.finder.userprofile
        profile.update_reputation()
        self.assertEqual(profile.reputation_score, 0)
        RecoveredItem.objects.create(item=self.item, owner=self.owner, finder=self.finder, original_report_date=self.item.date_reported, location="Library", rating=5)
        second = Item.objects.create(title="Keys", description="Keys", location="Park", status="found", reported_by=self.finder)
        RecoveredItem.objects.create(item=second, owner=self.owner, finder=self.finder, original_report_date=second.date_reported, location="Park")
        profile.update_reputation()
        self.assertEqual((profile.total_returns, profile.total_ratings, profile.reputation_score), (2, 1, 5))

    def test_statistics_query_budget_and_empty_values(self):
        with self.assertNumQueries(2):
            result = return_statistics_for(self.owner)
        self.assertEqual(result["total_recovered"], 0)
        self.assertEqual(result["avg_rating"], 0)
        self.assertEqual(result["rating_distribution"], {str(n): 0 for n in range(5, 0, -1)})

    def test_reputation_query_budget(self):
        profile = self.finder.userprofile
        with self.assertNumQueries(2):
            profile.update_reputation()

    def test_conversation_archive_and_restore(self):
        message = Message.objects.create(item=self.item, sender=self.finder, recipient=self.owner, content="Hello")
        self.client.force_login(self.owner)
        payload = {"item_id": self.item.pk, "recipient_id": self.finder.pk, "action": "archive"}
        response = self.client.post(reverse("clear_conversation"), json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertTrue(message.deleted_by_recipient)
        self.assertFalse(message.deleted_by_sender)
        payload["action"] = "unarchive"
        self.assertEqual(self.client.post(reverse("clear_conversation"), json.dumps(payload), content_type="application/json").status_code, 200)
        message.refresh_from_db()
        self.assertFalse(message.deleted_by_recipient)


class ChatTests(TransactionTestCase):
    def test_websocket_message_typing_edit_and_delete(self):
        sender = User.objects.create_user("chat-sender")
        recipient = User.objects.create_user("chat-recipient")
        item = Item.objects.create(title="Keys", description="Keys", location="Park", status="found", reported_by=sender)

        async def round_trip():
            socket = WebsocketCommunicator(ChatConsumer.as_asgi(), "/ws/chat/test/")
            socket.scope["user"] = sender
            socket.scope["url_route"] = {"kwargs": {"conversation_id": f"{item.pk}-{sender.pk}-{recipient.pk}"}}
            connected, _ = await socket.connect()
            self.assertTrue(connected)
            try:
                await socket.send_json_to({"message": "Hello", "sender_id": sender.pk, "recipient_id": recipient.pk, "item_id": item.pk})
                event = await socket.receive_json_from()
                self.assertEqual(event["message"], "Hello")
                message_id = event["message_id"]
                await socket.send_json_to({"type": "typing", "sender_id": sender.pk, "sender_username": sender.username, "is_typing": True})
                self.assertEqual((await socket.receive_json_from())["type"], "typing")
                await socket.send_json_to({"type": "edit", "message_id": message_id, "sender_id": sender.pk, "new_content": "Updated"})
                self.assertEqual((await socket.receive_json_from())["new_content"], "Updated")
                await socket.send_json_to({"type": "delete", "message_id": message_id, "sender_id": sender.pk, "for_everyone": True})
                self.assertEqual((await socket.receive_json_from())["type"], "message_deleted")
            finally:
                await socket.disconnect()

        async_to_sync(round_trip)()
        self.assertTrue(Message.objects.get(item=item).deleted_for_everyone)
