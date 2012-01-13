#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# This file is part of rms-tools
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
""" qsub wrapper """

import sys
import commands
import os
import os.path
import logging_tools
import time
import net_tools
import server_command
import process_tools

SERVER_PORT = 8009

def verb_log(what):
    print " v %s" % (what)
    
def get_sge_server():
    if os.environ.has_key("SGE_SERVER"):
        sge_server = os.environ["SGE_SERVER"]
    elif os.path.isfile("/etc/sge_server"):
        try:
            sge_server = file("/etc/sge_server", "r").read().split("\n")[0].strip()
        except:
            sge_server = "localhost"
    else:
        sge_server = "localhost"
    return sge_server

def connect(server, port, com_str, timeout):
    s_time = time.time()
    errnum, data = net_tools.single_connection(timeout=timeout, host=server, port=port, command=com_str).iterate()
    e_time = time.time()
    diff_time = e_time - s_time
    if errnum:
        ret_str = "error Socket error: %s (%d)" % (data, errnum)
    else:
        ret_str = data
    return ret_str, diff_time
    
def call_command(what):
    s_time = time.time()
    stat, ret_str = commands.getstatusoutput(what)
    e_time = time.time()
    return stat, ret_str, e_time - s_time

def get_sge_dict():
    sge_dict = {}
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"), ("SGE_CELL", "/etc/sge_cell")]:
        if not os.environ.has_key(v_name):
            if os.path.isfile(v_src):
                os.environ[v_name] = file(v_src, "r").read().strip().split("\n")[0]
            else:
                print "error Cannot assign environment-variable '%s', exiting..." % (v_name)
                sys.exit(1)
        sge_dict[v_name] = os.environ[v_name]
    return sge_dict
    
def main():
    start_time = time.time()
    verbose = os.environ.get("QSUB_VERBOSE", False)
    sge_dict = get_sge_dict()
    if os.path.isfile("/etc/sge_qsub_not_strict"):
        strict_mode = False
    else:
        strict_mode = True
    # drop nasty -clear and parse timeout-value
    args = sys.argv[1:]
    timeout = 10.0
    new_args = []
    while args:
        act_arg = args.pop(0)
        # drop nasty clear
        if act_arg in ["-clear"]:
            pass
        elif act_arg in ["--verbose"]:
            verbose = True
        elif act_arg == "-T":
            if args:
                try:
                    timeout = max(0.4, abs(float(args.pop(0))))
                except:
                    print "error cannot parse timeout"
                    sys.exit(1)
            else:
                print "error no argument given for -T option"
                sys.exit(1)
        else:
            new_args.append(act_arg)
    args = " ".join(new_args)
    if verbose:
        verb_log("argument list is '%s'" % (args))
    # determine architecture
    seg_arch = ""
    if sys.argv[0].startswith(sge_dict["SGE_ROOT"]):
        root_parts = [p for p in sge_dict["SGE_ROOT"].split("/") if p]
        argv_parts = [p for p in sys.argv[0].split("/") if p]
        while root_parts and root_parts[0] == argv_parts[0]:
            root_parts.pop(0)
            argv_parts.pop(0)
        if not root_parts and argv_parts:
            if argv_parts[0] == "bin" and len(argv_parts) > 1:
                sge_arch, sge_arch_source = (argv_parts[1], "sys.argv")
    if not sge_arch:
        # determine architecture via call to util/arch
        stat, sge_arch, arch_time = call_command("/%s/util/arch" % (sge_dict["SGE_ROOT"]))
        if stat:
            print "error Cannot evaluate ARCH (%s)" % (sge_arch)
            sys.exit(1)
        else:
            sge_arch_source = "util/arch"
    if verbose:
        verb_log("architecture is %s (via %s, took %s)" % (sge_arch,
                                                           sge_arch_source,
                                                           logging_tools.get_diff_time_str(arch_time)))
    stat, out, verify_time = call_command("/%s/bin/%s/.qsub -verify %s" % (sge_dict["SGE_ROOT"], sge_arch, args))
    if verbose:
        verb_log("verify-call took %s (stat is %d)" % (logging_tools.get_diff_time_str(verify_time),
                                                       stat))
    out_lines = out.split("\n")
    do_it = False
    # check for submitting of binaries
    elf_lines = [y for y in [x.strip() for x in out_lines if x.strip()] if y.startswith("\x7fELF")]
    if elf_lines:
        print " e You are not allowed to submit binaries"
        stat = -1
    else:
        if stat:
            print "Verifying your request resulted in an error (%d):" % (stat)
            print "\n".join(["e %s" % (line) for line in out_lines])
        else:
            # check for warnings
            warn_lines = [x for x in out_lines if x.startswith("warning:")]
            if len(warn_lines):
                print "Warnings:"
                print "\n".join(["w %s" % (line) for line in warn_lines])
            res_str, diff_time = connect(get_sge_server(), SERVER_PORT, server_command.server_command(command="check_submit_job",
                                                                                                      option_dict={"uid"       : os.getuid(),
                                                                                                                   "gid"       : os.getgid(),
                                                                                                                   "out_lines" : out_lines}),
                                         timeout)
            job_id = None
            try:
                srv_reply = server_command.server_reply(res_str)
            except:
                if strict_mode:
                    print " e Error connecting to sge-server %s (port %d)" % (get_sge_server(),
                                                                              SERVER_PORT)
                    print " e %s" % (res_str)
                    stat, do_it = (-1, False)
                else:
                    do_it = True
            else:
                if srv_reply.get_state() == server_command.SRV_REPLY_STATE_OK:
                    option_dict = srv_reply.get_option_dict()
                    opt_keys = option_dict.keys()
                    opt_keys.sort()
                    if verbose:
                        verb_log("result from check (took %s) has %s: %s" % (logging_tools.get_diff_time_str(diff_time),
                                                                             logging_tools.get_plural("key", len(opt_keys)),
                                                                             ", ".join(["%s" % (str(x)) for x in opt_keys])))
                    do_it = option_dict["submit_job"]
                    args = ("%s %s" % (args, option_dict.get("append_arg", ""))).strip()
                    temp_job_id = option_dict.get("temporary_id", None)
                    out_list = option_dict.get("out_list", [])
                    if out_list:
                        print "\n".join(["%s %s" % (stat, out_str) for stat, out_str in out_list])
                else:
                    if strict_mode:
                        print " e received an error from sge-server %s (port %d)" % (get_sge_server(),
                                                                                     SERVER_PORT)
                        print " e %s" % (process_tools.get_except_info())
                        print " e %s" % (srv_reply.get_result())
                        stat, do_it = (-1, False)
                    else:
                        do_it = True
            if do_it:
                if verbose:
                    verb_log("submitting job to SGE")
                stat, out, submit_time = call_command("/%s/bin/%s/.qsub %s" % (sge_dict["SGE_ROOT"], sge_arch, args))
                if not stat:
                    if temp_job_id:
                        if verbose:
                            verb_log("submit successful (took %s), transfering job_id '%s' to sge-server" % (logging_tools.get_diff_time_str(submit_time),
                                                                                                             temp_job_id))
                        ret_str, diff_time = connect(get_sge_server(), SERVER_PORT, server_command.server_command(command="got_final_job_id",
                                                                                                                  option_dict={"job_id"    : temp_job_id,
                                                                                                                               "out_lines" : [x.strip() for x in out.split("\n")]}),
                                                     timeout)
                        try:
                            srv_reply = server_command.server_reply(ret_str)
                        except:
                            print " e Error connecting to sge-server %s (port %d)" % (get_sge_server(),
                                                                                      SERVER_PORT)
                            print " e %s" % (process_tools.get_except_info())
                            print " e %s" % (ret_str)
                        else:
                            if verbose:
                                verb_log(" ... done in %s, result is: %s" % (logging_tools.get_diff_time_str(diff_time),
                                                                             srv_reply.get_result()))
                    else:
                        if verbose:
                            verb_log("no temporary job_id, strange...")
                print "%s (%s)" % (out, logging_tools.get_diff_time_str(time.time() - start_time))
    end_time = time.time()
    if verbose:
        verb_log("scripted needed %s to execute" % (logging_tools.get_diff_time_str(end_time - start_time)))
    sys.exit(stat)

if __name__ == "__main__":
    main()
