import os
import sys
import json
import time
import random
import requests

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

# Stripped down exclusively to McDonald's to speed up parsing
BRAND_MAPPING = {
    "mcdonald": ("food", "mcdonalds", "McDonald's"),
}


def identify_clean_brand(tags):
    combined = f"{tags.get('name', '')} {tags.get('brand', '')}".lower()
    for key, val in BRAND_MAPPING.items():
        if key in combined:
            return val
    return None, None, None


def generate_nc_grids():
    """Generates a tight bounding box grid covering only North Carolina."""
    grids = []
    # NC Approximate bounding bounds: Lat 33.5 to 37.0, Lon -84.5 to -75.0
    curr_lat = 33.5
    while curr_lat < 37.0:
        curr_lon = -84.5
        while curr_lon < -75.0:
            grids.append({
                "south": round(curr_lat, 2),
                "west":  round(curr_lon, 2),
                "north": round(curr_lat + 0.5, 2),
                "east":  round(curr_lon + 1.0, 2),
            })
            curr_lon += 1.0
        curr_lat += 0.5
    return grids


def build_overpass_query(zone):
    # Only querying for McDonald's removes massive overhead from the Overpass engine
    brand_re = "McDonald"
    bbox = f"{zone['south']},{zone['west']},{zone['north']},{zone['east']}"
    return (
        f'[out:json][timeout:30][bbox:{bbox}];\n'
        f'area["ISO3166-2"="US-NC"]->.nc;\n'
        f'(\n'
        f'  node["brand"~"{brand_re}",i](area.nc);\n'
        f'  way["brand"~"{brand_re}",i](area.nc);\n'
        f'  node["name"~"{brand_re}",i](area.nc);\n'
        f'  way["name"~"{brand_re}",i](area.nc);\n'
        f');\n'
        f'out center;'
    )


def _headers():
    return {
        "User-Agent":   random.choice(USER_AGENTS),
        "Content-Type": "text/plain",
        "Referer":      "https://www.openstreetmap.org/",
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
                    print(f"    Waiting {wait}s (rate-limited by {server_url})...", flush=True)
                    time.sleep(wait)
                    continue

                if res.status_code == 200:
                    return res.json()

                print(f"    HTTP {res.status_code} from {server_url}", flush=True)
                break

            except requests.exceptions.Timeout:
                backoff = 5 * (attempt + 1)
                print(f"    Timeout (attempt {attempt + 1}) on {server_url}. Retrying in {backoff}s...", flush=True)
                time.sleep(backoff)
            except Exception as exc:
                print(f"    Error on {server_url}: {exc}", flush=True)
                break

    return None


def generate_nc_database():
    output_file = "us_brands.json"
    compiled_pois = []
    seen_coords   = set()
    
    # 1. Load existing data to append and avoid duplicate matching
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as fh:
                compiled_pois = json.load(fh)
                for poi in compiled_pois:
                    fingerprint = f"{round(poi['lat'], 4)}_{round(poi['lon'], 4)}"
                    seen_coords.add(fingerprint)
            print(f"Resuming task. Loaded {len(compiled_pois)} existing POIs from {output_file}", flush=True)
        except Exception as e:
            print(f"Could not load existing file ({e}). Starting clean.", flush=True)

    micro_zones = generate_nc_grids()
    
    # 2. Slice grids if CLI indices are supplied
    start_idx = 0
    end_idx = len(micro_zones)
    if len(sys.argv) > 1:
        try:
            start_idx = int(sys.argv[1])
            if len(sys.argv) > 2:
                end_idx = int(sys.argv[2])
            print(f"Processing limited chunk slice: indices {start_idx} to {end_idx}", flush=True)
        except ValueError:
            print("Invalid CLI arguments. Processing all grids.", flush=True)

    target_zones = micro_zones[start_idx:end_idx]
    print(f"Launching scraper across {len(target_zones)} micro-sectors for NC...", flush=True)

    for slice_idx, zone in enumerate(target_zones):
        actual_global_idx = start_idx + slice_idx
        
        query    = build_overpass_query(zone)
        response = query_overpass(query)

        if response is None:
            print(f"    Sector [{actual_global_idx + 1}/{len(micro_zones)}] skipped -- all mirrors failed.", flush=True)
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
            
            compiled_pois.append(poi)
            seen_coords.add(fingerprint)
            zone_count += 1

        if zone_count > 0:
            print(
                f"Sector [{actual_global_idx + 1}/{len(micro_zones)}] +{zone_count} entries. "
                f"Total Compiled: {len(compiled_pois)}",
                flush=True,
            )
            # Incremental safe rewrite to append elements without corrupting JSON structures
            with open(output_file, "w", encoding="utf-8") as fh:
                json.dump(compiled_pois, fh, indent=2)

        time.sleep(random.uniform(1.5, 3.0))

    print(f"\nPipeline execution batch complete -- {len(compiled_pois)} total POIs saved.", flush=True)


if __name__ == "__main__":
    generate_nc_database()
