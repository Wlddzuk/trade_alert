from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import hmac


@dataclass(frozen=True, slots=True)
class DashboardAuthSettings:
    password: str | None = None
    session_secret: str | None = None
    session_cookie_name: str = "buy_signal_dashboard_session"

    @property
    def configured(self) -> bool:
        return bool(self.password and self.session_secret)


class DashboardSessionManager:
    def __init__(self, settings: DashboardAuthSettings | None = None) -> None:
        self.settings = settings or DashboardAuthSettings()

    def authenticate(self, submitted_password: str) -> bool:
        password = self.settings.password
        if password is None:
            return False
        return hmac.compare_digest(password, submitted_password)

    def is_authenticated(self, headers: Iterable[tuple[bytes, bytes]]) -> bool:
        if not self.settings.configured:
            return False
        cookies = _parse_cookie_header(headers)
        current = cookies.get(self.settings.session_cookie_name)
        if current is None:
            return False
        return hmac.compare_digest(current, self._session_token())

    def session_cookie(self) -> str:
        return (
            f"{self.settings.session_cookie_name}={self._session_token()}; "
            "Path=/; HttpOnly; SameSite=Lax"
        )

    def _session_token(self) -> str:
        secret = self.settings.session_secret or ""
        password = self.settings.password or ""
        return hashlib.sha256(f"{password}:{secret}".encode("utf-8")).hexdigest()


def _parse_cookie_header(headers: Iterable[tuple[bytes, bytes]]) -> dict[str, str]:
    for key, value in headers:
        if key.lower() != b"cookie":
            continue
        cookies: dict[str, str] = {}
        for segment in value.decode("utf-8").split(";"):
            name, _, cookie_value = segment.strip().partition("=")
            if name and cookie_value:
                cookies[name] = cookie_value
        return cookies
    return {}
