from web_browser.gamepad.components import Base


class Button(Base):
    def __init__(self, label=None):
        super().__init__(label)
        self.pressed = False
        self.touched = False
        self.value = 0

    def press(self):
        self.__dict__.update({'pressed': True, 'value': 1})
        self._change_event.dispatch()

    def release(self):
        self.__dict__.update({'pressed': False, 'value': 0})
        self._change_event.dispatch()

    def to_obj(self):
        return {'pressed': self.pressed, 'touched': self.touched, 'value': self.value}


if __name__ == "__main__":
    b = Button(label='A')

    print(b)
    print(repr(b))
    print(b.to_json)

    def pressed_message(button):
        print("button was changed")
        button.remove_change_event(pressed_message)

    b.on_change(pressed_message, b)

    b.press()
    b.release()



