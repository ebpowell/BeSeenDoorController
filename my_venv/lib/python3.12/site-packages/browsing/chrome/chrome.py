from selenium import webdriver
from web_browser.chrome.extension import Extension
from web_browser.chrome.background_process import BackgroundProcess
from web_browser.chrome.window import Window
from web_browser.chrome.profile import Profile
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Remote
from pathlib import Path


class Chrome:
    def __init__(self, chrome_driver_path: str or Path = None):
        self.selenium: webdriver.Chrome = None
        self.chrome_driver_path = chrome_driver_path
        self.options = Options()
        self.settings = []

    def add_extension(self, extension_path: str or Path):
        extension = Extension(extension_path)
        extension.add_to_browser(self.options)

    def run_as_a_background_process(self):
        background_process = BackgroundProcess()
        background_process.add_to_browser(self.options)

    def add_chrome_user_profile(self, user_profile_path: str or Path, profile_number: int):
        profile = Profile(user_profile_path, profile_number)
        profile.add_to_browser(self.options)

    def change_window(self, pos_x: int = 0, pos_y: int = 0, width: int = 800, height: int = 800):
        window = Window(pos_x=pos_x, pos_y=pos_y, width=width, height=height)
        window.add_to_browser(self.options)

    def open(self):
        # self.selenium = Remote(command_executor=str(chrome_driver_uri, options=self.options.bind())
        service = Service(executable_path=str(self.chrome_driver_path))
        self.selenium = webdriver.Chrome(service=service, options=self.options)

    def quit(self):
        self.selenium.quit()
        self.selenium = None

    def __repr__(self):
        return f"""<Chrome()>"""
