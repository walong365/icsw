# Copyright (C) 2014 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" virtual desktop capability """

from django.db.models import Q
from django.utils import timezone
from initat.cluster.backbone.models import device
from initat.cluster_server.capabilities.base import bg_stuff
from initat.cluster_server.config import global_config
from initat.tools import process_tools
import psutil
import os
import shutil
import subprocess
import glob
import pwd
import datetime
import sys
import daemon
import multiprocessing
import socket
import random
import string
import tempfile
from initat.cluster.backbone.models import virtual_desktop_protocol, window_manager, virtual_desktop_user_setting


# utility classes for virtual desktop handling. They are located here but don't have any dependency here.
class virtual_desktop_server(object):
    uses_websockify = False

    def __init__(self, logger):
        # logger: callable
        self.logger = logger

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def log(self, msg):
        self.logger(msg)

    @classmethod
    def get_class_for_vdus(cls, vdus):
        proto = vdus.virtual_desktop_protocol.name
        if proto == "vnc":
            return vncserver
        else:
            raise Exception("Unknown virtual desktop protocol: {}".format(proto))

    @classmethod
    def get_instance_for_vdus(cls, vdus, log):
        '''
        @return virtual_desktop_server
        '''
        klass = cls.get_class_for_vdus(vdus)
        return klass(log, vdus)


class vncserver(virtual_desktop_server):
    uses_websockify = True

    PORT_RANGE = (16450, 16550)

    def __init__(self, logger, vdus):
        super(vncserver, self).__init__(logger)
        self.vdus = vdus

        self.user_home_dir = os.path.expanduser("~" + self.vdus.user.login)
        self.corvus_dir = "{}/.corvus".format(self.user_home_dir)
        self.vnc_home_dir = "{}/vncsession-{}".format(self.corvus_dir, self.vdus.pk)
        self.vnc_dir = "{}/.vnc".format(self.vnc_home_dir)
        self.pwd_file = "{}/passwd".format(self.vnc_dir)
        # we don't know the display number, but there can only be one:
        self.pid_file_pattern = "{}/{}*.pid".format(self.vnc_dir, socket.gethostname())
        self.websockify_pid_file = "{}/websockify.pid".format(self.vnc_dir)
        self.vncstartup_file = "{}/xstartup".format(self.vnc_dir)

    def _setup(self):
        # must be called once before first start and not do any harm if called multiple times
        vnc_user_uid = self.vdus.user.uid

        # set up files and directories needed for vncserver to start
        if not os.path.exists(self.corvus_dir):
            os.mkdir(self.corvus_dir)
            os.chown(self.corvus_dir, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))

        # fresh dir for every start
        if os.path.exists(self.vnc_home_dir):
            try:
                # might fail for broken mounts, device files, etc.
                shutil.rmtree(self.vnc_home_dir)
            except OSError:
                # try to move file
                self.log("Failed to remove dir {}, moving it".format(self.vnc_home_dir))
                dir_path = tempfile.mkdtemp(dir=self.corvus_dir, prefix="vncsession-{}-dead-".format(self.vdus.pk))
                shutil.move(self.vnc_home_dir, dir_path)

        os.mkdir(self.vnc_home_dir)
        os.chown(self.vnc_home_dir, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))

        os.mkdir(self.vnc_dir)
        os.chown(self.vnc_dir, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))
        os.chmod(self.vnc_dir, 0700)

        # create startup file
        with open(self.vncstartup_file, "w") as f:
            f.write("#!/bin/sh\n")
            f.write("export HOME=\"{}\"\n".format(self.user_home_dir))
            f.write(self.vdus.window_manager.binary + " &\n")

        # make startup file executable
        os.chown(self.vncstartup_file, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))
        os.chmod(self.vncstartup_file, 0700)

    def _write_password_file(self, pw):
        # get binary data using vncpasswd
        outfile = open(self.pwd_file, "w")
        vncpw_proc = subprocess.Popen(["vncpasswd", "-f"], stdin=subprocess.PIPE, stdout=outfile)
        vncpw_proc.stdin.write(pw)
        vncpw_proc.stdin.close()
        vncpw_proc.wait()
        outfile.close()

        os.chown(self.pwd_file, self.vdus.user.uid, self._get_gid_of_uid(self.vdus.user.uid))
        os.chmod(self.pwd_file, 0600)

    def start(self):
        self._setup()

        # create pw for session (vnc truncates passwords longer than 8 characters)
        self.vdus.password = "".join(random.choice(string.ascii_letters + string.digits) for _i in xrange(8))

        self._write_password_file(self.vdus.password)

        # calculate effective pw
        self.vdus.effective_port = self.vdus.port if self.vdus.port != 0 else random.randint(*self.PORT_RANGE)
        self.vdus.websockify_effective_port = self.vdus.websockify_port if self.vdus.websockify_port != 0 else self.vdus.effective_port + 1

        self.vdus.last_start_attempt = timezone.now()

        # no vdus change below this line
        self.vdus.save_without_signals()

        cmd_line = "vncserver"
        cmd_line += " -geometry {} ".format(self.vdus.screen_size)
        cmd_line += " -rfbport {}".format(self.vdus.effective_port)
        cmd_line += " -rfbauth {}".format(self.pwd_file)
        cmd_line += " -extension RANDR"  # this prevents the window manager from changing the resolution,c.f. https://bugzilla.redhat.com/show_bug.cgi?id=847442

        websockify_cmd_line = "/opt/python-init/bin/websockify {} localhost:{}".format(self.vdus.websockify_effective_port, self.vdus.effective_port)

        self.log("Starting vncserver with command line: {}".format(cmd_line))
        self.log("Starting websockify with command line: {}".format(websockify_cmd_line))

        vnc_env = os.environ.copy()
        vnc_env["HOME"] = self.vnc_home_dir
        vnc_env["XAUTHORITY"] = "{}/.Xauthority".format(self.vnc_home_dir)

        def preexec():
            os.setgid(self._get_gid_of_uid(self.vdus.user.uid))
            os.setuid(self.vdus.user.uid)

        if True or global_config["DEBUG"]:
            # TODO: writing to dev null causes the vncserver to not start
            proc_stdout, proc_stderr = None, None
        else:
            proc_stdout, proc_stderr = open(os.devnull, "w"), open(os.devnull, "w")

        def vnc_start_fun():
            # make sure not to interfere with db (db should actually be already closed at this point but be really sure)
            from django.db import connection
            connection.close()

            # turn process into daemon
            with daemon.DaemonContext(detach_process=True, stdout=sys.stdout, stderr=sys.stderr):
                # execute vnc start script in daemon (writes pid file automatically)
                subprocess.Popen(cmd_line.strip().split(), env=vnc_env, preexec_fn=preexec, stdout=proc_stdout, stderr=proc_stderr)

                # run websockify
                if websockify_cmd_line:
                    # websockify needs to write somewhere
                    sub = subprocess.Popen(websockify_cmd_line.strip().split(), env=vnc_env, preexec_fn=preexec, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # write pid file manually
                    with open(self.websockify_pid_file, "w") as f:
                        f.write(str(sub.pid))
                    sub.wait()  # terminate when child does

                # pids are read in _call below such that we don't have to wait now

        # make sure not to interfere with db
        from django.db import connection
        connection.close()

        proc = multiprocessing.Process(target=vnc_start_fun)
        proc.start()

    def stop(self):
        p = _get_running_process(self.vdus.pid, self.vdus.process_name)
        if p:
            self.log("Killing vnc process with pid {}".format(p.pid))
            p.kill()
        else:
            self.log("Stop called but vnc server process isn't running (any more)")

        websockify_proc = _get_running_process(self.vdus.websockify_pid, self.vdus.websockify_process_name)
        if websockify_proc:
            self.log("Killing websockify process with pid {}".format(websockify_proc.pid))
            websockify_proc.kill()
        else:
            self.log("Stop called but websockify process isn't running (any more)")

    def get_pid_from_file(self):
        try:
            pid_file = glob.glob(self.pid_file_pattern)[0]
            return int(open(pid_file, "r").read())
        except:
            return None

    def get_websockify_pid_from_file(self):
        try:
            return int(open(self.websockify_pid_file, "r").read())
        except:
            return None

    @staticmethod
    def _get_gid_of_uid(uid):
        return pwd.getpwuid(uid).pw_gid


class virtual_desktop_stuff(bg_stuff):
    class Meta:
        name = "virtual_desktop"

    def init_bg_stuff(self):
        self.__effective_device = device.objects.get(Q(pk=global_config["EFFECTIVE_DEVICE_IDX"]))
        self.__first_run = True

    def _call(self, cur_time, builder):
        # handle first run locally
        is_first_run = self.__first_run
        self.__first_run = False
        if is_first_run:
            # only check for services on first run
            for vd_proto in virtual_desktop_protocol.objects.all():
                _vd_update = False
                available = process_tools.find_file(vd_proto.binary)
                if vd_proto.devices.filter(pk=self.__effective_device.pk):
                    if not available:
                        _vd_update = True
                        vd_proto.devices.remove(self.__effective_device)
                        self.log("Removing virtual desktop proto {} from {}".format(vd_proto.name, self.__effective_device.name))
                else:
                    if available:
                        _vd_update = True
                        vd_proto.devices.add(self.__effective_device)
                        self.log("Adding virtual desktop proto {} to {}".format(vd_proto.name, self.__effective_device.name))

                if _vd_update:
                    vd_proto.save()

            for wm in window_manager.objects.all():
                _wm_update = False
                available = process_tools.find_file(wm.binary)
                if wm.devices.filter(pk=self.__effective_device.pk):
                    if not available:
                        _wm_update = True
                        wm.devices.remove(self.__effective_device)
                        self.log("Removing window manager {} from {}".format(wm.name, self.__effective_device.name))
                else:
                    if available:
                        _wm_update = True
                        wm.devices.add(self.__effective_device)
                        self.log("Adding window manager {} to {}".format(wm.name, self.__effective_device.name))

                if _wm_update:
                    wm.save()

        for vdus in virtual_desktop_user_setting.objects.filter(device=self.__effective_device, to_delete=False):
            self.check_vdus_running(vdus, ignore_last_start_attempt=is_first_run)

    def check_vdus_running(self, vdus, ignore_last_start_attempt=False):
        # check if services are running as desired

        try:
            klass = virtual_desktop_server.get_class_for_vdus(vdus)
        except Exception as e:
            self.log(e)
            return  # this is the only early return here

        self.log("checking virtual desktop servers")

        if vdus.is_running:
            # check if actually running and start in case
            if not _check_vdus_running(vdus, log=self.log):
                # we are in STARTING unless we find a functional setup below
                vdus.update_state(virtual_desktop_user_setting.State.STARTING)
                s = klass(self.log, vdus)

                do_start = True  # start unless last start attempt was very recently
                if (timezone.now() - vdus.last_start_attempt) < datetime.timedelta(minutes=5):
                    self.log("Last virtual desktop start attempt was earlier than 5 minutes")
                    do_start = False
                    # check if pid file has appeared and contains valid pid
                    pid = s.get_pid_from_file()
                    server_success = bool(pid) and _check_process_running(pid)
                    if server_success:
                        # startup successful, save pid so we know it's running
                        vdus.pid = pid
                        vdus.process_name = psutil.Process(pid=pid).name()
                        vdus.save_without_signals()
                    self.log("Found vnc pid {}, pid valid: {}".format(pid, server_success))

                    websockify_success = True
                    if s.uses_websockify:
                        websockify_success = False
                        # this server uses websockify and we must track it
                        websockify_pid = s.get_websockify_pid_from_file()

                        if websockify_pid and _check_process_running(websockify_pid, log=self.log):
                            # websockify has started as well
                            vdus.websockify_pid = websockify_pid
                            vdus.websockify_process_name = psutil.Process(pid=websockify_pid).name()
                            vdus.save_without_signals()
                            websockify_success = True

                        self.log("Found websocket pid {}, pid valid: {}".format(websockify_pid, websockify_success))

                    if server_success and websockify_success:
                        # everything has started
                        vdus.update_state(virtual_desktop_user_setting.State.RUNNING)
                    else:
                        # not successful so far
                        if ignore_last_start_attempt:
                            do_start = True  # if we just restart, we don't want to wait, but still not start the server if it's already running now
                        else:
                            self.log("No successful virtual desktop start ({}, {}), waiting for it to become available or timeout".format(server_success,
                                                                                                                                          websockify_success))
                if do_start:
                    # start
                    self.log("Starting virtual desktop session {} {}".format(vdus.virtual_desktop_protocol.name, vdus.window_manager.name))

                    s.stop()
                    s.start()

            else:
                vdus.update_state(virtual_desktop_user_setting.State.RUNNING)
        else:
            # check if really not running and stop in case
            vdus.update_state(virtual_desktop_user_setting.State.DISABLED)

            if _check_vdus_running(vdus):
                self.log("stopping virtual desktop session {} {}".format(vdus.virtual_desktop_protocol.name, vdus.window_manager.name))
                s = klass(self.log, vdus)
                s.stop()


def _check_vdus_running(vdus, log=None):
    if not _check_process_running(vdus.pid, vdus.process_name, log=log):
        if log:
            log("Virtual desktop server not running {} {} ".format(vdus.pid, vdus.process_name))
        return False
    if virtual_desktop_server.get_class_for_vdus(vdus).uses_websockify:
        # check websockify
        if not _check_process_running(vdus.websockify_pid, vdus.websockify_process_name, log=log):
            if log:
                log("websockify not running {} {} ".format(vdus.pid, vdus.process_name))
            return False
    return True


def _check_process_running(*args, **kwargs):
    return bool(_get_running_process(*args, **kwargs))


def _get_running_process(pid, process_name=None, log=None):
    try:
        p = psutil.Process(pid=pid)
        if log:
            log("Found process {}, running: {}".format(p, p.is_running()))
        if p.is_running():
            if not process_name or p.name() == process_name:
                return p
            else:
                if log:
                    log("Found process with wrong name ({} vs {})".format(process_name, p.name()))
    except psutil.NoSuchProcess:
        if log:
            log("No such process {} {}".format(pid, process_name))
        pass
    return None


