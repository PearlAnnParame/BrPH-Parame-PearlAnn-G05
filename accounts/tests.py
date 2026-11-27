from django.test import TestCase
from django.urls import reverse

from .models import User


class StandardFeatureTests(TestCase):
    def reg(self, **kw):
        data = {"first_name": "Ana", "last_name": "Cruz", "username": "ana", "email": "ana@x.com",
                "contact_number": "09171234567", "password1": "Str0ng!pass99", "password2": "Str0ng!pass99"}
        data.update(kw)
        return self.client.post(reverse("register"), data)

    def test_registration_valid_creates_resident(self):
        self.assertRedirects(self.reg(), reverse("login"))
        self.assertEqual(User.objects.get(username="ana").role, "resident")

    def test_registration_invalid_input_rejected(self):
        self.reg()
        self.assertEqual(User.objects.count(), 1)
        for bad in ({"email": "ANA@x.com", "username": "ana2"}, {"password2": "different"},
                    {"username": "bob", "email": "b@x.com", "contact_number": "abc"}):
            self.assertEqual(self.reg(**bad).status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_role_cannot_be_chosen_during_registration(self):
        self.reg(role="admin", is_superuser="on")
        user = User.objects.get(username="ana")
        self.assertEqual(user.role, "resident")
        self.assertFalse(user.is_superuser)

    def test_dashboards_are_role_based_and_login_protected(self):
        res = User.objects.create_user("res", "r@x.com", "pass12345!")
        adm = User.objects.create_superuser("adm", "a@x.com", "pass12345!")
        self.assertEqual(self.client.get(reverse("resident_dashboard")).status_code, 302)
        self.client.force_login(res)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("resident_dashboard"))
        self.assertRedirects(self.client.get(reverse("admin_dashboard")), reverse("dashboard"),
                             fetch_redirect_response=False)
        self.client.force_login(adm)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("admin_dashboard"))

    def test_invalid_login_shows_error_and_logout_is_post_only(self):
        User.objects.create_user("res", "r@x.com", "pass12345!")
        resp = self.client.post(reverse("login"), {"username": "res", "password": "wrong"})
        self.assertContains(resp, "Invalid username or password")
        self.client.login(username="res", password="pass12345!")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))

    def test_profile_is_own_only_and_cannot_change_role(self):
        res = User.objects.create_user("res", "r@x.com", "pass12345!")
        User.objects.create_user("other", "o@x.com", "pass12345!")
        self.assertEqual(self.client.get(reverse("profile")).status_code, 302)
        self.client.force_login(res)
        self.client.post(reverse("profile_edit"), {
            "first_name": "R", "last_name": "S", "email": "r@x.com", "contact_number": "09171234567",
            "address": "Purok 1", "role": "admin"})
        res.refresh_from_db()
        self.assertEqual((res.address, res.role), ("Purok 1", "resident"))
        # email already used by another account is refused
        resp = self.client.post(reverse("profile_edit"), {
            "first_name": "R", "last_name": "S", "email": "o@x.com", "contact_number": "", "address": ""})
        self.assertEqual(resp.status_code, 200)

    def test_register_page_renders_password_help_as_html_without_safe_filter(self):
        resp = self.client.get(reverse("register"))
        self.assertContains(resp, "<ul>")          # validator help text is already marked safe by Django
        self.assertNotContains(resp, "&lt;ul&gt;")
