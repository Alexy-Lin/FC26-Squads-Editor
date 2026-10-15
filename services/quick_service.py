from __future__ import annotations

import datetime
import json
from pathlib import Path

from core.sav_file import SavFile
from .birthdates import AGE_BIRTHDATES, BIRTHDATE_AGE18, BIRTHDATE_MIN, describe
from .changes import ChangeSet, FieldChange


class QuickFeatureService:
    """Implement small, reversible bulk edits for the currently loaded save."""

    TABLE = "CZUM"
    KEY = "playerid"
    BIRTHDATE_FIELD = "birthdate"

    # FC stores birthdate as days since 1582-10-14.  2007-07-01 makes a
    # player 18 during the 2025/26 season, which is the season used by FC26.
    BIRTHDATE_AGE18 = BIRTHDATE_AGE18

    SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "birthdate_snapshots"

    def __init__(self, sav: SavFile):
        if not sav.db:
            raise ValueError("存档尚未加载")
        table = sav.db.get_table(self.TABLE)
        if not table:
            raise ValueError("存档中没有球员表 CZUM")
        if not table.get_field_by_name(self.BIRTHDATE_FIELD) and not table.get_field(self.BIRTHDATE_FIELD):
            raise ValueError("球员表没有 birthdate 字段")
        self.sav = sav
        self.table = table

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _players(self):
        for record in self.table.records:
            player_id = record.get(self.KEY, 0)
            if isinstance(player_id, int) and player_id > 0:
                yield player_id, record

    def snapshot_paths(self):
        """``(per_save, latest)`` snapshot paths for the loaded save."""
        stem = self.sav.filepath.stem if self.sav.filepath else "unsaved"
        return self.SNAPSHOT_DIR / f"{stem}.json", self.SNAPSHOT_DIR / "latest.json"

    def _read_snapshot(self, path: Path):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        birthdates = payload.get("birthdates")
        if not isinstance(birthdates, dict):
            return None
        cleaned = {}
        for key, value in birthdates.items():
            try:
                cleaned[int(key)] = int(value)
            except (TypeError, ValueError):
                continue
        if not cleaned:
            return None
        payload["birthdates"] = cleaned
        return payload

    def load_birthdate_snapshot(self):
        """Return the snapshot that "restore original birthdays" should use."""
        per_save, latest = self.snapshot_paths()
        for path in (per_save, latest):
            if path.is_file():
                payload = self._read_snapshot(path)
                if payload:
                    payload["path"] = str(path)
                    return payload
        return None

    def save_birthdate_snapshot(self, force: bool = False):
        """Remember the current birthdates before a global age change.

        The earliest snapshot wins, so running "everyone is 18" twice never
        overwrites the real birthdays with 18-year-old values.
        """
        if not self.sav.filepath:
            return None
        per_save, latest = self.snapshot_paths()
        payload = {
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "save": str(self.sav.filepath),
            "birthdates": {str(pid): record.get(self.BIRTHDATE_FIELD, 0)
                           for pid, record in self._players()},
        }
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=1)
        for path in {per_save, latest}:
            if force or not path.is_file():
                path.write_text(text, encoding="utf-8")
        return per_save

    # ------------------------------------------------------------------
    # quick features
    # ------------------------------------------------------------------
    def set_all_players_age(self, age: int = 18) -> ChangeSet:
        """Set every valid player's birthdate to the FC26 age-N value."""
        if age not in AGE_BIRTHDATES:
            raise ValueError(f"只支持 17 或 18 岁，收到 {age}")
        target = AGE_BIRTHDATES[age]
        self.save_birthdate_snapshot()
        changes = ChangeSet()
        for player_id, record in self._players():
            old_value = record.get(self.BIRTHDATE_FIELD, 0)
            if old_value == target:
                continue
            record[self.BIRTHDATE_FIELD] = target
            changes.add(FieldChange(
                self.TABLE,
                self.KEY,
                player_id,
                self.BIRTHDATE_FIELD,
                old_value,
                target,
            ))
        return changes

    def set_all_players_age18(self) -> ChangeSet:
        """Set every valid player's birthdate to the FC26 age-18 value."""
        return self.set_all_players_age(18)

    def preview_original_birthdays(self) -> dict:
        """Describe what "restore original birthdays" would do."""
        payload = self.load_birthdate_snapshot()
        if not payload:
            return {
                "available": False,
                "restore_count": 0,
                "message": "还没有生日快照：请先执行一次「全员 18 岁」，编辑器会自动记录原始生日。",
            }
        birthdates = payload["birthdates"]
        restore_count = 0
        for player_id, record in self._players():
            original = birthdates.get(player_id)
            if original is None:
                continue
            if record.get(self.BIRTHDATE_FIELD, 0) != original:
                restore_count += 1
        return {
            "available": True,
            "restore_count": restore_count,
            "snapshot_path": payload.get("path", ""),
            "snapshot_save": payload.get("save", ""),
            "snapshot_created": payload.get("created", ""),
            "saved_players": len(birthdates),
            "message": f"快照来自 {payload.get('save', '')}（{payload.get('created', '')}）",
        }

    def restore_original_birthdays(self) -> ChangeSet:
        """Undo a global age change using the recorded snapshot."""
        payload = self.load_birthdate_snapshot()
        if not payload:
            raise ValueError(
                "没有生日快照，无法恢复原始生日。请先执行一次「全员 18 岁」，"
                "或手动打开原始存档另存一份。"
            )
        birthdates = payload["birthdates"]
        changes = ChangeSet()
        for player_id, record in self._players():
            original = birthdates.get(player_id)
            if original is None:
                continue
            current = record.get(self.BIRTHDATE_FIELD, 0)
            if current == original:
                continue
            record[self.BIRTHDATE_FIELD] = original
            changes.add(FieldChange(
                self.TABLE,
                self.KEY,
                player_id,
                self.BIRTHDATE_FIELD,
                current,
                original,
            ))
        return changes

    # ------------------------------------------------------------------
    # diagnostics
    # ------------------------------------------------------------------
    def birthdate_report(self) -> dict:
        """Count players whose birthdate the game would silently drop."""
        invalid = []
        for player_id, record in self._players():
            value = record.get(self.BIRTHDATE_FIELD, 0)
            if value and int(value) < BIRTHDATE_MIN:
                invalid.append({
                    "playerid": player_id,
                    "birthdate": int(value),
                    "date": describe(value),
                })
        return {
            "min_allowed": BIRTHDATE_MIN,
            "invalid_count": len(invalid),
            "invalid": invalid[:50],
        }
