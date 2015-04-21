# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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

from initat.host_monitoring import filesys_tools
from initat.host_monitoring import limits, hm_classes
import commands
from initat.tools import logging_tools
import os
from initat.tools import process_tools
from initat.tools import server_command
import stat
import sys
import tempfile
import time


class _general(hm_classes.hm_module):
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


class check_file_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--mod", dest="mod_diff_time", type=int)
        self.parser.add_argument("--size", dest="min_file_size", type=int)
        self.parser.add_argument("--exclude-checkdate", dest="exclude_checkdate", type=str)

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

    def interpret_old(self, result, cur_ns):
        return self._interpret(hm_classes.net_to_sys(result[3:]), cur_ns)

    def _interpret(self, f_dict, cur_ns):
        ret_state = limits.nag_STATE_OK
        file_stat = f_dict["stat"]
        if type(file_stat) == dict:
            file_size = file_stat["st_size"]
            file_mtime = file_stat["st_mtime"]
        else:
            file_size = file_stat[stat.ST_SIZE]
            file_mtime = file_stat[stat.ST_MTIME]
        add_array = ["size %s" % (logging_tools.get_size_str(file_size))]
        act_time = time.localtime()
        act_time = (act_time.tm_wday + 1,
                    act_time.tm_hour,
                    act_time.tm_min)
        act_time = act_time[2] + 60 * (act_time[1] + 24 * act_time[0])
        in_exclude_range = False
        if cur_ns.exclude_checkdate:
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
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    add_array.append("changed %s ago > %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
                else:
                    add_array.append("changed %s ago < %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
        return ret_state, "file %s %s" % (f_dict["file"],
                                          ", ".join(add_array))


class resync_config_command(object):  # s.hmb_command):
    def __init__(self, **args):
        # hm_classes.hmb_command.__init__(self, "resync_config", **args)
        self.help_str = "call /root/bin/resync_config.sh (if present)"
        self.timeout = 30
        self.net_only = True

    def server_call(self, cm):
        msock = None
        return self.module_info.start_resync()
        boot_server_name = "/etc/motherserver"
        mount_options = "-o noacl,udp"
        try:
            boot_server = file(boot_server_name, "r").read().split("\n")[0].strip()
        except IOError:
            return "error no motherserver defined in %s" % (boot_server_name)
        # call get_target_state
        stat, com_out = msock.single_tcp_connection((boot_server, 8006, "get_target_sn"), None, 30, 1)
        if stat:
            self.log("Something bad happend while sending get_target_sn to config_server (%d):" % (stat))
            for l in com_out.split("\n"):
                self.log(" - %s" % (l.rstrip()))
        else:
            com_parts = com_out.strip().split()
            target_state, prod_net, dev_name = (com_parts[1], com_parts[2], com_parts[5])
            self.log("Target state is '%s', target network is '%s', device_name is '%s'" % (target_state, prod_net, dev_name))
            # call create_config
            stat, com_out = msock.single_tcp_connection((boot_server, 8006, "create_config"), None, 30, 1)
            if stat:
                self.log("Something bad happend while sending create_config to config_server (%d):" % (stat))
                for l in com_out.split("\n"):
                    self.log(" - %s" % (l.rstrip()))
            else:
                time.sleep(2)
                while 1:
                    stat, com_out = msock.single_tcp_connection((boot_server, 8006, "ack_config"), None, 30, 1)
                    if stat:
                        self.log("Something bad happend while sending create_config to config_server (%d):" % (stat))
                        for l in com_out.split("\n"):
                            self.log(" - %s" % (l.rstrip()))
                        break
                    if com_out.startswith("wait"):
                        time.sleep(5)
                    else:
                        break
                if not stat:
                    self.log("Config is ready")
                    temp_dir = tempfile.mkdtemp("rc", ".rc_")
                    self.log("trying to mount config for device %s from %s with options %s to %s" % (dev_name, boot_server, mount_options, temp_dir))
                    mount_com = "mount -o noacl %s:/tftpboot/config/%s %s" % (boot_server, dev_name, temp_dir)
                    umount_com = "umount %s" % (temp_dir)
                    stat, com_out = commands.getstatusoutput(mount_com)
                    if stat:
                        self.log("Something bad happend while trying to do '%s' (%d):" % (mount_com, stat))
                        for l in com_out.split("\n"):
                            self.log(" - %s" % (l.rstrip()))
                        ret_str = "error mounting (%s)" % (mount_com)
                    else:
                        self.log("Successfully mounted config")
                        try:
                            old_config_files = [x.strip() for x in file("%s/.config_files" % (temp_dir), "r").read().split("\n")]
                        except IOError:
                            self.log("No old config-files found")
                        else:
                            self.log("Found %s, deleting them now ..." % (logging_tools.get_plural("file", len(old_config_files))))
                            num_del_ok, error_dels = (0, [])
                            for f_name in old_config_files:
                                try:
                                    os.unlink("%s+" % (f_name))
                                except (IOError, OSError):
                                    error_dels += [f_name]
                                else:
                                    num_del_ok += 1
                            self.log("successfully deleted %s, %s: %s" % (logging_tools.get_plural("file", num_del_ok),
                                                                          logging_tools.get_plural("error file", len(error_dels)),
                                                                          ", ".join(error_dels)))
                            os.unlink("%s/.config_files" % (temp_dir))
                        generated, error_objs = ([], [])
                        if os.path.isfile("%s/config_dirs_%s" % (temp_dir, prod_net)):
                            self.log("Generating directories ...")
                            for new_dir in [x.strip() for x in file("%s/config_dirs_%s" % (temp_dir, prod_net), "r").read().split("\n") if x.strip()]:
                                dir_num, dir_uid, dir_gid, dir_mode, dir_name = new_dir.split()
                                dir_uid, dir_gid, int_dir_mode = (int(dir_uid), int(dir_gid), int(dir_mode, 8))
                                try:
                                    os.makedirs(dir_name)
                                    os.chmod(dir_name, int_dir_mode)
                                    os.chown(dir_name, dir_uid, dir_gid)
                                except OSError:
                                    self.log(" * some error occured while trying to generate %s (uid %d, gid %d, mode %s): %s" % (dir_name, dir_uid, dir_gid, dir_mode, sys.exc_info()[1]))
                                else:
                                    self.log(" - generated dir %s (uid %d, gid %d, mode %s)" % (dir_name, dir_uid, dir_gid, dir_mode))
                        if os.path.isfile("%s/config_files_%s" % (temp_dir, prod_net)):
                            self.log("Generating files ...")
                            for new_file in [x.strip() for x in file("%s/config_files_%s" % (temp_dir, prod_net), "r").read().split("\n") if x.strip()]:
                                file_num, file_uid, file_gid, file_mode, file_name = new_file.split()
                                file_num, file_uid, file_gid, int_file_mode = (int(file_num), int(file_uid), int(file_gid), int(file_mode, 8))
                                file_dir = os.path.dirname(file_name)
                                if not os.path.isdir(file_dir):
                                    try:
                                        os.makedirs(file_dir)
                                    except IOError:
                                        self.log(" * error creating directory %s for file %s: %s" % (file_dir, file_name, sys.exc_info()[1]))
                                    else:
                                        self.log(" - created directory %s for file %s" % (file_dir, file_name))
                                if os.path.isdir(file_dir):
                                    try:
                                        file(file_name, "w").write(file("%s/content_%s/%d" % (temp_dir, prod_net, file_num), "r").read())
                                        os.chmod(file_name, int_file_mode)
                                        os.chown(file_name, file_uid, file_gid)
                                    except:
                                        self.log(" * some error occured while trying to generate %s (uid %d, gid %d, mode %s): %s" % (file_name, file_uid, file_gid, file_mode, sys.exc_info()[1]))
                                        error_objs.append(file_name)
                                    else:
                                        self.log(" - generated file %s (uid %d, gid %d, mode %s)" % (file_name, file_uid, file_gid, file_mode))
                                        generated.append(file_name)
                                else:
                                    error_objs.append(file_name)
                        if os.path.isfile("%s/config_links_%s" % (temp_dir, prod_net)):
                            self.log("Generating links ...")
                            for new_link in [x.strip() for x in file("%s/config_links_%s" % (temp_dir, prod_net), "r").read().split("\n") if x.strip()]:
                                link_dest, link_src = new_link.split()
                                if os.path.islink(link_src):
                                    try:
                                        os.unlink(link_src)
                                    except IOError:
                                        self.log(" * error removing old link source %s" % (link_src))
                                    else:
                                        self.log(" - removed old link source %s" % (link_src))
                                if not os.path.isfile(link_src) and not os.path.islink(link_src):
                                    try:
                                        os.symlink(link_dest, link_src)
                                    except IOError:
                                        self.log(" * error generating link '%s' pointing to '%s'" % (link_src, link_dest))
                                        error_objs.append(link_src)
                                    else:
                                        self.log(" - generated link '%s' pointing to '%s'" % (link_src, link_dest))
                                        generated.append(link_src)
                                else:
                                    self.log(" * error old link source %s still present" % (link_src))
                                    error_objs.append(link_src)
                        self.log("%s generated successfully, %s" % (logging_tools.get_plural("object", len(generated)),
                                                                    logging_tools.get_plural("problem object", len(error_objs))))
                        stat, com_out = commands.getstatusoutput(umount_com)
                        if stat:
                            self.log("Something bad happend while trying to do '%s' (%d):" % (mount_com, stat))
                            for l in com_out.split("\n"):
                                self.log(" - %s" % (l.rstrip()))
                            ret_str = "error umounting (%s)" % (umount_com)
                        else:
                            self.log("Successfully unmounted config")
                            if error_objs:
                                ret_str = "warn %s with problems, %d ok" % (logging_tools.get_plural("object", len(error_objs)), len(generated))
                            else:
                                ret_str = "ok %s generated" % (logging_tools.get_plural("object", len(generated)))
        return ret_str

    def client_call(self, result, parsed_coms):
        if result.startswith("error"):
            return limits.nag_STATE_CRITICAL, result
        else:
            return limits.nag_STATE_OK, result


class call_script_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
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
            while "arguments:arg%d" % (len(args) + 1) in srv_com:
                args.append(srv_com["arguments:arg%d" % (len(args) + 1)].text)
            if os.path.isfile(script_name):
                if cur_ns.time:
                    cur_ns.use_at = True
                info_str = "Starting script %s with %s: %s" % (
                    script_name,
                    logging_tools.get_plural("argument", len(args)),
                    " ".join(args))
                if cur_ns.use_at:
                    info_str = "%s after %s" % (
                        info_str,
                        logging_tools.get_plural("minute", cur_ns.time))
                self.log(info_str)
                if cur_ns.use_at:
                    c_stat, log_lines = process_tools.submit_at_command(
                        " ".join([script_name] + args),
                        cur_ns.time)
                    ipl = "\n".join(log_lines)
                else:
                    c_stat, ipl = commands.getstatusoutput(
                        " ".join([script_name] + args))
                    log_lines = ipl.split("\n")
                self.log(" - gave stat %d (%s):" % (c_stat,
                                                    logging_tools.get_plural("log line", len(log_lines))))
                for line in map(lambda s_line: s_line.strip(), log_lines):
                    self.log("   - %s" % (line))
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
        return limits.nag_STATE_OK, srv_com["result"].attrib["reply"]


# class create_file(object):  # hm_classes.hmb_command):
#     def __init__(self, **args):
#         hm_classes.hmb_command.__init__(self, "create_file", **args)
#         self.help_str = "creates a (preferable small) file"
#         self.short_client_info = "[KEY:value] file content"
#
#     def server_call(self, cm):
#         if len(cm) < 2:
#             return "error need at least filename and content"
#         file_content = cm.pop()
#         file_name = cm.pop()
#         if not file_name.startswith("/"):
#             return "error file_name has to start with '/'"
#         dir_name, file_name = (os.path.dirname(file_name),
#                                os.path.basename(file_name))
#         if not os.path.isdir(dir_name):
#             return "error directory '%s' does not exist" % (dir_name)
#
#         file_dict = {"uid"         : 0,
#                      "gid"         : 0,
#                      "overwrite"   : False,
#                      "add_newline" : False}
#         # parse keys
#         for key in cm:
#             if key.count(":"):
#                 key, value = key.split(":", 1)
#             else:
#                 value = True
#             if key not in file_dict:
#                 return "error key '%s' not known (has to be one of: %s)" % (key,
#                                                                             ", ".join(sorted(file_dict.keys())))
#             orig_value = file_dict[key]
#             try:
#                 if type(orig_value) == type(True):
#                     dest_type = "bool"
#                     value = bool(value)
#                 elif type(orig_value) == type(0):
#                     dest_type = "int"
#                     value = int(value)
#                 else:
#                     dest_type = "string"
#             except:
#                 return "error casting value '%s' (type %s) of key %s" % (str(value),
#                                                                          dest_type,
#                                                                          key)
#             file_dict[key] = value
#         full_name = os.path.join(dir_name, file_name)
#         if os.path.exists(full_name) and not file_dict["overwrite"]:
#             return "error file '%s' already exists" % (full_name)
#         self.log("trying to create file '%s' (content is '%s'), dict has %s:" % (full_name,
#                                                                                  file_content,
#                                                                                  logging_tools.get_plural("key", len(file_dict.keys()))))
#         for key, entry in file_dict.iteritems():
#             self.log(" - %-20s: %s" % (key, str(entry)))
#         try:
#             file(full_name, "w").write("%s%s" % (file_content,
#                                                  "\n" if file_dict["add_newline"] else ""))
#         except:
#             err_str = "error creating file '%s': %s" % (full_name,
#                                                         process_tools.get_except_info())
#             self.log(err_str, logging_tools.LOG_LEVEL_ERROR)
#             return err_str
#         try:
#             os.chown(full_name, file_dict["uid"], file_dict["gid"])
#         except:
#             pass
#         return "ok created file '%s'" % (full_name)
#     def client_call(self, result, parsed_coms):
#         if result.startswith("error"):
#             return limits.nag_STATE_CRITICAL, result
#         else:
#             return limits.nag_STATE_OK, result


class create_dir_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.create_dir(srv_com, self.log)


class remove_dir_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.remove_dir(srv_com, self.log)


class get_dir_tree_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.get_dir_tree(srv_com, self.log)


class get_file_content_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.get_file_content(srv_com, self.log)


class set_file_content_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.set_file_content(srv_com, self.log)


class check_mount_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--type", default="nfs", type=str)

    def __call__(self, srv_com, cur_ns):
        if len(cur_ns.arguments) != 1:
            srv_com.set_result(
                "missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            path_name = cur_ns.arguments[0]
            _dict = {_entry[1]: _entry for _entry in [_line.strip().split() for _line in file("/etc/mtab", "r").readlines() if _line.strip()]}
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
            ret_state = limits.nag_STATE_CRITICAL
            _ret_f.extend(_errors)
        elif _warnings:
            ret_state = limits.nag_STATE_WARNING
            _ret_f.extend(_warnings)
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, "mountpoint {}: {}".format(
            mount_info[1],
            ", ".join(_ret_f)
        )


class check_dir_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

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
        return limits.nag_STATE_OK, "dir {} exists".format(srv_com["result:dir_stat"].attrib["directory"])
