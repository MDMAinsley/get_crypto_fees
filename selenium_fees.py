from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from webdriver_manager.firefox import GeckoDriverManager
from alive_progress import alive_bar
import time
import re
import sys
import json
import os
import logging


__version__ = "2.1.3"

settings_file = 'settings.json'

# Variables setup
item_purchase_price = 109  # Wanted item's purchase price
run_headless = True  # Disable to see the browser
xmr_fees_total = 0.5  # Change when needed
cookies_element_id = "L2AGLb"  # Change when needed

# Create and configure logger
logging.basicConfig(filename="GetFees.log",
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filemode='w',
                    level=logging.DEBUG)


# Function to create the webdriver instance with necessary settings and wait conditions
def setup_web_driver(headless):
    # Set up Firefox options
    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")  # Enable headless mode explicitly

    # Automatically downloads and sets up the latest GeckoDriver
    service = FirefoxService(GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)

    # Create a WebDriverWait instance with a 10-second timeout
    wait = WebDriverWait(driver, 10)
    logging.debug("Webdriver instance created succesfully.")
    return driver, wait


# Function to handle different website loading on current webdriver instance
def load_site(driver, index, xmr_trade_value):
    if index == 0:
        driver.get(f"https://www.google.com/search?q={item_purchase_price}gbp+to+xmr")
    elif index == 1:
        driver.get(f'https://changenow.io/?from=ltc&to=xmr&amountTo={xmr_trade_value}')
        time.sleep(3)
    elif index == 2:
        driver.get(f'https://changenow.io/?from=gbp&to=ltc&fiatMode=true&amount={item_purchase_price}')
        time.sleep(3)
    logging.debug(f"Site index{index}: Loaded successfully.")


# Function to accept Googles cookies pop-up
def accept_cookies(wait):
    # Wait for the accept cookies button element to be present and clickable
    cookies_button = wait.until(ec.element_to_be_clickable((By.ID, cookies_element_id)))
    cookies_button.click()
    logging.debug("'Accept' cookies button clicked successfully.")


# Function to obtain the current GBP item price in XMR using Google's latest conversion rate
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
        logging.debug(f"XMR trade price scraped successfully: {xmr_trade_value}XMR.")
        return xmr_trade_value
    else:
        logging.fatal("Less than two elements found with the specified aria-label.")


# Function to obtain the current XMR item value in LTC on CHANGENOW's platform
def select_and_parse_ltc_value(wait):
    # Wait for the input element with the ID 'amount-field' to be present
    amount_field = wait.until(ec.presence_of_element_located((By.ID, 'amount-field')))
    # Extract the value attribute
    scraped_value = amount_field.get_attribute("value")
    xmr_to_ltc_value = float(scraped_value)
    logging.debug(f"Successfully scraped CHANGENOW's XMR to LTC value: {xmr_to_ltc_value}")
    return xmr_to_ltc_value


# Function to obtain to current LTC to GBP trade value on CHANGENOW's platform
def select_and_parse_gbp_value(wait, retries=5):
    for attempt in range(retries):
        try:
            # Wait for the span element with the class name 'new-stepper-hints__rate' to be present
            span_element = wait.until(ec.presence_of_element_located((By.CLASS_NAME, 'new-stepper-hints__rate')))
            # Extract the text from the span element
            span_text = span_element.text
            # Use regular expression to extract the number after '=' and before 'GBP'
            match = re.search(r'[=~]\s*(\d+\.?\d*)\s*GBP', span_text)
            if match:
                scraped_number = match.group(1)
                one_ltc_in_gbp = float(scraped_number)
                logging.debug(f"Successfully scraped CHANGENOW's 1LTC to GBP value: {one_ltc_in_gbp}")
                return one_ltc_in_gbp
            else:
                logging.error(
                    f"No number found in the span text. Attempt {attempt + 1} of {retries}. Text: {span_text}")
        except ValueError as e:
            logging.error(f"Error converting scraped number to float on attempt {attempt + 1} of {retries}. Error: {e}")

        # Wait briefly before retrying to avoid overwhelming the server or repeating the same error too quickly
        time.sleep(1)

    # After retries are exhausted, log and raise an exception
    logging.fatal(f"Failed to scrape LTC to GBP value after {retries} attempts.")
    raise Exception(f"Failed to retrieve LTC to GBP value after {retries} attempts.")


# Function to calculate the final price from all the scraped values
def calculate_final_price(one_ltc_to_gbp_value, xmr_to_ltc_rate, current_balance):
    gross_trade_price = one_ltc_to_gbp_value * xmr_to_ltc_rate
    logging.debug(f"Gross trade price: £{gross_trade_price}")
    # Round to the nearest penny
    rounded_trade_price = round(gross_trade_price, 2)
    logging.debug(f"Rounded trade price: £{rounded_trade_price}")
    # Add static XMR trade fees (conservative fees estimate)
    with_fees_trade_price = rounded_trade_price + xmr_fees_total
    logging.debug(f"With fees trade price: £{with_fees_trade_price}")
    # Remove current XMR balance (applies rounding again to avoid unknown float bug)
    final_trade_price = round(with_fees_trade_price - current_balance, 2)
    logging.debug(f"Final trade price: £{final_trade_price}")
    return final_trade_price


# Function to load settings from the JSON file
def load_settings():
    if not os.path.exists(settings_file):
        # If the file doesn't exist, create it with default settings
        save_settings({"balance": 0.0, "debugging": False})
        print(f"File not found. Created new default settings file.")
        logging.info(f"File not found. Created new default settings file.")
    with open(settings_file, 'r') as f:
        settings = json.load(f)
        print(f"Successfully loaded settings file.")
        logging.info(f"Successfully loaded settings file.")
    if 'balance' not in settings:
        settings['balance'] = False
        save_settings(settings)
        print("Added 'balance' setting to the file.")
        logging.info("Added 'balance' setting to the file.")
    if 'item_price' not in settings:
        settings['item_price'] = 0
        save_settings(settings)
        print("Added 'item_price' setting to the file.")
        logging.info("Added 'item_price' setting to the file.")
    if 'run_headless' not in settings:
        settings['run_headless'] = True
        save_settings(settings)
        print("Added 'run_headless' setting to the file.")
        logging.info("Added 'run_headless' setting to the file.")
    if 'xmr_fees' not in settings:
        settings['xmr_fees'] = 0.5
        save_settings(settings)
        print("Added 'xmr_fees' setting to the file.")
        logging.info("Added 'xmr_fees' setting to the file.")
    return settings


# Function to save settings to the JSON file
def save_settings(settings):
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)


# Function to update the balance value in settings
def update_balance(new_balance, settings):
    settings['balance'] = new_balance
    save_settings(settings)


# Function to update the item price in settings
def update_item_price(new_item_price, settings):
    settings['item_price'] = new_item_price
    save_settings(settings)


# Function to update the headless mode value in settings
def update_headless_mode(new_headless_option, settings):
    settings['run_headless'] = new_headless_option
    save_settings(settings)


# Function to update the xmr_fees in settings
def update_xmr_fees(new_xmr_fees, settings):
    settings['xmr_fees'] = new_xmr_fees
    save_settings(settings)


# Function to allow the user to alter their balance in the settings file
def check_for_balance_update(current_settings):
    if input(f"Change balance[£{current_settings['balance']}]? (y/n): ") == "y":
        # Update the balance
        new_balance = float(input("Enter new balance: £"))
        update_balance(new_balance, current_settings)
        print(f"Balance updated to £{new_balance}")
        logging.info(f"Balance updated to £{new_balance}")
        return new_balance
    return current_settings['balance']


# Function to allow the user to alter the item purchase price in the settings file
def check_for_item_price_update(current_settings):
    if input(f"Change item price[£{current_settings['item_price']}]? (y/n): ") == "y":
        # Update the balance
        new_item_price = float(input("Enter new item price: £"))
        update_item_price(new_item_price, current_settings)
        print(f"item Price updated to £{new_item_price}")
        logging.info(f"item Price updated to £{new_item_price}")
        return new_item_price
    return current_settings['item_price']


# Function to allow the user to run the program headless
def check_for_headless_update(current_settings):
    if input(f"Change headless option[Status: {current_settings['run_headless']}]? (y/n): ") == "y":
        # Update the headless value
        user_input = input("Run Headless? (y/n): ")
        if user_input == "y":
            if not current_settings['run_headless'] is True:
                update_headless_mode(True, current_settings)
                print(f"Headless value updated to True")
                logging.info(f"Headless value updated to True")
                return True
        elif user_input == "n":
            if not current_settings['run_headless'] is False:
                update_headless_mode(False, current_settings)
                print(f"Headless value updated to False")
                logging.info(f"Headless value updated to False")
                return False
        else:
            print("Invalid input.")
            logging.error("Invalid input.")
    return current_settings['run_headless']


# Function to allow the user to alter the xmr fees in the settings file
def check_for_xmr_fees_update(current_settings):
    if input(f"Change xmr fees[£{current_settings['xmr_fees']}]? (y/n): ") == "y":
        # Update the xmr fee price
        new_xmr_fees = float(input("Enter new fee price: £"))
        update_item_price(new_xmr_fees, current_settings)
        print(f"XMR fees updated to £{new_xmr_fees}")
        logging.info(f"XMR fees updated to £{new_xmr_fees}")
        return new_xmr_fees
    return current_settings['xmr_fees']


# Function to clear the console on any os
def clear_console():
    # For Windows
    if os.name == 'nt':
        os.system('cls')
    # For Linux/macOS
    else:
        os.system('clear')


# Function to save the estimated price and other relevant data to a JSON file
def save_estimate(final_estimate, initial_product_price, filename='price_data.json'):
    # Get the current date and time
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Create a dictionary to hold the data
    data_entry = {
        'date_time': current_time,
        'final_estimate': final_estimate,
        'initial_product_price': initial_product_price
    }

    try:
        # Try to read existing data from the file
        with open(filename, 'r') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is empty, initialize data as an empty list
        data = []

    # Append the new data entry
    data.append(data_entry)

    # Write the updated data back to the file
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)

    print(f"Estimate saved.")
    logging.info(f"Estimate saved: {data_entry}")


# Function to read price data JSON and provided an estimated best time and price
def analyse_best_time(initial_product_price, tolerance=5, tolerance_increment=10, max_retries=10,
                      filename='price_data.json'):
    try:
        # Read the data from the file
        with open(filename, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"No data found in {filename}")
        logging.error(f"No data found in {filename}")
        return
    except json.JSONDecodeError:
        print(f"Error reading data from {filename}")
        logging.error(f"Error reading data from {filename}")
        return

    # Dictionary to store sums and counts of prices per quarter-hour for matching initial prices
    quarter_hourly_data = {}

    # Function to check if a price is within a certain tolerance
    def is_within_tolerance(value1, value2, tolerance):
        return abs(value1 - value2) <= tolerance

    # Helper function to round time to the nearest quarter-hour
    def round_to_nearest_quarter_hour(date_time):
        minutes = (date_time.minute // 15) * 15
        return date_time.replace(minute=minutes, second=0, microsecond=0)

    # Start with the initial tolerance
    current_tolerance = tolerance

    # Try to filter data and widen the tolerance up to max_retries
    for attempt in range(max_retries):
        # Filter data for entries with similar initial product prices within current tolerance
        filtered_data = [entry for entry in data if
                         is_within_tolerance(entry['initial_product_price'], initial_product_price, current_tolerance)]

        if filtered_data:
            logging.info(f"Data found within {current_tolerance} units of the initial product price.")
            break  # If data is found, break the loop
        else:
            logging.info(f"No data found within {current_tolerance} units of initial price. Increasing tolerance...")
            current_tolerance += tolerance_increment  # Increase the tolerance
    else:
        # If we complete all retries and still no data is found, exit the function
        logging.info(f"No sufficient data even after increasing the tolerance to {current_tolerance}.")
        return

    # Process the filtered data to calculate averages per quarter-hour
    for entry in filtered_data:
        # Parse the date and time from the entry
        date_time = datetime.strptime(entry['date_time'], '%Y-%m-%d %H:%M:%S')

        # Round the time to the nearest quarter-hour
        rounded_time = round_to_nearest_quarter_hour(date_time)

        # Get the final estimate
        price = entry['final_estimate']

        # Initialize or update the sum and count for the quarter-hour
        if rounded_time not in quarter_hourly_data:
            quarter_hourly_data[rounded_time] = {'sum': 0, 'count': 0}

        quarter_hourly_data[rounded_time]['sum'] += price
        quarter_hourly_data[rounded_time]['count'] += 1

    # Calculate the average price per quarter-hour for the filtered data
    quarter_hourly_averages = {time: quarter_hourly_data[time]['sum'] / quarter_hourly_data[time]['count']
                               for time in quarter_hourly_data}

    # Find the quarter-hour with the lowest average price
    best_time = min(quarter_hourly_averages, key=quarter_hourly_averages.get)
    best_price = quarter_hourly_averages[best_time]

    print(f"Best time to buy based on similar product prices is around {best_time.strftime('%H:%M')} with an average price of £{best_price:.2f}")
    logging.info(f"Best time to buy based on similar product prices is around {best_time.strftime('%H:%M')} with an average price of £{best_price:.2f}")


# Tasks array for the progress bar
tasks = ["Creating webdriver instance.", "Searching XMR rate.", "Accepting Cookies.", "Storing XMR value.",
         "Searching LTC to XMR rate.", "Storing XMR to LTC rate.", "Searching LTC to GBP rate.",
         "Storing LTC to GBP rate.", "Calculating final trade price."]


# Main program function
def main():
    global item_purchase_price
    global run_headless
    global xmr_fees_total
    if "--version" in sys.argv:
        print(f"v{__version__}")
        return
    print(f"Running application version v{__version__}")
    try:
        # Create or load settings file
        settings = load_settings()
        # Store settings into correct variables
        current_balance = settings['balance']
        item_purchase_price = settings['item_price']
        run_headless = settings['run_headless']
        xmr_fees_total = settings['xmr_fees']
        time.sleep(2)
        clear_console()
        # Ask user if they need to alter settings
        if input("Do you want to change any settings? (y/n): ") == "y":
            current_balance = check_for_balance_update(settings)
            item_purchase_price = check_for_item_price_update(settings)
            run_headless = check_for_headless_update(settings)
            xmr_fees_total = check_for_xmr_fees_update(settings)
        clear_console()
        # Display best time estimate
        analyse_best_time(item_purchase_price)
        input("Press Enter to continue...")
        clear_console()
        # Create the progress bar
        with alive_bar(len(tasks), spinner='classic', bar='classic') as bar:
            current_task = 0
            bar.text = tasks[current_task]
            logging.debug("Main function now running.")
            # Create web driver and wait instances
            driver, wait = setup_web_driver(run_headless)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Search current XMR value of desired total
            load_site(driver, 0, False)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Accept cookies pop up
            accept_cookies(wait)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Store the current trade price in XMR value
            xmr_trade_value = select_and_parse_xmr_value(wait)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Search LTC value of XMR trade price
            load_site(driver, 1, xmr_trade_value)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Store the current LTC total conversion rate
            xmr_to_ltc_rate = select_and_parse_ltc_value(wait)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Get CHANGENOW's LTC/GBP conversion price
            load_site(driver, 2, False)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Store CHANGENOW's current LTC to GBP trade price
            one_ltc_to_gbp_value = select_and_parse_gbp_value(wait)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Calculate final estimated price with fees
            final_estimate = calculate_final_price(one_ltc_to_gbp_value, xmr_to_ltc_rate, current_balance)
            bar()
            # Close the driver instance
            driver.close()
        # Display the final estimate price
        print()
        print("------------------------------------------------------")
        print(f"Estimated trade price ~ £{final_estimate}")
        print("------------------------------------------------------")
        logging.info(f"Estimated trade price ~ £{final_estimate}")
        # Make user confirm closing
        print()
        save_estimate(final_estimate, item_purchase_price)
        print()
        input("Press Enter to exit...")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
