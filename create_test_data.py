#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lost_and_found.settings')
django.setup()

from django.contrib.auth.models import User
from FindIt.models import Item, ItemCategory

# Create Bob user
bob, created = User.objects.get_or_create(username='bob', defaults={
    'first_name': 'Bob',
    'last_name': 'Test',
    'email': 'bob@test.com',
    'is_active': True
})
if created:
    bob.set_password('bobpass123')
    bob.save()
    print(f"✅ Created user: bob")
else:
    print(f"ℹ️  User bob already exists")

# Get or create a category
cat, _ = ItemCategory.objects.get_or_create(name='Electronics')

# Create a test item reported by Bob
item, created = Item.objects.get_or_create(
    title='Lost iPhone 13',
    reported_by=bob,
    defaults={
        'description': 'Black iPhone 13 lost near central park',
        'category': cat,
        'location': 'Central Park',
        'status': 'lost'
    }
)
if created:
    print(f"✅ Created item: {item.title}")
else:
    print(f"ℹ️  Item already exists: {item.title}")

print(f"\n📋 Test data ready:")
print(f"  - Alice: alice / alicepass123")
print(f"  - Bob: bob / bobpass123")
print(f"  - Item: {item.title} (ID: {item.id}) reported by {item.reported_by.username}")
