# Lost & Found Web Portal

A Django-based web portal for your community to report, search, and retrieve lost and found items.

## Features
- User registration (with contact number) and login
- Report lost or found items
- Upload item details and photos
- Search and filter items by category or location
- Contact form/message button for communication
- Website messaging system for item retrieval

## Getting Started
1. Ensure you have Python 3.8+ and pip installed.
2. Create and activate a virtual environment (already set up if using this repo).
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run migrations:
   ```
   python manage.py migrate
   ```
5. Start the development server:
   ```
   python manage.py runserver
   ```
6. Access the site at http://127.0.0.1:8000/

## Replace Placeholder Media
If you see placeholder images, replace them with actual item photos as needed.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
[MIT](LICENSE)
