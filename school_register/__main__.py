"""Build the Den Haag school register and dashboard: ``python -m school_register``."""
from collections import Counter

from school_register.export import write_dashboard, write_workbook
from school_register.geocode import PdokGeocoder
from school_register.globals import GlobalSettings
from school_register.matching import Matcher
from school_register.register import (assign_ids, build_rows, collect_corrections, geocode_records, read_previous_ids)
from school_register.rio import apply_rio, load_rio
from school_register.sources import load_besturen, load_cbs_scores, load_crm, load_duo, load_planned_culture


def main() -> None:
    """Run the full pipeline and print a summary."""
    settings = GlobalSettings()
    duo = load_duo(settings)
    besturen = load_besturen(settings)
    scores = load_cbs_scores(settings)
    rio = load_rio(settings)
    crm_rows, crm_excluded = load_crm(settings)
    pc_rows, pc_excluded = load_planned_culture(settings)

    matcher = Matcher(duo, settings)
    matcher.add_crm(crm_rows)
    matcher.add_planned_culture(pc_rows)

    geocoder = PdokGeocoder(settings.pdok_cache_path)
    records, outside = geocode_records(matcher.records, geocoder)
    excluded = crm_excluded + pc_excluded + matcher.excluded + outside
    unlisted = apply_rio(records, rio, settings.rio_same_building_m)

    rows = build_rows(records, besturen, scores)
    previous, highest = read_previous_ids(settings.xlsx_path)
    rows, highest = assign_ids(rows, previous, highest, settings)
    corrections = collect_corrections(rows, unlisted)
    xlsx = write_workbook(rows, excluded, highest, settings, corrections)
    dashboard = write_dashboard(rows, settings)

    kinds = Counter(r.record.kind for r in rows)
    flagged = sum(1 for r in rows if r.values["DATA_KWALITEIT"])
    print(f"DUO-locaties in 's-Gravenhage: {len(duo)}")
    print(f"Register: {len(rows)} locaties " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    print(f"Met DATA_KWALITEIT-opmerking: {flagged}")
    confirmed = sum(1 for r in rows if r.record.address_confirmed)
    print(f"Adres bevestigd door RIO: {confirmed}")
    print(f"Correcties voor CRM/Planned Culture: {len(corrections)} " +
          ", ".join(f"{k}={v}" for k, v in Counter(c.field_name for c in corrections).most_common()))
    print(f"Uitgesloten bronregels: {len(excluded)}")
    for reason, count in Counter(e.reason for e in excluded).most_common():
        print(f"  {count:3d}  {reason}")
    print(f"Geschreven: {xlsx}")
    print(f"Geschreven: {dashboard}")


if __name__ == "__main__":
    main()
