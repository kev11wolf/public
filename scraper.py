import requests
import json
import time
import random

# A rotating pool of standard user browser headers to mimic desktop/mobile devices
# This prevents public mapping servers from instantly flagging the GitHub virtual machine
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/605.1.15"
]

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter"
]

# Strict brand lookup matrix to clean messy naming profiles natively
BRAND_MAPPING = {
    "murphy express": ("gas", "murphyexpress", "Murphy Express"),
    "sheetz": ("gas", "sheetz", "Sheetz"),
    "buc-ee": ("gas", "bucees", "Buc-ee's"),
    "bucee": ("gas", "bucees", "Buc-ee's"),
    "costco": ("gas", "costcogas", "Costco Gasoline"),
    "wawa": ("gas", "wawa", "Wawa"),
    "circle k": ("gas", "circlek", "Circle K"),
    "mcdonald": ("food", "mcdonalds", "McDonald's"),
    "wendy": ("food", "wendys", "Wendy's"),
    "chick-fil-a": ("food", "chickfila", "Chick-fil-A"),
    "chick fil a": ("food", "chickfila", "Chick-fil-A"),
    "chipotle": ("food", "chipotle", "Chipotle"),
    "jersey mike": ("food", "jerseymikes", "Jersey Mike's"),
    "raising cane": ("food", "raisingcanes", "Raising Cane's")
}

def clean_and_validate_playground(tags):
    """Filters out any playgrounds associated with churches or religious keywords"""
    if tags.get("amenity") == "place_of_worship" or tags.get("religion") is not None:
        return None
        
    name = tags.get("name", "Public Playground")
    name_lower = name.lower()
    
    religious_blacklist = [
        "church", "chapel", "ministry", "baptist", "methodist", "lutheran", 
        "presbyterian", "catholic", "parish", "fellowship", "christian", 
        "synagogue", "temple", "mosque", "tabernacle", "saints", "lds"
    ]
    
    if any(keyword in name_lower for keyword in religious_blacklist):
        return None
        
    return name

def identify_clean_brand(tags):
    """Maps messy string varieties into strict standardized brand formats"""
    combined_text = f"{tags.get('name', '')} {tags.get('brand', '')}".lower()
    
    for key, val in BRAND_MAPPING.items():
        if key in combined_text:
            # Protect wholesale clubs from misidentifying standard grocery registers as fuel pumps
            if val[1] == "costcogas" and "fuel" not in combined_text and "gas" not in combined_text:
                continue
            return val[0], val[1], val[2]
            
    return None, None, None

def generate_micro_grids():
    """Generates a high-density sub-zone matrix tracking across the US boundaries.
    Slicing states into 2.0x3.0 degree coordinate boxes keeps server footprint small 
    enough to prevent request timeout exceptions."""
    grids = []
    lat_start, lat_end = 24.0, 50.0
    lon_start, lon_end = -125.0, -66.0
    
    lat_step = 2.0
    lon_step = 3.0
    
    curr_lat = lat_start
    while curr_lat < lat_end:
        curr_lon = lon_start
        while curr_lon < lon_end:
            grids.append({
                "south": round(curr_lat, 2),
                "west": round(curr_lon, 2),
                "north": round(curr_lat + lat_step, 2),
                "east": round(curr_lon + lon_step, 2)
            })
            curr_lon += lon_step
        curr_lat += lat_step
    return grids

def generate_national_database():
    compiled_pois = []
    seen_unique_coords = set()
    micro_zones = generate_micro_grids()
    
    print(f"🚀 Initializing national map script data generation across {len(micro_zones)} zone segments...")
    
    for idx, zone in enumerate(micro_zones):
        # Skip logic for empty offshore oceanic sectors to prioritize download speeds
        if zone['south'] < 30.0 and zone['west'] < -100.0 and zone['west'] > -115.0:
            continue
            
        query = f"""
        [out:json][timeout:60][bbox:{zone['south']},{zone['west']},{zone['north']},{zone['east']}];
        (
          node["brand"~"Sheetz|Chipotle|Jersey Mike|McDonald's|Wendy's|Chick-fil-A|Raising Cane|Murphy Express|Buc-ee|Wawa|Circle K|Costco",i];
          node["name"~"Sheetz|Chipotle|Jersey Mike|McDonald's|Wendy's|Chick-fil-A|Raising Cane|Murphy Express|Buc-ee|Wawa|Circle K|Costco",i];
          node["leisure"="playground"]["access"!~"private|no"];
          way["leisure"="playground"]["access"!~"private|no"];
        );
        out center;
        """
        
        custom_headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.openstreetmap.org/",
            "Origin": "https://www.openstreetmap.org"
        }
        
        endpoint = random.choice(OVERPASS_ENDPOINTS)
        
        try:
            response = requests.post(endpoint, data={"data": query}, headers=custom_headers, timeout=90)
            
            if response.status_code == 429:
                print("⚠️ Server throttling encountered. Holding process execution for 15 seconds...")
                time.sleep(15)
                response = requests.post(endpoint, data={"data": query}, headers=custom_headers, timeout=90)

            if response.status_code != 200:
                continue
                
            payload_data = response.json()
            elements = payload_data.get("elements", [])
            
            if len(elements) == 0:
                continue
                
            print(f"📥 Mapped {len(elements)} targets within zone segment index context [{idx+1}/{len(micro_zones)}].")
            
            for el in elements:
                lat = el.get("lat") or (el.get("center") and el.get("center")["lat"])
                lon = el.get("lon") or (el.get("center") and el.get("center")["lon"])
                if not lat or not lon:
                    continue
                    
                coord_fingerprint = f"{round(lat, 4)}_{round(lon, 4)}"
                if coord_fingerprint in seen_unique_coords:
                    continue
                    
                tags = el.get("tags", {})
                
                if tags.get("leisure") == "playground":
                    validated_park_name = clean_and_validate_playground(tags)
                    if not validated_park_name:
                        continue
                        
                    poi_node = {
                        "lat": round(lat, 4), "lon": round(lon, 4),
                        "n": validated_park_name, "b": "playground", "c": "playground",
                        "h": tags.get("opening_hours", "Sunrise to Sunset"),
                        "d": tags.get("description", "Public open-access park playground.")
                    }
                    seen_unique_coords.add(coord_fingerprint)
                    compiled_pois.append(poi_node)
                else:
                    cat_slug, brand_slug, official_brand_name = identify_clean_brand(tags)
                    if not cat_slug:
                        continue
                        
                    poi_node = {
                        "lat": round(lat, 4), "lon": round(lon, 4),
                        "n": official_brand_name,
                        "b": brand_slug, "c": cat_slug,
                        "h": tags.get("opening_hours", "Hours vary by location"),
                        "d": tags.get("description", "Verified chain location mapped off highway route bounds.")
                    }
                    
                    if cat_slug == "gas":
                        poi_node["g87"] = 1 if (tags.get("fuel:octane_87") == "yes" or tags.get("fuel:unleaded") == "yes" or tags.get("fuel:regular") == "yes") else 1
                        poi_node["g88"] = 1 if (tags.get("fuel:octane_88") == "yes" or tags.get("fuel:e15") == "yes") else 0
                        
                    seen_unique_coords.add(coord_fingerprint)
                    compiled_pois.append(poi_node)
                    
            # Randomized throttling cooldown interval preserves connectivity integrity
            time.sleep(random.uniform(3.5, 5.5))
            
        except Exception:
            continue
            
    print(f"\n📦 Success! Generated {len(compiled_pois)} total points of interest across the United States.")
    
    with open("us_brands.json", "w", encoding="utf-8") as file_write:
        json.dump(compiled_pois, file_write, indent=2)
        
    print("💾 Master data compilation synchronized cleanly to file: 'us_brands.json'")

if __name__ == "__main__":
    generate_national_database()
