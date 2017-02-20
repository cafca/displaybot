# coding: utf-8

"""Router control."""

import re
import logging
from selenium import webdriver


class RouterController:
    """Control FritzBox router through its web interface."""

    SID_REGEX = "(?<=sid=)[\w]*"

    def __init__(self, url, password_fname):
        """Setup controller with router password."""
        self.logger = logging.getLogger('oxo')
        self.logger.info("Setting up router controller...")
        self.url = url
        self.password_fname = password_fname

        self.driver = webdriver.PhantomJS()
        self.sid = self._login()

    def _get_password(self):
        try:
            with open(self.password_fname) as f:
                pw = f.read().strip()
        except IOError:
            self.logger.error("No password file found at '{}'. Please create \
                a file containing the router password.".format(self.password_fname))
            pw = None
        return pw

    def _login(self):
        self.driver.get("{}/login.lua".format(self.url))

        self.logger.debug("Logging in to FritzBox...")
        pwinput = self.driver.find_element_by_css_selector("#uiPass")
        pwinput.send_keys(self._get_password())
        pwinput.submit()

        # Extract session id from redirected path
        match = re.search(self.SID_REGEX, self.driver.current_url)
        if match:
            return match.group(0)
        else:
            self.logger.error("Router login failed.")
            return None

    def reboot(self):
        """Tell router to reboot."""
        if self.sid is None:
            self.logger.error("Not logged in.")
            return

        self.logger.debug("Load reboot page...")
        self.driver.get(
            "{}/system/reboot.lua?sid={}".format(self.url, self.sid))
        reboot = self.driver.find_element_by_name('reboot')
        self.logger.warning("Router is restarting now.")
        reboot.click()

if __name__ == '__main__':
    router = RouterController("http://192.168.188.1", "~/.displayBot/ROUTER_LOGIN")
    router.reboot()
