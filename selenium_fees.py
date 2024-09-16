import json
import os

from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from webdriver_manager.firefox import GeckoDriverManager
import time
import re
import sys

__version__ = "1.1.0"

settings_file = 'settings.json'

# Variables setup
item_purchase_price = 109  # Wanted item's purchase price
debug = False  # Enable for debug messages
xmr_fees_total = 0.5  # Change when needed
cookies_element_id = "L2AGLb"  # Change when needed


def setup_web_driver():
    # Set up Firefox options
    options = FirefoxOptions()
    options.headless = True  # Run in headless mode

    # Automatically downloads and sets up the latest GeckoDriver
    service = FirefoxService(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)

    # Create a WebDriverWait instance with a 10-second timeout
    wait = WebDriverWait(driver, 10)
    if debug:
        print("DEBUG: Web driver created successfully.")
    return driver, wait


def load_site(driver, index, xmr_trade_value):
    if index == 0:
        driver.get(f"https://www.google.com/search?q={item_purchase_price}gbp+to+xmr")
    elif index == 1:
        driver.get(f'https://changenow.io/?from=ltc&to=xmr&amountTo={xmr_trade_value}')
        time.sleep(3)
    elif index == 2:
        driver.get(f'https://changenow.io/?from=gbp&to=ltc&fiatMode=true&amount={item_purchase_price}')
        time.sleep(3)
    if debug:
        print(f"DEBUG: Site index{index}: Loaded successfully.")


def accept_cookies(wait):
    # Wait for the accept cookies button element to be present and clickable
    cookies_button = wait.until(ec.element_to_be_clickable((By.ID, cookies_element_id)))
    cookies_button.click()
    if debug:
        print("DEBUG: 'Accept' cookies button clicked successfully.")


def select_and_parse_xmr_value(wait):
    # Wait for all input elements with the specified aria-label to be present
    input_elements = wait.until(
        ec.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[aria-label="Currency Amount Field"]')))
    if len(input_elements) > 1:
        # Select the second instance (index 1) if available
        second_input_element = input_elements[1]
        # Extract the value attribute
        scraped_value = second_input_element.get_attribute("value")
        xmr_trade_value = float(scraped_value)
        if debug:
            print(f"DEBUG: XMR trade price scraped successfully: {xmr_trade_value}XMR.")
        return xmr_trade_value
    else:
        if debug:
            print("ERROR: Less than two elements found with the specified aria-label.")


def select_and_parse_ltc_value(wait):
    # Wait for the input element with the ID 'amount-field' to be present
    amount_field = wait.until(ec.presence_of_element_located((By.ID, 'amount-field')))
    # Extract the value attribute
    scraped_value = amount_field.get_attribute("value")
    xmr_to_ltc_value = float(scraped_value)
    if debug:
        print("DEBUG: Successfully scraped CHANGENOW'S XMR to LTC value.")
    return xmr_to_ltc_value


def select_and_parse_gbp_value(wait):
    # Wait for the span element with the class name 'new-stepper-hints__rate' to be present
    span_element = wait.until(ec.presence_of_element_located((By.CLASS_NAME, 'new-stepper-hints__rate')))
    # Extract the text from the span element
    span_text = span_element.text
    # Use regular expression to extract the number after '=' and before 'GBP'
    match = re.search(r'~\s*(\d+\.?\d*)\s*GBP', span_text)
    if match:
        scraped_number = match.group(1)
        one_ltc_in_gbp = float(scraped_number)
        if debug:
            print(f"DEBUG: Successfully scraped CHANGENOW's 1LTC to GBP value: {one_ltc_in_gbp}")
        return one_ltc_in_gbp
    else:
        if debug:
            print("ERROR: No number found in the span text.")


def calculate_final_price(one_ltc_to_gbp_value, xmr_to_ltc_rate, current_balance):
    gross_trade_price = one_ltc_to_gbp_value * xmr_to_ltc_rate
    if debug:
        print(f"DEBUG: Gross trade price: £{gross_trade_price}")
    # Round to the nearest penny
    rounded_trade_price = round(gross_trade_price, 2)
    if debug:
        print(f"DEBUG: Rounded trade price: £{rounded_trade_price}")
    # Add static XMR trade fees (conservative fees estimate)
    with_fees_trade_price = rounded_trade_price + xmr_fees_total
    if debug:
        print(f"DEBUG: With fees trade price: £{with_fees_trade_price}")
    # Remove current XMR balance
    final_trade_price = with_fees_trade_price - current_balance
    if debug:
        print(f"DEBUG: Final trade price: £{final_trade_price}")
    return final_trade_price


# Function to load settings from the JSON file
def load_settings():
    if not os.path.exists(settings_file):
        # If the file doesn't exist, create it with default settings
        save_settings({"balance": 0.0})
        if debug:
            print(f"DEBUG: File not found. Created new default settings file.")
    with open(settings_file, 'r') as f:
        settings = json.load(f)
        if debug:
            print(f"DEBUG: Successfully loaded settings file.")
    return settings


# Function to save settings to the JSON file
def save_settings(settings):
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)


# Function to update the balance value in settings
def update_balance(new_balance, settings):
    settings['balance'] = new_balance
    save_settings(settings)


def check_for_balance_update():
    # Load the current settings
    current_settings = load_settings()
    if input(f"Change balance[£{current_settings['balance']}]? (y/n): ") == "y":
        # Update the balance
        new_balance = float(input("Enter new balance: £"))
        update_balance(new_balance, current_settings)
        print(f"Balance updated to £{new_balance} .")
    return current_settings['balance']


def main():
    if "--version" in sys.argv:
        print(__version__)
        return
    print("Running application version", __version__)
    try:
        # Create or load balance file
        current_balance = check_for_balance_update()
        if debug:
            print("DEBUG: #### STARTED ####")
        # Create web driver and wait instances
        driver, wait = setup_web_driver()
        # Search current XMR value of desired total
        load_site(driver, 0, False)
        # Accept cookies pop up
        accept_cookies(wait)
        # Store the current trade price in XMR value
        xmr_trade_value = select_and_parse_xmr_value(wait)
        # Search LTC value of XMR trade price
        load_site(driver, 1, xmr_trade_value)
        # Store the current LTC total conversion rate
        xmr_to_ltc_rate = select_and_parse_ltc_value(wait)
        # Get CHANGENOW's LTC/GBP conversion price
        load_site(driver, 2, False)
        # Store CHANGENOW's current LTC to GBP trade price
        one_ltc_to_gbp_value = select_and_parse_gbp_value(wait)
        # Calculate final estimated price with fees
        final_estimate = calculate_final_price(one_ltc_to_gbp_value, xmr_to_ltc_rate, current_balance)
        # Close the driver instance
        driver.close()
        # Display the final estimate price
        print(f"Estimated trade price ~ £{final_estimate}")
        # Make user confirm closing
        input("Press Enter to exit...")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
