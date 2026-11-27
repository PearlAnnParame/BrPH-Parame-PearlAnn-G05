from django.urls import path

from . import views

urlpatterns = [
    # Resident
    path("requests/", views.request_list, name="request_list"),
    path("requests/new/", views.choose_type, name="choose_type"),
    path("requests/new/<int:type_id>/", views.request_create, name="request_create"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/edit/", views.request_edit, name="request_edit"),
    path("requests/<int:pk>/cancel/", views.request_cancel, name="request_cancel"),
    path("requests/<int:pk>/delete/", views.request_delete, name="request_delete"),
    path("requests/<int:pk>/delete/confirm/", views.request_delete_confirm, name="request_delete_confirm"),
    path("files/<int:pk>/", views.attachment_download, name="attachment_download"),
    # Admin
    path("manage/requests/", views.admin_request_list, name="admin_request_list"),
    path("manage/requests/<int:pk>/", views.admin_request_detail, name="admin_request_detail"),
    path("manage/types/", views.doctype_list, name="doctype_list"),
    path("manage/types/new/", views.doctype_form, name="doctype_create"),
    path("manage/types/<int:pk>/edit/", views.doctype_form, name="doctype_edit"),
    path("manage/types/<int:pk>/delete/", views.doctype_delete, name="doctype_delete"),
    path("manage/types/<int:pk>/delete/confirm/", views.doctype_delete_confirm, name="doctype_delete_confirm"),
]
