from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import (DocumentTypeForm, RequestForm, RequirementFormSet,
                    StatusUpdateForm)
from .models import DocumentRequest, DocumentType, StatusHistory

RESIDENT = User.Role.RESIDENT
ADMIN = User.Role.ADMIN
Status = DocumentRequest.Status


def log_status(doc_request, old, new, user, remarks=""):
    StatusHistory.objects.create(
        request=doc_request, old_status=old, new_status=new, changed_by=user, remarks=remarks
    )


# ---------------------------------------------------------------- Resident
@role_required(RESIDENT)
def choose_type(request):
    types = DocumentType.objects.filter(is_active=True).prefetch_related("requirements")
    return render(request, "documents/choose_type.html", {"types": types})


@role_required(RESIDENT)
def request_list(request):
    qs = DocumentRequest.objects.filter(resident=request.user).select_related("document_type")
    status = request.GET.get("status", "")
    if status in Status.values:
        qs = qs.filter(status=status)
    return render(request, "documents/request_list.html", {
        "requests": qs, "status": status, "statuses": Status.choices,
    })


@role_required(RESIDENT)
def request_create(request, type_id):
    doc_type = get_object_or_404(DocumentType, pk=type_id, is_active=True)
    form = RequestForm(request.POST or None, request.FILES or None,
                       document_type=doc_type, resident=request.user)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                doc_request = form.save(commit=False)
                doc_request.resident = request.user
                doc_request.document_type = doc_type
                doc_request.save()
                form.save_attachments(doc_request)
                log_status(doc_request, "", Status.PENDING, request.user, "Request submitted.")
            messages.success(request, f"Request {doc_request.reference_no} submitted successfully.")
            return redirect("request_detail", pk=doc_request.pk)
        messages.error(request, "Please correct the errors below.")
    return render(request, "documents/request_form.html", {"form": form, "doc_type": doc_type, "editing": False})


@role_required(RESIDENT)
def request_detail(request, pk):
    doc_request = get_object_or_404(DocumentRequest, pk=pk, resident=request.user)  # own records only
    return render(request, "documents/request_detail.html", {"r": doc_request})


@role_required(RESIDENT)
def request_edit(request, pk):
    doc_request = get_object_or_404(DocumentRequest, pk=pk, resident=request.user)
    if not doc_request.can_be_modified:
        messages.error(request, "Only pending requests can be edited.")
        return redirect("request_detail", pk=pk)
    form = RequestForm(request.POST or None, request.FILES or None, instance=doc_request,
                       document_type=doc_request.document_type, resident=request.user)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                form.save()
                form.save_attachments(doc_request)
                log_status(doc_request, Status.PENDING, Status.PENDING, request.user, "Request details updated.")
            messages.success(request, "Request updated successfully.")
            return redirect("request_detail", pk=pk)
        messages.error(request, "Please correct the errors below.")
    return render(request, "documents/request_form.html", {
        "form": form, "doc_type": doc_request.document_type, "editing": True, "r": doc_request,
    })


@role_required(RESIDENT)
@require_POST
def request_cancel(request, pk):
    doc_request = get_object_or_404(DocumentRequest, pk=pk, resident=request.user)
    if doc_request.status != Status.PENDING:
        messages.error(request, "Only pending requests can be cancelled.")
    else:
        doc_request.status = Status.CANCELLED
        doc_request.save()
        log_status(doc_request, Status.PENDING, Status.CANCELLED, request.user, "Cancelled by resident.")
        messages.success(request, "Request cancelled.")
    return redirect("request_detail", pk=pk)


@role_required(RESIDENT)
@require_POST
def request_delete(request, pk):
    doc_request = get_object_or_404(DocumentRequest, pk=pk, resident=request.user)
    if not doc_request.can_be_deleted:
        messages.error(request, "Only pending or cancelled requests can be deleted.")
        return redirect("request_detail", pk=pk)
    ref = doc_request.reference_no
    doc_request.delete()
    messages.success(request, f"Request {ref} deleted.")
    return redirect("request_list")


# ------------------------------------------------------------------- Admin
@role_required(ADMIN)
def admin_request_list(request):
    qs = DocumentRequest.objects.select_related("resident", "document_type")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    type_id = request.GET.get("type", "")
    if q:
        qs = qs.filter(
            Q(reference_no__icontains=q) | Q(resident__username__icontains=q)
            | Q(resident__first_name__icontains=q) | Q(resident__last_name__icontains=q)
        )
    if status in Status.values:
        qs = qs.filter(status=status)
    if type_id.isdigit():
        qs = qs.filter(document_type_id=type_id)
    return render(request, "documents/admin_request_list.html", {
        "requests": qs, "q": q, "status": status, "type_id": type_id,
        "statuses": Status.choices, "types": DocumentType.objects.all(),
    })


@role_required(ADMIN)
def admin_request_detail(request, pk):
    doc_request = get_object_or_404(DocumentRequest.objects.select_related("resident", "document_type"), pk=pk)
    form = None
    if doc_request.next_statuses:
        form = StatusUpdateForm(request.POST or None, doc_request=doc_request)
        if request.method == "POST":
            if form.is_valid():
                old = doc_request.status
                new = form.cleaned_data["new_status"]
                remarks = form.cleaned_data["remarks"].strip()
                doc_request.status = new
                doc_request.processed_by = request.user
                if remarks:
                    doc_request.admin_remarks = remarks
                doc_request.save()
                log_status(doc_request, old, new, request.user, remarks)
                messages.success(request, f"Status updated to {doc_request.get_status_display()}.")
                return redirect("admin_request_detail", pk=pk)
            messages.error(request, "Please correct the errors below.")
    return render(request, "documents/admin_request_detail.html", {"r": doc_request, "form": form})


@role_required(ADMIN)
def doctype_list(request):
    return render(request, "documents/doctype_list.html", {
        "types": DocumentType.objects.prefetch_related("requirements"),
    })


@role_required(ADMIN)
def doctype_form(request, pk=None):
    obj = get_object_or_404(DocumentType, pk=pk) if pk else None
    form = DocumentTypeForm(request.POST or None, instance=obj)
    formset = RequirementFormSet(request.POST or None, instance=obj)
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                saved = form.save()
                formset.instance = saved
                formset.save()
            messages.success(request, f"Document type '{saved.name}' saved.")
            return redirect("doctype_list")
        messages.error(request, "Please correct the errors below.")
    return render(request, "documents/doctype_form.html", {"form": form, "formset": formset, "obj": obj})


@role_required(ADMIN)
@require_POST
def doctype_delete(request, pk):
    obj = get_object_or_404(DocumentType, pk=pk)
    try:
        obj.delete()
        messages.success(request, f"Document type '{obj.name}' deleted.")
    except ProtectedError:
        messages.error(request, "This document type has existing requests. Mark it inactive instead of deleting.")
    return redirect("doctype_list")
