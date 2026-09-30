import pytest

from ingest.reference import expedition_number


@pytest.mark.parametrize(
    "title, expected",
    [
        ("09] Scientific Report Of Ninth Indian Expedition To Antarctica", 9),
        ("11] Scientific Report Eleventh Indian Expedition To Antarctica", 11),
        ("21] Scientific Report Of Twenty First Indian Expedition To Antarctica", 21),
        ("29] Scientific Report of Twenty Ninth Indian Expedition To Antarctica", 29),
        ("30] Scientific Report of Thirtieth Indian Expedition To Antarctica", 30),
        ("6.1] Sixth Indian Scientific Expedition To Antartica 1986-87", 6),
        ("Scientific Report of Ninth Indian Expedition to Antarctica, Technical Publication No. 6", 9),
        ("The 46th Indian Scientific Expedition to Antarctica begins", 46),
        ("46-ISEA proposal workshop", 46),
        ("Twenty-second expedition", 22),
        ("The first team of the 45th Indian Scientific Expedition to Antarctica (45th ISEA) departed", 45),
        ("Walk-in-interview for Medical Doctors for 35 ISEA", 35),
        ("Members of the 17th Indian Arctic Expedition took the pledge", 17),
    ],
)
def test_expedition_number(title, expected):
    result = expedition_number(title)
    assert result is not None and result[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "B]Scientific Report Of Indian Expedition To Weddell Sea",
        "The first sample was taken near the lake",
        "Monitoring of Icebergs in Antarctic Waters",
        "participated in the 42nd Chinese National Antarctic Research Expedition",
        "Fourth batch of the Indian Arctic Expedition (2013-2014)",
        "part of various national expeditions to Antarctica, Arctic, as well as the first",
    ],
)
def test_no_expedition_number(text):
    assert expedition_number(text) is None
