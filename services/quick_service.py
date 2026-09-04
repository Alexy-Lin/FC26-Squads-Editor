from core.sav_file import SavFile
from .changes import ChangeSet, FieldChange


class QuickFeatureService:
    """Implement small, reversible bulk edits for the currently loaded save."""

    TABLE = "CZUM"
    KEY = "playerid"
    BIRTHDATE_FIELD = "birthdate"

    # FC stores birthdate as days since 1582-10-14.  2007-07-01 makes a
    # player 18 during the 2025/26 season, which is the season used by FC26.
    BIRTHDATE_AGE18 = 155123

    def __init__(self, sav: SavFile):
        if not sav.db:
            raise ValueError("存档尚未加载")
        table = sav.db.get_table(self.TABLE)
        if not table:
            raise ValueError("存档中没有球员表 CZUM")
        if not table.get_field_by_name(self.BIRTHDATE_FIELD) and not table.get_field(self.BIRTHDATE_FIELD):
            raise ValueError("球员表没有 birthdate 字段")
        self.table = table

    def set_all_players_age18(self) -> ChangeSet:
        """Set every valid player's birthdate to the FC26 age-18 value."""
        changes = ChangeSet()
        for record in self.table.records:
            player_id = record.get(self.KEY, 0)
            if not isinstance(player_id, int) or player_id <= 0:
                continue
            old_value = record.get(self.BIRTHDATE_FIELD, 0)
            if old_value == self.BIRTHDATE_AGE18:
                continue
            record[self.BIRTHDATE_FIELD] = self.BIRTHDATE_AGE18
            changes.add(FieldChange(
                self.TABLE,
                self.KEY,
                player_id,
                self.BIRTHDATE_FIELD,
                old_value,
                self.BIRTHDATE_AGE18,
            ))
        return changes
