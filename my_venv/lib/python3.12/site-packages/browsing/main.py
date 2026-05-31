from web_browser.chrome import Chrome
from web_browser import Driver
import os
from web_browser.gamepad import Gamepad


def main(driver: Driver):
    print("Navigating to url")
    driver.get('https://gamepad-tester.com/')
    print("waiting for page to load")
    driver.pause(4)
    print("starting gamepad")
    gamepad = Gamepad(driver)
    print("Finished initializing gamepad")
    print("connecting to controller")
    gamepad.connect_controller()
    print("controller connected")
    print("sending buttons")
    gamepad.send_buttons('a', 'x', 'a', 'x', hold=5)


if __name__ == '__main__':
    c = Chrome(os.getenv('CHROME_DRIVER'))
    c.change_window(pos_x=500, width=1300, height=1000)
    c.add_extension('tests/extensions/Dark-Reader.crx')

    try:
        d = Driver(c)
        main(d)
        input("Press enter to quit")
        c.quit()
    except Exception as e:
        c.quit()
        raise e
