import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import time

load_dotenv()

SENDER_EMAIL = os.getenv("EMAIL")
SENDER_PASSWORD = os.getenv("APP_PASSWORD")

class NotificationDispatcher:
    def __init__(self):
        self.subject = ""
        self.content = ""

    def send_emails(self, baseline, type_of_baseline, alerts, location, property_type):
        try:
            # Establishing a connection to the SMTP Server.
            with smtplib.SMTP("smtp.gmail.com", 587) as connection:
                connection.ehlo()          
                connection.starttls()      
                connection.ehlo()          
                connection.login(user=SENDER_EMAIL, password=SENDER_PASSWORD)

                index = 0
                for alert in alerts:
                    content = f"""
                    ================================================================================
                                        COMMERCIAL ARBITRAGE OPPORTUNITY
                    ================================================================================

                    A new {alert['property_type']} listing has triggered an arbitrage pricing alert.

                    --------------------------------------------------------------------------------
                    FINANCIAL & ARBITRAGE METRICS
                    --------------------------------------------------------------------------------
                    Listed Rate:                   {alert['price']}
                    Baseline MarketMedian:              ${baseline:.2f} / SF / YR
                    Baseline Confidence Level (Based on the amount of samples): {type_of_baseline}
                    Arbitrage Delta (Δ):           +{alert['arbitrage_delta_percentage']:.1f}% BELOW MARKET

                    Est. Base Annual Rent:        ${alert['annual_total_rent_projection']:,.2f} / YR

                    --------------------------------------------------------------------------------
                    PROPERTY SPECS
                    --------------------------------------------------------------------------------
                    Property Type:                 {property_type}
                    Space Available:               {alert['size'][0]} - {alert['size'][1]}

                    --------------------------------------------------------------------------------
                    ACTION
                    --------------------------------------------------------------------------------
                    View Listing on LoopNet:       {alert['url']}
                    """

                    # Content structural generation
                    msg = EmailMessage()
                    msg["Subject"] = f"[ARBITRAGE ALERT] 🚨 +{alert["arbitrage_delta_percentage"]:.1f}% Below Market | {location})"
                    msg["From"] = SENDER_EMAIL
                    msg["To"] = f"marcos.d.zambrano@gmail.com"
                    msg.set_content(content)

                    # Single message transmission payload dispatch
                    try:
                        connection.send_message(msg)
                        print(f"[SUCCESS] Dispatched delivery of Arbitrage Alert Commercial Real Estate notification to marcos.d.zambrano@gmail.com")
                    except smtplib.SMTPException as recipient_err:
                        print(f"[DELIVERY FAILURE] Error sending email: {type(recipient_err).__name__} - {recipient_err}")
                        continue
                    
                    index = index + 1
                    time.sleep(5)

        except smtplib.SMTPAuthenticationError:
            print("[AUTHENTICATION CRITICAL] SMTP Gateway denied credentials. Verify your App Password settings.")
        except (smtplib.SMTPConnectError, OSError) as network_err:
            print(f"[NETWORK CRITICAL] Connection failed. Sockets could not resolve remote host: {network_err}")
