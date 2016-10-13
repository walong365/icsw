import subprocess
import time
import paramiko
import socket
import sys
import argparse

RESET_PASSWORD_COMMANDS = "from initat.cluster.backbone.models import user;" \
                          "u = user.objects.get(login='admin');u.password = 'abc123';u.save()"

def install_icsw_base_system(host, username, password):
    # try to connect via ssh
    sys.stdout.write("Trying to connect via ssh ... ")
    sys.stdout.flush()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    while True:
        try:
            ssh.connect(host, username=username, password=password)
            sys.stdout.write("done\n")
            sys.stdout.flush()
            break
        except socket.error as e:
            if e.errno != 111:
                raise e
            else:
                time.sleep(1)

    # install icsw-server icsw-client nginx-init
    cmd = "zypper ref && zypper --non-interactive in icsw-server icsw-client nginx-init"
    sys.stdout.write("Installing latest icsw-server and icsw-client ... ")
    sys.stdout.flush()
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)

    ssh_stdout.readlines()
    sys.stdout.write("done\n")
    sys.stdout.flush()

    # perform icsw setup
    sys.stdout.write("Perfoming icsw setup ... ")
    sys.stdout.flush()

    cmd = "/opt/cluster/sbin/icsw setup --ignore-existing --engine psql --port 5432"
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    ssh_stdout.readlines()
    sys.stdout.write("done\n")
    sys.stdout.flush()

    # reset admin login password
    sys.stdout.write("Resetting admin password ... ")
    sys.stdout.flush()

    cmd = '/opt/cluster/sbin/clustermanage.py shell -c "{}"'.format(RESET_PASSWORD_COMMANDS)
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    output = ssh_stdout.readlines()

    sys.stdout.write("done\n")
    sys.stdout.flush()

    # enable important services
    cmd = "/opt/cluster/sbin/icsw state enable uwsgi-init"
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    ssh_stdout.readlines()

    cmd = "/opt/cluster/sbin/icsw state enable nginx"
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    ssh_stdout.readlines()

    # restart icsw services
    sys.stdout.write("Restarting icsw services ... ")
    sys.stdout.flush()

    cmd = "/opt/cluster/sbin/icsw service restart"
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
    ssh_stdout.readlines()
    sys.stdout.write("done\n")
    sys.stdout.flush()


def reset_test_server(user, password, server_id, snapshot_id):
    base_params = [
        "curl",
        "-s",
        "-k",
        "-u", "{}:{}".format(user, password),
        "-H", "Content-type: application/xml",
    ]

    sys.stdout.write("Powering off test system ... ")
    sys.stdout.flush()

    # 1. poweroff test system
    uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms/{}/stop".format(server_id)
    args = [param for param in base_params]
    args.append("-d")
    args.append("<action/>")
    args.append("-X")
    args.append("POST")
    args.append(uri)

    output = subprocess.check_output(args)

    # 2. check status / poll until server is down
    uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms/{}".format(server_id)
    args = [param for param in base_params]
    args.append("-X")
    args.append("GET")
    args.append(uri)

    output = subprocess.check_output(args)
    while "<status>down</status>" not in output:
        time.sleep(5)
        output = subprocess.check_output(args)

    sys.stdout.write("done\n")
    sys.stdout.flush()

    # 3. restore snapshot
    sys.stdout.write("Restoring snapshot ... ")
    sys.stdout.flush()

    uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms/{}/snapshots/{}/restore".format(server_id, snapshot_id)
    args = [param for param in base_params]
    args.append("-d")
    args.append("<action/>")
    args.append("-X")
    args.append("POST")
    args.append(uri)

    subprocess.check_output(args)

    # 4. check status / poll until server is down (--> implies image not locked)
    uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms/{}".format(server_id)
    args = [param for param in base_params]
    args.append("-X")
    args.append("GET")
    args.append(uri)

    output = subprocess.check_output(args)
    while "<status>down</status>" not in output:
        time.sleep(5)
        output = subprocess.check_output(args)

    sys.stdout.write("done\n")
    sys.stdout.flush()

    # 5. bring machine up
    sys.stdout.write("Powering up test system ... ")
    sys.stdout.flush()

    uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms/{}/start".format(server_id)
    args = [param for param in base_params]
    args.append("-d")
    args.append("<action/>")
    args.append("-X")
    args.append("POST")
    args.append(uri)

    subprocess.check_output(args)

    # 6. check status / poll until server is down
    uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms/{}".format(server_id)
    args = [param for param in base_params]
    args.append("-X")
    args.append("GET")
    args.append(uri)

    output = subprocess.check_output(args)
    while "<status>up</status>" not in output:
        time.sleep(5)
        output = subprocess.check_output(args)

    sys.stdout.write("done\n")
    sys.stdout.flush()


def basic_availability_test(host):
    sys.stdout.write("Checking availability of icsw interface ... ")
    sys.stdout.flush()

    time.sleep(60)

    output = subprocess.check_output(["curl", "-s", "http://{}/icsw/api/v2/user/GetInitProduct".format(host)])

    if "Corvus splendens" in output and "CORVUS" in output:
        sys.stdout.write("done\n")
        sys.stdout.flush()
    else:
        sys.stdout.write("error\n")
        sys.stdout.flush()

        sys.stdout.write(output)
        sys.stdout.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='icsw installation tests')

    parser.add_argument('--test-system-id', nargs=1, action='store', dest='test_system_id',
        help='OVIrt ID of the test system', required=True)

    parser.add_argument('--snapshot-id', nargs=1, action='store', dest='snapshot_id',
        help='ID of the snapshot', required=True)

    parser.add_argument('--test-system-ip', nargs=1, action='store', dest='test_system_ip',
        help='IP of the test system', required=True)

    parser.add_argument('--ovirt-user', nargs=1, action='store', dest='ovirt_user',
        help='OVIrt username', required=True)

    parser.add_argument('--ovirt-pass', nargs=1, action='store', dest='ovirt_pass',
        help='OVIrt password', required=True)

    parser.add_argument('--test-system-user', nargs=1, action='store', dest='test_system_user',
        help='Test system username', required=True)

    parser.add_argument('--test-system-pass', nargs=1, action='store', dest='test_system_pass',
        help='Test system password', required=True)


    args = parser.parse_args()

    reset_test_server(args.ovirt_user[0], args.ovirt_pass[0], args.test_system_id[0], args.snapshot_id[0])

    install_icsw_base_system(args.test_system_ip[0], args.test_system_user[0], args.test_system_pass[0])

    basic_availability_test(args.test_system_ip[0])