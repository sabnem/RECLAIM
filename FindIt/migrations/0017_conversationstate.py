import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def move_legacy_archives(apps, schema_editor):
    """Archiving used to set every message's per-user deleted flag; keep those chats archived."""
    Message = apps.get_model('FindIt', 'Message')
    ConversationState = apps.get_model('FindIt', 'ConversationState')
    conversations = {}
    for message in Message.objects.only('id', 'item_id', 'sender_id', 'recipient_id', 'deleted_by_sender', 'deleted_by_recipient'):
        for user_id, other_id, hidden in (
            (message.sender_id, message.recipient_id, message.deleted_by_sender),
            (message.recipient_id, message.sender_id, message.deleted_by_recipient),
        ):
            key = (user_id, message.item_id, other_id)
            conversations.setdefault(key, []).append((message.id, hidden, user_id == message.sender_id))
    for (user_id, item_id, other_id), rows in conversations.items():
        if not all(hidden for _, hidden, _ in rows):
            continue
        ConversationState.objects.get_or_create(
            user_id=user_id, item_id=item_id, other_user_id=other_id, defaults={'archived': True},
        )
        Message.objects.filter(id__in=[pk for pk, _, sent in rows if sent]).update(deleted_by_sender=False)
        Message.objects.filter(id__in=[pk for pk, _, sent in rows if not sent]).update(deleted_by_recipient=False)


class Migration(migrations.Migration):

    dependencies = [
        ('FindIt', '0016_assistancerequest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversationState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archived', models.BooleanField(default=False)),
                ('cleared_at', models.DateTimeField(blank=True, null=True)),
                ('hidden', models.BooleanField(default=False)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_states', to='FindIt.item')),
                ('other_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_states', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('user', 'item', 'other_user'), name='unique_conversation_state')],
            },
        ),
        migrations.RunPython(move_legacy_archives, migrations.RunPython.noop),
    ]
