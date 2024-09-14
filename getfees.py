import requests

api_key = '2e5408eb01ff43e8cc77f658c5f706606150d9dfcb2c733a73a0905b1dc951c4'

headers = { 'x-changenow-api-key': api_key }

from_currency = 'usdt'  # Replace with the source currency

to_currency = 'btc'    # Replace with the target currency

from_amount = 1

# url = f'https://api.changenow.io/v2/exchange/range?fromCurrency={from_currency}&toCurrency={to_currency}'
# url = f'https://api.changenow.io/v2/markets/estimate?fromCurrency={from_currency}&toCurrency={to_currency}&fromAmount={from_amount}&type=direct'
url = f'https://api.changenow.io/v2/markets/estimate?fromCurrency={from_currency}&toCurrency={to_currency}&fromAmount={from_amount}&toAmount&type=direct'

response = requests.get(url, headers=headers)

if response.status_code == 200:

    data = response.json()

    min_amount = data['minAmount']

    max_amount = data['maxAmount']

    print(f"Minimum exchange amount: {min_amount}")

    print(f"Maximum exchange amount: {max_amount}")

else:

    print(f"Error: {response.status_code}")