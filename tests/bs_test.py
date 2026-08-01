ython
import requests
from bs4 import BeautifulSoup
from door_controller.common_lib.data_manager import DataManager
from door_controller.common_lib.pg_database import postgres


from door_controller.common_lib.utils import load_config
config = load_config()
controller_ip = config.get('settings', {}).get('urls', [])[0].split('//')[1]  # Extract the IP address from the URL
base_url = config.get('settings', {}).get('urls', [])[0]
username = config.get('settings', {}).get('username')
password = config.get('settings', {}).get('password')

# Now, extract a single record from the database to use in the test
pg_db = postgres(config.get('settings', {}).get('postgres_connect_string'))
# Fetch a single record to delete from the physical controller. This assumes that there is at least one unassigned fob in the database.
dm = DataManager(url, username, password)

# base_url = "http://69.21.119.147"  # Replace with your actual IP

session = requests.Session()

# 1. Fetch the live page first to get the fresh form ID
# (Change 'ACT_ID_324' to whatever the main URL of the page is)
response = session.get(f"{base_url}ACT_ID_324")
soup = BeautifulSoup(response.text, 'html.parser')

# 2. Find the search form dynamically
# It's the form that contains the text input named 'US21'
search_form = soup.find('input', {'name': 'US21'}).find_parent('form')
live_action = search_form['action']  # This gets the current 'ACT_ID_XXX'

# 3. Pull the live values of the hidden fields automatically
hidden_22 = soup.find('input', {'name': '22'})['value']
hidden_23 = soup.find('input', {'name': '23'})['value']

# 4. Construct the live URL and payload
search_url = f"{base_url}{live_action}"
payload = {
    'US21': 'William',
    '22': hidden_22,
    '23': hidden_23,
    '24': 'Search'
}

# 5. Submit to the fresh endpoint
headers = {'Referer': response.url}
result = session.post(search_url, data=payload, headers=headers)

print(f"Submitted to: {search_url}")
# Check if the text returned now shows the filtered search results
print(result.text)