"""Application authentication boundary."""

from modules.extras import (
    _configured_value,
    authenticate,
    change_password,
    ensure_default_user,
    ensure_schema,
)


def initialize_auth(conn=None):
    """Ensure authentication tables exist and seed the first manager account."""
    ensure_schema(conn)
    ensure_default_user(conn)
    reset_password = _configured_value("TASK_APP_RESET_PASSWORD", "")
    if reset_password:
        username = _configured_value("TASK_APP_USERNAME", "manager")
        change_password(username, reset_password, conn)


def authenticate_user(username, password, conn=None):
    """Return the authenticated identity or ``None`` for invalid credentials."""
    if not str(username or "").strip() or not str(password or ""):
        return None
    return authenticate(username, password, conn)
