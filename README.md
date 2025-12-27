# Canadian Political Science Simulator - Forum Application

A Django-based forum application for a Canadian political science simulator, featuring PostgreSQL backend and Canadian political party integration.

## Features

- **Forum Categories**: Organized discussion areas
- **Thread Management**: Create, view, and participate in discussions
- **User Profiles**: Extended profiles with political party affiliations
- **Canadian Political Context**: Built-in support for major Canadian political parties
- **User Authentication**: Login/logout functionality
- **Admin Interface**: Full Django admin panel for content management
- **Responsive Design**: Bootstrap 5 responsive layout
- **Pagination**: Efficient browsing of threads and posts

## Technology Stack

- **Backend**: Django 6.0
- **Database**: PostgreSQL (with psycopg2)
- **Frontend**: Bootstrap 5, HTML5, CSS3
- **Python**: 3.12+

## Models

### PoliticalParty
- Represents Canadian political parties (Liberal, Conservative, NDP, Bloc Québécois, Green, PPC, Independent)
- Includes party colors for visual identification

### UserProfile
- Extended user information
- Party affiliation
- Electoral riding (district)
- Role (MP, Senator, Minister, etc.)
- Biography

### ForumCategory
- Top-level organization for discussions
- Customizable ordering

### Thread
- Discussion topics within categories
- Pinning and locking capabilities
- View tracking

### Post
- Individual messages within threads
- Edit tracking
- Author attribution

## Installation

### Prerequisites

1. Python 3.12+
2. PostgreSQL database server
3. pip package manager

### Database Setup

1. Install PostgreSQL if not already installed
2. Create a database and user:



### Application Setup

1. Navigate to the project directory:
```bash
cd canadian_polsim
```

2. Update database settings in `canadian_polsim/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'canadian_polsim_db',
        'USER': 'polsim_user',
        'PASSWORD': 'your_password_here',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

3. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

4. Create a superuser:
```bash
python manage.py createsuperuser
```

5. Start the development server:
```bash
python manage.py runserver
```

6. Access the application:
   - Forum: http://localhost:8000/
   - Admin: http://localhost:8000/admin/

## Initial Setup

### 1. Add Political Parties (via Admin Panel)

Login to the admin panel and add political parties with their colors:

- Liberal Party: #FF0000 (Red)
- Conservative Party: #1A4782 (Blue)
- NDP: #FF6600 (Orange)
- Bloc Québécois: #87CEEB (Light Blue)
- Green Party: #99CC33 (Green)
- People's Party: #4B3F6C (Purple)

### 2. Create Forum Categories

Examples:
- House of Commons - Main parliamentary discussions
- Senate - Upper chamber discussions
- Party Caucuses - Internal party discussions
- Bills and Legislation - Discussion of proposed laws
- Elections and Campaigns - Electoral discussions
- Off-Topic - General discussion

### 3. Create User Profiles

After users register, assign them:
- Political party affiliation
- Electoral riding
- Role (MP, Senator, Minister, etc.)
- Biography

## Usage

### For Users

1. **Browse Forums**: Visit the homepage to see all categories
2. **Read Threads**: Click on a category to view threads
3. **Create Threads**: Login and click "New Thread" in any category
4. **Reply to Threads**: Login and scroll to the bottom of any thread
5. **View Profiles**: Click on any username to see their profile

### For Administrators

1. **Manage Content**: Use the admin panel to moderate
2. **Pin/Lock Threads**: Use admin interface to manage important threads
3. **Manage Users**: Assign parties, roles, and ridings
4. **Create Categories**: Organize forum structure

## Development Tips

### Using SQLite for Testing

If you want to use SQLite for development/testing instead of PostgreSQL, uncomment this in `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### Static Files

For production, collect static files:
```bash
python manage.py collectstatic
```

### Environment Variables

For production, use environment variables for sensitive settings:
```python
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
```

## File Structure

```
canadian_polsim/
├── canadian_polsim/        # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── forum/                  # Forum app
│   ├── models.py          # Database models
│   ├── views.py           # View logic
│   ├── forms.py           # Form definitions
│   ├── urls.py            # URL routing
│   ├── admin.py           # Admin configuration
│   └── templates/         # HTML templates
│       └── forum/
│           ├── base.html
│           ├── index.html
│           ├── category_detail.html
│           ├── thread_detail.html
│           ├── create_thread.html
│           ├── user_profile.html
│           └── login.html
└── manage.py              # Django management script
```

## Future Enhancements

- Private messaging system
- Advanced search functionality
- Voting/polling features
- Parliamentary bill tracking
- Committee management
- Role-based permissions
- Email notifications
- Rich text editor for posts
- File attachments
- User reputation system

## License

This is a basic implementation for educational and simulation purposes.

## Support

For issues or questions, please contact your system administrator.

