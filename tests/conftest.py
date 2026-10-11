"""Shared fixtures and builders for the school register tests."""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pytest

from school_register.geocode import GeoResult, PdokGeocoder
from school_register.globals import DUO_COPIED_COLUMNS, SOURCE_CRM, SOURCE_PC, GlobalSettings
from school_register.normalize import Address
from school_register.sources import SourceRow


def duo_row(code: str,
            name: str,
            street: str,
            number: str,
            postcode: str,
            bg: str = "41572",
            denominatie: str = "Openbaar") -> Dict[str, str]:
    """Build one DUO row with every copied column filled."""
    row = {col: "" for col in DUO_COPIED_COLUMNS}
    row.update({
        "BEVOEGD GEZAG NUMMER": bg,
        "INSTELLINGSCODE": code[:4],
        "VESTIGINGSCODE": code,
        "VESTIGINGSNAAM": name,
        "STRAATNAAM": street,
        "HUISNUMMER-TOEVOEGING": number,
        "POSTCODE": postcode,
        "PLAATSNAAM": "'S-GRAVENHAGE",
        "GEMEENTENUMMER": "0518",
        "GEMEENTENAAM": "S GRAVENHAGE",
        "DENOMINATIE": denominatie,
        "STRAATNAAM CORRESPONDENTIEADRES": "Postbus",
        "HUISNUMMER-TOEVOEGING CORRESPONDENTIEADRES": "1",
        "POSTCODE CORRESPONDENTIEADRES": "2500 AA",
        "PLAATSNAAM CORRESPONDENTIEADRES": "'S-GRAVENHAGE",
    })
    return row


def duo_frame(rows: List[Dict[str, str]]) -> pd.DataFrame:
    """Build a DUO frame from rows made by duo_row."""
    return pd.DataFrame(rows)


def source_row(source: str, source_id: str, name: str, code: str, address: Tuple[str, Optional[int], str, str],
               **extra: object) -> SourceRow:
    """Build a CRM or Planned Culture row; code may carry a CRM letter suffix."""
    street, number, addition, postcode = address
    return SourceRow(source=source,
                     source_id=source_id,
                     name=name,
                     base_code=code[:6],
                     suffix=code[6:],
                     address=Address(street, number, addition, postcode),
                     **extra)  # type: ignore[arg-type]


def crm(source_id: str, name: str, code: str, address: Tuple[str, Optional[int], str, str],
        **extra: object) -> SourceRow:
    """Build a CRM row."""
    return source_row(SOURCE_CRM, source_id, name, code, address, **extra)


def pc(source_id: str, name: str, code: str, address: Tuple[str, Optional[int], str, str],
       **extra: object) -> SourceRow:
    """Build a Planned Culture row."""
    return source_row(SOURCE_PC, source_id, name, code, address, **extra)


def geo(lat: float = 52.07,
        lon: float = 4.30,
        gemeentecode: str = "0518",
        wijkcode: str = "WK051829",
        exact: bool = True) -> GeoResult:
    """Build a geocoding result."""
    return GeoResult(exact=exact,
                     street="BAG-straat" if exact else "",
                     number=1 if exact else None,
                     addition="",
                     postcode="2525GG",
                     gemeentecode=gemeentecode,
                     gemeentenaam="'s-Gravenhage" if gemeentecode == "0518" else "Rijswijk",
                     wijkcode=wijkcode,
                     wijknaam="Schildersbuurt",
                     lat=lat,
                     lon=lon)


class FakeGeocoder(PdokGeocoder):
    """Geocoder that answers from a dict keyed by postcode, without network access."""

    def __init__(self, cache_path: Path, results: Dict[str, Optional[GeoResult]]) -> None:
        """Create the fake.

        Args:
            cache_path: unused cache location.
            results: geocoding result per postcode.
        """
        super().__init__(cache_path)
        self.results = results

    def geocode(self, address: Address) -> Optional[GeoResult]:
        """Return the prepared result for the postcode of the address."""
        return self.results.get(address.postcode)

    def save(self) -> None:
        """Do not write a cache."""


@pytest.fixture
def settings(tmp_path: Path) -> GlobalSettings:
    """Settings writing to a temporary directory."""
    return GlobalSettings(output_dir=tmp_path / "output", cache_dir=tmp_path / "cache")
