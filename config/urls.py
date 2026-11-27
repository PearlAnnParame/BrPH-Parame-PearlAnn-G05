from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("documents.urls")),
    # Only profile photos are served publicly. Request attachments (IDs, certificates) are
    # private and are served by documents.views.attachment_download after an access check.
    re_path(r"^media/(?P<path>profiles/.+)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
