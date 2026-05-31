from pathlib import Path
from selenium.webdriver.chrome.options import Options


class Extension:
    def __init__(self, path: str or Path):
        self.file = Path(path)
        if not self.file:
            raise FileNotFoundError(f"Extension path is invalid and must be provided")
        if not self.file.exists():
            raise FileNotFoundError(f"Extension path does not exist: {str(self.file)}")
        if self.file.suffix != '.crx':
            raise FileNotFoundError(f"Extension file needs to end in '.crx': {str(self.file.name)}")

    def add_to_browser(self, options: Options):
        options.add_extension(str(self.file))
