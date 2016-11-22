import time
import argparse
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from common import Webdriver, visible


def main(args):
    d = Webdriver(
        base_url='http://192.168.1.75/icsw/main.html#',
        command_executor='http://127.0.0.1:4444/wd/hub',
        desired_capabilities=DesiredCapabilities.CHROME,
        )
    d.screenshot_dir = args.outdir
    d.maximize_window()

    d.log_in('admin', 'abc123')

    # select the theme according to the CSS property "color"
    body = d.find_element_by_xpath('/html/body')
    while body.value_of_css_property('color') != 'rgba(85, 85, 85, 1)':
        ActionChains(d).send_keys(Keys.F2).perform()
        time.sleep(1)
    time.sleep(6)

    # open the device selection dialog
    visible(
        d.find_elements_by_xpath(
            '//span[@ng-click="device_selection($event)"]'
            )
        ).click()
    # wait to be loaded
    d.find_element_by_xpath('//span[text()="server_group"]')
    d.save_shot('device_selection', '//div[@class="modal-content"]')
    d.find_element_by_xpath('//button[@class="close"]').click()

    # only select the server device and group
    d.select_device('server|centos7-test')

    # device tree
    d.get_('/main/devtree')
    d.find_element_by_xpath('//thead/tr/th[text()="Name"]')
    d.save_shot('device_tree', '//table[@st-table="entries_displayed"]/..')

    # configuration assignment
    d.get_('/main/deviceconfig')
    # wait to be loaded
    d.find_element_by_xpath('//thead/tr/th[text()="Type"]')
    d.save_shot(
        'assign_server_config',
        '//div[starts-with(@id, "accordiongroup-")]/..',
        )

    # network setup
    d.get_('/main/network')
    # wait to be loaded
    d.find_element_by_xpath('//tbody/tr/td[text()="centos7-test"]')
    # un-collapse "IP Addresses"
    d.find_element_by_xpath(
        '//a/span/span[contains(., "IP Addresses")]/preceding::i[1]'
        ).click()
    d.save_shot('network_configuration', '//div[@class="tab-content"]')

    # create device dialog
    d.get_('/main/devicecreate')
    d.find_element_by_name('full_name').send_keys('bahlon')
    ActionChains(d).send_keys(Keys.TAB).perform()
    d.save_shot('create_device', '//div[@heading="Base Data"]')

    # only select the client device
    d.select_device('client-test')

    # monitoring checks
    d.get_('/main/devicemonconfig')
    # select config
    d.find_element_by_xpath('//td[@title=" (check_ping)"]').click()
    # wait for the check-mark
    d.find_element_by_xpath(
        '//td[@title=" (check_ping)" and contains(@class, "success")]'
        )
    d.save_shot('assign_monitoring_checks', '//div[@class="panel-body"]')

    # client peering
    d.get_('/main/network')
    # wait to be loaded
    d.find_element_by_xpath('//tbody/tr/td[text()="centos7-test"]')
    # un-collapse "Peer Connections"
    e = d.find_element_by_xpath(
        '//a/span/span[contains(., "Peer Connections")]/preceding::i[1]'
        )
    e.click()
    d.save_shot('peering', element=e.find_element_by_xpath('../../../../..'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Make screenshots of the CORVUS web-frontend.'
        )
    parser.add_argument(
        'outdir',
        help='the directory the screenshots should be written to'
        )
    parser.add_argument(
        '--executor',
        help='the URL of the Selenium server'
        )
    parser.add_argument(
        '--base',
        default='',
        help='the base URL of the web-frontend'
        )
    args = parser.parse_args()
    main(args)
