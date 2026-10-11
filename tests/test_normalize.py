"""Tests for school_register.normalize."""
import pytest

from school_register.normalize import (Address, format_house_number, format_postcode, is_den_haag, names_similar,
                                       normalize_phone, normalize_postcode, normalize_website, parse_address_line,
                                       parse_split_address, split_code)


class TestSplitCode:
    """Tests for split_code."""

    def test_plain_code(self) -> None:
        """A DUO code has no suffix."""
        assert split_code("27PC00") == ("27PC00", "")

    def test_crm_letter_suffix(self) -> None:
        """A CRM letter suffix is split off and upper-cased."""
        assert split_code(" 18pq00a ") == ("18PQ00", "A")

    @pytest.mark.parametrize("raw", ["", None, "Test", "05VW", "1234AB"])
    def test_invalid_code(self, raw: object) -> None:
        """Anything that is not a vestigingscode gives empty strings."""
        assert split_code(raw) == ("", "")


class TestPostcode:
    """Tests for normalize_postcode and format_postcode."""

    @pytest.mark.parametrize("raw", ["2525 GG", "2525gg", " 2525  GG "])
    def test_normalize(self, raw: str) -> None:
        """Spacing and case are normalised."""
        assert normalize_postcode(raw) == "2525GG"

    def test_invalid(self) -> None:
        """A non-postcode gives an empty string."""
        assert normalize_postcode("Den Haag") == ""

    def test_format(self) -> None:
        """Postcodes are written the DUO way, with a space."""
        assert format_postcode("2525GG") == "2525 GG"


class TestParseAddressLine:
    """Tests for parse_address_line."""

    def test_double_space(self) -> None:
        """The CRM often has two spaces before the number."""
        address = parse_address_line("Terwestenstraat  105", "2525 GG")
        assert address == Address("Terwestenstraat", 105, "", "2525GG")

    def test_house_letter(self) -> None:
        """A house letter directly after the number is the addition."""
        address = parse_address_line("Koningin Sophiestraat  24a", "2595 TG")
        assert (address.street, address.number, address.addition) == ("Koningin Sophiestraat", 24, "A")

    def test_street_with_digit(self) -> None:
        """A digit inside the street name is not the house number."""
        address = parse_address_line("2e Messstraat 31", "2586XA")
        assert (address.street, address.number) == ("2e Messstraat", 31)

    def test_no_number(self) -> None:
        """Without a number the whole line is the street."""
        address = parse_address_line("Prinsegracht", "2512GG")
        assert address.number is None
        assert address.key is None


class TestParseSplitAddress:
    """Tests for parse_split_address."""

    def test_separate_fields(self) -> None:
        """Street, number and addition fields are combined."""
        address = parse_split_address("Maarsbergenstraat", "169", "C", "2546 SP")
        assert address == Address("Maarsbergenstraat", 169, "C", "2546SP")

    def test_brin_code_in_number_field(self) -> None:
        """A BRIN code in the number field is ignored and the number is taken from the street field."""
        address = parse_split_address("Ambachtsgaarde 1", "19NZ", "", "2542 ED")
        assert (address.street, address.number) == ("Ambachtsgaarde", 1)

    def test_duo_range(self) -> None:
        """A DUO number range keeps the end of the range as addition."""
        address = parse_split_address("Rijslag", "17-23", "", "2587 BB")
        assert address.number_range == (17, 23)
        assert format_house_number(address.number, address.addition) == "17-23"


class TestSamePlace:
    """Tests for Address.same_place."""

    def test_number_inside_range(self) -> None:
        """A number inside a DUO range is the same building."""
        duo = Address("Rijslag", 17, "23", "2587BB")
        crm = Address("Rijslag", 21, "", "2587BB")
        assert duo.same_place(crm)
        assert crm.same_place(duo)

    def test_letter_ignored(self) -> None:
        """A house letter does not make a different building."""
        assert Address("Diamanthorst", 181, "A", "2592GD").same_place(Address("Diamanthorst", 181, "", "2592GD"))

    def test_different_postcode(self) -> None:
        """The same number in another postcode is a different place."""
        assert not Address("Diamanthorst", 181, "", "2592GD").same_place(Address("Diamanthorst", 181, "", "2592GH"))

    def test_missing_number(self) -> None:
        """An address without number never matches."""
        assert not Address("Prinsegracht", None, "", "2512GG").same_place(Address("Prinsegracht", None, "", "2512GG"))


class TestNamesSimilar:
    """Tests for names_similar."""

    def test_short_name_inside_duo_name(self) -> None:
        """The short CRM name is contained in the formal DUO name."""
        assert names_similar("De Parkiet", "Rooms Katholieke Basisschool De Parkiet", 0.75)

    def test_school_suffix(self) -> None:
        """A school name written as one word matches the split form."""
        assert names_similar("Da Costaschool", "Da Costa School Christelijke Basisonderwijs", 0.75)

    def test_different_schools(self) -> None:
        """Different schools do not match."""
        assert not names_similar("De Parkiet", "Willem de Zwijgerschool", 0.75)

    def test_only_generic_words(self) -> None:
        """Names made of generic words only never match."""
        assert not names_similar("Basisschool", "OBS", 0.75)


class TestContactDetails:
    """Tests for normalize_phone and normalize_website."""

    @pytest.mark.parametrize("raw", ["+31 (0) 703887915", "070-3887915", "0031703887915"])
    def test_phone(self, raw: str) -> None:
        """Dutch numbers become ten digits with a leading zero."""
        assert normalize_phone(raw) == "0703887915"

    def test_repeated_country_prefix(self) -> None:
        """A country prefix that the CRM repeats is dropped twice."""
        assert normalize_phone("+31 (0) +31 (0)70 354 94 54") == "0703549454"

    def test_invalid_phone_kept(self) -> None:
        """A number with the wrong digit count is kept as written, so it can be flagged."""
        assert normalize_phone("+31 (0) 70361 17 017") == "+31 (0) 70361 17 017"

    def test_website(self) -> None:
        """Scheme and trailing slash are dropped."""
        assert normalize_website("https://www.Al-Qoeba.nl/") == "www.al-qoeba.nl"


class TestIsDenHaag:
    """Tests for is_den_haag."""

    @pytest.mark.parametrize("raw",
                             ["Den Haag", "den  haag", "Den-Haag", "'s-Gravenhage", "'S-GRAVENHAGE", "The Hague"])
    def test_spellings(self, raw: str) -> None:
        """All usual spellings are recognised."""
        assert is_den_haag(raw)

    @pytest.mark.parametrize("raw", ["Rijswijk", "Voorburg", "Test", ""])
    def test_other_places(self, raw: str) -> None:
        """Other places are not Den Haag."""
        assert not is_den_haag(raw)
