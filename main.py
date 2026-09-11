from src.configManager import ConfigManager
from src.browserManager import BrowserManager
from src.loopNetScraper import LoopNetScraper
from src.valuationEngine import ValuationEngine

config = ConfigManager()

browserManager = BrowserManager()
browserManager.run()

loopNetScraper = LoopNetScraper(driver=browserManager.driver, config=config, browser=browserManager)
loopNetScraper.search()
listings = loopNetScraper.scrape_listing_cards()

valuationEngine = ValuationEngine(listings=listings, config=config)
baseline, type_of_baseline = valuationEngine.calculate_baseline()
valuationEngine.calculate_arbitrage_listing(baseline)
valuationEngine.alert_threshold(baseline=baseline, type_of_baseline=type_of_baseline)

