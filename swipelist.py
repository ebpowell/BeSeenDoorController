
from bs4 import BeautifulSoup

import requests
from requests.auth import HTTPBasicAuth
import lxml

def call_post_action(url, action_id, auth, data=None, headers=None):
  """
  Calls a POST action with the specified ID.

  Args:
    url: The base URL of the API endpoint.
    action_id: The ID of the action to call (e.g., "ACT_ID_21").
    data: A dictionary containing the data to be sent in the POST request.
    headers: A dictionary containing any custom headers for the request.
    auth: Authentication credentials (e.g., username/password, API key).

  Returns:
    The response object from the request.
  """

  try:
    response = requests.post(
        f"{url}/{action_id}",
        data=data,
        headers=headers,
        auth=auth
    )
    response.raise_for_status()  # Raise an exception for bad status codes
    return response.content
  except requests.exceptions.RequestException as e:
    print(f"An error occurred during the POST request: {e}")
    return None

def scrape_page_with_auth(url, authentication, data):
  """
  Scrapes data from a page protected by basic authentication.

  Args:
    url: The URL of the page to scrape.
    username: The username for authentication.
    password: The password for authentication.

  Returns:
    The BeautifulSoup object of the scraped page.
  """
  try:
    response = requests.post(url, auth=authentication, data=data)
    response.raise_for_status()  # Raise an exception for bad status codes
    return BeautifulSoup(response.content, "lxml-xml")
  # return BeautifulSoup(response.content, "html.parser")
  except requests.exceptions.RequestException as e:
    print(f"Error during request: {e}")
    return None


if __name__ == "__main__":

  base_url = "http://69.21.119.148"
  username = "abc"
  password = "123"
  auth = HTTPBasicAuth(username, password)

  action = 'ACT_ID_1'
  url = base_url +'/'+action
  data= {"name": "s4",
         "value": "Swipe"}
  soup = scrape_page_with_auth(url, auth, data)
  if soup:
    # Process the response data
    print(soup.text)
    #print(response.content)
    # print(response.json())
    # Or do something else with the response

#    action_id = "ACT_ID_21"
#    post_data = {
#        "name": "s4",
#        "value": "Swipe"
#    }
#    url = base_url + '/' + action_id
