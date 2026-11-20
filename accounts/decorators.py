from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(role):
    """Allow only users with the given role; others go back to their own dashboard."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role != role:
                messages.error(request, "You are not allowed to open that page.")
                return redirect("dashboard")
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
