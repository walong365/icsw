from StringIO import StringIO
import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from lxml.html import soupparser
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


class Toast(object):
    def __init__(self, element, title, text):
        self.element = element
        self.title = title
        self.text = text

    def matches(self, text):
        if text in self.title or text in self.text:
            return True
        return False


class Webdriver(webdriver.Remote):
    XPATH_TOAST_CONTAINER = '//div[@id="toast-container"]/div'

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

    def find_toast(self, text):
        def find_toast_(driver):
            for toast in driver.get_toasts():
                if toast.matches(text):
                    return toast

        return WebDriverWait(self, self.timeout).until(find_toast_)

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

    def get_toasts(self):
        elements = self.find_elements_by_xpath(self.XPATH_TOAST_CONTAINER)
        res = []
        for element in elements:
            tree = soupparser.fromstring(element.get_attribute('outerHTML'))
            title = tree.xpath(
                './div/div[@ng-class="config.title"]/text()'
                )
            title = title[0] if title else ''
            text = tree.xpath(
                './div/div[@ng-class="config.message"]/div/text()'
                )
            text = text[0] if text else ''
            res.append(Toast(element, title, text))
        return res

    def clear_toaster(self, no_wait=True):
        # it seems that find_elements_by_xpath entails some waiting even with
        # .implicitly_wait(0), so look if we have a toaster element by
        # inspecting the HTML with lxml
        if no_wait:
            tree = soupparser.fromstring(self.page_source)
            toasts = tree.xpath(self.XPATH_TOAST_CONTAINER)
        if not no_wait or toasts:
            for toaster in self.get_toasts():
                try:
                    toaster.element.click()
                except StaleElementReferenceException:
                    # the element has vanished in the meantime
                    pass
