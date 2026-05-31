from web_browser.gamepad.components import Base
from web_browser.gamepad.components import Button


class Menus(Base):
    def __init__(self):
        super().__init__()
        self.home = Button()
        self.start = Button()
        self.select = Button()

    def to_obj(self):
        return {
            'home': self.home.to_obj(),
            'start': self.start.to_obj(),
            'select': self.select.to_obj()
        }


if __name__ == "__main__":
    menus = Menus()
    print(menus)
    print(repr(menus))
    print(menus.to_json)
