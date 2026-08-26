import re
import json
import logging
import requests
from requests import Response
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import time
from door_controller.common_lib.utils import log_error, log_info

# Configure logging to align with the door_controller logger
logger = logging.getLogger("door_controller")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class ExternalSystemError(Exception):
    """Raised when the door controller system returns an unexpected or invalid response."""
    def __init__(self, status_code, response_body=None, message=None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message or f"Request failed with status code: {status_code}")


def validate_and_parse_controller_html(response: Response, expected_marker: str = None) -> str:
    """
    Validates HTML responses from the embedded BeSeen Door Controller.
    
    Since successful API calls return HTML for scraping, we inspect the page 
    content to detect if we've been redirected to the login/AddCard fallback page.
    
    :param response: The requests.Response object.
    :param expected_marker: An optional string expected in a successful scrape (e.g., table columns).
    :return: The raw HTML text if valid.
    :raises: ExternalSystemError if redirection, session expiry, or missing markers are detected.
    """

    # TO DO: IF request is AddCard AND response contains: 
    # "Add Successfully" and is_addcard_fallback = True, then return OK, not error
    # "user is deleted"
    # "edited successfully"

    text = response.text or ""
    
    # 1. Detect Redirection to the homepage / AddCard Menu (indicates session expired)
    is_addcard_fallback = (
        "<title>Web Controller</title>" in text and 
        ("Manual Input" in text or "AutoAddBySwiping" in text)
    )
    
    if is_addcard_fallback and expected_marker != 'Added Successfully': #In the case where a card is added, the proper response is to reload the addcard page with a Successful note
        logger.warning(
            f"Redirected to fallback console on {response.url}. Session expired or unauthenticated."
        )
        # Log a clean, truncated snippet instead of the full raw markup
        truncated_body = text[:150].strip().replace("\n", " ") + "..." if len(text) > 150 else text
        raise ExternalSystemError(
            status_code=response.status_code,
            response_body=truncated_body,
            message="Door controller redirected to AddCard homepage (session expired)."
        )

    # 2. Check for expected payload elements (fail-safe for empty/broken HTML)
    if expected_marker and expected_marker not in text:
        logger.error(
            f"HTML response received from {response.url} but missing expected data marker: '{expected_marker}'"
        )
        truncated_body = text[:150].strip().replace("\n", " ") + "..." if len(text) > 150 else text
        raise ExternalSystemError(
            status_code=response.status_code,
            response_body=truncated_body,
            message=f"HTML content mismatch: Missing expected marker '{expected_marker}'."
        )

    return text

class door_controller:
    def __init__(self, url, username, password):
        self.auth = HTTPBasicAuth(username, password)
        self.url = url
        self.username = username
        self.password = password
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': url,
            'Connection': 'keep-alive',
            'Referer': url+'/ACT_ID_1',
            'Upgrade-Insecure-Requests': '1',
            'Priority': 'u=0, i'
        }
        self.session = requests.session()
        self.session.headers.update(headers)
        self.sql = ''
        self.timeout = 10
        self.max_retries = 6

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.login_data = {'username': self.username,
        'pwd': self.password,
        'logid': '20101222'}
        self._logged_in = False
        self._login_response = None


    def get_httpresponse(self, url, data, expected_marker= None):
        for x in range (0, self.max_retries):
            try:
                response = self.session.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout=self.timeout)
                # Debugging code
                # raw_sent_string = response.request.body
                # print(raw_sent_string)
                # Check for successful response
                if response.status_code == 200:
                    # Mitigate Bug B: Enforce validation before proceeding
                    text = validate_and_parse_controller_html(response, expected_marker=expected_marker)  # Adjust marker as needed for your use case
        
                    # Continue with normal processing on structured JSON
                    return response
                    #return text  # Return the validated HTML text for further processing
                else:
                    log_error(f"door_controller.get_httpresponse: Request failed with status code: {response.status_code}")
                    if response.text:
                        log_error(response.text)
                    return response
            except requests.exceptions.RequestException as e:
                log_error(f"door_controller.get_httpresponse: RequestException encountered: {e}")
                if x == self.max_retries - 1:
                    raise e
                time.sleep(self.timeout / 3)
            except Exception as e:
                log_error(f"door_controller.get_httpresponse: Exception encountered: {e}")
                raise e
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

    def connect(self):
        if getattr(self, '_logged_in', False) and getattr(self, '_login_response', None) is not None:
            return self._login_response
        url = self.url+'/ACT_ID_1'
        for x in range(0, self.max_retries):
            try:
                # TO DO: Use self.get_httpresponse instead of direct requests.post to maintain session and headers
                response = self.get_httpresponse(url, data = self.login_data)
                # response = self.session.post(url, headers=self.session.headers, data=self.login_data, auth=self.auth, timeout=self.timeout)
                # Check for successful response
                if response and response.status_code == 200:
                    # print("door_controller.connect: Connected")
                    self._logged_in = True
                    self._login_response = response
                    return response
                else:
                    log_error(f"door_controller.connect: Connection Request failed with status code: {response.status_code if response else 'No Response'}")
                    if response:
                        log_error(response.text)
                    return response
            except requests.exceptions.RequestException as e:
                log_error(f"door_controller.connect: RequestException on attempt {x+1}: {e}")
                time.sleep(self.timeout / 3)
            except Exception as e:
                # raise e
                pass
        print('Connection Failed')
        return None

    def users_page(self):
        response = self.connect()
        if response and response.status_code == 200:
            self.session.headers['Referer'] = self.url + '/ACT_ID_1'
            url = self.url + '/ACT_ID_21'
            data ={'s2':'Users'}
            for x in range(0, self.max_retries):
                try:
                    response = self.get_httpresponse(url, data=data)
                    #response =  requests.post(url, headers=self.session.headers, data=data, auth=self.auth, timeout = self.timeout )
                    return response
                except requests.exceptions.RequestException as e:
                    log_error(f"door_controller.users_page: RequestException on attempt {x+1}: {e}")
                    time.sleep(self.timeout/3)
                except Exception:
                    time.sleep(self.timeout/3)
                    pass

    # def navigate(self):
    #     # obj_ACL = AccessControlList(self.username, self.password, self.url)
    #     try:
    #         response = self.connect()
    #         if response and response.status_code == 200:
    #             try:
    #                 response = self.users_page()
    #                 return response
    #             except Exception as e:
    #                 raise e
    #     except Exception as e:
    #         raise e

    def unlock_door(self, door_desc, door_no):
        self.connect()
        log_info([door_desc, door_no])
        self.session.headers['Referer'] = self.url + '/ACT_ID_1'
        target_url = self.url + '/ACT_ID_701'
        log_info(target_url)
        data = {f"UNCLOSE{door_no}": f"Remote Open #{door_no} Door {door_desc}"}
        # UNCLOSE1=Remote+Open+%231+Door+WW+Clubhouse
        try:
            response = self.get_httpresponse(target_url, data)
            raw_sent_string = response.request.body if response and hasattr(response, 'request') and hasattr(response.request, 'body') else None
            # log_info(raw_sent_string)
            if response and getattr(response, 'status_code', None) == 200:
                if response.text.find('successfully!') > 0:
                    log_info(f"Door {door_desc} remotely opened via app")
                    return response.status_code
                else:
                    log_info(raw_sent_string)
                    log_info(response.headers)
                    # log_info(response.text)
                    return None
                
            else:
                log_info(f"Door {door_desc} Remote open failed")
                return None
        except requests.exceptions.RequestException as e:
            log_error(f"Remote Door Open RequestException: {e}")
            raise e
        except Exception as e:
            log_error(f"Remote Door Open Error {e.args}")
            raise e