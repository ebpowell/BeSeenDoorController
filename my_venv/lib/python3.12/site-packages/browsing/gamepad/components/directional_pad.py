from web_browser.gamepad.components import Base, Button


class DirectionalPad(Base):
    def __init__(self):
        super().__init__()
        self.up = Button(label='Up')
        self.down = Button(label='Down')
        self.left = Button(label='Left')
        self.right = Button(label='Right')

    def to_obj(self):
        return {
            'up': self.up.to_obj(),
            'down': self.down.to_obj(),
            'left': self.left.to_obj(),
            'right': self.right.to_obj()
        }


if __name__ == "__main__":
    pad = DirectionalPad()
    print(pad)
    print(repr(pad))
    print(pad.to_json)
