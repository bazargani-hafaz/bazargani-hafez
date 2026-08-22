"""Defense-in-depth security hardening for Hafez store."""
import os
import time
from pathlib import Path
from collections import defaultdict, deque
from flask import abort, request

_LOGIN_WINDOW = 300
_LOGIN_LIMIT = 5
_attempts = defaultdict(deque)
ADMIN_PREFIX = os.getenv("ADMIN_PATH", "manage-7f4c9b2d6e8a1f5c3b9d")


def _client_ip():
    if os.getenv("TRUST_PROXY_HEADERS", "0").lower() in {"1", "true", "yes"}:
        return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    return request.remote_addr or "unknown"


class AdminPathMiddleware:
    """Expose the admin area only through a long, non-obvious public prefix."""
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        secret = "/" + ADMIN_PREFIX.strip("/")
        if path == "/admin" or path.startswith("/admin/"):
            return self._deny(environ, start_response)
        if path == secret or path.startswith(secret + "/"):
            environ["PATH_INFO"] = "/admin" + path[len(secret):]
        return self.application(environ, self._rewrite_location(start_response, secret))

    @staticmethod
    def _deny(environ, start_response):
        body = b"Not Found"
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]

    @staticmethod
    def _rewrite_location(start_response, secret):
        def wrapper(status, headers, exc_info=None):
            rewritten = []
            for name, value in headers:
                if name.lower() == "location":
                    value = value.replace("/admin/", secret + "/").replace("/admin", secret)
                rewritten.append((name, value))
            return start_response(status, rewritten, exc_info)
        return wrapper


def init_security(app):
    if not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is required in production")

    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=min(int(app.config.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)), 10 * 1024 * 1024),
    )

    app.wsgi_app = AdminPathMiddleware(app.wsgi_app)

    @app.before_request
    def security_request_checks():
        if os.getenv("TRUST_PROXY_HEADERS", "0").lower() not in {"1", "true", "yes"}:
            request.environ.pop("HTTP_X_FORWARDED_FOR", None)
            request.environ.pop("HTTP_X_REAL_IP", None)

        host = request.host.split(":", 1)[0].lower().rstrip(".")
        allowed = {"bazargani-hafez-production.up.railway.app"}
        allowed.update(x.strip().lower().rstrip(".") for x in os.getenv("TRUSTED_HOSTS", "").split(",") if x.strip())
        if host not in allowed and not host.endswith(".up.railway.app"):
            abort(400)

        # Login is a browser navigation/form submission and must not be blocked
        # by the strict Origin/Referer check. Protected admin mutations remain checked.
        if request.path.startswith("/admin") and request.path != "/admin/login" and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            expected = request.host_url.rstrip("/")
            if origin:
                if origin.rstrip("/") != expected:
                    abort(403)
            elif referer:
                if not referer.startswith(expected + "/"):
                    abort(403)
            else:
                abort(403)

        if request.path == "/admin/login" and request.method == "POST":
            key = _client_ip()
            now = time.monotonic()
            q = _attempts[key]
            while q and now - q[0] > _LOGIN_WINDOW:
                q.popleft()
            if len(q) >= _LOGIN_LIMIT:
                abort(429)
            q.append(now)

    @app.after_request
    def hardened_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-DNS-Prefetch-Control"] = "off"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; form-action 'self'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
            "frame-src https://www.openstreetmap.org; connect-src 'self'; upgrade-insecure-requests"
        )
        response.headers["Cache-Control"] = "no-store, max-age=0" if request.path.startswith("/admin") else response.headers.get("Cache-Control", "public, max-age=0, must-revalidate")
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers.pop("Server", None)
        return response

    @app.context_processor
    def security_context():
        version_path = Path(app.root_path) / "VERSION"
        try:
            version = version_path.read_text(encoding="utf-8").strip()
        except OSError:
            version = "unknown"
        return {"site_version": version}
