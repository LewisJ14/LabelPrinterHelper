from html.parser import HTMLParser
from typing import Dict
from urllib.parse import urljoin

import requests


class AstroApiError(RuntimeError):
    pass


class _CsrfParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "input":
            return
        values = dict(attrs)
        if values.get("name") == "csrf_token":
            self.token = values.get("value") or ""


class AstroClient:
    def __init__(self, base_url: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "AstroLabelPrinter/0.1",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

    def login(self, username: str, password: str) -> Dict:
        login_url = urljoin(self.base_url, "login")
        page = self.session.get(login_url, timeout=self.timeout)
        page.raise_for_status()
        parser = _CsrfParser()
        parser.feed(page.text)
        if not parser.token:
            raise AstroApiError("Astro did not provide a security token.")
        response = self.session.post(
            login_url,
            data={
                "username": username,
                "password": password,
                "csrf_token": parser.token,
                "remember": "y",
                "submit": "Log In",
            },
            timeout=self.timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        if "/login" in response.url or "/change-password" in response.url:
            raise AstroApiError("The username or password was not accepted.")
        return self.fetch_queue(after_id=0, bootstrap=True)

    def fetch_queue(self, after_id: int, bootstrap: bool = False) -> Dict:
        response = self.session.get(
            urljoin(self.base_url, "api/stock_units/label-queue"),
            params={
                "after_id": max(0, int(after_id)),
                "limit": 100,
                "bootstrap": "1" if bootstrap else "0",
            },
            timeout=self.timeout,
        )
        if response.status_code == 401:
            raise AstroApiError("Your Astro session has ended. Sign in again.")
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise AstroApiError("Astro returned an unexpected response.") from exc
        if not payload.get("success"):
            raise AstroApiError(payload.get("error") or "Could not read the label queue.")
        return payload

    def fetch_label_artwork(
        self,
        artwork_url: str,
        label_format: str = "main",
    ) -> bytes:
        response = self.session.get(
            urljoin(self.base_url, artwork_url),
            params={"format": label_format},
            timeout=self.timeout,
        )
        if response.status_code == 401:
            raise AstroApiError("Your Astro session has ended. Sign in again.")
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "image/png" not in content_type:
            raise AstroApiError("Astro did not return valid label artwork.")
        return response.content
