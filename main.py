from configManager import ConfigManager
from browserManager import BrowserManager
from loopNetScraper import LoopNetScraper

config = ConfigManager()

browserManager = BrowserManager()
browserManager.run()

loopNetScraper = LoopNetScraper(driver=browserManager.driver, config=config)
loopNetScraper.search()
