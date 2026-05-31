from pathlib import Path
from selenium.webdriver.chrome.options import Options


class Window:
    def __init__(self, pos_x: int = 0, pos_y: int = 0, width: int = 800, height: int = 800):
        """
        :param pos_x: The x-coordinate where the window is placed
        :param pos_y: The y-coordinate where the window is placed
        :param width: The length of width in pixels
        :param height: The length of width in pixels
        """
        if pos_x < 0:
            raise AttributeError(f"Argument pos_x must be 0 or greater but was: {pos_x=}")
        if pos_y < 0:
            raise AttributeError(f"Argument pos_y must be 0 or greater but was: {pos_y=}")
        if width < 0:
            raise AttributeError(f"Argument width must be 0 or greater but was: {width=}")
        if height < 0:
            raise AttributeError(f"Argument height must be 0 or greater but was: {height=}")
        self.x = pos_x
        self.y = pos_y
        self.width = width
        self.height = height

    def add_to_browser(self, options: Options):
        options.add_argument(f"--window-size={self.width},{self.height}")
        options.add_argument(f"--window-position={self.x},{self.y}")
