from configManager import ConfigManager

import statistics
import pprint

class ValuationEngine:
    def __init__(self, listings, config: ConfigManager):
        self.listings = listings
        self.config = config

    def calculate_baseline(self):
        # Calculates the median baseline and defines it into a category of LOW or HIGH based on the amount of samples used for calculating the median.
        print("Performing calculations...")

        min_sample_size = 5

        valid_rates = [float(l["price"].replace("$", "").replace("SF/YR", "").strip()) for l in self.listings if l["price"]]
        
        if len(valid_rates) >= min_sample_size:
            return statistics.median(valid_rates), "HIGH"
        
        if len(valid_rates) > 0:
            # Method 2: Compute median anyway, but mark confidence low
            return statistics.median(valid_rates), "LOW"
            
        return None, "NO_DATA"

    def calculate_arbitrage_listing(self, baseline):
        # The arbitrage_delta_percentage is calculated here, in other words, the difference in percentage between the median and the price of the listing card.
        for card in self.listings:
            arbitrage_delta_percentage = (1 - (float(card["price"].replace("$", "").replace("SF/YR", "").strip()) / baseline)) * 100
            card["arbitrage_delta_percentage"] = arbitrage_delta_percentage

        pprint.pprint(self.listings)

    # This function will trigger the function to send an email notification to the user for the great real estate opportunity found in LoopNet.
    def alert_threshold(self):
        # print(self.config.arbitrage_threshold_pct)
        # This function will fire the alert to the notification manager if the threshold is surpassed.
        for card in self.listings:
            if card["arbitrage_delta_percentage"] >= self.config.arbitrage_threshold_pct:
                print("SEND EMAIL WITH NOTIFICATION MANAGER")
        
