"""Constants and user-tunable settings for the school register."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# output columns, in the order requested; names mirror the DUO export where one exists
OUTPUT_COLUMNS: List[str] = [
    "UNIEK_ID",
    "BEVOEGD_GEZAG_NUMMER",
    "BEVOEGD_GEZAG_NAAM",
    "INSTELLINGSCODE",
    "VESTIGINGSCODE",
    "VESTIGINGSNAAM",
    "STRAATNAAM",
    "HUISNUMMER-TOEVOEGING",
    "POSTCODE",
    "PLAATSNAAM",
    "GEMEENTENUMMER",
    "GEMEENTENAAM",
    "DENOMINATIE",
    "TELEFOONNUMMER",
    "INTERNETADRES",
    "STRAATNAAM CORRESPONDENTIEADRES",
    "HUISNUMMER-TOEVOEGING CORRESPONDENTIEADRES",
    "POSTCODE CORRESPONDENTIEADRES",
    "PLAATSNAAM CORRESPONDENTIEADRES",
    "STADSDEEL",
    "WIJK",
    "DATA_KWALITEIT",
]
COORDINATE_COLUMNS: List[str] = ["LATITUDE", "LONGITUDE"]


@dataclass(frozen=True)
class CbsScoreFile:
    """One CBS table set with achterstandsscores per basisschoolvestiging.

    Attributes:
        column: output column that receives the score.
        label: year label used in notes, e.g. "2025".
        url: download URL of the CBS xlsx.
        filename: name of the cached copy in the external data directory.
        description: where the score comes from, for the Toelichting sheet.
    """
    column: str
    label: str
    url: str
    filename: str
    description: str


# the funded score "met drempel" (CBS table 1) is used, the same variant the CRM holds for 2022-2024
CBS_SCORE_FILES: List[CbsScoreFile] = [
    CbsScoreFile(column="ACHTERSTANDSSCORE_2025",
                 label="2025",
                 url="https://www.cbs.nl/-/media/_excel/2026/05/achterstandsscores_scholen_2025_schoolfusie.xlsx",
                 filename="achterstandsscores_scholen_2025_schoolfusie.xlsx",
                 description="CBS, achterstandsscore met drempel per basisschoolvestiging op 1 februari 2025, "
                 "definitief na bezwaren en fusies (gepubliceerd januari 2026). Basis voor de huidige bekostiging. "
                 "Alleen bij DUO-vestigingen; de score van een hoofdvestiging omvat ook haar nevenlocaties."),
    CbsScoreFile(column="ACHTERSTANDSSCORE_2026_VOORLOPIG",
                 label="2026 (voorlopig)",
                 url="https://www.cbs.nl/-/media/_excel/2026/29/achterstandsscores_scholen_2026_vrl.xlsx",
                 filename="achterstandsscores_scholen_2026_vrl.xlsx",
                 description="CBS, voorlopige achterstandsscore met drempel op 1 februari 2026 (gepubliceerd juli "
                 "2026), berekend met de herijkte methode: andere schaal, niet één op één vergelijkbaar met 2025. "
                 "Alleen bij DUO-vestigingen."),
]
SCORE_COLUMNS: List[str] = [f.column for f in CBS_SCORE_FILES]
# columns written to the workbook as numbers instead of text
NUMERIC_COLUMNS: List[str] = SCORE_COLUMNS + COORDINATE_COLUMNS
# every column of the register sheet and the dashboard, in order
REGISTER_COLUMNS: List[str] = OUTPUT_COLUMNS + SCORE_COLUMNS + COORDINATE_COLUMNS

# DUO column names differ from the output names for the bevoegd gezag number only
DUO_TO_OUTPUT: Dict[str, str] = {"BEVOEGD GEZAG NUMMER": "BEVOEGD_GEZAG_NUMMER"}
DUO_COPIED_COLUMNS: List[str] = [
    "BEVOEGD GEZAG NUMMER",
    "INSTELLINGSCODE",
    "VESTIGINGSCODE",
    "VESTIGINGSNAAM",
    "STRAATNAAM",
    "HUISNUMMER-TOEVOEGING",
    "POSTCODE",
    "PLAATSNAAM",
    "GEMEENTENUMMER",
    "GEMEENTENAAM",
    "DENOMINATIE",
    "TELEFOONNUMMER",
    "INTERNETADRES",
    "STRAATNAAM CORRESPONDENTIEADRES",
    "HUISNUMMER-TOEVOEGING CORRESPONDENTIEADRES",
    "POSTCODE CORRESPONDENTIEADRES",
    "PLAATSNAAM CORRESPONDENTIEADRES",
]
# fields a sub-location inherits from its main location
INHERITED_COLUMNS: List[str] = [
    "BEVOEGD_GEZAG_NUMMER",
    "BEVOEGD_GEZAG_NAAM",
    "INSTELLINGSCODE",
    "DENOMINATIE",
    "STRAATNAAM CORRESPONDENTIEADRES",
    "HUISNUMMER-TOEVOEGING CORRESPONDENTIEADRES",
    "POSTCODE CORRESPONDENTIEADRES",
    "PLAATSNAAM CORRESPONDENTIEADRES",
]

DUO_BESTUREN_URL = ("https://onderwijsdata.duo.nl/dataset/786f12ea-6224-42fd-ab72-de4d7d879535/resource/"
                    "d06cc759-ec8c-4430-91ad-14631b6c7bed/download/besturenbo.csv")
PDOK_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
# RIO (Register Instellingen en Opleidingen) on DUO open data: physical school buildings and their school codes; the
# file URLs are looked up by name through the CKAN API, because DUO refreshes the files daily
RIO_PACKAGE_URL = "https://onderwijsdata.duo.nl/api/3/action/package_show?id=rio_nfo_po_vo_vavo_mbo_ho"
RIO_FILES: List[str] = [
    "onderwijslocaties",
    "relaties_onderwijslocatiegebruiken_vestigingserkenningen",
    "vestigingserkenningen",
    "relaties_onderwijsinstellingserkenningen_vestigingserkenningen",
    "relaties_bevoegdgezagerkenningen_onderwijsinstellingserkenningen",
    "bevoegd_gezag_erkenningen",
]

# DUO spelling of the municipality, used for both filtering and output
GEMEENTE_CODE = "0518"
DUO_GEMEENTENAAM = "S GRAVENHAGE"
DUO_PLAATSNAAM = "'S-GRAVENHAGE"

# record kinds
KIND_DUO = "DUO"
KIND_NEVENLOCATIE = "NEVENLOCATIE"
KIND_DEPENDANCE = "DEPENDANCE"
KIND_NIET_IN_DUO = "NIET_IN_DUO"

SOURCE_CRM = "CRM"
SOURCE_PC = "Planned Culture"
SOURCE_DUO = "DUO"
SOURCE_RIO = "RIO"

# DATA_KWALITEIT note texts; placeholders are filled with str.format
NOTE_NIET_IN_DUO = "Niet in DUO of RIO (buitenlandse of particuliere school); gegevens uit CRM/Planned Culture"
NOTE_RIO_NOT_CONFIRMED = "Locatie niet bevestigd door RIO (mogelijk niet meer in gebruik)"
NOTE_RIO_BUILDING_OF = "Volgens RIO is dit gebouw van {schools}"
NOTE_RIO_OTHER_BUILDING = "Volgens RIO is het lesgebouw van {code}: {addresses}; dit adres staat niet in RIO"
NOTE_RIO_NO_BUILDING = "Adres niet bevestigd door RIO (geen lesgebouw geregistreerd voor {code})"
NOTE_RIO_UNLISTED = "RIO-gebouwen van {code} die niet in dit register staan: {addresses}"
NOTE_NEVENLOCATIE = ("Nevenlocatie van {parent}, niet apart in DUO; bestuur, denominatie en correspondentieadres "
                     "overgenomen van hoofdvestiging")
NOTE_NEVENLOCATIE_EIGEN_BESTUUR = ("Code lijkt op {parent} maar bestuur wijkt af; bestuur uit CRM, vestigingscode "
                                   "mogelijk onjuist")
NOTE_DEPENDANCE = ("Dependance uit Planned Culture, niet apart in DUO; bestuur, denominatie en correspondentieadres "
                   "overgenomen van hoofdlocatie")
NOTE_CODE_CONFLICT = "Vestigingscode verschilt tussen bronnen: {codes}"
NOTE_ADDRESS_CONFLICT = "Adres verschilt tussen bronnen: {addresses}"
NOTE_NOT_IN_BAG = "Adres niet gevonden in BAG; kaartlocatie is benadering op postcode"
NOTE_NO_LOCATION = "Adres niet gevonden in BAG; geen kaartlocatie"
NOTE_BG_NOT_FROM_DUO = "Naam bevoegd gezag uit CRM, niet gevonden in DUO"
NOTE_ARCHIVED = "Gearchiveerd in Planned Culture"
NOTE_ONLY_PC = "Alleen in Planned Culture (niet in CRM)"
NOTE_PHONE_INVALID = "Telefoonnummer uit CRM is ongeldig (overgenomen zoals het er staat)"
NOTE_SCORE_UNRELIABLE = "Achterstandsscore CBS {year} onbetrouwbaar (40 of minder leerlingen)"
NOTE_SCORE_MISSING = "Geen CBS-achterstandsscore {year} gevonden voor deze DUO-vestiging"

NOTE_EXPLANATIONS: Dict[str, str] = {
    NOTE_NIET_IN_DUO: "De school staat niet in DUO en niet in RIO (bijv. een buitenlandse of weekendschool). Naam en "
    "contactgegevens komen uit CRM/Planned Culture; het adres bestaat wel in de BAG.",
    NOTE_RIO_NOT_CONFIRMED:
    "RIO kent dit adres niet als lesgebouw van deze school; de locatie kan gesloten of verhuisd "
    "zijn. Controleer bij de school.",
    NOTE_RIO_BUILDING_OF:
    "RIO registreert dit gebouw bij een andere school (bijv. een gedeeld gebouw of een fout in de "
    "bron).",
    NOTE_RIO_OTHER_BUILDING: "DUO/CRM en RIO noemen verschillende gebouwen; het adres in het register is niet "
    "aangepast.",
    NOTE_RIO_NO_BUILDING: "De school staat in RIO, maar zonder geregistreerd lesgebouw.",
    NOTE_RIO_UNLISTED: "Deze gebouwen horen volgens RIO bij dezelfde DUO-vestiging; mogelijk is de school daarheen "
    "verhuisd.",
    NOTE_NEVENLOCATIE: "Locatie die in CRM/Planned Culture apart staat, maar in DUO onder de hoofdvestiging valt.",
    NOTE_NEVENLOCATIE_EIGEN_BESTUUR: "De vestigingscode wijst naar een DUO-school met een ander bestuur; de code in "
    "CRM is waarschijnlijk zelf bedacht of onjuist.",
    NOTE_DEPENDANCE: "Extra adres (dependance) van een school, alleen bekend in Planned Culture.",
    NOTE_CODE_CONFLICT: "CRM, Planned Culture en/of DUO gebruiken verschillende vestigingscodes voor deze locatie.",
    NOTE_ADDRESS_CONFLICT: "De bronnen geven verschillende adressen; het eerste adres (DUO, anders CRM) is gebruikt.",
    NOTE_NOT_IN_BAG: "Het adres bestaat niet in de BAG; de kaartstip staat op het midden van de postcode.",
    NOTE_NO_LOCATION: "Adres en postcode niet gevonden in de BAG; de school staat niet op de kaart.",
    NOTE_BG_NOT_FROM_DUO: "Het bestuursnummer staat niet in het DUO-bestand met besturen.",
    NOTE_ARCHIVED: "De school is in Planned Culture gearchiveerd; mogelijk gesloten of verhuisd.",
    NOTE_ONLY_PC: "De school komt alleen in Planned Culture voor.",
    NOTE_PHONE_INVALID: "Het telefoonnummer in CRM heeft geen 10 cijfers; controleer het nummer.",
    NOTE_SCORE_UNRELIABLE: "Het CBS markeert de score met \"a\": te weinig leerlingen voor een betrouwbare score.",
    NOTE_SCORE_MISSING:
    "De vestigingscode staat niet in de CBS-tabel van dat jaar, bijv. een nieuwe of gefuseerde school.",
}

# words that carry no identity when comparing school names
GENERIC_NAME_TOKENS = frozenset({
    "basisschool", "bs", "obs", "rkbs", "rk", "pcbs", "pcb", "cbs", "pc", "kc", "ikc", "kindcentrum", "school", "de",
    "het", "t", "van", "den", "der", "openbare", "christelijke", "christelijk", "protestants", "katholieke", "rooms",
    "po", "ibs", "islamitische", "basis", "onderwijs", "basisonderwijs", "bao", "en", "voor", "in", "the", "of",
    "stichting", "a", "d", "ds", "e", "g", "o"
})

# Den Haag wijk (CBS wijkcode, as returned by PDOK) -> stadsdeel. Derived from the CRM stadsdeel of the schools in
# each wijk (unanimous or a clear majority per wijk) and consistent with the stadsdeel indeling on
# denhaag.nl/stadsdelen. Only wijken that contain a school are listed; a school in an unlisted wijk keeps its CRM
# stadsdeel.
WIJK_STADSDEEL: Dict[str, str] = {
    "WK051802": "Scheveningen",  # Belgisch Park
    "WK051803": "Scheveningen",  # Westbroekpark en Duttendel
    "WK051804": "Haagse Hout",  # Benoordenhout
    "WK051805": "Centrum",  # Archipelbuurt
    "WK051807": "Scheveningen",  # Scheveningen
    "WK051808": "Scheveningen",  # Duindorp
    "WK051809": "Scheveningen",  # Geuzen- en Statenkwartier
    "WK051810": "Scheveningen",  # Zorgvliet
    "WK051811": "Scheveningen",  # Duinoord
    "WK051812": "Segbroek",  # Bomen- en Bloemenbuurt
    "WK051813": "Segbroek",  # Vogelwijk
    "WK051814": "Loosduinen",  # Bohemen en Meer en Bos
    "WK051815": "Loosduinen",  # Kijkduin en Ockenburgh
    "WK051816": "Loosduinen",  # Kraayenstein en Vroondaal
    "WK051817": "Loosduinen",  # Loosduinen
    "WK051818": "Loosduinen",  # Waldeck
    "WK051819": "Segbroek",  # Vruchtenbuurt
    "WK051820": "Segbroek",  # Valkenboskwartier
    "WK051821": "Segbroek",  # Regentessekwartier
    "WK051822": "Centrum",  # Zeeheldenkwartier
    "WK051823": "Centrum",  # Willemspark
    "WK051825": "Haagse Hout",  # Mariahoeve en Marlot
    "WK051826": "Haagse Hout",  # Bezuidenhout
    "WK051827": "Centrum",  # Stationsbuurt
    "WK051828": "Centrum",  # Centrum
    "WK051829": "Centrum",  # Schildersbuurt
    "WK051830": "Centrum",  # Transvaalkwartier
    "WK051831": "Escamp",  # Rustenburg en Oostbroek
    "WK051832": "Escamp",  # Leyenburg
    "WK051833": "Escamp",  # Bouwlust
    "WK051834": "Escamp",  # Morgenstond
    "WK051836": "Escamp",  # Moerwijk
    "WK051837": "Centrum",  # Groente- en Fruitmarkt
    "WK051838": "Laak",  # Laakkwartier en Spoorwijk
    "WK051839": "Laak",  # Binckhorst
    "WK051840": "Escamp",  # Wateringse Veld
    "WK051842": "Leidschenveen-Ypenburg",  # Ypenburg
    "WK051844": "Leidschenveen-Ypenburg",  # Leidschenveen
}


@dataclass
class GlobalSettings:
    """User-tunable settings for building the register.

    Attributes:
        id_prefix: prefix of every UNIEK_ID, followed by a dash and a zero-padded number.
        id_digits: number of digits in the numeric part of UNIEK_ID.
        name_similarity: minimum difflib ratio for two normalised school names to count as the same school.
        rio_same_building_m: a RIO building of the same school within this distance of a BAG address counts as the
            same building, e.g. a corner building with entrances on two streets [m].
        data_dir: directory with the three input files.
        cache_dir: directory for the PDOK geocoding cache.
        external_dir: directory where downloaded DUO reference files are stored.
        output_dir: directory where the xlsx and dashboard are written.
    """
    id_prefix: str = "DH"
    id_digits: int = 4
    name_similarity: float = 0.75
    rio_same_building_m: float = 75.0
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    cache_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "cache")
    external_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "external")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")

    @property
    def duo_path(self) -> Path:
        """Path of the DUO export of all basisonderwijs locations."""
        return self.data_dir / "DUO_02-alle-schoolvestigingen-basisonderwijs.xlsx"

    @property
    def crm_path(self) -> Path:
        """Path of the CRM export."""
        return self.data_dir / "CRM_Export.xlsx"

    @property
    def pc_path(self) -> Path:
        """Path of the Planned Culture export."""
        return self.data_dir / "Planned_Culture.csv"

    @property
    def rio_dir(self) -> Path:
        """Directory with the cached RIO files."""
        return self.external_dir / "rio"

    @property
    def cbs_dir(self) -> Path:
        """Directory with the cached CBS achterstandsscores workbooks."""
        return self.external_dir / "cbs"

    @property
    def besturen_path(self) -> Path:
        """Path of the cached DUO bevoegde gezagen file."""
        return self.external_dir / "besturenbo.csv"

    @property
    def pdok_cache_path(self) -> Path:
        """Path of the PDOK geocoding cache."""
        return self.cache_dir / "pdok.json"

    @property
    def xlsx_path(self) -> Path:
        """Path of the output register."""
        return self.output_dir / "scholen_den_haag.xlsx"

    @property
    def dashboard_path(self) -> Path:
        """Path of the output dashboard."""
        return self.output_dir / "dashboard.html"
