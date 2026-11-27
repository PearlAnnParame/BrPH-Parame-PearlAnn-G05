import re

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


PHONE_RE = re.compile(r"^[0-9+\-() ]{7,20}$")


def clean_phone(value):
    value = (value or "").strip()
    if value and not PHONE_RE.match(value):
        raise forms.ValidationError("Enter a valid contact number (7-20 digits; + - ( ) allowed).")
    return value


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    contact_number = forms.CharField(max_length=20, required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "contact_number")

    def clean_contact_number(self):
        return clean_phone(self.cleaned_data["contact_number"])

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.RESIDENT  # public registration is always a Resident
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "contact_number", "address", "profile_photo")

    def clean_contact_number(self):
        return clean_phone(self.cleaned_data["contact_number"])

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo and hasattr(photo, "size") and photo.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Profile photo must be 2 MB or smaller.")
        return photo

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email
