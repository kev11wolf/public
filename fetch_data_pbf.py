import json
import os
import sys
import osmium

# Expanded Filter Profiles mapping directly to your HTML configuration options
RELIGIOUS_BLACKLIST = [
    'church', 'ministries', 'baptist', 'methodist', 'catholic', 'lutheran', 
    'presbyterian', 'episcopal', 'synagogue', 'mosque', 'temple', 'parish', 
    'christian', 'chapel', 'fellowship', 'worship', 'adventist', 'saints'
]

SCHOOL_PRIVATE_BLACKLIST = [
    'school', 'academy', 'elementary', 'middle', 'high', 'charter', 
    'daycare', 'childcare', 'preschool', 'kindergarten', 'learning center',
    'private', 'subdivision', 'hoa', 'apartment', 'condo', 'townhome', 
    'club', 'resort', 'golf', 'fitness', 'ymca', 'campground', 'hotel', 'motel'
]

COMBINED_PLAYGROUND_BLACKLIST = RELIGIOUS_BLACKLIST + SCHOOL_PRIVATE_BLACKLIST
PUBLIC_PARK_KEYWORDS = ['park', 'public', 'community', 'recreation', 'civic', 'city', 'town', 'county', 'municipal']

class NationalPOIExtractor(osmium.SimpleHandler):
    def __init__(self):
        super(NationalPOIExtractor, self).__init__()
        self.output_records = []
        self.seen_keys = set()

    def load_existing_favorites(self):
        """Loads persistent repository favorites so they are never lost during file rebuilds."""
        if os.path.exists("favorites.json"):
            try:
                with open("favorites.json", "r", encoding="utf-8") as file:
                    favs = json.load(file)
                    for item in favs:
                        key = f"{round(float(item['lat']), 4)}_{round(float(item['lon']), 4)}_{item['b']}"
                        self.seen_keys.add(key)
                        item["is_repo_fav"] = True # Flag item for frontend tracking identification
                        self.output_records.append(item)
                print(f"Loaded {len(favs)} global saved favorites into baseline matrix.")
            except Exception as e:
                print(f"Favorites file skipped: {e}")

    def process_node_tags(self, tags, lat, lon):
        if not lat or not lon:
            return

        name = tags.get('name', '')
        brand = tags.get('brand', '').lower()
        name_lower = name.lower()
        leisure = tags.get('leisure', '').lower()
        highway = tags.get('highway', '').lower()
        amenity = tags.get('amenity', '').lower()
        tourism = tags.get('tourism', '').lower()

        b_slug, c_tag, desc = None, "food", "Official location."

        # Fast String Token Lookups
        if "chick-fil-a" in brand or "chick-fil-a" in name_lower:
            b_slug = "chickfila"
        elif "mcdonald" in brand or "mcdonald" in name_lower:
            b_slug = "mcdonalds"
        elif "chipotle" in brand or "chipotle" in name_lower:
            b_slug = "chipotle"
        elif "starbucks" in brand or "starbucks" in name_lower:
            b_slug = "starbucks"
        elif "wendy" in brand or "wendy" in name_lower:
            b_slug = "wendys"
        elif "raising cane" in brand or "raising cane" in name_lower:
            b_slug = "raisingcanes"
        elif "jersey mike" in brand or "jersey mike" in name_lower:
            b_slug = "jerseymikes"
        elif "sheetz" in brand or "sheetz" in name_lower:
            b_slug, c_tag = "sheetz", "gas"
        elif "buc-ee" in brand or "buc-ee" in name_lower:
            b_slug, c_tag = "bucees", "gas"
        elif "wawa" in brand or "wawa" in name_lower:
            b_slug, c_tag = "wawa", "gas"
        elif "circle k" in brand or "circle k" in name_lower:
            b_slug, c_tag = "circlek", "gas"
            
        # Specialized Infrastructure Mappings Matching Your Select Dropdowns
        elif highway == "rest_area":
            b_slug, c_tag, desc = "highway_rest", "highway", "State-maintained highway rest area."
        elif amenity == "toilets" and highway == "services":
            b_slug, c_tag, desc = "highway_toilets", "highway", "Public corridor sanitation restroom facility."
        elif amenity == "hospital":
            b_slug, c_tag, desc = "hospital", "medical", "Major emergency medical care facility hospital."
        elif amenity == "veterinary":
            b_slug, c_tag, desc = "veterinary", "medical", "Professional veterinary medical clinic facility."
        elif boundary := tags.get('boundary', '').lower() == 'national_park' or leisure == 'national_park':
            b_slug, c_tag, desc = "national_park", "parks", "National park protected preserve boundary area."
        elif leisure == "nature_reserve":
            b_slug, c_tag, desc = "nature_reserve", "parks", "Protected environmental nature reserve area."
        elif tourism == "attraction":
            b_slug, c_tag, desc = "attraction", "parks", "Public tourist attraction point of interest."
        elif tourism == "viewpoint":
            b_slug, c_tag, desc = "tourism_viewpoint", "tourism", "Scenic overlook viewpoint vantage spot."
        elif leisure == "dog_park":
            b_slug, c_tag, desc = "tourism_dogpark", "tourism", "Fenced public dog park community facility."
            
        # Strict Playground Access Filter Layer
        elif leisure == "playground":
            if tags.get('access', '').lower() in ['private', 'no', 'customers', 'residents', 'hoa']:
                return
            meta = f"{name} {tags.get('operator', '')} {tags.get('description', '')}".lower()
            if any(kw in meta for kw in COMBINED_PLAYGROUND_BLACKLIST):
                return
            if not any(kw in meta for kw in PUBLIC_PARK_KEYWORDS) and 'park' not in tags.get('mapRef', '').lower():
                return
            b_slug, c_tag, desc = "playground", "playground", "Secular public playground asset in verified municipal park zones."
            if not name: name = "Public Park Playground"

        if not b_slug:
            return

        record_key = f"{round(lat, 4)}_{round(lon, 4)}_{b_slug}"
        if record_key in self.seen_keys:
            return

        record = {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "n": name or f"{b_slug.replace('_', ' ').title()} Spot",
            "b": b_slug,
            "c": c_tag,
            "h": tags.get('opening_hours', '24/7' if c_tag in ['gas', 'highway'] else 'Varies'),
            "d": desc
        }

        # Dynamic Fuel Attributes
        if c_tag == "gas":
            record["g87"] = 1
            record["g88"] = 1 if b_slug == "sheetz" else 0

        self.output_records.append(record)
        self.seen_keys.add(record_key)

    def node(self, n):
        if n.tags:
            try: self.process_node_tags(dict(n.tags), n.location.lat, n.location.lon)
            except osmium.InvalidLocationError: pass

    def way(self, w):
        if w.tags and len(w.nodes) > 0:
            try: self.process_node_tags(dict(w.tags), w.nodes[0].lat, w.nodes[0].lon)
            except osmium.InvalidLocationError: pass

if __name__ == "__main__":
    output_filename = "us_brands.json"
    pbf_target = "region_map.osm.pbf"

    if not os.path.exists(pbf_target):
        print("![ERROR] Local map data snapshot layer file was not generated.")
        sys.exit(1)

    extractor = NationalPOIExtractor()
    extractor.load_existing_favorites()
    
    print("Executing high-speed streaming local extraction index build pass...")
    extractor.apply_file(pbf_target, locations=True)

    with open(output_filename, "w", encoding="utf-8") as file:
        json.dump(extractor.output_records, file, indent=2)
    print(f"Completed! Native index file array updated with {len(extractor.output_records)} rows.")
