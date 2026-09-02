"""FC26 Trait definitions — decoded from bitmask fields.

In FC26, CZUM has:
  - juxV  = trait1  (30-bit mask, traits 0-29)
  - inAr  = trait2  (17-bit mask, traits 30-46)

The exact trait-to-bit mappings need verification from the game.
Below is a best-effort mapping based on the FST editor's trait icons
(36 regular icons + 36 gold icons = up to 72 possible entries)
and adapted from known FIFA19 mappings where available.
"""

from typing import List, Tuple

# Bit position -> (field, short_name)
# trait1 (juxV) — bits 0-29
FC26_TRAIT1: List[Tuple[int, str]] = [
    # 0-9: Common traits (likely same/similar to FIFA19)
    (0,  "Power Header"),
    (1,  "Dives Into Tackles"),
    (2,  "Finesse Shot"),
    (3,  "GK Flat Kick"),
    (4,  "Long Passer"),
    (5,  "Long Shot Taker"),
    (6,  "Playmaker"),
    (7,  "Outside Foot Shot"),
    (8,  "Swerve Pass"),
    (9,  "Giant Throw-In"),
    # 10-19
    (10, "Flair"),
    (11, "Chip Shot"),
    (12, "Acrobatic Clearance"),
    (13, "Second Wind"),
    (14, "Injury Prone"),
    (15, "Leadership"),
    (16, "Team Player"),
    (17, "Club Legend"),
    (18, "One Club Player"),
    (19, "Injury Free"),
    # 20-29
    (20, "Speed Dribbler"),
    (21, "Technical Dribbler"),
    (22, "Set Piece Specialist"),
    (23, "Solid Player"),
    (24, "Leadership (Dupe)"),
    (25, "Tackling"),
    (26, "Early Crosser"),
    (27, "Holds Up Play"),
    (28, "Takes Powerful Driven Free Kick"),
    (29, "Rushes Out of Goal"),
]

# trait2 (inAr) — bits 0-16, mapped as bits 30-46 total
FC26_TRAIT2: List[Tuple[int, str]] = [
    (30, "Bicycle Kicks"),
    (31, "Backs Into Players"),
    (32, "Chip Shot (Dupe)"),
    (33, "Late Crosser"),
    (34, "Saves With Feet"),
    (35, "GK Long Throw"),
    (36, "Target Forward"),
    (37, "Cautious With Tackles"),
    (38, "Argues With Officials"),
    (39, "Selfish"),
    (40, "Stutter Penalty"),
    (41, "Hesitant To Foul"),
    (42, "Diver"),
    (43, "GK Flat Kick (Dupe)"),
    (44, "Fancy Free Kicks"),
    (45, "Lob Pass"),
    (46, "Long Throw"),
]

# Build combined mapping
_ALL_TRAITS = FC26_TRAIT1 + FC26_TRAIT2


def decode_traits(trait1_val: int, trait2_val: int) -> List[str]:
    """Decode FC26 trait1/trait2 bitmasks into a list of trait name strings.

    In FC26:
      - trait1 = juxV  (30-bit field)
      - trait2 = inAr  (17-bit field)

    Bits 0-29 map to trait1, bits 30-46 map to trait2.
    """
    combined = (trait2_val << 30) | trait1_val
    result = []
    for bit, name in _ALL_TRAITS:
        if combined & (1 << bit):
            result.append(name)
    return result


def format_traits(traits: List[str], indent: int = 0) -> str:
    """Format list of traits for CLI display."""
    prefix = "  " * indent
    return "\n".join(f"{prefix}▸ {t}" for t in sorted(traits))


# ── Specialities (computed from attribute thresholds) ──

def decode_specialities(record: dict) -> List[str]:
    """Compute FC26 specialities from attribute thresholds.

    Note: FC26 thresholds may differ from FIFA19.  These are best-effort.
    """
    s = []
    a = lambda name: record.get(name, 0) or 0

    # Goalkeeping
    gk_avg = (a("gkdiving") + a("gkhandling") + a("gkkicking")
              + a("gkpositioning") + a("gkreflexes")) / 5
    if gk_avg >= 84:
        s.append("GK Warrior")
    if a("gkhandling") >= 80:
        s.append("GK Handling")

    # Outfield
    if a("dribbling") >= 82 and a("agility") >= 78:
        s.append("Dribbler")
    if a("ballcontrol") >= 80 and a("dribbling") >= 76:
        s.append("Technical Dribbler")
    if a("shotpower") >= 85 and a("longshots") >= 80:
        s.append("Power Shots")
    if a("finishing") >= 85 and a("volleys") >= 75:
        s.append("Finisher")
    if a("acceleration") >= 82 and a("sprintspeed") >= 82:
        s.append("Speedster")
    if a("agility") >= 80 and a("balance") >= 70:
        s.append("Acrobat")
    if a("crossing") >= 80 and a("curve") >= 75 and a("shortpassing") >= 75:
        s.append("Crosser")
    if a("shortpassing") >= 83 and a("longpassing") >= 78 and a("vision") >= 75:
        s.append("Playmaker")
    if a("standingtackle") >= 80 and a("slidingtackle") >= 72:
        s.append("Tackler")
    if a("interceptions") >= 80 and a("defensiveawareness") >= 80 and a("standingtackle") >= 78:
        s.append("Defensive Wall")
    if a("penalties") >= 80:
        s.append("Penalty Taker")
    if a("composure") >= 80:
        s.append("Composed")
    if a("freekickaccuracy") >= 80 and a("curve") >= 75:
        s.append("Free Kick Specialist")
    if a("stamina") >= 85:
        s.append("Workhorse")
    if a("strength") >= 80:
        s.append("Strong")
    if a("jumping") >= 80 and a("headingaccuracy") >= 78:
        s.append("Aerial Threat")

    return s


def format_specialities(specs: List[str], indent: int = 0) -> str:
    """Format specialities for CLI."""
    prefix = "  " * indent
    return "\n".join(f"{prefix}▸ {s}" for s in sorted(specs))


# ── Icon traits (separate bitmask in FC26) ──

def decode_icon_traits(icontrait1_val: int, icontrait2_val: int) -> List[str]:
    """Decode FC26 icontrait1/icontrait2 (icon-specific traits).

    icontrait1 = OjQY (30-bit)
    icontrait2 = PqtG (17-bit)

    Mappings need verification from game data.
    """
    combined = (icontrait2_val << 30) | icontrait1_val
    icons = []
    for bit in range(47):
        if combined & (1 << bit):
            icons.append(f"IconTrait_{bit}")
    return icons
