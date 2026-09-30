"""A polite HTTP client: obeys robots.txt, waits between requests, caches every response.

Cache files live under data/cache/<host>/ so development never re-downloads anything.
"""
import hashlib
import logging
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.core.config import CACHE_DIR, get_settings

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    """The site's robots.txt forbids this URL. We never bypass this."""


class EmptyResponse(Exception):
    """The server answered 200 with no body."""


class PoliteClient:
    def __init__(self, cache_dir: Path = CACHE_DIR, min_interval: float | None = None):
        settings = get_settings()
        self.user_agent = settings.harvest_user_agent
        self.min_interval = min_interval if min_interval is not None else settings.harvest_min_interval_seconds
        self.cache_dir = cache_dir
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent}, timeout=120, follow_redirects=True
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.network_requests = 0

    # --- robots.txt -------------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._wait(parts.netloc)
            resp = self._client.get(origin + "/robots.txt")
            self.network_requests += 1
            if resp.status_code == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robots[origin] = rp
            else:
                self._robots[origin] = None  # no robots.txt: nothing is disallowed
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url)
        return rp is None or rp.can_fetch(self.user_agent, url)

    # --- rate limiting ----------------------------------------------------
    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request[host] = time.monotonic()

    # --- cache ------------------------------------------------------------
    def cache_path_for(self, url: str, suffix: str = "") -> Path:
        parts = urlsplit(url)
        digest = hashlib.sha1(url.encode()).hexdigest()[:16]
        return self.cache_dir / parts.netloc.replace(":", "_") / f"{digest}{suffix}"

    def get(self, url: str, *, suffix: str = "", refresh: bool = False) -> bytes:
        """Return the body of `url`, from cache if we have it."""
        path = self.cache_path_for(url, suffix)
        if path.exists() and path.stat().st_size == 0:
            path.unlink()  # left over from before empty bodies were rejected
        if path.exists() and not refresh:
            return path.read_bytes()
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        self._wait(urlsplit(url).netloc)
        log.info("GET %s", url)
        resp = self._client.get(url)
        self.network_requests += 1
        resp.raise_for_status()
        if not resp.content:
            raise EmptyResponse(url)  # never cache an empty body as if it were the file
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(resp.content)
        tmp.replace(path)  # atomic: a crash never leaves a half-written cache file
        return resp.content

    def close(self) -> None:
        self._client.close()
