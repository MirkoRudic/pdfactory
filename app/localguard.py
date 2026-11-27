"""VAJB localguard 1.0 - a local app's server answers only its own window (RULES.md F9). Based on Subtitis krug 30.

Any web page open in the user's browser can send requests to http://127.0.0.1:<port>:
- DNS rebinding: evil.com resolves to 127.0.0.1, the page then reads our API as "same origin" -> the Host header
  is evil.com:<port>, so only 127.0.0.1 / localhost / [::1] are allowed.
- CSRF: a page posts a form to our API -> requests that change something must come from our own page
  (Origin equal to Host, or Sec-Fetch-Site same-origin / none).

FastAPI:   import localguard; localguard.install(app, log)
Flask:     @app.before_request  ->  r = localguard.check(request.host, request.method,
                                       request.headers.get("Origin"), request.headers.get("Sec-Fetch-Site"))
                                       if r: return jsonify(ok=False, error="nedozvoljen zahtev"), 403
Requests without Origin and Sec-Fetch-Site (the launcher, scripts, MCP) pass: a browser always sends them.
"""
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
SAFE = ("GET", "HEAD", "OPTIONS")


def check(host: str | None, method: str, origin: str | None, site: str | None) -> str | None:
    """Reason to refuse, or None."""
    h = (host or "").lower()
    name = h.rsplit(":", 1)[0] if not h.endswith("]") else h
    if name not in LOCAL_HOSTS:
        return f"Host {host!r}"
    if method.upper() in SAFE:
        return None
    if site and site not in ("same-origin", "none"):
        return f"Sec-Fetch-Site {site!r}"
    if origin and origin.split("://", 1)[-1].lower() != h:
        return f"Origin {origin!r}"
    return None


def install(app, log=None):
    """FastAPI / Starlette: refuses with 403 before any route runs."""
    from starlette.responses import JSONResponse

    @app.middleware("http")
    async def _localguard(request, call_next):
        why = check(request.headers.get("host"), request.method, request.headers.get("origin"),
                    request.headers.get("sec-fetch-site"))
        if why:
            if log:
                log.warning("refused %s %s: %s", request.method, request.url.path, why)
            return JSONResponse({"ok": False, "error": "Not allowed."}, status_code=403)
        return await call_next(request)
