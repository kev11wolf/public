import os
import json
import random
import requests

# ==========================================
# CONFIGURATION BLOCK
# Change these values when switching chains!
# ==========================================
OUTPUT_FILE = "us_brands.json"
TARGET_STATE = "US-NC"        # ISO 3166-2 state code (e.g., US-NC, US-TX, US-CA)
BRAND_SEARCH = "McDonald"     # The regex string passed to Overpass
BRAND_SLUG = "mcdonalds"      # The machine-readable slug saved to "b"
CATEGORY_SLUG = "food"        # The category slug saved to "c" (e.g., food, gas)
DISPLAY_NAME = "McDonald's"   # The clean name saved to "n"

# Add any keywords here (case-insensitive) to skip unwanted matches
# e.g., corporate offices, distribution centers, closed locations, or training centers
BLACKLIST = [
    "corporate", 
    "office", 
    "headquarters", 
    "hq", 
    "distribution", 
    "training", 
    "closed", 
    "historical", 
    "warehouse"
]

# ==========================================
# SCRAPER CORE
# ==========================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]


def build_single_state_query():
    return (
        f'[out:json][timeout:90];\n'
        f'area["ISO3166-2"="{TARGET_STATE}"]->.search_area;\n'
        f'(\n'
        f'  node["brand"~"{BRAND_SEARCH}",i](area.search_area);\n'
        f'  way["brand"~"{BRAND_SEARCH}",i](area.search_area);\n'
        f'  node["name"~"{BRAND_SEARCH}",i](area.search_area);\n'
        f'  way["name"~"{BRAND_SEARCH}",i](area.search_area);\n'
        f');\n'
        f'out center;'
    )


def fetch_data():
    query = build_single_state_query()
    mirrors = list(OVERPASS_ENDPOINTS)
    random.shuffle(mirrors)

    for server_url in mirrors:
        print(f"Attempting to fetch {DISPLAY_NAME} for {TARGET_STATE} from {server_url}...", flush=True)
        try:
            res = requests.post(
                server_url,
                data={"data": query},
                headers={"User-Agent": random.choice(USER_AGENTS), "Content-Type": "text/plain"},
                timeout=95,
            )
            if res.status_code == 200:
                return res.json()
            print(f"  Server returned status code {res.status_code}, trying next mirror...", flush=True)
        except Exception as e:
            print(f"  Failed connecting to {server_url}: {e}", flush=True)
    return None


def is_blacklisted(tags):
    """Checks the location's name and brand tags against the blacklist."""
    name = tags.get("name", "").lower()
    brand = tags.get("brand", "").lower()
    description = tags.get("description", "").lower()
    
    # Check if any blacklisted keyword exists in the tags
    for word in BLACKLIST:
        if word in name or word in brand or word in description:
            return True
            
    # Explicitly catch OpenStreetMap lifecycle prefixes indicating closed status
    if tags.get("was:brand") or tags.get("old_brand") or tags.get("disused") == "yes":
        return True
        
    return False


def main():
    compiled_pois = []
    seen_coords = set()
    
    # 1. Load existing data if it exists so we safely append to us_brands.json
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as fh:
                compiled_pois = json.load(fh)
                for poi in compiled_pois:
                    # Creating unique fingerprint via coordinates to guarantee no duplicates inside the file
                    fingerprint = f"{round(poi['lat'], 4)}_{round(poi['lon'], 4)}"
                    seen_coords.add(fingerprint)
            print(f"Loaded {len(compiled_pois)} existing POIs from {OUTPUT_FILE}")
        except Exception as e:
            print(f"Could not read existing file ({e}). Starting fresh.")

    # 2. Run the single state query
    raw_data = fetch_data()
    if not raw_data:
        print("Error: All Overpass mirrors failed or timed out. Please try again shortly.")
        return

    elements = raw_data.get("elements", [])
    new_entries_count = 0
    blacklisted_count = 0

    # 3. Parse data
    for el in elements:
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lon:
            continue

        # Coordinate-based deduplication
        fingerprint = f"{round(lat, 4)}_{round(lon, 4)}"
        if fingerprint in seen_coords:
            continue

        tags = el.get("tags", {})
        
        # Apply the blacklist filter
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
        
        # Automatically capture fuel attributes if you configure this for a gas station run
        if CATEGORY_SLUG == "gas":
            poi["g87"] = 1 if (tags.get("fuel:octane_87") == "yes" or tags.get("fuel:unleaded") == "yes") else 1
            poi["g88"] = 1 if (tags.get("fuel:octane_88") == "yes" or tags.get("fuel:e15") == "yes") else 0

        compiled_pois.append(poi)
        seen_coords.add(fingerprint)
        new_entries_count += 1

    # 4. Save cleanly appended data back to us_brands.json
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(compiled_pois, fh, indent=2)

    print(f"\nExecution Complete:")
    print(f" -> Added {new_entries_count} new entries.")
    print(f" -> Filtered out {blacklisted_count} locations matching blacklist rules.")
    print(f" -> Total records inside {OUTPUT_FILE}: {len(compiled_pois)}")


if __name__ == "__main__":
    main()
