import pytest

from label_printer_helper.api import AstroApiError, AstroClient


class FakeResponse:
    def __init__(self, content_type="image/png", status_code=200, content=b"png"):
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_label_artwork_uses_the_authenticated_astro_session(monkeypatch):
    client = AstroClient("https://dev.astro-portal.co.uk")
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        return FakeResponse(content=b"server-rendered-label")

    monkeypatch.setattr(client.session, "get", fake_get)

    result = client.fetch_label_artwork(
        "/api/stock_units/label-artwork/42.png"
    )

    assert result == b"server-rendered-label"
    assert calls == [
        (
            "https://dev.astro-portal.co.uk/api/stock_units/label-artwork/42.png",
            {"format": "main"},
            20,
        )
    ]


def test_fetch_label_artwork_rejects_an_html_login_page(monkeypatch):
    client = AstroClient("https://dev.astro-portal.co.uk")
    monkeypatch.setattr(
        client.session,
        "get",
        lambda url, params, timeout: FakeResponse(content_type="text/html"),
    )

    with pytest.raises(AstroApiError, match="valid label artwork"):
        client.fetch_label_artwork("/label.png")


def test_fetch_label_artwork_requests_selected_format(monkeypatch):
    client = AstroClient("https://dev.astro-portal.co.uk")
    requested = {}

    def fake_get(url, params, timeout):
        requested.update(params)
        return FakeResponse()

    monkeypatch.setattr(client.session, "get", fake_get)

    client.fetch_label_artwork("/label.png", "second_checked")

    assert requested == {"format": "second_checked"}
