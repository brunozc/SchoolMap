"""Tests for school_register.rio and the RIO-based corrections and ID stability."""
import csv
from pathlib import Path
from typing import Dict, List, Optional

import pytest
from conftest import FakeGeocoder, crm, duo_frame, duo_row, geo

from school_register.export import write_workbook
from school_register.globals import (KIND_DEPENDANCE, KIND_DUO, KIND_NEVENLOCATIE, KIND_NIET_IN_DUO, NOTE_DEPENDANCE,
                                     NOTE_NIET_IN_DUO, NOTE_NOT_IN_BAG, NOTE_RIO_NOT_CONFIRMED, GlobalSettings)
from school_register.matching import Matcher, SchoolRecord
from school_register.normalize import Address
from school_register.register import (assign_ids, build_rows, collect_corrections, geocode_records, read_previous_ids)
from school_register.rio import RioBuilding, RioRegister, RioVestiging, apply_rio, distance_m, load_rio

# about 0.0001 degree latitude is 11 m
NEAR = 0.0002
FAR = 0.01


def building(code: str, street: str, number: int, postcode: str, lat: float, lon: float = 4.30) -> RioBuilding:
    """Build a RIO building."""
    return RioBuilding(code=code, address=Address(street, number, "", postcode), lat=lat, lon=lon)


def register() -> RioRegister:
    """A small RIO with two buildings for 19SI00, one for 05VW00, a private school and a shared building."""
    return RioRegister(
        [
            building("19SI00", "De la Reyweg", 212, "2571GH", 52.0700),
            building("19SI00", "Voorthuizenstraat", 245, "2573AH", 52.0500),
            building("05VW00", "Turfhaven", 7, "2511DK", 52.0800),
            building("17UD00", "Withuysstraat", 2, "2523GW", 52.0400),
            building("30WD00", "Bezuidenhoutseweg", 91, "2594AC", 52.0900),
            building("30BH00", "Korte Voorhout", 1, "2511CW", 52.0950),
        ], {
            "30WD00": RioVestiging("30WD00", "Winford Bilingual Primary School", "90458", "Winford Beheer B.V."),
            "30BH00": RioVestiging("30BH00", "Winford Den Haag VO", "90458", "Winford Beheer B.V."),
            "17UD00": RioVestiging("17UD00", "Gerth van Wijkschool", "70176", "SCOH"),
        })


def record(kind: str,
           code: str,
           street: str,
           number: int,
           postcode: str,
           lat: float,
           exact: bool = True,
           parent: Optional[SchoolRecord] = None,
           notes: Optional[List[str]] = None) -> SchoolRecord:
    """Build a geocoded school record."""
    result = SchoolRecord(kind=kind,
                          name=f"School {street}",
                          code=code,
                          address=Address(street, number, "", postcode),
                          duo={"BEVOEGD GEZAG NUMMER": "41572"} if kind == KIND_DUO else {},
                          parent=parent,
                          notes=list(notes or []),
                          code_official=kind == KIND_DUO)
    result.geo = geo(lat=lat, exact=exact)
    return result


class TestRioRegister:
    """Tests for the RIO lookups."""

    def test_building_at(self) -> None:
        """A building is found by code and address, house letters ignored."""
        rio = register()
        assert rio.building_at("19SI00", Address("De la Reyweg", 212, "A", "2571GH")) is not None
        assert rio.building_at("05VW00", Address("De la Reyweg", 212, "", "2571GH")) is None

    def test_codes_at(self) -> None:
        """All codes using a building are returned."""
        assert register().codes_at(Address("Withuysstraat", 2, "", "2523GW")) == ["17UD00"]

    def test_nearest(self) -> None:
        """The nearest building of a code is returned with its distance."""
        found = register().nearest("19SI00", (52.0702, 4.30))
        assert found is not None
        assert found[0].address.street == "De la Reyweg"
        assert found[1] == pytest.approx(22.2, abs=0.5)

    def test_distance(self) -> None:
        """One thousandth of a degree latitude is about 111 m."""
        assert distance_m((52.0, 4.3), (52.001, 4.3)) == pytest.approx(111.2, abs=0.5)


class TestApplyRio:
    """Tests for apply_rio."""

    def test_duo_confirmed(self) -> None:
        """A DUO address that RIO registers is confirmed; the other RIO building is reported as missing."""
        duo = record(KIND_DUO, "19SI00", "De la Reyweg", 212, "2571GH", 52.0700)
        unlisted = apply_rio([duo], register())
        assert duo.address_confirmed
        assert duo.notes == []
        assert [b.address.street for _, b in unlisted] == ["Voorthuizenstraat"]

    def test_duo_same_complex(self) -> None:
        """A RIO building of the same school a few metres away confirms the address; the BAG point is kept."""
        duo = record(KIND_DUO, "05VW00", "Spuiplein", 150, "2511DG", 52.0800 + NEAR)
        unlisted = apply_rio([duo], register())
        assert duo.address_confirmed
        assert duo.rio_point is None
        assert unlisted == []

    def test_duo_other_building(self) -> None:
        """A RIO building far away is flagged and the address is not changed."""
        duo = record(KIND_DUO, "05VW00", "Nassaulaan", 26, "2514JT", 52.0800 + FAR)
        apply_rio([duo], register())
        assert not duo.address_confirmed
        assert duo.address.street == "Nassaulaan"
        assert duo.notes == [
            "Volgens RIO is het lesgebouw van 05VW00: Turfhaven 7 (2511DK); dit adres staat niet in RIO"
        ]

    def test_unplaced_address_gets_rio_point(self) -> None:
        """When PDOK only found the postcode but RIO knows the address, the map uses the RIO location."""
        duo = record(KIND_DUO, "19SI00", "Voorthuizenstraat", 245, "2573AH", 52.1, exact=False)
        apply_rio([duo], register())
        row = build_rows([duo], {})[0]
        assert row.values["LATITUDE"] == "52.050000"
        assert NOTE_NOT_IN_BAG not in row.values["DATA_KWALITEIT"]

    def test_sub_location_confirmed(self) -> None:
        """A sub-location at a RIO building of its DUO location takes the official code and loses its notes."""
        duo = record(KIND_DUO, "19SI00", "De la Reyweg", 212, "2571GH", 52.0700)
        sub = record(KIND_NEVENLOCATIE,
                     "19SI00B",
                     "Voorthuizenstraat",
                     245,
                     "2573AH",
                     52.0500,
                     parent=duo,
                     notes=["Nevenlocatie van 19SI00, niet apart in DUO; bestuur overgenomen"])
        unlisted = apply_rio([duo, sub], register())
        assert sub.code == "19SI00"
        assert sub.code_official and sub.address_confirmed and sub.inherit
        assert sub.notes == []
        assert unlisted == []

    def test_sub_location_not_confirmed(self) -> None:
        """An unknown dependance is flagged, with the distance to RIO buildings missing from the register."""
        duo = record(KIND_DUO, "05VW00", "Turfhaven", 7, "2511DK", 52.0800)
        other = record(KIND_DUO, "19SI00", "De la Reyweg", 212, "2571GH", 52.0700)
        dep = record(KIND_DEPENDANCE, "", "Eksterhof", 3, "2496HT", 52.0300, parent=other, notes=[NOTE_DEPENDANCE])
        apply_rio([duo, other, dep], register())
        assert NOTE_DEPENDANCE in dep.notes
        assert NOTE_RIO_NOT_CONFIRMED in dep.notes
        hint = "RIO-gebouwen van 19SI00 die niet in dit register staan: Voorthuizenstraat 245 (2573AH), 2224 m"
        assert hint in dep.notes

    def test_registered_private_school(self) -> None:
        """A school outside DUO-02 that RIO knows gets its official name and board, and its address is checked."""
        school = record(KIND_NIET_IN_DUO, "30WD00", "Korte Voorhout", 1, "2511CW", 52.0950, notes=[NOTE_NIET_IN_DUO])
        unlisted = apply_rio([school], register())
        assert school.rio_name == "Winford Bilingual Primary School"
        assert school.rio_bestuur == ("90458", "Winford Beheer B.V.")
        assert NOTE_NIET_IN_DUO not in school.notes
        assert "Volgens RIO is dit gebouw van 30BH00 Winford Den Haag VO" in school.notes
        assert [b.address.street for _, b in unlisted] == ["Bezuidenhoutseweg"]
        values = build_rows([school], {})[0].values
        assert values["VESTIGINGSNAAM"] == "Winford Bilingual Primary School"
        assert values["BEVOEGD_GEZAG_NUMMER"] == "90458"

    def test_unregistered_school_in_shared_building(self) -> None:
        """A school RIO does not know keeps its note and learns whose building it uses."""
        school = record(KIND_NIET_IN_DUO, "", "Withuysstraat", 2, "2523GW", 52.0400, notes=[NOTE_NIET_IN_DUO])
        apply_rio([school], register())
        assert school.notes == [NOTE_NIET_IN_DUO, "Volgens RIO is dit gebouw van 17UD00 Gerth van Wijkschool"]


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    """Write rows as a CSV with a header."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class TestLoadRio:
    """Tests for load_rio on small cached files."""

    def test_load(self, settings: GlobalSettings, tmp_path: Path) -> None:
        """Active buildings and school codes are loaded with their board; ended links are ignored."""
        settings.external_dir = tmp_path / "external"
        folder = settings.rio_dir
        folder.mkdir(parents=True)
        write_csv(folder / "onderwijslocaties.csv", [
            {"ONDERWIJSLOCATIECODE": "L1", "BAG_ID": "1", "GPS_LATITUDE": "52.07", "GPS_LONGITUDE": "4.30",
             "STRAATNAAM": "Zuidwal", "HUISNUMMER": "47", "HUISNUMMERTOEVOEGING": "", "POSTCODE": "2512XT",
             "PLAATSNAAM": "'s-Gravenhage"},
            {"ONDERWIJSLOCATIECODE": "L2", "BAG_ID": "2", "GPS_LATITUDE": "", "GPS_LONGITUDE": "",
             "STRAATNAAM": "Lepelstraat", "HUISNUMMER": "6", "HUISNUMMERTOEVOEGING": "", "POSTCODE": "2512CW",
             "PLAATSNAAM": "'s-Gravenhage"},
        ])  # yapf: disable
        write_csv(folder / "relaties_onderwijslocatiegebruiken_vestigingserkenningen.csv", [
            {"ONDERWIJSLOCATIECODE": "L1", "ONDERWIJSBESTUURID": "B", "VESTIGINGSCODE": "19ZJ00",
             "BEGINDATUM": "2010-01-01", "EINDDATUM": ""},
            {"ONDERWIJSLOCATIECODE": "L2", "ONDERWIJSBESTUURID": "B", "VESTIGINGSCODE": "19ZJ00",
             "BEGINDATUM": "2010-01-01", "EINDDATUM": "2015-01-01"},
        ])  # yapf: disable
        write_csv(folder / "vestigingserkenningen.csv", [
            {"VESTIGINGSCODE": "19ZJ00", "EINDDATUM_PERIODE": "", "UIT_BEDRIJFDATUM": "", "VOLLEDIGE_NAAM": "Zuidwal"},
        ])  # yapf: disable
        write_csv(folder / "relaties_onderwijsinstellingserkenningen_vestigingserkenningen.csv", [{
            "OIE_CODE": "19ZJ",
            "VESTIGINGSCODE": "19ZJ00",
            "BEGINDATUM": "2010-01-01",
            "EINDDATUM": ""
        }])
        write_csv(folder / "relaties_bevoegdgezagerkenningen_onderwijsinstellingserkenningen.csv", [{
            "BGE_CODE": "41572",
            "OIE_CODE": "19ZJ",
            "BEGINDATUM": "2010-01-01",
            "EINDDATUM": ""
        }])
        write_csv(folder / "bevoegd_gezag_erkenningen.csv", [{
            "BGE_CODE": "41572",
            "EINDDATUM_PERIODE": "",
            "VOLLEDIGE_NAAM": "De Haagse Scholen"
        }])
        rio = load_rio(settings)
        assert [b.address.street for b in rio.buildings_of("19ZJ00")] == ["Zuidwal"]
        assert rio.buildings_of("19ZJ00")[0].lat == pytest.approx(52.07)
        assert rio.vestiging("19ZJ00") == RioVestiging("19ZJ00", "Zuidwal", "41572", "De Haagse Scholen")
        assert rio.vestiging("99XX00") is None


class TestRioCorrectionsAndIds:
    """Tests for corrections and UNIEK_ID stability once RIO changes codes."""

    @staticmethod
    def matched(tmp_path: Path) -> List[SchoolRecord]:
        """Match a DUO school with two CRM buildings and geocode them without network."""
        duo = duo_frame([duo_row("19SI00", "De La Reyschool", "De la Reyweg", "212", "2571 GH")])
        matcher = Matcher(duo, GlobalSettings())
        matcher.add_crm([
            crm("1", "De La Reyschool (De La Reyweg)", "19SI00A", ("De La Reyweg", 212, "", "2571GH")),
            crm("2",
                "De La Reyschool (Voorthuizenstraat)",
                "19SI09", ("Voorthuizenstraat", 245, "", "2573AH"),
                stadsdeel="Centrum"),
        ])
        geocoder = FakeGeocoder(tmp_path / "c.json", {"2571GH": geo(lat=52.07), "2573AH": geo(lat=52.05)})
        records, _ = geocode_records(matcher.records, geocoder)
        return records

    def test_wrong_code_becomes_correction(self, tmp_path: Path, settings: GlobalSettings) -> None:
        """A confirmed sub-location gets the official code; the invented CRM code is listed as a correction."""
        records = self.matched(tmp_path)
        unlisted = apply_rio(records, register())
        rows, _ = assign_ids(build_rows(records, {}), {}, 0, settings)
        sub = next(r for r in rows if r.record.kind == KIND_NEVENLOCATIE)
        assert sub.values["VESTIGINGSCODE"] == "19SI00"
        assert sub.values["DATA_KWALITEIT"] == ""
        fixes = collect_corrections(rows, unlisted)
        assert [(c.source_id, c.field_name, c.value, c.correct) for c in fixes if c.field_name == "VESTIGINGSCODE"] \
            == [("2", "VESTIGINGSCODE", "19SI09", "19SI00")]

    def test_ids_survive_code_change(self, tmp_path: Path, settings: GlobalSettings) -> None:
        """A row keeps its UNIEK_ID through the Koppeling sheet when RIO gives it the official code."""
        before = build_rows(self.matched(tmp_path), {})
        before, highest = assign_ids(before, {}, 0, settings)
        write_workbook(before, [], highest, settings)
        ids_before = {r.values["VESTIGINGSNAAM"]: r.values["UNIEK_ID"] for r in before}

        records = self.matched(tmp_path)
        apply_rio(records, register())
        previous, stored_highest = read_previous_ids(settings.xlsx_path)
        after, _ = assign_ids(build_rows(records, {}), previous, stored_highest, settings)
        assert {r.values["VESTIGINGSNAAM"]: r.values["UNIEK_ID"] for r in after} == ids_before
