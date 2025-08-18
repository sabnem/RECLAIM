from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	contact_number = models.CharField(max_length=20)
	profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

	def __str__(self):
		return f"{self.user.username} Profile"

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
	reported_by = models.ForeignKey(User, on_delete=models.CASCADE)
	is_returned = models.BooleanField(default=False)

	def __str__(self):
		return f"{self.title} ({self.get_status_display()})"
# Trigger migration recreation

class Message(models.Model):
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
	item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='messages')
	content = models.TextField()
	timestamp = models.DateTimeField(auto_now_add=True)
	is_read = models.BooleanField(default=False)
	deleted_by_sender = models.BooleanField(default=False)
	deleted_by_recipient = models.BooleanField(default=False)

	def __str__(self):
		return f"From {self.sender.username} to {self.recipient.username} about {self.item.title}"
