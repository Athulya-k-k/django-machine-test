from celery import shared_task
from django.core.mail import send_mail
from .models import User

@shared_task
def notify_users_about_expiry(expired_user_id, affected_user_ids):
    """
    Notify users when someone is marked as expired
    This is a placeholder function - in real scenario, it would send emails
    """
    try:
        expired_user = User.objects.get(id=expired_user_id)
        affected_users = User.objects.filter(id__in=affected_user_ids)
        
        print(f"=== EXPIRY NOTIFICATION ===")
        print(f"User {expired_user.name} ({expired_user.email}) has been marked as expired.")
        print(f"₹1 has been deducted from {affected_users.count()} users.")
        
        for user in affected_users:
            print(f"Notified {user.name} ({user.email}) about deduction.")
            # In real scenario: send_mail(...)
        
        print("=== END NOTIFICATION ===")
        
    except User.DoesNotExist:
        print(f"User with id {expired_user_id} not found")

@shared_task
def notify_users_about_revert(reverted_user_id, affected_user_ids):
    """
    Notify users when someone is reverted from expired
    This is a placeholder function - in real scenario, it would send emails
    """
    try:
        reverted_user = User.objects.get(id=reverted_user_id)
        affected_users = User.objects.filter(id__in=affected_user_ids)
        
        print(f"=== REVERT NOTIFICATION ===")
        print(f"User {reverted_user.name} ({reverted_user.email}) has been reverted from expired status.")
        print(f"₹1 has been refunded to {affected_users.count()} users.")
        
        for user in affected_users:
            print(f"Notified {user.name} ({user.email}) about refund.")
            # In real scenario: send_mail(...)
        
        print("=== END NOTIFICATION ===")
        
    except User.DoesNotExist:
        print(f"User with id {reverted_user_id} not found")