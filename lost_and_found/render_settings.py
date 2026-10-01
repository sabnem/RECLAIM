"""Render production configuration; local development uses settings.py."""

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403

DEBUG = False
render_hostname = env('RENDER_EXTERNAL_HOSTNAME', default='')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set explicit production ALLOWED_HOSTS or RENDER_EXTERNAL_HOSTNAME.')

SITE_URL = env('SITE_URL', default=f'https://{render_hostname}').rstrip('/')
if not SITE_URL.startswith('https://') or SITE_URL == 'https:':
    raise ImproperlyConfigured('SITE_URL must be the public HTTPS address.')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[SITE_URL])
if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f'https://{render_hostname}')

DATABASES = {'default': dj_database_url.parse(
    env('DATABASE_URL'), conn_max_age=0, conn_health_checks=True,
)}
if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Render requires a PostgreSQL DATABASE_URL; SQLite is not persistent.')
DATABASES['default'].setdefault('OPTIONS', {})['connect_timeout'] = 10

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': env('CLOUDINARY_API_KEY'),
    'API_SECRET': env('CLOUDINARY_API_SECRET'),
    'SECURE': True,
}
if not all(CLOUDINARY_STORAGE.values()):
    raise ImproperlyConfigured('All three Cloudinary credentials must be provided.')

CHANNEL_LAYERS = {'default': {
    'BACKEND': 'channels_redis.core.RedisChannelLayer',
    'CONFIG': {'hosts': [env('REDIS_URL')]},
}}

EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_TIMEOUT = 20
