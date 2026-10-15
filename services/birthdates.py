"""Shared birthdate knowledge for the FC26 editor.

FC stores ``birthdate`` as *days since 1582-10-14* (Gregorian epoch).

Findings that this module encodes (see docs/save-format.md):

* The game **skips players whose birthdate is out of range**.  In FC26's shipped
  squad data the oldest player is 125812 (1927-04-01, Ferenc Puskás), so anything
  below that (for example the 120000 / 130000 placeholders that ship inside
  ``legend_database.db`` for Kempes and Rivellino) makes the player invisible in
  squad selection screens.
* EA's own ICON/Hero rows in the older snapshots use "2007 + real month/day"
  values, which is why imported veterans looked 18 years old.
* 155123 = 2007-07-01 (18 years old during the 2025/26 season),
  155489 = 2008-07-01 (17 years old).
"""

from __future__ import annotations

import datetime

EPOCH = datetime.date(1582, 10, 14)

#: Birthdates below this value are rejected by the game (invisible players).
BIRTHDATE_MIN = 125812

#: Birthdate used by the "everyone is 18" quick feature (2007-07-01).
BIRTHDATE_AGE18 = 155123

#: Birthdate used by the "everyone is 17" option (2008-07-01).
BIRTHDATE_AGE17 = 155489

AGE_BIRTHDATES = {
    17: BIRTHDATE_AGE17,
    18: BIRTHDATE_AGE18,
}

#: Real birthdays for every legend the editor can import.  The source database
#: carries placeholders (or "2007 + month/day" values) for these players, and the
#: wrong value is exactly what hides them inside the game.
REAL_BIRTHDAYS = {
    5679: 143832,    # Nwankwo Kanu        1976-08-01
    8348: 143548,    # Míchel Salgado      1975-10-22
    10959: 145021,   # Pablo Aimar         1979-11-03
    20775: 146444,   # Quaresma            1983-09-26
    23174: 144524,   # Juan Román Riquelme 1978-06-24
    39386: 145954,   # D. Beasley          1982-05-24
    50752: 145365,   # Ledley King         1980-10-12
    51412: 145054,   # Tim Cahill          1979-12-06
    155897: 146243,  # Clint Dempsey       1983-03-09
    156353: 141053,  # Luis Hernández      1968-12-22
    168880: 144406,  # Mohammed Noor       1978-02-26
    168886: 142503,  # Sami Al Jaber       1972-12-11
    170733: 147783,  # Gervinho            1987-05-27
    188428: 148001,  # S. Doumbia          1987-12-31
    191694: 140254,  # Jorge Campos        1966-10-15
    204550: 148871,  # V. Ibarbo           1990-05-19
    214267: 138109,  # Gary Lineker        1960-11-30
    242625: 144006,  # Hidetoshi Nakata    1977-01-22
    243030: 144358,  # Gennaro Gattuso     1978-01-09
    266694: 140562,  # Saeed Al Owairan    1967-08-19
    266695: 141395,  # Tomas Brolin        1969-11-29
    82092: 135779,   # Mario Kempes        1954-07-15
    191190: 132662,  # Roberto Rivellino   1946-01-01
}


def to_date(value: int) -> datetime.date:
    """Convert a stored birthdate into a calendar date."""
    return EPOCH + datetime.timedelta(days=int(value))


def describe(value: int) -> str:
    """Human readable ``1946-01-01`` (or ``?`` when the value is unusable)."""
    try:
        return to_date(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return "?"


def is_valid(value: int) -> bool:
    """True when the game accepts the birthdate (see :data:`BIRTHDATE_MIN`)."""
    try:
        return int(value) >= BIRTHDATE_MIN
    except (TypeError, ValueError):
        return False
