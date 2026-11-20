from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import ProfileForm, RegistrationForm
from documents.models import DocumentRequest

from .models import User


def home(request):
    return redirect("dashboard")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully! You can now log in.")
            return redirect("login")
        messages.error(request, "Please correct the errors below.")
    return render(request, "accounts/register.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().first_name or form.get_user().username}!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.")
        return super().form_invalid(form)


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")


@login_required
def dashboard(request):
    """Send each user to the dashboard for their role."""
    if request.user.role == User.Role.ADMIN:
        return redirect("admin_dashboard")
    return redirect("resident_dashboard")


@role_required(User.Role.RESIDENT)
def resident_dashboard(request):
    mine = DocumentRequest.objects.filter(resident=request.user).select_related("document_type")
    context = {
        "total": mine.count(),
        "pending": mine.filter(status=DocumentRequest.Status.PENDING).count(),
        "ready": mine.filter(status=DocumentRequest.Status.READY).count(),
        "recent": mine[:5],
    }
    return render(request, "accounts/resident_dashboard.html", context)


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    all_requests = DocumentRequest.objects.select_related("resident", "document_type")
    context = {
        "resident_count": User.objects.filter(role=User.Role.RESIDENT).count(),
        "total": all_requests.count(),
        "pending": all_requests.filter(status=DocumentRequest.Status.PENDING).count(),
        "under_review": all_requests.filter(status=DocumentRequest.Status.UNDER_REVIEW).count(),
        "recent": all_requests.filter(status=DocumentRequest.Status.PENDING)[:5],
    }
    return render(request, "accounts/admin_dashboard.html", context)


@login_required
def profile(request):
    # Always the logged-in user's own profile; no user id in the URL
    return render(request, "accounts/profile.html", {"profile_user": request.user})


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
        messages.error(request, "Please correct the errors below.")
    return render(request, "accounts/profile_edit.html", {"form": form})
