import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List


APP_NAME = "AstroLabelPrinter"


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class AppConfig:
    astro_url: str = "https://dev.astro-portal.co.uk"
    last_username: str = ""
    printer_name: str = ""
    selected_users: List[str] = field(default_factory=list)
    poll_seconds: int = 3

    @classmethod
    def load(cls) -> "AppConfig":
        path = app_data_dir() / "config.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                astro_url=str(data.get("astro_url") or cls.astro_url).rstrip("/"),
                last_username=str(data.get("last_username") or ""),
                printer_name=str(data.get("printer_name") or ""),
                selected_users=list(data.get("selected_users") or []),
                poll_seconds=max(2, min(60, int(data.get("poll_seconds") or 3))),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self) -> None:
        path = app_data_dir() / "config.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temporary.replace(path)
