"""Production SPA static hosting with safe history fallback and cache headers."""

from pathlib import Path, PurePosixPath

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles


IMMUTABLE_SUFFIXES = {
    ".js", ".css", ".map", ".woff", ".woff2", ".ttf", ".otf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
}


class SPAStaticFiles(StaticFiles):
    """Serve Vite assets and use index.html only for client-side routes."""

    def __init__(self, *, directory: str | Path):
        super().__init__(directory=str(directory), html=True)

    @staticmethod
    def _looks_like_asset(path: str) -> bool:
        return PurePosixPath(path).suffix.lower() in IMMUTABLE_SUFFIXES

    @staticmethod
    def _apply_cache_header(path: str, response: Response) -> Response:
        if path == "index.html" or response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        elif SPAStaticFiles._looks_like_asset(path):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    async def get_response(self, path: str, scope) -> Response:
        normalized = path.strip("/") or "index.html"
        try:
            response = await super().get_response(normalized, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or self._looks_like_asset(normalized):
                raise
            response = await super().get_response("index.html", scope)
            normalized = "index.html"

        if response.status_code == 404 and not self._looks_like_asset(normalized):
            response = await super().get_response("index.html", scope)
            normalized = "index.html"
        return self._apply_cache_header(normalized, response)
