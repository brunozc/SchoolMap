"""Write the register workbook and the map dashboard."""
import json
import re
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from school_register.globals import (CBS_SCORE_FILES, NOTE_EXPLANATIONS, NUMERIC_COLUMNS, REGISTER_COLUMNS, SOURCE_DUO,
                                     GlobalSettings)
from school_register.register import HIGHEST_ID_LABEL, ID_SHEET, INFO_SHEET, LINK_SHEET, Correction, RegisterRow
from school_register.sources import ExcludedRow

FLAG_FILL = PatternFill("solid", fgColor="FFF2CC")
CORRECTIONS_SHEET = "Correcties CRM-PC"

SHEET_EXPLANATIONS: Dict[str, str] = {
    "Scholen":
    "Het register: één rij per schoolgebouw in 's-Gravenhage.",
    "Koppeling":
    "Welke rij uit DUO, CRM en Planned Culture bij welke UNIEK_ID hoort.",
    CORRECTIONS_SHEET:
    "Waarden in CRM of Planned Culture die volgens DUO, RIO of de BAG niet kloppen, met de juiste "
    "waarde. Deze rijen zijn in het register zeker en hebben daarom geen DATA_KWALITEIT-opmerking. "
    "Ook gebouwen die RIO bij een school registreert maar die in geen enkel bestand staan.",
    "Uitgesloten":
    "Bronregels die niet in het register staan, met de reden.",
}
HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")

COLUMN_SOURCES: Dict[str, str] = {
    "UNIEK_ID":
    "Nieuw, blijft gelijk bij een volgende run (zie 'Hoogste toegekende UNIEK_ID' onderaan).",
    "BEVOEGD_GEZAG_NUMMER":
    "DUO; bij scholen buiten DUO: CRM of de hoofdvestiging.",
    "BEVOEGD_GEZAG_NAAM":
    "DUO-bestand 'Adressen bevoegde gezagen basisonderwijs'; bij particuliere scholen in RIO: "
    "RIO; anders CRM.",
    "INSTELLINGSCODE":
    "DUO; bij scholen buiten DUO: hoofdvestiging of eerste 4 tekens van de vestigingscode.",
    "VESTIGINGSCODE":
    "DUO. Een gebouw dat RIO bij een DUO-vestiging registreert, krijgt de officiële code van die "
    "vestiging; meerdere rijen met dezelfde code zijn dus meerdere gebouwen van één school. Niet bevestigde locaties "
    "houden de code uit CRM (bijv. 05VW03) of Planned Culture.",
    "VESTIGINGSNAAM":
    "DUO; bij particuliere scholen in RIO: RIO; anders CRM, dan Planned Culture.",
    "STRAATNAAM":
    "DUO; bij scholen buiten DUO: BAG (via PDOK).",
    "HUISNUMMER-TOEVOEGING":
    "DUO; bij scholen buiten DUO: BAG (via PDOK).",
    "POSTCODE":
    "DUO; bij scholen buiten DUO: BAG (via PDOK).",
    "PLAATSNAAM":
    "DUO-spelling.",
    "GEMEENTENUMMER":
    "DUO / CBS-gemeentecode.",
    "GEMEENTENAAM":
    "DUO-spelling.",
    "DENOMINATIE":
    "DUO; bij nevenlocaties en dependances: hoofdvestiging; anders leeg.",
    "TELEFOONNUMMER":
    "DUO; bij scholen buiten DUO: CRM. Telefoonnummers van contactpersonen zijn niet gebruikt.",
    "INTERNETADRES":
    "DUO; bij scholen buiten DUO: CRM.",
    "STRAATNAAM CORRESPONDENTIEADRES":
    "DUO; bij nevenlocaties en dependances: hoofdvestiging.",
    "HUISNUMMER-TOEVOEGING CORRESPONDENTIEADRES":
    "DUO; bij nevenlocaties en dependances: hoofdvestiging.",
    "POSTCODE CORRESPONDENTIEADRES":
    "DUO; bij nevenlocaties en dependances: hoofdvestiging.",
    "PLAATSNAAM CORRESPONDENTIEADRES":
    "DUO; bij nevenlocaties en dependances: hoofdvestiging.",
    "STADSDEEL":
    "Afgeleid uit de wijk van het adres (BAG); anders CRM.",
    "WIJK":
    "CBS-wijk van het adres volgens de BAG (via PDOK).",
    "DATA_KWALITEIT":
    "Leeg = gegevens zeker (DUO, zonder tegenstrijdigheden). Anders: zie de toelichting hieronder.",
    "LATITUDE":
    "BAG (via PDOK), voor de kaart; als PDOK het adres niet vindt maar RIO het bevestigt: RIO.",
    "LONGITUDE":
    "BAG (via PDOK), voor de kaart.",
}


def __write_table(sheet: Worksheet, header: Sequence[str], rows: List[List[object]]) -> None:
    sheet.append(list(header))
    for row in rows:
        sheet.append(row)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for index, name in enumerate(header, start=1):
        longest = max([len(str(name))] + [len(str(r[index - 1])) for r in rows if r[index - 1] is not None])
        sheet.column_dimensions[get_column_letter(index)].width = min(max(10, longest + 2), 60)


def __float_or_none(text: str) -> object:
    return float(text) if text else None


def write_workbook(rows: List[RegisterRow],
                   excluded: List[ExcludedRow],
                   highest_id: int,
                   settings: GlobalSettings,
                   corrections: Optional[List[Correction]] = None) -> Path:
    """Write the register workbook: Scholen, Koppeling, Correcties CRM-PC, Uitgesloten and Toelichting.

    Args:
        rows: register rows with UNIEK_ID.
        excluded: source rows that are not in the register.
        highest_id: highest UNIEK_ID number ever assigned, stored so numbers are never reused.
        settings: build settings.
        corrections: values to fix in the CRM and Planned Culture.

    Returns:
        Path of the written workbook.
    """
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = ID_SHEET
    header = REGISTER_COLUMNS
    table = [[__float_or_none(r.values[c]) if c in NUMERIC_COLUMNS else r.values[c] for c in header] for r in rows]
    __write_table(sheet, header, table)
    quality_col = header.index("DATA_KWALITEIT") + 1
    for row_cells in sheet.iter_rows(min_row=2):
        if row_cells[quality_col - 1].value:
            for cell in row_cells:
                cell.fill = FLAG_FILL
    sheet.column_dimensions[get_column_letter(quality_col)].width = 80

    links = workbook.create_sheet(LINK_SHEET)
    link_rows: List[List[object]] = []
    for row in rows:
        uid, name, record = row.values["UNIEK_ID"], row.values["VESTIGINGSNAAM"], row.record
        if record.duo:
            link_rows.append([uid, name, SOURCE_DUO, record.code, record.name, record.code])
        for source in record.sources:
            link_rows.append([uid, name, source.source, source.source_id, source.name, source.full_code])
        if record.dependance_of is not None:
            dep = record.dependance_of
            link_rows.append([uid, name, f"{dep.source} (dependance)", dep.source_id, dep.name, record.code])
    __write_table(links, ["UNIEK_ID", "VESTIGINGSNAAM", "BRON", "BRON_ID", "NAAM_IN_BRON", "CODE_IN_BRON"], link_rows)

    fixes = workbook.create_sheet(CORRECTIONS_SHEET)
    __write_table(fixes, [
        "BRON", "BRON_ID", "NAAM_IN_BRON", "UNIEK_ID", "VELD", "WAARDE_IN_BRON", "JUISTE_WAARDE", "BRON_JUISTE_WAARDE"
    ], [[c.source, c.source_id, c.source_name, c.uid, c.field_name, c.value, c.correct, c.authority]
        for c in corrections or []])

    dropped = workbook.create_sheet("Uitgesloten")
    __write_table(dropped, ["BRON", "BRON_ID", "NAAM", "VESTIGINGSCODE", "ADRES", "REDEN"],
                  [[e.source, e.source_id, e.name, e.code, e.address, e.reason] for e in excluded])

    info = workbook.create_sheet(INFO_SHEET)
    info_rows: List[List[object]] = [
        ["Gemaakt op", date.today().isoformat()],
        [
            "Bronnen", f"{settings.duo_path.name}; {settings.crm_path.name}; {settings.pc_path.name}; "
            f"{settings.besturen_path.name} (DUO open data); "
            f"{', '.join(spec.filename for spec in CBS_SCORE_FILES)} (CBS); RIO onderwijslocaties en "
            f"vestigingen (DUO open data); BAG via PDOK Locatieserver"
        ],
        ["Scope", "Regulier basisonderwijs in de gemeente 's-Gravenhage, één rij per schoollocatie."],
        ["", ""],
        ["KOLOM", "HERKOMST"],
    ]
    sources = {**COLUMN_SOURCES, **{spec.column: spec.description for spec in CBS_SCORE_FILES}}
    info_rows += [[col, sources.get(col, "")] for col in header]
    info_rows += [["", ""], ["DATA_KWALITEIT-OPMERKING", "BETEKENIS"]]
    info_rows += [[re.sub(r"\{\w+\}", "…", note), text] for note, text in NOTE_EXPLANATIONS.items()]
    info_rows += [["", ""], ["BLADEN", ""]]
    info_rows += [[sheet_name, text] for sheet_name, text in SHEET_EXPLANATIONS.items()]
    info_rows += [["", ""], [HIGHEST_ID_LABEL, f"{settings.id_prefix}-{highest_id:0{settings.id_digits}d}"]]
    for info_row in info_rows:
        info.append(info_row)
    for label_row in (5, 6 + len(header) + 1):
        for cell in info[label_row]:
            cell.font = Font(bold=True)
    info.column_dimensions["A"].width = 48
    info.column_dimensions["B"].width = 110
    for row_cells in info.iter_rows():
        for cell in row_cells:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    workbook.save(settings.xlsx_path)
    return settings.xlsx_path


def write_dashboard(rows: List[RegisterRow], settings: GlobalSettings) -> Path:
    """Write the single-file map dashboard with the register embedded as JSON.

    Args:
        rows: register rows with UNIEK_ID.
        settings: build settings.

    Returns:
        Path of the written dashboard.
    """
    template = resources.files("school_register").joinpath("dashboard_template.html").read_text(encoding="utf-8")
    columns = REGISTER_COLUMNS
    data = {"columns": columns, "rows": [[r.values[c] for c in columns] for r in rows]}
    # "</" must not appear inside the inline script, or a school name could end the script block early
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("/*__DATA__*/null", payload).replace("__DATASET_NAME__", settings.xlsx_path.name)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.dashboard_path.write_text(html, encoding="utf-8")
    return settings.dashboard_path
