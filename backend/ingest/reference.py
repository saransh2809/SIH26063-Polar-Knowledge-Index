"""Fixed reference lists: stations and topics, plus expedition-number parsing.

Stations carry only a name, region and spelling variants. No establishment years or other
facts are stored here, because we have no source URL for them in the database.
"""
import re

STATIONS = [
    {"name": "Dakshin Gangotri", "region": "Antarctic", "aliases": ["Dakshin Gangotri", "Dakshin Gangotri station"]},
    {"name": "Maitri", "region": "Antarctic", "aliases": ["Maitri"]},
    {"name": "Bharati", "region": "Antarctic", "aliases": ["Bharati"]},
    {"name": "Himadri", "region": "Arctic", "aliases": ["Himadri"]},
    {"name": "Himansh", "region": "Himalaya", "aliases": ["Himansh"]},
]

# Keywords are matched as whole words, case-insensitively, against titles and DSpace section names.
TOPICS = [
    {"key": "glaciology", "label": "Glaciology", "keywords": ["glacier", "glaciology", "glaciological", "ice shelf", "iceberg", "ice berg", "ablation", "snow accumulation", "ice sheet", "moraine", "firn", "ice core"]},
    {"key": "atmosphere", "label": "Atmospheric science & meteorology", "keywords": ["atmospheric", "atmosphere", "meteorology", "meteorological", "meteorolgy", "weather", "ozone", "aerosol", "radiation", "wind", "climate", "radiophysics", "radio physics", "ionosphere", "ionospheric"]},
    {"key": "geology", "label": "Geology & earth science", "keywords": ["geology", "geological", "earth science", "earth sciences", "rock", "rocks", "gneiss", "gneisses", "mineral", "petrology", "dyke", "mylonite", "mylonites", "geochemical", "geochemistry", "sediment", "sediments", "soil"]},
    {"key": "geophysics", "label": "Geophysics & geomagnetism", "keywords": ["geophysics", "geophysical", "geomagnetism", "geomagnetic", "magnetic", "gravity", "seismic", "seismological"]},
    {"key": "oceanography", "label": "Oceanography & marine science", "keywords": ["oceanography", "oceanographic", "ocean", "marine", "sea ice", "pack ice", "southern ocean", "krill", "plankton", "bathymetry"]},
    {"key": "biology", "label": "Biology & ecology", "keywords": ["biology", "biological", "bio-sciences", "biosciences", "flora", "fauna", "ecosystem", "ecosystems", "lichen", "lichens", "moss", "mosses", "algae", "bacteria", "microbial", "penguin", "penguins", "birds", "seal", "seals"]},
    {"key": "environment", "label": "Environmental science", "keywords": ["environmental", "environment", "pollution", "pollutant", "pollutants", "waste", "contamination", "heavy metals", "conservation"]},
    {"key": "human_physiology", "label": "Human physiology & medicine", "keywords": ["physiology", "physiological", "medical", "medicine", "health", "psychology", "psychological", "human"]},
    {"key": "engineering_logistics", "label": "Engineering, logistics & communication", "keywords": ["engineering", "logistics", "logistic", "communication", "communications", "navigation", "instrument", "instrumentation", "energy", "non-conventional energy", "materials", "construction", "flying operations"]},
    {"key": "remote_sensing", "label": "Remote sensing & mapping", "keywords": ["remote sensing", "satellite", "mapping", "survey", "gps", "photogrammetry"]},
    {"key": "astronomy", "label": "Astronomy & upper atmosphere", "keywords": ["astronomy", "aurora", "auroral", "cosmic ray", "cosmic rays"]},
    {"key": "paleoclimate", "label": "Palaeoclimate", "keywords": ["paleoclimate", "paleoclimatology", "palaeoclimate", "palaeoclimatic", "paleoclimatic", "holocene", "quaternary"]},
]

_UNITS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19,
}
_TENS_ORDINAL = {"twentieth": 20, "thirtieth": 30, "fortieth": 40, "fiftieth": 50}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}

_UNIT_WORDS = "|".join(sorted(_UNITS, key=len, reverse=True))
_ORDINAL = (
    rf"(?P<tens>twenty|thirty|forty|fifty)[\s-]+(?P<unit>{_UNIT_WORDS})"
    rf"|(?P<tensord>twentieth|thirtieth|fortieth|fiftieth)"
    rf"|(?P<single>{_UNIT_WORDS})"
    rf"|(?P<num>\d{{1,2}})\s*(?:st|nd|rd|th)"
)
# The ordinal must sit directly before "(Indian) (Scientific) (Antarctic|Arctic) Expedition".
# This rejects "the first team of ...", "Fourth batch of the ... Expedition" and
# "42nd Chinese National Antarctic Research Expedition".
EXPEDITION_PHRASE_RE = re.compile(
    rf"\b(?:{_ORDINAL})[\s-]+(?:(?:indian|scientific|antarctic|arctic)[\s-]+){{0,3}}expedition\b", re.I
)
# Codes like "46-ISEA", "35 ISEA", "45th ISEA", "ISEA-9".
ISEA_CODE_RE = re.compile(r"\b(?:ISEA[\s-]*(\d{1,2})\b|(\d{1,2})(?:st|nd|rd|th)?[\s-]*ISEA\b)", re.I)


def _ordinal_value(m: re.Match) -> int:
    if m.group("tens"):
        return _TENS[m.group("tens").lower()] + _UNITS[m.group("unit").lower()]
    if m.group("tensord"):
        return _TENS_ORDINAL[m.group("tensord").lower()]
    if m.group("single"):
        return _UNITS[m.group("single").lower()]
    return int(m.group("num"))


def find_expeditions(text: str) -> list[tuple[int, str, int, bool]]:
    """All expedition numbers in the text: [(number, matched words, end offset, is_isea_code)]."""
    found = [(_ordinal_value(m), m.group(0), m.end(), False) for m in EXPEDITION_PHRASE_RE.finditer(text)]
    found += [(int(m.group(1) or m.group(2)), m.group(0), m.end(), True) for m in ISEA_CODE_RE.finditer(text)]
    return sorted(found, key=lambda f: f[2])


def expedition_number(text: str) -> tuple[int, str] | None:
    """First expedition number in text like 'Ninth Indian Expedition', '46th ISEA', 'ISEA-9'."""
    found = find_expeditions(text)
    return (found[0][0], found[0][1]) if found else None


def keyword_pattern(keywords: list[str]) -> re.Pattern:
    alts = "|".join(re.escape(k).replace(r"\ ", r"[\s-]+") for k in sorted(keywords, key=len, reverse=True))
    return re.compile(rf"\b(?:{alts})\b", re.I)
