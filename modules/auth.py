"""Application authentication boundary."""

from modules.extras import authenticate, ensure_default_user, ensure_schema


def initialize_auth(conn=None):
    """Ensure authentication tables exist and seed the first manager account."""
    ensure_schema(conn)
    ensure_default_user(conn)


def authenticate_user(username, password, conn=None):
    """Return the authenticated identity or ``None`` for invalid credentials."""
    if not str(username or "").strip() or not str(password or ""):
        return None
    return authenticate(username, password, conn)
