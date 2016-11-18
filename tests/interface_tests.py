from __future__ import (division, absolute_import, print_function,
    unicode_literals)
import unittest
import os
import time
from common import Webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (NoSuchElementException,
    TimeoutException)


def unique_str():
    return '{:.3f}'.format(time.time()).replace('.', 'd')


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

    def test_010_login(self):
        self.driver.log_in('admin', 'abc123')
        self.assertEqual(self.driver.title, 'Dashboard')

    def test_020_add_new_device(self):
        TestIcsw.device = 'device' + unique_str()
        self._add_device(TestIcsw.device)
        self.assert_toast('created new device')

    def test_021_duplicate_device(self):
        self._add_device(TestIcsw.device)
        self.assert_toast('already exists')

    def test_022_select_device(self):
        self.driver.select_device(self.device)

    def test_030_device_information(self):
        self.driver.get_('/main/deviceinfo')
        self.assert_element('//div[label[contains(.,"FQDN")]]'
            '/div[contains(., "{}")]'.format(TestIcsw.device))

    def test_040_device_tree(self):
        self.driver.get_('/main/devtree')
        self.driver.wait_overlay()
        device_button = self.driver.find_element_by_xpath(
            '//button[contains(., "{}")]'.format(TestIcsw.device)
            )
        self.driver.wait_overlay()

        # modify device
        device_button.click()
        modal = self.get_modal()
        self.click_button(ng_click='modify()', base_element=modal)
        modal = self.get_modal()
        self.fill_form({'comment': 'test'}, modal)
        time.sleep(1)
        self.click_button('Modify', base_element=modal)
        self.assert_toast('comment : changed from')

        # create device
        self.driver.get_('/main/devtree')
        # wait to be loaded
        self.driver.find_element_by_xpath('//th[text()="Name"]')
        self.driver.wait_overlay()
        self.click_button(ng_click='create_device( $event)')
        device_name = 'device' + unique_str()
        self.fill_form({'name': device_name})
        self.click_button('Create')
        self.assert_toast("created 'device'")

    def test_050_assign_configuration(self):
        self.driver.get_('main/deviceconfig')
        # wait to be loaded
        self.driver.find_element_by_xpath('//th[text()="Type"]')
        # get all available configurations
        configs = [
            e.text
            for e in self.driver.find_elements_by_xpath(
                '//thead/tr/th/div/span'
                )
            ]
        self.assertIn('check_ping', configs)
        self.assertIn('server', configs)
        # enable the "check_ping" configuration
        e = self.driver.find_element_by_xpath(
            '//tr[th[text()="{}"]]'
            '/td[@title="check_ping"]/span'.format(self.device)
            )
        e.click()
        self.click_button('Modify')
        self.assert_toast('added config check_ping')
        self.driver.wait_overlay()
        e.click()
        self.click_button('Modify')
        self.assert_toast('removed config check_ping')

    def test_060_network(self):
        def get_network_accordion(header):
            return self.driver.find_element_by_xpath(
                '//div[@uib-accordion-group and '
                './/span[contains(.,"{}")]]'.format(header))

        self.driver.get_('/main/network')

        # create a new net device
        accordion = get_network_accordion('Devices')
        row = accordion.find_element_by_xpath(
            ('.//tr[@icsw-device-network-device-row]'
                '/td[contains(.,"{}")]/..').format(self.device)
            )
        button = row.find_element_by_xpath('.//button[contains(., "create")]')
        button.click()
        button.find_element_by_xpath('..//a[text()="Netdevice"]').click()
        # fill in the form
        modal = self.get_modal()
        netdevice_name = 'netdevice' + unique_str()
        self.fill_form({'devname': netdevice_name}, modal)
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new netdevice')
        # For whatever reason the dialog doesn't close automatically, so close
        # it by pressing "Cancel".
        self.click_button('Cancel', base_element=modal)

        # create an IP address
        button.click()
        button.find_element_by_xpath('..//a[text()="IP Address"]').click()
        modal = self.get_modal()
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new net_ip')

    def test_070_categories(self):
        self.driver.get_('/main/categorytree')

        # create a new category
        self.driver.find_element_by_xpath(
            '//a[text()="Manage Categories"]').click()
        self.click_button('create')
        modal = self.get_modal()
        name = 'category' + unique_str()
        self.fill_form({'name': name}, modal)
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new category')

        # assign the category
        self.driver.find_element_by_xpath(
            '//a[text()="Category Assignment"]').click()
        time.sleep(2)
        checkbox = self.driver.find_element_by_xpath(
            '//span[span/span[text()="{}"]]/input'.format(name))
        checkbox.click()
        self.assert_toast('added to 1 device')

    def test_080_locations(self):
        # create a new location
        self.driver.get_('/main/devlocation')
        self.driver.find_element_by_xpath(
            '//li[@heading="Manage Locations"]'
            ).click()
        self.click_button('create')
        modal = self.get_modal()
        location_name = 'location' + unique_str()
        self.fill_form({'name': location_name}, modal)
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new category')

        # assign the location
        self.driver.find_element_by_xpath(
            '//li[@heading="Assign Locations"]'
            ).click()
        checkbox_xpath = '//span[contains(.,"{}")]/../input'.format(
            location_name
            )
        self.driver.find_element_by_xpath(checkbox_xpath).click()
        self.assert_toast('added to 1 device')
        # the checkbox has to be retrieved again as it has been recreated in
        # the DOM
        self.driver.wait_overlay()
        self.driver.find_element_by_xpath(checkbox_xpath).click()
        self.assert_toast('removed from 1 device')

        # TODO: modify and delete

    def test_090_domain_names(self):
        # create a new domain
        self.driver.get_('/main/domaintree')
        self.click_button('create new')
        modal = self.get_modal()
        domain_name = 'domain' + unique_str()
        self.fill_form({'name': domain_name}, modal)
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new domain_tree_node')

    def test_100_setup_progress(self):
        self.driver.get_('/main/setup/progress')
        self.assert_element(
            '//td[contains(text(), "Add at least one Device to the system")]'
            )

    def test_110_monitoring_overview(self):
        self.driver.get_('/main/monitorov')

        self.assert_element(
            '//td[text()="{}"]'.format(TestIcsw.device)
            )

    def test_120_license_overview(self):
        self.driver.get_('/main/syslicenseoverview')

        self.assert_element(
            '//span[contains(.,"Your Licenses for this Server")]'
            )

    def test_130_user_tree(self):
        self.driver.get_('/main/usertree')
        self.assert_element(
            '//h3[contains(.,"User / Groups / Roles")]'
            )
        # create a user
        button = self.driver.find_element_by_xpath(
            '//button[contains(.,"Create")]'
            )
        button.click()
        button.find_element_by_xpath(
            './..//a[contains(.,"Group")]'
            ).click()
        group_name = 'group' + unique_str()
        edit = self.driver.find_element_by_xpath(
            '//icsw-group-edit'
            )
        self.fill_form({'groupname': group_name}, edit, 'object')
        self.click_button('create')
        self.driver.wait_overlay()
        self.assert_toast('created new group')

    def test_140_account_info(self):
        self.driver.get_('/main/useraccount')
        self.assert_element(
            '//h3[text()="Account Information for \'admin\'"]'
            )
        form = self.driver.find_element_by_xpath('//form')
        first_name = 'firstname' + unique_str()
        self.fill_form({'first_name': first_name}, form, 'struct.user')
        self.click_button('submit')
        self.driver.wait_overlay()
        self.assert_toast('first name : changed from')

    def get_modal(self):
        # note the "s" in elements: find_element_by_xpath does not work
        # because Selenium always returns the first element, even with "last()"
        modals = self.driver.find_elements_by_xpath(
            '//div[@class="modal-content"]'
            )
        self.assert_(modals, 'Modal dialog could not be found.')
        return modals[-1]

    def click_button(self, text=None, ng_click=None, base_element=None):
        if not base_element:
            base_element = self.driver
        if text:
            base_element.find_element_by_xpath(
                './/button[contains(.,"{}")]'.format(text)
                ).click()
        else:
            base_element.find_element_by_xpath(
                '(.//button|.//icsw-tools-button)[@ng-click="{}"]'.format(
                    ng_click)
                ).click()

    def fill_form(self, values, base_element=None, edit_object='edit_obj'):
        if not base_element:
            base_element = self.driver
        for (key, value) in values.items():
            e = base_element.find_element_by_xpath(
                './/input[@ng-model="{}.{}"]'.format(edit_object, key)
                )
            e.clear()
            e.send_keys(value)

    def _add_device(self, name):
        self.driver.get_('/main/devicecreate')
        self.fill_form(
            {'full_name': name, 'ip': '192.168.0.1'},
            edit_object='device_data',
            )
        self.driver.wait_overlay()
        self.click_button('create Device')

    def assert_toast(self, text, msg=None):
        try:
            toast = self.driver.find_toast(text)
            toast.element.click()
        except TimeoutException:
            msg = self._formatMessage(
                msg,
                'Toast text "{}" not found.'.format(text)
                )
            raise self.failureException(msg)

    def assert_element(self, xpath, root=None, msg=None):
        if root is None:
            root = self.driver
        try:
            root.find_element_by_xpath(xpath)
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
    unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
