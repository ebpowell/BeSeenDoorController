from web_browser.gamepad.components import Base
from web_browser.gamepad.components import Button


class JoyStick(Base):
    def __init__(self, label=None):
        super().__init__(label=label)
        self.x = 0
        self.y = 0
        self.button = Button()

    def press(self):
        self.button.press()

    def release(self):
        self.button.release()

    def __setattr__(self, key, value):
        if key in self.keys() and (isinstance(value, int) or isinstance(value, float)):
            value = 1 if value > 1 else value
            value = -1 if value < -1 else value
        self.__dict__[key] = value

    def to_obj(self) -> dict:
        return {'x': self.x, 'y': self.y, 'button': self.button.to_obj()}


if __name__ == "__main__":
    j = JoyStick()
    print(j)
    j.x = 2
    print(j)
