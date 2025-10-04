from django.contrib import admin
from .models import UserProfile, Item, ItemCategory, Message, RecoveredItem

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'contact_number')

@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
	list_display = ('name',)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
	list_display = ('title', 'status', 'category', 'location', 'date_reported', 'reported_by')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ('sender', 'recipient', 'item', 'timestamp', 'is_read')

@admin.register(RecoveredItem)
class RecoveredItemAdmin(admin.ModelAdmin):
	list_display = ('item', 'owner', 'finder', 'recovered_date', 'rating', 'rated_at')
	list_filter = ('recovered_date', 'rating')
	search_fields = ('item__title', 'owner__username', 'finder__username')
	readonly_fields = ('recovered_date', 'original_report_date')
