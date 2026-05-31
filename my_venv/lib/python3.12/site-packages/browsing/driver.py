from arklibrary import pathify
from web_browser.chrome.chrome import Chrome
from web_browser.components import Element
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from urllib.parse import urlparse
from selenium.webdriver.common.action_chains import ActionChains
from pathlib import Path
from time import sleep


class Driver:
    DEFAULT = {'x': -1000, 'y': 100, 'width': 800, 'height': 800}
    DRIVERS = {}
    __INDEX = 0

    def __init__(self, browser: Chrome):
        self.browser = browser
        if browser.selenium is None:
            browser.open()
        self._current_tab = 'about_blank'
        self.tabs = {self._current_tab: self.browser.selenium.window_handles[-1]}
        self.close_irrelevant_tabs()
        self.__id = Driver.__INDEX
        Driver.DRIVERS[Driver.__INDEX] = self
        Driver.__INDEX += 1

    def bind(self):
        return self.browser.selenium

    def get(self, url, timeout=0) -> None:
        if self.browser.selenium:
            domain = urlparse(url).netloc
            domain = domain.replace("www.", "")
            if domain in self.tabs:
                self.switch_tab(domain)
            self.browser.selenium.get(url)
            if domain not in self.tabs:
                self.tabs[domain] = self.tabs[self._current_tab]
                del self.tabs[self._current_tab]
                self._current_tab = domain
            for i in range(timeout if timeout > 0 else 5):
                state = self.execute_script('return document.readyState')
                if state == 'complete':
                    break
                self.pause(1)

    def switch_tab(self, name) -> None:
        if self.browser.selenium and name in self.tabs and self._current_tab != name:
            self.browser.selenium.switch_to.window(self.tabs[name])
            self._current_tab = name

    def close_tab(self, name: str = None) -> None:
        if name is None:
            name = self._current_tab
        if self.browser.selenium and name in self.tabs:
            if len(self.tabs) == 1:
                Driver.close(self)
            else:
                prev = self._current_tab
                if self._current_tab != name:
                    self.switch_tab(name)
                self.browser.selenium.close()
                del self.tabs[name]
                self.switch_tab(prev)
        if len(self.tabs) == 0:
            self.close()

    def new_tab(self, key: str=None, url: str=None) -> None:
        if not self.browser.selenium or not url:
            return
        if key is None or key not in self.tabs:
            self.browser.selenium.execute_script(f"window.open('{url}');")
            if not key:
                key = self.domain()
            self.tabs[key] = self.browser.selenium.window_handles[-1]
            self.switch_tab(key)
            self._current_tab = key
        else:
            self.browser.selenium.switch_to.window(self.tabs[key])
        self.browser.selenium.get(url)

    def switch_to(self, frame: Element) -> None:
        self.browser.selenium.switch_to.frame(frame.ele)

    def domain(self) -> str:
        if self.browser.selenium:
            netloc = urlparse(self.browser.selenium.current_url).netloc
            netloc = netloc.replace("www.", "")
            return netloc

    def url(self) -> str:
        if self.browser.selenium:
            return self.browser.selenium.current_url

    def browser_name(self) -> str:
        if self.browser.selenium:
            return self.browser.selenium.name.title()

    def root_element(self) -> 'Element':
        element = self.browser.selenium.find_element(By.XPATH, './*')
        return Element(driver=self.browser.selenium, element=element)

    def xpath(self, path: str, timeout=0, **kwargs) -> 'Element':
        elements = self.xpaths(path, timeout=timeout, **kwargs)
        if elements:
            return elements[0]
        return Element.null_element()

    def xpaths(self, path: str, timeout=0, **kwargs) -> list['Element']:
        return self.root_element().xpaths(path, timeout=timeout, **kwargs)

    def element(self, tag: str = None, timeout=0, class_name=None, text=None, **kwargs) -> 'Element':
        elements = self.elements(tag=tag, timeout=timeout, class_name=class_name, text=text, **kwargs)
        if elements:
            return elements[0]
        path = (tag and f"//{tag}" or '//*') + pathify(text=text, class_name=class_name, **kwargs)
        raise TimeoutException(f"\nUnable to find path: {path}")

    def elements(self, tag: str = None, timeout=0, class_name=None, text=None, **kwargs) -> list['Element']:
        if not self.browser.selenium:
            return []
        path = f"//{tag or '*'}" + pathify(text=text, class_name=class_name,  **kwargs)
        try:
            return self.xpaths(path, timeout=timeout)
        except TimeoutException as e:
            return []

    def execute_script(self, script: str, *args) -> None:
        if self.browser.selenium:
            return self.browser.selenium.execute_script(script, *args)

    def send_button(self, *keys, hold=0, spread=0) -> None:
        if self.browser.selenium:
            alt_keys = {k: v for k, v in Keys.__dict__.items() if k[0] != '_'}
            for key in keys:
                action = ActionChains(self.browser.selenium)
                if key.upper() in alt_keys:
                    action.key_down(alt_keys[key.upper()])
                    action.pause(hold)
                    action.key_up(alt_keys[key.upper()])
                    action.perform()
                    self.pause(spread)
                elif len(key) > 0:
                    for c in key:
                        action.key_down(c)
                        action.perform()
                    self.pause(hold)
                    action.perform()
                    for c in key:
                        action.key_up(c)
                        action.perform()
                    self.pause(spread)
                    action.perform()
                else:
                    action.key_down(key)
                    action.pause(hold)
                    action.key_up(key)
                    action.perform()
                    self.pause(spread)

    def send_keys(self, *keys) -> None:
        if self.browser.selenium:
            action = ActionChains(self.browser.selenium)
            action.send_keys(*keys)
            action.perform()

    def accept_alert(self) -> None:
        if self.browser.selenium:
            self.browser.selenium.switch_to.alert.accept()

    def cancel_alert(self) -> None:
        if self.browser.selenium:
            self.browser.selenium.switch_to.alert.dismiss()

    def alert_message(self) -> None:
        if self.browser.selenium:
            return self.browser.selenium.switch_to.alert.text

    def send_to_alert(self, keys: str) -> None:
        if self.browser.selenium:
            self.browser.selenium.switch_to.alert.send_keys(keys)

    def pause(self, seconds: int or float) -> None:
        if self.browser.selenium:
            sleep(seconds)
            # the one below needs an action before the pause
            # action.send_keys("hello")
            # action.pause(seconds)
            # action.send_keys("world").perform()

    def close(self) -> None:
        if self.browser.selenium:
            self.browser.quit()
        if self.__id in Driver.DRIVERS:
            del Driver.DRIVERS[self.__id]
        self._current_tab = None
        self.__id = None
        self.__kwargs = {}
        self.tabs = {}

    def close_irrelevant_tabs(self) -> None:
        known_handles = set(self.tabs.values())
        all_handles = self.browser.selenium.window_handles
        for handle in all_handles:
            if handle not in known_handles:
                self.browser.selenium.switch_to.window(handle)
                self.browser.selenium.close()
        self.browser.selenium.switch_to.window(self.tabs[self._current_tab])

    def vertical_scroll(self, amount: int) -> None:
        if self.browser.selenium:
            action = ActionChains(self.browser.selenium)
            action.scroll_by_amount(amount, 0).perform()

    def horizontal_scroll(self, amount: int) -> None:
        if self.browser.selenium:
            action = ActionChains(self.browser.selenium)
            action.scroll_by_amount(0, amount).perform()

    def save_png(self, path: str or Path) -> None:
        if self.browser.selenium:
            with open(path, 'wb') as wb:
                wb.write(self.browser.selenium.get_screenshot_as_png())

    def png_bytes(self):
        return self.browser.selenium.get_screenshot_as_png()

    def __contains__(self, site_name):
        if not self.browser.selenium:
            return False
        return site_name in self.tabs

    def __getitem__(self, site_name) -> None:
        self.switch_tab(site_name)

    def __setitem__(self, key, url):
        self.new_tab(key, url)

    def __delitem__(self, name):
        self.close_tab(name)

    def __len__(self):
        if not self.browser.selenium:
            return 0
        return len(self.tabs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        Driver.close(self)

    def __str__(self):
        args = ', '.join([f"{repr(k)}" for k in self.tabs.keys()])
        s = f"""<Driver({args})>"""
        return s

    def __repr__(self):
        args = ', '.join([f"{repr(k)}" for k in self.tabs.keys()])
        if self.browser_name():
            return f"""<Driver({args})>"""
        return f"""</>"""

    @classmethod
    def destroy_all(cls) -> None:
        drivers = list(cls.DRIVERS.values())
        for driver in drivers:
            driver.close()
        cls.DRIVERS = {}
        cls.__INDEX = 0

    def clear_tabs(self) -> None:
        while len(self.tabs) > 1:
            name = next(iter(self.tabs.keys()))
            self.close_tab(name)
        prev = self._current_tab
        self.new_tab(key="about_blank", url="about:blank")
        self.close_tab(prev)

    @classmethod
    def find_driver(cls):
        for found_driver in Driver.DRIVERS.values():
            return found_driver

    @classmethod
    def new(cls, **kwargs):
        found_driver = cls.find_driver()
        if found_driver:
            found_driver.new_tab(key='about_blank', url="about:blank")
            return found_driver
        return Driver(**kwargs)


