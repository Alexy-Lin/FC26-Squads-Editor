"""Small compatibility layer for nation lookups used by optional clients."""

from .mappings import NATIONS_CN


def get_nationality_name(nation_id: int) -> str:
    return NATIONS_CN.get(nation_id, str(nation_id))


def get_nation_dict() -> dict[int, str]:
    return dict(NATIONS_CN)
