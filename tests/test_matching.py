"""Tests for school_register.matching."""
from conftest import crm, duo_frame, duo_row, pc

from school_register.globals import (KIND_DEPENDANCE, KIND_DUO, KIND_NEVENLOCATIE, KIND_NIET_IN_DUO, NOTE_NIET_IN_DUO,
                                     GlobalSettings)
from school_register.matching import Matcher
from school_register.normalize import Address
from school_register.sources import REASON_ARCHIVED


def make_matcher() -> Matcher:
    """Two DUO schools: Haagsche Schoolvereeniging (05VW00) and De La Reyschool (19SI00)."""
    duo = duo_frame([
        duo_row("05VW00",
                "Basisschool van de Stichting Haagsche School Vereniging",
                "Nassaulaan",
                "26",
                "2514 JT",
                bg="95694"),
        duo_row("19SI00", "De La Reyschool", "De la Reyweg", "212", "2571 GH"),
    ])
    return Matcher(duo, GlobalSettings())


class TestAddCrm:
    """Tests for Matcher.add_crm."""

    def test_link_at_duo_address(self) -> None:
        """A CRM row at the DUO address with the same code is linked, not added."""
        matcher = make_matcher()
        matcher.add_crm([crm("1", "De La Reyschool (De La Reyweg)", "19SI00A", ("De La Reyweg", 212, "", "2571GH"))])
        assert len(matcher.records) == 2
        assert matcher.links[("CRM", "1")].code == "19SI00"

    def test_shared_code_becomes_nevenlocatie(self) -> None:
        """Of two CRM rows sharing a code, the one away from the DUO address becomes a sub-location."""
        matcher = make_matcher()
        matcher.add_crm([
            crm("1", "De La Reyschool (Voorthuizenstraat)", "19SI00B", ("Voorthuizenstraat", 245, "", "2573AH")),
            crm("2", "De La Reyschool (De La Reyweg)", "19SI00A", ("De La Reyweg", 212, "", "2571GH")),
        ])
        main, extra = matcher.links[("CRM", "2")], matcher.links[("CRM", "1")]
        assert main.kind == KIND_DUO
        assert extra.kind == KIND_NEVENLOCATIE
        assert extra.parent is main
        assert extra.code == "19SI00B"
        assert extra.inherit

    def test_unknown_location_number_of_known_brin(self) -> None:
        """A code that is not in DUO but whose BRIN is, becomes a sub-location of that BRIN's main location."""
        matcher = make_matcher()
        matcher.add_crm(
            [crm("1", "Basisschool voor Jong Talent", "05VW03", ("Spuiplein", 150, "", "2511DG"), bg_nummer="95694")])
        record = matcher.links[("CRM", "1")]
        assert record.kind == KIND_NEVENLOCATIE
        assert record.parent is not None and record.parent.code == "05VW00"

    def test_other_board_is_not_inherited(self) -> None:
        """A sub-location whose CRM board differs from the DUO parent keeps its own board."""
        matcher = make_matcher()
        matcher.add_crm([crm("1", "Some School", "05VW05", ("Spuiplein", 150, "", "2511DG"), bg_nummer="46879")])
        record = matcher.links[("CRM", "1")]
        assert not record.inherit
        assert "bestuur wijkt af" in record.notes[0]

    def test_no_code_is_niet_in_duo(self) -> None:
        """A CRM school without code is a non-DUO school with a note."""
        matcher = make_matcher()
        matcher.add_crm([crm("1", "Lycée Vincent van Gogh", "", ("Scheveningseweg", 237, "", "2584AA"))])
        record = matcher.links[("CRM", "1")]
        assert record.kind == KIND_NIET_IN_DUO
        assert record.notes == [NOTE_NIET_IN_DUO]

    def test_renamed_school_linked_by_code_and_address(self) -> None:
        """A school with a new name is still linked when code and address agree."""
        matcher = make_matcher()
        matcher.add_crm([crm("1", "Kindcentrum O3", "19SI00", ("De la Reyweg", 212, "", "2571GH"))])
        assert matcher.links[("CRM", "1")].kind == KIND_DUO


class TestAddPlannedCulture:
    """Tests for Matcher.add_planned_culture."""

    def test_archived_unmatched_is_excluded(self) -> None:
        """An archived Planned Culture school that matches nothing is excluded, not added."""
        matcher = make_matcher()
        matcher.add_planned_culture(
            [pc("7", "OBS Ypenburg", "26AU00", ("Bottgerwater", 21, "", "2497ZJ"), archived=True)])
        assert len(matcher.records) == 2
        assert matcher.excluded[0].reason == REASON_ARCHIVED

    def test_link_by_address_despite_other_code(self) -> None:
        """A row at a known address with a similar name is linked even if its code differs."""
        matcher = make_matcher()
        matcher.add_crm([crm("1", "De Meerpaal", "19VH02", ("Tesselsestraat", 75, "", "2583JH"))])
        matcher.add_planned_culture([pc("2", "De Meerpaal", "17RV00", ("Tesselsestraat", 75, "", "2583JH"))])
        assert matcher.links[("Planned Culture", "2")] is matcher.links[("CRM", "1")]

    def test_wrong_number_same_brin_and_postcode(self) -> None:
        """A row of the same instelling with a similar name in the same postcode is linked, not duplicated."""
        matcher = make_matcher()
        matcher.add_crm([
            crm("1", "De La Reyschool (Voorthuizenstraat)", "19SI00B", ("Voorthuizenstraat", 245, "", "2573AH")),
            crm("2", "De La Reyschool (De La Reyweg)", "19SI00A", ("De La Reyweg", 212, "", "2571GH")),
        ])
        matcher.add_planned_culture(
            [pc("2", "De la Reyschool (Voorthuizenstraat)", "19SI01", ("De la Reyweg", 212, "", "2573AH"))])
        assert matcher.links[("Planned Culture", "2")] is matcher.links[("CRM", "1")]
        assert len(matcher.records) == 3

    def test_new_school_only_in_planned_culture(self) -> None:
        """A school only Planned Culture knows becomes its own record."""
        matcher = make_matcher()
        matcher.add_planned_culture(
            [pc("3", "Deutsche Internationale Schule", "", ("Van Bleiswijkstraat", 125, "", "2582LB"))])
        assert matcher.links[("Planned Culture", "3")].kind == KIND_NIET_IN_DUO


class TestDependances:
    """Tests for dependance addresses from Planned Culture."""

    def test_dependance_creates_record(self) -> None:
        """A dependance at a new address becomes a record that inherits from the main location."""
        matcher = make_matcher()
        dependance = Address("Eksterhof", 3, "", "2496HT")
        matcher.add_planned_culture([
            pc("12", "De La Reyschool", "19SI00", ("De la Reyweg", 212, "", "2571GH"), dependances=[(dependance, "")])
        ])
        record = matcher.records[-1]
        assert record.kind == KIND_DEPENDANCE
        assert record.parent is not None and record.parent.code == "19SI00"
        assert record.name == "De La Reyschool (dependance Eksterhof)"

    def test_dependance_at_main_address_is_ignored(self) -> None:
        """A dependance that repeats the main address adds nothing."""
        matcher = make_matcher()
        same = Address("De la Reyweg", 212, "", "2571GH")
        matcher.add_planned_culture(
            [pc("12", "De La Reyschool", "19SI00", ("De la Reyweg", 212, "", "2571GH"), dependances=[(same, "")])])
        assert len(matcher.records) == 2

    def test_dependance_of_archived_school_is_ignored(self) -> None:
        """Dependances of archived schools are not added."""
        matcher = make_matcher()
        dependance = Address("Eksterhof", 3, "", "2496HT")
        matcher.add_planned_culture([
            pc("12",
               "De La Reyschool",
               "19SI00", ("De la Reyweg", 212, "", "2571GH"),
               archived=True,
               dependances=[(dependance, "")])
        ])
        assert len(matcher.records) == 2
