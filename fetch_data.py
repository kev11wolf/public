import json
import os
import requests
import time
import sys

# Redundant Overpass API endpoints to fallback on if one is down or timing out
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter"
]

def get_overpass_query(search_criteria):
    """Generates an optimized Overpass QL query with higher server-side allocation."""
    return f"""
    [out:json][timeout:180][maxsize:536870912];
    area["ISO3166-2"="US-NC"]->.searchArea;
    (
      {search_criteria}(area.searchArea);
    );
    out center;
    """

def fetch_category_with_fallback(criteria, category_name):
    """Tries multiple Overpass endpoints with proper headers, backoffs, and tracking."""
    query = get_overpass_query(criteria)
    
    # Crucial Header Addition: Tells the server who we are so they don't throw 406 blocks
    headers = {
        "User-Agent": "NCBrandDataFetcher/1.1 (https://github.com/kev11wolf/public; automated open-source data pull)",
        "Accept-Encoding": "gzip, deflate"
    }
    
    for endpoint in OVERPASS_ENDPOINTS:
        print(f"[{category_name}] Attempting fetch from: {endpoint}")
        for attempt in range(1, 4):
            try:
                response = requests.post(
                    endpoint, 
                    data={'data': query}, 
                    headers=headers, 
                    timeout=(15, 210)
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        elements = data.get('elements', [])
                        
                        # Fix for silent empty sets on unstable mirrors
                        if len(elements) == 0 and endpoint != "https://overpass-api.de/api/interpreter":
                            print(f"![WARN] Server returned 0 items for {category_name}. Skipping mirror validation...")
                            break
                            
                        print(f"Successfully fetched {len(elements)} items for {category_name}.")
                        return elements
                    except json.JSONDecodeError as je:
                        print(f"![ERROR] JSON Parse failure on {endpoint}. Error: {je}")
                        break
                        
                elif response.status_code == 406:
                    print(f"![CRITICAL] 406 Blocked on {endpoint}. Header profile rejected.")
                    break
                elif response.status_code == 429:
                    wait_time = attempt * 20
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
    """Creates a deterministic unique string key based on rounded lat, lon, and brand slug."""
    try:
        return f"{round(float(item['lat']), 4)}_{round(float(item['lon']), 4)}_{item['b']}"
    except KeyError:
        return None

def main():
    output_filename = "us_brands.json"
    existing_records = []
    seen_keys = set()

    if os.path.exists(output_filename):
        try:
            with open(output_filename, "r", encoding="utf-8") as file:
                existing_records = json.load(file)
                if isinstance(existing_records, list):
                    for item in existing_records:
                        key = generate_unique_key(item)
                        if key:
                            seen_keys.add(key)
            print(f"Loaded {len(existing_records)} existing baseline records from {output_filename}.")
        except Exception as e:
            print(f"![ERROR] Could not read existing file. Error: {e}")

    targets = {
        "chickfila": 'nwr["brand"~"Chick-fil-A",i]',
        "mcdonalds": 'nwr["brand"~"McDonald\'s",i]',
        "chipotle": 'nwr["brand"~"Chipotle",i]',
        "starbucks": 'nwr["brand"~"Starbucks",i]',
        "raisingcanes": 'nwr["brand"~"Raising Cane\'s",i]',
        "jerseymikes": 'nwr["brand"~"Jersey Mike",i]',
        "sheetz": 'nwr["brand"~"Sheetz",i]',
        "bucees": 'nwr["brand"~"Buc-ee",i]',
        "wawa": 'nwr["brand"~"Wawa",i]',
        "circlek": 'nwr["brand"~"Circle K",i]',
        "rest_stops": 'nwr["highway"="rest_area"]',
        "playgrounds": 'nwr["leisure"="playground"]'
    }

    religious_blacklist = [
        'church', 'ministries', 'baptist', 'methodist', 'catholic', 'lutheran', 
        'presbyterian', 'episcopal', 'synagogue', 'mosque', 'temple', 'parish', 
        'christian', 'chapel', 'fellowship', 'worship', 'adventist', 'saints'
    ]

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
            b_slug, c_tag, desc = key, "food", f"Official {key} location."

            if key in ["sheetz", "bucees", "wawa", "circlek"]:
                c_tag = "gas"
            elif key == "rest_stops":
                b_slug, c_tag, desc = "rest_stop", "travel", "State-maintained highway rest area."
            elif key == "playgrounds":
                meta_text = f"{name} {tags.get('operator', '')} {tags.get('description', '')}".lower()
                if any(keyword in meta_text for keyword in religious_blacklist):
                    continue
                b_slug, c_tag, desc = "playground", "recreation", "Public community playground facility."

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
        
        time.sleep(6)

    try:
        with open(output_filename, "w", encoding="utf-8") as file:
            json.dump(existing_records, file, indent=2)
        print(f"\nProcessing Complete!")
        print(f"-> Added {new_additions_count} new unique locations.")
        print(f"-> Total records now inside '{output_filename}': {len(existing_records)}")
    except Exception as e:
        print(f"![CRITICAL] Failed writing out data: {e}")
        sys.exit(1)

    if failed_categories:
        print(f"\n![ALERT] Complete structural failures for: {failed_categories}")
        sys.exit(1)

if __name__ == "__main__":
    main()
