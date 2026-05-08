# Cloudinary Integration Setup Guide

## Overview
Your RECLAIM project has been successfully configured to use **Cloudinary** for managing all media uploads instead of local storage or AWS S3.

## What Was Set Up

### 1. Cloudinary Configuration
- **Cloud Name**: `dqv8znzsj`
- **API Key**: `989933919878537`
- **API Secret**: Stored securely in `.env`

### 2. Package Installation
```bash
✅ cloudinary==1.44.2 (already installed)
✅ django-cloudinary-storage==0.3.0
```

### 3. Django Settings Updated
**File**: `lost_and_found/settings.py`

Changes made:
- Added `cloudinary_storage` and `cloudinary` to `INSTALLED_APPS`
- Configured Cloudinary to read credentials from environment variables
- Set `MediaCloudinaryStorage` as the default storage backend
- Kept `WhiteNoiseMiddleware` for static files

```python
# Cloudinary Configuration
cloudinary.config(
    cloud_name=env('CLOUDINARY_CLOUD_NAME', default='dqv8znzsj'),
    api_key=env('CLOUDINARY_API_KEY', default='989933919878537'),
    api_secret=env('CLOUDINARY_API_SECRET', default='9e1xUANz_Z32KToucCsLyEZ4xyo'),
)

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

### 4. Environment Variables
**File**: `lost_and_found/.env`

```env
CLOUDINARY_CLOUD_NAME=dqv8znzsj
CLOUDINARY_API_KEY=989933919878537
CLOUDINARY_API_SECRET=9e1xUANz_Z32KToucCsLyEZ4xyo
```

### 5. Model Updates
All image/file upload fields have been converted from `ImageField` to `CloudinaryField`:

| Model | Field | Purpose |
|-------|-------|---------|
| `UserProfile` | `profile_picture` | User profile images |
| `Item` | `photo` | Lost/found item photos |
| `Message` | `image` | Chat message images |
| `ReturnConfirmation` | `finder_photo` | Return evidence photos |
| `ReturnConfirmation` | `owner_photo` | Return evidence photos |
| `library` | `image` | Library item images |

### 6. Database Migration
**Migration File**: `FindIt/migrations/0008_alter_item_photo_alter_message_image_and_more.py`

Status: ✅ **Applied Successfully**

## Features with Cloudinary

### Automatic Features:
- ✅ Automatic image optimization
- ✅ Responsive image delivery
- ✅ CDN distribution (fast global delivery)
- ✅ Automatic format conversion (WebP, AVIF, etc.)
- ✅ Image transformations (resize, crop, watermark, etc.)

### URL Format:
All uploaded images will have Cloudinary URLs like:
```
https://res.cloudinary.com/dqv8znzsj/image/upload/...
```

## Usage in Templates

### Display a Cloudinary Image:
```html
<!-- Profile picture -->
<img src="{{ user_profile.profile_picture.url }}" alt="Profile">

<!-- Item photo -->
<img src="{{ item.photo.url }}" alt="Item Photo">

<!-- With transformations -->
<img src="{{ item.photo.url|add:'w_300,h_300,c_fill' }}" alt="Item">
```

### Upload in Forms:
File uploads work automatically through Django forms:
```python
class ItemForm(ModelForm):
    class Meta:
        model = Item
        fields = ['title', 'description', 'photo', ...]
```

## Benefits Over AWS S3 / Local Storage

| Feature | Local | AWS S3 | Cloudinary |
|---------|-------|--------|-----------|
| Image Optimization | ❌ No | ⚠️ Manual | ✅ Automatic |
| CDN | ❌ No | ✅ Yes | ✅ Yes |
| Transformations | ❌ No | ❌ No | ✅ Built-in |
| Cost (Free Tier) | ∞ | 5GB | 25GB |
| Management Dashboard | ❌ | ⚠️ Basic | ✅ Excellent |

## Testing Cloudinary Setup

### 1. Check Configuration:
```bash
python manage.py shell
```
```python
>>> from django.conf import settings
>>> from cloudinary_storage.storage import MediaCloudinaryStorage
>>> storage = MediaCloudinaryStorage()
>>> print(storage.cloudinary_url)  # Should show cloud name
```

### 2. Upload a Test Image:
1. Go to the admin panel
2. Add a new Item with a photo
3. Verify image appears with Cloudinary URL

### 3. Test in Forms:
1. Register a new user
2. Edit profile and upload a profile picture
3. Check that it uploads to Cloudinary

## Important Notes

⚠️ **Security**: Your Cloudinary credentials are stored in `.env` - **NEVER commit `.env` to Git!**

✅ **Recommendation**: For production, store credentials in environment variables on your hosting platform.

## Rollback (if needed)

To revert to local file storage:

1. Update `STORAGES` in settings.py:
```python
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}
```

2. Revert model fields:
```python
profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
```

3. Create and run migration

## Next Steps

1. ✅ Test uploads in development
2. ✅ Verify images appear in templates
3. ✅ Check Cloudinary dashboard for uploaded files
4. ✅ Deploy to production with environment variables
5. ✅ Monitor Cloudinary usage in admin dashboard

## Support

- Cloudinary Dashboard: https://cloudinary.com/console
- Documentation: https://cloudinary.com/documentation
- Django Integration: https://cloudinary.com/documentation/django_integration

---
**Setup Completed**: May 8, 2026
