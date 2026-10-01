import json

from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from .assistance import find_best_match
from .models import AssistanceFAQ, AssistanceRequest


class AssistanceTests(TestCase):
    def test_seeded_help_topics_and_fallback(self):
        for question in ['Report an item', 'My claims', 'Appeal a claim', 'Notifications']:
            response = self.client.post(reverse('assistant_reply'), json.dumps({'message': question}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("couldn't match", response.json()['response'])
        self.assertIsNone(find_best_match('zzzz nonsense'))

    def test_validation_and_method(self):
        for data in ['[]', 'null', '{', '{"message": 42}', '{"message":""}', json.dumps({'message':'x'*1001})]:
            self.assertEqual(self.client.post(reverse('assistant_reply'), data, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.get(reverse('assistant_reply')).status_code, 405)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('assistant_reply'), json.dumps({'message':'Hello'}), content_type='application/json').status_code, 403)
        client.get(reverse('home'))
        self.assertEqual(client.post(reverse('assistant_reply'), json.dumps({'message':'Hello'}), content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)

    def test_matching_ignores_disabled_topics_and_substrings(self):
        AssistanceFAQ.objects.all().delete()
        AssistanceFAQ.objects.create(title='Greeting', keywords='hi', response='Hello')
        self.assertIsNone(find_best_match('this'))
        self.assertEqual(find_best_match('Hi!').response, 'Hello')
        AssistanceFAQ.objects.update(is_active=False)
        self.assertIsNone(find_best_match('hi'))


class AssistanceRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('help-user')
        self.client.force_login(self.user)

    def submit(self, question='How can I change the language?'):
        return self.client.post(reverse('request_answer'), json.dumps({'message':question}), content_type='application/json')

    def test_request_deduplication_privacy_and_limit(self):
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(AssistanceRequest.objects.count(), 1)
        self.assertContains(self.client.get(reverse('assistance_requests')), 'change the language')
        for index in range(4):
            self.assertEqual(self.submit(f'Other question {index}').status_code, 201)
        self.assertEqual(self.submit('One too many').status_code, 429)
        other = User.objects.create_user('different-user')
        self.client.force_login(other)
        self.assertEqual(len(self.client.get(reverse('assistance_requests')).context['page_obj']), 0)
        self.client.logout()
        self.assertEqual(self.submit().status_code, 401)
        self.assertEqual(self.client.get(reverse('assistance_requests')).status_code, 302)

    def test_validation_and_csrf(self):
        self.assertEqual(self.client.get(reverse('request_answer')).status_code, 405)
        for data in ['[]', '{', '{"message": 7}', json.dumps({'message':'x'*1001})]:
            self.assertEqual(self.client.post(reverse('request_answer'), data, content_type='application/json').status_code, 400)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('request_answer'), json.dumps({'message':'test'}), content_type='application/json').status_code, 403)

    def test_admin_answer_and_draft_publication(self):
        self.submit()
        question = AssistanceRequest.objects.get()
        admin = User.objects.create_superuser('help-admin', 'help@example.com', 'test-pass')
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:FindIt_assistancerequest_change', args=[question.pk]), {'answer':'This option is not available yet.', '_save':'Save'})
        self.assertEqual(response.status_code, 302)
        question.refresh_from_db()
        self.assertEqual(question.answered_by, admin)
        self.assertIsNotNone(question.answered_at)
        response = self.client.post(reverse('admin:FindIt_assistancerequest_changelist'), {'action':'create_faq_drafts', '_selected_action':[question.pk]})
        self.assertEqual(response.status_code, 302)
        question.refresh_from_db()
        self.assertFalse(question.faq.is_active)
        self.assertEqual(question.faq.keywords, '')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('assistance_requests')), 'This option is not available yet.')

    def test_unknown_questions_suggest_topics_without_creating_requests(self):
        response = self.client.post(reverse('assistant_reply'), json.dumps({'message':'notifcations'}), content_type='application/json').json()
        self.assertFalse(response['matched'])
        self.assertIn('Notifications', response['suggestions'])
        self.assertFalse(AssistanceRequest.objects.exists())
