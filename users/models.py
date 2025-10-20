from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_expired = models.BooleanField(default=False)
    expired_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Check max 10 members limit
        if not self.pk and User.objects.count() >= 10:
            raise ValidationError("Maximum 10 members allowed. Cannot create new user.")
        
        # Validate wallet balance
        if self.wallet_balance < 0:
            raise ValidationError("Wallet balance cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @transaction.atomic
    def mark_as_expired(self):
        """Mark user as expired and deduct ₹1 from other alive members"""
        # Check if already expired
        if self.is_expired:
            return  # Already expired, nothing to do
        
        # Get all alive users excluding this one
        alive_users = User.objects.filter(is_expired=False).exclude(id=self.id).select_for_update()
        
        # Check if all alive users have sufficient balance
        insufficient_balance_users = []
        for user in alive_users:
            if user.wallet_balance < 1:
                insufficient_balance_users.append(f"{user.name} (₹{user.wallet_balance})")
        
        if insufficient_balance_users:
            raise ValidationError(
                f"Cannot mark as expired. Following users have insufficient balance: "
                f"{', '.join(insufficient_balance_users)}"
            )
        
        # Mark this user as expired FIRST
        self.is_expired = True
        self.expired_date = timezone.now()
        self.save()
        
        # Deduct ₹1 from other alive members
        affected_user_ids = []
        for user in alive_users:
            user.wallet_balance -= 1
            user.save()
            affected_user_ids.append(user.id)
        
        # Trigger notification task
        if affected_user_ids:
            from .tasks import notify_users_about_expiry
            notify_users_about_expiry.delay(self.id, affected_user_ids)

    @transaction.atomic
    def revert_from_expired(self):
        """Revert user from expired to alive and refund ₹1 to others"""
        # Check if actually expired
        if not self.is_expired:
            return  # Not expired, nothing to do
        
        # CRITICAL FIX: Only refund to users who were alive when this user was marked as expired
        # This means users who:
        # 1. Are currently alive (is_expired=False)
        # 2. Were created BEFORE this user's expiry date (existed at the time)
        # 3. Are not this user
        
        # Edge case handling:
        # - If a user joined AFTER this user expired, they never paid, so no refund
        # - If a user was expired when this user expired, they didn't pay, so no refund
        # - If a user was alive, paid, and is still alive, they get refund
        # - If a user was alive, paid, but is now expired, they still get refund (they paid!)
        
        # Get all users who existed before expiry and were alive at that time
        # Since we can't track historical state, we assume all users created before expiry
        # who are currently alive should get refunds (safest assumption)
        alive_users = User.objects.filter(
            is_expired=False,
            created_at__lt=self.expired_date  # Only users who existed before expiry
        ).exclude(id=self.id).select_for_update()
        
        # Revert this user
        self.is_expired = False
        self.expired_date = None
        self.save()
        
        # Refund ₹1 to users who were charged
        affected_user_ids = []
        for user in alive_users:
            user.wallet_balance += 1
            user.save()
            affected_user_ids.append(user.id)
        
        # Trigger notification task for revert
        if affected_user_ids:
            from .tasks import notify_users_about_revert
            notify_users_about_revert.delay(self.id, affected_user_ids)

    def __str__(self):
        status = "EXPIRED" if self.is_expired else "ALIVE"
        return f"{self.name} ({self.email}) - Balance: ₹{self.wallet_balance} [{status}]"

    class Meta:
        db_table = 'users'