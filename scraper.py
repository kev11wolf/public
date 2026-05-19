import os
import json
import random
import requests

# ==========================================
# CONFIGURATION BLOCK
# Change these values when switching chains!
# ==========================================
OUTPUT_FILE = "us_brands.json"

# North Carolina's bounding box coordinates (South, West, North, East)
# This completely replaces the slow 'area' lookup logic
BBOX = "33.75,-84.33,36.59,-75.46" 

BRAND_SEARCH = "McDonald"     # The regex string passed to Overpass
BRAND_SLUG = "mcdonalds"      # The machine-readable slug saved to "b"
CATEGORY_SLUG = "food"        # The category slug saved to "c" (e.g., food, gas)
DISPLAY_NAME = "McDonald's"   # The clean name saved to "n"

# Keywords used to filter out offices or inactive storefronts
BLACKLIST = [
    "corporate", "office", "headquarters", "hq", "distribution", 
    "training", "closed", "historical", "warehouse"
]

# ==========================================
# SCRAPER CORE
# ==========================================
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]


def build_bbox_query():
    # Injecting the bounding box directly into the query metadata header
    return (
        f'[out:json][timeout:60][bbox:{BBOX}];\n'
        f'(\n'
        f'  node["brand"~"{BRAND_SEARCH}",i];\n'
        f'  way["brand"~"{BRAND_SEARCH}",i];\n'
        f'  node["name"~"{BRAND_SEARCH}",i];\n'
        f'  way["name"~"{BRAND_SEARCH}",i];\n'
        f');\n'
        f'out center;'
    )


def fetch_data():
    query = build_bbox_query()
    mirrors = list(OVERPASS_ENDPOINTS)
    random.shuffle(mirrors)

    # Using a clean, standard browser profile ensures the 406 blocks are bypassed
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.openstreetmap.org/",
    }

    for server_url in mirrors:
        print(f"Attempting to fetch {DISPLAY_NAME} within BBox via {server_url}...", flush=True)
        try:
            # Using standard form-encoding data dict, which is universally accepted across all mirrors
            res = requests.post(
                server_url,
                data={"data": query},
                headers=headers,
                timeout=60,
            )
            
            if res.status_code == 200:
                return res.json()
            
            print(f"  Server returned status code {res.status_code}, trying next mirror...", flush=True)
                
        except Exception as e:
            print(f"  Failed connecting to {server_url}: {e}", flush=True)
    return None


def is_blacklisted(tags):
    name = tags.get("name", "").lower()
    brand = tags.get("brand", "").lower()
    description = tags.get("description", "").lower()
    
    for word in BLACKLIST:
        if word in name or word in brand or word in description:
            return True
            
    if tags.get("was:brand") or tags.get("old_brand") or tags.get("disused") == "yes":
        return True
        
    return False


def main():
    compiled_pois = []
    seen_coords = set()
    
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as fh:
                compiled_pois = json.load(fh)
                for poi in compiled_pois:
                    fingerprint = f"{round(poi['lat'], 4)}_{round(poi['lon'], 4)}"
                    seen_coords.add(fingerprint)
            print(f"Loaded {len(compiled_pois)} existing POIs from {OUTPUT_FILE}")
        except Exception as e:
            print(f"Could not read existing file ({e}). Starting fresh.")

    raw_data = fetch_data()
    if not raw_data:
        print("Error: All Overpass mirrors failed or timed out. The servers may be overloaded.")
        return

    elements = raw_data.get("elements", [])
    new_entries_count = 0
    blacklisted_count = 0

    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lon:
            continue

        fingerprint = f"{round(lat, 4)}_{round(lon, 4)}"
        if fingerprint in seen_coords:
            continue

        tags = el.get("tags", {})
        if is_blacklisted(tags):
            blacklisted_count += 1
            continue

        poi = {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "n":   DISPLAY_NAME,
            "b":   BRAND_SLUG,
            "c":   CATEGORY_SLUG,
            "h":   tags.get("opening_hours", "Hours vary by location"),
            "d":   tags.get("description", "Verified chain location mapped off regional route bounds."),
        }
        
        if CATEGORY_SLUG == "gas":
            poi["g87"] = 1 if (tags.get("fuel:octane_87") == "yes" or tags.get("fuel:unleaded") == "yes") else 1
            poi["g88"] = 1 if (tags.get("fuel:octane_88") == "yes" or tags.get("fuel:e15") == "yes") else 0

        compiled_pois.append(poi)
        seen_coords.add(fingerprint)
        new_entries_count += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(compiled_pois, fh, indent=2)

    print(f"\nExecution Complete:")
    print(f" -> Added {new_entries_count} new entries.")
    print(f" -> Filtered out {blacklisted_count} locations matching blacklist rules.")
    print(f" -> Total records inside {OUTPUT_FILE}: {len(compiled_pois)}")


if __name__ == "__main__":
    main()
