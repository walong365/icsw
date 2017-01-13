#!/usr/bin/python3.4 -Ot

import datetime
import subprocess
import time
import paramiko
import socket
import sys
import argparse

import check_for_new_packages

try:
    import configparser
except ImportError:
    import configparser as ConfigParser

from common import Webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

try:
    from lxml import etree
except ImportError:
    try:
        import xml.etree.cElementTree as etree
    except ImportError:
        try:
            import xml.etree.ElementTree as etree
        except ImportError:
            try:
                import cElementTree as etree
            except ImportError:
                import elementtree.ElementTree as etree


RESET_PW_SCRIPT = "from initat.cluster.backbone.models import user;" \
                  "u = user.objects.get(login='admin');u.password = 'abc123';u.save()"


def install_icsw_base_system(host, username, password, package_manager, machine_name):
    package_dict = check_for_new_packages.check_for_new_packages()
    icsw_version, _ = package_dict[machine_name]

    # try to connect via ssh
    sys.stdout.write("Trying to connect via ssh ... ")
    sys.stdout.flush()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    retries = 60
    while retries:
        retries -= 1
        try:
            ssh.connect(host, username=username, password=password)
            sys.stdout.write("done\n")
            sys.stdout.flush()
            break
        except socket.error:
            time.sleep(1)

    setup_command = ""
    refresh_command = ""
    icsw_server_version_command = ""
    icsw_client_version_command = ""
    expected_icsw_server_string = ""
    expected_icsw_client_string = ""
    if package_manager == "zypper":
        refresh_command = "zypper --non-interactive --no-gpg-checks ref"
        icsw_server_version_command = "zypper info icsw-server"
        expected_icsw_server_string = "3.0-{}".format(icsw_version)
        icsw_client_version_command = "zypper info icsw-client"
        expected_icsw_client_string = "3.0-{}".format(icsw_version)
        setup_command = "zypper --non-interactive --no-gpg-checks in icsw-server icsw-client nginx-init"
    elif package_manager == "apt-get":
        refresh_command = "apt-get update"
        icsw_server_version_command = "apt-cache madison icsw-server"
        expected_icsw_server_string = "3.0-{}".format(icsw_version)
        icsw_client_version_command = "apt-cache madison icsw-client"
        expected_icsw_client_string = "3.0-{}".format(icsw_version)
        setup_command = "apt-get -y --force-yes install icsw-server icsw-client nginx-init"
    elif package_manager == "yum":
        refresh_command = "yum clean all"
        icsw_server_version_command = "yum info icsw-server"
        expected_icsw_server_string = "{}".format(icsw_version)
        icsw_client_version_command = "yum info icsw-client"
        expected_icsw_client_string = "{}".format(icsw_version)
        setup_command = "yum -t -y --nogpgcheck install icsw-server icsw-client nginx-init"

    commands = [
        ("Refreshing package manager ... ", refresh_command, None),
        ("Checking if icsw-server-3.0-{} is available ... ".format(icsw_version), icsw_server_version_command,
         expected_icsw_server_string),
        ("Checking if icsw-client-3.0-{} is available ... ".format(icsw_version), icsw_client_version_command,
         expected_icsw_client_string),
        ("Installing icsw-server and icsw-client ... ", setup_command, None),
        ("Performing icsw setup ... ", "/opt/cluster/sbin/icsw setup --ignore-existing --engine psql --port 5432",
         None),
        ("Resetting admin password ... ", '/opt/cluster/sbin/clustermanage.py shell -c "{}"'.format(RESET_PW_SCRIPT),
         None),
        ("Enabling uwsgi-init ... ", "/opt/cluster/sbin/icsw service enable uwsgi-init", None),
        ("Enabling nginx ... ", "/opt/cluster/sbin/icsw service enable nginx", None),
        ("Setting role to noctua  ... ", "/opt/cluster/sbin/icsw config role noctua", None),
        ("Restarting icsw services ... ",  "/opt/cluster/sbin/icsw service restart", None)
    ]

    with open("{}.log".format(machine_name), "ab", 0) as log_file:
        for status_msg, command, expected_string in commands:
            sys.stdout.write(status_msg)
            sys.stdout.flush()

            start_time = datetime.datetime.now()
            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
            log_file.write(str.encode("*** Command executed: {}\n".format(command)))

            expected_string_found = True
            if expected_string:
                expected_string_found = False

            while True:
                try:
                    output = next(ssh_stdout)
                    if expected_string and expected_string in output:
                        expected_string_found = True
                    log_file.write(str.encode(output))
                except StopIteration:
                    break

            if not expected_string_found:
                raise Exception("Expected string {} not found in output".format(expected_string))

            end_time = datetime.datetime.now()

            sys.stdout.write("done in ({})\n".format((end_time - start_time)))
            log_file.write(str.encode("*** Command ({}) execution took: {}\n".format(command, (end_time - start_time))))
            sys.stdout.flush()


def reset_test_server(user, password, server_id, snapshot_id, machine_name):
    base_uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms"
    base_params = [
        "curl",
        "-s",
        "-k",
        "-u", "{}:{}".format(user, password),
        "-H", "Content-type: application/xml",
    ]

    # command structure is ([print(Status Message)], [api-uri to perform action on], [GET/POST action_type],
    # [output to check for], [id to save (raw) output with (saved into output_dict)])
    commands = [
        ("Powering off test system ... ", "{}/{}/stop".format(base_uri, server_id), "POST", None, None),
        ("Waiting for system to power off ... ", "{}/{}".format(base_uri, server_id), "GET",
         "<status>down</status>", None),
        ("Restoring snapshot ... ", "{}/{}/snapshots/{}/restore".format(base_uri, server_id, snapshot_id), "POST",
         None, None),
        ("Waiting for snapshot restore ... ", "{}/{}".format(base_uri, server_id), "GET", "<status>down</status>",
         None),
        ("Powering up test system ... ", "{}/{}/start".format(base_uri, server_id), "POST", None, None),
        ("Waiting for system to be up ... ", "{}/{}".format(base_uri, server_id), "GET", "<status>up</status>", None),
        ("Retreiving system ip ... ", "{}/{}/nics".format(base_uri, server_id), "GET",
         "<description>guest reported data</description>", "address")
    ]

    output_dict = {}

    with open("{}.log".format(machine_name), "ab", 0) as log_file:
        for status_msg, action_uri, method, check_output, output_save_identifier in commands:
            sys.stdout.write(status_msg)
            sys.stdout.flush()

            args = [param for param in base_params]
            if method == "POST":
                args.append("-d")
                args.append("<action/>")
            args.append("-X")
            args.append(method)
            args.append(action_uri)

            start_time = datetime.datetime.now()
            while True:
                output = subprocess.check_output(args)
                log_file.write(str.encode("*** Command executed: {}\n".format("".join(args))))
                log_file.write(output)

                if check_output:
                    if check_output in output.decode():
                        output_dict[output_save_identifier] = output
                        break
                    else:
                        time.sleep(5)
                else:
                    break

            end_time = datetime.datetime.now()

            log_file.write(str.encode("*** Command ({}) execution took: {}\n".format("".join(args),
                                                                                     (end_time - start_time))))
            sys.stdout.write("done (execution took {})\n".format((end_time - start_time)))
            sys.stdout.flush()

    return output_dict


def basic_availability_test(host, test_system_name):
    sys.stdout.write("Checking availability of icsw interface ... ")
    sys.stdout.flush()

    time.sleep(60)

    exception = None
    title = None
    for i in range(5):
        try:
            driver = Webdriver(
                base_url='http://{}'.format(host),
                command_executor='http://192.168.1.246:4444/wd/hub',
                desired_capabilities=DesiredCapabilities.CHROME,
            )
            driver.maximize_window()

            driver.log_in('admin', 'abc123', delay=60)
            title = driver.title
        except Exception as e:
            exception = e
        else:
            exception = None
            break

    if exception:
        raise exception

    if title and title == 'Dashboard':
        sys.stdout.write("done\n")
        sys.stdout.flush()
    else:
        sys.stdout.write("error\n")
        sys.stdout.flush()


def main():
    config = configparser.ConfigParser()
    config.read("installation_test.cfg")

    parser = argparse.ArgumentParser(description='icsw installation tests')

    parser.add_argument('--ovirt-user', nargs=1, action='store', dest='ovirt_user',
                        help='OVIrt username', required=True)

    parser.add_argument('--ovirt-pass', nargs=1, action='store', dest='ovirt_pass',
                        help='OVIrt password', required=True)

    machine_names_str = ", ".join([system_name for system_name in config.sections()])
    parser.add_argument('--test-machine', nargs=1, action='store', dest='test_machine',
                        help='One of the following: {}'.format(machine_names_str), required=True)

    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read("installation_test.cfg")

    test_system_name = args.test_machine[0]
    test_system_id = config.get(test_system_name, "id")
    snapshot_id = config.get(test_system_name, "snapshot_id")
    password = config.get(test_system_name, "password")
    package_manager = config.get(test_system_name, "package_manager")

    output_dict = reset_test_server(args.ovirt_user[0],
                                    args.ovirt_pass[0], test_system_id, snapshot_id, test_system_name)
    output_dict = parse_output_dict(output_dict)

    install_icsw_base_system(output_dict['ip'], "root", password, package_manager, test_system_name)
    basic_availability_test(output_dict['ip'], test_system_name)


def parse_output_dict(output_dict):
    new_output_dict = {}
    root = etree.fromstring(output_dict['address'])
    ip_elements = root.findall(".//ip")
    for ip_element in ip_elements:
        if ip_element.find("version").text == "v4":
            new_output_dict['ip'] = ip_element.find("address").text

    return new_output_dict

if __name__ == "__main__":
    main()
