from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ADMIN = "ADMIN"
DOCTOR = "DOCTOR"
RECEPTIONIST = "RECEPTIONIST"
PATIENT = "PATIENT"
STAFF = (ADMIN, RECEPTIONIST)


def role_required(*roles):
    """Require login AND one of the given roles (otherwise HTTP 403)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return login_required(wrapper)
    return decorator
