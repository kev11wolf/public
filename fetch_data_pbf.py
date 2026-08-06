import json
import os
import sys
import tempfile
import unicodedata

import osmium


PRIVATE_ACCESS = {
    "private", "no", "customers", "residents", "permit"
}

PLAYGROUND_BLACKLIST = {
    "church", "ministries", "baptist", "methodist", "catholic",
    "lutheran", "presbyterian", "episcopal", "synagogue", "mosque",
    "temple", "parish", "christian", "chapel", "fellowship",
    "worship", "adventist", "saints", "school", "academy",
    "elementary", "middle", "high school", "charter", "daycare",
    "childcare", "preschool", "kindergarten", "learning center",
    "private", "subdivision", "hoa", "apartment", "condo",
    "townhome", "resort", "golf", "fitness", "ymca",
    "campground", "hotel", "motel"
}

# aliases, slug, category, fallback display name
BRAND_RULES = (
    # ── Food ──────────────────────────────────────────────────────────────
    (("chickfila",), "chickfila", "food", "Chick-fil-A"),
    (("mcdonalds",), "mcdonalds", "food", "McDonald's"),
    (("chipotle",), "chipotle", "food", "Chipotle"),
    (("starbucks",), "starbucks", "food", "Starbucks"),
    (("wendys",), "wendys", "food", "Wendy's"),
    (("raisingcanes",), "raisingcanes", "food", "Raising Cane's"),
    (("jerseymikes",), "jerseymikes", "food", "Jersey Mike's"),
    (("culvers",), "culvers", "food", "Culver's"),
    (("shakeshack",), "shakeshack", "food", "Shake Shack"),
    (("innout", "innoutburger"), "innout", "food", "In-N-Out Burger"),
    (("potbelly",), "potbelly", "food", "Potbelly"),
    (("smithfields", "smithfieldschickenbarbq"), "smithfieldsbbq", "food", "Smithfield's BBQ"),
    (("baskinrobbins",), "baskinrobbins", "food", "Baskin-Robbins"),
    (("bojangles",), "bojangles", "food", "Bojangles"),
    (("cookout",), "cookout", "food", "Cook Out"),
    (("zaxbys",), "zaxbys", "food", "Zaxby's"),
    (("wafflehouse",), "wafflehouse", "food", "Waffle House"),
    (("crackerbarrel",), "crackerbarrel", "food", "Cracker Barrel"),
    (("panera", "panerabread"), "panera", "food", "Panera Bread"),
    (("fiveguys",), "fiveguys", "food", "Five Guys"),
    (("dunkin", "dunkindonuts"), "dunkin", "food", "Dunkin'"),
    (("krispykreme",), "krispykreme", "food", "Krispy Kreme"),
    (("whataburger",), "whataburger", "food", "Whataburger"),

    # ── Gas and travel ────────────────────────────────────────────────────
    (("sheetz",), "sheetz", "gas", "Sheetz"),
    (("bucees",), "bucees", "gas", "Buc-ee's"),
    (("wawa",), "wawa", "gas", "Wawa"),
    (("circlek",), "circlek", "gas", "Circle K"),
    (("quiktrip", "qt"), "quiktrip", "gas", "QuikTrip"),
    (("racetrac",), "racetrac", "gas", "RaceTrac"),
    (("speedway",), "speedway", "gas", "Speedway"),
    (("pilotflyingj", "flyingj", "pilottravel"), "pilotflyingj", "gas", "Pilot Flying J"),
    (("lovestravelstops", "loves"), "loves", "gas", "Love's Travel Stop"),
    (("travelcentersofamerica", "travelcenters", "ta"), "travelcenters", "gas", "TravelCenters of America"),
    (("petro",), "petro", "gas", "Petro Travel Center"),
    (("murphyusa", "murphyexpress"), "murphyusa", "gas", "Murphy USA"),

    # ── Grocery, retail, hardware, and outdoor ────────────────────────────
    (("walmart",), "walmart", "shopping", "Walmart"),
    (("target",), "target", "shopping", "Target"),
    (("dollartree",), "dollartree", "shopping", "Dollar Tree"),
    (("costco",), "costco", "shopping", "Costco"),
    (("staples",), "staples", "shopping", "Staples"),
    (("upsstore",), "upsstore", "shopping", "The UPS Store"),
    (("basspro", "cabelas"), "basspro", "shopping", "Bass Pro Shops / Cabela's"),
    (("lowes",), "lowes", "shopping", "Lowe's"),
    (("homedepot",), "homedepot", "shopping", "The Home Depot"),
    (("publix",), "publix", "shopping", "Publix"),
    (("foodlion",), "foodlion", "shopping", "Food Lion"),
    (("harristeeter",), "harristeeter", "shopping", "Harris Teeter"),
    (("aldi",), "aldi", "shopping", "ALDI"),
    (("lidl",), "lidl", "shopping", "Lidl"),
    (("kroger",), "kroger", "shopping", "Kroger"),
    (("samsclub",), "samsclub", "shopping", "Sam's Club"),
    (("bjswholesale", "bjs"), "bjs", "shopping", "BJ's Wholesale Club"),
    (("traderjoes",), "traderjoes", "shopping", "Trader Joe's"),
    (("dollargeneral",), "dollargeneral", "shopping", "Dollar General"),
    (("familydollar",), "familydollar", "shopping", "Family Dollar"),
    (("acehardware",), "acehardware", "shopping", "Ace Hardware"),
    (("tractorsupply",), "tractorsupply", "shopping", "Tractor Supply"),
    (("harborfreight",), "harborfreight", "shopping", "Harbor Freight"),
    (("rei",), "rei", "shopping", "REI"),
    (("academysports", "academyoutdoors"), "academy", "shopping", "Academy Sports + Outdoors"),
    (("campingworld",), "campingworld", "shopping", "Camping World"),

    # ── Pharmacy and medical ──────────────────────────────────────────────
    (("cvspharmacy", "cvs"), "cvs", "medical", "CVS Pharmacy"),
    (("walgreens",), "walgreens", "medical", "Walgreens"),
)


def normalize_text(value):
    """Normalize text so brand matching ignores spaces, punctuation, and accents."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode("ascii")
    return "".join(character for character in value.lower() if character.isalnum())


def first_tag(tags, *keys):
    """Return the first non-empty OSM tag from the supplied keys."""
    for key in keys:
        value = tags.get(key, "").strip()
        if value:
            return value
    return ""


def build_address(tags):
    """Build a readable address from standard OSM addr:* tags."""
    house_number = first_tag(tags, "addr:housenumber")
    street = first_tag(tags, "addr:street")
    unit = first_tag(tags, "addr:unit")

    street_line = " ".join(
        value for value in (house_number, street, unit) if value
    ).strip()

    city = first_tag(
        tags,
        "addr:city",
        "addr:town",
        "addr:village",
        "addr:hamlet",
        "addr:place"
    )

    state = first_tag(tags, "addr:state", "addr:province")
    postcode = first_tag(tags, "addr:postcode")

    state_line = " ".join(value for value in (state, postcode) if value)

    return ", ".join(
        value for value in (street_line, city, state_line) if value
    )


def build_display_name(tags, fallback_name):
    """
    Always prefer the actual mapped name first.
    The generic fallback is used only when no useful OSM name exists.
    """
    return first_tag(
        tags,
        "name",
        "official_name",
        "name:en",
        "short_name",
        "brand",
        "operator"
    ) or fallback_name


class NationalPOIExtractor:
    def __init__(self):
        self.records = []
        self.seen_keys = set()
        self.stats = {
            "processed": 0,
            "matched": 0,
            "duplicates": 0,
            "written": 0
        }

    def get_center(self, element):
        """Return a practical center point for OSM nodes, ways, and areas."""
        if element.is_node():
            try:
                return element.location.lat, element.location.lon
            except osmium.InvalidLocationError:
                return None, None

        coordinates = []

        if element.is_way():
            nodes = element.nodes
        elif element.is_area():
            nodes = [
                node
                for ring in element.outer_rings()
                for node in ring
            ]
        else:
            return None, None

        for node in nodes:
            try:
                coordinates.append((node.lat, node.lon))
            except osmium.InvalidLocationError:
                continue

        if not coordinates:
            return None, None

        lat = sum(point[0] for point in coordinates) / len(coordinates)
        lon = sum(point[1] for point in coordinates) / len(coordinates)

        return lat, lon

    def is_public_playground(self, tags):
        """Exclude obvious school, church, HOA, lodging, and private playgrounds."""
        if tags.get("access", "").lower().strip() in PRIVATE_ACCESS:
            return False

        if tags.get("amenity", "").lower().strip() == "school":
            return False

        if tags.get("landuse", "").lower().strip() == "education":
            return False

        text_to_check = " ".join([
            tags.get("name", ""),
            tags.get("operator", ""),
            tags.get("owner", ""),
            tags.get("description", ""),
            tags.get("website", "")
        ]).lower()

        return not any(term in text_to_check for term in PLAYGROUND_BLACKLIST)

    def get_brand_matches(self, tags):
        """Match configured brands using OSM name, brand, operator, and official name."""
        source_text = " ".join([
            tags.get("name", ""),
            tags.get("brand", ""),
            tags.get("operator", ""),
            tags.get("official_name", ""),
            tags.get("brand:wikidata", "")
        ])

        identity = normalize_text(source_text)
        matches = []

        for aliases, slug, category, fallback_name in BRAND_RULES:
            if any(alias in identity for alias in aliases):
                matches.append((slug, category, fallback_name))

        amenity = tags.get("amenity", "").lower().strip()

        # A Costco fuel station should appear under Gas, not only Shopping.
        if "costco" in identity and amenity == "fuel":
            matches = [
                match for match in matches
                if match[0] != "costco"
            ]
            matches.append(("costcogas", "gas", "Costco Gas"))

        return matches

    def get_generic_matches(self, tags):
        """Capture useful non-brand POIs using high-confidence OSM tags."""
        matches = []

        access = tags.get("access", "").lower().strip()
        amenity = tags.get("amenity", "").lower().strip()
        highway = tags.get("highway", "").lower().strip()
        leisure = tags.get("leisure", "").lower().strip()
        tourism = tags.get("tourism", "").lower().strip()
        boundary = tags.get("boundary", "").lower().strip()
        landuse = tags.get("landuse", "").lower().strip()
        emergency = tags.get("emergency", "").lower().strip()
        parking = tags.get("parking", "").lower().strip()

        # Gas and EV
        if amenity == "fuel":
            matches.append(("gas", "gas", "Gas Station"))

        if amenity == "charging_station":
            matches.append(("ev_charging", "ev", "EV Charging Station"))

        # Medical
        if amenity == "hospital":
            matches.append(("hospital", "medical", "Hospital"))

        if amenity == "clinic":
            matches.append(("clinic", "medical", "Medical Clinic / Urgent Care"))

        if amenity == "pharmacy":
            matches.append(("pharmacy", "medical", "Pharmacy"))

        if amenity == "veterinary":
            matches.append(("veterinary", "medical", "Veterinary Clinic"))

        if amenity == "dentist":
            matches.append(("dentist", "medical", "Dental Clinic"))

        if emergency in {"yes", "emergency_ward"}:
            matches.append(("emergency", "medical", "Emergency Care"))

        # Highway and travel
        if highway == "rest_area":
            matches.append(("highway_rest", "highway", "Highway Rest Area"))

        if highway == "services":
            matches.append(("highway_services", "highway", "Highway Service Area"))

        if amenity == "toilets" and access not in PRIVATE_ACCESS:
            matches.append(("highway_toilets", "highway", "Public Restroom"))

        if amenity == "parking" and (
            parking in {"truck", "hgv"}
            or tags.get("hgv", "").lower() == "yes"
        ):
            matches.append(("truck_parking", "highway", "Truck Parking"))

        if tourism == "information" and tags.get("information", "").lower() in {
            "visitor_centre", "office"
        }:
            matches.append(("visitor_center", "highway", "Visitor Center"))

        # Parks, campgrounds, and family recreation
        if (
            boundary == "national_park"
            or leisure == "national_park"
            or boundary == "protected_area"
        ):
            matches.append(("national_park", "parks", "Protected Area"))

        elif leisure == "nature_reserve":
            matches.append(("nature_reserve", "parks", "Nature Reserve"))

        elif leisure == "park" or landuse == "recreation_ground":
            matches.append(("parks", "parks", "Public Park"))

        if tourism == "attraction":
            matches.append(("attraction", "parks", "Tourist Attraction"))

        if tourism == "zoo":
            matches.append(("zoo", "parks", "Zoo"))

        if tourism == "museum":
            matches.append(("museum", "parks", "Museum"))

        if tourism in {"camp_site", "caravan_site"} or landuse == "camp_site":
            if access not in {"private", "no"}:
                matches.append(("campground", "campground", "Campground"))

        if amenity == "sanitary_dump_station":
            matches.append(("rv_dump", "campground", "RV Dump Station"))

        if leisure == "playground" and self.is_public_playground(tags):
            matches.append(("playground", "playground", "Public Playground"))

        if leisure == "water_park":
            matches.append(("splash_pad", "playground", "Water Park / Splash Pad"))

        if leisure == "slipway":
            matches.append(("boat_ramp", "tourism", "Boat Ramp"))

        # Tourism and outdoor
        if tourism == "viewpoint":
            matches.append(("tourism_viewpoint", "tourism", "Scenic Viewpoint"))

        if leisure == "dog_park":
            matches.append(("tourism_dogpark", "tourism", "Dog Park"))

        return matches

    def build_description(self, tags, category):
        """Build a compact useful detail string for the popup."""
        details = []

        operator = tags.get("operator", "").strip()
        if operator:
            details.append(f"Operator: {operator}")

        fee = tags.get("fee", "").lower().strip()
        if fee == "yes":
            details.append("Fee may apply")
        elif fee == "no":
            details.append("No fee listed")

        if category == "food":
            cuisine = tags.get("cuisine", "").replace("_", " ").strip()
            if cuisine:
                details.append(f"Cuisine: {cuisine.title()}")

            if tags.get("drive_through", "").lower() == "yes":
                details.append("Drive-through")

            if tags.get("outdoor_seating", "").lower() == "yes":
                details.append("Outdoor seating")

        if category == "gas":
            if (
                tags.get("fuel:diesel", "").lower() == "yes"
                or tags.get("fuel:hgv_diesel", "").lower() == "yes"
            ):
                details.append("Diesel available")

            if tags.get("convenience", "").lower() == "yes":
                details.append("Convenience store")

        if category == "ev":
            sockets = [
                key.replace("socket:", "").replace("_", " ")
                for key, value in tags.items()
                if key.startswith("socket:") and value.lower() in {"yes", "1"}
            ]

            if sockets:
                details.append(f"Connectors: {', '.join(sockets[:3])}")

        if category in {"parks", "campground", "playground"}:
            if tags.get("drinking_water", "").lower() == "yes":
                details.append("Drinking water")

            if tags.get("sanitary_dump_station", "").lower() == "yes":
                details.append("RV dump station")

            if tags.get("tents", "").lower() == "yes":
                details.append("Tent camping")

            if tags.get("caravans", "").lower() == "yes":
                details.append("RV / caravan access")

            if tags.get("toilets", "").lower() == "yes":
                details.append("Restrooms")

        return " | ".join(details)

    def create_record(self, tags, lat, lon, slug, category, fallback_name):
        """Create the JSON format consumed by the route explorer."""
        record = {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "n": build_display_name(tags, fallback_name),
            "b": slug,
            "c": category,
            "a": build_address(tags),
            "h": first_tag(tags, "opening_hours") or "Hours not listed",
            "d": self.build_description(tags, category)
        }

        phone = first_tag(tags, "contact:phone", "phone")
        website = first_tag(tags, "contact:website", "website", "url")

        if phone:
            record["phone"] = phone

        if website:
            record["website"] = website

        if category == "gas":
            record["g87"] = 1
            record["g88"] = 1 if slug == "sheetz" else 0

        return record

    def process_element(self, element):
        """Evaluate one OSM object and save qualifying POIs."""
        self.stats["processed"] += 1

        tags = dict(element.tags)
        if not tags:
            return

        lat, lon = self.get_center(element)
        if lat is None or lon is None:
            return

        matches = self.get_brand_matches(tags)
        matches.extend(self.get_generic_matches(tags))

        for slug, category, fallback_name in matches:
            self.stats["matched"] += 1

            dedupe_key = (
                f"{round(lat, 5)}_"
                f"{round(lon, 5)}_"
                f"{category}_"
                f"{slug}"
            )

            if dedupe_key in self.seen_keys:
                self.stats["duplicates"] += 1
                continue

            self.records.append(
                self.create_record(
                    tags,
                    lat,
                    lon,
                    slug,
                    category,
                    fallback_name
                )
            )

            self.seen_keys.add(dedupe_key)
            self.stats["written"] += 1

    def get_sorted_records(self):
        """Produce stable JSON ordering for cleaner Git diffs."""
        return sorted(
            self.records,
            key=lambda record: (
                record["c"],
                record["b"],
                record["n"].lower(),
                record["lat"],
                record["lon"]
            )
        )


def write_json_safely(output_filename, records):
    """Write atomically so a failed run cannot leave a broken JSON file."""
    output_directory = os.path.dirname(output_filename) or "."
    os.makedirs(output_directory, exist_ok=True)

    descriptor, temporary_filename = tempfile.mkstemp(
        dir=output_directory,
        prefix=".poi-output-",
        suffix=".json"
    )

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
            json.dump(records, output_file, indent=2, ensure_ascii=False)
            output_file.write("\n")

        os.replace(temporary_filename, output_filename)

    except Exception:
        if os.path.exists(temporary_filename):
            os.remove(temporary_filename)
        raise


def main():
    if len(sys.argv) != 2:
        print("Usage: python fetch_data_pbf.py <state-slug>")
        sys.exit(1)

    state_slug = sys.argv[1].strip().lower()
    pbf_filename = "region_map.osm.pbf"
    output_filename = f"data/{state_slug}_brands.json"

    if not os.path.exists(pbf_filename):
        print(f"[ERROR] Missing downloaded PBF file: {pbf_filename}")
        sys.exit(1)

    extractor = NationalPOIExtractor()

    print(f"Starting POI extraction for: {state_slug}")
    print("Processing OSM nodes, ways, and areas...")

    processor = (
        osmium.FileProcessor(pbf_filename)
        .with_locations()
        .with_areas()
    )

    for osm_object in processor:
        extractor.process_element(osm_object)

    records = extractor.get_sorted_records()
    write_json_safely(output_filename, records)

    print(f"Completed: {state_slug}")
    print(f"OSM elements processed: {extractor.stats['processed']:,}")
    print(f"Potential matches: {extractor.stats['matched']:,}")
    print(f"Duplicates skipped: {extractor.stats['duplicates']:,}")
    print(f"POIs written: {len(records):,}")
    print(f"Saved to: {output_filename}")


if __name__ == "__main__":
    main()
