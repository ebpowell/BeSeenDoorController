import re
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout, ConnectionError, HTTPError, RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.auth import HTTPBasicAuth # Import HTTPBasicAuth
import time

class door_controller:
    def __init__(self, url, username, password):
        self.auth = HTTPBasicAuth(username, password)
        self.url = url
        self.username = username
        self.password = password
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Priority': 'u=0, i'
        }
        # self.session = requests.session()
        # self.session.headers.update(headers)
        self.sql = ''
        self.timeout = 10
        self.max_retries = 2


    def get_httpresponse(self, url, data, headers=None, timeout=(10, 20), retries = 5):
        # allow overriding default timeout
        if timeout == 0:
            timeout = self.timeout
        print('timeout:', timeout)
        session_headers = self.headers
        if headers:
            # session_headers.update(headers)
            update_headers = {'Origin': self.url}
        else:
            update_headers= {'Referer': self.url+'/ACT_ID_1',
                             'Origin': self.url}
        session_headers.update(update_headers)
        # print(session_headers)
        response = self.resilient_request(url, method='POST', data=data, headers=session_headers, timeout=timeout,
                          retries=retries)
        if response.status_code == 200:
                print("door_controller.get_httpresponse: Connected")
                return response
        else:
            print(f"door_controller.get_httpresponse: Request failed with status code: {response.status_code}")
            print(response.text)
            return None

    def resilient_request(self, url, method='POST', data=None, json=None, headers=None,
                          timeout=(5, 10),
                          retries=3,
                          backoff_factor=0.3,
                          status_forcelist=(500, 502, 503, 504)):

        session = requests.Session()

        # Apply authentication to the session if provided
        session.auth = self.auth
            # Note: If auth is a (username, password) tuple, requests automatically
            # converts it to an HTTPBasicAuth object internally for the session.
            # If you pass HTTPBasicAuth(user, pass) directly, it also works.

        retry_strategy = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=frozenset(['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE'])
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        try:
            if method.upper() == 'GET':
                response = session.get(url, timeout=timeout, headers=headers)
            elif method.upper() == 'POST':
                response = session.post(url, data=data, json=json, timeout=timeout, headers=headers)
            elif method.upper() == 'PUT':
                response = session.put(url, data=data, json=json, timeout=timeout, headers=headers)
            elif method.upper() == 'DELETE':
                response = session.delete(url, timeout=timeout, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response

        except ConnectTimeout:
            print(f"Connection to {url} timed out after {retries} retries.")
            return None
        except ReadTimeout:
            print(f"Server at {url} took too long to respond with data after {retries} retries.")
            return None
        except HTTPError as e:
            print(f"HTTP error for {url}: {e.response.status_code} - {e.response.reason}")
            if e.response.status_code == 401:  # Specifically handle Unauthorized
                print("Authentication failed (401 Unauthorized). Check credentials.")
            return None
        except ConnectionError:
            print(f"Failed to connect to {url}. Check URL or network.")
            return None
        except RequestException as e:
            print(f"An unknown requests error occurred for {url}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected non-requests error occurred: {e}")
            return None

    def is_convertible_to_int(self, token):
      """
      Checks if a given token can be converted to an integer.

      Args:
        token: The token to be checked.

      Returns:
        True if the token can be converted to an integer, False otherwise.
      """
      try:
        int(token)
        return True
      except ValueError:
        return False

    def parse_tr_data(self, text, the_regex, tag_count):
        """
        Parses the given text and extracts data from <tr class=Y> tags into a list of tuples.

        Args:
            text: The input text containing <tr> tags.

        Returns:
            A list of tuples, where each tuple represents the data from a <tr class=Y> tag.
        """
        results = []
        tr_tags = re.findall(the_regex, text, re.DOTALL)
        # tr_tags = re.findall(r'<tr class=(.*?)</tr>', text, re.DOTALL)
        for tr_tag_content in tr_tags:
            td_tags = re.findall(r'<td>(.*?)</td>', tr_tag_content)
            if len(td_tags) == tag_count:  # Ensure we have the correct number of columns
                results.append(tuple(td_tags))
        # print(results)
        return results



    def add_fob(self):
            ...

    def set_permissions(self):
             ...

    def del_fob(self):
        ...




if __name__ == '__main__':
    # --- Usage ---
    # Example 1: Successful request after a retry
    print("--- Test 1: Simulating a flaky network (may timeout once or twice) ---")
    # Use a service like httpbin.org/delay/X to simulate a slow response
    # This will likely time out once and then retry
    response1 = resilient_request("https://httpbin.org/delay/7", timeout=(3, 5), retries=2, backoff_factor=1)
    if response1:
        print(f"Response 1 status: {response1.status_code}")
    else:
        print("Response 1 failed.")

    # Example 2: Request that eventually succeeds
    print("\n--- Test 2: Request that should succeed ---")
    response2 = resilient_request("https://api.github.com/zen")
    if response2:
        print(f"Response 2: {response2.text}")
    else:
        print("Response 2 failed.")

    # Example 3: Request that times out repeatedly
    print("\n--- Test 3: Request that will always time out ---")
    response3 = resilient_request("https://httpbin.org/delay/20", timeout=(2, 5), retries=1)
    if response3:
        print(f"Response 3 status: {response3.status_code}")
    else:
        print("Response 3 failed as expected.")

