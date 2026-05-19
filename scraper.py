import requests
import json
import time
import random
import sys

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/605.1.15",
]

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

BRAND_MAPPING = {
    "murphy express":  ("gas",  "murphyexpress", "Murphy Express"),
    "sheetz":          ("gas",  "sheetz",        "Sheetz"),
    "buc-ee":          ("gas",  "bucees",        "Buc-ee's"),
    "bucee":           ("gas",  "bucees",        "Buc-ee's"),
    "costco":          ("gas",  "costcogas",     "Costco Gasoline"),
    "wawa":            ("gas",  "wawa",          "Wawa"),
    "circle k":        ("gas",  "circlek",       "Circle K"),
    "mcdonald":        ("food", "mcdonalds",     "McDonald's"),
    "wendy":           ("food", "wendys",        "Wendy's"),
    "chick-fil-a":     ("food", "chickfila",     "Chick-fil-A"),
    "chick fil a":     ("food", "chickfila",     "Chick-fil-A"),
    "chipotle":        ("food", "chipotle",      "Chipotle"),
    "jersey mike":     ("food", "jerseymikes",   "Jersey Mike's"),
    "raising cane":    ("food", "raisingcanes",  "Raising Cane's"),
}

RELIGIOUS_BLACKLIST = [
    "church", "chapel", "ministry", "baptist", "methodist", "lutheran",
    "presbyterian", "catholic", "parish", "fellowship", "christian",
    "synagogue", "temple", "mosque", "tabernacle", "saints", "lds",
]


def clean_and_validate_playground(tags):
    if tags.get("amenity") == "place_of_worship" or tags.get("religion") is not None:
        return None
    name = tags.get("name", "Public Playground")
    if any(k in name.lower() for k in RELIGIOUS_BLACKLIST):
        return None
    return name


def identify_clean_brand(tags):
    combined = f"{tags.get('name', '')} {tags.get('brand', '')}".lower()
    for key, val in BRAND_MAPPING.items():
        if key in combined:
            if val[1] == "costcogas" and "fuel" not in combined and "gas" not in combined:
                continue
            return val
    return None, None, None


def generate_stable_grids():
    grids = []
    curr_lat = 24.0
    while curr_lat < 50.0:
        curr_lon = -125.0
        while curr_lon < -66.0:
            grids.append({
                "south": round(curr_lat, 2),
                "west":  round(curr_lon, 2),
                "north": round(curr_lat + 1.5, 2),
                "east":  round(curr_lon + 2.5, 2),
            })
            curr_lon += 2.5
        curr_lat += 1.5
    return grids


def build_overpass_query(zone):
    brand_re = (
        "Sheetz|Chipotle|Jersey Mike|McDonald|Wendy|Chick-fil-A|"
        "Raising Cane|Murphy Express|Buc-ee|Wawa|Circle K|Costco"
    )
    bbox = f"{zone['south']},{zone['west']},{zone['north']},{zone['east']}"
    return (
        f'[out:json][timeout:25][bbox:{bbox}];\n'
        f'(\n'
        f'  node["brand"~"{brand_re}",i];\n'
        f'   way["brand"~"{brand_re}",i];\n'
        f'  node["name"~"{brand_re}",i];\n'
        f'   way["name"~"{brand_re}",i];\n'
        f'  node["leisure"="playground"]["access"!~"private|no"];\n'
        f'   way["leisure"="playground"]["access"!~"private|no"];\n'
        f');\n'
        f'out center;'
    )


def _headers():
    return {
        "User-Agent":   random.choice(USER_AGENTS),
        "Content-Type": "text/plain",
        "Referer":      "https://www.openstreetmap.org/",
        # "Accept: application/json" intentionally omitted - causes HTTP 406
    }


def query_overpass(query, max_retries=3):
    mirrors = list(OVERPASS_ENDPOINTS)
    random.shuffle(mirrors)

    for server_url in mirrors:
        for attempt in range(max_retries):
            try:
                res = requests.post(
                    server_url,
                    data={"data": query},
                    headers=_headers(),
                    timeout=35,
                )

                if res.status_code == 429:
                    wait = 60 * (attempt + 1)
                    print(f"   Waiting {wait}s (rate-limited by {server_url})...", flush=True)
                    time.sleep(wait)
                    continue

                if res.status_code == 200:
                    return res.json()

                print(f"   HTTP {res.status_code} from {server_url}", flush=True)
                break

            except requests.exceptions.Timeout:
                backoff = 5 * (attempt + 1)
                print(f"   Timeout (attempt {attempt + 1}) on {server_url}. Retrying in {backoff}s...", flush=True)
                time.sleep(backoff)
            except Exception as exc:
                print(f"   Error on {server_url}: {exc}", flush=True)
                break

    return None


def generate_national_database():
    compiled_pois = []
    seen_coords   = set()
    micro_zones   = generate_stable_grids()

    print(f"Launching across {len(micro_zones)} stable sectors...", flush=True)

    for idx, zone in enumerate(micro_zones):
        if zone["south"] < 29.0 and zone["west"] < -92.0:
            continue
        if zone["south"] > 44.0 and zone["west"] < -124.0:
            continue

        query    = build_overpass_query(zone)
        response = query_overpass(query)

        if response is None:
            print(f"   Sector [{idx + 1}/{len(micro_zones)}] skipped -- all mirrors failed.", flush=True)
            continue

        elements = response.get("elements", [])
        if not elements:
            continue

        zone_count = 0
        for el in elements:
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if not lat or not lon:
                continue

            fingerprint = f"{round(lat, 4)}_{round(lon, 4)}"
            if fingerprint in seen_coords:
                continue

            tags = el.get("tags", {})

            if tags.get("leisure") == "playground":
                name = clean_and_validate_playground(tags)
                if not name:
                    continue
                compiled_pois.append({
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "n":   name,
                    "b":   "playground",
                    "c":   "playground",
                    "h":   tags.get("opening_hours", "Sunrise to Sunset"),
                    "d":   tags.get("description",   "Public open-access park playground."),
                })
            else:
                cat_slug, brand_slug, display_name = identify_clean_brand(tags)
                if not cat_slug:
                    continue

                poi = {
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "n":   display_name,
                    "b":   brand_slug,
                    "c":   cat_slug,
                    "h":   tags.get("opening_hours", "Hours vary by location"),
                    "d":   tags.get("description",   "Verified chain location mapped off highway route bounds."),
                }
                if cat_slug == "gas":
                    poi["g87"] = 1 if (
                        tags.get("fuel:octane_87") == "yes" or
                        tags.get("fuel:unleaded")  == "yes"
                    ) else 1
                    poi["g88"] = 1 if (
                        tags.get("fuel:octane_88") == "yes" or
                        tags.get("fuel:e15")       == "yes"
                    ) else 0
                compiled_pois.append(poi)

            seen_coords.add(fingerprint)
            zone_count += 1

        if zone_count > 0:
            print(
                f"Sector [{idx + 1}/{len(micro_zones)}] +{zone_count} entries. "
                f"Total: {len(compiled_pois)}",
                flush=True,
            )

        time.sleep(random.uniform(1.5, 3.0))

    if not compiled_pois:
        print("CRITICAL: 0 results compiled. Aborting save.", flush=True)
        sys.exit(1)

    print(f"\nPipeline complete -- {len(compiled_pois)} total POIs.", flush=True)

    with open("us_brands.json", "w", encoding="utf-8") as fh:
        json.dump(compiled_pois, fh, indent=2)

    print("'us_brands.json' written successfully.", flush=True)


if __name__ == "__main__":
    generate_national_database()
