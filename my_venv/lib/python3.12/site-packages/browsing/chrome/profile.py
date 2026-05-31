from pathlib import Path
from selenium.webdriver.chrome.options import Options
import os


class Profile:
    def __init__(self, profile_path: str or Path = None, profile_number: int = 0):
        """
        :param profile_path: Typically found at "%LOCALAPPDATA%/Google/Chrome Dev/User Data"
        :param profile_number: The profile index found at the directory of profile_path
        """
        default = Path(os.getenv('LOCALAPPDATA')) / Path('Google/Chrome Dev/User Data')
        self.directory = profile_path and Path(profile_path) or default
        self.profile_number = profile_number
        if not self.directory:
            raise FileNotFoundError(f"Profile path is invalid and must be provided")
        if not self.directory.exists():
            raise FileNotFoundError(f"Profile path does not exist: {str(self.directory)}")
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Profile path must be a directory: {str(self.directory)}")

    def add_to_browser(self, options: Options):
        options.add_argument(f"--user-data-dir={self.directory}")
        options.add_argument(f"--profile-directory=Profile {self.profile_number}")
