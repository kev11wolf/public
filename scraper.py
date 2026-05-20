import json
import os
import requests
import time
import sys

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter"
]

# Shared filter profiles for checking both live data and existing JSON datasets
RELIGIOUS_BLACKLIST = [
    'church', 'ministries', 'baptist', 'methodist', 'catholic', 'lutheran', 
    'presbyterian', 'episcopal', 'synagogue', 'mosque', 'temple', 'parish', 
    'christian', 'chapel', 'fellowship', 'worship', 'adventist', 'saints'
]

SCHOOL_PRIVATE_BLACKLIST = [
    'school', 'academy', 'elementary', 'middle', 'high', 'charter', 
    'daycare', 'childcare', 'preschool', 'kindergarten', 'learning center',
    'private', 'subdivision', 'hoa', 'apartment', 'condo', 'townhome', 
    'club', 'resort', 'golf', 'fitness', 'ymca', 'campground', 'hotel', 'motel',
    'studio', 'therapy', 'clinic', 'hospital', 'community center'
]

COMBINED_PLAYGROUND_BLACKLIST = RELIGIOUS_BLACKLIST + SCHOOL_PRIVATE_BLACKLIST

PUBLIC_PARK_KEYWORDS = [
    'park', 'public', 'community', 'recreation', 'civic', 'city', 'town', 'county', 'municipal', 'village'
]

def get_overpass_query(search_criteria):
    """Generates an index-optimized Overpass QL query template."""
    return f"""
    [out:json][timeout:120][maxsize:268435456];
    area["ISO3166-2"="US-NC"]->.searchArea;
    (
      {search_criteria}
    );
    out center;
    """

def fetch_category_with_fallback(criteria, category_name):
    """Tries multiple Overpass endpoints with proper headers, backoffs, and tracking."""
    query = get_overpass_query(criteria)
    headers = {
        "User-Agent": "NCBrandDataFetcher/1.3 (https://github.com/kev11wolf/public; automated data engine)",
        "Accept-Encoding": "gzip, deflate"
    }
    
    for endpoint in OVERPASS_ENDPOINTS:
        print(f"[{category_name}] Attempting fetch from: {endpoint}")
        for attempt in range(1, 4):
            try:
                response = requests.post(endpoint, data={'data': query}, headers=headers, timeout=(15, 140))
                if response.status_code == 200:
                    try:
                        data = response.json()
                        elements = data.get('elements', [])
                        if len(elements) == 0 and endpoint != "https://overpass-api.de/api/interpreter" and category_name not in ["bucees", "wawa"]:
                            print(f"![WARN] Mirror server returned 0 items suspiciously for {category_name}. Shifting mirror...")
                            break
                        print(f"Successfully fetched {len(elements)} items for {category_name}.")
                        return elements
                    except json.JSONDecodeError as je:
                        print(f"![ERROR] JSON Parse failure on {endpoint}. Error: {je}")
                        break
                elif response.status_code == 429:
                    wait_time = attempt * 25
                    print(f"![WARN] Rate limited (429). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif response.status_code == 504:
                    print(f"![WARN] Gateway Timeout (504) on {endpoint}. Shifting mirror...")
                    break
                else:
                    print(f"![ERROR] HTTP Error {response.status_code} from {endpoint}")
                    break
            except requests.exceptions.Timeout as te:
                print(f"![TIMEOUT] Network timeout reached on {endpoint}. Details: {te}")
                time.sleep(5)
            except requests.exceptions.ConnectionError as ce:
                print(f"![CONNECTION ERROR] Failed to connect to {endpoint}. Details: {ce}")
                time.sleep(5)
            except Exception as e:
                print(f"![UNEXPECTED ERROR] An unhandled exception occurred: {e}")
                time.sleep(5)
        print(f"Moving away from endpoint: {endpoint}\n")
    print(f"!!! [CRITICAL FAILURE] All endpoints failed for category: {category_name} !!!")
    return None

def generate_unique_key(item):
    try:
        return f"{round(float(item['lat']), 4)}_{round(float(item['lon']), 4)}_{item['b']}"
    except KeyError:
        return None

def main():
    output_filename = "us_brands.json"
    existing_records = []
    seen_keys = set()
    purged_old_playgrounds = 0

    # Step 1: Load and clean current JSON of any old non-compliant playgrounds
    if os.path.exists(output_filename):
        try:
            with open(output_filename, "r", encoding="utf-8") as file:
                raw_records = json.load(file)
                if isinstance(raw_records, list):
                    for item in raw_records:
                        # Clean previously saved school/private playgrounds out of the database array
                        if item.get('b') == 'playground':
                            meta = f"{item.get('n', '')} {item.get('d', '')}".lower()
                            if any(kw in meta for kw in COMBINED_PLAYGROUND_BLACKLIST):
                                purged_old_playgrounds += 1
                                continue
                            if not any(kw in meta for kw in PUBLIC_PARK_KEYWORDS):
                                purged_old_playgrounds += 1
                                continue
                        
                        key = generate_unique_key(item)
                        if key:
                            existing_records.append(item)
                            seen_keys.add(key)
            print(f"Loaded baseline data. Retroactively cleaned & purged {purged_old_playgrounds} old private/school playgrounds.")
            print(f"Retained {len(existing_records)} valid unique records to build upon.")
        except Exception as e:
            print(f"![ERROR] Could not read existing file. Error: {e}")

    # Step 2: Target Queries with Wendy's added and index optimization
    targets = {
        "chickfila": 'nwr["brand"~"Chick-[fF]il-[aA]"](area.searchArea); nwr["name"~"Chick-[fF]il-[aA]"](area.searchArea);',
        "mcdonalds": 'nwr["brand"~"Mc[dD]onald"](area.searchArea); nwr["name"~"Mc[dD]onald"](area.searchArea);',
        "chipotle": 'nwr["brand"~"Chipotle"](area.searchArea); nwr["name"~"Chipotle"](area.searchArea);',
        "starbucks": 'nwr["brand"~"Starbucks"](area.searchArea); nwr["name"~"Starbucks"](area.searchArea);',
        "wendys": 'nwr["brand"~"Wendy"](area.searchArea); nwr["name"~"Wendy"](area.searchArea);',
        "raisingcanes": 'nwr["brand"~"Raising Cane"](area.searchArea); nwr["name"~"Raising Cane"](area.searchArea);',
        "jerseymikes": 'nwr["brand"~"Jersey Mike"](area.searchArea); nwr["name"~"Jersey Mike"](area.searchArea);',
        "sheetz": 'nwr["brand"~"Sheetz"](area.searchArea); nwr["name"~"Sheetz"](area.searchArea);',
        "bucees": 'nwr["brand"~"Buc-ee"](area.searchArea); nwr["name"~"Buc-ee"](area.searchArea);',
        "wawa": 'nwr["brand"~"Wawa"](area.searchArea); nwr["name"~"Wawa"](area.searchArea);',
        "circlek": 'nwr["brand"~"Circle K"](area.searchArea); nwr["name"~"Circle K"](area.searchArea);',
        "rest_stops": 'nwr["highway"="rest_area"](area.searchArea);',
        "playgrounds": 'nwr["leisure"="playground"](area.searchArea);'
    }

    new_additions_count = 0
    failed_categories = []

    for key, criteria in targets.items():
        elements = fetch_category_with_fallback(criteria, key)
        if elements is None:
            failed_categories.append(key)
            continue
            
        for elem in elements:
            tags = elem.get('tags', {})
            lat = elem.get('lat') or elem.get('center', {}).get('lat')
            lon = elem.get('lon') or elem.get('center', {}).get('lon')
            if not lat or not lon:
                continue

            name = tags.get('name', f"Unbranded {key}" if key in ["rest_stops", "playgrounds"] else f"{key} Location")
            brand_raw = tags.get('brand', '').lower()
            name_raw = name.lower()
            
            b_slug, c_tag, desc = key, "food", f"Official {key} location."

            # Dynamic classification matching
            if "chick-fil-a" in brand_raw or "chick-fil-a" in name_raw:
                b_slug = "chickfila"
            elif "mcdonald" in brand_raw or "mcdonald" in name_raw:
                b_slug = "mcdonalds"
            elif "chipotle" in brand_raw or "chipotle" in name_raw:
                b_slug = "chipotle"
            elif "starbucks" in brand_raw or "starbucks" in name_raw:
                b_slug = "starbucks"
            elif "wendy" in brand_raw or "wendy" in name_raw:
                b_slug, desc = "wendys", "Fast-food chain known for square beef burgers, sea-salt fries, and Frosty desserts."
            elif "raising cane" in brand_raw or "raising cane" in name_raw:
                b_slug = "raisingcanes"
            elif "jersey mike" in brand_raw or "jersey mike" in name_raw:
                b_slug = "jerseymikes"

            if key in ["sheetz", "bucees", "wawa", "circlek"]:
                c_tag = "gas"
                b_slug = key
            elif key == "rest_stops":
                b_slug, c_tag, desc = "rest_stop", "travel", "State-maintained highway rest area."
            elif key == "playgrounds":
                # Strict Playground Filtering Rules
                access_val = tags.get('access', '').lower()
                if access_val in ['private', 'no', 'customers', 'permissive', 'residents', 'delivery']:
                    continue # Skip private infrastructure completely
                if tags.get('amenity') == 'school' or tags.get('landuse') == 'education':
                    continue # Skip explicit school boundaries
                    
                meta_text = f"{name} {tags.get('operator', '')} {tags.get('description', '')} {tags.get('site', '')}".lower()
                
                if any(keyword in meta_text for keyword in COMBINED_PLAYGROUND_BLACKLIST):
                    continue # Filter school/private/church affiliations
                    
                if not any(kw in meta_text for kw in PUBLIC_PARK_KEYWORDS):
                    continue # Ensure it resides in a secular, public park space
                    
                b_slug, c_tag, desc = "playground", "recreation", "Public community playground facility located in a public park space with free parking access."

            temp_record = {"lat": round(lat, 4), "lon": round(lon, 4), "b": b_slug}
            record_key = generate_unique_key(temp_record)
            
            if record_key in seen_keys:
                continue

            record = {
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "n": name,
                "b": b_slug,
                "c": c_tag
            }

            if c_tag == "gas":
                record["g87"] = 1
                record["g88"] = 1 if b_slug == "sheetz" else 0

            record["h"] = tags.get('opening_hours', '24/7' if c_tag in ['gas', 'travel'] else 'Varies')
            record["d"] = desc
            
            existing_records.append(record)
            seen_keys.add(record_key)
            new_additions_count += 1
        
        time.sleep(5)

    # Step 3: Commit structural output arrays
    try:
        with open(output_filename, "w", encoding="utf-8") as file:
            json.dump(existing_records, file, indent=2)
        print(f"\nProcessing Complete!")
        print(f"-> Added {new_additions_count} new unique locations (including Wendy's).")
        print(f"-> Total valid records now inside '{output_filename}': {len(existing_records)}")
    except Exception as e:
        print(f"![CRITICAL] Failed writing out data: {e}")
        sys.exit(1)

    if failed_categories:
        print(f"\n![ALERT] Complete structural failures for: {failed_categories}")
        sys.exit(1)

if __name__ == "__main__":
    main()
