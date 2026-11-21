"""DOR land use and sale qualification code groups for the Phase 1 backtest.

Source: Florida DOR, 2026 NAL, SDF and NAP Users Guide, field 8 (DOR_UC, pages 5 to 7) and
field 55 (QUAL_CD1, pages 17 to 18). Opened and read on 2026-11-21:
https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/User%20Guides/2026%20Users%20guide%20and%20quick%20reference/2026_NAL_SDF_NAP_Users_Guide.pdf

Codes are three-digit strings, "000" to "099". Every code in that range sits in exactly one group.
"""


def _r(a: int, b: int) -> set[str]:
    return {f"{i:03d}" for i in range(a, b + 1)}


# Vacant land that can be built on. 099 is "acreage not zoned agricultural", open acreage.
VACANT = {"000", "010", "040", "070", "099"}

# 050 improved agricultural to 069 ornamentals. Counted as open land at every T,
# even when a farmhouse sits on it.
AGRICULTURAL = _r(50, 69)

# Excluded at every T. 009 residential common areas (HOA land, retention), 076 cemeteries,
# 080 to 089 government (includes 082 forests and parks), 091 utilities and canals,
# 094 rights of way, 095 rivers and lakes, 096 waste land, marsh, swamps, borrow pits,
# 097 classified-use parkland and recharge land, 098 centrally assessed (railroads).
NEVER_DEVELOPABLE = {"009", "076", "091", "094", "095", "096", "097", "098"} | _r(80, 89)

# Neither open nor excluded, and no building expected: 090 leaseholds on government land,
# 092 mining lands, 093 subsurface rights. Kept out of open acres, not counted as built.
OTHER = {"090", "092", "093"}

# Everything else is an improved use (residential, commercial, industrial, institutional).
IMPROVED = _r(0, 99) - VACANT - AGRICULTURAL - NEVER_DEVELOPABLE - OTHER

# Residential improved codes. A parcel here counts at least 1 home even if NO_RES_UNT is blank.
RESIDENTIAL = {"001", "002", "004", "005", "006", "007", "008", "003"}

# Arm's-length sales "qualified and included in sales ratio analysis" (guide, page 17).
# 03 to 06 are arm's length but excluded (property changed after sale, or multi-parcel prices),
# so their price does not describe this one parcel as it is on the roll.
MARKET_QUAL = {"01", "02"}

GROUPS = {"vacant": VACANT, "agricultural": AGRICULTURAL, "never_developable": NEVER_DEVELOPABLE,
          "other": OTHER, "improved": IMPROVED}

# Last year whose home count is complete in the 2026 roll. Set from reports/01_audit.md.
LAST_FULL_YEAR = 2024


def group_of(code: str) -> str:
    for name, s in GROUPS.items():
        if code in s:
            return name
    return "unknown"


assert sum(len(s) for s in GROUPS.values()) == 100, "groups must partition 000-099"
