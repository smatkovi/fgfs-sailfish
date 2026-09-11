#!/usr/bin/env python3
"""Turn FGData's apt.dat.gz into small per-country airport lists.

The picker wants: country -> large or small -> the list.  Parsing 27000
airports out of a 27 MB compressed file at every start would be absurd, and
one big JSON would be slow to load in QML, so this runs once and writes one
small file per country plus an index.

Large versus small is decided by the longest hard runway:
  >= 1800 m of asphalt or concrete counts as large.
That is roughly what a narrowbody airliner needs, and it puts the airports
one would actually fly a jet into on one list and the grass strips on the
other.  Airports with no runway at all (heliports, water) are dropped.

Both runway record formats are handled.  This file is a hybrid: 33721 rows
of the 1000-format (type 100, length computed from the two end positions)
and 60383 of the old 810-format (type 10, length given in feet).  Taking
only one of them would lose two thirds of the airports.

Usage:
    make-airports.py <apt.dat.gz> <output-dir>
"""

import gzip
import json
import math
import os
import sys

# ICAO prefix -> country.  Two-letter keys are tried first, then one-letter,
# so "ED" (Germany) wins over "E" (northern Europe) and K/C/Y stay whole.
ICAO = {
    "AG": "Solomon Islands", "AN": "Nauru", "AY": "Papua New Guinea",
    "BG": "Greenland", "BI": "Iceland", "BK": "Kosovo",
    "C":  "Canada",
    "DA": "Algeria", "DB": "Benin", "DF": "Burkina Faso", "DG": "Ghana",
    "DI": "Ivory Coast", "DN": "Nigeria", "DR": "Niger", "DT": "Tunisia",
    "DX": "Togo",
    "EB": "Belgium", "ED": "Germany", "EE": "Estonia", "EF": "Finland",
    "EG": "United Kingdom", "EH": "Netherlands", "EI": "Ireland",
    "EK": "Denmark", "EL": "Luxembourg", "EN": "Norway", "EP": "Poland",
    "ES": "Sweden", "ET": "Germany", "EV": "Latvia", "EY": "Lithuania",
    "FA": "South Africa", "FB": "Botswana", "FC": "Congo",
    "FD": "Eswatini", "FE": "Central African Republic", "FG": "Equatorial Guinea",
    "FH": "Saint Helena", "FI": "Mauritius", "FJ": "British Indian Ocean Territory",
    "FK": "Cameroon", "FL": "Zambia", "FM": "Madagascar", "FN": "Angola",
    "FO": "Gabon", "FP": "Sao Tome and Principe", "FQ": "Mozambique",
    "FS": "Seychelles", "FT": "Chad", "FV": "Zimbabwe", "FW": "Malawi",
    "FX": "Lesotho", "FY": "Namibia", "FZ": "DR Congo",
    "GA": "Mali", "GB": "Gambia", "GC": "Spain", "GE": "Spain",
    "GF": "Sierra Leone", "GG": "Guinea-Bissau", "GL": "Liberia",
    "GM": "Morocco", "GO": "Senegal", "GQ": "Mauritania", "GS": "Western Sahara",
    "GU": "Guinea", "GV": "Cape Verde",
    "HA": "Ethiopia", "HB": "Burundi", "HC": "Somalia", "HD": "Djibouti",
    "HE": "Egypt", "HH": "Eritrea", "HK": "Kenya", "HL": "Libya",
    "HR": "Rwanda", "HS": "Sudan", "HT": "Tanzania", "HU": "Uganda",
    "K":  "United States",
    "LA": "Albania", "LB": "Bulgaria", "LC": "Cyprus", "LD": "Croatia",
    "LE": "Spain", "LF": "France", "LG": "Greece", "LH": "Hungary",
    "LI": "Italy", "LJ": "Slovenia", "LK": "Czechia", "LL": "Israel",
    "LM": "Malta", "LN": "Monaco", "LO": "Austria", "LP": "Portugal",
    "LQ": "Bosnia and Herzegovina", "LR": "Romania", "LS": "Switzerland",
    "LT": "Turkey", "LU": "Moldova", "LV": "Palestine", "LW": "North Macedonia",
    "LX": "Gibraltar", "LY": "Serbia and Montenegro", "LZ": "Slovakia",
    "MB": "Turks and Caicos", "MD": "Dominican Republic", "MG": "Guatemala",
    "MH": "Honduras", "MK": "Jamaica", "MM": "Mexico", "MN": "Nicaragua",
    "MP": "Panama", "MR": "Costa Rica", "MS": "El Salvador",
    "MT": "Haiti", "MU": "Cuba", "MW": "Cayman Islands", "MY": "Bahamas",
    "MZ": "Belize",
    "NC": "Cook Islands", "NF": "Fiji", "NG": "Kiribati", "NI": "Niue",
    "NL": "Wallis and Futuna", "NS": "Samoa", "NT": "French Polynesia",
    "NV": "Vanuatu", "NW": "New Caledonia", "NZ": "New Zealand",
    "OA": "Afghanistan", "OB": "Bahrain", "OE": "Saudi Arabia", "OI": "Iran",
    "OJ": "Jordan", "OK": "Kuwait", "OL": "Lebanon", "OM": "United Arab Emirates",
    "OO": "Oman", "OP": "Pakistan", "OR": "Iraq", "OS": "Syria",
    "OT": "Qatar", "OY": "Yemen",
    "PA": "United States (Alaska)", "PH": "United States (Hawaii)",
    "PG": "Guam", "PJ": "Johnston Atoll", "PK": "Marshall Islands",
    "PL": "Kiribati", "PM": "United States (Midway)", "PT": "Micronesia",
    "PW": "United States (Wake)",
    "RC": "Taiwan", "RJ": "Japan", "RK": "South Korea", "RO": "Japan",
    "RP": "Philippines",
    "SA": "Argentina", "SB": "Brazil", "SC": "Chile", "SD": "Brazil",
    "SE": "Ecuador", "SF": "Falkland Islands", "SG": "Paraguay",
    "SI": "Brazil", "SJ": "Brazil", "SK": "Colombia", "SL": "Bolivia",
    "SM": "Suriname", "SN": "Brazil", "SO": "French Guiana", "SP": "Peru",
    "SS": "Brazil", "SU": "Uruguay", "SV": "Venezuela", "SW": "Brazil",
    "SY": "Guyana",
    "TA": "Antigua and Barbuda", "TB": "Barbados", "TD": "Dominica",
    "TF": "French Antilles", "TG": "Grenada", "TI": "US Virgin Islands",
    "TJ": "Puerto Rico", "TK": "Saint Kitts and Nevis", "TL": "Saint Lucia",
    "TN": "Caribbean Netherlands", "TQ": "Anguilla", "TR": "Montserrat",
    "TT": "Trinidad and Tobago", "TU": "British Virgin Islands",
    "TV": "Saint Vincent and the Grenadines", "TX": "Bermuda",
    "U":  "Russia",
    "UA": "Kazakhstan", "UB": "Azerbaijan", "UD": "Armenia", "UG": "Georgia",
    "UK": "Ukraine", "UM": "Belarus", "UT": "Uzbekistan",
    "VA": "India", "VC": "Sri Lanka", "VD": "Cambodia", "VE": "India",
    "VG": "Bangladesh", "VH": "Hong Kong", "VI": "India", "VL": "Laos",
    "VM": "Macau", "VN": "Nepal", "VO": "India", "VQ": "Bhutan",
    "VR": "Maldives", "VT": "Thailand", "VV": "Vietnam", "VY": "Myanmar",
    "WA": "Indonesia", "WB": "Malaysia", "WI": "Indonesia", "WM": "Malaysia",
    "WP": "Timor-Leste", "WQ": "Indonesia", "WR": "Indonesia", "WS": "Singapore",
    "Y":  "Australia",
    "Z":  "China",
    "ZK": "North Korea", "ZM": "Mongolia",
}

HARD = {"1", "2", "15"}          # asphalt, concrete, hard but unspecified
LARGE_METRES = 1800.0


# Where the identifier is no help, the position is.  A third of this file
# carries FAA identifiers such as "07MT" or "3C8", which have no ICAO prefix
# to look up at all, and a handful of other strips use local schemes.  These
# boxes are deliberately coarse and only consulted as a fallback, so an
# overlap at a border misfiles a grass strip rather than an airport anyone
# would search for.
BOXES = [
    ("United States (Alaska)",  51.0,  72.0, -170.0, -129.0),
    ("United States (Hawaii)",  18.0,  23.0, -161.0, -154.0),
    ("United States",           24.0,  49.5, -125.0,  -66.9),
    ("Canada",                  49.5,  84.0, -141.0,  -52.0),
    ("Mexico",                  14.5,  32.7, -118.5,  -86.7),
    ("Australia",              -44.0, -10.0,  112.0,  154.0),
    ("New Zealand",            -47.5, -34.0,  166.0,  179.0),
    ("Brazil",                 -34.0,   5.3,  -74.0,  -34.8),
    ("Russia",                  41.0,  78.0,   27.0,  190.0),
    ("China",                   18.0,  53.6,   73.5,  135.0),
    ("India",                    6.0,  35.5,   68.0,   97.5),
    ("South Africa",           -35.0, -22.0,   16.0,   33.0),
    ("Argentina",              -55.0, -21.8,  -73.6,  -53.6),
]


def country_of(icao, lat=None, lon=None):
    if len(icao) >= 2 and icao[:2] in ICAO:
        return ICAO[icao[:2]]
    if icao and icao[0] in ICAO:
        return ICAO[icao[0]]
    if lat is not None and lon is not None:
        for name, la0, la1, lo0, lo1 in BOXES:
            if la0 <= lat <= la1 and lo0 <= lon <= lo1:
                return name
    return "Other"


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    src, outdir = argv[1], argv[2]

    airports = []      # (icao, name, longest_hard_m, longest_any_m)
    cur = None

    def flush():
        if cur and cur["icao"] and (cur["hard"] > 0 or cur["any"] > 0):
            airports.append(cur)

    with gzip.open(src, "rt", encoding="latin-1", errors="replace") as f:
        for line in f:
            f0 = line.split()
            if not f0:
                continue
            code = f0[0]

            if code in ("1", "16", "17"):
                flush()
                # Heliports (16) and seaports (17) are read so that their
                # runway rows are not attributed to the previous airport,
                # but they are not collected.
                if code == "1" and len(f0) >= 6:
                    cur = {"icao": f0[4], "name": " ".join(f0[5:]),
                           "hard": 0.0, "any": 0.0,
                           "lat": None, "lon": None}
                else:
                    cur = None
                continue

            if cur is None:
                continue

            length = 0.0
            surface = ""
            if code == "100" and len(f0) >= 20:
                try:
                    la, lo = float(f0[9]), float(f0[10])
                    length = haversine(la, lo, float(f0[18]), float(f0[19]))
                    surface = f0[2]
                    if cur["lat"] is None:
                        cur["lat"], cur["lon"] = la, lo
                except ValueError:
                    continue
            elif code == "10" and len(f0) >= 11:
                # Old format.  A designation of "xxx" marks a taxiway, not a
                # runway - counting those would call every large airport's
                # taxi network a runway.
                if f0[3].lower().startswith("xxx"):
                    continue
                try:
                    length = float(f0[5]) * 0.3048      # feet
                    surface = f0[10]
                    if cur["lat"] is None:
                        cur["lat"], cur["lon"] = float(f0[1]), float(f0[2])
                except (ValueError, IndexError):
                    continue
            else:
                continue

            if length > cur["any"]:
                cur["any"] = length
            if surface in HARD and length > cur["hard"]:
                cur["hard"] = length

    flush()

    by_country = {}
    for a in airports:
        c = country_of(a["icao"], a.get("lat"), a.get("lon"))
        big = a["hard"] >= LARGE_METRES
        # icao, name, longest runway, and the coordinates: the app fetches
        # the TerraSync scenery around the departure airport before a
        # start, and needs them for that
        entry = [a["icao"], a["name"], int(round(max(a["hard"], a["any"]))),
                 round(a["lat"], 3) if a.get("lat") is not None else 0,
                 round(a["lon"], 3) if a.get("lon") is not None else 0]
        d = by_country.setdefault(c, {"large": [], "small": []})
        d["large" if big else "small"].append(entry)

    os.makedirs(outdir, exist_ok=True)
    index = []
    for c in sorted(by_country):
        d = by_country[c]
        # Longest runway first: the airport someone is looking for in a
        # country is usually its biggest.
        d["large"].sort(key=lambda e: -e[2])
        d["small"].sort(key=lambda e: -e[2])
        fn = "".join(ch if ch.isalnum() else "_" for ch in c) + ".json"
        with open(os.path.join(outdir, fn), "w") as f:
            json.dump(d, f, separators=(",", ":"))
        index.append({"name": c, "file": fn,
                      "large": len(d["large"]), "small": len(d["small"])})

    index.sort(key=lambda e: e["name"])
    with open(os.path.join(outdir, "countries.json"), "w") as f:
        json.dump(index, f, separators=(",", ":"))

    total = sum(e["large"] + e["small"] for e in index)
    big = sum(e["large"] for e in index)
    print("%d airports in %d countries (%d large, %d small)"
          % (total, len(index), big, total - big))
    other = [e for e in index if e["name"] == "Other"]
    if other:
        print("unmapped ICAO prefixes: %d airports under \"Other\""
              % (other[0]["large"] + other[0]["small"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
