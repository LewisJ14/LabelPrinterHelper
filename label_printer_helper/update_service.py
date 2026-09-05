import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import requests

from . import __version__


DEFAULT_MANIFEST_URL = (
    "https://github.com/LewisJ14/LabelPrinterHelper/"
    "releases/latest/download/update.json"
)

UPDATE_SCRIPT = r"""
param(
    [Parameter(Mandatory=$true)][string]$NewExePath,
    [Parameter(Mandatory=$true)][string]$TargetExePath
)

for ($attempt = 0; $attempt -lt 360; $attempt++) {
    try {
        if (Test-Path -LiteralPath $TargetExePath) {
            $stream = [System.IO.File]::Open(
                $TargetExePath,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $stream.Close()
        }
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

Move-Item -LiteralPath $NewExePath -Destination $TargetExePath -Force
Start-Process -FilePath $TargetExePath
"""


@dataclass
class UpdateManifest:
    version: str
    download_url: str = ""
    release_page: str = ""
    notes: str = ""
    sha256: str = ""


class UpdateService:
    def __init__(self, manifest_url: str = "", timeout: int = 15):
        self.manifest_url = (
            manifest_url
            or os.environ.get("ASTRO_LABEL_PRINTER_UPDATE_MANIFEST_URL")
            or DEFAULT_MANIFEST_URL
        )
        self.timeout = timeout

    @staticmethod
    def _version_tuple(value: str) -> Tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", str(value)))

    def fetch_manifest(self) -> UpdateManifest:
        response = requests.get(
            self.manifest_url,
            timeout=self.timeout,
            headers={"User-Agent": f"AstroLabelPrinter/{__version__}"},
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("The update manifest is not valid JSON.") from exc
        version = str(payload.get("version") or "").strip()
        if not version:
            raise RuntimeError("The update manifest does not include a version.")
        return UpdateManifest(
            version=version,
            download_url=str(payload.get("download_url") or "").strip(),
            release_page=str(payload.get("release_page") or "").strip(),
            notes=str(payload.get("notes") or "").strip(),
            sha256=str(payload.get("sha256") or "").strip().lower(),
        )

    def check_for_updates(self) -> Optional[UpdateManifest]:
        manifest = self.fetch_manifest()
        if self._version_tuple(manifest.version) > self._version_tuple(__version__):
            return manifest
        return None

    @staticmethod
    def _is_packaged() -> bool:
        return bool(getattr(sys, "frozen", False))

    def _download(self, manifest: UpdateManifest) -> Path:
        if not manifest.download_url:
            raise RuntimeError("The update does not include a download address.")
        if not re.fullmatch(r"[0-9a-f]{64}", manifest.sha256):
            raise RuntimeError(
                "The update does not include a valid security checksum."
            )
        folder = Path(tempfile.gettempdir()) / "AstroLabelPrinterUpdater"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"AstroLabelPrinter-{manifest.version}.exe"
        digest = hashlib.sha256()
        with requests.get(
            manifest.download_url,
            timeout=60,
            stream=True,
            headers={"User-Agent": f"AstroLabelPrinter/{__version__}"},
        ) as response:
            response.raise_for_status()
            with target.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        output.write(chunk)
        if digest.hexdigest().lower() != manifest.sha256:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                "The downloaded update failed its security check and was not installed."
            )
        return target

    def launch_update(self, manifest: UpdateManifest) -> bool:
        if not self._is_packaged() or sys.platform != "win32":
            address = manifest.release_page or manifest.download_url
            if not address:
                raise RuntimeError("The update does not include a download page.")
            webbrowser.open(address)
            return False
        downloaded = self._download(manifest)
        folder = downloaded.parent
        script = folder / "apply_update.ps1"
        script.write_text(UPDATE_SCRIPT.strip(), encoding="utf-8")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-NewExePath",
                str(downloaded),
                "-TargetExePath",
                str(Path(sys.executable).resolve()),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        return True
