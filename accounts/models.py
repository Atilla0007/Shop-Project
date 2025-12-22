from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    phone_verified = models.BooleanField(default=False)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    privacy_accepted_at = models.DateTimeField(null=True, blank=True)
    marketing_email_opt_in = models.BooleanField(default=False)
    marketing_sms_opt_in = models.BooleanField(default=False)
    marketing_opt_in_updated_at = models.DateTimeField(null=True, blank=True)

    def mark_phone_verified(self):
        self.phone_verified = True
        self.phone_verified_at = timezone.now()
        self.save(update_fields=['phone_verified', 'phone_verified_at'])

    def mark_email_verified(self):
        self.email_verified = True
        self.email_verified_at = timezone.now()
        self.save(update_fields=['email_verified', 'email_verified_at'])

    def __str__(self):
        return f'Profile({self.user_id})'
