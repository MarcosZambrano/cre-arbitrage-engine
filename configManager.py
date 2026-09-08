import yaml
import os
from dotenv import load_dotenv

class ConfigManager:
    def __init__(self):
        load_dotenv()

        self.EMAIL = os.getenv("EMAIL")
        self.APP_NAME = os.getenv("APP_NAME")
        self.PASSWORD = os.getenv("APP_PASSWORD")

        with open("config.yaml", mode="r") as file:
            self.config = yaml.safe_load(file)

        self.max_annual_budget = self.config["filters"]["max_annual_budget"]
        self.min_square_feet = self.config["filters"]["min_square_feet"]
        self.property_type = self.config["search"]["property_type"]
        self.location = self.config["search"]["target_location"]
                
