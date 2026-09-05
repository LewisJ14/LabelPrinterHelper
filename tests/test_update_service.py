import pytest

from label_printer_helper.update_service import UpdateManifest, UpdateService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_update_check_returns_newer_manifest(monkeypatch):
    service = UpdateService("https://example.test/update.json")
    monkeypatch.setattr(
        "label_printer_helper.update_service.requests.get",
        lambda *args, **kwargs: FakeResponse(
            {
                "version": "9.0.0",
                "download_url": "https://example.test/app.exe",
                "sha256": "abc123",
            }
        ),
    )

    manifest = service.check_for_updates()

    assert manifest == UpdateManifest(
        version="9.0.0",
        download_url="https://example.test/app.exe",
        sha256="abc123",
    )


def test_update_check_ignores_current_or_older_versions(monkeypatch):
    service = UpdateService()
    monkeypatch.setattr(
        service,
        "fetch_manifest",
        lambda: UpdateManifest(version="0.1.0"),
    )

    assert service.check_for_updates() is None


def test_update_install_requires_a_security_checksum():
    service = UpdateService()

    with pytest.raises(RuntimeError, match="security checksum"):
        service._download(
            UpdateManifest(
                version="9.0.0",
                download_url="https://example.test/app.exe",
            )
        )
