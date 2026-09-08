"""Notes: parsing the square-footage text on a LoopNet listing card.

Run this file directly to see the regex applied to every case:

    python notes.py

The size <li> has no `name` attribute (only Price does), so it is located by
content and then parsed from text:

    SF_XPATH = ("//ul[contains(@class,'data-points')]"
                "/li[contains(., ' SF') and not(contains(., '/YR'))]")
"""

import re

# ([\d,]+)              group 1: digits or commas -> "64,533" whole
# (?:\s*-\s*([\d,]+))?  optional, non-capturing: dash + group 2 (upper bound)
# \s*SF                 anchor on the literal "SF" so years/house numbers miss
SIZE_RE = re.compile(r"([\d,]+)(?:\s*-\s*([\d,]+))?\s*SF")


def parse_sf(text):
    """Return (sf_min, sf_max) from a card's size line, or (None, None).

    int("64,533") raises, so the commas are stripped first. When there is no
    range, sf_max is set equal to sf_min - that way every listing carries both
    values and callers never have to check which form it was.
    """
    match = SIZE_RE.search(text)
    if not match:
        return None, None
    low = int(match.group(1).replace(",", ""))
    high = int(match.group(2).replace(",", "")) if match.group(2) else low
    return low, high


# (input, expected) - expectations are hand-traced, the run below checks them.
CASES = [
    # --- real strings from the Dallas industrial results page ---
    ("64,533 SF Industrial Space",           (64533, 64533)),
    ("135,000 SF Industrial Space",          (135000, 135000)),
    ("11,442 - 38,872 SF Industrial Spaces", (11442, 38872)),
    ("9,859 - 148,369 SF Space",             (9859, 148369)),
    ("2,684 - 30,182 SF Space",              (2684, 30182)),

    # --- variants that parse correctly ---
    ("1,200-4,800 SF Office Space",          (1200, 4800)),      # no spaces around dash
    ("850 SF Retail Space",                  (850, 850)),        # no commas
    ("1,000,000 SF Industrial Space",        (1000000, 1000000)),

    # --- no match, correctly ---
    ("Built in 1972",                        (None, None)),      # no "SF"
    ("Negotiable",                           (None, None)),      # no digits
    ("",                                     (None, None)),

    # --- GOTCHA 1: a price string does NOT return None ---------------------
    # The regex fails at "7" (next char is "."), slides forward, and matches
    # the "00" of ".00 SF". int("00") == 0, so you get a silent 0 SF listing.
    # This is why the XPath carries not(contains(., '/YR')): the filter is what
    # stops price text from ever reaching this function.
    ("$7.00 SF/YR",                          (0, 0)),

    # --- GOTCHA 2: an en dash silently loses the minimum --------------------
    # U+2013 is not the ASCII hyphen, so \s*-\s* does not match it. The regex
    # then matches "9,000 SF" alone and reports the UPPER bound as a fixed size.
    # Nothing on the current page uses en dashes, but if that changes, widen the
    # class to [-–—] to cover hyphen, en dash and em dash.
    ("5,000 – 9,000 SF Space",          (9000, 9000)),
]


if __name__ == "__main__":
    print(f"{'INPUT':42} {'g1':>11} {'g2':>10}   ->  RESULT")
    print("-" * 88)
    failures = 0
    for text, expected in CASES:
        match = SIZE_RE.search(text)
        group1 = repr(match.group(1)) if match else "-"
        group2 = repr(match.group(2)) if match and match.group(2) else "None"
        result = parse_sf(text)
        flag = "" if result == expected else f"   <-- expected {expected}"
        if result != expected:
            failures += 1
        print(f"{text!r:42} {group1:>11} {group2:>10}   ->  {result}{flag}")
    print("-" * 88)
    print(f"{len(CASES) - failures}/{len(CASES)} matched the hand-traced expectations.")
