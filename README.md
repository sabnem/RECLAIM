# Lost & Found Web Portal

A Django-based web portal for your community to report, search, and retrieve lost and found items.

## ✨ Features

### Core Functionality
- 👤 User registration (with contact number) and login
- 📝 Report lost or found items
- 📷 Upload item details and photos
- 🔍 Search and filter items by category or location
- 💬 Website messaging system for communication
- 🌓 Dark mode support with theme toggle

### Item Recovery System
- ✅ Mark items as returned with owner confirmation
- ⭐ Rate finders with 5-star interactive system
- 💾 Recovered items archive (separate from active listings)
- 📊 Detailed feedback and comments

### Reputation & Statistics
- 🏆 User reputation scores based on ratings
- 🎖️ Badge system (Hero, Trusted, Helpful, Active, New)
- 📈 Comprehensive statistics dashboard
- 👥 Top finders leaderboard
- 📉 Rating distribution analytics
- 🕐 Recent recoveries timeline

### Notifications & Export
- 📧 Email notifications when rated (configurable)
- 📄 PDF export of recovered items
- 📊 Statistics export functionality

## 🚀 Getting Started

1. **Prerequisites**
   - Python 3.8+ and pip installed
   - Virtual environment recommended

2. **Installation**
   ```bash
   # Clone the repository
   git clone <repository-url>
   cd RECLAIM

   # Create and activate virtual environment
   python -m venv lfound
   lfound\Scripts\activate  # Windows
   # source lfound/bin/activate  # macOS/Linux

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Database Setup**
   ```bash
   # Run migrations
   python manage.py migrate

   # (Optional) Create superuser for admin access
   python manage.py createsuperuser
   ```

4. **Start Development Server**
   ```bash
   python manage.py runserver
   ```

5. **Access the Application**
   - Main site: http://127.0.0.1:8000/
   - Admin panel: http://127.0.0.1:8000/admin/

## 📖 Usage Guide

### For Item Finders (Reporters)
1. Sign up/Login to your account
2. Click "Report Found Item"
3. Fill in item details and upload photo
4. Mark item as returned when owner retrieves it
5. Receive rating and reputation boost

### For Item Owners
1. Search for your lost item
2. Contact the finder via messaging system
3. Confirm item return when retrieved
4. Rate the finder's helpfulness
5. View recovered items in your dashboard

### Statistics Dashboard
- Navigate to: Profile → Statistics Dashboard
- View your performance metrics
- Check community statistics
- See top finders leaderboard
- Export data to PDF

## 🛠️ Configuration

### Email Notifications
By default, emails are sent to console (development mode).

For production, update `lost_and_found/settings.py`:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

### Dark Mode
- Toggle using the moon/sun icon in the navigation bar
- Preference saved in browser localStorage
- Fully supported across all pages

## 📁 Project Structure

```
RECLAIM/
├── FindIt/                 # Main application
│   ├── models.py          # Database models (Item, RecoveredItem, UserProfile)
│   ├── views.py           # View logic and controllers
│   ├── forms.py           # Form definitions
│   ├── urls.py            # URL routing
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS, images
│   └── templatetags/      # Custom template filters
├── lost_and_found/        # Project settings
├── media/                 # User-uploaded files
├── static/                # Static assets
└── requirements.txt       # Python dependencies
```

## 🔧 Technologies Used

- **Backend**: Django 5.0.6
- **Database**: PostgreSQL (configurable)
- **Frontend**: Bootstrap 5.3.2, Custom CSS
- **PDF Generation**: ReportLab
- **Email**: Django SMTP backend
- **Icons**: Bootstrap Icons

## 📊 Database Models

### RecoveredItem
- Links completed item returns
- Stores rating and feedback
- Tracks recovery date and participants

### UserProfile
- Extends Django User model
- Reputation score (0.00-5.00)
- Total returns and ratings count
- Profile picture support

## 🧪 Testing

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for detailed testing instructions.

Quick test workflow:
1. Create two user accounts (finder and owner)
2. Report an item as finder
3. Mark item as returned
4. Confirm return as owner
5. Submit rating
6. Check statistics dashboard
7. Export PDF report

## Replace Placeholder Media
If you see placeholder images, replace them with actual item photos as needed.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](LICENSE)
