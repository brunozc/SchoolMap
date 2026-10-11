"""RIO (Register Instellingen en Opleidingen): confirm school buildings and complete registered private schools.

RIO is DUO's register of physical school buildings (onderwijslocaties) and the school codes that use them. It is
used to confirm or flag addresses, never to change one. An address counts as a RIO building of a school when RIO
registers the same address, or a building of that school within a short distance of it (the same complex with another
entrance number, e.g. a corner building).
"""
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import DefaultDict, Dict, List, Optional, Tuple

import pandas as pd
import requests

from school_register.globals import (KIND_DUO, KIND_NIET_IN_DUO, NOTE_DEPENDANCE, NOTE_NEVENLOCATIE,
                                     NOTE_NEVENLOCATIE_EIGEN_BESTUUR, NOTE_NIET_IN_DUO, NOTE_RIO_BUILDING_OF,
                                     NOTE_RIO_NO_BUILDING, NOTE_RIO_NOT_CONFIRMED, NOTE_RIO_OTHER_BUILDING,
                                     NOTE_RIO_UNLISTED, RIO_FILES, RIO_PACKAGE_URL, GlobalSettings)
from school_register.matching import SchoolRecord
from school_register.normalize import Address, clean, normalize_postcode, parse_house_number
from school_register.sources import download_file

# notes that say a sub-location is not separately known; RIO confirmation makes them obsolete
_SUB_LOCATION_NOTES = tuple(
    note.split("{")[0] for note in (NOTE_NEVENLOCATIE, NOTE_NEVENLOCATIE_EIGEN_BESTUUR, NOTE_DEPENDANCE))


@dataclass(frozen=True)
class RioBuilding:
    """A building in which a school code gives lessons, according to RIO.

    Attributes:
        code: vestigingscode using the building.
        address: address of the building.
        lat: latitude [deg], None if RIO has none.
        lon: longitude [deg], None if RIO has none.
    """
    code: str
    address: Address
    lat: Optional[float]
    lon: Optional[float]


@dataclass(frozen=True)
class RioVestiging:
    """An active school code in RIO with its bevoegd gezag.

    Attributes:
        code: vestigingscode.
        name: full official name.
        bestuur_nummer: bevoegd gezag number, empty if unknown.
        bestuur_naam: bevoegd gezag name, empty if unknown.
    """
    code: str
    name: str
    bestuur_nummer: str
    bestuur_naam: str


class RioRegister:
    """Lookups on the RIO buildings and school codes."""

    def __init__(self, buildings: List[RioBuilding], vestigingen: Dict[str, RioVestiging]) -> None:
        """Index the buildings by code and by postcode.

        Args:
            buildings: active building usages.
            vestigingen: active school codes.
        """
        self.__by_code: DefaultDict[str, List[RioBuilding]] = defaultdict(list)
        self.__by_postcode: DefaultDict[str, List[RioBuilding]] = defaultdict(list)
        for building in buildings:
            self.__by_code[building.code].append(building)
            self.__by_postcode[building.address.postcode].append(building)
        self.__vestigingen = vestigingen

    def buildings_of(self, code: str) -> List[RioBuilding]:
        """Buildings used by a school code.

        Args:
            code: vestigingscode.

        Returns:
            The buildings, empty if RIO registers none.
        """
        return list(self.__by_code.get(code, []))

    def building_at(self, code: str, address: Address) -> Optional[RioBuilding]:
        """The building of a school code at an address, if RIO registers one.

        Args:
            code: vestigingscode.
            address: address to look for.

        Returns:
            The building, or None.
        """
        return next((b for b in self.__by_code.get(code, []) if b.address.same_place(address)), None)

    def codes_at(self, address: Address) -> List[str]:
        """School codes that RIO registers in the building at an address.

        Args:
            address: address to look for.

        Returns:
            The codes, sorted and without duplicates.
        """
        return sorted({b.code for b in self.__by_postcode.get(address.postcode, []) if b.address.same_place(address)})

    def nearest(self, code: str, point: Tuple[float, float]) -> Optional[Tuple[RioBuilding, float]]:
        """The building of a school code closest to a point.

        Args:
            code: vestigingscode.
            point: latitude and longitude [deg].

        Returns:
            The closest building and its distance [m], or None if the code has no building with coordinates.
        """
        located = [(b, distance_m(point, (b.lat, b.lon))) for b in self.__by_code.get(code, [])
                   if b.lat is not None and b.lon is not None]
        return min(located, key=lambda pair: pair[1]) if located else None

    def vestiging(self, code: str) -> Optional[RioVestiging]:
        """An active school code.

        Args:
            code: vestigingscode.

        Returns:
            The school code with its name and board, or None if RIO does not know it.
        """
        return self.__vestigingen.get(code)

    def label(self, code: str) -> str:
        """Code with its RIO name, e.g. "17UD00 Dr J A Gerth V Wijksch ..."."""
        vestiging = self.__vestigingen.get(code)
        return f"{code} {vestiging.name}" if vestiging else code


def distance_m(first: Tuple[float, float], second: Tuple[float, float]) -> float:
    """Distance between two points, accurate enough within a city (equirectangular approximation).

    Args:
        first: latitude and longitude [deg].
        second: latitude and longitude [deg].

    Returns:
        The distance [m].
    """
    (lat1, lon1), (lat2, lon2) = first, second
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371000.0 * math.hypot(x, y)


def __exact_point(record: SchoolRecord) -> Optional[Tuple[float, float]]:
    """The BAG location of the record, only when its address exists in the BAG."""
    if record.geo is None or not record.geo.exact:
        return None
    return record.geo.lat, record.geo.lon


def __active(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Rows whose end date is empty or in the future."""
    today = date.today().isoformat()
    return frame[(frame[column] == "") | (frame[column] > today)]


def __float(text: str) -> Optional[float]:
    try:
        return float(text)
    except ValueError:
        return None


def __download_missing(settings: GlobalSettings) -> None:
    missing = [name for name in RIO_FILES if not (settings.rio_dir / f"{name}.csv").exists()]
    if not missing:
        return
    response = requests.get(RIO_PACKAGE_URL, timeout=60)
    response.raise_for_status()
    urls = {r["name"]: r["url"] for r in response.json()["result"]["resources"]}
    for name in missing:
        download_file(urls[name], settings.rio_dir / f"{name}.csv")


def load_rio(settings: GlobalSettings) -> RioRegister:
    """Load the RIO buildings and school codes, downloading the files on first use.

    Args:
        settings: build settings.

    Returns:
        The RIO lookups.

    Raises:
        requests.HTTPError: if a file is not cached and its download fails.
        KeyError: if DUO no longer publishes one of the expected files.
    """
    __download_missing(settings)

    def read(name: str) -> pd.DataFrame:
        return pd.read_csv(settings.rio_dir / f"{name}.csv", dtype=str, keep_default_na=False)

    usage = __active(read("relaties_onderwijslocatiegebruiken_vestigingserkenningen"), "EINDDATUM")
    located = usage.merge(read("onderwijslocaties"), on="ONDERWIJSLOCATIECODE")
    buildings: List[RioBuilding] = []
    for _, row in located.drop_duplicates(["VESTIGINGSCODE", "ONDERWIJSLOCATIECODE"]).iterrows():
        number, _ = parse_house_number(row["HUISNUMMER"])
        address = Address(street=clean(row["STRAATNAAM"]),
                          number=number,
                          addition=clean(row["HUISNUMMERTOEVOEGING"]).upper(),
                          postcode=normalize_postcode(row["POSTCODE"]))
        buildings.append(
            RioBuilding(code=row["VESTIGINGSCODE"],
                        address=address,
                        lat=__float(row["GPS_LATITUDE"]),
                        lon=__float(row["GPS_LONGITUDE"])))

    codes = __active(__active(read("vestigingserkenningen"), "EINDDATUM_PERIODE"), "UIT_BEDRIJFDATUM")
    codes = codes.drop_duplicates("VESTIGINGSCODE", keep="last")
    instelling = __active(read("relaties_onderwijsinstellingserkenningen_vestigingserkenningen"), "EINDDATUM")
    bestuur = __active(read("relaties_bevoegdgezagerkenningen_onderwijsinstellingserkenningen"), "EINDDATUM")
    besturen = __active(read("bevoegd_gezag_erkenningen"), "EINDDATUM_PERIODE").drop_duplicates("BGE_CODE", keep="last")
    instelling_of = dict(zip(instelling["VESTIGINGSCODE"], instelling["OIE_CODE"]))
    bestuur_of = dict(zip(bestuur["OIE_CODE"], bestuur["BGE_CODE"]))
    bestuur_naam = dict(zip(besturen["BGE_CODE"], besturen["VOLLEDIGE_NAAM"]))
    vestigingen: Dict[str, RioVestiging] = {}
    for _, row in codes.iterrows():
        code = row["VESTIGINGSCODE"]
        nummer = bestuur_of.get(instelling_of.get(code, ""), "")
        vestigingen[code] = RioVestiging(code=code,
                                         name=clean(row["VOLLEDIGE_NAAM"]),
                                         bestuur_nummer=nummer,
                                         bestuur_naam=clean(bestuur_naam.get(nummer, "")))
    return RioRegister(buildings, vestigingen)


def __confirm(record: SchoolRecord, building: RioBuilding) -> None:
    record.address_confirmed = True
    # the RIO location only replaces the map point when it is this very address and PDOK could not place it
    if building.address.same_place(record.address) and building.lat is not None and building.lon is not None:
        record.rio_point = (building.lat, building.lon)


def __labels(buildings: List[RioBuilding]) -> str:
    return " / ".join(b.address.label() for b in buildings)


def __building_of(record: SchoolRecord, rio: RioRegister, code: str, same_building_m: float) -> Optional[RioBuilding]:
    """The RIO building of a school code at the record's address, or within the same-building distance of it."""
    building = rio.building_at(code, record.address)
    if building is not None:
        return building
    point = __exact_point(record)
    near = rio.nearest(code, point) if point is not None else None
    return near[0] if near is not None and near[1] <= same_building_m else None


def __check_duo(record: SchoolRecord, rio: RioRegister, same_building_m: float) -> None:
    record.code_official = True
    building = __building_of(record, rio, record.code, same_building_m)
    if building is not None:
        __confirm(record, building)
        return
    buildings = rio.buildings_of(record.code)
    if buildings:
        record.note(NOTE_RIO_OTHER_BUILDING.format(code=record.code, addresses=__labels(buildings)))


def __check_sub_location(record: SchoolRecord, rio: RioRegister, same_building_m: float) -> None:
    """A confirmed sub-location takes the official code of its DUO location and loses its uncertainty notes."""
    ancestor = record.duo_ancestor()
    building = __building_of(record, rio, ancestor.code, same_building_m) if ancestor is not None else None
    if ancestor is not None and building is not None:
        record.code = ancestor.code
        record.code_official = True
        record.inherit = True
        record.drop_notes(*_SUB_LOCATION_NOTES)
        __confirm(record, building)
        return
    record.note(NOTE_RIO_NOT_CONFIRMED)
    others = [c for c in rio.codes_at(record.address) if ancestor is None or c != ancestor.code]
    if others:
        record.note(NOTE_RIO_BUILDING_OF.format(schools=", ".join(rio.label(c) for c in others)))


def __check_outside_duo(record: SchoolRecord, rio: RioRegister, same_building_m: float) -> None:
    """A school outside DUO-02 that RIO knows gets its official name and board; others keep their note."""
    code = record.code[:6]
    vestiging = rio.vestiging(code) if code else None
    others = [c for c in rio.codes_at(record.address) if c != code]
    if vestiging is None:
        if others:
            record.note(NOTE_RIO_BUILDING_OF.format(schools=", ".join(rio.label(c) for c in others)))
        return
    record.drop_notes(NOTE_NIET_IN_DUO)
    record.code = code
    record.code_official = True
    record.rio_name = vestiging.name
    record.rio_bestuur = (vestiging.bestuur_nummer, vestiging.bestuur_naam)
    building = __building_of(record, rio, code, same_building_m)
    if building is not None:
        __confirm(record, building)
        return
    buildings = rio.buildings_of(code)
    if buildings:
        record.note(NOTE_RIO_OTHER_BUILDING.format(code=code, addresses=__labels(buildings)))
    else:
        record.note(NOTE_RIO_NO_BUILDING.format(code=code))
    if others:
        record.note(NOTE_RIO_BUILDING_OF.format(schools=", ".join(rio.label(c) for c in others)))


def apply_rio(records: List[SchoolRecord],
              rio: RioRegister,
              same_building_m: float = 75.0) -> List[Tuple[SchoolRecord, RioBuilding]]:
    """Confirm or flag every record against RIO; addresses are never changed.

    DUO locations are checked for a RIO building at their address. Sub-locations and dependances that RIO lists as a
    building of their DUO location are confirmed and get the official code; the others are flagged. Schools outside
    DUO-02 that RIO knows (registered private schools) get their official name and board.

    Args:
        records: geocoded school records.
        rio: RIO lookups.
        same_building_m: a RIO building of the same school within this distance of an address that exists in the BAG
            counts as the same building [m].

    Returns:
        RIO buildings of schools in the register that no register row covers, with the school they belong to.
    """
    for record in records:
        if record.kind == KIND_DUO:
            __check_duo(record, rio, same_building_m)
        elif record.kind == KIND_NIET_IN_DUO:
            __check_outside_duo(record, rio, same_building_m)
        else:
            __check_sub_location(record, rio, same_building_m)

    def covered(building: RioBuilding, code: str) -> bool:
        # known when a register row or any of its CRM/Planned Culture rows has the address
        known = [r.address for r in records] + [s.address for r in records for s in r.sources]
        if any(a.same_place(building.address) for a in known):
            return True
        if building.lat is None or building.lon is None:
            return False
        family = [r for r in records if r.code[:6] == code or (r.duo_ancestor() or r).code == code]
        points = [p for p in (__exact_point(r) for r in family) if p is not None]
        return any(distance_m(p, (building.lat, building.lon)) <= same_building_m for p in points)

    unlisted: List[Tuple[SchoolRecord, RioBuilding]] = []
    for owner in records:
        if not (owner.kind == KIND_DUO or owner.rio_name):
            continue
        for building in rio.buildings_of(owner.code):
            if not covered(building, owner.code):
                unlisted.append((owner, building))
    by_code: DefaultDict[str, List[RioBuilding]] = defaultdict(list)
    for owner, building in unlisted:
        by_code[owner.code].append(building)
    for record in records:
        ancestor = record.duo_ancestor()
        if record.kind == KIND_DUO or record.address_confirmed or ancestor is None or not by_code.get(ancestor.code):
            continue
        here = (record.geo.lat, record.geo.lon) if record.geo else None
        labels = [
            f"{b.address.label()}, {distance_m(here, (b.lat, b.lon)):.0f} m"
            if here is not None and b.lat is not None and b.lon is not None else b.address.label()
            for b in by_code[ancestor.code]
        ]
        record.note(NOTE_RIO_UNLISTED.format(code=ancestor.code, addresses=" / ".join(labels)))
    return unlisted
