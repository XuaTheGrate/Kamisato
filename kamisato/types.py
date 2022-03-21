from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Protocol, TypedDict, TypeVar, TYPE_CHECKING, _TypedDict

if TYPE_CHECKING:
    from typing_extensions import TypeGuard
else:
    reveal_type = lambda i: i


class _ConfigDiscord(TypedDict):
    token: str
    extensions: list[str]

class _ConfigPostgres(TypedDict):
    host: str
    password: str
    port: int
    db: str

class _ConfigOptional(TypedDict, total=False):
    ssh_tunnel: list[str]

class Config(_ConfigOptional):
    discord: _ConfigDiscord
    postgresql: _ConfigPostgres


class Rarity(int, Enum):
    grey = 1
    green = 2
    blue = 3
    purple = 4
    gold = 5

    def __str__(self) -> str: return str(self.value)


ArtifactSet = Literal[
    "OceanHuedClam"
]

ArtifactSlot = Literal[
    "flower",
    "plume",
    "sands",
    "goblet",
    "circlet"
]

Character = Literal[
    "SangonomiyaKokomi"
]

main_stats = [
    "geo_dmg_",
    "pyro_dmg_",
    "anemo_dmg_",
    "hydro_dmg_",
    "electro_dmg_",
    "cryo_dmg_",
    "physical_dmg_",
    "heal_",
    "atk_",
    "hp_",
    "def_",
    "eleMas",
    "enerRech_",
    "critRate_",
    "critDMG_"
]

sub_stats = [
    "hp",
    "hp_",
    "atk",
    "atk_",
    "def",
    "def_",
    "enerRech_",
    "eleMas",
    "critRate_",
    "critDMG_"
]

stats = set(main_stats + sub_stats)

stat_transform: dict[str, str] = {
    "hp": "HP: {0:,.0f}",
    "hp_": "HP: {0:.1f}%",
    "atk": "ATK: {0:,.0f}",
    "atk_": "ATK: {0:.1f}%",
    "def": "DEF: {0:,.0f}",
    "def_": "DEF: {0:.1f}%",
    "enerRech_": "Energy Recharge: {0:.1f}%",
    "eleMas": "Elemental Mastery: {0:.0f}",
    "critRate_": "Crit Rate: {0:.1f}%",
    "critDMG_": "Crit DMG: {0:.1f}%",
    "heal_": "Healing Bonus: {0:.1f}%",

    "physical_dmg_": "Physical DMG Bonus: {0:.1%}",
    "anemo_dmg_": "Anemo DMG Bonus: {0:.1%}",
    "geo_dmg_": "Geo DMG Bonus: {0:.1%}",
    "electro_dmg_": "Electro DMG Bonus: {0:.1%}",
    "hydro_dmg_": "Hydro DMG Bonus: {0:.1%}",
    "pyro_dmg_": "Pyro DMG Bonus: {0:.1%}",
    "cryo_dmg_": "Cryo DMG Bonus: {0:.1%}"
}


class _ScanData_Artifacts_Artifact_Substat(TypedDict):
    key: str
    value: float

class _ScanData_Artifacts_Artifact(TypedDict):
    SubStatsCount: int
    level: int
    location: Character
    lock: bool
    mainStatKey: str
    rarity: Literal[1, 2, 3, 4, 5]
    setKey: ArtifactSet
    slotKey: ArtifactSlot
    substats: list[_ScanData_Artifacts_Artifact_Substat]

class ScanData(_TypedDict, total=False):
    artifacts: list[_ScanData_Artifacts_Artifact]


_ArtifactSubstats_Rarity_Def = TypedDict("_ArtifactSUbstats_Rarity_Def", {"def": list[float]})

class _ArtifactSubstats_Rarity(_ArtifactSubstats_Rarity_Def):
    atk: list[float]
    atk_: list[float]
    critDMG_: list[float]
    critRate_: list[float]
    def_: list[float]
    eleMas: list[float]
    enerRech_: list[float]
    hp: list[float]
    hp_: list[float]

ArtifactSubstats = TypedDict("ArtifactSubstats", {
    "1": _ArtifactSubstats_Rarity,
    "2": _ArtifactSubstats_Rarity,
    "3": _ArtifactSubstats_Rarity,
    "4": _ArtifactSubstats_Rarity,
    "5": _ArtifactSubstats_Rarity
})


def conforms(obj: dict[str, Any], typ: Any) -> tuple[bool, set[str]] | None:
    required = typ.__required_keys__ - obj.keys()
    if required:
        return True, required
    
    extra = obj.keys() - set([*typ.__required_keys__, *typ.__optional_keys__])
    if extra:
        return False, extra


if __name__ == '__main__':
    print(Rarity.gold)
    print(Rarity(5))
    print(Rarity["gold"])
