import json
import os
import sys
import osmium

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

    def load_existing_dataset(self, filename):
        """Safely loads baseline database array using missing key protection templates."""
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if isinstance(data, list):
                        for item in data:
                            lat = item.get('lat')
                            lon = item.get('lon')
                            b_slug = item.get('b', 'unknown')
                            if lat is not None and lon is not None:
                                key = f"{round(float(lat), 4)}_{round(float(lon), 4)}_{b_slug}"
                                if key not in self.seen_keys:
                                    self.seen_keys.add(key)
                                    self.output_records.append(item)
                print(f"Successfully loaded {len(self.output_records)} existing state baseline points.")
            except Exception as e:
                print(f"![WARN] Baseline parsing skipped safely: {e}")

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
        shop = tags.get('shop', '').lower()

        b_slug, c_tag, desc = None, "food", "Official location."

        # Food & Restaurant Mappings
        if "chick-fil-a" in brand or "chick-fil-a" in name_lower:
            b_slug = "chickfila"
        elif "mcdonald" in brand or "mcdonald" in name_lower:
            b_slug = "mcdonalds"
        elif "chipotle" in brand or "chipotle" in name_lower:
            b_slug = "chipotle"
        elif "starbucks" in brand or "starbucks" in name_lower:
            b_slug = "starbucks"
        elif "wendy" in brand or "wendy" in name_lower:
            b_slug, desc = "wendys", "Official Wendy's fast food establishment."
        elif "raising cane" in brand or "raising cane" in name_lower:
            b_slug = "raisingcanes"
        elif "jersey mike" in brand or "jersey mike" in name_lower:
            b_slug = "jerseymikes"
        elif "culver" in brand or "culver" in name_lower:
            b_slug, desc = "culvers", "Official Culver's butterburgers & frozen custard facility."
        elif "shake shack" in brand or "shake shack" in name_lower:
            b_slug, desc = "shakeshack", "Official Shake Shack modern road-side burger stand."
        elif "in-n-out" in brand or "in-n-out" in name_lower or "innout" in brand:
            b_slug, desc = "innout", "Official In-N-Out Burger iconic fresh fast-food location."
        elif "potbelly" in brand or "potbelly" in name_lower:
            b_slug, desc = "potbelly", "Official Potbelly Sandwich Shop warm toasted sub shop."
            
        # Fuel Terminal Mappings
        elif "sheetz" in brand or "sheetz" in name_lower:
            b_slug, c_tag = "sheetz", "gas"
        elif "buc-ee" in brand or "buc-ee" in name_lower:
            b_slug, c_tag = "bucees", "gas"
        elif "wawa" in brand or "wawa" in name_lower:
            b_slug, c_tag = "wawa", "gas"
        elif "circle k" in brand or "circle k" in name_lower:
            b_slug, c_tag = "circlek", "gas"
            
        # Retail & Shopping Supply Mappings (New Additions Layer)
        elif "walmart" in brand or "walmart" in name_lower:
            b_slug, c_tag, desc = "walmart", "shopping", "Walmart retail store location for travel supply re-provisioning."
        elif "target" in brand or "target" in name_lower:
            b_slug, c_tag, desc = "target", "shopping", "Target retail store location featuring snacks and essentials."
        elif "dollar tree" in brand or "dollar tree" in name_lower:
            b_slug, c_tag, desc = "dollartree", "shopping", "Dollar Tree discount convenience shopping hub."
        elif "costco" in brand or "costco" in name_lower:
            b_slug, c_tag, desc = "costco", "shopping", "Costco Wholesale bulk club supply center."
        elif "staples" in brand or "staples" in name_lower:
            b_slug, c_tag, desc = "staples", "shopping", "Staples office supplies, tech, and travel print services node."
        elif "ups store" in brand or "ups store" in name_lower or "the ups store" in brand:
            b_slug, c_tag, desc = "upsstore", "shopping", "The UPS Store commercial parcel shipping and pack service node."

        # Infrastructure & Recreation Mappings
        elif highway == "rest_area":
            b_slug, c_tag, desc = "highway_rest", "highway", "State-maintained highway rest area."
        elif amenity == "toilets":
            b_slug, c_tag, desc = "highway_toilets", "highway", "Public corridor sanitation restroom facility."
        elif amenity == "hospital":
            b_slug, c_tag, desc = "hospital", "medical", "Major emergency medical care facility hospital."
        elif amenity == "veterinary":
            b_slug, c_tag, desc = "veterinary", "medical", "Professional veterinary medical clinic facility."
        elif tags.get('boundary', '').lower() == 'national_park' or leisure == 'national_park':
            b_slug, c_tag, desc = "national_park", "parks", "National park protected preserve boundary area."
        elif leisure == "nature_reserve":
            b_slug, c_tag, desc = "nature_reserve", "parks", "Protected environmental nature reserve area."
        elif tourism == "attraction":
            b_slug, c_tag, desc = "attraction", "parks", "Public tourist attraction point of interest."
        elif tourism == "viewpoint":
            b_slug, c_tag, desc = "tourism_viewpoint", "tourism", "Scenic overlook viewpoint vantage spot."
        elif leisure == "dog_park" or tags.get('dog', '').lower() == 'leashed':
            b_slug, c_tag, desc = "tourism_dogpark", "tourism", "Fenced public dog park community facility."
        elif leisure == "playground":
            if tags.get('access', '').lower() in ['private', 'no', 'customers', 'residents', 'hoa']:
                return
            if tags.get('amenity') == 'school' or tags.get('landuse') == 'education':
                return
            meta = f"{name} {tags.get('operator', '')} {tags.get('description', '')}".lower()
            if any(kw in meta for kw in COMBINED_PLAYGROUND_BLACKLIST):
                return
            if not any(kw in meta for kw in PUBLIC_PARK_KEYWORDS):
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

    def area(self, a):
        if a.tags:
            try:
                for ring in a.outer_rings():
                    for node in ring:
                        self.process_node_tags(dict(a.tags), node.lat, node.lon)
                        return 
            except:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("![ERROR] Missing target state name configuration parameter.")
        sys.exit(1)
        
    state_slug = sys.argv[1]
    os.makedirs("data", exist_ok=True)
    output_filename = f"data/{state_slug}_brands.json"
    pbf_target = "region_map.osm.pbf"

    if not os.path.exists(pbf_target):
        print(f"![ERROR] Local file layers missing for state slug: {state_slug}")
        sys.exit(1)

    extractor = NationalPOIExtractor()
    extractor.load_existing_dataset(output_filename)
    
    print(f"Running high-speed local stream extractor loop for state: {state_slug}...")
    extractor.apply_file(pbf_target, locations=True)

    with open(output_filename, "w", encoding="utf-8") as file:
        json.dump(extractor.output_records, file, indent=2)
    print(f"Success! {state_slug} data sync complete. Rows saved: {len(extractor.output_records)}")
