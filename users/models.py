from django.db import models
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

    def mark_as_expired(self):
        """Mark user as expired and deduct ₹1 from other alive members"""
        if not self.is_expired:
            self.is_expired = True
            self.expired_date = timezone.now()
            self.save()
            
            # Deduct ₹1 from other alive members
            alive_users = User.objects.filter(is_expired=False).exclude(id=self.id)
            for user in alive_users:
                user.wallet_balance -= 1
                user.save()
            
            # Trigger notification task
            from .tasks import notify_users_about_expiry
            notify_users_about_expiry.delay(self.id, [user.id for user in alive_users])

    def revert_from_expired(self):
        """Revert user from expired to alive and refund ₹1 to others"""
        if self.is_expired:
            self.is_expired = False
            self.expired_date = None
            self.save()
            
            # Refund ₹1 to other alive members who were charged
            alive_users = User.objects.filter(is_expired=False).exclude(id=self.id)
            for user in alive_users:
                user.wallet_balance += 1
                user.save()
            
            # Trigger notification task for revert
            from .tasks import notify_users_about_revert
            notify_users_about_revert.delay(self.id, [user.id for user in alive_users])

    def __str__(self):
        return f"{self.name} ({self.email}) - Balance: ₹{self.wallet_balance}"

    class Meta:
        db_table = 'users'