# Copyright (C) 2001-2015,2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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

import os
import stat
import subprocess
import time

from initat.constants import PLATFORM_SYSTEM_TYPE, PlatformSystemTypeEnum
from initat.tools import logging_tools, process_tools, server_command
from .. import filesys_tools, limits, hm_classes
from ..constants import HMAccessClassEnum


class ModuleDefinition(hm_classes.MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "4fb08ee8-99da-4b3d-b232-df0ecc54629c"

    def _parse_ecd(self, in_str):
        # parse exclude_checkdate, ecd has the form [WHHMM][-WHHMM]
        # W ... weekday, 1 ... monday, 7 ... sunday
        if in_str.count("-"):
            start_str, end_str = in_str.strip().split("-")
            if not len(start_str):
                start_str = None
            if not len(end_str):
                end_str = None
        else:
            start_str, end_str = (in_str.strip(), None)
        return (self._parse_ecd2(start_str), self._parse_ecd2(end_str))

    def _parse_ecd2(self, in_str):
        if in_str is None:
            return in_str
        else:
            if len(in_str) != 5 or not in_str.isdigit():
                raise SyntaxError("exclude_checkdate '{}' has wrong form (not WHHMM)".format(in_str))
            weekday, hour, minute = (
                int(in_str[0]),
                int(in_str[1:3]),
                int(in_str[3:5])
            )
            if weekday < 1 or weekday > 7:
                raise SyntaxError("exclude_checkdate '%s' has invalid weekday" % (in_str))
            if hour < 0 or hour > 23:
                raise SyntaxError("exclude_checkdate '%s' has invalid hour" % (in_str))
            if minute < 0 or minute > 59:
                raise SyntaxError("exclude_checkdate '%s' has invalid minute" % (in_str))
            return (weekday, hour, minute)


class check_file_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "7c70d4c2-f933-4576-86dd-112cb4b6cc1e"
        description = "information about files (size, gid, uid, change dates)"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter(
                "--min-mod-time",
                "mod_diff_time",
                0,
                "minimum difference in modification time in seconds",
            ),
            hm_classes.MCParameter(
                "--min-size",
                "min_file_size",
                0,
                "minimum file size in Bytes",
            ),
            # hm_classes.MCParameter(
            #    "--exclude-checkdate",
            #    "exclude_checkdate",
            #    "",
            #    "",
            # ),
            hm_classes.MCParameter("", "arguments", "", "Mountpoint"),
        )

    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" not in srv_com:
            srv_com.set_result("need filename", server_command.SRV_REPLY_STATE_ERROR)
        else:
            file_name = srv_com["arguments:arg0"].text.strip()
            if os.path.isfile(file_name):
                f_stat = os.stat(file_name)
                stat_keys = [key for key in dir(f_stat) if key.startswith("st_")]
                f_stat = dict([(key, getattr(f_stat, key)) for key in stat_keys])
                srv_com["stat_result"] = {
                    "file": file_name,
                    "stat": f_stat,
                    "local_time": time.time()
                }
            else:
                srv_com.set_result("file '{}' not found".format(file_name), server_command.SRV_REPLY_STATE_ERROR)

    def interpret(self, srv_com, cur_ns):
        return self._interpret(srv_com["stat_result"], cur_ns)

    def _interpret(self, f_dict, cur_ns):
        ret_state = limits.mon_STATE_OK
        file_stat = f_dict["stat"]
        if isinstance(file_stat, dict):
            file_size = file_stat["st_size"]
            file_mtime = file_stat["st_mtime"]
        else:
            file_size = file_stat[stat.ST_SIZE]
            file_mtime = file_stat[stat.ST_MTIME]
        add_array = ["size %s" % (logging_tools.get_size_str(file_size))]
        act_time = time.localtime()
        act_time = (
            act_time.tm_wday + 1,
            act_time.tm_hour,
            act_time.tm_min
        )
        act_time = act_time[2] + 60 * (act_time[1] + 24 * act_time[0])
        in_exclude_range = False
        if False and cur_ns.exclude_checkdate:
            for s_time, e_time in cur_ns.exclude_checkdate:
                if s_time:
                    s_time = s_time[2] + 60 * (s_time[1] + 24 * s_time[0])
                if e_time:
                    e_time = e_time[2] + 60 * (e_time[1] + 24 * e_time[0])
                if s_time and e_time:
                    if s_time <= act_time and act_time <= e_time:
                        in_exclude_range = True
                if s_time:
                    if s_time <= act_time:
                        in_exclude_range = True
                if e_time:
                    if act_time <= e_time:
                        in_exclude_range = True
        if in_exclude_range:
            add_array.append("in exclude_range")
        else:
            if cur_ns.mod_diff_time:
                md_time = abs(file_mtime - f_dict["local_time"])
                if md_time > cur_ns.mod_diff_time:
                    ret_state = max(ret_state, limits.mon_STATE_CRITICAL)
                    add_array.append("changed %s ago > %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
                else:
                    add_array.append("changed %s ago < %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
        return ret_state, "file %s %s" % (f_dict["file"],
                                          ", ".join(add_array))


class call_script_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level2
        uuid = "fa28d8d1-0523-4eca-8336-507385d721cf"
        description = "call arbitrary script on target platform"

    def __init__(self, name):
        hm_classes.MonitoringCommand.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--at-time", dest="time", type=int, default=0)
        self.parser.add_argument("--use-at", dest="use_at", default=False, action="store_true")

    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" not in srv_com:
            srv_com.set_result(
                "call_script(): missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            script_name = srv_com["arguments:arg0"].text
            args = []
            while "arguments:arg{:d}".format(len(args) + 1) in srv_com:
                args.append(srv_com["arguments:arg{:d}".format(len(args) + 1)].text)
            if os.path.isfile(script_name):
                if cur_ns.time:
                    cur_ns.use_at = True
                info_str = "Starting script {} with {}: {}".format(
                    script_name,
                    logging_tools.get_plural("argument", len(args)),
                    " ".join(args)
                )
                if cur_ns.use_at:
                    info_str = "{} after {}".format(
                        info_str,
                        logging_tools.get_plural("minute", cur_ns.time)
                    )
                self.log(info_str)
                if cur_ns.use_at:
                    c_stat, log_lines = process_tools.submit_at_command(
                        " ".join([script_name] + args),
                        cur_ns.time
                    )
                    ipl = "\n".join(log_lines)
                else:
                    c_stat, ipl = subprocess.getstatusoutput(
                        " ".join([script_name] + args)
                    )
                    log_lines = ipl.split("\n")
                self.log(
                    " - gave stat {:d} ({}):".format(
                        c_stat,
                        logging_tools.get_plural("log line", len(log_lines))
                    )
                )
                for line in [s_line.strip() for s_line in log_lines]:
                    self.log("   - {}".format(line))
                if c_stat:
                    srv_com.set_result(
                        "problem while executing {}: {}".format(script_name, ipl),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                else:
                    srv_com.set_result(
                        "script {} gave: {}".format(script_name, ipl)
                    )
            else:
                srv_com.set_result(
                    "script {} not found".format(script_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_OK, srv_com["result"].attrib["reply"]


class create_dir_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level2
        uuid = "55f35c53-3fb0-4dda-8264-ced2df694941"
        description = "create new directories"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        filesys_tools.create_dir(srv_com, self.log)


class remove_dir_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level2
        uuid = "e429d019-1822-4f98-8300-109842a6fe75"
        description = "remove directories"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        filesys_tools.remove_dir(srv_com, self.log)


class get_dir_tree_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level1
        uuid = "03ff9f6a-3e79-4569-b407-b1d193e58845"
        description = "list of directory tree"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        filesys_tools.get_dir_tree(srv_com, self.log)


class get_file_content_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level1
        uuid = "1f1f2993-20ef-4811-b752-a114fab3a75b"
        description = "read/return content of a file"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        filesys_tools.get_file_content(srv_com, self.log)


class set_file_content_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level2
        uuid = "7694dab7-d77e-48fd-bd96-0cbc0480b484"
        description = "write content to a file"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        filesys_tools.set_file_content(srv_com, self.log)


class check_mount_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "4537cc1f-00fa-433c-91ee-797363d12358"
        description = "check if a given mountpoint has the specified type"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("--type", "type", "nfs", "Mount Type"),
            hm_classes.MCParameter("", "arguments", "", "Mountpoint"),
        )

    def __call__(self, srv_com, cur_ns):
        if len(cur_ns.arguments) != 1:
            srv_com.set_result(
                "missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            path_name = cur_ns.arguments[0]
            _dict = {_entry[1]: _entry for _entry in [_line.strip().split() for _line in open("/etc/mtab", "r").readlines() if _line.strip()]}
            if path_name in _dict:
                srv_com["mpinfo"] = _dict[path_name]
            else:
                srv_com.set_result(
                    "path '{}' not found in mtab".format(path_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )

    def interpret(self, srv_com, cur_ns):
        mount_info = srv_com["*mpinfo"]
        # target_type
        _errors, _warnings = ([], [])
        t_type = cur_ns.type
        _ret_f = ["from {}".format(mount_info[0])]
        if mount_info[2] != t_type:
            _warnings.append("type differs: {} != {}".format(mount_info[2], t_type))
        else:
            _ret_f.append("type is {}".format(t_type))
        if _errors:
            ret_state = limits.mon_STATE_CRITICAL
            _ret_f.extend(_errors)
        elif _warnings:
            ret_state = limits.mon_STATE_WARNING
            _ret_f.extend(_warnings)
        else:
            ret_state = limits.mon_STATE_OK
        return ret_state, "mountpoint {}: {}".format(
            mount_info[1],
            ", ".join(_ret_f)
        )


class check_dir_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "9a3be3b0-d030-4f0c-86b0-9c1b2eadc615"
        description = "check availability of a given directory"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("", "arguments", "", "Mountpoint"),
        )

    def __call__(self, srv_com, cur_ns):
        if len(cur_ns.arguments) != 1:
            srv_com.set_result(
                "missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            dir_name = cur_ns.arguments[0]
            link_followed = False
            while os.path.islink(dir_name):
                link_followed = True
                dir_name = os.readlink(dir_name)
            if os.path.isdir(dir_name):
                f_stat = os.stat(dir_name)
                srv_com["result"].append(
                    srv_com.builder(
                        "dir_stat",
                        directory=dir_name,
                        local_time="{}".format(time.time()),
                        link_followed="1" if link_followed else "0",
                    )
                )
                srv_com["result:dir_result:stat"] = {key: getattr(stat, key) for key in dir(f_stat) if key.startswith("ST")}
            else:
                srv_com.set_result(
                    "directory {} not found".format(dir_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_OK, "dir {} exists".format(srv_com["result:dir_stat"].attrib["directory"])


class modules_fingerprint_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "2d9ae7a1-c37b-42ac-829c-eee5a3d84b28"
        description = "checksum/fingerprint of installed host monitoring modules"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        from initat.host_monitoring.modules import local_mc
        from initat.host_monitoring.hm_classes import HM_ALL_MODULES_KEY
        srv_com["checksum"] = local_mc.HM_MODULES_HEX_CHECKSUMS[HM_ALL_MODULES_KEY]

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_OK, srv_com["checksum"].text


class update_modules_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level2
        uuid = "da051ddb-a316-4db7-b23a-0eb68fdab161"
        description = "update/refresh installed host monitoring modules"
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        if "update_dict" not in srv_com:
            srv_com.set_result(
                "Missing update_dict",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            from initat.host_monitoring.modules import local_mc
            from initat.host_monitoring.hm_classes import HM_ALL_MODULES_KEY
            import pickle
            import bz2
            import binascii
            from threading import Thread

            new_modules_dict = srv_com["update_dict"].text.strip()
            new_modules_dict = binascii.a2b_base64(new_modules_dict)
            new_modules_dict = bz2.decompress(new_modules_dict)
            new_modules_dict = pickle.loads(new_modules_dict)

            modules_updated = 0

            for module_name in new_modules_dict.keys():
                path = os.path.normpath(os.path.join(local_mc.get_root_dir(), module_name))
                f = open(path, "wb")
                f.write(new_modules_dict[module_name])
                f.close()

                modules_updated += 1

            local_mc.reload_module_checksum()

            srv_com["update_result"] = "{} modules updated".format(modules_updated)
            srv_com["new_modules_fingerprint"] = local_mc.HM_MODULES_HEX_CHECKSUMS[HM_ALL_MODULES_KEY]

            def killme():
                time.sleep(1)
                os._exit(1)

            t = Thread(target=killme)
            t.start()

    def interpret(self, srv_com, cur_ns):
        if "new_modules_fingerprint" in srv_com:
            return limits.mon_STATE_OK, "{}, new_fingerprint: {}".format(srv_com["update_result"].text,
                                                                         srv_com["new_modules_fingerprint"].text)
        else:
            return limits.mon_STATE_OK, srv_com["update_result"].text


class full_update_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.WINDOWS
        required_access = HMAccessClassEnum.level2
        uuid = "5d67b3d3-7ded-4483-814d-8f6dcd3e10f8"
        description = "Perform a full update of the windows host monitoring software."
        create_mon_check_command = False

    def mc_init(self):
        self.update_progress = 0.0
        self.update_thread = None

    def __call__(self, srv_com, cur_ns):
        if self.update_thread:
            srv_com["update_status"] = self.update_progress
        else:
            import binascii
            import tarfile
            import lzma
            import io
            import shutil

            from threading import Thread

            update_file_data = srv_com["update_file_data"].text
            srv_com["update_file_data"] = ""
            update_file_data = binascii.a2b_base64(update_file_data)

            lzma_file = lzma.LZMAFile(filename=io.BytesIO(update_file_data))
            tar_file = tarfile.TarFile(fileobj=lzma_file)

            def update_func(**kwargs):
                config_files = {
                    "Lib\site-packages\opt\cluster\etc\.cluster_device_uuid": None,
                    "Lib\site-packages\opt\cluster\etc\cstores.d\client_config.xml": None,
                    "Lib\site-packages\opt\cluster\etc\cstores.d\icsw.device_config.xml": None,
                    "Lib\site-packages\opt\cluster\etc\cstores.d\icsw.hm.0mq-mapping_config.xml": None,
                    "Lib\site-packages\opt\cluster\etc\cstores.d\icsw.hm.machvector_config.xml": None
                }

                for config_file in config_files.keys():
                    with open(config_file, "rb") as f:
                        config_files[config_file] = f.read()

                shutil.rmtree(".", ignore_errors=True)
                for old_path in os.listdir("."):
                    # ignore log files
                    if old_path.startswith("log"):
                        continue

                    # ignore icsw_old files
                    _, ext = os.path.splitext(old_path)
                    if ext == ".icsw_old":
                        continue

                    idx = 0
                    while True:
                        new_path = "{}.{}.{}".format(old_path, idx, "icsw_old")
                        if not os.path.exists(new_path):
                            break
                        idx += 1

                    shutil.move(old_path, new_path)

                update_progress_obj = kwargs["update_progress_obj"]

                num_files = len(tar_file.getmembers())
                idx = 0
                for member in tar_file.getmembers():
                    idx += 1
                    tar_file.extract(member)

                    update_progress_obj.update_progress = (idx / num_files) * 100

                    print(update_progress_obj.update_progress)

                for config_file in config_files.keys():
                    with open(config_file, "wb") as f:
                        if config_files[config_file]:
                            f.write(bytes(config_files[config_file]))

                time.sleep(1)
                os._exit(1)

            srv_com["update_status"] = "started"

            self.update_thread = Thread(target=update_func, kwargs={"update_progress_obj": self})
            self.update_thread.start()


class platform_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "7f1499f8-33f0-40e5-8b07-b20f93e09acb"
        description = "platform type of this host_monitor ({}, {})".format(PlatformSystemTypeEnum.WINDOWS.name,
                                                                           PlatformSystemTypeEnum.LINUX.name)
        create_mon_check_command = False

    def __call__(self, srv_com, cur_ns):
        srv_com["platform"] = PLATFORM_SYSTEM_TYPE.value
        if PLATFORM_SYSTEM_TYPE == PlatformSystemTypeEnum.WINDOWS:
            if os.path.exists("hm_icsw_w32"):
                srv_com["platform_bits"] = "32"
            elif os.path.exists("hm_icsw_w64"):
                srv_com["platform_bits"] = "64"
        else:
            srv_com["platform_bits"] = "64"

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_OK, "Platform is {}".format(PlatformSystemTypeEnum(int(srv_com["platform"].text)).name)
