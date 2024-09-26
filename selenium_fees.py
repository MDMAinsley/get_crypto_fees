import base64
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from webdriver_manager.firefox import GeckoDriverManager
from alive_progress import alive_bar
from dotenv import load_dotenv
import time
import requests
import re
import sys
import json
import os
import logging

__version__ = "1.2.2"

# Variables setup
settings_file = 'settings.json'
cookies_element_id = "L2AGLb"  # Change when needed

# Constants
load_dotenv()  # Load environment variables from .env file
RAW_GITHUB_URL = 'https://raw.githubusercontent.com/MDMAinsley/get_crypto_fees/main/price_data.json'
GITHUB_API_URL = 'https://api.github.com/repos/MDMAinsley/get_crypto_fees/contents/price_data.json'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'}

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
def load_site(driver, index, xmr_trade_value, fiat_currency, initial_crypto, final_crypto, item_purchase_price):
    if index == 0:
        driver.get(f"https://www.google.com/search?q={item_purchase_price}{fiat_currency}+to+{final_crypto}")
    elif index == 1:
        driver.get(f'https://changenow.io/?from={initial_crypto}&to={final_crypto}&amountTo={xmr_trade_value}')
        time.sleep(3)
    elif index == 2:
        driver.get(f'https://changenow.io/?from={fiat_currency}&to={initial_crypto}'
                   f'&fiatMode=true&amount={item_purchase_price}')
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
def calculate_final_price(one_ltc_to_gbp_value, xmr_to_ltc_rate, current_balance, xmr_fees_total):
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
        save_settings({"do_setup": True, "balance": 0.0, "item_price": 0.0, "run_headless": True, "xmr_fees": 0.5,
                       "fiat_currency": 'gbp', "initial_crypto": 'ltc', "final_crypto": 'xmr'})
        print(f"File not found. Created new default settings file.")
        logging.info(f"File not found. Created new default settings file.")
    with open(settings_file, 'r') as f:
        settings = json.load(f)
        print(f"Successfully loaded settings file.")
        logging.info(f"Successfully loaded settings file.")
    if 'do_setup' not in settings:
        settings['do_setup'] = True
        save_settings(settings)
        print_and_log("Added 'do_setup' setting to the file.", logging.info)
    if 'balance' not in settings:
        settings['balance'] = False
        save_settings(settings)
        print_and_log("Added 'balance' setting to the file.", logging.info)
    if 'item_price' not in settings:
        settings['item_price'] = 0.0
        save_settings(settings)
        print_and_log("Added 'item_price' setting to the file.", logging.info)
    if 'run_headless' not in settings:
        settings['run_headless'] = True
        save_settings(settings)
        print_and_log("Added 'run_headless' setting to the file.", logging.info)
    if 'xmr_fees' not in settings:
        settings['xmr_fees'] = 0.5
        save_settings(settings)
        print_and_log("Added 'xmr_fees' setting to the file.", logging.info)
    if 'fiat_currency' not in settings:
        settings['fiat_currency'] = 'gbp'
        save_settings(settings)
        print_and_log("Added 'fiat_currency' setting to the file.", logging.info)
    if 'initial_crypto' not in settings:
        settings['initial_crypto'] = 'ltc'
        save_settings(settings)
        print_and_log("Added 'initial_crypto' setting to the file.", logging.info)
    if 'final_crypto' not in settings:
        settings['final_crypto'] = 'xmr'
        save_settings(settings)
        print_and_log("Added 'final_crypto' setting to the file.", logging.info)
    return settings


# Function to save settings to the JSON file
def save_settings(settings):
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)


# Function to change a setting in the settings file
def update_setting(new_setting, setting_name, setting_file):
    setting_file[setting_name] = new_setting
    save_settings(setting_file)


# Function to allow the user to alter their balance in the settings file
def check_for_balance_update(current_settings):
    if specific_input(f"Change balance[£{current_settings['balance']}]? (y/n): ", ["y", "n"]) == "y":
        # Update the balance
        new_balance = specific_input("Enter new balance: £", None, float)
        update_setting(new_balance, 'balance', current_settings)
        print_and_log(f"Balance updated to £{new_balance}", logging.info)
        return new_balance
    return current_settings['balance']


# Function to allow the user to alter the item purchase price in the settings file
def check_for_item_price_update(current_settings):
    if specific_input(f"Change item price[£{current_settings['item_price']}]? (y/n): ", ["y", "n"]) == "y":
        # Update the balance
        new_item_price = specific_input("Enter new item price: £", None, float)
        update_setting(new_item_price, 'item_price', current_settings)
        print_and_log(f"item Price updated to £{new_item_price}", logging.info)
        return new_item_price
    return current_settings['item_price']


# Function to allow the user to run the program headless
def check_for_headless_update(current_settings):
    if specific_input(f"Change headless option[Status: {current_settings['run_headless']}]? (y/n): ",
                      ["y", "n"]) == "y":
        # Update the headless value
        user_input = specific_input("Run Headless? (y/n): ", ["y", "n"])
        if user_input == "y":
            if not current_settings['run_headless'] is True:
                update_setting(True, 'run_headless', current_settings)
                print_and_log(f"Headless value updated to True", logging.info)
                return True
        elif user_input == "n":
            if not current_settings['run_headless'] is False:
                update_setting(False, 'run_headless', current_settings)
                print_and_log(f"Headless value updated to False", logging.info)
                return False
        else:
            print("Invalid input.")
            logging.error("Invalid input.")
    return current_settings['run_headless']


# Function to allow the user to alter the xmr fees in the settings file
def check_for_xmr_fees_update(current_settings):
    if specific_input(f"Change xmr fees[£{current_settings['xmr_fees']}]? (y/n): ", ["y", "n"]) == "y":
        # Update the xmr fee price
        new_xmr_fees = specific_input("Enter new fee price: £", None, float)
        update_setting(new_xmr_fees, 'xmr_fees', current_settings)
        print_and_log(f"XMR fees updated to £{new_xmr_fees}", logging.info)
        return new_xmr_fees
    return current_settings['xmr_fees']


def check_for_fiat_update(current_settings):
    if specific_input(f"Change fiat currency[fiat={current_settings['fiat_currency']}]? (y/n): ", ["y", "n"]) == "y":
        # Update the fiat currency
        new_fiat_currency = specific_input("Enter fiat currency: ", None, str)
        update_setting(new_fiat_currency, 'fiat_currency', current_settings)
        print_and_log(f"Fiat currency updated to {new_fiat_currency}", logging.info)
        return new_fiat_currency
    return current_settings['fiat_currency']


def check_for_initial_crypto_update(current_settings):
    if specific_input(f"Change initial crypto[initial={current_settings['initial_crypto']}]? (y/n): ",
                      ["y", "n"]) == "y":
        # Update the initial cryptocurrency
        new_initial_crypto = specific_input("Enter initial crypto: ", None, str)
        update_setting(new_initial_crypto, 'initial_crypto', current_settings)
        print_and_log(f"Initial Crypto updated to {new_initial_crypto}", logging.info)
        return new_initial_crypto
    return current_settings['initial_crypto']


def check_for_final_crypto_update(current_settings):
    if specific_input(f"Change final crypto[final={current_settings['final_crypto']}]? (y/n): ",
                      ["y", "n"]) == "y":
        # Update the initial cryptocurrency
        new_final_crypto = specific_input("Enter final crypto: ", None, str)
        update_setting(new_final_crypto, 'final_crypto', current_settings)
        print_and_log(f"Final Crypto updated to {new_final_crypto}", logging.info)
        return new_final_crypto
    return current_settings['final_crypto']


# Function to clear the console on any os
def clear_console():
    # For Windows
    if os.name == 'nt':
        os.system('cls')
    # For Linux/macOS
    else:
        os.system('clear')


# Function to save the estimated price and other relevant data to a JSON file
def save_estimate(final_estimate, initial_product_price, fiat_curr, init_cryp, final_crypt, filename='price_data.json'):
    # Get the current date and time
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Create a dictionary to hold the data
    data_entry = {
        'date_time': current_time,
        'final_estimate': final_estimate,
        'initial_product_price': initial_product_price,
        'fiat_currency': fiat_curr,
        'initial_crypto': init_cryp,
        'final_crypto': final_crypt,
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

    print_and_log("Estimated saved.", logging.info)


# Function to read price data JSON and provide an estimated best time and price
def analyse_best_time(initial_product_price, fiat_currency, initial_crypto, final_crypto, days_to_search=7, tolerance=5,
                      tolerance_increment=10, max_retries=10, filename='price_data.json'):
    try:
        # Log initial parameters
        logging.info(f"Starting analysis with parameters: initial_product_price={initial_product_price}, "
                     f"fiat_currency={fiat_currency}, initial_crypto={initial_crypto}, "
                     f"final_crypto={final_crypto}, days_to_search={days_to_search}")

        # Update the price_data.json to include the most recent changes
        sync_data()

        # Read the data from the file
        with open(filename, 'r') as file:
            content = file.read()
            logging.info(f"Raw JSON content: {content}")
            data = json.loads(content)
            logging.info(f"Parsed JSON data: {data}")

        # Log the number of entries loaded
        logging.info(f"Loaded {len(data)} entries from {filename}")
    except FileNotFoundError:
        logging.error(f"No data found in {filename}")
        return
    except json.JSONDecodeError:
        logging.error(f"Error reading data from {filename}")
        return

    # Calculate the date to filter entries from
    data_to_use = datetime.now() - timedelta(days=days_to_search)
    logging.info(f"Filtering data from the past {days_to_search} days (cutoff: {data_to_use}).")

    # Initialize an empty list for recent_data
    recent_data = []

    # Iterate through each entry and parse date_time with logging
    for entry in data:
        try:
            # Log the original and parsed date_time
            logging.info(f"Original date_time string: {entry['date_time']}")
            parsed_date_time = datetime.strptime(entry['date_time'], '%Y-%m-%d %H:%M:%S')
            logging.info(f"Parsed date_time: {parsed_date_time}")

            # Check if the parsed date_time is within the date range
            if parsed_date_time >= data_to_use:
                recent_data.append(entry)
                logging.info(f"Entry from {parsed_date_time} added to recent_data.")
            else:
                logging.info(f"Entry from {parsed_date_time} is older than {data_to_use}, not added.")
        except ValueError as e:
            logging.error(f"Error parsing date_time for entry {entry}: {e}")

    # Log how many entries were found
    logging.info(f"Total entries found within the date range: {len(recent_data)}")

    if not recent_data:
        logging.error(f"No data found in the past {days_to_search} days.")
        return

    # Dictionary to store sums and counts of prices per quarter-hour for matching initial prices
    quarter_hourly_data = {}

    # Function to check if a price is within a certain tolerance
    def is_within_tolerance(value1, value2, tol):
        # Log the values and tolerance before performing the check
        logging.info(
            f"Checking if value {value1} is within {tol} units of value {value2}. "
            f"Difference: {abs(value1 - value2)}")

        # Perform the tolerance check
        within_tolerance = abs(value1 - value2) <= tol

        # Log the result of the tolerance check
        logging.info(f"Result: {'Within tolerance' if within_tolerance else 'Out of tolerance'}")

        return within_tolerance

    # Helper function to round time to the nearest quarter-hour
    def round_to_nearest_quarter_hour(dt):
        minutes = (dt.minute // 15) * 15
        return dt.replace(minute=minutes, second=0, microsecond=0)

    # Start with the initial tolerance
    current_tolerance = tolerance

    # Try to filter data and widen the tolerance up to max_retries
    for attempt in range(max_retries):
        # Filter data for entries with similar product prices and matching crypto values within current tolerance
        filtered_data = [
            entry for entry in recent_data
            if (is_within_tolerance(entry['initial_product_price'], initial_product_price, current_tolerance) and
                entry['fiat_currency'] == fiat_currency and
                entry['initial_crypto'] == initial_crypto and
                entry['final_crypto'] == final_crypto)
        ]

        # Log the number of filtered entries found
        logging.info(f"Attempt {attempt + 1}: Found {len(filtered_data)} entries within {current_tolerance} tolerance.")

        if filtered_data:
            logging.info(f"Data found within {current_tolerance} units of the initial product price.")
            break  # If data is found, break the loop
        else:
            logging.info(f"No data found within {current_tolerance} units of initial price. Increasing tolerance...")
            current_tolerance += tolerance_increment  # Increase the tolerance
    else:
        # If we complete all retries and still no data is found, exit the function
        logging.error(f"No sufficient data even after increasing the tolerance to {current_tolerance}.")
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
    quarter_hourly_averages = {
        quarter_hour: quarter_hourly_data[quarter_hour]['sum'] / quarter_hourly_data[quarter_hour]['count']
        for quarter_hour in quarter_hourly_data
    }

    # Find the quarter-hour with the lowest average price
    best_time = min(quarter_hourly_averages, key=quarter_hourly_averages.get)
    best_price = quarter_hourly_averages[best_time]

    hour = best_time.strftime('%H')
    am_pm = 'AM' if int(hour) < 12 else 'PM'
    formatted_time = f"{hour}:{best_time.strftime('%M')}{am_pm}"

    print_and_log(f"----------Best Estimates----------", logging.info)
    print_and_log(f"For {fiat_currency.upper()} to {final_crypto.upper()} via {initial_crypto.upper()}.",
                  logging.info)
    print_and_log(f"Best time to convert is around {formatted_time}.",
                  logging.info)
    print_and_log(f"For an average trade price of £{best_price:.2f}.",
                  logging.info)
    print()
    print_and_log(f"----------Trade Insights----------", logging.info)
    print_and_log(f"Initial trade amount - £{initial_product_price:.2f}",
                  logging.info)
    print_and_log(f"Total trade fees - £{best_price - initial_product_price:.2f}",
                  logging.info)
    print()


# Function to add a specific reply requirement onto the input function of Python
def specific_input(question_to_ask, required_answers=None, input_type=None):
    while True:
        user_input = input(question_to_ask)

        # Type validation
        if input_type:
            try:
                # Check for integer input
                if input_type == int:
                    user_input = int(user_input)

                # Check for float input
                elif input_type == float:
                    user_input = float(user_input)

                # Check for string input
                elif input_type == str:
                    user_input = str(user_input)

                # Check for char input (ensure single character)
                elif input_type == 'char':
                    if len(user_input) != 1:
                        raise ValueError("Please enter a single character.")

                # Check for boolean input (interpret true/false)
                elif input_type == bool:
                    user_input_lower = user_input.lower()
                    if user_input_lower in ['true', 't', 'yes', 'y', '1']:
                        user_input = True
                    elif user_input_lower in ['false', 'f', 'no', 'n', '0']:
                        user_input = False
                    else:
                        raise ValueError("Please enter a valid boolean (yes/no, true/false).")
                else:
                    raise ValueError(f"Unsupported input type: {input_type}")

            except ValueError as ve:
                print(ve)
                continue

        # If RequiredAnswers is provided, ensure input matches allowed answers
        if required_answers is not None:
            if str(user_input).lower() not in [answer.lower() for answer in required_answers]:
                print(f"Please enter one of the following: {', '.join(required_answers)}")
                continue

        return user_input


# Function to print to the console and log at the same time
def print_and_log(message_to_print, logging_func):
    # Print to the console
    print(message_to_print)
    # Call the logging function
    if callable(logging_func):
        logging_func(message_to_print)
    else:
        logging.error(f"Invalid logging function specified for message: {message_to_print}")


# Function to check for internet connection
def check_internet():
    try:
        requests.get('https://www.google.com/', timeout=5)
        return True
    except requests.ConnectionError:
        return False


# Function to download shared data from GitHub
def download_shared_data():
    logging.info("Attempting to download shared data from GitHub...")
    try:
        response = requests.get(RAW_GITHUB_URL, headers=HEADERS)
        response.raise_for_status()
        logging.info("Received response from GitHub.")
        shared_data = response.json()  # Directly assign the response to shared_data
        logging.info("Downloaded shared data from GitHub.")
        return shared_data
    except requests.HTTPError as e:
        logging.error(f"HTTP error fetching shared data: {e}")
    except Exception as e:
        logging.error(f"Error fetching shared data: {e}")
    return None


# Function to upload local data to GitHub
def upload_to_github(local_data):
    logging.info("Attempting to upload merged data to GitHub...")
    try:
        # Load the current file SHA to make an update (GitHub requires this)
        response = requests.get(GITHUB_API_URL, headers=HEADERS)
        response.raise_for_status()
        file_info = response.json()
        if 'sha' not in file_info:
            logging.error("SHA not found in response from GitHub.")
            return
        sha = file_info['sha']

        # Convert data to base64
        encoded_data = base64.b64encode(json.dumps(local_data).encode('utf-8')).decode('utf-8')

        # Upload the updated content
        data = {
            'message': 'Update price_data.json',
            'content': encoded_data,
            'sha': sha
        }

        response = requests.put(GITHUB_API_URL, headers=HEADERS, json=data)
        response.raise_for_status()
        logging.info("Uploaded local data to GitHub.")
    except requests.HTTPError as e:
        logging.error(f"Error uploading to GitHub: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


# Function to merge local and shared data intelligently
def merge_data(local_data, shared_data):
    # Convert shared data to a dictionary for conflict resolution
    shared_dict = {
        (entry['initial_product_price'], entry['final_estimate'], entry['date_time'],
         entry['fiat_currency'], entry['initial_crypto'], entry['final_crypto']): entry for entry in shared_data
    }

    for entry in local_data:
        key = (entry['initial_product_price'], entry['final_estimate'], entry['date_time'],
               entry['fiat_currency'], entry['initial_crypto'], entry['final_crypto'])

        # Only add entry if it's not an exact duplicate
        if key not in shared_dict:
            shared_dict[key] = entry

    # Convert the dictionary back to a list
    return list(shared_dict.values())


# Main sync function
def sync_data(filename='price_data.json'):
    # Load local data
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            local_data = json.load(f)
    else:
        local_data = []

    # Check if the user has internet
    if check_internet():
        # Download shared data from GitHub
        shared_data = download_shared_data()

        if shared_data is not None:
            # Check if the required keys exist in local data
            keys_to_check = ['fiat_currency', 'initial_crypto', 'final_crypto']
            if local_data and any(key not in local_data[0] for key in keys_to_check):
                logging.warning("Local data is missing required keys. Replacing with shared data.")
                # Replace local data with shared data
                with open(filename, 'w') as f:
                    json.dump(shared_data, f, indent=4)
                return  # Exit the function after replacing data

            # Check if shared data is the same as local data
            if shared_data == local_data:
                logging.info("Local data is the same as shared data. No upload needed.")
                return  # Exit the function if data is the same

            # Merge the local data with the shared data
            merged_data = merge_data(local_data, shared_data)

            # Save the merged data locally
            with open(filename, 'w') as f:
                json.dump(merged_data, f, indent=4)

            # Upload merged data to GitHub
            upload_to_github(merged_data)
        else:
            logging.info("Using local data as no shared data was available.")
    else:
        logging.info("No internet connection. Using local data.")


# Main program function
def main():
    if "--version" in sys.argv:
        print(f"v{__version__}")
        return
    if check_internet():
        print_and_log("Connection active.", logging.info)
    else:
        print_and_log("Offline Mode", logging.info)
    print_and_log(f"Running application version v{__version__}", logging.info)
    try:
        # Create or load settings file
        settings = load_settings()
        # Store settings into correct variables
        do_setup = settings['do_setup']
        current_balance = settings['balance']
        item_purchase_price = settings['item_price']
        run_headless = settings['run_headless']
        xmr_fees_total = settings['xmr_fees']
        fiat_currency = settings['fiat_currency']
        initial_crypto = settings['initial_crypto']
        final_crypto = settings['final_crypto']
        time.sleep(2)
        clear_console()
        # Display best time estimate
        analyse_best_time(item_purchase_price, fiat_currency, initial_crypto, final_crypto)
        # Present user with first time config or ask user if they need to alter settings
        if do_setup:
            print_and_log("Running first time configuration.", logging.info)
            current_balance = check_for_balance_update(settings)
            item_purchase_price = check_for_item_price_update(settings)
            run_headless = check_for_headless_update(settings)
            xmr_fees_total = check_for_xmr_fees_update(settings)
            fiat_currency = check_for_fiat_update(settings)
            initial_crypto = check_for_initial_crypto_update(settings)
            final_crypto = check_for_final_crypto_update(settings)
            update_setting(False, 'do_setup', settings)
        elif specific_input("Do you want to change any settings? (y/n): ", ["y", "n"]) == "y":
            current_balance = check_for_balance_update(settings)
            item_purchase_price = check_for_item_price_update(settings)
            run_headless = check_for_headless_update(settings)
            xmr_fees_total = check_for_xmr_fees_update(settings)
            fiat_currency = check_for_fiat_update(settings)
            initial_crypto = check_for_initial_crypto_update(settings)
            final_crypto = check_for_final_crypto_update(settings)
        clear_console()

        # Tasks array for the progress bar
        tasks = ["Creating webdriver instance.", f"Searching {final_crypto.upper()} rate.", "Accepting Cookies.",
                 f"Storing {final_crypto.upper()} value.",
                 f"Searching {initial_crypto.upper()} to {final_crypto.upper()} rate.",
                 f"Storing {final_crypto.upper()} to {initial_crypto.upper()} rate.",
                 f"Searching {initial_crypto.upper()} to {fiat_currency.upper()} rate.",
                 f"Storing {initial_crypto.upper()} to {fiat_currency} rate.", "Calculating final trade price."]

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
            load_site(driver, 0, False, fiat_currency, initial_crypto, final_crypto, item_purchase_price)
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
            load_site(driver, 1, xmr_trade_value, fiat_currency, initial_crypto, final_crypto, item_purchase_price)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Store the current LTC total conversion rate
            xmr_to_ltc_rate = select_and_parse_ltc_value(wait)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Get CHANGENOW's LTC/GBP conversion price
            load_site(driver, 2, False, fiat_currency, initial_crypto, final_crypto, item_purchase_price)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Store CHANGENOW's current LTC to GBP trade price
            one_ltc_to_gbp_value = select_and_parse_gbp_value(wait)
            current_task += 1
            bar()
            bar.text = tasks[current_task]
            # Calculate final estimated price with fees
            final_estimate = calculate_final_price(one_ltc_to_gbp_value, xmr_to_ltc_rate, current_balance,
                                                   xmr_fees_total)
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
        # Add the current balance back to the estimate for more accurate estimated best time and price
        estimate_to_save = final_estimate + current_balance
        save_estimate(estimate_to_save, item_purchase_price, fiat_currency, initial_crypto, final_crypto)
        # Sync data with GitHub to merge and upload
        sync_data()
        print()
        input("Press Enter to exit...")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
