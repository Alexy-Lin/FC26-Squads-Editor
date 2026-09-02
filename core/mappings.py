"""FC26 display mappings and the fields exposed by the web editor."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = PROJECT_ROOT / "config"


def _load_kv(path: Path) -> dict[int, str]:
    result: dict[int, str] = {}
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip().lstrip("-").isdigit() and value.strip():
                    result[int(key.strip())] = value.strip()
    except OSError:
        pass
    return result


POSITION_NAMES = _load_kv(CONFIG_ROOT / "positions.txt")
ROLE_NAMES = _load_kv(CONFIG_ROOT / "roles.txt")
INT_REP_LABELS = _load_kv(CONFIG_ROOT / "international.txt")
NATIONS_CN = _load_kv(CONFIG_ROOT / "nationalities.txt")

FOOT_CN = {1: "右脚", 2: "左脚"}
WEAK_FOOT_CN = {value: f"{value}/5" for value in range(1, 6)}
# FC26 stores skill moves as 0..4, where 0 is the one-star value.
SKILL_MOVES_CN = {value: f"{max(1, value)}/5" for value in range(5)}


def _labels(start: int, end: int, suffix: str = "") -> dict[int, str]:
    return {value: f"{value}{suffix}" for value in range(start, end + 1)}


ATTRIBUTE_CATEGORIES = [
    ("球员信息", [
        ("playerid", "球员 ID"),
        ("firstnameid", "名字 ID"),
        ("lastnameid", "姓氏 ID"),
        ("commonnameid", "通用名 ID"),
        ("playerjerseynameid", "球衣名 ID"),
    ]),
    ("评分", [
        ("overallrating", "总评"),
        ("potential", "潜力"),
        ("modifier", "状态加成"),
        ("internationalrep", "国际声望"),
    ]),
    ("位置 / 角色", [
        ("preferredposition1", "主位置"),
        ("preferredposition2", "次位置 1"),
        ("preferredposition3", "次位置 2"),
        ("preferredposition4", "次位置 3"),
        ("preferredposition5", "次位置 4"),
        ("preferredposition6", "次位置 5"),
        ("preferredposition7", "次位置 6"),
        ("preferredfoot", "惯用脚"),
        ("skillmoves", "花式技巧"),
        ("weakfootabilitytypecode", "逆足能力"),
        ("skillmoveslikelihood", "花式倾向"),
        ("role1", "角色 1"),
        ("role2", "角色 2"),
        ("role3", "角色 3"),
        ("role4", "角色 4"),
        ("role5", "角色 5"),
    ]),
    ("进攻", [
        ("crossing", "传中"),
        ("finishing", "射术"),
        ("headingaccuracy", "头球精度"),
        ("shortpassing", "短传"),
        ("volleys", "凌空射门"),
    ]),
    ("技巧", [
        ("dribbling", "盘带"),
        ("curve", "弧线"),
        ("freekickaccuracy", "任意球精度"),
        ("longpassing", "长传"),
        ("ballcontrol", "控球"),
    ]),
    ("移动", [
        ("acceleration", "加速"),
        ("sprintspeed", "速度"),
        ("agility", "敏捷"),
        ("reactions", "反应"),
        ("balance", "平衡"),
    ]),
    ("力量", [
        ("shotpower", "射门力量"),
        ("jumping", "弹跳"),
        ("stamina", "体力"),
        ("strength", "强壮"),
        ("longshots", "远射"),
    ]),
    ("精神", [
        ("aggression", "侵略性"),
        ("interceptions", "拦截"),
        ("positioning", "进攻站位"),
        ("vision", "视野"),
        ("penalties", "点球"),
        ("composure", "沉着"),
    ]),
    ("防守", [
        ("defensiveawareness", "防守意识"),
        ("standingtackle", "抢断"),
        ("slidingtackle", "铲球"),
    ]),
    ("门将", [
        ("gkdiving", "扑救"),
        ("gkhandling", "手控球"),
        ("gkkicking", "开球"),
        ("gkpositioning", "门将站位"),
        ("gkreflexes", "反应"),
    ]),
    ("身体数据", [
        ("height", "身高 (cm)"),
        ("weight", "体重 (kg)"),
        ("birthdate", "出生日期"),
        ("nationality", "国籍"),
        ("bodytypecode", "体型"),
    ]),
]

FIELD_LABELS_CN = {
    field: label
    for _category, fields in ATTRIBUTE_CATEGORIES
    for field, label in fields
}

OPTION_MAPS = {
    "preferredposition1": POSITION_NAMES,
    "preferredposition2": {-1: "—", **POSITION_NAMES},
    "preferredposition3": {-1: "—", **POSITION_NAMES},
    "preferredposition4": {-1: "—", **POSITION_NAMES},
    "preferredposition5": {-1: "—", **POSITION_NAMES},
    "preferredposition6": {-1: "—", **POSITION_NAMES},
    "preferredposition7": {-1: "—", **POSITION_NAMES},
    "preferredfoot": FOOT_CN,
    "weakfootabilitytypecode": WEAK_FOOT_CN,
    "skillmoves": SKILL_MOVES_CN,
    "skillmoveslikelihood": SKILL_MOVES_CN,
    "role1": ROLE_NAMES,
    "role2": ROLE_NAMES,
    "role3": ROLE_NAMES,
    "role4": ROLE_NAMES,
    "role5": ROLE_NAMES,
    "internationalrep": INT_REP_LABELS,
}


def get_field_label(field_name: str) -> str:
    return FIELD_LABELS_CN.get(field_name, field_name)
