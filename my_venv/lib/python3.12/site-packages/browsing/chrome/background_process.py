from pathlib import Path
from selenium.webdriver.chrome.options import Options


class BackgroundProcess:
    def __init__(
            self,
            headless: bool = True,
            gpu_disabled: bool = True,
            extensions_disabled: bool = True,
            sandbox_disabled: bool = True,
            dev_shm_usage_disabled: bool = True,
    ):
        """
        :param headless: The x-coordinate where the window is placed
        :param gpu_disabled: The y-coordinate where the window is placed
        :param extensions_disabled: The length of width in pixels
        :param sandbox_disabled: The length of width in pixels
        :param dev_shm_usage_disabled: The length of width in pixels
        """
        self.headless = headless
        self.gpu_disabled = gpu_disabled
        self.extensions_disabled = extensions_disabled
        self.sandbox_disabled = sandbox_disabled
        self.dev_shm_usage_disabled = dev_shm_usage_disabled

    def add_to_browser(self, options: Options):
        options.add_argument('--disable-extensions')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

    def __repr__(self):
        args = ', '.join([f"{k}={repr(v)}" for k,v in self.__dict__.items()])
        return f"<BackgroundProcess({args})"