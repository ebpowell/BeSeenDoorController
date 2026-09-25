# File: door_controller/common_lib/key_fobs.py

import re
import time
from door_controller.common_lib.door_controller import door_controller
from door_controller.common_lib.utils import log_info, log_error, log_warning

class key_fobs(door_controller):
    def __init__(self, url, username, password):
        super().__init__(url, username, password)

    def parse_fob_data(self, markup):
        """Safely parses table rows containing key fob records."""
        tpl_rows = []
        if not markup or '<th>User ID</th>' not in markup:
            # Fallback check depending on controller board template
            if '<th>CardNO</th>' not in markup and '<th>Name</th>' not in markup:
                return tpl_rows

        try:
            # Regex extracts table rows with 4 or 5 columns
            rows = self.parse_tr_data(markup, r'<tr class=(.*?)</tr>', 4)
            for r in rows:
                rec_id = r[0].strip()
                fob_id = r[1].strip()
                status = r[2].strip() if len(r) > 2 else 'Active'
                owner_name = r[3].strip() if len(r) > 3 else ''
                tpl_rows.append([rec_id, fob_id, status, owner_name, self.url])
        except Exception as e:
            log_error(f"parse_fob_data error: {e}")

        return tpl_rows

    def get_fob_page(self, cursor=None):
        """
        Retrieves a single page (up to 20-40 records) of fobs from the controller.
        - cursor=None or 0: Initial Users Page (/ACT_ID_21 -> /ACT_ID_324)
        - cursor>0: Subsequent Page (/ACT_ID_325 with cursor pointer)
        Returns: (records: list, next_cursor: int or None, has_more: bool)
        """
        self.verify_or_reauth()

        if not cursor or int(cursor) == 0:
            # Load initial user table
            response = self.users_page()
        else:
            url = f"{self.url}/ACT_ID_325"
            data = {'PC': int(cursor), 'PE': 0, 'PN': 'Next'}
            response = self.get_httpresponse(url, data)

        if not response or response.status_code != 200:
            log_warning(f"Failed to fetch fob page from {self.url}: HTTP {getattr(response, 'status_code', None)}")
            return [], None, False

        batch = self.parse_fob_data(response.text)
        if not batch:
            return [], None, False

        # Defensive cursor calculation
        try:
            if len(batch) > 1:
                next_cursor = int(batch[-1][0])
            else:
                next_cursor = int(batch[0][0])
        except (ValueError, IndexError):
            next_cursor = None

        has_more = len(batch) >= 20 and next_cursor is not None
        return batch, next_cursor, has_more