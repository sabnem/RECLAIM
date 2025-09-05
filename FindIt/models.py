# Store account deletion feedback
 # Force migration detection
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
class AccountDeletionFeedback(models.Model):
	username = models.CharField(max_length=150)
	email = models.EmailField()
	reason = models.CharField(max_length=255, blank=True)
	other_reason = models.TextField(blank=True)
	submitted_at = models.DateTimeField(default=timezone.now)



class UserProfile(models.Model):
	address = models.CharField(max_length=255, blank=True, null=True)
	bio = models.TextField(blank=True, null=True)
	social_links = models.URLField(blank=True, null=True)
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	contact_number = models.CharField(max_length=20)
	profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
	notify_email = models.BooleanField(default=True)
	notify_sms = models.BooleanField(default=False)
	PROFILE_VISIBILITY_CHOICES = [
		('everyone', 'Everyone'),
		('registered', 'Registered Users'),
		('private', 'Only Me'),
	]
	profile_visibility = models.CharField(max_length=20, choices=PROFILE_VISIBILITY_CHOICES, default='everyone')
	contact_visibility = models.CharField(max_length=20, choices=PROFILE_VISIBILITY_CHOICES, default='registered')
	show_email = models.BooleanField(default=True, help_text='Allow others to see your email')
	show_phone = models.BooleanField(default=True, help_text='Allow others to see your phone number')
	show_items = models.BooleanField(default=True, help_text='Show your reported items to others')
	show_activity = models.BooleanField(default=True, help_text='Show your recent activity to others')
	allow_messages = models.BooleanField(default=True, help_text='Allow others to send you messages')

	def __str__(self):
		return f"{self.user.username} Profile"


# Reputation system: User reviews
class UserReview(models.Model):
	reviewer = models.ForeignKey(User, related_name='given_reviews', on_delete=models.CASCADE)
	reviewed = models.ForeignKey(User, related_name='received_reviews', on_delete=models.CASCADE)
	rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
	comment = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ('reviewer', 'reviewed')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
	if created:
		UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
	if hasattr(instance, 'userprofile'):
		instance.userprofile.save()

class ItemCategory(models.Model):
	name = models.CharField(max_length=50)

	def __str__(self):
		return self.name

class Item(models.Model):
	STATUS_CHOICES = [
		('lost', 'Lost'),
		('found', 'Found'),
	]
	title = models.CharField(max_length=100)
	description = models.TextField()
	category = models.ForeignKey(ItemCategory, on_delete=models.SET_NULL, null=True)
	location = models.CharField(max_length=100)
	photo = models.ImageField(upload_to='item_photos/', blank=True, null=True)
	status = models.CharField(max_length=5, choices=STATUS_CHOICES)
	date_reported = models.DateTimeField(auto_now_add=True)
	reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='items_reported')
	owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='items_owned')
	is_returned = models.BooleanField(default=False)

	def __str__(self):
		return f"{self.title} ({self.get_status_display()})"
# Trigger migration recreation


class Message(models.Model):
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
	item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='messages')
	content = models.TextField(blank=True)
	image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	is_read = models.BooleanField(default=False)
	deleted_by_sender = models.BooleanField(default=False)
	deleted_by_recipient = models.BooleanField(default=False)

	def __str__(self):
		return f"From {self.sender.username} to {self.recipient.username} about {self.item.title}"

# Return confirmation model
class ReturnConfirmation(models.Model):
	item = models.OneToOneField('Item', on_delete=models.CASCADE, related_name='return_confirmation')
	finder_confirmed = models.BooleanField(default=False)
	owner_confirmed = models.BooleanField(default=False)
	finder_photo = models.ImageField(upload_to='return_evidence/', blank=True, null=True)
	owner_photo = models.ImageField(upload_to='return_evidence/', blank=True, null=True)
	finder_signature = models.TextField(blank=True, null=True)  # Store base64 or SVG data
	owner_signature = models.TextField(blank=True, null=True)
	confirmed_at = models.DateTimeField(blank=True, null=True)

	def is_fully_confirmed(self):
		return self.finder_confirmed and self.owner_confirmed
