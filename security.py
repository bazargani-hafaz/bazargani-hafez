"""Application security hardening for Hafez store."""
import os
from flask import abort, request


def init_security(app):
    # Production must use a stable secret from Railway/environment variables.
    if not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is required in production")

    @app.before_request
    def security_request_checks():
        # Protect every state-changing admin request against cross-site requests.
        if request.path.startswith("/admin/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            host = request.host_url.rstrip("/")

            if origin:
                if origin.rstrip("/") != host:
                    abort(403)
            elif referer:
                if not referer.startswith(host + "/"):
                    abort(403)
            else:
                # Browsers normally send Origin or Referer for these requests.
                # Rejecting requests with neither prevents header-less CSRF attempts.
                abort(403)

    @app.after_request
    def hardened_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        if request.path.startswith("/admin"):
            response.headers.setdefault("Cache-Control", "no-store, max-age=0")
            response.headers.setdefault("Pragma", "no-cache")

        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    # Avoid trusting spoofable X-Forwarded-For unless the deployment explicitly
    # opts into a trusted reverse proxy. app.py's login limiter can then use the
    # real remote address by default.
    app.config.setdefault("TRUST_PROXY_HEADERS", False)
