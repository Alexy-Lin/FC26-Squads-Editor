from typing import Dict, Iterable, List, Optional

from core.name_resolver import NameResolver
from core.sav_file import SavFile
from core.traits import FC26_TRAIT1, FC26_TRAIT2, decode_traits
from core.types import EFieldTypes
from .changes import FieldChange


class PlayerService:
    TABLE = "CZUM"
    KEY = "playerid"
    MASK_FIELDS = {"trait1", "trait2", "icontrait1", "icontrait2"}

    def __init__(self, sav: SavFile):
        if not sav.db:
            raise ValueError("存档尚未加载")
        table = sav.db.get_table(self.TABLE)
        if not table:
            raise ValueError("存档中没有球员表 CZUM")
        self.sav = sav
        self.table = table
        self.resolver = NameResolver(sav.db)

    def get_player(self, player_id: int) -> Dict:
        record = next((r for r in self.table.records if r.get(self.KEY) == player_id), None)
        if record is None:
            raise ValueError(f"未找到球员 ID {player_id}")
        return record

    def search(self, query: str, limit: Optional[int] = 50) -> List[Dict]:
        result = []
        for player_id in self.resolver.search(query, self.table):
            record = self.get_player(player_id)
            club, national = self.resolver.get_player_team(player_id)
            result.append({
                "playerid": player_id,
                "name": self.resolver.get_name(record),
                "overallrating": record.get("overallrating"),
                "potential": record.get("potential"),
                "position": record.get("preferredposition1"),
                "club": club,
                "nationalteam": national,
            })
            if limit is not None and len(result) >= limit:
                break
        return result

    def update_fields(self, player_id: int, updates: Dict[str, str]) -> List[FieldChange]:
        record = self.get_player(player_id)
        staged = []
        for requested_name, raw_value in updates.items():
            key = requested_name.strip()
            fd = self.table.get_field_by_name(key.lower()) or self.table.get_field(key)
            if not fd:
                raise ValueError(f"球员表没有字段 {requested_name}")
            field_name = fd.field_name or fd.short_name_str
            if field_name == self.KEY:
                raise ValueError("playerid 是受保护的主键，不能直接修改")
            if field_name in self.MASK_FIELDS:
                raise ValueError("特性位掩码请使用 traits API 或 CLI 的 --set-trait")
            old_value = record.get(field_name)
            new_value = self._parse_value(fd, raw_value, old_value)
            if new_value != old_value:
                staged.append((field_name, old_value, new_value))
        changes = []
        for field_name, old_value, new_value in staged:
            record[field_name] = new_value
            changes.append(FieldChange(self.TABLE, self.KEY, player_id, field_name, old_value, new_value))
        return changes

    def set_trait(self, player_id: int, bank: int, bit: int, enabled: bool, icon: bool = False):
        mapping = FC26_TRAIT1 if bank == 1 else FC26_TRAIT2 if bank == 2 else None
        if mapping is None or bit not in {item[0] for item in mapping}:
            raise ValueError(f"trait{bank} 不支持 bit {bit}")
        field = ("icontrait" if icon else "trait") + str(bank)
        record = self.get_player(player_id)
        old_value = int(record.get(field, 0) or 0)
        # trait2/icontrait2 are stored as their own 17-bit field; the mapping
        # uses combined positions 30..46 for display and decoding.
        local_bit = bit - 30 if bank == 2 else bit
        mask = 1 << local_bit
        new_value = old_value | mask if enabled else old_value & ~mask
        if new_value == old_value:
            return None
        record[field] = new_value
        return FieldChange(self.TABLE, self.KEY, player_id, field, old_value, new_value)

    def traits(self, player_id: int):
        record = self.get_player(player_id)
        return decode_traits(record.get("trait1", 0), record.get("trait2", 0))

    @staticmethod
    def parse_updates(values: Iterable[str]) -> Dict[str, str]:
        result = {}
        for value in values:
            if "=" not in value:
                raise ValueError(f"字段修改必须使用 field=value 格式：{value}")
            field, raw = value.split("=", 1)
            if not field.strip():
                raise ValueError(f"字段名不能为空：{value}")
            result[field.strip()] = raw.strip()
        return result

    @staticmethod
    def _parse_value(fd, raw_value: str, old_value):
        if fd.field_type == EFieldTypes.Integer:
            value = int(old_value or 0) + int(raw_value) if raw_value.startswith(("+", "-")) else int(raw_value)
            return max(fd.range_low, min(fd.range_high, value))
        if fd.field_type == EFieldTypes.Float:
            return float(raw_value)
        return raw_value
