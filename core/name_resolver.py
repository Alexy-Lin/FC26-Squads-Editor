"""Player name resolver — builds lookup tables from available name sources."""
import csv
from pathlib import Path
from typing import Dict, Optional, Tuple

from .table import Table
from .db_file import DbFile

# The project keeps the FST-compatible lookup files beside the runtime data.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FST_CONFIG_DIR = PROJECT_ROOT / "config"


class NameResolver:
    """Resolves player names and nationality from available data sources.

    Player name sources (in priority order):
      1. player_names.csv:       static CSV file with player ID → display name overrides
      2. editedplayernames:      playerid → firstname/surname (from save file)
      3. playernames.txt (FST):  nameid → name string (41190 entries, full EA database)
      4. dcplayernames (save):   nameid → name string (fallback if FST file unavailable)
      5. commonnameid fallback:  look up in dcplayernames
      6. Fallback: "Player #{pid}"

    Nationality source:
      - data/nations.csv:        English names (218 nations)
      - config/nationalities.txt:  Chinese names (optional fallback)

    Team name sources:
      - data/teams_cn.csv:       Chinese team names (287 teams)
      - lyxL (teams table):      English team names from the save file
    """

    def __init__(self, db: DbFile):
        self._db = db
        self._edited: Dict[int, tuple[str, str, str]] = {}  # pid -> (first, last, jersey)
        self._dc_names: Dict[int, str] = {}  # nameid -> best name string
        self._csv_names: Dict[int, str] = {}  # pid -> display_name (from CSV)
        self._csv_common_names: Dict[int, str] = {}  # pid -> common_name (from common_names.csv)
        self._nations: Dict[int, str] = {}  # nationid -> nationname (from nations.csv)
        self._team_names_cn: Dict[int, str] = {}  # teamid -> Chinese name
        self._team_names_en: Dict[int, str] = {}  # teamid -> English name (from save)
        self._player_team: Dict[int, list] = {}  # playerid -> [teamid, ...] (from RrqT)
        self._player_jersey: Dict[int, int] = {}  # playerid -> jersey number
        players_tbl = db.get_table("CZUM")
        self._players_by_id = {
            record.get("playerid"): record
            for record in (players_tbl.records if players_tbl else [])
            if record.get("playerid")
        }

        # Build team name lookup from teams_cn.csv
        teams_path = Path(__file__).resolve().parent.parent / "data" / "teams_cn.csv"
        if teams_path.exists():
            try:
                with teams_path.open("r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        tid = (row.get("teamid") or "").strip()
                        cn = (row.get("teamname_cn") or "").strip()
                        if tid.isdigit() and cn:
                            self._team_names_cn[int(tid)] = cn
            except Exception:
                pass

        # Build team name lookup from save file's lyxL (teams) table
        teams_tbl = db.get_table("lyxL")
        if teams_tbl:
            for r in teams_tbl.records:
                tid = r.get("teamid", 0)
                name = r.get("teamname", "")
                if tid and name:
                    self._team_names_en[tid] = name

        # Build player→team mapping from RrqT (teamplayerlinks)
        # Players can have multiple entries (club + national team)
        rqt = db.get_table("RrqT")
        if rqt:
            for r in rqt.records:
                pid = r.get("playerid", 0)
                tid = r.get("teamid", 0)
                num = r.get("jerseynumber", 0)
                if pid and tid:
                    if pid not in self._player_team:
                        self._player_team[pid] = []
                    self._player_team[pid].append(tid)
                    if num and pid not in self._player_jersey:
                        self._player_jersey[pid] = num

        # Build editedplayernames lookup
        et = db.get_table("nQVU")
        if et:
            for r in et.records:
                pid = r.get("playerid", 0)
                first = r.get("firstname", "") or ""
                last = r.get("surname", "") or ""
                jersey = r.get("playerjerseyname", "") or ""
                if pid > 0 and (first or last):
                    self._edited[pid] = (first, last, jersey)

        # Build dcplayernames lookup: FST playernames.txt first, supplement from save bneD
        pn_path = FST_CONFIG_DIR / "playernames.txt"
        if pn_path.exists():
            self._load_playernames(pn_path)
        dt = db.get_table("bneD")
        if dt:
            for r in dt.records:
                nid = r.get("nameid", 0)
                name_str = r.get("name", "") or ""
                if nid > 0 and name_str and nid not in self._dc_names:
                    self._dc_names[nid] = name_str

        # Build nation lookup: supplement English names with Chinese from FST
        nat_fst_path = FST_CONFIG_DIR / "nationalities.txt"
        if nat_fst_path.exists():
            self._load_nationalities_fst(nat_fst_path)

        # Build CSV name lookup from the static player_names.csv file
        csv_path = Path(__file__).resolve().parent.parent / "data" / "player_names.csv"
        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        pid_str = (row.get("playerid") or "").strip()
                        display_name = (row.get("display_name") or "").strip()
                        common_name = (row.get("common_name") or "").strip()
                        if pid_str.isdigit() and display_name:
                            self._csv_names[int(pid_str)] = display_name
                        # Also store common_name column as a common name source
                        if pid_str.isdigit() and common_name and common_name != display_name:
                            self._csv_common_names[int(pid_str)] = common_name
            except Exception:
                pass

        # Build common name lookup from common_names.csv (Icon short names)
        common_csv = Path(__file__).resolve().parent.parent / "data" / "common_names.csv"
        if common_csv.exists():
            try:
                with common_csv.open("r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        pid_str = (row.get("playerid") or "").strip()
                        name = (row.get("common_name") or "").strip()
                        if pid_str.isdigit() and name:
                            self._csv_common_names[int(pid_str)] = name
            except Exception:
                pass

        # Build nation name lookup from nations.csv (extracted from template DB)
        nations_path = Path(__file__).resolve().parent.parent / "data" / "nations.csv"
        if nations_path.exists():
            try:
                with nations_path.open("r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        nid_str = (row.get("nationid") or "").strip()
                        name = (row.get("nationname") or "").strip()
                        if nid_str.isdigit() and name:
                            self._nations[int(nid_str)] = name
            except Exception:
                pass

    def get_nation_name(self, nationid: int) -> str:
        """Get English name for a nationality code."""
        return self._nations.get(nationid, str(nationid))

    def get_nation_name_cn(self, nationid: int) -> str:
        """Return the configured Chinese nation name when available."""
        path = FST_CONFIG_DIR / "nationalities.txt"
        if not hasattr(self, "_nations_cn"):
            self._nations_cn = {}
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        if key.strip().isdigit() and value.strip():
                            self._nations_cn[int(key.strip())] = value.strip()
            except OSError:
                pass
        return self._nations_cn.get(nationid, self.get_nation_name(nationid))

    def get_nation_code(self, nation_name: str) -> Optional[int]:
        """Reverse lookup: nation name → code."""
        for code, name in self._nations.items():
            if name.lower() == nation_name.lower():
                return code
        return None

    def get_nations(self) -> Dict[int, str]:
        """Get the full nation mapping (code → name)."""
        return dict(self._nations)

    def get_name(self, record: dict) -> str:
        """Build the best possible display name for a player record."""
        pid = record.get("playerid", 0)

        # 1. CSV name lookup (user-curated, overrides in-game edited names)
        if pid in self._csv_names:
            return self._csv_names[pid]

        # 2. Edited name (from save file's editedplayernames)
        if pid in self._edited:
            first, last, jersey = self._edited[pid]
            display = f"{first} {last}".strip()
            if not display:
                display = jersey
            return display

        # 3. Try commonnameid -> dcplayernames
        cnid = record.get("commonnameid", 0)
        if cnid > 0 and cnid in self._dc_names:
            return self._dc_names.get(cnid, "")

        # 4. Try firstnameid + lastnameid -> dcplayernames
        fnid = record.get("firstnameid", 0) or 0
        lnid = record.get("lastnameid", 0) or 0
        first = self._dc_names.get(fnid, "") if fnid > 0 else ""
        last = self._dc_names.get(lnid, "") if lnid > 0 else ""
        if first and last:
            return f"{first} {last}"
        if last:
            return last
        if first:
            return first

        # 5. Fallback
        return f"Player #{pid}"

    def get_common_name(self, record: dict) -> str:
        """Get the common/short name for a player (e.g. 'Ronaldo' for R9, 'Kaká')."""
        pid = record.get("playerid", 0)
        # 1. Common names CSV (Icons)
        if pid in self._csv_common_names:
            return self._csv_common_names[pid]
        # 2. Look up commonnameid in dcplayernames
        cnid = record.get("commonnameid", 0)
        if cnid > 0 and cnid in self._dc_names:
            return self._dc_names[cnid]
        # 3. CSV display name (might differ from common name, but useful fallback)
        if pid in self._csv_names:
            return self._csv_names[pid]
        return ""

    def get_name_by_player_id(self, playerid: int) -> str:
        """Get display name for a player by ID."""
        record = self._players_by_id.get(playerid)
        if record:
            return self.get_name(record)
        return f"Player #{playerid}"

    def get_name_cn(self, record: dict) -> str:
        """Return a localized display name, falling back to the resolved name."""
        return self.get_name(record)

    def get_name_cn_by_player_id(self, playerid: int) -> str:
        return self.get_name_by_player_id(playerid)

    # National team IDs (from 国家队ID.txt)
    _NATIONAL_TEAM_IDS = {
        1318, 1322, 1325, 1327, 1330, 1331, 1334, 1335, 1337, 1338,
        1341, 1343, 1352, 1353, 1354, 1355, 1356, 1357, 1359, 1361,
        1362, 1363, 1364, 1365, 1367, 1369, 1370, 1375, 1377, 1386,
        1387, 1395, 1415, 1886, 105035,
        110081, 111099, 111108, 111109, 111112, 111130, 111451,
        111455, 111459, 111465, 111466, 111473, 111487,
    }

    def get_player_team(self, playerid: int) -> tuple[Optional[str], Optional[str]]:
        """Get (club_name, national_team_name) for a player, or (None, None)."""
        teamids = self._player_team.get(playerid, [])
        if not teamids:
            return None, None
        club = None
        nat = None
        for tid in teamids:
            name = self._team_names_cn.get(tid, self._team_names_en.get(tid, None))
            if tid in self._NATIONAL_TEAM_IDS:
                nat = name or str(tid)
            else:
                club = name or str(tid)
        return club, nat

    def get_player_team_ids(self, playerid: int) -> tuple[Optional[int], Optional[int]]:
        """Return (club_id, national_team_id) for a player."""
        teamids = self._player_team.get(playerid, [])
        club = next((tid for tid in teamids if not self.is_national_team(tid)), None)
        national = next((tid for tid in teamids if self.is_national_team(tid)), None)
        return club, national

    def get_team_names(self, teamid: int) -> tuple[str, str]:
        return self._team_names_en.get(teamid, ""), self._team_names_cn.get(teamid, "")

    def is_national_team(self, teamid: int) -> bool:
        return teamid in self._NATIONAL_TEAM_IDS

    def refresh_player_teams(self, table=None):
        """Rebuild team indexes after an in-memory RrqT edit."""
        self._player_team.clear()
        self._player_jersey.clear()
        table = table or self._db.get_table("RrqT")
        if table:
            for r in table.records:
                pid = r.get("playerid", 0)
                tid = r.get("teamid", 0)
                num = r.get("jerseynumber", 0)
                if pid and tid:
                    self._player_team.setdefault(pid, []).append(tid)
                    if num and pid not in self._player_jersey:
                        self._player_jersey[pid] = num

    def get_team_name(self, teamid: int) -> str:
        """Get team name (Chinese preferred, English fallback, ID as last resort)."""
        return self._team_names_cn.get(teamid, self._team_names_en.get(teamid, str(teamid)))

    # ------------------------------------------------------------------
    # FST reference file loaders
    # ------------------------------------------------------------------

    def _load_playernames(self, path: Path):
        """Load player name database from FST's playernames.txt (UTF-16 with BOM).

        Format: tab-separated TSV with header: name, nameid, commentaryid
        Contains all ~41190 EA game name strings, keyed by nameid.
        """
        try:
            # Use 'utf-16' (not 'utf-16-le') to auto-strip the BOM
            with path.open("r", encoding="utf-16", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    nid_str = (row.get("nameid") or "").strip()
                    name_str = (row.get("name") or "").strip()
                    if nid_str.isdigit() and name_str:
                        nid = int(nid_str)
                        if nid > 0 and nid not in self._dc_names:
                            self._dc_names[nid] = name_str
        except Exception:
            pass

    def _load_nationalities_fst(self, path: Path):
        """Load Chinese nation names from FST's nationalities.txt.

        Format: ID=ChineseName per line (UTF-8).
        Supplements the English nations.csv with Chinese names.
        """
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        nid_str, name = line.split("=", 1)
                        if nid_str.strip().isdigit() and name.strip():
                            nid = int(nid_str.strip())
                            # Only set if not already in _nations (prefer existing)
                            if nid not in self._nations:
                                self._nations[nid] = name.strip()
        except Exception:
            pass

    def search(self, query: str, players_table: Table) -> list[int]:
        """Search players by name or playerid.

        Returns matching playerids.
        """
        results = set()
        q = query.lower().strip()

        for r in players_table.records:
            pid = r.get("playerid", 0)
            if q.isdigit() and pid == int(q):
                return [pid]
            name = self.get_name(r)
            if q in name.lower():
                results.add(pid)

        return sorted(results)
