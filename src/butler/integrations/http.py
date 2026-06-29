"""Bounded HTTP reads for allowlisted public research sources."""

from __future__ import annotations

import ipaddress
import json
import random
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.parse import urlsplit


class HttpReadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    body: bytes
    content_type: str
    status: int

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text())


class BoundedHttpClient:
    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        timeout_seconds: float = 15.0,
        max_bytes: int = 2 * 1024 * 1024,
        retries: int = 2,
    ) -> None:
        self.allowed_hosts = {host.casefold() for host in allowed_hosts}
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.retries = retries
        self._opener = urllib.request.build_opener(
            _SafeRedirectHandler(self.allowed_hosts),
            urllib.request.HTTPCookieProcessor(CookieJar()),
        )

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise HttpReadError("Only absolute HTTPS source URLs are allowed")
        if parsed.hostname.casefold() not in self.allowed_hosts:
            raise HttpReadError(f"Source host is not allowlisted: {parsed.hostname}")
        self._validate_public_host(parsed.hostname)

        request_headers = {
            "Accept": (
                "application/json, application/atom+xml, application/rss+xml, text/html;q=0.8"
            ),
            "Accept-Encoding": "identity",
            "User-Agent": "Butler-Cyber-Radar/0.1 (+local-first)",
            **(headers or {}),
        }
        error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(url, headers=request_headers, method="GET")
                with self._opener.open(request, timeout=self.timeout_seconds) as response:
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise HttpReadError(f"Source response exceeds {self.max_bytes} bytes")
                    return HttpResponse(
                        body=body,
                        content_type=response.headers.get("Content-Type", ""),
                        status=response.status,
                    )
            except (OSError, urllib.error.URLError, urllib.error.HTTPError, HttpReadError) as exc:
                error = exc
                if attempt < self.retries:
                    delay = min(4.0, 0.75 * (2**attempt)) + random.uniform(0.0, 0.25)
                    time.sleep(delay)
        raise HttpReadError(f"Unable to read {parsed.hostname}: {error}") from error

    @staticmethod
    def _validate_public_host(hostname: str) -> None:
        try:
            addresses = {
                result[4][0]
                for result in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
            }
        except OSError as error:
            raise HttpReadError(f"Unable to resolve source host: {hostname}") from error
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise HttpReadError(f"Source host resolves to a non-public address: {hostname}")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        parsed = urlsplit(newurl)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.casefold() not in self.allowed_hosts
        ):
            raise HttpReadError("Source redirect left the HTTPS allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)
