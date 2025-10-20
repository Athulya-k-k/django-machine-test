# User Management System

A Django-based user management system with wallet balance tracking, expiry management, and bulk CSV upload functionality.

## Features

- **User Management**: Create, view, and manage users with wallet balances
- **Expiry System**: Mark users as expired with automatic wallet deduction from alive members
- **Revert Functionality**: Revert expired users back to alive status with automatic refunds
- **Bulk CSV Upload**: Upload multiple users at once via CSV file with comprehensive validation
- **Asynchronous Notifications**: Celery-based task queue for sending notifications
- **Admin Interface**: Full-featured Django admin panel for all operations

## Technical Stack

- **Framework**: Django 4.2.7
- **Task Queue**: Celery 5.3.4
- **Message Broker**: Redis 5.0.1
- **Data Processing**: Pandas 2.1.3
- **Database**: SQLite (default)

## Prerequisites

- Python 3.8 or higher
- Redis server (for Celery tasks)

## Installation

1. **Clone the repository or extract the project files**

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start Redis server** (in a separate terminal)
   ```bash
   redis-server
   ```

7. **Start Celery worker** (in a separate terminal)
   ```bash
   celery -A user_management worker --loglevel=info
   ```

8. **Run the development server**
   ```bash
   python manage.py runserver
   ```

9. **Access the application**
   - Navigate to `http://127.0.0.1:8000/admin/`
   - Login with your superuser credentials

## Usage

### Adding Users

#### Manual Creation
1. Go to the admin panel
2. Click on "Users" → "Add User"
3. Fill in the details (name, email, wallet_balance)
4. Click "Save"

#### Bulk CSV Upload
1. Go to the Users section in admin
2. Click the "Bulk Upload" button in the top right
3. Upload a CSV file with the following format:

```csv
name,email,wallet_balance
John Doe,john@example.com,100.00
Jane Smith,jane@example.com,150.50
Bob Johnson,bob@example.com,200.00
```

**CSV Requirements:**
- Must contain columns: `name`, `email`, `wallet_balance`
- Email must be unique
- Wallet balance must be non-negative
- Maximum 10 users allowed in the system

**Validation:**
- Duplicate emails in CSV are detected
- Existing emails in database are checked
- All validations run before any data is saved
- If errors occur, an error report CSV can be downloaded

### Marking Users as Expired

1. Select users from the user list
2. Choose "Mark selected users as expired" from the Actions dropdown
3. Click "Go"

**Business Logic:**
- User is marked as expired
- ₹1 is deducted from all alive members' wallets
- Fails if any alive member has insufficient balance (< ₹1)
- Notifications are sent asynchronously via Celery

### Reverting Users from Expired

1. Select expired users from the user list
2. Choose "Revert selected users from expired" from the Actions dropdown
3. Click "Go"

**Business Logic:**
- User is reverted to alive status
- ₹1 is refunded to all alive members who were alive at the time of expiry
- Users who joined after the expiry don't receive refunds
- Notifications are sent asynchronously via Celery

## System Constraints

- **Maximum Users**: 10 users allowed in the system
- **Wallet Balance**: Cannot be negative
- **Unique Email**: Each user must have a unique email address
- **Expiry Logic**: Users who don't have sufficient balance prevent expiry actions

## Project Structure

```
user_management/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── user_management/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py
├── users/
│   ├── models.py          # User model with business logic
│   ├── admin.py           # Admin interface and bulk upload
│   ├── tasks.py           # Celery tasks for notifications
│   ├── forms.py           # Bulk upload form
│   └── migrations/
└── templates/
    └── users/
        ├── bulk_upload.html
        └── upload_result.html
```

## Models

### User Model
- `name`: CharField (max 100 characters)
- `email`: EmailField (unique)
- `wallet_balance`: DecimalField (max 10 digits, 2 decimal places)
- `is_expired`: BooleanField (default: False)
- `expired_date`: DateTimeField (nullable)
- `created_at`: DateTimeField (auto)
- `updated_at`: DateTimeField (auto)

## API Methods

### User.mark_as_expired()
Marks user as expired and deducts ₹1 from all alive members.

### User.revert_from_expired()
Reverts user from expired status and refunds ₹1 to eligible members.

## Celery Tasks

### notify_users_about_expiry
Sends notifications when a user is marked as expired.

### notify_users_about_revert
Sends notifications when a user is reverted from expired.


## Error Handling

- **Validation Errors**: All form inputs are validated
- **Database Constraints**: Enforced at model level
- **Transaction Safety**: Uses Django's atomic transactions
- **Bulk Upload**: Comprehensive validation with error reporting


```




