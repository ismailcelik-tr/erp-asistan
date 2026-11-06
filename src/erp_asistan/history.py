"""Conversation transcripts on disk: one JSON file per conversation."""

import json
import re
from datetime import datetime
from pathlib import Path

__all__ = ["History"]

_ID_FORMAT = "%Y%m%d-%H%M%S-%f"
_ID_PATTERN = re.compile(r"\d{8}-\d{6}-\d{6}")


def _new_id() -> str:
    return datetime.now().strftime(_ID_FORMAT)


class History:
    def __init__(self, root: Path, erp: str | None = None) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self.erp = erp
        self.current = _new_id()

    def start(self, erp: str | None = None) -> None:
        if erp:
            self.erp = erp
        self.current = _new_id()

    def add(self, event: dict) -> None:
        convo = self.get(self.current) or {
            "id": self.current,
            "started": datetime.now().isoformat(timespec="seconds"),
            "title": None,
            "erp": self.erp,
            "events": [],
        }
        if convo["title"] is None and event.get("type") == "user":
            convo["title"] = event["text"]
        convo["events"].append(event)

        # Write-then-rename: a crash mid-write must not corrupt the transcript.
        tmp = self._path(self.current).with_suffix(".tmp")
        tmp.write_text(json.dumps(convo, ensure_ascii=False, default=str))
        tmp.replace(self._path(self.current))

    def list(self) -> list[dict]:
        items = []
        for path in sorted(self._root.glob("*.json"), reverse=True):
            convo = json.loads(path.read_text())
            items.append({"id": convo["id"], "title": convo["title"], "started": convo["started"], "erp": convo.get("erp")})
        return items

    def get(self, convo_id: str) -> dict | None:
        if not _ID_PATTERN.fullmatch(convo_id):
            return None

        path = self._path(convo_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _path(self, convo_id: str) -> Path:
        return self._root / f"{convo_id}.json"
