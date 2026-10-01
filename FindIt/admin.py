from django.contrib import admin
from .models import AssistanceFAQ, AssistanceRequest
from django.utils import timezone
from django.db import transaction


@admin.register(AssistanceFAQ)
class AssistanceFAQAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_active', 'priority')
    list_filter = ('is_active', 'category')
    search_fields = ('title', 'keywords', 'response')


class AssistanceAnsweredFilter(admin.SimpleListFilter):
    title = 'Answer status'
    parameter_name = 'answered'

    def lookups(self, request, model_admin):
        return [('no', 'Awaiting answer'), ('yes', 'Answered')]

    def queryset(self, request, queryset):
        if self.value() == 'no':
            return queryset.filter(answer='')
        if self.value() == 'yes':
            return queryset.exclude(answer='')
        return queryset


@admin.register(AssistanceRequest)
class AssistanceRequestAdmin(admin.ModelAdmin):
    list_display = ('question', 'user', 'created_at', 'answered_at')
    list_filter = (AssistanceAnsweredFilter,)
    search_fields = ('question', 'answer', 'user__username')
    readonly_fields = ('user', 'question', 'created_at', 'answered_at', 'answered_by', 'faq')
    fields = ('user', 'question', 'created_at', 'answer', 'answered_at', 'answered_by', 'faq')
    actions = ['create_faq_drafts']

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if 'answer' in form.changed_data:
            obj.answer = obj.answer.strip()
            obj.answered_at = timezone.now() if obj.answer else None
            obj.answered_by = request.user if obj.answer else None
        super().save_model(request, obj, form, change)

    @admin.action(description='Create inactive FAQ drafts from answered requests')
    def create_faq_drafts(self, request, queryset):
        if not request.user.has_perm('FindIt.add_assistancefaq'):
            self.message_user(request, 'You need permission to add FAQs.', level='error')
            return
        count = 0
        with transaction.atomic():
            for question in queryset.select_for_update().exclude(answer='').filter(faq__isnull=True):
                question.faq = AssistanceFAQ.objects.create(
                    title=f'Help request {question.pk}: {question.question[:150]}',
                    response=question.answer, keywords='', is_active=False,
                )
                question.save(update_fields=['faq'])
                count += 1
        self.message_user(request, f'{count} inactive FAQ draft(s) created. Edit the title, remove private details, add keywords, then activate.')
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
