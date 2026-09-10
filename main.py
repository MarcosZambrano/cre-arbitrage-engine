from configManager import ConfigManager
from browserManager import BrowserManager
from loopNetScraper import LoopNetScraper
from valuationEngine import ValuationEngine

config = ConfigManager()

browserManager = BrowserManager()
browserManager.run()

loopNetScraper = LoopNetScraper(driver=browserManager.driver, config=config, browser=browserManager)
loopNetScraper.search()
listings = loopNetScraper.scrape_listing_cards()

valuationEngine = ValuationEngine(listings=listings, config=config)
baseline, type_of_baseline = valuationEngine.calculate_baseline()
valuationEngine.calculate_arbitrage_listing(baseline)
valuationEngine.alert_threshold()

