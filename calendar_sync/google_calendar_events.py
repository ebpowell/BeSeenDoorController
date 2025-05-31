import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarAPI:
    def __init__(self, token_file='token.json', credentials_file='credentials.json'):
        """
        Initializes the Google Calendar API client.

        Args:
            token_file (str): Path to the file storing the user's access and refresh tokens.
            credentials_file (str): Path to the client secrets file downloaded from Google Cloud Console.
        """
        self.SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        self.creds = None
        self.token_file = token_file
        self.credentials_file = credentials_file
        self._authenticate()
        self.service = build('calendar', 'v3', credentials=self.creds)

    def _authenticate(self):
        """Handles authentication with the Google Calendar API."""
        if os.path.exists(self.token_file):
            self.creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                self.creds = flow.local_server_redirect()
            # Save the credentials for the next run
            with open(self.token_file, 'w') as token:
                token.write(self.creds.to_json())

    def get_upcoming_events(self, calendar_id='primary', max_results=10):
        """
        Retrieves upcoming events from the specified calendar.

        Args:
            calendar_id (str): The ID of the calendar to retrieve events from.
                               'primary' refers to the user's primary calendar.
            max_results (int): The maximum number of events to retrieve.

        Returns:
            list: A list of dictionaries, where each dictionary represents an event.
        """
        try:
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            print(f'Getting the next {max_results} upcoming events from calendar: {calendar_id}')
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if not events:
                print('No upcoming events found.')
                return []

            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append({
                    'id': event['id'],
                    'summary': event.get('summary', 'No Title'),
                    'start': start,
                    'end': event['end'].get('dateTime', event['end'].get('date')),
                    'htmlLink': event['htmlLink']
                })
            return event_list

        except HttpError as error:
            print(f'An error occurred: {error}')
            return []

    # Note: Google Calendar API treats "tasks" as a separate resource.
    # While you can represent tasks as events, a more robust solution for
    # dedicated task management would involve the Google Tasks API.
    # This example focuses on Calendar events, which can include event-like tasks.


# Example Usage:
if __name__ == '__main__':
    # BEFORE RUNNING:
    # 1. Go to Google Cloud Console (console.cloud.google.com)
    # 2. Create a new project or select an existing one.
    # 3. Enable the "Google Calendar API" for your project.
    # 4. Go to "Credentials" -> "Create Credentials" -> "OAuth client ID".
    # 5. Select "Desktop app" (or Web application if preferred, adjusting redirect URIs).
    # 6. Download the client configuration JSON file and rename it to 'credentials.json'
    #    and place it in the same directory as this script.

    calendar_api = GoogleCalendarAPI()

    print("\n--- Upcoming Events ---")
    upcoming_events = calendar_api.get_upcoming_events(max_results=5)
    for event in upcoming_events:
        print(f"  Event: {event['summary']}")
        print(f"  Start: {event['start']}")
        print(f"  Link: {event['htmlLink']}\n")

    # Example of accessing a different calendar (if you know its ID)
    # print("\n--- Events from a Specific Calendar ID (e.g., holiday calendar) ---")
    # You would replace 'your_calendar_id_here' with an actual calendar ID
    # specific_calendar_events = calendar_api.get_upcoming_events(
    #     calendar_id='en.usa#holiday@group.v.calendar.google.com', max_results=3
    # )
    # for event in specific_calendar_events:
    #     print(f"  Event: {event['summary']}")
    #     print(f"  Start: {event['start']}")
    #     print(f"  Link: {event['htmlLink']}\n")