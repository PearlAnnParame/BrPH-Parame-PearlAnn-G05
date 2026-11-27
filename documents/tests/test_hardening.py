"""Hardening tests: validation, access control, integrity, error pages (PD3)."""
import datetime
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from documents.forms import DocumentTypeForm
from documents.models import (DocumentRequest, DocumentType, RequestAttachment,
                              Requirement)

PASSWORD = "pass12345!"


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="brph_test_media_"))
class HardeningBase(TestCase):
    def setUp(self):
        self.res1 = User.objects.create_user("res1", "r1@x.com", PASSWORD)
        self.res2 = User.objects.create_user("res2", "r2@x.com", PASSWORD)
        self.admin = User.objects.create_superuser("boss", "b@x.com", PASSWORD)
        self.dt = DocumentType.objects.create(name="Barangay Clearance", fee=100)
        self.req = Requirement.objects.create(document_type=self.dt, name="Valid ID", is_mandatory=True)

    def login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=PASSWORD))

    def make_request(self, resident=None, status="pending", doc_type=None):
        return DocumentRequest.objects.create(
            resident=resident or self.res1, document_type=doc_type or self.dt, purpose="Employment",
            copies=1, preferred_pickup_date=timezone.localdate(), status=status)

    def payload(self, **kw):
        data = {
            "purpose": "Job application", "copies": 1,
            "preferred_pickup_date": (timezone.localdate() + datetime.timedelta(days=3)).isoformat(),
            "remarks": "",
            f"req_{self.req.pk}": SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        }
        data.update(kw)
        return data


class ValidationTests(HardeningBase):
    def post_new(self, **kw):
        self.login("res1")
        return self.client.post(reverse("request_create", args=[self.dt.pk]), self.payload(**kw))

    def test_copies_out_of_range_rejected(self):
        for bad in ("0", "6", "-1", "abc"):
            resp = self.post_new(copies=bad)
            self.assertEqual(resp.status_code, 200, bad)
        self.assertEqual(DocumentRequest.objects.count(), 0)

    def test_purpose_too_short_and_pickup_too_far_rejected(self):
        resp = self.post_new(purpose="  a ")
        self.assertContains(resp, "at least 5 characters")
        far = (timezone.localdate() + datetime.timedelta(days=200)).isoformat()
        resp = self.post_new(preferred_pickup_date=far)
        self.assertContains(resp, "within the next 90 days")
        self.assertEqual(DocumentRequest.objects.count(), 0)

    def test_fake_pdf_with_wrong_content_is_rejected(self):
        fake = SimpleUploadedFile("id.pdf", b"MZ\x90\x00 this is an exe", content_type="application/pdf")
        resp = self.post_new(**{f"req_{self.req.pk}": fake})
        self.assertContains(resp, "does not match its extension")
        self.assertEqual(DocumentRequest.objects.count(), 0)

    def test_document_type_name_unique_ignoring_case(self):
        form = DocumentTypeForm({"name": "barangay clearance", "fee": "10", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_negative_fee_rejected(self):
        form = DocumentTypeForm({"name": "New Type", "fee": "-5", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("fee", form.errors)

    def test_status_remarks_too_long_is_a_form_error_not_a_crash(self):
        r = self.make_request()
        self.login("boss")
        resp = self.client.post(reverse("admin_request_detail", args=[r.pk]),
                                {"new_status": "rejected", "remarks": "x" * 300})
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")

    def test_cancelled_request_does_not_block_a_new_one(self):
        self.make_request(status="cancelled")
        resp = self.post_new()
        self.assertEqual(DocumentRequest.objects.filter(status="pending").count(), 1)
        self.assertEqual(resp.status_code, 302)


class AccessControlTests(HardeningBase):
    def test_every_core_url_requires_login(self):
        r = self.make_request()
        names = [("request_list", []), ("choose_type", []), ("request_create", [self.dt.pk]),
                 ("request_detail", [r.pk]), ("request_edit", [r.pk]), ("request_delete_confirm", [r.pk]),
                 ("admin_request_list", []), ("admin_request_detail", [r.pk]), ("doctype_list", []),
                 ("doctype_create", []), ("doctype_edit", [self.dt.pk]), ("doctype_delete_confirm", [self.dt.pk]),
                 ("attachment_download", [1])]
        for name, args in names:
            url = reverse(name, args=args)
            resp = self.client.get(url)
            self.assertRedirects(resp, f"{reverse('login')}?next={url}", fetch_redirect_response=False, msg_prefix=name)

    def test_post_only_actions_reject_get_and_change_nothing(self):
        r = self.make_request()
        self.login("res1")
        for name in ("request_cancel", "request_delete"):
            self.assertEqual(self.client.get(reverse(name, args=[r.pk])).status_code, 405)
        self.login("boss")
        self.assertEqual(self.client.get(reverse("doctype_delete", args=[self.dt.pk])).status_code, 405)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")
        self.assertTrue(DocumentType.objects.filter(pk=self.dt.pk).exists())

    def test_resident_cannot_cancel_or_delete_others_request(self):
        other = self.make_request(self.res2)
        self.login("res1")
        self.assertEqual(self.client.post(reverse("request_cancel", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("request_delete_confirm", args=[other.pk])).status_code, 404)
        other.refresh_from_db()
        self.assertEqual(other.status, "pending")

    def test_resident_cannot_change_status_through_admin_url(self):
        r = self.make_request()
        self.login("res1")
        resp = self.client.post(reverse("admin_request_detail", args=[r.pk]), {"new_status": "approved"})
        self.assertRedirects(resp, reverse("dashboard"), fetch_redirect_response=False)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")

    def test_admin_cannot_use_resident_request_pages(self):
        self.login("boss")
        self.assertRedirects(self.client.get(reverse("request_list")), reverse("dashboard"),
                             fetch_redirect_response=False)

    def test_csrf_token_is_enforced_on_post(self):
        r = self.make_request()
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="res1", password=PASSWORD)
        self.assertEqual(strict.post(reverse("request_cancel", args=[r.pk])).status_code, 403)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")

    def test_attachment_files_are_private(self):
        r = self.make_request()
        att = RequestAttachment.objects.create(
            request=r, requirement=self.req, file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 secret"))
        url = reverse("attachment_download", args=[att.pk])
        self.assertEqual(self.client.get(url).status_code, 302)             # anonymous -> login
        self.login("res2")
        self.assertEqual(self.client.get(url).status_code, 404)             # another resident
        self.login("res1")
        self.assertEqual(b"".join(self.client.get(url).streaming_content), b"%PDF-1.4 secret")
        self.login("boss")
        self.assertEqual(self.client.get(url).status_code, 200)             # admin
        self.assertEqual(self.client.get("/media/" + att.file.name).status_code, 404)  # no public URL


class ErrorHandlingTests(HardeningBase):
    def test_custom_404_page_for_unknown_url(self):
        resp = self.client.get("/this/page/does/not/exist/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "Page not found", status_code=404)
        self.assertNotContains(resp, "Traceback", status_code=404)

    def test_missing_and_huge_ids_return_404_not_500(self):
        self.login("res1")
        for url in (reverse("request_detail", args=[999999]),
                    reverse("request_detail", args=[10 ** 30]),
                    reverse("request_create", args=[999999]),
                    reverse("attachment_download", args=[999999])):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.login("boss")
        self.assertEqual(self.client.get(reverse("admin_request_detail", args=[999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("doctype_edit", args=[999999])).status_code, 404)

    def test_weird_filter_values_do_not_crash(self):
        self.login("boss")
        for qs in ("?type=%C2%B2", "?type=99999999999999999999999", "?status=<script>", "?page=abc", "?page=-4"):
            self.assertEqual(self.client.get(reverse("admin_request_list") + qs).status_code, 200, qs)

    def test_custom_500_template_has_no_debug_info(self):
        from django.template.loader import render_to_string
        html = render_to_string("500.html")
        self.assertIn("Something went wrong", html)
        self.assertNotIn("Traceback", html)

    def test_logout_requires_post(self):
        self.login("res1")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)


class IntegrityTests(HardeningBase):
    def test_database_blocks_second_active_request_for_same_type(self):
        self.make_request()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_request()

    def test_database_blocks_invalid_copies(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DocumentRequest.objects.create(
                resident=self.res1, document_type=self.dt, purpose="x", copies=9,
                preferred_pickup_date=timezone.localdate())

    def test_resident_with_requests_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        self.make_request()
        with self.assertRaises(ProtectedError):
            self.res1.delete()

    def test_delete_requires_confirmation_page_then_post(self):
        r = self.make_request()
        self.login("res1")
        resp = self.client.get(reverse("request_delete_confirm", args=[r.pk]))
        self.assertContains(resp, "This cannot be undone")
        self.assertTrue(DocumentRequest.objects.filter(pk=r.pk).exists())
        self.client.post(reverse("request_delete", args=[r.pk]))
        self.assertFalse(DocumentRequest.objects.filter(pk=r.pk).exists())

    def test_attachment_file_removed_from_storage_with_request(self):
        r = self.make_request()
        att = RequestAttachment.objects.create(
            request=r, requirement=self.req, file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 x"))
        path = att.file.path
        self.assertTrue(os.path.exists(path))
        r.delete()
        self.assertFalse(os.path.exists(path))

    def test_released_requests_cannot_be_deleted_or_cancelled(self):
        r = self.make_request(status="released")
        self.login("res1")
        self.client.post(reverse("request_delete", args=[r.pk]))
        self.client.post(reverse("request_cancel", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.status, "released")

    def test_stale_status_update_is_refused(self):
        r = self.make_request()
        self.login("boss")
        url = reverse("admin_request_detail", args=[r.pk])
        self.client.post(url, {"new_status": "under_review", "remarks": ""})
        resp = self.client.post(url, {"new_status": "under_review", "remarks": ""})  # no longer allowed
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(r.history.count(), 1)


class PaginationTests(HardeningBase):
    def test_lists_are_paginated_and_bad_pages_fall_back(self):
        for _ in range(25):
            self.make_request(status="released")
        self.login("res1")
        url = reverse("request_list")
        self.assertEqual(len(self.client.get(url).context["page"]), 10)
        self.assertEqual(len(self.client.get(url + "?page=3").context["page"]), 5)
        self.assertEqual(self.client.get(url + "?page=999").status_code, 200)
        self.login("boss")
        self.assertEqual(len(self.client.get(reverse("admin_request_list")).context["page"]), 10)


class QueryCountTests(HardeningBase):
    def test_request_list_query_count_does_not_grow_with_rows(self):
        for _ in range(8):
            self.make_request(status="released")
        self.login("res1")
        with self.assertNumQueries(4):  # session, user, count, rows (document type joined)
            self.client.get(reverse("request_list"))
