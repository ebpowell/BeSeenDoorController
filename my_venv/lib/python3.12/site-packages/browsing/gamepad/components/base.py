import json
from abc import abstractmethod
from collections.abc import Iterable
import re
from web_browser.gamepad.components.event import Event


class Base:
    def __init__(self, label=None):
        self._label = label
        self._change_event = Event()

    @abstractmethod
    def to_obj(self) -> dict:
        ...

    def to_json(self) -> str:
        return json.dumps(self.to_obj())

    def __iter__(self):
        return iter([k for k in self.__dict__.keys() if re.match('[a-zA-Z0-9].*', k)])

    def __contains__(self, item):
        if isinstance(item, str):
            return item.lower() in self.__dict__
        return False

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.__dict__[item.lower()]

    def keys(self) -> Iterable:
        return list(self)

    def values(self) -> Iterable:
        return dict(self).values()

    def items(self) -> Iterable:
        return dict(self).items()

    def on_change(self, func, *args, **kwargs):
        self._change_event[func] = (args, kwargs)

    def remove_change_event(self, func):
        del self._change_event[func]

    def __setattr__(self, key, value):
        changed = key in self.__dict__ and self.__dict__[key] != value
        self.__dict__[key] = value
        if changed:
            self._change_event.dispatch()

    def __str__(self):
        label = self._label and f":{self._label}" or ''
        args = []
        for k, v in self.items():
            v = v if hasattr(v, '__class__') else repr(v)
            args.append(f'\033[34m{k}=\033[31m{str(v)}\033[34m\033[0m')
        title = f'\033[96m{self.__class__.__name__}{label}\033[0m'
        return f"\033[34m<\033[0m{title}({', '.join(args)})\033[34m>\033[0m"

    def __repr__(self):
        return str(self.to_obj())


