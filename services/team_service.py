from typing import Dict, Iterable, List, Optional

from core.name_resolver import NameResolver
from core.sav_file import SavFile
from core.types import EFieldTypes
from .changes import FieldChange


class TeamService:
    TABLE = "lyxL"
    KEY = "teamid"

    def __init__(self, sav: SavFile):
        if not sav.db:
            raise ValueError("存档尚未加载")
        table = sav.db.get_table(self.TABLE)
        if not table:
            raise ValueError("存档中没有球队表 lyxL")
        self.sav = sav
        self.table = table
        self.resolver = NameResolver(sav.db)

    def get_team(self, team_id: int) -> Dict:
        record = next((r for r in self.table.records if r.get(self.KEY) == team_id), None)
        if record is None:
            raise ValueError(f"未找到球队 ID {team_id}")
        return record

    def search(self, query: str = "", limit: Optional[int] = 50) -> List[Dict]:
        needle = query.strip().casefold()
        result = []
        for record in self.table.records:
            team_id = record.get(self.KEY, 0)
            name_en, name_cn = self.resolver.get_team_names(team_id)
            raw_name = str(record.get("teamname", "") or "")
            haystack = f"{team_id} {name_en} {name_cn} {raw_name}".casefold()
            if needle and needle not in haystack:
                continue
            result.append({
                "teamid": team_id,
                "name": name_cn or name_en or raw_name or str(team_id),
                "name_en": name_en,
                "name_cn": name_cn,
                "teamname": raw_name,
                "overallrating": record.get("overallrating"),
                "attackrating": record.get("attackrating"),
                "midfieldrating": record.get("midfieldrating"),
                "defenserating": record.get("defenserating"),
            })
            if limit is not None and len(result) >= limit:
                break
        return result

    def roster(self, team_id: int) -> List[Dict]:
        self.get_team(team_id)
        links = self.sav.db.get_table("RrqT")
        result = []
        if not links:
            return result
        for record in links.records:
            if record.get("teamid") != team_id:
                continue
            pid = record.get("playerid", 0)
            result.append({
                "playerid": pid,
                "name": self.resolver.get_name_by_player_id(pid),
                "name_cn": self.resolver.get_name_cn_by_player_id(pid),
                "jerseynumber": record.get("jerseynumber"),
                "position": record.get("position"),
            })
        return sorted(result, key=lambda item: (item["jerseynumber"] or 999, item["playerid"]))

    def update_fields(self, team_id: int, updates: Dict[str, str]) -> List[FieldChange]:
        raise ValueError("FC26 球队基础数据保持只读；请使用球队阵容页调整球衣号码")
