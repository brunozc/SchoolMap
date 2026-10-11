"""Normalisation of codes, addresses, names and contact details from the source files."""
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from school_register.globals import GENERIC_NAME_TOKENS

_CODE_RE = re.compile(r"^([0-9]{2}[A-Z]{2}[0-9]{2})([A-Z]?)$")
_POSTCODE_RE = re.compile(r"^([1-9][0-9]{3})\s*([A-Za-z]{2})$")
# street, house number, optional addition (letter, "-a", "a", "-2", "bis"); the street may contain digits ("2e")
_ADDRESS_LINE_RE = re.compile(r"^(?P<street>.*?\D)\s+(?P<number>\d+)\s*[-/]?\s*(?P<addition>[A-Za-z0-9]{0,4})\s*$")


@dataclass(frozen=True)
class Address:
    """A street address split into its parts.

    Attributes:
        street: street name.
        number: house number.
        addition: house letter or addition, upper case, empty if none.
        postcode: postcode without space, upper case ("2525GG").
    """
    street: str
    number: Optional[int]
    addition: str
    postcode: str

    @property
    def key(self) -> Optional[str]:
        """Postcode plus house number, the key used to compare addresses between sources."""
        if not self.postcode or self.number is None:
            return None
        return f"{self.postcode}-{self.number}"

    @property
    def number_range(self) -> Optional[Tuple[int, int]]:
        """First and last house number, so that "17-23" covers 17 up to and including 23."""
        if self.number is None:
            return None
        if self.addition.isdigit() and int(self.addition) > self.number:
            return self.number, int(self.addition)
        return self.number, self.number

    def same_place(self, other: "Address") -> bool:
        """Check whether two addresses point to the same building: same postcode and overlapping house numbers.

        Args:
            other: address to compare with.

        Returns:
            True if the postcodes are equal and the house number ranges overlap.
        """
        first, second = self.number_range, other.number_range
        if not self.postcode or self.postcode != other.postcode or first is None or second is None:
            return False
        return first[0] <= second[1] and second[0] <= first[1]

    def label(self) -> str:
        """Human-readable address for notes, e.g. "Mackaystraat 6 (2571AR)"."""
        number = "" if self.number is None else f" {self.number}{('-' + self.addition) if self.addition else ''}"
        return f"{self.street}{number} ({self.postcode})"


def clean(value: object) -> str:
    """Turn a cell value into a stripped string; missing values become an empty string.

    Args:
        value: raw cell value from pandas.

    Returns:
        The stripped string, with internal runs of whitespace collapsed.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def split_code(raw: object) -> Tuple[str, str]:
    """Split a vestigingscode into the 6-character DUO code and an optional letter suffix.

    The CRM marks extra buildings that share one DUO code with a letter, e.g. "05VW00B".

    Args:
        raw: the code as written in a source file.

    Returns:
        The DUO-style base code and the suffix letter; both are empty if the value is not a valid code.
    """
    code = re.sub(r"\s", "", clean(raw)).upper()
    match = _CODE_RE.match(code)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def normalize_postcode(raw: object) -> str:
    """Normalise a Dutch postcode to "1234AB".

    Args:
        raw: postcode in any spacing or case.

    Returns:
        The postcode without space and upper case, or an empty string if it is not a valid postcode.
    """
    match = _POSTCODE_RE.match(clean(raw))
    if not match:
        return ""
    return f"{match.group(1)}{match.group(2).upper()}"


def format_postcode(postcode: str) -> str:
    """Format a normalised postcode the DUO way, "1234 AB".

    Args:
        postcode: postcode as returned by normalize_postcode.

    Returns:
        The postcode with a space, or the input unchanged if it is not normalised.
    """
    if len(postcode) == 6:
        return f"{postcode[:4]} {postcode[4:]}"
    return postcode


def parse_house_number(raw_number: object, raw_addition: object = "") -> Tuple[Optional[int], str]:
    """Split a house number field into its number and addition.

    Args:
        raw_number: house number, possibly with an addition ("24a", "85-a", "76-78").
        raw_addition: separate addition field, if the source has one.

    Returns:
        The house number (None if there is no number) and the addition in upper case.
    """
    text = clean(raw_number)
    match = re.match(r"^(\d+)\s*[-/]?\s*([A-Za-z0-9]*)", text)
    if not match:
        return None, clean(raw_addition).upper()
    addition = clean(raw_addition) or match.group(2)
    return int(match.group(1)), addition.upper()


def parse_address_line(line: object, postcode: object) -> Address:
    """Parse a single address line such as "Terwestenstraat  105" or "Koningin Sophiestraat  24a".

    Args:
        line: street and house number in one field.
        postcode: postcode belonging to the address.

    Returns:
        The parsed address; the number is None if no house number could be found.
    """
    text = clean(line)
    match = _ADDRESS_LINE_RE.match(text)
    if not match:
        return Address(street=text, number=None, addition="", postcode=normalize_postcode(postcode))
    return Address(street=match.group("street").strip(),
                   number=int(match.group("number")),
                   addition=match.group("addition").upper(),
                   postcode=normalize_postcode(postcode))


def parse_split_address(street: object, number: object, addition: object, postcode: object) -> Address:
    """Build an address from separate street, number and addition fields.

    Planned Culture sometimes puts the number in the street field ("Ieplaan 85-a") or junk in the number field, so
    the street field is parsed as a full line when the number field does not start with a digit.

    Args:
        street: street name field.
        number: house number field.
        addition: house number addition field.
        postcode: postcode field.

    Returns:
        The parsed address.
    """
    number_text = clean(number)
    # "24", "24a", "85-a", "76-78"; anything else (e.g. a BRIN code "19NZ") is not a house number, and then the number
    # is usually at the end of the street field ("Ambachtsgaarde 1")
    if not re.fullmatch(r"\d+\s*[-/]?\s*[A-Za-z]?\d{0,3}", number_text):
        return parse_address_line(street, postcode)
    parsed_number, parsed_addition = parse_house_number(number_text, addition)
    return Address(street=clean(street),
                   number=parsed_number,
                   addition=parsed_addition,
                   postcode=normalize_postcode(postcode))


def format_house_number(number: Optional[int], addition: str) -> str:
    """Format a house number the DUO way: "103", "103-A".

    Args:
        number: house number.
        addition: house letter or addition.

    Returns:
        The formatted house number, or an empty string if there is no number.
    """
    if number is None:
        return ""
    return f"{number}-{addition}" if addition else str(number)


def normalize_phone(raw: object) -> str:
    """Normalise a phone number to the DUO format, digits only with a leading zero ("0703887915").

    Args:
        raw: phone number in any format, e.g. "+31 (0) 703887915".

    Returns:
        The normalised number, or the stripped input if it does not look like a Dutch number.
    """
    text = clean(raw)
    # drop every country prefix, also when the CRM repeats it ("+31 (0) +31 (0)70 ...")
    digits = re.sub(r"\D", "", re.sub(r"\+31|^0031|\(0\)", " ", text))
    if len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    if is_valid_phone(digits):
        return digits
    return text


def is_valid_phone(phone: str) -> bool:
    """Check whether a phone number is in the DUO format, ten digits starting with zero.

    Args:
        phone: phone number.

    Returns:
        True for a valid Dutch number in DUO format.
    """
    return bool(re.fullmatch(r"0\d{9}", phone))


def normalize_website(raw: object) -> str:
    """Normalise a website to the DUO style, without scheme and trailing slash.

    Args:
        raw: website as written in the source.

    Returns:
        The normalised website, lower case.
    """
    text = clean(raw).lower()
    text = re.sub(r"^https?://", "", text)
    return text.rstrip("/")


def strip_accents(text: str) -> str:
    """Remove diacritics, e.g. "Lycée" becomes "Lycee".

    Args:
        text: any text.

    Returns:
        The text without combining characters.
    """
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def name_tokens(name: str) -> List[str]:
    """Split a school name into its distinctive tokens, dropping generic words like "basisschool".

    Args:
        name: school name.

    Returns:
        Lower-case tokens without generic words or punctuation.
    """
    text = strip_accents(name).lower().replace("'", "")
    tokens = re.split(r"[^a-z0-9]+", text)
    # "Da Costaschool" and "Da Costa School" should compare equal
    tokens = [t[:-6] if t.endswith("school") and len(t) > 8 else t for t in tokens]
    return [t for t in tokens if t and t not in GENERIC_NAME_TOKENS]


def names_similar(first: str, second: str, threshold: float) -> bool:
    """Decide whether two school names refer to the same school.

    Names match when the distinctive tokens of one are contained in the other ("De Parkiet" and "Rooms Katholieke
    Basisschool De Parkiet"), or when their difflib ratio reaches the threshold.

    Args:
        first: first school name.
        second: second school name.
        threshold: minimum difflib ratio, between 0 and 1.

    Returns:
        True if the names are considered the same school.
    """
    tokens_a, tokens_b = name_tokens(first), name_tokens(second)
    if not tokens_a or not tokens_b:
        return False
    set_a, set_b = set(tokens_a), set(tokens_b)
    if set_a <= set_b or set_b <= set_a:
        return True
    return SequenceMatcher(None, " ".join(tokens_a), " ".join(tokens_b)).ratio() >= threshold


def name_similarity(first: str, second: str) -> float:
    """Score how similar two school names are, for picking the best of several candidates.

    Args:
        first: first school name.
        second: second school name.

    Returns:
        A ratio between 0 and 1.
    """
    return SequenceMatcher(None, " ".join(name_tokens(first)), " ".join(name_tokens(second))).ratio()


def normalized_name(name: str) -> str:
    """Return a canonical form of a school name, used as part of the UNIEK_ID matching key.

    Args:
        name: school name.

    Returns:
        The distinctive tokens joined by spaces.
    """
    return " ".join(name_tokens(name))


def is_den_haag(plaats: object) -> bool:
    """Check whether a place name refers to Den Haag ('s-Gravenhage, The Hague, ...).

    Args:
        plaats: place name in any spelling.

    Returns:
        True for any of the usual spellings of Den Haag.
    """
    text = re.sub(r"[^a-z]", "", strip_accents(clean(plaats)).lower())
    return text in {"denhaag", "sgravenhage", "thehague", "gravenhage"}
