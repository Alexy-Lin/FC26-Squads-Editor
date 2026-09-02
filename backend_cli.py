"""FC26 Save Editor command-line interface.

Examples:
  python backend_cli.py Squads... --search Messi
  python backend_cli.py Squads... --set 158023 overallrating=99 finishing=99 --save
  python backend_cli.py Squads... --set-team 158023 47 10 --save-as boosted.sav
"""

import argparse
import sys
from pathlib import Path

from core.exporter import export_to_excel
from core.mappings import NATIONS_CN, OPTION_MAPS, POSITION_NAMES
from core.meta_parser import MetaDatabase
from core.name_resolver import NameResolver
from core.sav_file import SavFile
from core.traits import decode_icon_traits, decode_specialities, decode_traits
from services.player_service import PlayerService
from services.roster_service import RosterService
from services.save_service import SafeSaveService


PROJECT_ROOT = Path(__file__).resolve().parent
META_PATH = PROJECT_ROOT / "data" / "fifa_ng_db-meta.xml"


def load_save(path: Path):
    if not path.is_file():
        raise ValueError(f"找不到存档：{path}")
    meta = MetaDatabase.from_file(META_PATH)
    sav = SavFile()
    sav.load(path, meta)
    return sav, meta


def print_summary(sav: SavFile):
    print(sav.summary())
    for short_name in ("CZUM", "lyxL", "RrqT"):
        table = sav.db.get_table(short_name) if sav.db else None
        if table:
            print(f"{short_name}: {table.long_name} | {len(table.fields)} fields | {len(table.records):,} records")


def print_player(sav: SavFile, player_id: int):
    resolver = NameResolver(sav.db)
    players = PlayerService(sav)
    table = players.table
    record = players.get_player(player_id)
    club, national = resolver.get_player_team(player_id)
    pos = POSITION_NAMES.get(record.get("preferredposition1"), record.get("preferredposition1"))
    nation_id = record.get("nationality", 0)
    print(f"\n{resolver.get_name(record)} (ID={player_id})")
    print(f"  OVR {record.get('overallrating')} | POT {record.get('potential')} | POS {pos}")
    print(f"  国籍 {NATIONS_CN.get(nation_id, resolver.get_nation_name(nation_id))} | 俱乐部 {club or '自由球员'} | 国家队 {national or '—'}")
    print(f"  身高 {record.get('height')}cm | 体重 {record.get('weight')}kg | 惯用脚 {OPTION_MAPS['preferredfoot'].get(record.get('preferredfoot'), record.get('preferredfoot'))}")
    print(f"  逆足 {record.get('weakfootabilitytypecode')}/5 | 花式 {record.get('skillmoves', 0) + 1}/5")
    print("\n  能力值：")
    for field in (
        "crossing", "finishing", "headingaccuracy", "shortpassing", "volleys",
        "dribbling", "curve", "freekickaccuracy", "longpassing", "ballcontrol",
        "acceleration", "sprintspeed", "agility", "reactions", "balance",
        "shotpower", "jumping", "stamina", "strength", "longshots",
        "aggression", "interceptions", "positioning", "vision", "penalties", "composure",
        "defensiveawareness", "standingtackle", "slidingtackle",
    ):
        fd = table.get_field_by_name(field)
        if fd:
            print(f"    {field:<22} {record.get(field)}")
    traits = decode_traits(record.get("trait1", 0), record.get("trait2", 0))
    icon_traits = decode_icon_traits(record.get("icontrait1", 0), record.get("icontrait2", 0))
    print(f"\n  特性：{', '.join(traits) if traits else '无'}")
    if icon_traits:
        print(f"  图标特性：{', '.join(icon_traits)}")
    specialties = decode_specialities(record)
    if specialties:
        print(f"  特技：{', '.join(specialties)}")


def print_search(sav: SavFile, query: str):
    players = PlayerService(sav)
    resolver = players.resolver
    for item in players.search(query, 100):
        position = POSITION_NAMES.get(item["position"], item["position"])
        print(f"{item['playerid']:>7}  {item['name']:<30}  OVR {item['overallrating']:>2}  {position!s:<4}  {item['club'] or '自由球员'}")


def apply_trait(sav, values):
    if len(values) != 4:
        raise ValueError("--set-trait 格式：player_id bank bit on|off")
    player_id, bank, bit = map(int, values[:3])
    enabled = values[3].strip().lower() in ("1", "true", "on", "yes", "启用")
    change = PlayerService(sav).set_trait(player_id, bank, bit, enabled)
    return [change] if change else []


def save_changes(sav, meta, changes, output_path=None):
    result = SafeSaveService(meta).save(sav, changes, output_path=output_path)
    print(f"已保存并验证：{result.path}")


def build_parser():
    parser = argparse.ArgumentParser(description="FC26 Squad 存档编辑器")
    parser.add_argument("save_file", type=Path, help="Squads 存档路径")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--search", metavar="TEXT", help="按球员姓名或 ID 搜索")
    group.add_argument("--player", type=int, metavar="ID", help="显示球员资料")
    group.add_argument("--set", nargs="+", metavar="VALUE", help="修改球员：ID field=value ...")
    group.add_argument("--set-team", nargs="+", metavar="VALUE", help="修改现有球队关系：球员ID 球队ID [球衣号]")
    group.add_argument("--set-trait", nargs=4, metavar=("ID", "BANK", "BIT", "STATE"), help="按位修改特性")
    group.add_argument("--export", type=Path, metavar="XLSX", help="导出全部数据库表")
    group.add_argument("--export-players", type=Path, metavar="XLSX", help="仅导出 CZUM 球员表")
    parser.add_argument("--save", action="store_true", help="修改后生成新的 Squads 时间戳文件")
    parser.add_argument("--save-as", type=Path, metavar="PATH", help="修改后保存到指定新文件")
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        if args.save and args.save_as:
            raise ValueError("--save 与 --save-as 只能选一个")
        sav, meta = load_save(args.save_file)
        if args.search is not None:
            print_search(sav, args.search)
            return 0
        if args.player is not None:
            print_player(sav, args.player)
            return 0
        if args.export or args.export_players:
            output = args.export or args.export_players
            export_to_excel(sav, output, tables_filter={"CZUM"} if args.export_players else None)
            print(f"已导出：{output}")
            return 0

        changes = []
        if args.set:
            if len(args.set) < 2:
                raise ValueError("--set 格式：player_id field=value ...")
            player_id = int(args.set[0])
            changes = PlayerService(sav).update_fields(player_id, PlayerService.parse_updates(args.set[1:]))
        elif args.set_team:
            if len(args.set_team) not in (2, 3):
                raise ValueError("--set-team 格式：player_id team_id [jersey]")
            player_id, team_id = map(int, args.set_team[:2])
            roster = RosterService(sav)
            link = roster.current_team_link(player_id, roster.resolver.is_national_team(team_id))
            if link is None:
                raise ValueError("未找到与目标类型匹配的现有关系记录")
            changes = list(roster.replace_team(player_id, team_id, roster.resolver.is_national_team(team_id)))
            if len(args.set_team) == 3:
                jersey = int(args.set_team[2])
                fd = roster.table.get_field_by_name("jerseynumber")
                if jersey < fd.range_low or jersey > fd.range_high:
                    raise ValueError(f"球衣号码必须在 {fd.range_low}..{fd.range_high} 之间")
                roster._validate_jersey(team_id, player_id, jersey)
                old = link.get("jerseynumber")
                if jersey != old:
                    link["jerseynumber"] = jersey
                    from services.changes import FieldChange
                    changes.append(FieldChange("RrqT", "artificialkey", link.get("artificialkey"), "jerseynumber", old, jersey))
        elif args.set_trait:
            changes = apply_trait(sav, args.set_trait)
        else:
            print_summary(sav)
            return 0

        for change in changes:
            print(f"{change.table}.{change.field}: {change.old_value} -> {change.new_value}")
        if args.save or args.save_as:
            save_changes(sav, meta, changes, args.save_as)
        else:
            print("预览模式：未写入文件。使用 --save 或 --save-as 保存。")
        return 0
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
