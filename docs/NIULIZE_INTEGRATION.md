# NIULIZE assistance in RECLAIM

Adapted from the user's [NIULIZE-CHATBOT](https://github.com/sabnem/NIULIZE-CHATBOT)
repository, inspected at commit `f3b5a9e59fd632e523d34f082edd0389db923284`.
The original Django FAQ model and keyword-scoring approach are the basis of
`AssistanceFAQ` and `FindIt/assistance.py`. This is an integrated adaptation,
not an iframe or a live connection to the original repository.

No separate hosting, LLM subscription or API key is needed. NIULIZE answers
from editable FAQ records and does not access private claims or messages.
It cannot take actions for users. Unknown questions receive a help-topic fallback.
The integration does not import the original SQLite database, login pages,
college FAQs, compiled files, or project settings. Ordinary chat text stays in
the current page's memory. If a signed-in member explicitly requests an answer,
that question is saved with their account for administrators to answer. No IP
logging is added.

Deploy the new code with `python manage.py migrate --noinput` and
`python manage.py collectstatic --noinput`. The migrations create the FAQ table
and initial RECLAIM help topics. Edit responses, keywords, priorities, and active
status under **Django admin → Assistance FAQs**. Topics are matched by complete
words/phrases; ambiguous or weak matches offer clarification topics. Responses are displayed
as plain text to prevent HTML injection.

The floating Need help button opens an accessible modal dialog: Escape closes
it, keyboard focus stays inside and returns to the button, and both color themes
and small screens are supported. The endpoint uses same-origin CSRF-protected
POST requests with bounded input. Browser errors keep the question for retry.

## Unanswered questions

Related-topic buttons suggest nearby FAQs (including common spelling mistakes).
Request an answer is available after any reply so members can also report an
unhelpful match. A confirmation explains that the last question will be saved.
Members must sign in; duplicate pending questions reuse the existing request,
and new requests are limited to five per member per rolling 24 hours.

Migration 0016 adds the request table. Members see their private answers through
the widget's My help requests & answers link. Administrators open Django admin's
Assistance requests, filter Awaiting answer, enter an answer and save. This is
an in-app queue, with no email notifications or guaranteed response time.

The Create inactive FAQ drafts action copies answered requests into inactive
FAQs. Before publishing, review the response for private information, rewrite
the title as a general question, add matching keywords and activate the FAQ.
Drafts do not affect chatbot replies until activated.
