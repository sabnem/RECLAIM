import os
import sys
import django
from django.utils import timezone

# Ensure project root is on sys.path when running from scripts/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lost_and_found.settings')
django.setup()

from django.contrib.auth import get_user_model
from FindIt.models import Item, Claim, ReturnConfirmation, RecoveredItem

User = get_user_model()

print('Starting E2E return flow test')

# Create or get users
finder, created = User.objects.get_or_create(username='finder_user', defaults={'email': 'finder@example.com'})
if created:
    finder.set_password('finderpass')
    finder.save()

claimant, created = User.objects.get_or_create(username='NEMO', defaults={'email': 'nemo@example.com'})
if created:
    claimant.set_password('Joyce@2003')
    claimant.save()

# Create a test item reported by finder
item = Item.objects.create(
    title='E2E Test Item',
    description='Item used for automated E2E return test',
    category=None,
    location='Test Location',
    status='found',
    reported_by=finder,
)
print(f'Created item id={item.id} title={item.title}')

# Submit a claim by claimant
claim = Claim.objects.create(item=item, claimant=claimant, proof_text='I can prove this is mine')
print(f'Created claim id={claim.id} status={claim.status} claimant={claim.claimant.username}')

# Approve the claim as finder
claim.status = Claim.STATUS_APPROVED
claim.reviewed_by = finder
claim.reviewed_at = timezone.now()
claim.save()
print('Claim approved; generating OTP...')

# Generate verification code (OTP)
code = claim.generate_verification_code()
print(f'Generated OTP: {code}')

# Verify code (simulate finder entering code)
valid = claim.verify_code(code)
print(f'Verify code returned: {valid}')

if valid:
    # Mark returned
    claim.mark_returned()
    item.mark_as_returned(owner=claimant)
    ReturnConfirmation.objects.create(
        claim=claim,
        item=item,
        finder=finder,
        claimant=claimant,
        entered_claimant_username=claimant.username,
        is_valid=True,
        confirmed_by=finder,
    )
    RecoveredItem.objects.create(
        item=item,
        owner=claimant,
        finder=finder,
        original_report_date=item.date_reported,
        location=item.location,
    )
    print('Return flow completed: item marked returned and records created')
else:
    print('OTP verification failed; aborting')

# Final checks
claim.refresh_from_db()
item.refresh_from_db()
print('Claim is_returned:', claim.is_returned)
print('Item is_returned:', item.is_returned)
print('Item owner:', item.owner.username)

print('E2E test finished')
