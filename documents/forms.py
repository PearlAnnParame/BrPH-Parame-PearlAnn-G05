import datetime

from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from .models import (DocumentRequest, DocumentType, RequestAttachment,
                     Requirement, validate_file_content,
                     validate_file_size)


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ("name", "description", "fee", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 3:
            raise forms.ValidationError("Name must be at least 3 characters.")
        dup = DocumentType.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if dup.exists():
            raise forms.ValidationError("A document type with this name already exists.")
        return name


class BaseRequirementFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            name = (form.cleaned_data.get("name") or "").strip().lower()
            if not name:
                continue
            if name in seen:
                raise forms.ValidationError(f"Requirement '{name}' is listed more than once.")
            seen.add(name)


RequirementFormSet = forms.inlineformset_factory(
    DocumentType, Requirement, formset=BaseRequirementFormSet,
    fields=("name", "description", "is_mandatory"),
    extra=2, can_delete=True,
)


class RequestForm(forms.ModelForm):
    """Document request form. One file field is added per requirement of the document type."""

    class Meta:
        model = DocumentRequest
        fields = ("purpose", "copies", "preferred_pickup_date", "remarks")
        widgets = {
            "preferred_pickup_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, document_type, resident, **kwargs):
        super().__init__(*args, **kwargs)
        self.document_type = document_type
        self.resident = resident
        existing = {}
        if self.instance.pk:
            existing = {a.requirement_id: a for a in self.instance.attachments.all()}
        self._reqs = []
        for req in document_type.requirements.all():
            name = f"req_{req.pk}"
            has_file = req.pk in existing
            self.fields[name] = forms.FileField(
                label=req.name + ("" if req.is_mandatory else " (optional)"),
                required=req.is_mandatory and not has_file,
                widget=forms.FileInput,
                validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"]), validate_file_size,
                            validate_file_content],
                help_text=(req.description + " " if req.description else "") + "PDF, JPG or PNG, max 5 MB.",
            )
            self._reqs.append((req, name, existing.get(req.pk)))

    def file_fields(self):
        return [(req, self[name], att) for req, name, att in self._reqs]

    def clean_purpose(self):
        purpose = " ".join(self.cleaned_data["purpose"].split())
        if len(purpose) < 5:
            raise forms.ValidationError("Please describe the purpose (at least 5 characters).")
        return purpose

    def clean_copies(self):
        copies = self.cleaned_data["copies"]
        if not 1 <= copies <= 5:
            raise forms.ValidationError("You can request 1 to 5 copies.")
        return copies

    def clean_preferred_pickup_date(self):
        date = self.cleaned_data["preferred_pickup_date"]
        if date < timezone.localdate():
            raise forms.ValidationError("Pickup date cannot be in the past.")
        if date > timezone.localdate() + datetime.timedelta(days=90):
            raise forms.ValidationError("Pickup date must be within the next 90 days.")
        return date

    def clean(self):
        cleaned = super().clean()
        qs = DocumentRequest.objects.filter(
            resident=self.resident, document_type=self.document_type,
            status__in=DocumentRequest.ACTIVE_STATUSES,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f"You already have an active request for {self.document_type.name}. "
                "Wait until it is completed or cancel it first."
            )
        return cleaned

    def save_attachments(self, doc_request):
        for req, name, existing in self._reqs:
            upload = self.cleaned_data.get(name)
            if upload:
                if existing:
                    existing.file.delete(save=False)
                    existing.delete()
                RequestAttachment.objects.create(request=doc_request, requirement=req, file=upload)


class StatusUpdateForm(forms.Form):
    new_status = forms.ChoiceField(label="Update status to")
    remarks = forms.CharField(
        required=False, max_length=255, label="Remarks (required when rejecting)",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, doc_request, **kwargs):
        super().__init__(*args, **kwargs)
        labels = dict(DocumentRequest.Status.choices)
        self.fields["new_status"].choices = [(s, labels[s]) for s in doc_request.next_statuses]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_status") == DocumentRequest.Status.REJECTED and not cleaned.get("remarks", "").strip():
            self.add_error("remarks", "Please give a reason when rejecting a request.")
        return cleaned
