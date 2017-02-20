#
# Copyright (C) 2001-2009,2011-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-client
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" container for service checks """

import netifaces
import os
import signal
import stat
import psutil
import subprocess

from lxml.builder import E

from initat.constants import VERSION_CS_NAME, INITAT_BASE
from initat.tools import logging_tools, process_tools, config_store, threading_tools
from .constants import *


def check_config_enum(c_enum, config_tools, log_com):
    def _check(c_enum):
        if isinstance(c_enum, list):
            _cr = config_tools.icswServerCheck(service_type_enum_list=c_enum)
        else:
            _cr = config_tools.icswServerCheck(service_type_enum=c_enum)
        return _cr.get_result()

    try:
        _cr = _check(c_enum)
    except (threading_tools.int_error, threading_tools.term_error):
        log_com(
            "got int or term error, reraising",
            logging_tools.LOG_LEVEL_ERROR
        )
        raise
    except:
        config_tools.close_db_connection()
        try:
            _cr = _check(c_enum)
        except:
            raise
            # cannot get server_check instance, set config_check_ok to False
            _cr = None
    return _cr


class Service(object):
    _COMPAT_DICT = {
        "rms-server": "rms_server",
        "logcheck-server": "logcheck",
    }

    def __new__(cls, entry, log_com):
        _ct = entry.attrib["check_type"]
        if _ct == "simple":
            new_cls = SimpleService
        elif _ct == "meta":
            new_cls = MetaService
        elif _ct == "pid_file":
            new_cls = PIDService
        else:
            raise KeyError("unknown check_type '{}'".format(_ct))
        return super(Service, new_cls).__new__(new_cls)

    def __init__(self, entry, log_com):
        self.__log_com = log_com
        self.name = entry.attrib["name"]
        self.__entry = entry
        self.__attrib = dict(self.__entry.attrib)
        self.config_check_ok = True

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[srv {}] {}".format(self.name, what), log_level)

    @property
    def attrib(self):
        return self.__attrib

    @property
    def entry(self):
        return self.__entry

    @property
    def init_script_name(self):
        return os.path.join("/", "etc", "init.d", self.attrib["init_script_name"])

    @property
    def msi_name(self):
        c_name = self.attrib["name"]
        _path = os.path.join("/", "var", "lib", "meta-server", c_name)
        # compat layer for buggy specs
        if not os.path.exists(_path) and c_name in self._COMPAT_DICT:
            _alt_path = os.path.join("/", "var", "lib", "meta-server", self._COMPAT_DICT[c_name])
            if os.path.exists(_alt_path):
                _path = _alt_path
        return _path

    @property
    def old_binary(self):
        # returns name of old binary
        _old_bin = self.entry.findtext(".//old-binary")
        if _old_bin:
            _old_bin = _old_bin.strip()
        else:
            _old_bin = self.name
        return _old_bin

    @property
    def prog_title(self):
        _prog_title = self.entry.findtext(".//programm-title")
        if _prog_title:
            _prog_title = _prog_title.strip()
        else:
            _prog_title = "icsw.{}".format(self.name)
        return _prog_title

    @property
    def prog_name(self):
        _prog_name = self.entry.findtext(".//programm-name")
        if _prog_name:
            _prog_name = _prog_name.strip()
        else:
            _prog_name = self.name
        return _prog_name

    @property
    def module_name(self):
        _mod_name = self.entry.findtext(".//module-name")
        if _mod_name:
            _mod_name = _mod_name.strip()
        else:
            _mod_name = "initat.{}.main".format(self.name.replace("-", "_"))
        return _mod_name

    @property
    def run_state(self):
        # return
        # - "ok" if the service in entry is running completely (no processes missing)
        # - "warn" if the service is only running partially
        # - "error" if the service is not running
        if len(self.entry.findall(".//pids/pid")):
            # any pids found
            _si = self.entry.find(".//process_state_info")
            if _si is not None:
                _state = int(_si.get("state"))
                return "ok" if _state in [SERVICE_OK, SERVICE_NOT_CONFIGURED] else "warn"
            else:
                return "error"
        else:
            _si = self.entry.find(".//process_state_info[@check_source='simple']")
            if _si is not None:
                _state = int(_si.get("state"))
                return "ok" if _state in [SERVICE_OK, SERVICE_NOT_CONFIGURED] else "warn"
            else:
                return "error"

    def check(
        self,
        act_proc_dict,
        refresh=True,
        config_tools=None,
        valid_licenses=None,
        version_changed=False,
        meta_result=None,
        check_results=None,
    ):
        if self.entry.find("result") is not None:
            if refresh:
                # remove current result record
                self.entry.remove(self.entry.find("result"))
            else:
                # result record already present, return
                return
        dev_config, dev_config_error = ([], [])
        if config_tools is not None:
            if check_results is None:
                # check config status via config_tools call
                try:
                    from initat.cluster.backbone.server_enums import icswServiceEnum
                except ImportError:
                    from initat.host_monitoring.client_enums import icswServiceEnum
                if self.entry.find(".//config-enums/config-enum") is not None:
                    _enum_names = [
                        _entry.text for _entry in self.entry.findall(".//config-enums/config-enum")
                    ]
                    # print("_enum", _enum_names)
                    for _enum_name in _enum_names:
                        _enum = getattr(icswServiceEnum, _enum_name)
                        if config_tools is not None:
                            _cr = check_config_enum(_enum, config_tools, self.log)
                        else:
                            _cr = None
                        if _cr is None:
                            # cannot get server_check instance, set config_check_ok to False
                            self.config_check_ok = False
                        else:
                            if _cr.effective_device:
                                dev_config.append(_cr)
                            else:
                                dev_config_error.append(_cr.server_info_str)
            else:
                # check results already evaluated
                for _cr in check_results:
                    if _cr.effective_device:
                        dev_config.append(_cr)
                    else:
                        dev_config_error.append(_cr.server_info_str)
        required_ips = set(
            list(
                self.entry.xpath(".//required-ips/required-ip/text()", smart_strings=True)
            )
        )
        if required_ips:
            _found_ips = set(
                [
                    _val["addr"] for _val in sum(
                        [
                            netifaces.ifaddresses(_dev).get(netifaces.AF_INET, []) for _dev in netifaces.interfaces()
                        ],
                        []
                    )
                ]
            )
            ip_match = True if required_ips & _found_ips else False
        else:
            ip_match = True
        _result = E.result()
        self.entry.append(_result)

        self._check(_result, act_proc_dict)

        act_state = int(_result.find("process_state_info").attrib["state"])
        c_state = CONF_STATE_RUN

        if meta_result is not None:
            _meta_result = meta_result.xpath(".//ns:instance[@name='{}']".format(self.attrib["name"]))
            if len(_meta_result):
                _meta_result = _meta_result[0]
                _result.append(
                    E.meta_result(
                        target_state=_meta_result.get("target_state"),
                        ignore=_meta_result.get("ignore"),
                    )
                )
        run_info = []
        if self.attrib["runs_on"] == "server":
            if version_changed:
                # force state to failed
                c_state = CONF_STATE_MODELS_CHANGED
                run_info.append("DB / models changed")
            else:
                if dev_config:
                    run_info.append(
                        ", ".join(
                            [
                                _dc.server_info_str for _dc in dev_config
                            ]
                        )
                    )
                else:
                    if self.entry.find(".//ignore-missing-database") is not None:
                        run_info.append("relayer mode")
                    else:
                        c_state = CONF_STATE_STOP
                        run_info.append(
                            ", ".join(
                                sorted(
                                    list(
                                        set(dev_config_error)
                                    )
                                )
                            ) or "not configured"
                        )
            if valid_licenses is not None:
                from initat.cluster.backbone.models import License
                _req_lic = self.entry.find(".//required-license")
                if _req_lic is not None:
                    _req_lic = _req_lic.text.strip()
                    # default license state
                    lic_state = LIC_STATE_NONE
                    for _vl in valid_licenses:
                        if _vl.name == _req_lic:
                            lic_state = License.objects._get_license_state(_vl)
                            break
                else:
                    lic_state = LIC_STATE_NOT_NEEDED
            else:
                lic_state = LIC_STATE_NOT_NEEDED
        else:
            lic_state = LIC_STATE_NOT_NEEDED
            run_info.append(self.attrib["runs_on"])
        if not ip_match:
            c_state = CONF_STATE_IP_MISMATCH
            run_info.append("IP mismatch")
        _result.append(
            E.configured_state_info(
                state="{:d}".format(c_state)
            )
        )
        _result.append(
            E.config_info(", ".join(run_info))
        )
        _result.append(
            E.license_info(state="{:d}".format(lic_state))
        )
        if self.entry.get("runs_on") in ["client", "server"] and act_state != SERVICE_NOT_INSTALLED:
            _result.attrib["version_ok"] = "0"
            try:
                _cs = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
                _result.attrib["version_ok"] = "1"
                _result.attrib["version"] = _cs["software"]
            except:
                _result.attrib["version"] = "error getting version: {}".format(process_tools.get_except_info())

    def _get_proc_info_str(self, unique_pids, num_found, diff_dict, any_ok):
        num_procs = len(unique_pids)
        ret_f = []
        if any_ok and False:
            ret_f.append(
                "{} running".format(logging_tools.get_plural("process", num_found))
            )
        else:
            num_under, num_over = (
                len([_v for _v in diff_dict.values() if _v < 0]),
                len([_v for _v in diff_dict.values() if _v > 0]),
            )
            if num_under:
                ret_f.append(
                    "{} {} missing".format(
                        logging_tools.get_plural("process", num_under),
                        num_under == 1 and "is" or "are",
                    )
                )
            if num_over:
                ret_f.append(
                    "{} too much".format(
                        logging_tools.get_plural("process", num_over),
                    )
                )
            if not num_under and not num_over:
                ret_f.append(
                    "the process is running" if num_procs == 1 else "{}{} running".format(
                        "all " if num_procs > 1 else "",
                        logging_tools.get_plural("process", num_procs),
                    )
                )
            if diff_dict:
                ret_f.append(
                    "[diff: {}]".format(
                        ", ".join(
                            [
                                "{:d}: {:d}".format(
                                    _key,
                                    _value
                                ) for _key, _value in diff_dict.items()
                            ]
                        )
                    )
                )
        return ", ".join(ret_f)

    def _check_processes(self, pids, act_proc_dict):
        # name = self.name
        any_ok = True if int(self.attrib["any-processes-ok"]) else False
        unique_pids = {
            key: pids.count(key) for key in set(pids)
        }
        pids_found = {key: True for key in set(pids) if key in act_proc_dict}
        # for key in set(pids):
        #    if key in act_proc_dict:
        #        try:
        #            pids_found[key] = act_proc_dict[key].num_threads()
        #        except psutil.NoSuchProcess:
        #            pass
        # num_started = sum(unique_pids.values()) if unique_pids else 0
        # num_found = sum(pids_found.values()) if pids_found else 0
        num_started = len(unique_pids)
        num_found = len(pids_found)
        # print num_started, num_found, unique_pids, pids_found
        # check for extra Nagios2.x thread
        if any_ok and num_found:
            ret_state = SERVICE_OK
        elif num_started == num_found:
            ret_state = SERVICE_OK
        else:
            ret_state = SERVICE_NOT_CONFIGURED
        return ret_state, num_started, num_found

    def _add_non_running(self, result, check_init_script=True):
        init_script_name = self.init_script_name
        if os.path.isfile(init_script_name) or check_init_script is False:
            act_state = SERVICE_DEAD
            result.append(
                E.process_state_info(
                    "no processes",
                    state="{:d}".format(act_state),
                )
            )
        else:
            act_state = SERVICE_NOT_INSTALLED
            result.append(
                E.process_state_info(
                    "not installed",
                    state="{:d}".format(act_state),
                )
            )

    def _add_pids(self, result, act_pids, act_proc_dict, main_pid=None, msi_block=None):
        # print "+", main_pid
        if act_pids:
            mem_pids = set([pid for pid in act_pids])
            if int(self.attrib["sum-subprocesses"]):
                _added = True
                while _added:
                    _added = False
                    for _key, _value in act_proc_dict.items():
                        if _key not in mem_pids:
                            try:
                                _ppid = _value.ppid()
                                if _ppid in mem_pids:
                                    mem_pids.add(_key)
                                    _added = True
                            except (FileNotFoundError, psutil.NoSuchProcess):
                                pass
            result.append(
                E.pids(
                    *[
                        E.pid(
                            "{:d}".format(cur_pid),
                            count="{:d}".format(act_pids.count(cur_pid)),
                            main="1" if cur_pid == main_pid else "0",
                        ) for cur_pid in set(act_pids)
                    ]
                )
            )

            mem_dict = {
                cur_pid: process_tools.get_mem_info(cur_pid) for cur_pid in mem_pids
            }
            _mem_info = E.memory_info(
                "{:d}".format(
                    sum(mem_dict.values()),
                ) if act_pids else "",
                valid="1" if act_pids else "0",
            )
            if msi_block and act_pids:
                _mem_info.append(
                    E.details(
                        *[
                            E.mem("{:d}".format(_value), name=msi_block.get_process_name(_key)) for _key, _value in mem_dict.items()
                        ]
                    )
                )
            result.append(_mem_info)

    # action commands
    def action(self, action, act_proc_dict, debug_args=None):
        _cmd = {
            "stop": self.stop,
            "start": self.start,
            "cleanup": self.cleanup,
            "wait": self.wait,
            "debug": self.debug,
            "reload": self.reload,
            # special command when active service is restart: signal a simple restart command
            "signal_restart": self.signal_restart,
        }[action]
        if action == "debug":
            return _cmd(act_proc_dict, debug_args)
        else:
            return _cmd(act_proc_dict)

    def wait(self, act_proc_dict):
        return

    def reload(self, act_proc_dict):
        if not int(self.entry.get("reload", "1")) and False:
            return
        self._reload()

    def _reload(self):
        # for subclasses
        pass

    def start(self, act_proc_dict):
        if not int(self.entry.get("startstop", "1")):
            return
        self._start()

    def _start(self):
        # for subclasses
        pass

    def stop(self, act_proc_dict):
        if not int(self.entry.get("startstop", "1")):
            return
        self._stop()

    def _stop(self):
        pass

    def debug(self, act_proc_dict, debug_args):
        if not int(self.entry.get("startstop", "1")):
            return
        self._debug(debug_args)

    def _debug(self, debug_args):
        # for subclasses
        pass

    def signal_restart(self, act_proc_dict):
        if not int(self.entry.get("startstop", "1")):
            return
        self._signal_restart()

    def _signal_restart(self):
        # for subclasses
        pass

    def cleanup(self, act_proc_dict):
        # late import of psutil to avoid chroot errors
        import psutil
        if not int(self.entry.get("startstop", "1")):
            return
        _meta_pids = set([int(_val.text) for _val in self.entry.findall(".//pids/pid")])
        # protect myself from getting killed :-)
        _proc_pids = self._find_pids_by_name(act_proc_dict) - set([os.getpid()])
        # self.log("cleanup {} {}".format(str(_meta_pids), str(_proc_pids)))
        _all_pids = _meta_pids | _proc_pids
        if _all_pids:
            for _pid in _all_pids:
                try:
                    _cur_proc = psutil.Process(_pid)
                except psutil.NoSuchProcess:
                    self.log("process {:d} no longer exists".format(_pid), logging_tools.LOG_LEVEL_WARN)
                else:
                    try:
                        os.kill(_pid, 9)
                    except OSError:
                        self.log("process {:d} has vanished".format(_pid), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("sent signal 9 to {:d}".format(_pid))
        # remove meta server
        ms_name = self.msi_name
        if os.path.exists(ms_name):
            self.log("removing msi-block {}".format(ms_name))
            os.unlink(ms_name)

    def _find_pids_by_name(self, act_proc_dict):
        _new_title = self.prog_title
        _old_bins = self.old_binary.strip().split(",")
        # print _new_title, "old_bins", _old_bins
        _pid_list = set()
        for _key, _value in act_proc_dict.items():
            try:
                _cmdline = _value.cmdline()
            except:
                # can be ignored
                pass
            else:
                if _cmdline:
                    _cmdline = sum([_part.strip().split() for _part in _cmdline], [])
                    if _cmdline:  # kernel processes such as kthreadd can have an empty command line
                        if _cmdline[0] == _new_title:
                            # print "+", _cmdline, _new_title
                            _pid_list.add(_key)
                        elif _cmdline[0].endswith("python-init"):
                            # print _cmdline
                            _icsw_found, _old_found = (
                                any([_part.count("icsw") or _part.count("check_scripts") for _part in _cmdline]),
                                False
                            )
                            # print "*", _cmdline
                            for _part in _cmdline:
                                if any(
                                    [
                                        _part.count(_old_bin) for _old_bin in _old_bins
                                    ]
                                ):
                                    # match
                                    _old_found = True
                            # print _old_found, _icsw_found
                            if _old_found and not _icsw_found:
                                _pid_list.add(_key)
        # print "found", _pid_list
        return _pid_list


class SimpleService(Service):
    # Service backup up by an init-RC script
    def _check(self, result, act_proc_dict):
        init_script_name = self.init_script_name
        pid_file_name = self.attrib["pid_file_name"]
        _status_from_pid = True if int(self.attrib["status_from_pid"]) else False
        if not pid_file_name.startswith("/"):
            pid_file_name = os.path.join("/", "var", "run", pid_file_name)
        if os.path.isfile(pid_file_name):
            start_time = os.stat(pid_file_name)[stat.ST_MTIME]
        else:
            start_time = 0
        if os.path.isfile(init_script_name):
            if _status_from_pid:
                if os.path.isfile(pid_file_name):
                    act_state, act_str = (SERVICE_OK, "running")
                else:
                    act_state, act_str = (SERVICE_DEAD, "not running")
            else:
                if os.getuid() != 0:
                    self.log(
                        "Need root permissions to reliably obtain status information.",
                        logging_tools.LOG_LEVEL_WARN
                    )
                (_status, _output) = process_tools.getstatusoutput("{} status".format(init_script_name))
                if _status == 0:
                    act_state, act_str = (SERVICE_OK, "running")
                else:
                    act_state, act_str = (SERVICE_DEAD, "not running")

        else:
            act_state, act_str = (SERVICE_NOT_INSTALLED, "not installed")
        result.append(
            E.process_state_info(
                act_str,
                check_source="simple",
                state="{:d}".format(act_state),
                proc_info_str=act_str,
                start_time="{:d}".format(start_time),
            ),
        )
        if "pid_file_name" in self.attrib:
            pid_file_name = self.attrib["pid_file_name"]
            if not pid_file_name.startswith("/"):
                pid_file_name = os.path.join("/", "var", "run", pid_file_name)
            if os.path.isfile(pid_file_name):
                try:
                    act_pid = int(open(pid_file_name, "r").read().strip())
                except:
                    pass
                else:
                    self._add_pids(result, [act_pid], act_proc_dict)

    def _start(self):
        self._handle_service_rc("start")

    def _stop(self):
        self._handle_service_rc("stop")

    def _handle_service_rc(self, command):
        if os.path.exists(self.init_script_name):
            process_tools.call_command(
                "{} {}".format(
                    self.init_script_name,
                    command
                ),
                self.log
            )
        else:
            self.log(
                "rc-script {} does not exist".format(
                    self.init_script_name
                ),
                logging_tools.LOG_LEVEL_WARN
            )


class PIDService(Service):
    # Service backed up by a PID-file
    def _check(self, result, act_proc_dict):
        name = self.name
        pid_file_name = self.attrib["pid_file_name"]
        if not pid_file_name.startswith("/"):
            pid_file_name = os.path.join("/", "var", "run", pid_file_name)
        if os.path.isfile(pid_file_name):
            start_time = os.stat(pid_file_name)[stat.ST_CTIME]
            # print("*", start_time, pid_file_name)
            act_pids = [int(line.strip()) for line in open(pid_file_name, "r").read().split("\n") if line.strip().isdigit()]
            act_state, num_started, num_found = self._check_processes(act_pids, act_proc_dict)
            unique_pids = set(act_pids)
            diff_dict = {}
            result.append(
                E.process_state_info(
                    *[
                        E.diff_info(
                            pid="{:d}".format(key),
                            diff="{:d}".format(value)
                        ) for key, value in diff_dict.items()
                    ],
                    check_source="pid",
                    num_started="{:d}".format(num_started),
                    num_found="{:d}".format(num_found),
                    num_diff="{:d}".format(abs(num_started - num_found)),
                    start_time="{:d}".format(start_time),
                    state="{:d}".format(act_state),
                    proc_info_str=self._get_proc_info_str(
                        unique_pids,
                        num_found,
                        diff_dict,
                        True if int(self.entry.attrib["any-processes-ok"]) else False,
                    )
                ),
            )
            self._add_pids(result, act_pids, act_proc_dict)
        else:
            self._add_non_running(result)


class MetaService(Service):
    # Service backup up by a meta-server file
    def _check(self, result, act_proc_dict):
        ms_name = self.msi_name
        if os.path.exists(ms_name):
            # TODO : cache msi files
            ms_block = process_tools.MSIBlock(ms_name)
            start_time = ms_block.start_time
            # trigger check
            _check = ms_block.do_check(act_proc_dict)
            diff_dict = {
                key: value for key, value in ms_block.bound_dict.items() if value
            }
            diff_procs = sum([abs(_v) for _v in list(diff_dict.values())]) if diff_dict else 0
            act_pids = ms_block.pids_found
            # print "*", act_pids
            unique_pids = set(act_pids)
            num_started = len(act_pids)
            if diff_procs:
                act_state = SERVICE_INCOMPLETE
                # hm, not correct, FIXME
                num_found = num_started
            else:
                act_state = SERVICE_OK
                num_found = num_started
            result.append(
                E.process_state_info(
                    *[
                        E.diff_info(
                            pid="{:d}".format(key),
                            diff="{:d}".format(value)
                        ) for key, value in diff_dict.items()
                    ],
                    check_source="meta",
                    num_started="{:d}".format(num_started),
                    num_found="{:d}".format(num_found),
                    num_diff="{:d}".format(diff_procs),
                    start_time="{:d}".format(int(start_time)),
                    state="{:d}".format(act_state),
                    proc_info_str=self._get_proc_info_str(
                        unique_pids,
                        num_found,
                        diff_dict,
                        True if int(self.entry.attrib["any-processes-ok"]) else False,
                    )
                ),
            )
            # print act_pids, ms_block.pids
            self._add_pids(result, act_pids, act_proc_dict, main_pid=ms_block.get_main_pid(), msi_block=ms_block)
        else:
            self._add_non_running(result, check_init_script=False)

    def _stop(self):
        _main_pids = [int(_val.text) for _val in self.entry.findall(".//pids/pid[@main='1']")]
        _meta_pids = [int(_val.text) for _val in self.entry.findall(".//pids/pid")]
        # print etree.tostring(entry, pretty_print=True)
        # print _main_pids, _meta_pids
        if len(_meta_pids):
            try:
                if _main_pids:
                    os.kill(_main_pids[0], signal.SIGTERM)
                    self.log("sent signal {:d} to {:d}".format(signal.SIGTERM, _main_pids[0]))
                else:
                    os.kill(_meta_pids[0], signal.SIGTERM)
                    self.log("sent signal {:d} to {:d}".format(signal.SIGTERM, _meta_pids[0]))
            except OSError:
                self.log("process vanished: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no pids to kill")

    def _reload(self):
        _main_pids = [int(_val.text) for _val in self.entry.findall(".//pids/pid[@main='1']")]
        _meta_pids = [int(_val.text) for _val in self.entry.findall(".//pids/pid")]
        if len(_meta_pids):
            try:
                if _main_pids:
                    os.kill(_main_pids[0], signal.SIGHUP)
                    self.log("sent signal {:d} to {:d}".format(signal.SIGHUP, _main_pids[0]))
                else:
                    os.kill(_meta_pids[0], signal.SIGHUP)
                    self.log("sent signal {:d} to {:d}".format(signal.SIGHUP, _meta_pids[0]))
            except OSError:
                self.log("process vanished: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no pids to signal")

    def _start(self):
        arg_list = self._generate_py_arg_list()
        self.log("starting: {}".format(" ".join(arg_list)))
        if not os.fork():
            subprocess.call(arg_list + ["-d"])
            os._exit(1)
        else:
            _child_pid, _child_state = os.wait()

    def _debug(self, debug_args):
        # ignore sigint to catch keyboard interrupt
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        arg_list = self._generate_py_arg_list(debug=True)
        arg_list.append("--debug")
        if "--debug-flag" in debug_args:
            # move debug flag to arg_list
            arg_list.append("--debug-flag")
            debug_args.remove("--debug-flag")
        if debug_args:
            arg_list.append("--")
            arg_list.extend(debug_args)
        self.log("debug, arg_list is '{}'".format(" ".join(arg_list)))
        subprocess.call(" ".join(arg_list), shell=True)

    def _signal_restart(self):
        if self.name in ["meta-server"]:
            from initat.tools import net_tools, server_command
            self.log("sending signal-restart")
            _result = net_tools.ZMQConnection(
                "icsw_restart_{:d}".format(os.getpid())
            ).add_connection(
                "tcp://localhost:8012",
                server_command.srv_command(
                    command="next-stop-is-restart",
                ),
            )
            if _result is not None:
                self.log(*_result.get_log_tuple())

    def _generate_py_arg_list(self, debug=False):
        _prog_name = self.prog_name
        _prog_title = self.prog_title
        arg_dict = {_val.get("key"): _val.text.strip() for _val in self.entry.findall(".//arg[@key]")}
        _module_name = self.entry.get("module", self.module_name)
        if debug:
            _daemon_path = os.path.split(os.path.split(os.path.dirname(__file__))[0])[0]
        else:
            _daemon_path = INITAT_BASE
        _arg_list = [
            os.path.join(_daemon_path, "tools", "daemonize.py"),
            "--progname",
            _prog_name,
            "--modname",
            _module_name,
            "--proctitle",
            _prog_title,
        ]
        for _add_key in ["user", "group", "groups"]:
            if _add_key in arg_dict:
                _arg_list.extend(
                    [
                        "--{}".format(_add_key),
                        arg_dict[_add_key],
                    ]
                )
        if self.entry.find("nice-level") is not None:
            _arg_list.extend(
                [
                    "--nice",
                    "{:d}".format(int(self.entry.findtext("nice-level").strip())),
                ]
            )
        # check access rights
        for _dir_el in self.entry.findall(".//access-rights/dir[@value]"):
            _dir = _dir_el.get("value")
            if not os.path.isdir(_dir) and int(_dir_el.get("create", "0")):
                os.makedirs(_dir)
            _recursive = True if int(_dir_el.get("recursive", "0")) else False
            if "mask" in _dir_el.attrib:
                _mask = _dir_el.get("mask")
                try:
                    _mask = int(_mask, 8)
                except:
                    self.log(
                        "cannot interpret mask '{}' with base 8".format(
                            _mask,
                        ),
                        logging_tools.LOG_LEVEL_ERROR,
                    )
                    _mask = None
            else:
                _mask = None
            if os.path.isdir(_dir):
                if _mask:
                    os.chmod(_dir, _mask)
                _uid, _gid = (
                    process_tools.get_uid_from_name(_dir_el.get("user", "root"))[0],
                    process_tools.get_gid_from_name(_dir_el.get("group", "root"))[0],

                )
                os.chown(_dir, _uid, _gid)
                if _recursive:
                    for _dir, _dirs, _files in os.walk(_dir):
                        for _file in _files:
                            _file = os.path.join(_dir, _file)
                            if os.path.isfile(_file):
                                os.chown(_file, _uid, _gid)
        for _file_el in self.entry.findall(".//access-rights/file[@value]"):
            if os.path.isfile(_file_el.get("value")):
                os.chown(
                    _file_el.get("value"),
                    process_tools.get_uid_from_name(_file_el.get("user", "root"))[0],
                    process_tools.get_gid_from_name(_file_el.get("group", "root"))[0],
                )
        return _arg_list
