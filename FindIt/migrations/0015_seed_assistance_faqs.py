from django.db import migrations


TOPICS = [
    ('Report an item', 'Items', 'report, report an item, found an item, lost an item',
     'Choose Report in the navigation, enter the item title, description, category and location, select Lost or Found, and add a clear photo if possible. Keep identifying details private so the owner can use them to prove ownership.'),
    ('Search for an item', 'Items', 'search, search items, find an item, browse, missing',
     'Open the items page. Search by title, description or location, then narrow results by category and Lost or Found. Open a card to see details. Use Clear filters to start again.'),
    ('My claims', 'Claims', 'claim, claims, ownership, my claims',
     'Sign in and open an item, then choose Claim Ownership and provide proof. My claims lists your submissions and their status. The Claims received tab lists requests on your own reports. A reporter must review the evidence before approval.'),
    ('Appeal a claim', 'Claims', 'appeal, appeal a claim, rejected, denied, denial',
     'Open My claims. For a denied claim, choose Appeal with new evidence, explain the identifying details and submit. The reporter receives a notification. Appeals are unavailable once the item is returned or another claimant is approved.'),
    ('End a claim', 'Claims', 'end claim, end a claim, withdraw, cancel claim',
     'Open My claims, expand End this claim, and confirm. This permanently closes the request and keeps its history. You cannot reopen an ended claim. Completed returns cannot be ended this way.'),
    ('Notifications', 'Claims', 'notification, notifications, unread, mark as read',
     'Open Notifications using the bell in the navigation. New submissions and appeals notify the reporter; approvals and denials notify the claimant. View claim marks an alert read, or choose Mark as read. The unread badge refreshes every 30 seconds while the page is visible.'),
    ('Return an item', 'Returns', 'return, returned, otp, verification code, approved',
     'The reporter reviews claims and approves the verified owner. A verification code is sent to the claimant by email. At handover, the reporter uses Confirm Return With OTP on the item page. The code expires after 24 hours and works once. Do not put verification codes in this chat.'),
    ('Message a reporter', 'Messages', 'message, messages, inbox, contact reporter',
     'Sign in, open the item and choose Message Reporter to start a conversation. Continue it from Inbox. This assistance panel explains the site; it cannot read your conversations or contact anyone for you.'),
    ('Profile pictures', 'Account', 'profile, picture, avatar, photo, upload',
     'Open Profile and use the camera control to upload or remove your profile picture. If an upload or removal fails, retry later and contact the site administrator if the issue continues. Do not share account passwords or API keys here.'),
    ('Safety and privacy', 'Safety', 'safety, privacy, safe, scam',
     'Verify ownership before handing over an item, meet in a safe public location, and avoid sharing sensitive personal information. Read Safety & Terms for site guidance. NIULIZE gives general instructions and cannot verify a person or a claim.'),
    ('Hello', 'Getting started', 'hello, hi, help, habari, msaada',
     'Hello! I am NIULIZE, your RECLAIM FAQ guide. Ask about reporting or searching for items, claims, appeals, notifications, profile pictures, or returning an item. I cannot inspect private records or perform actions for you.'),
]


def seed(apps, schema_editor):
    faq = apps.get_model('FindIt', 'AssistanceFAQ')
    for title, category, keywords, response in TOPICS:
        faq.objects.using(schema_editor.connection.alias).get_or_create(
            title=title, defaults={'category': category, 'keywords': keywords, 'response': response},
        )


class Migration(migrations.Migration):
    dependencies = [('FindIt', '0014_assistancefaq')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
