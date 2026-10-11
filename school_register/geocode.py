"""Geocoding of school addresses through the PDOK Locatieserver (BAG), with an on-disk cache."""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from school_register.globals import PDOK_URL
from school_register.normalize import Address

_FIELDS = ("type,straatnaam,huisnummer,huisletter,huisnummertoevoeging,postcode,woonplaatsnaam,gemeentecode,"
           "gemeentenaam,wijkcode,wijknaam,centroide_ll")


@dataclass(frozen=True)
class GeoResult:
    """Location and administrative areas of an address.

    Attributes:
        exact: True if the address itself was found in the BAG; False if only the postcode was found.
        street: BAG street name, empty if not exact.
        number: BAG house number, None if not exact.
        addition: BAG house letter and/or addition.
        postcode: BAG postcode without space.
        gemeentecode: CBS municipality code ("0518").
        gemeentenaam: municipality name.
        wijkcode: CBS wijk code ("WK051829").
        wijknaam: CBS wijk name without the "Wijk NN" prefix ("Schildersbuurt").
        lat: latitude [deg].
        lon: longitude [deg].
    """
    exact: bool
    street: str
    number: Optional[int]
    addition: str
    postcode: str
    gemeentecode: str
    gemeentenaam: str
    wijkcode: str
    wijknaam: str
    lat: float
    lon: float


def strip_wijk_prefix(wijknaam: str) -> str:
    """Remove the CBS numbering from a wijk name, "Wijk 29 Schildersbuurt" becomes "Schildersbuurt".

    Args:
        wijknaam: wijk name as returned by PDOK.

    Returns:
        The wijk name without prefix.
    """
    return re.sub(r"^Wijk\s+\d+\s+", "", wijknaam).strip()


def parse_point(point: str) -> Optional[Tuple[float, float]]:
    """Parse a WKT point "POINT(lon lat)".

    Args:
        point: WKT point as returned by PDOK.

    Returns:
        Latitude and longitude [deg], or None if the text is not a point.
    """
    match = re.match(r"POINT\(([-0-9.]+) ([-0-9.]+)\)", point or "")
    if not match:
        return None
    return float(match.group(2)), float(match.group(1))


class PdokGeocoder:
    """Look up addresses in the PDOK Locatieserver, caching every response on disk.

    Attributes:
        cache_path: JSON file holding the raw PDOK documents per query.
    """

    def __init__(self, cache_path: Path, session: Optional[requests.Session] = None) -> None:
        """Create a geocoder.

        Args:
            cache_path: JSON file used to cache PDOK responses between runs.
            session: HTTP session, injectable for tests.
        """
        self.cache_path = cache_path
        self.__session = session or requests.Session()
        self.__cache: Dict[str, List[Dict[str, Any]]] = {}
        if cache_path.exists():
            self.__cache = json.loads(cache_path.read_text(encoding="utf-8"))

    def save(self) -> None:
        """Write the cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.__cache, indent=1, sort_keys=True, ensure_ascii=False),
                                   encoding="utf-8")

    def __query(self, query: str, doc_type: str) -> List[Dict[str, Any]]:
        key = f"{doc_type}|{query}"
        if key not in self.__cache:
            params: Dict[str, str] = {"q": query, "fq": f"type:{doc_type}", "rows": "20", "fl": _FIELDS}
            response = self.__session.get(PDOK_URL, params=params, timeout=30)
            response.raise_for_status()
            self.__cache[key] = response.json()["response"]["docs"]
        return self.__cache[key]

    @staticmethod
    def __pick(docs: List[Dict[str, Any]], addition: str) -> Optional[Dict[str, Any]]:
        if not docs:
            return None
        wanted = addition.upper()
        for doc in docs:
            doc_addition = (doc.get("huisletter", "") + doc.get("huisnummertoevoeging", "")).upper()
            if doc_addition == wanted:
                return doc
        return docs[0]

    def geocode(self, address: Address) -> Optional[GeoResult]:
        """Find an address in the BAG, falling back to the centre of its postcode.

        Args:
            address: address to look up; needs at least a postcode.

        Returns:
            The location, or None if neither the address nor the postcode is known to PDOK.

        Raises:
            requests.HTTPError: if PDOK returns an error for a query that is not cached.
        """
        if not address.postcode:
            return None
        if address.number is not None:
            doc = self.__pick(self.__query(f"postcode:{address.postcode} AND huisnummer:{address.number}", "adres"),
                              address.addition)
            if doc:
                return self.__to_result(doc, exact=True)
        # the address is not in the BAG: use the nearest existing house number in the same postcode, which also
        # gives the wijk (postcode documents have no wijk)
        docs = self.__query(f"postcode:{address.postcode}", "adres")
        if not docs:
            return None
        wanted = address.number or 0
        nearest = min(docs, key=lambda d: (abs(int(d.get("huisnummer", 0)) - wanted), d.get("huisnummer", 0)))
        return self.__to_result(nearest, exact=False)

    @staticmethod
    def __to_result(doc: Dict[str, Any], exact: bool) -> Optional[GeoResult]:
        point = parse_point(doc.get("centroide_ll", ""))
        if point is None:
            return None
        addition = doc.get("huisletter", "") + doc.get("huisnummertoevoeging", "")
        return GeoResult(exact=exact,
                         street=doc.get("straatnaam", "") if exact else "",
                         number=doc.get("huisnummer") if exact else None,
                         addition=addition.upper() if exact else "",
                         postcode=doc.get("postcode", ""),
                         gemeentecode=doc.get("gemeentecode", ""),
                         gemeentenaam=doc.get("gemeentenaam", ""),
                         wijkcode=doc.get("wijkcode", ""),
                         wijknaam=strip_wijk_prefix(doc.get("wijknaam", "")),
                         lat=point[0],
                         lon=point[1])
