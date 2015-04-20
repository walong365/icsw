#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2010,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of init-license-tools
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
""" python interface to emulate a loadsensor for SGE """

import logging_tools
import os
import sge_license_tools
import stat
import sys
import time
import zmq


class error(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class term_error(error):
    def __init__(self):
        pass


class alarm_error(error):
    def __init__(self):
        pass


class stop_error(error):
    def __init__(self):
        pass


class int_error(error):
    def __init__(self):
        pass


def raw_read(fd):
    ret_str = ""
    while True:
        in_byte = os.read(fd, 1)
        if len(in_byte):
            if ord(in_byte) == 10:
                break
            ret_str = "{}{}".format(ret_str, in_byte)
    return ret_str


def parse_actual_license_usage(log_template, actual_licenses, act_conf, lc_dict):
    # build different license-server calls
    # see license.py in rms-server
    all_server_addrs = set(
        [
            "{:d}@{}".format(act_lic.get_port(), act_lic.get_host()) for act_lic in actual_licenses.values() if act_lic.license_type == "simple"
        ]
    )
    # print "asa:", all_server_addrs
    q_s_time = time.time()
    for server_addr in all_server_addrs:
        if server_addr not in lc_dict:
            lc_dict[server_addr] = sge_license_tools.license_check(
                lmutil_path=os.path.join(
                    act_conf["LMUTIL_PATH"]
                ),
                port=int(server_addr.split("@")[0]),
                server=server_addr.split("@")[1],
                log_com=log_template.log)
        srv_result = lc_dict[server_addr].check()
    q_e_time = time.time()
    log_template.info(
        "{} to query, took {}: {}".format(
            logging_tools.get_plural("license server", len(all_server_addrs)),
            logging_tools.get_diff_time_str(q_e_time - q_s_time),
            ", ".join(all_server_addrs)
        )
    )
    return srv_result


def build_sge_report_lines(log_template, configured_lics, actual_lics, cur_used):
    lines = ["start"]
    rep_dict = {
        "lics_in_use": [],
        "simple_lics": 0,
        "complex_lics": 0
    }
    for configured_lic in configured_lics:
        act_lic = actual_lics[configured_lic]
        free_lics = act_lic.free
        if act_lic.license_type == "simple":
            rep_dict["simple_lics"] += 1
        else:
            rep_dict["complex_lics"] += 1
        if free_lics != act_lic.total:
            rep_dict["lics_in_use"].append(configured_lic)
        if configured_lic not in cur_used or act_lic.used != cur_used[configured_lic]:
            log_template.info(
                "reporting {:d} free of {:d} for {}".format(
                    free_lics,
                    act_lic.total,
                    configured_lic)
                )
        lines.append("global:{}:{:d}".format(configured_lic, free_lics))
    lines.append("end")
    return lines, rep_dict


def main():
    # change IO-descriptors
    zmq_context = zmq.Context()
    log_template = logging_tools.get_logger(
        "loadsensor",
        "uds:/var/lib/logging-server/py_log",
        init_logger=True,
        zmq=True,
        context=zmq_context,
    )
    base_dir = "/etc/sysconfig/licenses"
    my_pid = os.getpid()
    sge_dict = sge_license_tools.get_sge_environment()
    log_template.info("starting for pid {:d}, base_dir is {}".format(my_pid, base_dir))
    log_template.info(sge_license_tools.get_sge_log_line(sge_dict))
    _act_site_file = sge_license_tools.text_file(
        os.path.join(base_dir, sge_license_tools.ACT_SITE_NAME),
    )
    act_site = _act_site_file.lines
    if not act_site:
        log_template.error("Actual site not defined, exiting...")
        sys.exit(1)
    act_site = act_site[0]

    act_conf = sge_license_tools.text_file(
        sge_license_tools.get_site_config_file_name(base_dir, act_site),
    ).dict
    log_template.info("read config for actual site '%s'" % (act_site))
    log_template.info("keys in config: {:d}".format(len(act_conf.keys())))
    for key, value in act_conf.iteritems():
        log_template.info(" - %-20s : %s" % (key, value))
    call_num = 0
    io_in_fd = sys.stdin.fileno()
    io_out_fd = sys.stdout.fileno()
    log_template.info("starting up, input handle is {:d}, output handle is {:d}".format(io_in_fd, io_out_fd))
    actual_licenses, lic_read_time = ([], time.time())
    # read node_grouping file
    # ng_dict = sge_license_tools.read_ng_file(log_template)
    # license_check_dict
    lc_dict = {}
    # vector socket
    try:
        while True:
            in_lines = raw_read(io_in_fd)
            call_num += 1
            if in_lines == "quit":
                log_template.warning("call #{:d}, received '{}'".format(call_num, in_lines))
                break
            else:
                log_template.info("starting reporting load values (call #%d)" % (call_num))
                start_time = time.time()
                site_lic_file_name = sge_license_tools.get_site_license_file_name(base_dir, act_site)
                if os.path.isfile(site_lic_file_name):
                    file_time = os.stat(site_lic_file_name)[stat.ST_MTIME]
                    if not actual_licenses or file_time > lic_read_time:
                        log_template.info("reading license_file for site %s" % (act_site))
                        actual_licenses = sge_license_tools.parse_license_lines(
                            sge_license_tools.text_file(
                                sge_license_tools.get_site_license_file_name(base_dir, act_site),
                                ignore_missing=True,
                                strip_empty=False,
                                strip_hash=False,
                            ).lines,
                            act_site
                        )
                        lic_read_time = file_time
                    if not sge_license_tools.handle_license_policy(base_dir):
                        cur_used = {_key: _value.used for _key, _value in actual_licenses.iteritems()}
                        srv_result = parse_actual_license_usage(log_template, actual_licenses, act_conf, lc_dict)
                        sge_license_tools.update_usage(actual_licenses, srv_result)
                        # [cur_lic.handle_node_grouping() for cur_lic in actual_licenses.itervalues()]
                        for log_line, log_level in sge_license_tools.handle_complex_licenses(actual_licenses):
                            log_template.log(log_line, log_level)
                        sge_license_tools.calculate_usage(actual_licenses)
                        configured_licenses = [_key for _key, _value in actual_licenses.iteritems() if _value.is_used]
                        sge_lines, rep_dict = build_sge_report_lines(log_template, configured_licenses, actual_licenses, cur_used)
                    else:
                        log_template.log("licenses are controlled via rms-server, reporting nothing to SGE", logging_tools.LOG_LEVEL_WARN)
                        sge_lines, rep_dict = ([], None)
                    # report to SGE
                    print "\n".join(sge_lines)
                    end_time = time.time()
                    if rep_dict:
                        log_template.info(
                            "{} defined, {:d} configured, {:d} in use{}, ({:d} simple, {:d} complex), took {}".format(
                                logging_tools.get_plural("license", len(actual_licenses.keys())),
                                len(configured_licenses),
                                len(rep_dict["lics_in_use"]),
                                rep_dict["lics_in_use"] and " ({})".format(", ".join(sorted(rep_dict["lics_in_use"]))) or "",
                                rep_dict["simple_lics"],
                                rep_dict["complex_lics"],
                                logging_tools.get_diff_time_str(end_time - start_time)
                            )
                        )
                else:
                    log_template.warning("site_file for site {} not readable (base_dir is {})".format(act_site, base_dir))
    except KeyboardInterrupt:
        log_template.warning("proc {:d}: got KeyboardInterrupt, exiting ...".format(my_pid))
    except term_error:
        log_template.warning("proc %d: got term-signal, exiting ..." % (my_pid))
    except stop_error:
        log_template.warning("proc %d: got stop-signal, exiting ..." % (my_pid))
    except int_error:
        log_template.warning("proc %d: got int-signal, exiting ..." % (my_pid))
    log_template.close()
    zmq_context.term()
    sys.exit(0)

if __name__ == "__main__":
    main()
