
# Store account deletion feedback
# Force migration detection
import secrets
import uuid
from datetime import timedelta

from cloudinary.models import CloudinaryField
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
	
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
	profile_picture = CloudinaryField('image', blank=True, null=True)
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
	
	# Reputation fields
	reputation_score = models.FloatField(default=0.0, help_text='Average rating score')
	total_returns = models.IntegerField(default=0, help_text='Total items returned to owners')
	total_ratings = models.IntegerField(default=0, help_text='Total ratings received')

	def __str__(self):
		return f"{self.user.username} Profile"
	
	def update_reputation(self):
		"""Calculate and update reputation score based on ratings"""
		from .models import RecoveredItem
		ratings = RecoveredItem.objects.filter(finder=self.user, rating__isnull=False)
		if ratings.exists():
			total_rating = sum(r.rating for r in ratings)
			self.total_ratings = ratings.count()
			self.reputation_score = round(total_rating / self.total_ratings, 2)
		else:
			self.reputation_score = 0.0
			self.total_ratings = 0
		
		# Update total returns
		self.total_returns = RecoveredItem.objects.filter(finder=self.user).count()
		self.save()
	
	def get_reputation_badge(self):
		"""Get reputation badge based on score"""
		if self.reputation_score >= 4.5:
			return {'name': 'Hero', 'color': 'gold', 'icon': 'trophy-fill'}
		elif self.reputation_score >= 4.0:
			return {'name': 'Trusted', 'color': 'success', 'icon': 'patch-check-fill'}
		elif self.reputation_score >= 3.5:
			return {'name': 'Helpful', 'color': 'primary', 'icon': 'hand-thumbs-up-fill'}
		elif self.reputation_score >= 3.0:
			return {'name': 'Active', 'color': 'info', 'icon': 'star-fill'}
		else:
			return {'name': 'New', 'color': 'secondary', 'icon': 'person-fill'}


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
	RETURN_STATUS_CHOICES = [
		('FOUND', 'Found'),
		('CLAIMED', 'Claimed'),
		('VERIFIED', 'Verified'),
		('RETURNED', 'Returned'),
	]
	title = models.CharField(max_length=100)
	description = models.TextField()
	category = models.ForeignKey(ItemCategory, on_delete=models.SET_NULL, null=True)
	location = models.CharField(max_length=100)
	photo = CloudinaryField('image', blank=True, null=True)
	status = models.CharField(max_length=5, choices=STATUS_CHOICES)
	verification_status = models.CharField(max_length=20, choices=RETURN_STATUS_CHOICES, default='FOUND')
	date_reported = models.DateTimeField(auto_now_add=True)
	reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='items_reported')
	owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='items_owned')
	is_returned = models.BooleanField(default=False)
	returned_at = models.DateTimeField(blank=True, null=True)

	def __str__(self):
		return f"{self.title} ({self.get_status_display()})"

	def mark_as_claimed(self):
		self.verification_status = 'CLAIMED'
		self.save(update_fields=['verification_status'])

	def mark_as_verified(self):
		self.verification_status = 'VERIFIED'
		self.save(update_fields=['verification_status'])

	def mark_as_returned(self, owner=None):
		update_fields = ['verification_status', 'is_returned', 'returned_at']
		self.verification_status = 'RETURNED'
		self.is_returned = True
		self.returned_at = timezone.now()
		if owner:
			self.owner = owner
			update_fields.append('owner')
		self.save(update_fields=update_fields)
# Trigger migration recreation


class Message(models.Model):
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
	item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='messages')
	content = models.TextField(blank=True)
	image = CloudinaryField('image', blank=True, null=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	is_read = models.BooleanField(default=False)
	deleted_by_sender = models.BooleanField(default=False)
	deleted_by_recipient = models.BooleanField(default=False)
	# New fields for edit/delete features
	edited = models.BooleanField(default=False)
	edited_at = models.DateTimeField(blank=True, null=True)
	deleted_for_everyone = models.BooleanField(default=False)
	deleted_at = models.DateTimeField(blank=True, null=True)
	deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='deleted_messages')

	def __str__(self):
		return f"From {self.sender.username} to {self.recipient.username} about {self.item.title}"


class Claim(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_APPROVED = 'approved'
	STATUS_REJECTED = 'rejected'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_APPROVED, 'Approved'),
		(STATUS_REJECTED, 'Rejected'),
	]

	item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='claims')
	claimant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='item_claims')
	proof_text = models.TextField()
	proof_image = CloudinaryField('image', blank=True, null=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_item_claims')
	reviewed_at = models.DateTimeField(blank=True, null=True)
	verification_code_hash = models.CharField(max_length=128, blank=True)
	verification_code_sent_at = models.DateTimeField(blank=True, null=True)
	verification_code_expires_at = models.DateTimeField(blank=True, null=True)
	verification_code_used_at = models.DateTimeField(blank=True, null=True)
	returned_at = models.DateTimeField(blank=True, null=True)
	is_returned = models.BooleanField(default=False)
	claim_reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.UniqueConstraint(
				fields=['item'],
				condition=Q(status='approved'),
				name='unique_approved_claim_per_item',
			),
		]

	def __str__(self):
		return f"{self.claimant.username} -> {self.item.title} ({self.get_status_display()})"

	def clean(self):
		if self.item_id and self.claimant_id and self.item.reported_by_id == self.claimant_id:
			raise ValidationError('The finder cannot claim their own item.')
		if self.item_id and self.item.is_returned:
			raise ValidationError('This item has already been returned.')

	def generate_verification_code(self):
		code = f"{secrets.randbelow(1000000):06d}"
		self.verification_code_hash = make_password(code)
		now = timezone.now()
		self.verification_code_sent_at = now
		self.verification_code_expires_at = now + timedelta(hours=24)
		self.verification_code_used_at = None
		self.save(update_fields=['verification_code_hash', 'verification_code_sent_at', 'verification_code_expires_at', 'verification_code_used_at', 'updated_at'])
		return code

	def code_is_active(self):
		return bool(self.verification_code_hash and not self.verification_code_used_at and self.verification_code_expires_at and timezone.now() <= self.verification_code_expires_at)

	def verify_code(self, raw_code):
		if not self.code_is_active():
			return False
		return check_password(raw_code, self.verification_code_hash)

	def mark_returned(self):
		self.is_returned = True
		self.returned_at = timezone.now()
		self.verification_code_used_at = timezone.now()
		self.status = self.STATUS_APPROVED
		self.save(update_fields=['is_returned', 'returned_at', 'verification_code_used_at', 'status', 'updated_at'])


class ReturnConfirmation(models.Model):
	claim = models.OneToOneField(Claim, on_delete=models.CASCADE, related_name='return_confirmation', null=True, blank=True)
	item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='return_confirmations', null=True, blank=True)
	finder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finder_return_confirmations', null=True, blank=True)
	claimant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='claimant_return_confirmations', null=True, blank=True)
	entered_claimant_username = models.CharField(max_length=150, blank=True)
	is_valid = models.BooleanField(default=False)
	confirmed_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
	confirmed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='confirmed_return_actions')
	notes = models.CharField(max_length=255, blank=True)

	def __str__(self):
		return f"Return confirmation for {self.item.title}"


# Recovered Items - items successfully returned to owner
class RecoveredItem(models.Model):
	item = models.OneToOneField('Item', on_delete=models.CASCADE, related_name='recovered_record')
	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recovered_items')
	finder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='returned_items')
	recovered_date = models.DateTimeField(auto_now_add=True)
	original_report_date = models.DateTimeField()
	location = models.CharField(max_length=100)
	
	# Rating and feedback from owner to finder
	rating = models.PositiveSmallIntegerField(
		choices=[(i, i) for i in range(1, 6)],
		null=True,
		blank=True,
		help_text='Rating from owner to finder (1-5 stars)'
	)
	feedback = models.TextField(
		blank=True,
		help_text='Feedback from owner about the return experience'
	)
	rated_at = models.DateTimeField(null=True, blank=True)
	
	class Meta:
		ordering = ['-recovered_date']
	
	def __str__(self):
		return f"{self.item.title} - Returned by {self.finder.username} to {self.owner.username}"
