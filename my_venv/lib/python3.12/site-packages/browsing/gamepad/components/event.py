from collections.abc import Iterable


class Event:
    def __init__(self):
        self.event = {}

    def add_event(self, func, *args, **kwargs):
        self.event[func] = (args, kwargs)

    def remove_event(self, func):
        if func in self.event:
            del self.event[func]

    def __iadd__(self, other):
        assert callable(other), f"Right side must be a function but was: {other}"
        self.event[other] = (tuple(), {})

    def __isub__(self, other):
        if other in self.event:
            del self.event[other]

    def __setitem__(self, key, value):
        assert callable(key), f"{key} must be a function"
        assert isinstance(value, Iterable), f"{value} must be a list"
        self.event[key] = value

    def __delitem__(self, key):
        if key in self.event:
            del self.event[key]

    def __iter__(self):
        funcs = list(self.event.keys())
        for func in funcs:
            if func in self.event:
                args, kwargs = self.event[func]
                yield func, args, kwargs

    def dispatch(self):
        for func, args, kwargs in self:
            func(*args, **kwargs)