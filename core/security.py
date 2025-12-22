from django.conf import settings


def build_csp_header() -> str:
    """Return CSP header value from settings, with a safe default."""
    raw = getattr(settings, "CSP_DEFAULT", "")
    default = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self' data:;"
    return raw.strip() or default
