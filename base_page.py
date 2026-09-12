from driver_manager import DriverManager


class BasePage:
    def __init__(self):
        self.driver = DriverManager.get_driver()

    def restart(self):
        """Kill the crashed driver and attach a fresh one. Caller must
        re-login after this (the new session has no cookies)."""
        self.driver = DriverManager.restart_driver()
        return self.driver

    def open_url(self, url):
        self.driver.get(url)

    def find_element(self, locator):
        return self.driver.find_element(*locator)
