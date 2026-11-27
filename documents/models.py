from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def validate_file_size(f):
    if f.size > 5 * 1024 * 1024:
        raise ValidationError("File is too large. Maximum size is 5 MB.")


# File signatures ("magic bytes") so a renamed .exe cannot pass as a .pdf/.jpg/.png
_SIGNATURES = {
    "pdf": (b"%PDF-",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
}


def validate_file_content(f):
    ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
    sigs = _SIGNATURES.get(ext)
    if sigs is None:
        return  # extension validator reports unsupported types
    head = f.read(16)
    f.seek(0)
    if not any(head.startswith(sig) for sig in sigs):
        raise ValidationError("The file content does not match its extension. Upload a real PDF, JPG or PNG.")


class DocumentType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                              validators=[MinValueValidator(0), MaxValueValidator(100000)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Requirement(models.Model):
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name="requirements")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.document_type.name} - {self.name}"


class DocumentRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        READY = "ready", "Ready for Pickup"
        RELEASED = "released", "Released"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    # Statuses an admin may move a request to, from each current status
    TRANSITIONS = {
        "pending": ["under_review", "rejected"],
        "under_review": ["approved", "rejected"],
        "approved": ["ready", "rejected"],
        "ready": ["released"],
    }
    ACTIVE_STATUSES = ["pending", "under_review", "approved", "ready"]

    reference_no = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    resident = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_requests")
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name="requests")
    purpose = models.CharField(max_length=255)
    copies = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    preferred_pickup_date = models.DateField()
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_remarks = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference_no} - {self.document_type.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference_no:
            self.reference_no = f"BRPH-{timezone.now():%Y}-{self.pk:05d}"
            super().save(update_fields=["reference_no"])

    @property
    def can_be_modified(self):
        return self.status == self.Status.PENDING

    @property
    def can_be_deleted(self):
        return self.status in (self.Status.PENDING, self.Status.CANCELLED)

    @property
    def next_statuses(self):
        return self.TRANSITIONS.get(self.status, [])


class RequestAttachment(models.Model):
    request = models.ForeignKey(DocumentRequest, on_delete=models.CASCADE, related_name="attachments")
    requirement = models.ForeignKey(Requirement, on_delete=models.SET_NULL, null=True, blank=True, related_name="attachments")
    file = models.FileField(upload_to="attachments/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.request.reference_no} - {self.requirement}"


class StatusHistory(models.Model):
    request = models.ForeignKey(DocumentRequest, on_delete=models.CASCADE, related_name="history")
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    remarks = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name_plural = "status histories"

    def __str__(self):
        return f"{self.request.reference_no}: {self.old_status} -> {self.new_status}"
