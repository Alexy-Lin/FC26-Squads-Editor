"""Export the FIFA19 peak attributes used by the "restore active veterans" feature.

Two FIFA19 sources are merged, keeping the **higher** value per attribute:

1. ``players.db`` (``source='fifa19'``) - the values used by the original
   hand-made restore.  It has no goalkeeper / defensive-mental columns.
2. The official sofifa FIFA19 player export (``players_19.csv``) - has all
   attributes, including the five goalkeeper attributes, and is the source for
   ``aggression`` / ``defensiveawareness`` / ``gkdiving`` / ``gkhandling`` /
   ``gkkicking`` / ``gkpositioning`` / ``gkreflexes``.

Merging matters because the two disagree: for Memphis Depay (202556) the
database says acceleration 82 while the official export says 89, so a
database-only table left him below his real peak.

Writes ``data/fifa19_peak.csv`` (41 attribute columns), which
``PeakRestoreService`` consumes at runtime.

Usage:
    python tools/export_fifa19_peak.py
    python tools/export_fifa19_peak.py --db PATH --official PATH --out data/fifa19_peak.csv
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_CANDIDATES = (
    Path(r"C:\Users\Lin\OneDrive\code\FC26\fc26-editor\data\players.db"),
    APP_ROOT / "data" / "players.db",
)
DEFAULT_OFFICIAL_CANDIDATES = (
    Path(r"C:\Users\Lin\OneDrive\code\FIFA19\.codex\legend_roster_work\historical_data\players_19.csv"),
    APP_ROOT / "data" / "players_19.csv",
)

#: Attribute columns of the exported table.
FIELDS = [
    "overallrating", "potential", "finishing", "dribbling", "ballcontrol", "sprintspeed",
    "acceleration", "shotpower", "shortpassing", "longpassing", "vision", "composure",
    "agility", "balance", "jumping", "strength", "headingaccuracy", "standingtackle",
    "slidingtackle", "interceptions", "curve", "freekickaccuracy", "penalties", "volleys",
    "positioning", "crossing", "longshots", "stamina", "reactions", "aggression",
    "defensiveawareness", "gkdiving", "gkhandling", "gkkicking", "gkpositioning", "gkreflexes",
    "weakfootabilitytypecode", "skillmoves", "skillmoveslikelihood", "preferredfoot",
    "internationalrep",
]

#: Extra columns kept for identity checks and reporting.
EXTRA = ["nationality", "height", "preferredposition1", "name"]

#: official sofifa CSV column -> our field name
OFFICIAL_MAP = {
    "overall": "overallrating",
    "potential": "potential",
    "attacking_crossing": "crossing",
    "attacking_finishing": "finishing",
    "attacking_heading_accuracy": "headingaccuracy",
    "attacking_short_passing": "shortpassing",
    "attacking_volleys": "volleys",
    "skill_dribbling": "dribbling",
    "skill_curve": "curve",
    "skill_fk_accuracy": "freekickaccuracy",
    "skill_long_passing": "longpassing",
    "skill_ball_control": "ballcontrol",
    "movement_acceleration": "acceleration",
    "movement_sprint_speed": "sprintspeed",
    "movement_agility": "agility",
    "movement_reactions": "reactions",
    "movement_balance": "balance",
    "power_shot_power": "shotpower",
    "power_jumping": "jumping",
    "power_stamina": "stamina",
    "power_strength": "strength",
    "power_long_shots": "longshots",
    "mentality_aggression": "aggression",
    "mentality_interceptions": "interceptions",
    "mentality_positioning": "positioning",
    "mentality_vision": "vision",
    "mentality_penalties": "penalties",
    "mentality_composure": "composure",
    "defending_marking": "defensiveawareness",
    "defending_standing_tackle": "standingtackle",
    "defending_sliding_tackle": "slidingtackle",
    "gk_diving": "gkdiving",
    "gk_handling": "gkhandling",
    "gk_kicking": "gkkicking",
    "gk_positioning": "gkpositioning",
    "gk_reflexes": "gkreflexes",
    "weak_foot": "weakfootabilitytypecode",
    "international_reputation": "internationalrep",
}

#: Columns that must not be merged with ``max`` (not "higher is better").
NO_MAX = {"preferredfoot", "skillmoveslikelihood"}

#: Columns players.db does not have; they can only come from the official CSV.
OFFICIAL_ONLY = {
    "aggression", "defensiveawareness", "gkdiving", "gkhandling", "gkkicking",
    "gkpositioning", "gkreflexes",
}


def _int(value):
    try:
        text = str(value).strip()
        return int(float(text)) if text else 0
    except (TypeError, ValueError):
        return 0


def load_official(path: Path, player_ids=None):
    """Return {playerid: {field: value}} from the official sofifa export."""
    official = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            raw_id = (row.get("sofifa_id") or "").strip()
            if not raw_id.isdigit():
                continue
            player_id = int(raw_id)
            if player_ids is not None and player_id not in player_ids:
                continue
            values = {}
            for column, field in OFFICIAL_MAP.items():
                raw = (row.get(column) or "").strip()
                if raw:
                    values[field] = _int(raw)
            moves = (row.get("skill_moves") or "").strip()
            if moves.isdigit():
                values["skillmoves"] = max(0, min(4, int(moves) - 1))
            foot = (row.get("preferred_foot") or "").strip().lower()
            if foot in ("right", "left"):
                values["preferredfoot"] = 1 if foot == "right" else 2
            if values:
                official[player_id] = values
    return official


def main(argv=None):
    parser = argparse.ArgumentParser(description="导出 FIFA19 巅峰属性表（合并两套数据）")
    parser.add_argument("--db", default=None, help="players.db 路径")
    parser.add_argument("--official", default=None, help="官方 FIFA19 CSV（players_19.csv）")
    parser.add_argument("--out", default=str(APP_ROOT / "data" / "fifa19_peak.csv"))
    parser.add_argument("--source", default="fifa19", help="players 表的 source 值")
    parser.add_argument("--min-ovr", type=int, default=0, help="只导出巅峰 OVR 不低于该值的球员")
    parser.add_argument("--no-official", action="store_true", help="只用 players.db，不合并官方 CSV")
    args = parser.parse_args(argv)

    database = Path(args.db) if args.db else next(
        (candidate for candidate in DEFAULT_DB_CANDIDATES if candidate.is_file()), None
    )
    if not database or not Path(database).is_file():
        print("找不到 players.db，请用 --db 指定路径", file=sys.stderr)
        return 1

    columns = FIELDS + EXTRA
    db_fields = [f for f in FIELDS if f not in OFFICIAL_ONLY]
    with sqlite3.connect(str(database)) as connection:
        present = {row[1] for row in connection.execute("pragma table_info(players)")}
        selected = [f for f in db_fields if f in present]
        extra_present = [f for f in EXTRA if f in present]
        query = (f"SELECT playerid, {','.join(selected + extra_present)} FROM players "
                 f"WHERE source=? AND overallrating>=? ORDER BY overallrating DESC")
        rows = list(connection.execute(query, (args.source, args.min_ovr)))

    official_path = None if args.no_official else (
        Path(args.official) if args.official else next(
            (candidate for candidate in DEFAULT_OFFICIAL_CANDIDATES if candidate.is_file()), None
        )
    )
    official = {}
    if official_path and Path(official_path).is_file():
        official = load_official(Path(official_path))
        print(f"官方 FIFA19 CSV: {official_path}（{len(official)} 名球员）")
    elif not args.no_official:
        print("提示：没找到官方 FIFA19 CSV，本次只使用 players.db 的值", file=sys.stderr)

    merged = []
    raised = 0
    for row in rows:
        record = dict(zip(selected + extra_present, row[1:]))
        player_id = row[0]
        values = {field: _int(record.get(field)) for field in FIELDS}
        upgraded = False
        for field, value in official.get(player_id, {}).items():
            if not value:
                continue
            if field in NO_MAX:
                if not values.get(field):
                    values[field] = value
                continue
            if value > values.get(field, 0):
                values[field] = value
                upgraded = True
        if upgraded:
            raised += 1
        merged.append([player_id] + [values[f] for f in FIELDS] + [
            record.get("nationality", "") or "",
            record.get("height", "") if "height" in extra_present else "",
            record.get("preferredposition1", "") if "preferredposition1" in extra_present else "",
            (record.get("name", "") or "").strip(),
        ])
    merged.sort(key=lambda item: -item[1])

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["playerid"] + columns)
        writer.writerows(merged)

    print(f"已导出 {len(merged)} 条记录（其中 {raised} 条被官方 CSV 抬高） -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
