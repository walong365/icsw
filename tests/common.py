from StringIO import StringIO
import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from PIL import Image
import base64
import os


def find_any(elements):
    def find_any_(driver):
        for (key, xpath) in elements:
            # this doesn't raise an exception but returns an empty list instead
            res = driver.find_elements(By.XPATH, xpath)
            if res:
                return key
    return find_any_


def visible(elements):
    for element in elements:
        if element.is_displayed():
            return element


class Webdriver(webdriver.Remote):

    def __init__(self, base_url, timeout=10, *args, **kw_args):
        super(Webdriver, self).__init__(*args, **kw_args)
        self.shot_names = set()
        self.timeout = timeout
        self.base_url = base_url
        self.implicitly_wait(timeout)

        self.screenshot_dir = None

    def find_any(self, elements):
        """For a list of tuples of the form ``(key, xpath)``, find any element
        patching ``xpath`` and return the corresponding ``key``.
        """
        return WebDriverWait(self, self.timeout).until(
            find_any(elements))

    def get_(self, url):
        return self.get(self.base_url + url)

    def log_in(self, user, password):
        self.get(self.base_url)
        time.sleep(2)
        self.find_element_by_name('username').send_keys(user)
        self.find_element_by_name('password').send_keys(password)
        self.find_element_by_name('button').click()
        self.wait_loading()
        # confirm the warning about a concurrent login
        xpath_logged_in = '//a[@href="#/main/dashboard"]'
        find_elements = [
            ('concurrent', '//div[@class="bootstrap-dialog-message" and '
                'starts-with(., "Another user is already using this '
                'account")]'),
            ('success', xpath_logged_in),
            ]
        key = self.find_any(find_elements)
        if key == 'concurrent':
            self.find_element_by_xpath('//button[contains(., "Yes")]').click()
            self.find_element_by_xpath(xpath_logged_in)  # wait to be loaded

    def save_shot(self, name, xpath=None, element=None):
        assert name not in self.shot_names
        self.shot_names.add(name)
        self.wait_loading()
        image = Image.open(
            StringIO(base64.decodestring(self.get_screenshot_as_base64()))
            )
        if xpath:
            element = self.find_element_by_xpath(xpath)
        x = int(element.location['x'])
        y = int(element.location['y'])
        width = int(element.size['width'])
        height = int(element.size['height'])
        image = image.crop((x, y, x + width, y + height))
        file_name = '{}.png'.format(name)
        print 'Saving "{}"'.format(file_name)
        with open(os.path.join(self.screenshot_dir, file_name), 'wb') as file_:
            image.save(file_, 'png', quality=90)

    def wait_loading(self):
        WebDriverWait(self, self.timeout).until(
            EC.invisibility_of_element_located((By.XPATH, '/html/body/div[1]'))
            )

    def select_device(self, expression):
        self.wait_loading()
        visible(
            self.find_elements_by_xpath(
                '//span[@ng-click="device_selection($event)"]'
                )
            ).click()
        # wait to be loaded
        self.find_element_by_xpath('//span[text()="server_group"]')
        e = self.find_element_by_xpath(
            '//input[@placeholder="search by name, IP or MAC"]'
            )
        e.send_keys(expression)
        time.sleep(3)
        self.find_element_by_xpath('//button[@class="close"]').click()

    def clear_toaster_messages(self):
        xpath = '//div[@id="toast-container"]/div[@ng-class="toaster.type"]'
        for element in self.find_elements(By.XPATH, xpath):
            element.click()
