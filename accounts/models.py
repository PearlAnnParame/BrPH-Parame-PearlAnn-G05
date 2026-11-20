from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        RESIDENT = "resident", "Resident"
        ADMIN = "admin", "Barangay Admin"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RESIDENT)
    contact_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)

    def save(self, *args, **kwargs):
        # Superusers created via createsuperuser are always Barangay Admins
        if self.is_superuser:
            self.role = self.Role.ADMIN
        self.email = (self.email or "").lower()
        super().save(*args, **kwargs)

    @property
    def is_barangay_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_resident(self):
        return self.role == self.Role.RESIDENT
