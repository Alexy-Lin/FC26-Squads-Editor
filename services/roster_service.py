from typing import Dict

from core.name_resolver import NameResolver
from core.sav_file import SavFile
from .changes import ChangeSet, FieldChange


class RosterService:
    """In-place RrqT editor.

    FC26 的安全路径只改现有关系记录的 teamid/jerseynumber/position，保持
    RrqT 的记录数量和槽位布局不变。
    """

    TABLE = "RrqT"
    FREE_AGENT_TEAM_ID = 111592
    MIN_CLUB_ROSTER_SIZE = 16
    MAX_CLUB_ROSTER_SIZE = 42

    def __init__(self, sav: SavFile):
        if not sav.db:
            raise ValueError("存档尚未加载")
        table = sav.db.get_table(self.TABLE)
        if not table:
            raise ValueError("存档中没有阵容关系表 RrqT")
        self.sav = sav
        self.table = table
        self.resolver = NameResolver(sav.db)

    def links(self, player_id: int):
        return [r for r in self.table.records if r.get("playerid") == player_id]

    def team_options(self, national: bool):
        teams = self.sav.db.get_table("lyxL")
        result = []
        if not teams:
            return result
        for record in teams.records:
            team_id = record.get("teamid")
            if not team_id or self.resolver.is_national_team(team_id) != national:
                continue
            name_en, name_cn = self.resolver.get_team_names(team_id)
            if team_id == self.FREE_AGENT_TEAM_ID:
                name_en, name_cn = "Free Agents", "自由球员"
            label = " / ".join(dict.fromkeys(name for name in (name_cn, name_en) if name)) or str(team_id)
            result.append({
                "teamid": team_id,
                "name_en": name_en,
                "name_cn": name_cn,
                "label": f"{label} (ID={team_id})",
            })
        return sorted(result, key=lambda item: item["label"].casefold())

    def current_team_link(self, player_id: int, national: bool):
        return next((r for r in self.links(player_id) if self.resolver.is_national_team(r.get("teamid")) == national), None)

    def resolve_team(self, text: str, national: bool) -> int:
        query = str(text).strip().casefold()
        if not query:
            raise ValueError("球队名称不能为空")
        if query in ("自由球员", "free agent", "free agents"):
            if national:
                raise ValueError("国家队不能设置为自由球员")
            return self.FREE_AGENT_TEAM_ID
        options = self.team_options(national)
        if query.isdigit():
            matches = [item for item in options if item["teamid"] == int(query)]
        else:
            exact = []
            partial = []
            for item in options:
                values = {item["label"].casefold(), item["name_en"].casefold(), item["name_cn"].casefold()} - {""}
                if query in values:
                    exact.append(item)
                elif any(query in value for value in values):
                    partial.append(item)
            matches = exact or partial
        if not matches:
            raise ValueError(f"找不到{'国家队' if national else '俱乐部'}：{text}")
        if len(matches) > 1:
            raise ValueError("球队名称匹配多项，请输入更完整名称或球队 ID：" + "、".join(item["label"] for item in matches[:5]))
        return matches[0]["teamid"]

    def replace_team(self, player_id: int, to_team_id: int, national: bool):
        self._validate_player_and_team(player_id, to_team_id)
        if self.resolver.is_national_team(to_team_id) != national:
            raise ValueError(f"目标球队不属于{'国家队' if national else '俱乐部'}类型")
        record = self.current_team_link(player_id, national)
        if record is None:
            raise ValueError(f"球员 {player_id} 没有可原位修改的{'国家队' if national else '俱乐部'}关系记录")
        old_team_id = record.get("teamid")
        if old_team_id == to_team_id:
            return ChangeSet()
        if not national and to_team_id != self.FREE_AGENT_TEAM_ID:
            self._validate_roster_capacity(old_team_id, to_team_id)
        jersey = record.get("jerseynumber", 0) or 0
        if to_team_id != self.FREE_AGENT_TEAM_ID:
            self._validate_jersey(to_team_id, player_id, jersey)
        changes = ChangeSet()
        record["teamid"] = to_team_id
        changes.add(FieldChange(self.TABLE, "artificialkey", record.get("artificialkey"), "teamid", old_team_id, to_team_id))
        return changes

    def transfer_in_place(self, player_id: int, from_team_id: int, to_team_id: int) -> ChangeSet:
        self._validate_player_and_team(player_id, from_team_id)
        self._validate_player_and_team(player_id, to_team_id)
        if from_team_id == to_team_id:
            raise ValueError("来源球队和目标球队不能相同")
        if self.resolver.is_national_team(from_team_id) or self.resolver.is_national_team(to_team_id):
            raise ValueError("快捷转会只支持俱乐部与自由球员")
        record = next((r for r in self.table.records if r.get("playerid") == player_id and r.get("teamid") == from_team_id), None)
        if record is None:
            raise ValueError(f"球员 {player_id} 不在来源球队 {from_team_id} 中")
        return self._move_record(record, to_team_id)

    def renumber(self, team_id: int, assignments: Dict[int, int]) -> ChangeSet:
        if team_id == self.FREE_AGENT_TEAM_ID:
            raise ValueError("自由球员不支持编辑球衣号码")
        links = {r.get("playerid"): r for r in self.table.records if r.get("teamid") == team_id}
        missing = sorted(set(assignments) - set(links))
        if missing:
            raise ValueError(f"以下球员不在球队 {team_id} 中：{', '.join(map(str, missing))}")
        fd = self.table.get_field_by_name("jerseynumber")
        requested = {}
        for player_id, jersey in assignments.items():
            if jersey < fd.range_low or jersey > fd.range_high:
                raise ValueError(f"球衣号码必须在 {fd.range_low}..{fd.range_high} 之间")
            if jersey in requested:
                raise ValueError(f"球队 {team_id} 的 {jersey} 号被重复分配")
            requested[jersey] = player_id
        original = {pid: rec.get("jerseynumber", 0) for pid, rec in links.items()}
        planned = {**original, **assignments}
        occupied = {}
        for pid, jersey in planned.items():
            if jersey and jersey in occupied:
                raise ValueError(f"球队 {team_id} 的 {jersey} 号存在冲突：{occupied[jersey]} 和 {pid}")
            occupied[jersey] = pid
        changes = ChangeSet()
        for pid, jersey in planned.items():
            if jersey == original[pid]:
                continue
            rec = links[pid]
            rec["jerseynumber"] = jersey
            changes.add(FieldChange(self.TABLE, "artificialkey", rec.get("artificialkey"), "jerseynumber", original[pid], jersey))
        return changes

    def _move_record(self, record, to_team_id: int) -> ChangeSet:
        player_id = record.get("playerid")
        old_team_id = record.get("teamid")
        if old_team_id != self.FREE_AGENT_TEAM_ID and to_team_id != self.FREE_AGENT_TEAM_ID:
            self._validate_roster_capacity(old_team_id, to_team_id)
        jersey = record.get("jerseynumber", 0) or 0
        if to_team_id != self.FREE_AGENT_TEAM_ID:
            if jersey < 1 or self._jersey_conflict(to_team_id, player_id, jersey):
                jersey = self._available_jersey(to_team_id, player_id)
        changes = ChangeSet()
        record["teamid"] = to_team_id
        changes.add(FieldChange(self.TABLE, "artificialkey", record.get("artificialkey"), "teamid", old_team_id, to_team_id))
        old_jersey = record.get("jerseynumber", 0)
        if jersey != old_jersey:
            record["jerseynumber"] = jersey
            changes.add(FieldChange(self.TABLE, "artificialkey", record.get("artificialkey"), "jerseynumber", old_jersey, jersey))
        return changes

    def _validate_player_and_team(self, player_id, team_id):
        players = self.sav.db.get_table("CZUM")
        teams = self.sav.db.get_table("lyxL")
        if not players or not any(r.get("playerid") == player_id for r in players.records):
            raise ValueError(f"未找到球员 ID {player_id}")
        if not teams or not any(r.get("teamid") == team_id for r in teams.records):
            raise ValueError(f"未找到球队 ID {team_id}")

    def _validate_roster_capacity(self, from_team_id, to_team_id):
        if from_team_id != self.FREE_AGENT_TEAM_ID and sum(r.get("teamid") == from_team_id for r in self.table.records) <= self.MIN_CLUB_ROSTER_SIZE:
            raise ValueError(f"球队 {from_team_id} 转出后球员人数不能少于 {self.MIN_CLUB_ROSTER_SIZE} 人")
        if to_team_id != self.FREE_AGENT_TEAM_ID and sum(r.get("teamid") == to_team_id for r in self.table.records) >= self.MAX_CLUB_ROSTER_SIZE:
            raise ValueError(f"球队 {to_team_id} 转入后球员人数不能超过 {self.MAX_CLUB_ROSTER_SIZE} 人")

    def _jersey_conflict(self, team_id, player_id, jersey):
        return any(r.get("teamid") == team_id and r.get("playerid") != player_id and r.get("jerseynumber") == jersey for r in self.table.records)

    def _validate_jersey(self, team_id, player_id, jersey):
        fd = self.table.get_field_by_name("jerseynumber")
        if jersey < fd.range_low or jersey > fd.range_high:
            raise ValueError(f"球衣号码必须在 {fd.range_low}..{fd.range_high} 之间")
        if jersey and self._jersey_conflict(team_id, player_id, jersey):
            raise ValueError(f"球队 {team_id} 的 {jersey} 号已被占用")

    def _available_jersey(self, team_id, player_id):
        fd = self.table.get_field_by_name("jerseynumber")
        used = {r.get("jerseynumber") for r in self.table.records if r.get("teamid") == team_id and r.get("playerid") != player_id}
        for jersey in range(max(1, fd.range_low), fd.range_high + 1):
            if jersey not in used:
                return jersey
        raise ValueError(f"球队 {team_id} 没有可用球衣号码")
