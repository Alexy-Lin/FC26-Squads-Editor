import csv
import sqlite3
from pathlib import Path

from core.sav_file import SavFile
from .changes import ChangeSet, RecordChange


class LegendService:
    """Stage missing FC26 legend records from the bundled source database."""

    PLAYER_TABLE = "CZUM"
    LINK_TABLE = "RrqT"
    PLAYER_KEY = "playerid"
    LINK_KEY = "artificialkey"
    FREE_AGENT_TEAM_ID = 111592
    ICON_LIST = Path(__file__).resolve().parent.parent / "data" / "icon_hero_list.csv"
    DATABASE = Path(__file__).resolve().parent.parent / "data" / "legend_database.db"

    def __init__(self, sav: SavFile):
        if not sav.db:
            raise ValueError("存档尚未加载")
        self.sav = sav
        self.players = sav.db.get_table(self.PLAYER_TABLE)
        self.links = sav.db.get_table(self.LINK_TABLE)
        if not self.players or not self.links:
            raise ValueError("存档缺少传奇球员所需的 CZUM 或 RrqT 表")

    @staticmethod
    def _value(source, key, default=0):
        if key in source:
            return source[key] if source[key] is not None else default
        lowered = key.casefold()
        for source_key, value in source.items():
            if str(source_key).casefold() == lowered:
                return value if value is not None else default
        return default

    def _catalog(self):
        if not self.ICON_LIST.is_file():
            raise ValueError("缺少传奇球员清单 data/icon_hero_list.csv")
        entries = []
        seen = set()
        with self.ICON_LIST.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                raw_id = (row.get("IDs") or "").strip()
                if not raw_id.isdigit():
                    continue
                comment = (row.get("COMMENT") or "").upper()
                if "WOMEN" in comment or "DELETED" in comment:
                    continue
                player_id = int(raw_id)
                if player_id in seen:
                    continue
                seen.add(player_id)
                entries.append({
                    "playerid": player_id,
                    "name": (row.get("Full Name") or "").strip() or f"Player #{player_id}",
                })
        return entries

    def _source_records(self):
        if not self.DATABASE.is_file():
            raise ValueError("缺少传奇球员源数据库 data/legend_database.db")
        with sqlite3.connect(self.DATABASE) as connection:
            connection.row_factory = sqlite3.Row
            try:
                players = {
                    int(row[self.PLAYER_KEY]): dict(row)
                    for row in connection.execute("SELECT * FROM czum")
                    if row[self.PLAYER_KEY] is not None
                }
                links = {}
                for row in connection.execute("SELECT * FROM rrqt"):
                    item = dict(row)
                    player_id = item.get(self.PLAYER_KEY)
                    if player_id is not None:
                        links.setdefault(int(player_id), []).append(item)
            except sqlite3.Error as exc:
                raise ValueError(f"传奇球员源数据库无法读取：{exc}") from exc
        return players, links

    def _available(self):
        source_players, source_links = self._source_records()
        current_ids = {
            record.get(self.PLAYER_KEY)
            for record in self.players.records
            if record.get(self.PLAYER_KEY)
        }
        result = []
        for item in self._catalog():
            player_id = item["playerid"]
            source = source_players.get(player_id)
            links = source_links.get(player_id, [])
            if not source or not links:
                continue
            result.append({
                **item,
                "overallrating": self._value(source, "overallrating", 0),
                "missing": player_id not in current_ids,
            })
        return result, source_players, source_links

    def preview(self):
        available, _source_players, _source_links = self._available()
        missing = [item for item in available if item["missing"]]
        return {
            "available_count": len(available),
            "missing_count": len(missing),
            "missing": missing,
        }

    def _record_for_table(self, table, source, player_id, link_key=None):
        record = {}
        for field in table.fields:
            key = field.field_name or field.short_name_str
            record[key] = self._value(source, key)
            if "playerid" in key.casefold() or key == "ykFq":
                record[key] = player_id
        if link_key is not None:
            record[self.LINK_KEY] = link_key
            if "teamid" in record:
                record["teamid"] = self.FREE_AGENT_TEAM_ID
        return record

    def add_missing_legends(self):
        available, source_players, source_links = self._available()
        missing = [item for item in available if item["missing"]]
        if not missing:
            return ChangeSet(), {"added": 0, "legends": []}

        player_capacity = self.players.n_records - len(self.players.records)
        link_count = sum(len(source_links[item["playerid"]]) for item in missing)
        link_capacity = self.links.n_records - len(self.links.records)
        if len(missing) > player_capacity:
            raise ValueError(f"CZUM 没有足够空位，至少还需要 {len(missing)} 个空位")
        if link_count > link_capacity:
            raise ValueError(f"RrqT 没有足够空位，至少还需要 {link_count} 个空位")

        max_artificialkey = max(
            (self._value(record, self.LINK_KEY, 0) or 0 for record in self.links.records),
            default=0,
        )
        player_additions = []
        link_additions = []
        changes = ChangeSet()
        player_index = len(self.players.records)
        link_index = len(self.links.records)
        for item in missing:
            player_id = item["playerid"]
            player_record = self._record_for_table(
                self.players,
                source_players[player_id],
                player_id,
            )
            player_additions.append(player_record)
            changes.add(RecordChange(
                self.PLAYER_TABLE,
                self.PLAYER_KEY,
                player_id,
                "add",
                dict(player_record),
                player_index,
            ))
            player_index += 1
            for source_link in source_links[player_id]:
                max_artificialkey += 1
                link_record = self._record_for_table(
                    self.links,
                    source_link,
                    player_id,
                    max_artificialkey,
                )
                link_additions.append(link_record)
                changes.add(RecordChange(
                    self.LINK_TABLE,
                    self.LINK_KEY,
                    max_artificialkey,
                    "add",
                    dict(link_record),
                    link_index,
                ))
                link_index += 1

        self.players.records.extend(player_additions)
        self.links.records.extend(link_additions)
        for table in (self.players, self.links):
            table.n_valid_records = len(table.records)
            if table.n_valid_records > table.n_records:
                table.n_records = table.n_valid_records
            table.n_bit_records = table.n_records * table.record_size
        return changes, {
            "added": len(player_additions),
            "legends": missing,
        }
