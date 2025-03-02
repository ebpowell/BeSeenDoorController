import requests
from bs4 import BeautifulSoup

def login(username, password, login_url):
    """
    Logs in to the website and returns a session object.

    Args:
        username (str): Username for login.
        password (str): Password for login.
        login_url (str): URL of the login page.

    Returns:
        requests.Session: A session object with the authenticated session.
    """
    session = requests.Session()
    login_data = {'username': username, 'password': password}  # Replace with actual form field names
    response = session.post(login_url, data=login_data)

    # Check if login was successful (e.g., by checking for a successful redirect or a specific message in the response)
    if response.status_code == 200:  # Adjust this check based on the website's login response
        return session
    else:
        print(f"Login failed. Status code: {response.status_code}")
        return None

def get_data_from_protected_page(session, url):
    """
    Fetches data from a protected page using the authenticated session.

    Args:
        session (requests.Session): The authenticated session object.
        url (str): URL of the protected page.

    Returns:
        str: The HTML content of the protected page.
    """
    if session:
        response = session.get(url)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
    return None

# Example Usage
if __name__=='__main__':
    login_url = "http://69.21.119.148"
    protected_page_url = "http://69.21.119.148/ACT_ID_21"  # Replace with the actual URL

    username = "abc"
    password = "654321"

    session = login(username, password, login_url)

    if session:
        data = get_data_from_protected_page(session, protected_page_url)
        if data:
            # Process the retrieved data (e.g., parse with BeautifulSoup)
            soup = BeautifulSoup(data, 'html.parser')
            # Extract data from the HTML using BeautifulSoup
            # ...
            print(soup)

