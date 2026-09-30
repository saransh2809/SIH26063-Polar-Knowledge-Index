"""Crop the full-page screenshots to the regions each slide slot shows."""
from pathlib import Path

from PIL import Image

SHOTS = Path(__file__).resolve().parent / "shots"
CROPS = {
    # name: (source, (left, top, right, bottom))
    "s2_page_viewer.png": ("page_viewer.png", (230, 140, 1370, 870)),
    "s5_search.png": ("search_glacier.png", (230, 90, 1370, 800)),
    "s5_answer.png": ("review_answer.png", (230, 170, 1020, 660)),
    "s5_page.png": ("page_viewer.png", (230, 140, 1370, 850)),
}

for out, (src, box) in CROPS.items():
    Image.open(SHOTS / src).crop(box).save(SHOTS / out)
    print(out, box[2] - box[0], "x", box[3] - box[1])
