import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from configManager import ConfigManager

class LoopNetScraper:
    # One tile per property type: Office, Retail, Industrial, Flex, Coworking,
    # Medical, Land, Restaurant, Lab. The last two sit outside the visible
    # carousel window.
    PROPERTY_TYPE_TILE = "div.property-type-icons div.property-type"

    def __init__(self, driver: webdriver.Chrome, config: ConfigManager):
        self.driver = driver
        self.config = config

        # --- 4. Find the search bar --------------------------------------------------
        #
        # Two inputs are named "geography"; the first is the visible one
        # (placeholder "Enter a location"), the second is hidden.

    def search(self):
        wait = WebDriverWait(self.driver, 10)


        print("\nFilters for the search: ")
        print(f"1. Max annual price for the search: {self.config.max_annual_budget}")
        print(f"2. Minimum square feet: {self.config.min_square_feet}")
        print(f"3. Property type desired: {self.config.property_type}")
        print(f"4. Location: {self.config.location}")

        # Selecting the wanted property_type (parameters that comes from config.yaml)
        self.select_property_type()

        geography_input = wait.until(
            EC.visibility_of_element_located(
                (By.NAME, "geography")
            )
        )

        # Type the location to search:
        geography_input.send_keys(f"{self.config.location}")

        # Press ENTER to start the search.
        geography_input.send_keys(Keys.ENTER)
        print("Clicked the basic search button")

        wait = WebDriverWait(self.driver, 10)

        # We are going add some filters so that only the listing cards that are between a range of values are shown (This allows us to perform less pagination)
        filters_element = wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, "//*[@id='quickSearchFilters']/div[2]/div[13]/button/span[1]")
            )
        )

        filters_element.click()

        wait = WebDriverWait(self.driver, 10)

        # Getting the Maximum Annual Rate Element and sending the configuration value to it.
        max_annual_rate_element = wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, "//*[@id='top']/section[1]/div[3]/div[2]/div/click-event-bridge/section/form/div[4]/section[3]/div/section[1]/div[1]/div[1]/div/div[3]/input")
            )
        )
        max_annual_rate_element.send_keys(f"{self.config.max_annual_budget}")

        # Getting the Minimum Space Range in SF (Square Foot)
        min_square_feet = self.driver.find_element(By.XPATH, "//*[@id='top']/section[1]/div[3]/div[2]/div/click-event-bridge/section/form/div[4]/section[3]/div/section[1]/div[5]/div[1]/div/div[1]/input")
        min_square_feet.send_keys(self.config.min_square_feet)

        search_button = self.driver.find_element(By.XPATH, "//*[@id='top']/section[1]/div[3]/div[2]/div/click-event-bridge/div/button[2]")
        search_button.click()

    def select_property_type(self):

        # Labels of every property-type tile, in the order the page lists them.
        tiles = self.driver.find_elements(By.CSS_SELECTOR, self.PROPERTY_TYPE_TILE)
        # .text is empty here: the <p> labels are visually hidden, so the rendered
        # text is "". textContent reads the DOM instead of the rendering.
        property_types = [
            tile.find_element(By.CSS_SELECTOR, "p.bold")
                .get_attribute("textContent").strip()
            for tile in tiles
        ]

        #Click the property-type tile matching `property_type` (config by default)."""
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

        