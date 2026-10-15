from collections import Counter, defaultdict

from core.mappings import NATIONS_CN
from core.name_resolver import NameResolver
from .changes import ChangeSet, FieldChange


class NationalService:
    """Select an FC26 national-team roster in place.

    FC26 stores the national-team roster in existing ``RrqT`` links.  The
    service deliberately keeps the number of links and their artificial keys
    unchanged, so a selection can be saved without rebuilding the table.

    Candidate filtering (learned from real saves):

    * Men's and women's players share the same ``nationality`` id, so filtering
      by nationality alone offers women (Alexia Putellas et al.) for the men's
      team.  The roster's own gender decides which pool is offered.
    * Small-sided ("Rush"/5v5) placeholder players such as ``Rush Goalkeeper`` and
      manager records (a second "Zinedine Zidane" in the free-agent manager pool)
      are linked only to placeholder teams and must never be candidates.
    """

    TABLE = "RrqT"
    TEAM_TABLE = "lyxL"
    NATION_LINK_TABLE = "CxJp"
    EXPECTED_ROSTER_SIZE = 26
    MIN_ROSTER_SIZE = 5
    MIN_JERSEY_NUMBER = 1
    MAX_JERSEY_NUMBER = 99
    TEAM_NATION_ALIASES = {
        1322: 4,       # Austria (National team)
        111112: 108,   # Ivory Coast / Côte d'Ivoire
        1365: 48,      # T��rkiye / Turkey in some save encodings
    }
    #: 占位球队的判据集中在 NameResolver.NON_PLAYER_TEAM_MARKERS（5v5/Rush、经理池）。
    NON_PLAYER_MARKERS = NameResolver.NON_PLAYER_TEAM_MARKERS

    def __init__(self, rosters):
        self.rosters = rosters

    # ------------------------------------------------------------------
    # candidate pool helpers
    # ------------------------------------------------------------------
    def _players(self):
        table = self.rosters.sav.db.get_table("CZUM")
        return {record.get("playerid"): record for record in table.records} if table else {}

    def small_sided_team_ids(self):
        """Placeholder/manager team ids (5v5/Rush squads, free-agent manager pool)."""
        table = self.rosters.sav.db.get_table(self.TEAM_TABLE)
        if not table:
            return set()
        found = set()
        for record in table.records:
            team_id = record.get("teamid")
            if team_id and self.rosters.resolver.is_non_player_team(team_id):
                found.add(team_id)
        return found

    def placeholder_player_ids(self):
        """Players whose only links are placeholder/manager pools.

        Covers the 5v5/Rush placeholders (``Rush Goalkeeper``) and manager records
        such as the second "Zinedine Zidane" (id 238399) sitting in the free-agent
        manager pool - they must never be selectable as national-team players.
        """
        small = self.small_sided_team_ids()
        if not small:
            return set()
        grouped = defaultdict(list)
        for record in self.rosters.table.records:
            player_id = record.get("playerid")
            team_id = record.get("teamid")
            if player_id and team_id:
                grouped[player_id].append(team_id)
        return {
            player_id for player_id, team_ids in grouped.items()
            if any(team_id in small for team_id in team_ids)
            and all(team_id in small or self.rosters.resolver.is_national_team(team_id)
                    for team_id in team_ids)
        }

    def roster_gender(self, links) -> int:
        """Gender of the existing roster: 0 = men, 1 = women."""
        players = self._players()
        counts = Counter()
        for record in links:
            gender = players.get(record.get("playerid"), {}).get("gender")
            counts[1 if gender == 1 else 0] += 1
        return 1 if counts.get(1, 0) > counts.get(0, 0) else 0

    @staticmethod
    def expected_roster_size(links) -> int:
        """In-place selection rewrites the existing links, so keep their count.

        Men's national teams carry 26 links, the women's teams the save also
        contains carry 23.
        """
        return len(links)

    def is_candidate(self, record, gender: int, placeholders: set) -> bool:
        """Whether a player may appear in this national team's candidate list."""
        if (record.get("gender") or 0) != gender:
            return False
        return record.get("playerid") not in placeholders

    def _nation_from_links(self, team_id):
        """Read the nation id straight from the save's team-nation link table.

        Some saves store Chinese team names in ``lyxL`` (the game localises them),
        so name matching is not reliable; ``CxJp`` already carries the mapping.
        """
        table = self.rosters.sav.db.get_table(self.NATION_LINK_TABLE)
        if not table:
            return None
        for record in table.records:
            if record.get("teamid") == team_id:
                nation = record.get("nationid")
                if isinstance(nation, int) and nation > 0:
                    return nation
        return None

    def context(self, team_id):
        option = next(
            (team for team in self.rosters.team_options(True) if team["teamid"] == team_id),
            None,
        )
        if option is None:
            raise ValueError("请选择有效的国家队")
        nation = self.TEAM_NATION_ALIASES.get(team_id)
        if nation is None:
            nation = self._nation_from_links(team_id)
        if nation is None:
            nation = next(
                (code for code, name in NATIONS_CN.items()
                 if name and name in (option["name_cn"], option["name_en"])),
                None,
            )
        if nation is None:
            team_name = option["name_en"].removesuffix(" (National team)").strip()
            nation = self.rosters.resolver.get_nation_code(team_name)
        if nation is None:
            nation = self.rosters.resolver.get_nation_code(option["name_cn"])
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
        # 原位选拔只重写已有的 RrqT 记录，所以必须选满该队原有的人数。
        # 男足是 26 人，女足（本次新识别出的 113xxx/115xxx 队）是 23 人。
        expected = self.expected_roster_size(links)
        if expected < self.MIN_ROSTER_SIZE:
            raise ValueError(
                f"原名单只有 {expected} 条记录，无法安全原位选拔；请使用完整的国家队存档"
            )
        if len({record.get("playerid") for record in links}) != len(links):
            raise ValueError("原名单含重复球员，无法安全原位选拔")

        roster = body.get("roster") if isinstance(body, dict) else None
        if not isinstance(roster, list) or len(roster) != expected:
            raise ValueError(f"该队原名单是 {expected} 人，必须恰好选拔 {expected} 人")

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
