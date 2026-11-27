import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from documents.models import DocumentRequest, DocumentType, Requirement, StatusHistory

TMP_MEDIA = override_settings(MEDIA_ROOT="/tmp/brph_test_media")


@TMP_MEDIA
class DocumentRequestTests(TestCase):
    def setUp(self):
        self.res1 = User.objects.create_user("res1", "r1@x.com", "pass12345!")
        self.res2 = User.objects.create_user("res2", "r2@x.com", "pass12345!")
        self.admin = User.objects.create_superuser("boss", "b@x.com", "pass12345!")
        self.dt = DocumentType.objects.create(name="Barangay Clearance", fee=100)
        self.req = Requirement.objects.create(document_type=self.dt, name="Valid ID", is_mandatory=True)

    def payload(self, **kw):
        data = {
            "purpose": "Job application", "copies": 1,
            "preferred_pickup_date": (timezone.localdate() + datetime.timedelta(days=3)).isoformat(),
            "remarks": "",
            f"req_{self.req.pk}": SimpleUploadedFile("id.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        }
        data.update(kw)
        return data

    def make_request(self, resident=None):
        r = DocumentRequest.objects.create(
            resident=resident or self.res1, document_type=self.dt, purpose="x", copies=1,
            preferred_pickup_date=timezone.localdate())
        return r

    def test_login_required(self):
        resp = self.client.get(reverse("request_list"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('request_list')}")

    def test_resident_creates_request_with_attachment_and_history(self):
        self.client.login(username="res1", password="pass12345!")
        resp = self.client.post(reverse("request_create", args=[self.dt.pk]), self.payload())
        r = DocumentRequest.objects.get()
        self.assertRedirects(resp, reverse("request_detail", args=[r.pk]))
        self.assertEqual(r.resident, self.res1)
        self.assertTrue(r.reference_no.startswith("BRPH-"))
        self.assertEqual(r.attachments.count(), 1)
        self.assertEqual(StatusHistory.objects.filter(request=r).count(), 1)

    def test_validation_missing_mandatory_file_and_past_date(self):
        self.client.login(username="res1", password="pass12345!")
        data = self.payload(preferred_pickup_date="2000-01-01")
        del data[f"req_{self.req.pk}"]
        resp = self.client.post(reverse("request_create", args=[self.dt.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(DocumentRequest.objects.count(), 0)
        self.assertContains(resp, "cannot be in the past")

    def test_rejects_bad_file_type(self):
        self.client.login(username="res1", password="pass12345!")
        bad = SimpleUploadedFile("virus.exe", b"x")
        resp = self.client.post(reverse("request_create", args=[self.dt.pk]),
                                self.payload(**{f"req_{self.req.pk}": bad}))
        self.assertEqual(DocumentRequest.objects.count(), 0)
        self.assertEqual(resp.status_code, 200)

    def test_duplicate_active_request_blocked(self):
        self.make_request()
        self.client.login(username="res1", password="pass12345!")
        resp = self.client.post(reverse("request_create", args=[self.dt.pk]), self.payload())
        self.assertEqual(DocumentRequest.objects.count(), 1)
        self.assertContains(resp, "already have an active request")

    def test_resident_cannot_view_or_edit_others_records(self):
        other = self.make_request(self.res2)
        self.client.login(username="res1", password="pass12345!")
        self.assertEqual(self.client.get(reverse("request_detail", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("request_edit", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("request_delete", args=[other.pk])).status_code, 404)

    def test_resident_cannot_open_admin_pages(self):
        self.client.login(username="res1", password="pass12345!")
        for name in ("admin_request_list", "doctype_list"):
            self.assertRedirects(self.client.get(reverse(name)), reverse("dashboard"), fetch_redirect_response=False)

    def test_update_cancel_delete_flow(self):
        r = self.make_request()
        self.client.login(username="res1", password="pass12345!")
        self.client.post(reverse("request_edit", args=[r.pk]),
                         self.payload(purpose="Updated purpose"))
        r.refresh_from_db()
        self.assertEqual(r.purpose, "Updated purpose")
        self.client.post(reverse("request_cancel", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.status, "cancelled")
        self.client.post(reverse("request_delete", args=[r.pk]))
        self.assertEqual(DocumentRequest.objects.count(), 0)

    def test_admin_status_workflow_and_reject_needs_reason(self):
        r = self.make_request()
        self.client.login(username="boss", password="pass12345!")
        url = reverse("admin_request_detail", args=[r.pk])
        self.client.post(url, {"new_status": "under_review", "remarks": ""})
        r.refresh_from_db()
        self.assertEqual(r.status, "under_review")
        self.assertEqual(r.processed_by, self.admin)
        resp = self.client.post(url, {"new_status": "rejected", "remarks": ""})
        r.refresh_from_db()
        self.assertEqual(r.status, "under_review")
        self.assertContains(resp, "give a reason")
        self.client.post(url, {"new_status": "approved", "remarks": "OK"})
        r.refresh_from_db()
        self.assertEqual(r.status, "approved")

    def test_resident_cannot_edit_after_review_starts(self):
        r = self.make_request()
        r.status = "under_review"
        r.save()
        self.client.login(username="res1", password="pass12345!")
        resp = self.client.get(reverse("request_edit", args=[r.pk]))
        self.assertRedirects(resp, reverse("request_detail", args=[r.pk]))

    def test_admin_document_type_crud(self):
        self.client.login(username="boss", password="pass12345!")
        data = {
            "name": "Business Permit", "description": "d", "fee": "250", "is_active": "on",
            "requirements-TOTAL_FORMS": "1", "requirements-INITIAL_FORMS": "0",
            "requirements-MIN_NUM_FORMS": "0", "requirements-MAX_NUM_FORMS": "1000",
            "requirements-0-name": "DTI Permit", "requirements-0-description": "", "requirements-0-is_mandatory": "on",
        }
        self.client.post(reverse("doctype_create"), data)
        bp = DocumentType.objects.get(name="Business Permit")
        self.assertEqual(bp.requirements.count(), 1)
        self.client.post(reverse("doctype_delete", args=[bp.pk]))
        self.assertFalse(DocumentType.objects.filter(name="Business Permit").exists())
        # type with requests is protected from deletion
        self.make_request()
        self.client.post(reverse("doctype_delete", args=[self.dt.pk]))
        self.assertTrue(DocumentType.objects.filter(pk=self.dt.pk).exists())

    def test_dashboards_show_request_counts(self):
        self.make_request()
        self.client.login(username="res1", password="pass12345!")
        self.assertEqual(self.client.get(reverse("resident_dashboard")).status_code, 200)
        self.client.login(username="boss", password="pass12345!")
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 200)
