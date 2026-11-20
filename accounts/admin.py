from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("BrPH", {"fields": ("role", "contact_number", "address", "profile_photo")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("BrPH", {"fields": ("email", "role", "contact_number")}),
    )
    list_display = ("username", "email", "role", "is_active")
    list_filter = ("role", "is_active")
