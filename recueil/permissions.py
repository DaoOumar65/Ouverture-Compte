from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


MANAGER_GROUP = "GESTIONNAIRE"
ADMIN_GROUP = "ADMIN"


def has_role(user, role):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=role).exists()
    )


def manager_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if has_role(request.user, ADMIN_GROUP) or not request.user.groups.filter(
            name=MANAGER_GROUP
        ).exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not has_role(request.user, ADMIN_GROUP):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def manager_or_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not (
            has_role(request.user, ADMIN_GROUP)
            or request.user.groups.filter(name=MANAGER_GROUP).exists()
        ):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped
