from django.contrib import admin
from .models import UserProfile, Item, ItemCategory, Message, RecoveredItem, Claim, ReturnConfirmation

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'contact_number')

@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
	list_display = ('name',)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
	list_display = ('title', 'status', 'verification_status', 'category', 'location', 'date_reported', 'reported_by')
	list_filter = ('status', 'verification_status', 'category', 'date_reported')
	search_fields = ('title', 'description', 'location', 'reported_by__username')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ('sender', 'recipient', 'item', 'timestamp', 'is_read')

@admin.register(RecoveredItem)
class RecoveredItemAdmin(admin.ModelAdmin):
	list_display = ('item', 'owner', 'finder', 'recovered_date', 'rating', 'rated_at')
	list_filter = ('recovered_date', 'rating')
	search_fields = ('item__title', 'owner__username', 'finder__username')
	readonly_fields = ('recovered_date', 'original_report_date')


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
	list_display = ('item', 'claimant', 'status', 'reviewed_by', 'created_at', 'returned_at')
	list_filter = ('status', 'created_at', 'reviewed_at')
	search_fields = ('item__title', 'claimant__username', 'proof_text')
	readonly_fields = ('claim_reference', 'created_at', 'updated_at', 'verification_code_hash', 'verification_code_sent_at', 'verification_code_expires_at', 'verification_code_used_at', 'returned_at')


@admin.register(ReturnConfirmation)
class ReturnConfirmationAdmin(admin.ModelAdmin):
	list_display = ('item', 'claimant', 'finder', 'confirmed_by', 'is_valid', 'confirmed_at')
	list_filter = ('is_valid', 'confirmed_at')
	search_fields = ('item__title', 'claimant__username', 'finder__username', 'entered_claimant_username')
