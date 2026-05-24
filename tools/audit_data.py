"""Audit OpenBand data.json for coverage and parser health."""

import json
from pathlib import Path

EXPECTED_SK_BANDS = [
    "Ahtahkakoop Cree Nation",
    "Beardy's and Okemasis' Cree Nation",
    "Big River First Nation",
    "Birch Narrows Dene Nation",
    "Black Lake Denesuline First Nation",
    "Buffalo River Dene Nation",
    "Canoe Lake Cree First Nation",
    "Carry the Kettle Nakoda Nation",
    "Clearwater River Dene Nation",
    "Cowessess First Nation",
    "Cree Nation of Chitek Lake",
    "Cumberland House Cree Nation",
    "Day Star First Nation",
    "English River First Nation",
    "Fishing Lake First Nation",
    "Flying Dust First Nation",
    "Fond du Lac Denesuline First Nation",
    "George Gordon First Nation",
    "Hatchet Lake Denesuline",
    "Hatchet Lake Denesuline Nation",
    "James Smith Cree Nation",
    "Kahkewistahaw First Nation",
    "Kawacatoose First Nation",
    "Keeseekoose First Nation",
    "Key First Nation",
    "Kinistin Saulteaux Nation",
    "Lac La Ronge Indian Band",
    "Little Black Bear First Nation",
    "Little Pine First Nation",
    "Lucky Man Cree Nation",
    "Makwa Sahgaiehcan First Nation",
    "Mistawasis Nehiyawak",
    "Montreal Lake Cree Nation",
    "Mosquito, Grizzly Bear's Head, Lean Man",
    "Mosquito, Grizzly Bear's Head, Lean Man First Nation",
    "Muscowpetung First Nation",
    "Muscowpetung Saulteaux Nation",
    "Muskeg Lake Cree Nation",
    "Muskoday First Nation",
    "Muskowekwan First Nation",
    "Nekaneet Cree Nation",
    "Nekaneet First Nation",
    "Ocean Man First Nation",
    "Ochapowace First Nation",
    "Ochapowace Nation",
    "Okanese First Nation",
    "One Arrow First Nation",
    "Onion Lake Cree Nation",
    "Pasqua First Nation",
    "Peepeekisis Cree Nation",
    "Pelican Lake First Nation",
    "Peter Ballantyne Cree Nation",
    "Pheasant Rump Nakota Nation",
    "Piapot First Nation",
    "Poundmaker Cree Nation",
    "Red Earth Cree Nation",
    "Red Pheasant Cree Nation",
    "Sakimay First Nation",
    "Saulteaux First Nation",
    "Shoal Lake Cree Nation",
    "Standing Buffalo Dakota Nation",
    "Star Blanket Cree Nation",
    "Sturgeon Lake First Nation",
    "Sweetgrass First Nation",
    "The Key First Nation",
    "Thunderchild First Nation",
    "Wahpeton Dakota Nation",
]


def has_people(filing):
    return bool(filing.get("people"))


def is_remuneration(filing):
    return "remuneration" in filing.get("docType", "").lower()


def normalize(name):
    return " ".join(name.lower().replace("&", "and").split())


def main():
    data = json.loads(Path("data.json").read_text(encoding="utf-8"))
    bands = data.get("bands", [])
    by_name = {normalize(band.get("name", "")): band for band in bands}

    parsed_bands = []
    parsed_filings = 0
    pending_posted = []
    for band in bands:
        band_has_parsed = False
        for filing in band.get("filings", []):
            if not is_remuneration(filing):
                continue
            if has_people(filing):
                parsed_filings += 1
                band_has_parsed = True
            elif filing.get("posted"):
                pending_posted.append((band.get("name"), filing.get("year"), filing.get("parse_status")))
        if band_has_parsed:
            parsed_bands.append(band.get("name"))

    missing = []
    for name in EXPECTED_SK_BANDS:
        if normalize(name) not in by_name:
            # Skip alternate spellings if one of the pair is present.
            if name == "Hatchet Lake Denesuline Nation" and normalize("Hatchet Lake Denesuline") in by_name:
                continue
            if name == "Mosquito, Grizzly Bear's Head, Lean Man First Nation" and normalize("Mosquito, Grizzly Bear's Head, Lean Man") in by_name:
                continue
            if name == "Muscowpetung Saulteaux Nation" and normalize("Muscowpetung First Nation") in by_name:
                continue
            if name == "Nekaneet First Nation" and normalize("Nekaneet Cree Nation") in by_name:
                continue
            if name == "Ochapowace Nation" and normalize("Ochapowace First Nation") in by_name:
                continue
            if name == "Key First Nation" and normalize("The Key First Nation") in by_name:
                continue
            missing.append(name)

    print(f"generated: {data.get('generated')}")
    print(f"bands: {len(bands)}")
    print(f"error_count: {data.get('error_count')}")
    print(f"bands with parsed remuneration: {len(parsed_bands)}")
    print(f"parsed remuneration filings: {parsed_filings}")
    print(f"expected SK names missing: {len(missing)}")
    for name in missing:
        print(f"  MISSING: {name}")
    print(f"posted remuneration filings still pending: {len(pending_posted)}")
    for name, year, status in pending_posted[:40]:
        print(f"  PENDING: {name} {year} ({status})")

    if missing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
