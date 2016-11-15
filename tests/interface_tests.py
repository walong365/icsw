import unittest
import os
import base64
import time
from StringIO import StringIO
from common import Webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from PIL import Image


def unique_str():
    return str(time.time()).replace('.', 'd')


class TestIcsw(unittest.TestCase):
    # Ideally tests should be mutually independent, here however we use some
    # tests for logging-in and populating the database and some class variables
    # "global" to all tests.
    device = None

    @classmethod
    def setUpClass(cls):
        cls.driver = Webdriver(
            base_url='http://192.168.1.92/icsw/main.html#',
            command_executor='http://127.0.0.1:4444/wd/hub',
            desired_capabilities=DesiredCapabilities.CHROME,
            )
        cls.driver.maximize_window()

    def test_001_login(self):
        self.driver.log_in('admin', 'abc123')
        self.assertEqual(self.driver.title, 'Dashboard')

    def test_002_add_new_device(self):
        TestIcsw.device = 'device' + unique_str()
        self._add_device(TestIcsw.device)
        self._check_toaster('created new device')
        self.driver.clear_toaster_messages()
        self.driver.select_device(TestIcsw.device)

    def test_003_duplicate_device(self):
        self._add_device(TestIcsw.device)
        self._check_toaster('already exists')
        self.driver.clear_toaster_messages()

    def test_004_device_information(self):
        self.driver.get_('/main/deviceinfo')
        self.assert_element('//div[label[contains(.,"FQDN")]]'
            '/div[contains(., "{}")]'.format(TestIcsw.device))

    def test_005_device_tree(self):
        self.driver.get_('/main/devtree')
        self.assert_element(
            '//button[contains(., "{}")]'.format(TestIcsw.device)
            )

    def test_006_device_tree_create_device(self):
        self.driver.get_('/main/devtree')
        # wait to be loaded
        self.driver.find_element_by_xpath('//th[text()="Name"]')
        self.driver.wait_loading()
        self.driver.find_element_by_xpath(
            '//button[@ng-click="create_device( $event)"]').click()
        name = 'device' + unique_str()
        e = self.driver.find_element_by_xpath(
            '//input[@ng-model="edit_obj.name"]'
            )
        e.clear()
        e.send_keys(name)
        self.driver.find_element_by_xpath(
            '//button[contains(.,"Create")]'
            ).click()
        self._check_toaster("created 'device'")

    def _add_device(self, name):
        self.driver.get_('/main/devicecreate')
        self.driver.find_element_by_name('full_name').send_keys(name)
        ActionChains(self.driver).send_keys(Keys.TAB).perform()
        self.driver.find_element_by_name('ip').send_keys('192.168.0.1')
        self.driver.wait_loading()
        self.driver.find_element_by_xpath(
            '//icsw-tools-button[@value="create Device"]').click()

    def _check_toaster(self, message):
        self.driver.find_element_by_xpath('//div[@ng-class="toaster.type"]'
            '/div[@ng-class="config.message"]'
            '/div[contains(.,"{}")]'.format(message))

    def assert_element(self, xpath, msg=None):
        try:
            self.driver.find_element_by_xpath(xpath)
        except NoSuchElementException:
            msg = self._formatMessage(
                msg,
                'Element "{}" not found.'.format(xpath)
                )
            raise self.failureException(msg)

    def debug_state(self, name=None):
        file_name = 'debug{}'.format('_' + name if name else '')
        path = '/usr/local/share/home/huymajer/development/icsw/'
        self.driver.save_screenshot(os.path.join(path, file_name + '.png'))
        with open(os.path.join(path, file_name + '.html'), 'wb') as file_:
            file_.write(self.driver.page_source.encode('utf-8'))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIcsw)
    unittest.TextTestRunner(verbosity=2).run(suite)
