from web_browser.gamepad.xbox.xbox import XboxController
from web_browser.driver import Driver


def controller_listener(driver: Driver, controller: XboxController):
    driver.execute_script(controller.js_update(), controller.encode())


class Gamepad:
    def __init__(self, driver: Driver):
        self.driver = driver
        self.controller = XboxController()
        self.controller.on_change(controller_listener, self.driver, self.controller)

    def connect_controller(self):
        self.driver.execute_script(self.controller.js_connect())
        self.controller.on_change(controller_listener, self.driver, self.controller)

    def disconnect_controller(self):
        self.driver.execute_script(self.controller.js_disconnect())

    def disable_controller(self):
        self.driver.execute_script(self.controller.js_disconnect())
        self.controller.remove_on_change(controller_listener)

    def send_buttons(self, *keys, hold=0.1, spread: float = 0):
        for key in keys:
            self.controller[key].press()
            self.driver.pause(hold)
            self.controller[key].release()
            self.driver.pause(spread)

    def send_multi_buttons(self, keys: list[str], hold=0.1, spread=0):
        for key in keys:
            self.controller[key].press()
        self.driver.pause(hold)
        for key in keys:
            self.controller[key].release()
        self.driver.pause(spread)