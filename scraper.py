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

    def assemble_dynamic_description(self, tags, b_slug, c_tag, base_desc):
        """Assembles available sub-tags into a concise, high-density metadata pipeline string."""
        pieces = []
        if base_desc:
            pieces.append(base_desc)
        
        operator = tags.get('operator')
        if operator:
            pieces.append(f"Operator: {operator}")
            
        fee = tags.get('fee', '').lower()
        if fee == 'yes':
            pieces.append("Paid Entry 💵")
        elif fee == 'no':
            pieces.append("Free Entry 🆓")

        drive_through = tags.get('drive_through', '').lower()
        if drive_through == 'yes':
            pieces.append("Drive-Through Available 🚗")

        if c_tag == "gas":
            if tags.get('fuel:diesel') == 'yes' or tags.get('fuel:hgv_diesel') == 'yes':
                pieces.append("⛽ Diesel")
            if tags.get('convenience') == 'yes':
                pieces.append("Convenience Market 🛒")

        elif c_tag == "food":
            cuisine = tags.get('cuisine')
            if cuisine:
                pieces.append(f"Cuisine: {cuisine.replace('_', ' ').title()}")
            if tags.get('outdoor_seating') == 'yes':
                pieces.append("Outdoor Seating 🪑")

        elif c_tag in ["parks", "campground"]:
            if tags.get('drinking_water') == 'yes':
                pieces.append("Drinking Water 💧")
            if tags.get('sanitary_dump_station') == 'yes':
                pieces.append("RV Dump Station 🚾")
            if tags.get('tents') == 'yes':
                pieces.append("Tents Mapped ⛺")
            if tags.get('caravans') == 'yes':
                pieces.append("RVs/Caravans Allowed 🚐")

        elif b_slug == "playground":
            surface = tags.get('surface')
            if surface:
                pieces.append(f"Surface: {surface.replace('_', ' ').title()}")
            if tags.get('lit') == 'yes':
                pieces.append("Lighted Facilities 💡")

        return " | ".join(pieces) if pieces else "Official verified corridor asset."

    def process_node_tags(self, tags, lat, lon):
        if not lat or not lon:
            return

        name = tags.get('name', '')
        name_lower = name.lower()
        leisure = tags.get('leisure', '').lower()
        highway = tags.get('highway', '').lower()
        amenity = tags.get('amenity', '').lower()
        tourism = tags.get('tourism', '').lower()

        # FIXED: Generates an ultra-aggressive serialized string across all keys and values to stop naming tag omissions
        all_tags_serialized = " ".join([f"{k}={v}" for k, v in tags.items()]).lower()

        matches = []

        # --- Sub-Block A: Food & Restaurant Profiles ---
        if "chick-fil-a" in all_tags_serialized or "chickfila" in all_tags_serialized:
            matches.append(("chickfila", "food", "Official Chick-fil-A location."))
        if "mcdonald" in all_tags_serialized:
            matches.append(("mcdonalds", "food", "Official McDonald's location."))
        if "chipotle" in all_tags_serialized:
            matches.append(("chipotle", "food", "Official Chipotle Mexican Grill."))
        if "starbucks" in all_tags_serialized:
            matches.append(("starbucks", "food", "Official Starbucks Coffee spot."))
        if "wendy" in all_tags_serialized:
            matches.append(("wendys", "food", "Official Wendy's fast food facility."))
        if "raising cane" in all_tags_serialized or "raisingcane" in all_tags_serialized:
            matches.append(("raisingcanes", "food", "Official Raising Cane's chicken fingers."))
        if "jersey mike" in all_tags_serialized or "jerseymikes" in all_tags_serialized:
            matches.append(("jerseymikes", "food", "Official Jersey Mike's sub shop."))
        if "culver" in all_tags_serialized:
            matches.append(("culvers", "food", "Official Culver's fresh frozen custard location."))
        if "shake shack" in all_tags_serialized or "shakeshack" in all_tags_serialized:
            matches.append(("shakeshack", "food", "Official Shake Shack roadside burger stand."))
        if "in-n-out" in all_tags_serialized or "innout" in all_tags_serialized:
            matches.append(("innout", "food", "Official In-N-Out Burger location."))
        if "potbelly" in all_tags_serialized:
            matches.append(("potbelly", "food", "Official Potbelly Sandwich Shop."))
            
        # --- Sub-Block B: Fuel & Travel Terminals ---
        if "sheetz" in all_tags_serialized:
            matches.append(("sheetz", "gas", "Official Sheetz travel center."))
        if "buc-ee" in all_tags_serialized or "bucees" in all_tags_serialized:
            matches.append(("bucees", "gas", "Official Buc-ee's mega travel center."))
        if "wawa" in all_tags_serialized:
            matches.append(("wawa", "gas", "Official Wawa station."))
        if "circle k" in all_tags_serialized or "circlek" in all_tags_serialized:
            matches.append(("circlek", "gas", "Official Circle K storefront."))
            
        # --- Sub-Block C: Retail Supply Logistics (Fixed Target Omission Gates) ---
        if "walmart" in all_tags_serialized:
            matches.append(("walmart", "shopping", "Walmart retail provision center."))
        
        # FIXED: Aggressive extraction check ensures Target retail assets pass while blocking archery/shooting ranges
        if "target" in all_tags_serialized:
            if not any(sport_kw in all_tags_serialized for sport_kw in ["shooting", "archery", "range", "club"]):
                matches.append(("target", "shopping", "Target shopping hub."))
                
        if "dollar tree" in all_tags_serialized or "dollartree" in all_tags_serialized:
            matches.append(("dollartree", "shopping", "Dollar Tree discount convenience location."))
        if "costco" in all_tags_serialized:
            matches.append(("costco", "shopping", "Costco Wholesale membership hub."))
        if "staples" in all_tags_serialized:
            matches.append(("staples", "shopping", "Staples business copy center."))
        if "ups store" in all_tags_serialized or "ups_store" in all_tags_serialized:
            matches.append(("upsstore", "shopping", "The UPS Store processing terminal."))
        if "bass pro" in all_tags_serialized or "cabela" in all_tags_serialized:
            matches.append(("basspro", "shopping", "Bass Pro Shops / Cabela's outfitters showroom."))

        # --- Sub-Block D: Infrastructure, Recreation, & Campgrounds ---
        if highway == "rest_area":
            matches.append(("highway_rest", "highway", "State-maintained highway rest area."))
        if amenity == "toilets":
            matches.append(("highway_toilets", "highway", "Public highway sanitation restroom facility."))
        if amenity == "hospital":
            matches.append(("hospital", "medical", "Major medical care emergency hospital."))
        if amenity == "veterinary":
            matches.append(("veterinary", "medical", "Professional veterinary medical clinic."))
        if tags.get('boundary', '').lower() == 'national_park' or leisure == 'national_park' or tags.get('boundary', '').lower() == 'protected_area':
            matches.append(("national_park", "parks", "National park protected preserve boundary."))
        if leisure == "nature_reserve" or leisure == "park" or tags.get('landuse', '').lower() == 'recreation_ground':
            matches.append(("nature_reserve", "parks", "Protected nature preserve or public green space."))
        if tourism == "attraction":
            matches.append(("attraction", "parks", "Public tourist attraction point."))
        if tourism == "viewpoint":
            matches.append(("tourism_viewpoint", "tourism", "Scenic overlook viewpoint vantage point."))
        if leisure == "dog_park" or tags.get('dog', '').lower() == 'leashed':
            matches.append(("tourism_dogpark", "tourism", "Fenced public dog park facility."))
        if tourism in ["camp_site", "caravan_site"] or tags.get('landuse', '').lower() == 'camp_site':
            matches.append(("campground", "campground", "Verified campground outdoor hospitality property."))
        
        if leisure == "playground":
            access_val = tags.get('access', '').lower()
            amenity_val = tags.get('amenity', '').lower()
            landuse_val = tags.get('landuse', '').lower()
            
            if access_val not in ['private', 'no', 'customers', 'residents', 'hoa'] and amenity_val != 'school' and landuse_val != 'education':
                meta = f"{name} {tags.get('operator', '')} {tags.get('description', '')}".lower()
                if not any(kw in meta for kw in COMBINED_PLAYGROUND_BLACKLIST):
                    matches.append(("playground", "playground", "Public recreation playground area asset."))

        # --- Committing and Filtering Execution Loop ---
        for b_slug, c_tag, base_desc in matches:
            record_key = f"{round(lat, 4)}_{round(lon, 4)}_{b_slug}"
            if record_key in self.seen_keys:
                continue

            rec_name = name
            if not rec_name:
                if b_slug == "playground":
                    rec_name = "Public Park Playground"
                elif b_slug == "campground":
                    rec_name = "Public/Private Campground Property"
                elif b_slug in ["nature_reserve", "national_park"]:
                    rec_name = "Public Nature Preserve Area"
                else:
                    rec_name = f"{b_slug.replace('_', ' ').title()} Spot"

            final_description = self.assemble_dynamic_description(tags, b_slug, c_tag, base_desc)

            record = {
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "n": rec_name,
                "b": b_slug,
                "c": c_tag,
                "h": tags.get('opening_hours', '24/7' if c_tag in ['gas', 'highway'] else 'Varies'),
                "d": final_description
            }

            if c_tag == "gas":
                record["g87"] = 1
                record["g88"] = 1 if b_slug == "sheetz" else 0

            self.output_records.append(record)
            self.seen_keys.add(record_key)

    # =====================================================================
    # --- PHASE 2: TRUE RADIAL GEOMETRIC CENTROID PARSING OVERHAULS -------
    # =====================================================================
    def node(self, n):
        if n.tags:
            try: 
                self.process_node_tags(dict(n.tags), n.location.lat, n.location.lon)
            except osmium.InvalidLocationError: 
                pass

    def way(self, w):
        if w.tags and len(w.nodes) > 0:
            try:
                lats = []
                lons = []
                for node in w.nodes:
                    try:
                        lats.append(node.lat)
                        lons.append(node.lon)
                    except osmium.InvalidLocationError:
                        continue
                if lats and lons:
                    centroid_lat = sum(lats) / len(lats)
                    centroid_lon = sum(lons) / len(lons)
                    self.process_node_tags(dict(w.tags), centroid_lat, centroid_lon)
            except Exception:
                pass

    def area(self, a):
        if a.tags:
            try:
                lats = []
                lons = []
                for ring in a.outer_rings():
                    for node in ring:
                        try:
                            lats.append(node.lat)
                            lons.append(node.lon)
                        except osmium.InvalidLocationError:
                            continue
                if lats and lons:
                    centroid_lat = sum(lats) / len(lats)
                    centroid_lon = sum(lons) / len(lons)
                    self.process_node_tags(dict(a.tags), centroid_lat, centroid_lon)
            except Exception:
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
    
    # FIXED: Re-architected standard executor blocks to bind an active Location Cache and AreaManager 
    # to synthesize and extract multipolygon corporate structures from relation elements cleanly
    src_reader = osmium.io.Reader(pbf_target)
    location_index = osmium.index.create_index("flex_mem")
    location_handler = osmium.NodeLocationsHandler(location_index)
    location_handler.pre_node_ways = True
    
    area_assembler = osmium.area.AreaManager()
    
    osmium.apply(src_reader, location_handler, area_assembler, extractor)
    src_reader.close()

    with open(output_filename, "w", encoding="utf-8") as file:
        json.dump(extractor.output_records, file, indent=2)
    print(f"Success! {state_slug} data sync complete. Rows saved: {len(extractor.output_records)}")
