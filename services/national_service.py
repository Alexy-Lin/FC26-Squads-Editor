from core.mappings import NATIONS_CN
from .changes import ChangeSet, FieldChange


class NationalService:
    """Select an FC26 national-team roster in place.

    FC26 stores the national-team roster in existing ``RrqT`` links.  The
    service deliberately keeps the number of links and their artificial keys
    unchanged, so a selection can be saved without rebuilding the table.
    """

    TABLE = "RrqT"
    EXPECTED_ROSTER_SIZE = 26
    MIN_JERSEY_NUMBER = 1
    MAX_JERSEY_NUMBER = 99
    TEAM_NATION_ALIASES = {
        1322: 4,       # Austria (National team)
        111112: 108,   # Ivory Coast / Côte d'Ivoire
        1365: 48,      # T��rkiye / Turkey in some save encodings
    }

    def __init__(self, rosters):
        self.rosters = rosters

    def context(self, team_id):
        option = next(
            (team for team in self.rosters.team_options(True) if team["teamid"] == team_id),
            None,
        )
        if option is None:
            raise ValueError("请选择有效的国家队")
        nation = self.TEAM_NATION_ALIASES.get(team_id)
        if nation is None:
            nation = next(
                (code for code, name in NATIONS_CN.items() if name == option["name_cn"]),
                None,
            )
        if nation is None:
            team_name = option["name_en"].removesuffix(" (National team)").strip()
            nation = self.rosters.resolver.get_nation_code(team_name)
        if nation is None:
            raise ValueError("无法确认国家队对应的国籍，暂不支持选拔")
        links = [
            record
            for record in self.rosters.table.records
            if record.get("teamid") == team_id
        ]
        return nation, links

    def apply(self, team_id, body):
        nation, links = self.context(team_id)
        if len(links) != self.EXPECTED_ROSTER_SIZE:
            raise ValueError(
                f"原名单不是 {self.EXPECTED_ROSTER_SIZE} 人，无法安全原位选拔；"
                "请使用完整的国家队存档"
            )
        if len({record.get("playerid") for record in links}) != self.EXPECTED_ROSTER_SIZE:
            raise ValueError("原名单含重复球员，无法安全原位选拔")

        roster = body.get("roster") if isinstance(body, dict) else None
        if not isinstance(roster, list) or len(roster) != self.EXPECTED_ROSTER_SIZE:
            raise ValueError(f"国家队必须恰好选拔 {self.EXPECTED_ROSTER_SIZE} 人")

        players_table = self.rosters.sav.db.get_table("CZUM")
        players = {record.get("playerid"): record for record in players_table.records}
        planned = {}
        numbers = set()
        for item in roster:
            if not isinstance(item, dict):
                raise ValueError("球员名单格式无效")
            player_id = item.get("playerid")
            jersey = item.get("jerseynumber")
            if type(player_id) is not int or player_id not in players or player_id in planned:
                raise ValueError("名单含有不存在或重复的球员")
            if players[player_id].get("nationality") != nation:
                raise ValueError(f"球员 {player_id} 的国籍与国家队不一致")
            if (
                type(jersey) is not int
                or not self.MIN_JERSEY_NUMBER <= jersey <= self.MAX_JERSEY_NUMBER
                or jersey in numbers
            ):
                raise ValueError(
                    f"球衣号码必须为 {self.MIN_JERSEY_NUMBER}–{self.MAX_JERSEY_NUMBER} 的整数且不能重复"
                )
            if any(
                record.get("teamid") != team_id
                and self.rosters.resolver.is_national_team(record.get("teamid"))
                for record in self.rosters.links(player_id)
            ):
                raise ValueError(f"球员 {player_id} 已在其他国家队，不能重复选拔")
            planned[player_id] = jersey
            numbers.add(jersey)

        retained = {record.get("playerid") for record in links} & planned.keys()
        incoming = iter(player_id for player_id in planned if player_id not in retained)
        changes = ChangeSet()
        for record in links:
            player_id = (
                record["playerid"]
                if record["playerid"] in retained
                else next(incoming)
            )
            for field, value in (
                ("playerid", player_id),
                ("jerseynumber", planned[player_id]),
            ):
                old_value = record.get(field)
                if old_value != value:
                    changes.add(
                        FieldChange(
                            self.TABLE,
                            "artificialkey",
                            record.get("artificialkey"),
                            field,
                            old_value,
                            value,
                        )
                    )

        for change in changes:
            record = next(
                item
                for item in links
                if item.get("artificialkey") == change.key_value
            )
            record[change.field] = change.new_value
        return changes
