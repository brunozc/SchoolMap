"""Entity resolution: merge DUO, CRM and Planned Culture rows into one record per school location."""
from dataclasses import dataclass, field
from itertools import groupby
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from school_register.geocode import GeoResult
from school_register.globals import (KIND_DEPENDANCE, KIND_DUO, KIND_NEVENLOCATIE, KIND_NIET_IN_DUO, NOTE_DEPENDANCE,
                                     NOTE_NEVENLOCATIE, NOTE_NEVENLOCATIE_EIGEN_BESTUUR, NOTE_NIET_IN_DUO, SOURCE_CRM,
                                     SOURCE_PC, GlobalSettings)
from school_register.normalize import Address, clean, name_similarity, names_similar, parse_split_address
from school_register.sources import REASON_ARCHIVED, ExcludedRow, SourceRow


@dataclass
class SchoolRecord:
    """One physical school location in the register.

    Attributes:
        kind: DUO, NEVENLOCATIE, DEPENDANCE or NIET_IN_DUO.
        name: school name used in the register.
        code: vestigingscode used in the register, empty if unknown.
        address: address used for matching and geocoding.
        duo: the DUO row for DUO records, empty otherwise.
        parent: main location this record inherits board and denominatie from.
        inherit: whether board, denominatie and correspondence address are taken from the parent.
        sources: CRM and Planned Culture rows describing this location.
        dependance_of: the Planned Culture row whose dependance address created this record.
        notes: DATA_KWALITEIT notes.
        geo: BAG location of the address.
        code_official: True if the code is confirmed by DUO or RIO for this location.
        address_confirmed: True if RIO registers this address as a building of the location's code.
        rio_point: latitude and longitude of the RIO building [deg], when RIO confirms the address.
        rio_name: official name from RIO, for schools that RIO knows but DUO-02 does not.
        rio_bestuur: bevoegd gezag number and name from RIO, for the same schools.
    """
    kind: str
    name: str
    code: str
    address: Address
    duo: Dict[str, str] = field(default_factory=dict)
    parent: Optional["SchoolRecord"] = None
    inherit: bool = False
    sources: List[SourceRow] = field(default_factory=list)
    dependance_of: Optional[SourceRow] = None
    notes: List[str] = field(default_factory=list)
    geo: Optional[GeoResult] = None
    code_official: bool = False
    address_confirmed: bool = False
    rio_point: Optional[Tuple[float, float]] = None
    rio_name: str = ""
    rio_bestuur: Tuple[str, str] = ("", "")

    def codes(self) -> Set[str]:
        """Base vestigingscodes used for this location by DUO and the sources."""
        codes = {s.base_code for s in self.sources if s.base_code}
        if self.kind == KIND_DUO:
            codes.add(self.code)
        return codes

    def names(self) -> List[str]:
        """All names this location goes by in DUO and the sources."""
        return [self.name] + [s.name for s in self.sources]

    def has_source(self, source: str) -> bool:
        """Check whether a row from the given source is linked to this location.

        Args:
            source: name of the source file.

        Returns:
            True if at least one row of that source is linked.
        """
        return any(s.source == source for s in self.sources)

    def note(self, text: str) -> None:
        """Add a DATA_KWALITEIT note, once.

        Args:
            text: the note.
        """
        if text not in self.notes:
            self.notes.append(text)

    def drop_notes(self, *prefixes: str) -> None:
        """Remove the notes that start with any of the given texts.

        Args:
            prefixes: beginnings of the notes to remove.
        """
        self.notes = [n for n in self.notes if not n.startswith(prefixes)]

    def duo_ancestor(self) -> Optional["SchoolRecord"]:
        """The DUO location this record belongs to: itself, its parent, or its parent's parent.

        Returns:
            The DUO record, or None for a school outside DUO.
        """
        record: Optional[SchoolRecord] = self
        while record is not None and record.kind != KIND_DUO:
            record = record.parent
        return record


class Matcher:
    """Build school records from DUO and link CRM and Planned Culture rows to them.

    Attributes:
        records: all school records built so far, DUO records first.
        excluded: source rows that were dropped while matching.
        links: for every linked source row, the record it belongs to, keyed by (source, source ID).
    """

    def __init__(self, duo: pd.DataFrame, settings: GlobalSettings) -> None:
        """Seed the register with one record per DUO location.

        Args:
            duo: DUO rows of the municipality.
            settings: build settings.
        """
        self.__threshold = settings.name_similarity
        self.records: List[SchoolRecord] = []
        self.excluded: List[ExcludedRow] = []
        self.links: Dict[Tuple[str, str], SchoolRecord] = {}
        self.__by_duo_code: Dict[str, SchoolRecord] = {}
        self.__main_by_brin: Dict[str, SchoolRecord] = {}
        for _, row in duo.sort_values("VESTIGINGSCODE").iterrows():
            values = {str(k): clean(v) for k, v in row.items()}
            record = SchoolRecord(kind=KIND_DUO,
                                  name=values["VESTIGINGSNAAM"],
                                  code=values["VESTIGINGSCODE"],
                                  address=parse_split_address(values["STRAATNAAM"], values["HUISNUMMER-TOEVOEGING"], "",
                                                              values["POSTCODE"]),
                                  duo=values,
                                  code_official=True)
            self.records.append(record)
            self.__by_duo_code[record.code] = record
            # the lowest location number of an instelling is its main location
            self.__main_by_brin.setdefault(values["INSTELLINGSCODE"], record)

    def __similar(self, name: str, record: SchoolRecord) -> bool:
        return any(names_similar(name, other, self.__threshold) for other in record.names())

    @staticmethod
    def __best(name: str, candidates: List[SchoolRecord]) -> SchoolRecord:
        return max(candidates, key=lambda r: max(name_similarity(name, n) for n in r.names()))

    def __match_at_address(self, row: SourceRow, pool: List[SchoolRecord]) -> Optional[SchoolRecord]:
        """Find the record at the same address: by name, or by code if the name differs."""
        at_address = [r for r in pool if r.address.same_place(row.address)]
        similar = [r for r in at_address if self.__similar(row.name, r)]
        if similar:
            return self.__best(row.name, similar)
        coded = [r for r in at_address if row.base_code and row.base_code in r.codes()]
        if len(coded) == 1:
            return coded[0]
        return None

    def __match_same_code(self, row: SourceRow, pool: List[SchoolRecord]) -> Optional[SchoolRecord]:
        """Find a record with the same code and a similar name at a different address."""
        if not row.base_code:
            return None
        candidates = [r for r in pool if row.base_code in r.codes() and self.__similar(row.name, r)]
        return self.__best(row.name, candidates) if candidates else None

    def __match_same_brin_nearby(self, row: SourceRow, pool: List[SchoolRecord]) -> Optional[SchoolRecord]:
        """Find a record of the same instelling with a similar name on the same street or in the same postcode.

        Catches rows whose location number and house number are both wrong, e.g. "19SI01, De la Reyweg 212, 2573AH"
        for the De La Reyschool building at Voorthuizenstraat 245, 2573AH.
        """
        if not row.base_code:
            return None
        brin = row.base_code[:4]
        street = row.address.street.lower()
        candidates = [
            r for r in pool if any(c[:4] == brin for c in r.codes()) and self.__similar(row.name, r) and (
                r.address.postcode == row.address.postcode or (street and r.address.street.lower() == street))
        ]
        return self.__best(row.name, candidates) if candidates else None

    def __link(self, record: SchoolRecord, row: SourceRow) -> None:
        record.sources.append(row)
        self.links[(row.source, row.source_id)] = record

    def __create(self, row: SourceRow) -> SchoolRecord:
        """Create a record for a row that matches no existing location."""
        existing = self.__match_at_address(row, [r for r in self.records if r.kind != KIND_DUO])
        if existing:
            self.__link(existing, row)
            return existing
        parent = None
        if row.base_code:
            parent = self.__by_duo_code.get(row.base_code) or self.__main_by_brin.get(row.base_code[:4])
        if parent is None:
            record = SchoolRecord(kind=KIND_NIET_IN_DUO, name=row.name, code=row.full_code, address=row.address)
            record.note(NOTE_NIET_IN_DUO)
        else:
            parent_bg = parent.duo.get("BEVOEGD GEZAG NUMMER", "")
            # a different board means the code was most likely invented or mistyped, not a real sub-location
            inherit = not (row.bg_nummer and row.bg_nummer != parent_bg)
            record = SchoolRecord(kind=KIND_NEVENLOCATIE,
                                  name=row.name,
                                  code=row.full_code,
                                  address=row.address,
                                  parent=parent,
                                  inherit=inherit)
            record.note((NOTE_NEVENLOCATIE if inherit else NOTE_NEVENLOCATIE_EIGEN_BESTUUR).format(parent=parent.code))
        self.records.append(record)
        self.__link(record, row)
        return record

    def add_crm(self, rows: List[SourceRow]) -> None:
        """Link CRM rows to DUO locations, creating sub-locations and non-DUO schools for the rest.

        Rows at the address of a DUO location are linked first, so that a code shared by several CRM rows ends up
        with the row that really sits at the DUO address.

        Args:
            rows: CRM rows in scope.
        """
        duo_records = list(self.records)
        pending: List[SourceRow] = []
        for row in rows:
            record = self.__match_at_address(row, duo_records)
            if record:
                self.__link(record, row)
            else:
                pending.append(row)
        pending.sort(key=lambda r: (r.base_code, r.suffix, r.source_id))
        for base_code, group_iter in groupby(pending, key=lambda r: r.base_code):
            group = list(group_iter)
            record = self.__by_duo_code.get(base_code) if base_code else None
            if record and not record.has_source(SOURCE_CRM):
                similar = [r for r in group if self.__similar(r.name, record)]
                if similar:
                    best = max(similar, key=lambda r: max(name_similarity(r.name, n) for n in record.names()))
                    self.__link(record, best)
                    group.remove(best)
            for row in group:
                self.__create(row)

    def add_planned_culture(self, rows: List[SourceRow]) -> None:
        """Link Planned Culture rows to existing locations, creating records for schools not seen before.

        Archived rows that match nothing are excluded; their dependance addresses are ignored.

        Args:
            rows: Planned Culture rows in scope.
        """
        for row in rows:
            record = (self.__match_at_address(row, self.records) or self.__match_same_code(row, self.records)
                      or self.__match_same_brin_nearby(row, self.records))
            if record:
                self.__link(record, row)
            elif row.archived:
                self.excluded.append(
                    ExcludedRow(row.source, row.source_id, row.name, row.full_code, row.address.label(),
                                REASON_ARCHIVED))
            else:
                self.__create(row)
        for row in rows:
            record = self.links.get((row.source, row.source_id))
            if record is None or row.archived:
                continue
            for address, code in row.dependances:
                self.__add_dependance(record, row, address, code)

    def __add_dependance(self, main: SchoolRecord, row: SourceRow, address: Address, code: str) -> None:
        if address.key is None or address.same_place(main.address):
            return
        for other in self.records:
            if not other.address.same_place(address):
                continue
            same_school = (other is main or other.parent is main or bool(main.codes() & other.codes())
                           or (code and code in other.codes()) or self.__similar(main.name, other))
            if same_school:
                return
        record = SchoolRecord(kind=KIND_DEPENDANCE,
                              name=f"{main.name} (dependance {address.street})",
                              code=code,
                              address=address,
                              parent=main,
                              inherit=True,
                              dependance_of=row)
        record.note(NOTE_DEPENDANCE)
        self.records.append(record)

    def source_rows(self) -> Dict[str, List[SourceRow]]:
        """Group linked source rows per source, for reporting.

        Returns:
            Linked rows keyed by source name.
        """
        grouped: Dict[str, List[SourceRow]] = {SOURCE_CRM: [], SOURCE_PC: []}
        for record in self.records:
            for row in record.sources:
                grouped.setdefault(row.source, []).append(row)
        return grouped
