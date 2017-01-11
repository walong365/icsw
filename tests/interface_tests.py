from __future__ import (division, absolute_import, print_function,
    unicode_literals)
import sys
import unittest
import os
import time
from common import Webdriver
from lxml.html import soupparser
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

    noctua_ip = None

    @classmethod
    def setUpClass(cls):
        cls.driver = Webdriver(
            base_url='http://{}/icsw/main.html'.format(TestIcsw.noctua_ip),
            command_executor='http://127.0.0.1:4444/wd/hub',
            desired_capabilities=DesiredCapabilities.CHROME,
            timeout=30
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
        time.sleep(1)
        modal = self.get_modal()
        time.sleep(1)
        self.click_button(ng_click='modify($event)', base_element=modal)
        modal = self.get_modal()
        self.fill_form({'comment': 'test' + unique_str()}, modal)
        time.sleep(1)
        self.click_button('Modify', base_element=modal)
        self.assert_toast('comment : changed from')

        # create device
        self.driver.get_('/main/devtree')
        # wait to be loaded
        self.driver.find_element_by_xpath('//th[text()="Name"]')
        self.driver.wait_overlay()
        self.click_button(ng_click='create_device( $event)')
        modal = self.get_modal()
        device_name = 'device' + unique_str()
        self.fill_form({'name': device_name})
        self.click_button('Create')
        self.assert_toast("created 'device'")
        self.driver.wait_staleness_of(modal)

        # deleting devices doesn't work

        # create a device group
        device_group_name = 'devicegroup' + unique_str()
        self.click_button('create Device Group')
        modal = self.get_modal()
        self.fill_form({'name': device_group_name})
        self.click_button('Create')
        self.click_button('Cancel')
        self.driver.wait_staleness_of(modal)
        self.assert_toast('created new device_group')

        # modify device group
        self.driver.refresh()
        row_xpath = '//td/strong[contains(., "{}")]/../..'.format(
            device_group_name
            )
        row = self.driver.find_element_by_xpath(row_xpath)
        self.click_button('modify', base_element=row)
        modal = self.get_modal()
        self.fill_form({'description': 'new' + unique_str()})
        self.click_button('Modify')
        self.driver.wait_staleness_of(modal)
        self.assert_toast('description : changed from')

        # delete the device group
        row = self.driver.find_element_by_xpath(row_xpath)
        self.click_button('delete', base_element=row)
        modal = self.get_modal()
        self.click_button('delete', base_element=modal)
        self.assert_toast('Deleting 1 object')
        self.assert_toast('Finished deleting 1 object')

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

        # create an IP address
        button.click()
        button.find_element_by_xpath('..//a[text()="IP Address"]').click()
        modal = self.get_modal()
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new net_ip')

        # TODO: create peering

    def test_064_variables(self):
        self.driver.get_('/main/variables')
        # wait to be loaded
        self.driver.find_element_by_xpath(
            '//th[text()="Info"]'
        )

        # create a new variable
        self.click_button('create')
        variable_name = 'variable' + unique_str()
        modal = self.get_modal()
        self.fill_form(
            {'name': variable_name, 'val_str': 'test value'},
            modal
            )
        self.click_button('Create', base_element=modal)
        self.driver.wait_staleness_of(modal)

        # modify variable
        self.click_button(ng_click='config_service.toggle_expand(obj)')
        self.click_button('modify')
        modal = self.get_modal()
        self.fill_form({'val_str': 'new value'}, modal)
        self.click_button('Modify')
        self.assert_toast('val str : changed ')

        # delete variable
        self.click_button('delete')
        self.click_button('Yes')

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
        self.driver.wait_staleness_of(modal)
        self.assert_toast('created new category')

        # assign the category
        self.driver.find_element_by_xpath(
            '//a[text()="Category Assignment"]').click()
        checkbox = self.driver.find_element_by_xpath(
            '//span[span/span[text()="{}"]]/input'.format(name))
        checkbox.click()
        self.click_button("modify")
        self.assert_toast('added to 1 device')

    def test_080_locations(self):
        manage_locations_xpath = '//li[@heading="Configure Locations"]'

        # create a new location
        self.driver.get_('/main/devlocation')
        self.driver.find_element_by_xpath(manage_locations_xpath).click()
        self.click_button('create')
        modal = self.get_modal()
        location_name = 'location' + unique_str()
        self.fill_form({'name': location_name}, modal)
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new category')
        self.driver.wait_staleness_of(modal)

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

        self.driver.wait_overlay()
        self.driver.find_element_by_xpath(manage_locations_xpath).click()
        table_row = self.driver.find_element_by_xpath(
            '//td[contains(.,"{}")]/..'.format(location_name)
            )

        # modify the location
        self.click_button('modify', base_element=table_row)
        modal = self.get_modal()
        self.fill_form({'comment': 'new comment'}, modal)
        self.click_button('Modify', base_element=modal)
        self.assert_toast('comment : changed from')

        # delete the location
        self.click_button('delete', base_element=table_row)
        self.click_button('Yes')
        self.driver.refresh()
        self.assert_(location_name not in self.driver.page_source)

    def test_090_domain_names(self):
        # create a new domain
        self.driver.get_('/main/domaintree')
        self.click_button('create new')
        modal = self.get_modal()
        domain_name = 'domain' + unique_str()
        self.fill_form({'name': domain_name}, modal)
        self.click_button('Create', base_element=modal)
        self.assert_toast('created new domain_tree_node')

    # def test_100_setup_progress(self):
    #     row_xpath = '//td[contains(text(), "Add at least one user")]/..'
    #
    #     self.driver.get_('/main/setup/progress')
    #     row = self.driver.find_element_by_xpath(row_xpath)
    #     self.click_button('Ignore Issue', base_element=row)
    #
    #     time.sleep(5)
    #     self.driver.refresh()
    #     row = self.driver.find_element_by_xpath(row_xpath)
    #     self.click_button('Unignore Issue', base_element=row)
    #
    #     time.sleep(5)
    #     self.driver.refresh()
    #     row = self.driver.find_element_by_xpath(row_xpath)
    #     self.assert_element(
    #         '//button[contains(.,"Ignore Issue")]',
    #         root=row
    #         )

    def test_110_monitoring_overview(self):
        self.driver.get_('/main/monitorov')

        self.assert_element(
            '//td[normalize-space(text())="{}"]'.format(TestIcsw.device)
            )

    def test_120_monitoring_setup(self):
        def select_tab(level_1, level_2):
            time.sleep(1)
            self.driver.find_element_by_xpath(
                '//uib-tab-heading[contains(., "{}")]'.format(level_1)
                ).click()
            time.sleep(1)
            self.driver.find_element_by_xpath(
                '//div[@class="tab-content"]'
                '//li/a[contains(text(), "{}")]'.format(level_2)
                ).click()

        def get_rest_table(service):
            return self.driver.find_element_by_xpath(
                '//icsw-tools-rest-table-new[@config-service="{}"]'.format(
                    service
                    )
                )

        def get_table_row(tab_content, column_header, search_value):
            """Returns the row that has ``search_value`` in the column
            ``column_header``."""
            table = tab_content.find_element_by_xpath(
                './/table[@st-table="entries_displayed"]'
                )
            tree = soupparser.fromstring(table.get_attribute('outerHTML'), features="html.parser")
            column_headers = tree.xpath('//thead/tr[2]/th/text()')

            row = table.find_element_by_xpath(
                '//tbody/tr/td[{} and text()="{}"]/..'.format(
                    column_headers.index(column_header) + 1,
                    search_value,
                    )
                )
            return row

        def test_monitoring_setup_(tabs, config_service, object_name,
                                   form_values, column, value):
            select_tab(*tabs)
            tab_content = get_rest_table(config_service)
            self.click_button('create new', base_element=tab_content)
            modal = self.get_modal()
            self.fill_form(form_values, modal)
            self.click_button('Create', base_element=modal)
            self.assert_toast('created new {}'.format(object_name))
            row = get_table_row(tab_content, column, value)
            self.click_button('delete', base_element=row)
            modal = self.get_modal()
            self.click_button('Yes', base_element=modal)

        name = unique_str()
        self.driver.get_('/main/monitorbasics')

        # service templates
        test_monitoring_setup_(
            ('Basic Setup', 'Service Templates'),
            'icswMonitoringBasicServiceTemplateService',
            'mon_service_templ',
            {'name': name},
            'Name',
            name,
            )

        # device templates
        test_monitoring_setup_(
            ('Basic Setup', 'Device Templates'),
            'icswMonitoringBasicDeviceTemplateService',
            'mon_device_templ',
            {'name': name},
            'Name',
            name,
            )

        # host check command
        test_monitoring_setup_(
            ('Basic Setup', 'Host Check Commands'),
            'icswMonitoringBasicHostCheckCommandService',
            'host_check_command',
            {'name': name, 'command_line': name},
            'Name',
            name,
            )

    def test_130_license_overview(self):
        self.driver.get_('/main/syslicenseoverview')

        self.assert_element(
            '//span[contains(.,"Your Licenses for this Server")]'
            )

    def test_140_user_tree(self):
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

    def test_150_account_info(self):
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
        time.sleep(2.5)
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
                '(.//input|.//textarea)[@ng-model="{}.{}"]'.format(
                    edit_object, key)
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

    def debug_state(self, name=None, element=None):
        file_name = 'debug{}'.format('_' + name if name else '')
        path = '/usr/local/share/home/huymajer/development/icsw/'
        self.driver.save_screenshot(os.path.join(path, file_name + '.png'))
        if element:
            source = element.get_attribute('outerHTML')
        else:
            source = self.driver.page_source
        with open(os.path.join(path, file_name + '.html'), 'wb') as file_:
            file_.write(source.encode('utf-8'))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Please provide ip of test system as first argument.")
    else:
        TestIcsw.noctua_ip = sys.argv[1]
        suite = unittest.TestLoader().loadTestsFromTestCase(TestIcsw)
        unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
