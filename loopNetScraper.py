import re
import unicodedata
import urllib.parse
import pprint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from configManager import ConfigManager

HOMEPAGE = "https://www.loopnet.com/"

# LoopNet slugs a US location as "city-state" using the two-letter code, but an
# international one as "city--country" with a DOUBLE dash. Both forms verified
# live: dallas-tx, new-york-ny, paris--france, berlin--germany.
US_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
    "district of columbia": "dc", "florida": "fl", "georgia": "ga", "hawaii": "hi",
    "idaho": "id", "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv",
    "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm", "new york": "ny",
    "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
    "oregon": "or", "pennsylvania": "pa", "rhode island": "ri",
    "south carolina": "sc", "south dakota": "sd", "tennessee": "tn", "texas": "tx",
    "utah": "ut", "vermont": "vt", "virginia": "va", "washington": "wa",
    "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy",
}
US_STATE_CODES = set(US_STATES.values())

SIZE_RE = re.compile(r"([\d,]+)(?:\s*-\s*([\d,]+))?\s*SF") # Regex 

def parse_sf(text):

    """ Return (sf_min, sf_max) from a card's size line, or (None, None).
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

def slugify(text):
    """Lowercase ASCII slug; strips accents, joins words with single dashes."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return "-".join(text.split())


def location_slug(location):
    """Turn a human location into LoopNet's URL segment.

    "Dallas, TX"                -> dallas-tx        (US: one dash + state code)
    "San Francisco, California" -> san-francisco-ca (full state name accepted)
    "Paris, France"             -> paris--france    (international: TWO dashes)
    "Austin"                    -> austin           (no region given)
    """
    parts = [part.strip() for part in str(location).split(",") if part.strip()]
    if not parts:
        return ""

    city = slugify(parts[0])
    if len(parts) == 1:
        return city

    # Use the last part, so "Brooklyn, New York, NY" resolves its region as NY.
    region = parts[-1]
    key = slugify(region).replace("-", " ")

    if key in US_STATE_CODES:
        return f"{city}-{key}"
    if key in US_STATES:
        return f"{city}-{US_STATES[key]}"
    return f"{city}--{slugify(region)}"


class LoopNetScraper:
    # One tile per property type: Office, Retail, Industrial, Flex, Coworking,
    # Medical, Land, Restaurant, Lab. The last two sit outside the visible
    # carousel window. Only used by select_property_type(), which the URL-driven
    # search no longer needs - kept as a way to validate a config value.
    PROPERTY_TYPE_TILE = "div.property-type-icons div.property-type"

    def __init__(self, driver: webdriver.Chrome, config: ConfigManager, browser=None):
        self.driver = driver
        self.config = config
        # BrowserManager, needed for navigation. Every page load has to go through
        # browser.navigate(), which relaunches Chrome on the target URL.
        self.browser = browser

    def search_url(self):
        """Build the results URL, filters included, that the search form would produce.

        e.g. "Industrial" + "Dallas, TX" + min 25000 SF becomes
        https://www.loopnet.com/search/industrial-space/dallas-tx/for-lease/?min-space-size=25000

        Filtering through the URL rather than the filter panel is not merely
        tidier: the panel ends in a Search button click, and that click is a
        navigation, which Akamai rejects in any browser ChromeDriver has attached.
        """
        property_type = slugify(self.config.property_type)
        location = location_slug(self.config.location)

        # Both values are cast to int: max_annual_budget is a float in YAML, and
        # "500000.0" is not valid in the query string.
        params = {}
        if self.config.max_annual_budget:
            params["max-rent"] = int(self.config.max_annual_budget)
        if self.config.min_square_feet:
            params["min-space-size"] = int(self.config.min_square_feet)

        url = (
            "https://www.loopnet.com/search/"
            f"{property_type}-space/{location}/for-lease/"
        )
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return url

    def search(self):
        print("\nFilters for the search: ")
        print(f"1. Max annual price for the search: {self.config.max_annual_budget}")
        print(f"2. Minimum square feet: {self.config.min_square_feet}")
        print(f"3. Property type desired: {self.config.property_type}")
        print(f"4. Location: {self.config.location}")

        # One navigation, straight to the filtered results. The homepage visit,
        # the property-type click and the geography typeahead are all unnecessary
        # now that the URL encodes the property type - and since every page load
        # costs a Chrome relaunch, halving them halves the chance of a burn.
        url = self.search_url()
        print(f"\nSearching: {url}")
        self.driver = self.browser.navigate(url)

        title = self.driver.title or ""
        if "404" in title or "Page Not Found" in title:
            raise SystemExit(
                f"LoopNet has no results page for {self.config.location!r} "
                f"(slug: {location_slug(self.config.location)}).\n"
                "Coverage outside the US is partial: France, Germany and Spain "
                "resolve, while the UK, Canada and Italy return 404."
            )

        print(f"Results page: {title}")

    def scrape_listing_cards(self):
        listings = []
        """ This function takes a listing from a website and extracts the listing cards from it."""

        # listing_price = self.driver.find_elements(By.CSS_SELECTOR, "li[name='Price']")
        # listings_prices = [price.text for price in listing_price]
        # print(f"Listings prices: {listings_prices}")

        # listing_sizes = self.driver.find_elements(By.XPATH, "//ul[contains(@class,'data-points')]"
        #     "/li[contains(., ' SF') and not(contains(., '/YR'))]")
        # sizes = [parse_sf(size.text) for size in listing_sizes]
        # print(f"Listings sizes {sizes}")


        # listings_urls = self.driver.find_element(By.CSS_SELECTOR, "h4 a").get_attribute("href")
        # print(f"Listings urls: {listings_urls}")

        cards_elements = self.driver.find_elements(By.CSS_SELECTOR, "article.placard")
        for card in cards_elements:
            listing_price = card.find_element(By.CSS_SELECTOR, "li[name='Price']").text
            listing_size = parse_sf(card.find_element(By.XPATH, "//ul[contains(@class,'data-points')]").text)
            listing_url = card.find_element(By.CSS_SELECTOR, "h4 a").get_attribute("href")

            listing_price_num = float(listing_price.replace("$", "").replace("SF/YR", "").strip())
            # print("Listing price number ready for calculations: ", listing_price_num)
            listing_size_min = float(listing_size[0])

            listings.append({
                "price": listing_price,
                "size": listing_size,
                "property_type": self.config.property_type,
                "url": listing_url,
                "annual_total_rent_projection": listing_price_num * listing_size_min, # We are choosing the minimum size for the listing card.
            })

        print("Listings present for the search:\n\n")
        pprint.pprint(listings)

        return listings


    def select_property_type(self):
        """Click the property-type tile on the HOMEPAGE matching the config value.

        No longer part of search(), which encodes the type in the URL instead.
        Kept because it is the only check that a config property_type actually
        exists on the site.
        """
        # Labels of every property-type tile, in the order the page lists them.
        tiles = self.driver.find_elements(By.CSS_SELECTOR, self.PROPERTY_TYPE_TILE)
        # .text is empty here: the <p> labels are visually hidden, so the rendered
        # text is "". textContent reads the DOM instead of the rendering.
        property_types = [
            tile.find_element(By.CSS_SELECTOR, "p.bold")
                .get_attribute("textContent").strip()
            for tile in tiles
        ]

        wanted = self.config.property_type

        # The predicate form [.//p[...]] selects the TILE itself. Using
        # /ancestor::div[contains(@class,'property-type')] instead returns every
        # matching ancestor, and find_element takes the first in document order --
        # which is the outermost one, i.e. the whole 'property-type-icons' carousel.
        # Clicking that hits its centre point, which is why every property type
        # landed on the same tile regardless of the label.
        xpath = (
            "//div[contains(@class,'property-type-icons')]"
            "//div[contains(@class,'property-type')]"
            f"[.//p[normalize-space(text())='{wanted}']]"
        )

        try:
            tile = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except TimeoutException:
            raise SystemExit(
                f"No property type named {wanted!r} on the page.\n"
                f"Available: {', '.join(property_types)}"
            )

        # A JavaScript click, not tile.click(). The carousel is overlaid by
        # div.new-quick-search-wrap, so a native click is delivered to the overlay
        # and never reaches Angular's ng-click. It also works for tiles scrolled
        # out of view (Restaurant, Lab), which a native click cannot reach.
        self.driver.execute_script("arguments[0].click();", tile)

        WebDriverWait(self.driver, 10).until(
            lambda drv: "selected" in (tile.get_attribute("class") or "")
        )
        print(f"Property type selected: {wanted}")
