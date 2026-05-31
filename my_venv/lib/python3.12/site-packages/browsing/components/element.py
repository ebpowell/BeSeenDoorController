from arklibrary import pathify
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from itertools import groupby
from selenium.webdriver.common.action_chains import ActionChains
from pathlib import Path


class Element:
    @classmethod
    def null_element(cls):
        return Element()

    def __init__(self, driver: WebDriver = None, element: WebElement = None):
        self.ele: WebElement = element
        self.driver: WebDriver = driver

    def enabled(self) -> bool:
        if self.exists():
            return self.ele.is_enabled()
        return False

    def disabled(self) -> bool:
        if self.exists():
            return not self.ele.is_enabled()
        return False

    def tag(self) -> str:
        if self.exists():
            return self.ele.tag_name
        return ''

    def value(self):
        if self.exists():
            return self.ele.get_attribute('value')
        return None

    def text(self) -> str:
        if self.exists():
            return self.ele.text
        return ''

    def text_content(self) -> str:
        if self.exists():
            self.get_attribute("textContent")
        return ''

    def get_attribute(self, name: str) -> str:
        if self.exists():
            return self.ele.get_attribute(name)

    def hover(self):
        if self.exists():
            action = ActionChains(self.driver)
            action.move_to_element(self.ele).perform()

    def click(self):
        if self.exists():
            self.ele.click()

    def click_hold(self, pause=0):
        if self.exists():
            action = ActionChains(self.driver)
            action.click_and_hold(self.ele)
            action.pause(pause).perform()

    def double_click(self):
        if self.exists():
            action = ActionChains(self.driver)
            action.double_click(self.ele).perform()

    def drag_drop_coord(self, x: int=0, y: int=0, pause=0):
        if self.exists():
            action = ActionChains(self.driver)
            if pause == 0:
                action.drag_and_drop_by_offset(self.ele, x, y).perform()
            else:
                action.click_and_hold(self.ele).pause(pause)
                action.move_by_offset(x, y).pause(pause)
                action.release(self.ele).perform()

    def drag_drop(self, to_element: 'Element', pause=0, x_offset=0, y_offset=0):
        if self.exists() and to_element:
            action = ActionChains(self.driver)
            if pause == 0:
                action.drag_and_drop(self.ele, to_element.ele).perform()
            else:
                action.click_and_hold(self.ele)
                action.pause(pause)
                action.move_to_element_with_offset(to_element.ele, x_offset, y_offset)
                action.pause(pause)
                action.release(self.ele)
                action.perform()

    def release(self, pause=0):
        if self.exists():
            action = ActionChains(self.driver)
            action.pause(pause).release(self.ele).perform()

    def scroll_to_here(self):
        if self.exists():
            action = ActionChains(self.driver)
            action.scroll_to_element(self.ele).perform()

    def right_click(self):
        if self.exists():
            action = ActionChains(self.driver)
            action.context_click(self.ele).perform()

    def clear(self):
        if self.exists():
            self.ele.clear()

    def send_keys(self, *keys):
        if self.exists():
            for key in keys:
                self.ele.send_keys(key)

    def send_buttons(self, *keys):
        if self.exists():
            alt_keys = {k: v for k, v in Keys.__dict__.items() if k[0] != '_'}
            for key in keys:
                if key in alt_keys:
                    self.ele.send_keys(alt_keys[key])
                else:
                    self.ele.send_keys(key)

    def img(self, **kwargs) -> 'Element':
        return self.element('img', **kwargs)

    def iframe(self, **kwargs) -> 'Element':
        return self.element('iframe', **kwargs)

    def iframes(self, **kwargs) -> list:
        return self.elements('iframe', **kwargs)

    def span(self, **kwargs) -> 'Element':
        return self.element('span', **kwargs)

    def h1(self, **kwargs) -> 'Element':
        return self.element('h1', **kwargs)

    def h2(self, **kwargs) -> 'Element':
        return self.element('h2', **kwargs)

    def h3(self, **kwargs) -> 'Element':
        return self.element('h3', **kwargs)

    def h4(self, **kwargs) -> 'Element':
        return self.element('h4', **kwargs)

    def label(self, **kwargs) -> 'Element':
        return self.element('label', **kwargs)

    def div(self, **kwargs) -> 'Element':
        return self.element('div', **kwargs)

    def link(self, **kwargs) -> 'Element':
        return self.element('a', **kwargs)

    def input(self, **kwargs) -> 'Element':
        return self.element('input', **kwargs)

    def svg(self, **kwargs) -> 'Element':
        return self.element('svg', **kwargs)

    def svgs(self, kwargs) -> list['Element']:
        return self.elements('svg', **kwargs)

    def button(self, **kwargs) -> 'Element':
        return self.element('button', **kwargs)

    def textarea(self, **kwargs) -> 'Element':
        return self.element('textarea', **kwargs)

    def xpath(self, path: str, **kwargs) -> 'Element':
        elements = self.xpaths(path, **kwargs)
        if elements:
            return elements[0]
        return Element.null_element()

    def xpaths(self, path: str, timeout=0, **kwargs) -> list['Element']:
        if not self.exists():
            return []
        try:
            if timeout == 0:
                elements = self.ele.find_elements(By.XPATH, path)
            else:
                elements = WebDriverWait(self.driver, timeout).until(ChildrenXPath(self, path))
            return [Element(driver=self.driver, element=e) for e in elements]
        except Exception as e:
            return []

    def element(self, tag: str = None, timeout=0, text: str = None, class_name: str = None,
                **kwargs) -> 'Element':
        elements = self.elements(tag=tag, timeout=timeout, text=text, class_name=class_name, **kwargs)
        if elements:
            return elements[0]
        return Element.null_element()

    def elements(self, tag: str = None, timeout=0, text: str = None, class_name: str = None,
                 **kwargs) -> list['Element']:
        if not self.exists():
            return []
        path = f".//{tag or '*'}" + pathify(text=text, class_name=class_name, **kwargs)
        try:
            return self.xpaths(path, timeout=timeout)
        except TimeoutException as e:
            return []

    def children(self, tag: str = None, timeout=0, text: str = None, class_name: str = None,
                 **kwargs) -> list:
        """ Children one level deep """
        if self.exists():
            path = f"./child::{tag or '*'}" + pathify(text=text, class_name=class_name, **kwargs)
            return self.xpaths(path, timeout=timeout)
        return []

    def children_deep(self, tag: str = None, timeout=0, text: str = None, class_name: str = None,
                 **kwargs) -> list:
        """ Children all levels deep """
        if self.exists():
            path = f".//child::{tag or '*'}" + pathify(text=text, class_name=class_name, **kwargs)
            return self.xpaths(path, timeout=timeout)
        return []

    def parent(self) -> 'Element':
        if self.exists():
            p = self.xpath('./parent::*')
            if not p.driver or not p.ele:
                return self
            return p
        return Element.null_element()

    def parents(self, tag: str = None, timeout=0, text: str = None, class_name: str = None,
                 **kwargs) -> list:
        if self.exists():
            path = f".//parent::{tag or '*'}" + pathify(text=text, class_name=class_name, **kwargs)
            return self.xpaths(path, timeout=timeout)
        return []

    def root(self, timeout=0, **kwargs) -> 'Element':
        if not self.driver:
            return Element.null_element()
        element = WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.XPATH, './*')))
        return Element(driver=self.driver, element=element)

    def group_by(self, tag: str, key=None, **kwargs):
        if key is None:
            key = lambda x: x
        elements = self.elements(tag, **kwargs)
        grouped = [(key(elements), e) for e in elements]
        grouped.sort()
        return groupby(grouped, key=lambda x: x[0])

    def attributes(self) -> dict:
        if not self.exists():
            return {}
        html_string = self.ele.get_attribute('outerHTML')
        soup = BeautifulSoup(html_string, 'html.parser')
        children = list(soup.children)  # type: list
        if children:
            return children[0].attrs
        return {}

    def screenshot(self, filename: str):
        self.ele.screenshot(filename)

    def screenshot_base64(self):
        return self.ele.screenshot_as_base64

    def png(self):
        return self.ele.screenshot_as_png

    def css_styles(self) -> dict:
        names = self.driver.execute_script("""
        let elem = arguments[0];
        return window.getComputedStyle(elem);
        """, self.ele)
        return {name: self.ele.value_of_css_property(name) for name in names}

    def is_displayed(self) -> bool:
        if self.exists():
            return self.ele.is_displayed()
        return False

    def is_selected(self) -> bool:
        if self.exists():
            return self.ele.is_selected()
        return False

    def wait_until_disappear(self, timeout=0):
        try:
            WebDriverWait(self.driver, timeout).until(EC.invisibility_of_element(self.ele))
        except (NoSuchElementException, StaleElementReferenceException):
            return self
        return self

    def wait_until_clickable(self, timeout=0):
        WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable(self.ele))
        return self

    def wait_until_selected(self, timeout=0):
        WebDriverWait(self.driver, timeout).until(EC.element_to_be_selected(self.ele))
        return self

    def wait_until_text_present(self, text: str, timeout=0):
        WebDriverWait(self.driver, timeout).until(EC.text_to_be_present_in_element(self.ele, text))
        return self

    def exists(self):
        try:
            if not self.ele or not self.driver:
                return False
            self.ele.is_enabled()
            return True
        except StaleElementReferenceException:
            return False

    def save_png(self, path: str or Path):
        with open(path, 'wb') as wb:
            wb.write(self.ele.screenshot_as_png)

    def __getitem__(self, attribute: str):
        attrs = self.attributes()
        if attribute in attrs:
            return attrs[attribute]
        raise IndexError(f"Attribute '{attribute}' is not in the element.")

    def __contains__(self, item):
        attrs = self.attributes()
        for value in attrs.values():
            if type(value) == str and item == value:
                return True
            elif type(value) == list and item in value:
                return True
        return False

    def __eq__(self, other):
        return self.ele == other.ele

    def __iter__(self):
        self.__iter_children = self.children()
        self.__i = 0
        return self

    def __next__(self):
        if self.__i >= len(self.__iter_children):
            raise StopIteration
        child = self.__iter_children[self.__i]
        self.__i += 1
        yield child

    def __repr__(self):
        if not self.exists():
            return "\033[34m<\033[96m/\033[34m>\033[0m"
        attrs = [f'\033[96m{self.ele.tag_name}\033[0m']
        for key, val in self.attributes().items():
            if type(val) == list:
                prop = ' '.join([str(v) for v in val])
                attrs.append(f'\033[34m{key}="\033[31m{prop}\033[34m"\033[0m')
            else:
                attrs.append(f'\033[34m{key}="\033[31m{str(val)}\033[34m"\033[0m')
        return f"\033[34m<\033[0m{' '.join(attrs)}\033[34m>\033[0m"

    def __str__(self):
        if self.exists():
            return self.ele.text
        return ''


class ChildrenXPath:
    """ https://stackoverflow.com/questions/35606708/what-is-the-difference-between-and-in-xpath
    There are several distinct, key XPath concepts in play here...

    Absolute vs relative XPaths (/ vs .)

    / introduces an absolute location path, starting at the root of the document.
    . introduces a relative location path, starting at the context node.

    Named element vs any element (ename vs *)

    /ename  selects an ename root element
    ./ename selects all ename child elements of the current node.
    /*      selects the root element, regardless of name.
    ./* or * selects all child elements of the context node, regardless of name.

    descendant-or-self axis (//*)

    //ename     selects all ename elements in a document.
    .//ename    selects all ename elements at or beneath the context node.
    //* selects all elements in a document, regardless of name.
    .//* selects all elements, regardless of name, at or beneath the context node.
    """

    def __init__(self, element: Element, xpath: str):
        self.element: WebElement = element.ele
        self.xpath: str = xpath

    def __call__(self, driver: WebDriver):
        try:
            elements = self.element.find_elements(By.XPATH, self.xpath)
            if elements:
                return elements
        except Exception as e:
            return False
        return False
