from django.contrib import admin

from .models import DocumentRequest, DocumentType, RequestAttachment, Requirement, StatusHistory


class RequirementInline(admin.TabularInline):
    model = Requirement
    extra = 1


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "fee", "is_active")
    inlines = [RequirementInline]


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = ("reference_no", "resident", "document_type", "status", "created_at")
    list_filter = ("status", "document_type")


admin.site.register(RequestAttachment)
admin.site.register(StatusHistory)
