from web_browser.gamepad.components import Base, JoyStick, Button, DirectionalPad
from web_browser.gamepad.components import ShoulderButtons, Menus
from time import time
from arkcloud import gamepad
import os
from pathlib import Path


class XboxController(Base):
    path = Path(os.path.dirname(gamepad.__file__)) / Path('browser')

    @classmethod
    def js_connect(cls):
        setup = cls.path / Path('connect.js')
        with open(setup, 'r') as r:
            return r.read()

    @classmethod
    def js_disconnect(cls):
        setup = cls.path / Path('disconnect.js')
        with open(setup, 'r') as r:
            return r.read()

    @classmethod
    def js_update(cls):
        setup = cls.path / Path('update.js')
        with open(setup, 'r') as r:
            return r.read()

    def __init__(self):
        super().__init__()
        self.__shoulder_buttons = ShoulderButtons()
        self.__menus = Menus()
        self.__directional_pad = DirectionalPad()
        self.connected = False

        self.a = Button(label="\033[32mA\033[0m")
        self.b = Button(label="\033[31mB\033[0m")
        self.x = Button(label="\033[34mX\033[0m")
        self.y = Button(label="\033[33mY\033[0m")

        self.left_bumper = self.__shoulder_buttons.left_bumper
        self.right_bumper = self.__shoulder_buttons.right_bumper
        self.left_trigger = self.__shoulder_buttons.left_trigger
        self.right_trigger = self.__shoulder_buttons.right_trigger

        self.select = self.__menus.select
        self.start = self.__menus.start

        self.up = self.__directional_pad.up
        self.down = self.__directional_pad.down
        self.left = self.__directional_pad.left
        self.right = self.__directional_pad.right

        self.left_joystick = JoyStick()
        self.right_joystick = JoyStick()

        self.home = self.__menus.home

    def press_buttons(self, *keys):
        for key in keys:
            self[key].press()

    def release_buttons(self, *keys):
        for key in keys:
            self[key].release()

    def on_change(self, func, *args, **kwargs):
        self.a.on_change(func, *args, **kwargs)
        self.b.on_change(func, *args, **kwargs)
        self.x.on_change(func, *args, **kwargs)
        self.y.on_change(func, *args, **kwargs)
        self.up.on_change(func, *args, **kwargs)
        self.down.on_change(func, *args, **kwargs)
        self.left.on_change(func, *args, **kwargs)
        self.right.on_change(func, *args, **kwargs)
        self.start.on_change(func, *args, **kwargs)
        self.select.on_change(func, *args, **kwargs)
        self.home.on_change(func, *args, **kwargs)
        self.left_bumper.on_change(func, *args, **kwargs)
        self.right_bumper.on_change(func, *args, **kwargs)
        self.left_trigger.on_change(func, *args, **kwargs)
        self.right_trigger.on_change(func, *args, **kwargs)
        self.left_joystick.button.on_change(func, *args, **kwargs)
        self.right_joystick.button.on_change(func, *args, **kwargs)

    def remove_on_change(self, func):
        for button in self.values():
            button.remove_change_event(func)

    def to_obj(self):
        items = {
            'a': self.a.to_obj,
            'b': self.b.to_obj,
            'x': self.x.to_obj,
            'y': self.y.to_obj,
            'directional_pad': self.__directional_pad.to_obj,
            'shoulder_buttons': self.__shoulder_buttons.to_obj,
            'left_joystick': self.left_joystick.to_obj,
            'right_joystick': self.right_joystick.to_obj,
            'menus': self.__menus.to_obj
        }
        return items

    def encode(self):
        return {
            'axes': [self.left_joystick.x, self.left_joystick.y, self.right_joystick.x, self.right_joystick.y],
            'buttons': self.__buttons(),
            'connected': self.connected,
            'id': 'Xbox 360 Controller (XInput STANDARD GAMEPAD)',
            'index': 0,
            'mapping': 'standard',
            'timestamp': time(),
            'hapticActuators': [],
        }

    def __buttons(self):
        return [
            self.a.to_obj(),
            self.b.to_obj(),
            self.x.to_obj(),
            self.y.to_obj(),
            self.__shoulder_buttons.left_bumper.to_obj(),
            self.__shoulder_buttons.right_bumper.to_obj(),
            self.__shoulder_buttons.left_trigger.to_obj(),
            self.__shoulder_buttons.right_trigger.to_obj(),
            self.__menus.select.to_obj(),
            self.__menus.start.to_obj(),
            self.left_joystick.button.to_obj(),
            self.right_joystick.button.to_obj(),
            self.__directional_pad.up.to_obj(),
            self.__directional_pad.down.to_obj(),
            self.__directional_pad.left.to_obj(),
            self.__directional_pad.right.to_obj(),
            self.__menus.home.to_obj()
        ]


if __name__ == "__main__":
    controller = XboxController()

    def print_pressed(contrl):
        print(f"controller changed: {contrl}")

    controller.on_change(print_pressed, controller)
    controller.a.press()

