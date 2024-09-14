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

__version__ = "1.0.0"


def setup_web_driver(debug):
    # Set up Firefox options
    options = FirefoxOptions()
    options.headless = True  # Run in headless mode

    # Automatically downloads and sets up the latest GeckoDriver
    service = FirefoxService(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)

    # Create a WebDriverWait instance with a 10-second timeout
    wait = WebDriverWait(driver, 10)
    if debug:
        print("Web driver services created successfully.")
    return driver, wait


def load_site(driver, index, debug, value):
    if index == 0:
        driver.get("https://www.google.com/search?q=109gbp+to+xmr")
    elif index == 1:
        driver.get(f'https://changenow.io/?from=ltc&to=xmr&amountTo={value}')
        time.sleep(3)
    elif index == 2:
        driver.get(f'https://changenow.io/?from=gbp&to=ltc&fiatMode=true&amount=110')
        time.sleep(3)
    if debug:
        print(f"Site index{index}: Loaded successfully.")


def accept_cookies(wait, debug, cookies_element_id):
    # Wait for the accept cookies button element to be present and clickable
    cookies_button = wait.until(ec.element_to_be_clickable((By.ID, cookies_element_id)))
    cookies_button.click()
    if debug:
        print("Cookies accepted clicked successfully.")


def select_and_parse_xmr_value(wait, debug):
    # Wait for all input elements with the specified aria-label to be present
    input_elements = wait.until(
        ec.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[aria-label="Currency Amount Field"]')))
    if len(input_elements) > 1:
        # Select the second instance (index 1) if available
        second_input_element = input_elements[1]
        # Extract the value attribute
        value = second_input_element.get_attribute("value")
        if debug:
            print("XMR Value parsed successfully.")
        return value
    else:
        if debug:
            print("Less than two elements found with the specified aria-label.")


def select_and_parse_ltc_value(wait, debug):
    # Wait for the input element with the ID 'amount-field' to be present
    amount_field = wait.until(ec.presence_of_element_located((By.ID, 'amount-field')))
    # Extract the value attribute
    ltc_amount = amount_field.get_attribute("value")
    # Convert to floating point number
    ltc_amount_float = float(ltc_amount)
    if debug:
        print("Successfully scraped LTC amount value.")
    return ltc_amount_float


def select_and_parse_gbp_value(wait, debug):
    # Wait for the span element with the class name 'new-stepper-hints__rate' to be present
    span_element = wait.until(ec.presence_of_element_located((By.CLASS_NAME, 'new-stepper-hints__rate')))
    # Extract the text from the span element
    span_text = span_element.text
    # Use regular expression to extract the number after '=' and before 'GBP'
    match = re.search(r'~\s*(\d+\.?\d*)\s*GBP', span_text)
    if match:
        number = match.group(1)
        if debug:
            print(f"Extracted number: {number}")
        return number
    else:
        if debug:
            print("No number found in the span text.")


def calculate_final_price(debug, gbp_value, ltc_rate, xmr_fees_total):
    total_to_pay = float(gbp_value) * ltc_rate
    total_to_pay += xmr_fees_total
    if debug:
        print(f"Estimated costs after fees: £{round(total_to_pay, 2)}")
    return round(total_to_pay, 2)


def main():
    if "--version" in sys.argv:
        print(__version__)
        return
    print("Running application version", __version__)
    try:
        # Variables setup
        debug = False  # Enable for debug messages
        xmr_fees_total = 0.25  # Change when needed
        cookies_element_id = "L2AGLb"

        driver, wait = setup_web_driver(debug)
        # Search current XMR value of desired total
        load_site(driver, 0, debug, False)
        # Accept cookies pop up
        accept_cookies(wait, debug, cookies_element_id)
        # Store the current XMR total value
        value = select_and_parse_xmr_value(wait, debug)
        # Search LTC value of XMR total
        load_site(driver, 1, debug, value)
        # Store the current LTC total conversion rate
        ltc_rate = select_and_parse_ltc_value(wait, debug)
        # Get CHANGENOW's LTC/GBP conversion price
        load_site(driver, 2, debug, False)
        # Store CHANGENOW's current LTC trade price
        gbp_value = select_and_parse_gbp_value(wait, debug)
        # Calculate final estimated price with fees
        final_estimate = calculate_final_price(debug, gbp_value, ltc_rate, xmr_fees_total)
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
