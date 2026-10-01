from unittest.mock import patch

from cloudinary import CloudinaryResource
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class RemoveProfilePictureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('picture-owner')
        self.profile = self.user.userprofile
        self.profile.profile_picture = CloudinaryResource(
            public_id='profiles/avatar', resource_type='image', type='upload', format='jpg',
        )
        self.profile.save(update_fields=['profile_picture'])
        self.client.force_login(self.user)
        self.url = reverse('remove_profile_picture')

    @patch('FindIt.views.cloudinary.uploader.destroy', return_value={'result': 'ok'})
    def test_removes_cloudinary_asset_and_clears_reference(self, destroy):
        self.assertRedirects(self.client.post(self.url), reverse('profile'))
        destroy.assert_called_once_with('profiles/avatar', resource_type='image', type='upload', invalidate=True)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)
        self.client.post(self.url)
        self.assertEqual(destroy.call_count, 1)

    @patch('FindIt.views.cloudinary.uploader.destroy', return_value={'result': 'not found'})
    def test_already_missing_asset_clears_reference(self, destroy):
        self.client.post(self.url)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.profile_picture)

    @patch('FindIt.views.cloudinary.uploader.destroy')
    def test_failure_keeps_picture_and_shows_message(self, destroy):
        for result in [RuntimeError('Service unavailable'), {'result': 'error'}]:
            destroy.side_effect = result if isinstance(result, Exception) else None
            destroy.return_value = result
            response = self.client.post(self.url, follow=True)
            self.assertContains(response, 'Your picture could not be removed right now.')
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.profile_picture.public_id, 'profiles/avatar')

    @patch('FindIt.views.cloudinary.uploader.destroy')
    def test_requires_authenticated_post(self, destroy):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        destroy.assert_not_called()
