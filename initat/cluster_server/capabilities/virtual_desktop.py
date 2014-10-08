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
from psutil import NoSuchProcess
""" virtual desktop capability """

from django.db.models import Q
from django.utils import timezone
from initat.cluster.backbone.models import device
from initat.cluster_server.capabilities.base import bg_stuff
from initat.cluster_server.config import global_config
import process_tools
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
try:
    from initat.cluster.backbone.models import virtual_desktop_protocol, window_manager, virtual_desktop_user_setting
except ImportError:
    virtual_desktop_protocol = None
    virtual_desktop_user_setting = None
    window_manager = None


class virtual_desktop_server(object):
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
    def get_class_for_protocol(cls, proto):
        if proto == "vnc":
            return vncserver
        else:
            raise Exception("Unknown virtual desktop protocol: {}".format(proto))


class vncserver(virtual_desktop_server):
    def __init__(self, logger, vdus):
        super(vncserver, self).__init__(logger)
        self.vdus = vdus

        self.user_home_dir = os.path.expanduser("~"+self.vdus.user.login)
        self.corvus_dir = "{}/.corvus".format(self.user_home_dir)
        self.vnc_home_dir = "{}/vncsession-{}".format(self.corvus_dir, self.vdus.pk)
        self.vnc_dir = "{}/.vnc".format(self.vnc_home_dir)
        self.pwd_file = "{}/passwd".format(self.vnc_dir)
        # we don't know the display number, but there can only be one:
        self.pid_file_pattern = "{}/*.pid".format(self.vnc_dir)
        self.vncstartup_file = "{}/xstartup".format(self.vnc_dir)

    def setup(self):
        # must be called once before first start
        vnc_user_uid = self.vdus.user.uid

        # set up files and directories needed for vncserver to start
        if not os.path.exists(self.corvus_dir):
            os.mkdir(self.corvus_dir)
            os.chown(self.corvus_dir, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))

        # fresh dir for every start
        if os.path.exists(self.vnc_home_dir):
            shutil.rmtree(self.vnc_home_dir)

        os.mkdir(self.vnc_home_dir)
        os.chown(self.vnc_home_dir, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))

        os.mkdir(self.vnc_dir)
        os.chown(self.vnc_dir, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))
        os.chmod(self.vnc_dir, 0700)

        # get binary data using vncpasswd
        outfile = open(self.pwd_file, "w")
        vncpw_proc = subprocess.Popen(["vncpasswd", "-f"], stdin=subprocess.PIPE, stdout=outfile)
        vncpw_proc.stdin.write("init4uinit4u")
        vncpw_proc.stdin.close()
        vncpw_proc.wait()
        outfile.close()

        os.chown(self.pwd_file, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))
        os.chmod(self.pwd_file, 0600)

        # create startup file
        with open(self.vncstartup_file, "w") as f:
            f.write("#!/bin/sh\n")
            f.write("export HOME=\"{}\"\n".format(self.user_home_dir))
            f.write(self.vdus.window_manager.binary+" &\n")

        # make startup file executable
        os.chown(self.vncstartup_file, vnc_user_uid, self._get_gid_of_uid(vnc_user_uid))
        os.chmod(self.vncstartup_file, 0700)

    def start(self):
        cmd_line = "vncserver"
        cmd_line += " -geometry {} ".format(self.vdus.screen_size)
        if self.vdus.port != 0:
            cmd_line += " -rfbport {}".format(self.vdus.port)
        cmd_line += " -rfbauth {}".format(self.pwd_file)

        self.log("Starting vncserver with command line: {}".format(cmd_line))

        vnc_env = os.environ.copy()
        vnc_env["HOME"] = self.vnc_home_dir
        vnc_env["XAUTHORITY"] = "{}/.Xauthority".format(self.vnc_home_dir)

        def preexec():
            os.setgid(self._get_gid_of_uid(self.vdus.user.uid))
            os.setuid(self.vdus.user.uid)

        if global_config["DEBUG"]:
            proc_stdout, proc_stderr = None, None
        else:
            proc_stdout, proc_stderr = open(os.devnull, "w"), open(os.devnull, "w")

        def vnc_start_fun():
            # make sure not to interfere with db
            from django.db import connection
            connection.close()

            # turn process into daemon
            with daemon.DaemonContext(detach_process=True, stdout=sys.stdout, stderr=sys.stderr):
                # execute vnc start script in daemon
                subprocess.Popen(cmd_line.strip().split(), env=vnc_env, preexec_fn=preexec, stdout=proc_stdout, stderr=proc_stderr)

        proc = multiprocessing.Process(target=vnc_start_fun)
        proc.start()

    def stop(self):
        p = _check_process_running(self.vdus.pid, self.vdus.process_name)
        if p:
            self.log("Killing process with pid {}".format(p.pid))
            p.kill()
        else:
            self.log("Stop called but vnc server process isn't running (any more)")

    def get_pid_from_file(self):
        try:
            pid_file = glob.glob(self.pid_file_pattern)[0]
            return int(open(pid_file, "r").read())
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
        if self.__first_run:
            self.__first_run = False
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

        # check if services are running as desired
        for vdus in virtual_desktop_user_setting.objects.filter(device=self.__effective_device):
            if vdus.is_running:
                # check if actually running and start in case
                if not _check_process_running(vdus.pid, vdus.process_name):
                    try:
                        klass = virtual_desktop_server.get_class_for_protocol(vdus.virtual_desktop_protocol.name)
                    except Exception as e:
                        self.log(e)
                        continue

                    s = klass(self.log, vdus)

                    if (timezone.now() - vdus.last_start_attempt) < datetime.timedelta(minutes=5):
                        # check if pid file has appeared and contains valid pid
                        pid = s.get_pid_from_file()
                        self.log("Last start attempt was earlier than 5 minutes, found pid: {}".format(pid))
                        if pid:
                            # we found a pid, check if it's valid
                            try:
                                p = psutil.Process(pid=pid)
                                # startup successful, save pid so we know it's running
                                vdus.pid = pid
                                vdus.process_name = p.name()
                                vdus.save()
                                self.log("Virtual desktop server startup successful")
                            except NoSuchProcess:
                                self.log("Virtual desktop server pid not valid")
                    else:
                        # start
                        self.log("Virtual desktop session {} {} should be running but isn't, starting".format(vdus.virtual_desktop_protocol.name,
                                                                                                              vdus.window_manager.name))
                        s.setup()
                        s.start()
                        vdus.last_start_attempt = timezone.now()
                        vdus.save()
            else:
                # check if really not running and stop in case
                if _check_process_running(vdus.pid, vdus.process_name):
                    self.log("Virtual desktop session {} {} should not be running but is, stopping".format(vdus.virtual_desktop_protocol.name,
                                                                                                           vdus.window_manager.name))
                    try:
                        klass = virtual_desktop_server.get_class_for_protocol(vdus.virtual_desktop_protocol.name)
                    except Exception as e:
                        self.log(e)
                        continue

                    s = klass(self.log, vdus)
                    s.stop()


def _check_process_running(pid, process_name):
    try:
        p = psutil.Process(pid=pid)
        if p.name() == process_name and p.is_running():
            return p
        else:
            return None
    except psutil.NoSuchProcess:
        return None
