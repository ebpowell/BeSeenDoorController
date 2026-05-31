from web_browser.gamepad.components import Button
from web_browser.gamepad.components import Base


class ShoulderButtons(Base):
    def __init__(self):
        super().__init__()
        self.left_bumper = Button()
        self.right_bumper = Button()
        self.left_trigger = Button()
        self.right_trigger = Button()

    def to_obj(self):
        return {
            'left_bumper': self.left_bumper.to_obj(),
            'right_bumper': self.right_trigger.to_obj(),
            'left_trigger': self.left_trigger.to_obj(),
            'right_trigger': self.right_trigger.to_obj()
        }


if __name__ == "__main__":
    b = ShoulderButtons()

    print(b)
    print(repr(b))
    print(b.to_json)
