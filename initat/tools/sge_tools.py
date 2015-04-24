# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" tools for the SGE """

from lxml import etree  # @UnresolvedImport
import argparse
import commands
import copy
import datetime
import os
import re
import stat
import json
import time
import uuid

from lxml.builder import E  # @UnresolvedImport
from initat.tools import logging_tools, process_tools, server_command
import zmq  # @UnresolvedImport

try:
    import memcache
except:
    memcache = None


def get_empty_job_options(**kwargs):
    options = argparse.Namespace()
    options.users = set()
    options.complexes = set()
    options.show_memory = False
    options.suppress_times = False
    options.suppress_nodelist = False
    options.compress_nodelist = True
    options.only_valid_waiting = False
    options.long_status = False
    options.show_stdoutstderr = True
    for key, value in kwargs.iteritems():
        if not hasattr(options, key):
            print("wrong key in get_empty_node_options: {}".format(key))
        else:
            setattr(options, key, value)
    return options


def get_empty_node_options(**kwargs):
    options = argparse.Namespace()
    options.users = set()
    options.complexes = set()
    options.node_sort = False
    options.suppress_empty = False
    options.show_nonstd = True
    options.show_seq = False
    options.suppress_status = False
    options.long_status = False
    options.show_type = False
    options.show_long_type = False
    options.show_complexes = True
    options.show_pe = True
    options.show_memory = False
    options.show_acl = False
    options.merge_node_queue = False
    for key, value in kwargs.iteritems():
        if not hasattr(options, key):
            print("wrong key in get_empty_node_options: {}".format(key))
        else:
            setattr(options, key, value)
    return options


def compress_list(ql, queues=None, postfix=""):
    # node prefix, postfix, start_string, end_string
    # not exactly the same as the version in logging_tools
    def add_p(np, ap, s_str, e_str):
        if s_str == e_str:
            return "{}{}{}{}".format(np, s_str, ap, postfix)
        elif int(s_str) + 1 == int(e_str):
            return "{}{}{}-{}{}".format(np, s_str, ap, e_str, ap)
        else:
            return "{}{}{}-{}{}".format(np, s_str, ap, e_str, ap)
    if not queues or queues == "-":
        q_list = []
    else:
        q_list = [cur_q.strip() for cur_q in queues.split(",")]
    pf_re = re.compile("^(?P<pef>\D+)(?P<num>\d*)(?P<pof>.*)$")
    pf_q_re = re.compile("^(?P<pef>.+@\D+)(?P<num>\d*)(?P<pof>.*)$")
    ql.sort()
    nc_dict = {}
    for q_name in ql:
        if q_name.count("@"):
            pf_m = pf_q_re.match(q_name)
        else:
            pf_m = pf_re.match(q_name)
        if pf_m is None:
            # no match, handle special machine names
            i_idx, idx = (0, "")
            pef, pof = (q_name, "")
        else:
            pef = pf_m.group("pef")
            if len(q_list) == 1 and pef.startswith("{}@".format(q_list[0])):
                pef = pef[len(q_list[0]) + 1:]
            idx = pf_m.group("num")
            pof = pf_m.group("pof").split(".")[0]
            if idx:
                i_idx = int(idx)
            else:
                i_idx = 0
        nc_dict.setdefault(pef, {}).setdefault(pof, {})[i_idx] = idx
    nc_a = []
    for pef in nc_dict.keys():
        for pof, act_l in nc_dict[pef].iteritems():
            s_idx = None
            for e_idx in sorted(act_l.keys()):
                e_num = act_l[e_idx]
                if s_idx is None:
                    s_idx, s_num = (e_idx, e_num)
                    l_num, l_idx = (s_num, s_idx)
                else:
                    if e_idx == l_idx + 1:
                        pass
                    else:
                        nc_a.append(add_p(pef, pof, s_num, l_num))
                        s_num, s_idx = (e_num, e_idx)
                    l_num, l_idx = (e_num, e_idx)
            if pef:
                nc_a.append(add_p(pef, pof, s_num, l_num))
    return ",".join(nc_a)


def str_to_sec(in_str):
    if in_str == "---":
        sec = in_str
    else:
        is_f = [int(x) for x in in_str.split()[0].split(":")]
        sec, mult = (0, 0)
        while len(is_f):
            sec = sec * mult + is_f.pop(0)
            if len(is_f) > 2:
                mult = 24
            else:
                mult = 60
    return sec


def sec_to_str(in_sec):
    if in_sec == "---":
        out_f = "---"
    else:
        if in_sec >= 0:
            diff_d = int(in_sec / (3600 * 24))
            dt = in_sec - 3600 * 24 * diff_d
            diff_h = int(dt / 3600)
            dt -= 3600 * diff_h
            diff_m = int(dt / 60)
            dt -= diff_m * 60
            # if diff_d:
            out_f = "{}{:02d}:{:02d}:{:02d}".format(
                diff_d and "{:2d}:".format(diff_d) or "",
                diff_h,
                diff_m,
                dt)
        else:
            out_f = "????"
    return out_f


class sge_info(object):
    def __init__(self, **kwargs):
        """ arguments :
        verbose            : enables verbose messages
        sge_dict           : env_dict for accessing the SGE direct via calling commands
        log_command        : how to handle log events (defaults to syslog)
        is_active          : flag, if set to false no direct calls to the SGE will be made
        run_initial_update : flag, if set to false no initial update_call will be made
        init_dicts         : default values for the various dicts (for webfrontend)
        ignore_dicts       : dicts to ignore
        server             : name of server to connect, defaults to localhost
        server_port        : port of server to connect, defaults to 8009
        source             : source mode, can be
         - local (always call sge-commands)
         - server (always call server)
        persistent_socket  : use a persistent 0MQ socket
        """
        self.__verbose = kwargs.pop("verbose", 0)
        self.__sge_dict = kwargs.pop("sge_dict", {})
        self.__log_com = kwargs.pop("log_command", kwargs.get("log_com", None))
        # active: has sge_dict and can make calls to the system
        self.__is_active = kwargs.pop("is_active", True)
        self.__server = kwargs.pop("server", "localhost")
        self.__server_port = kwargs.pop("server_port", 8009)
        self.__source = kwargs.pop("source", "local")
        self.__persistent_socket = kwargs.pop("persistent_socket", True)
        _riu = kwargs.pop("run_initial_update", True)
        if kwargs:
            print("*** not all kwargs parsed for sge_info.__init__(): {}".format(", ".join(kwargs.keys())))
        if self.__source not in ["server", "local"]:
            print("*** wrong source set {}, using local".format(self.__source))
            self.__source = "local"
        self.__0mq_context, self.__0mq_socket = (None, None)
        self.__uuid = uuid.uuid4()
        # update counter
        self.__counter = 0
        # empty lut
        self.__job_lut = {}
        self._init_cache()
        # key : (relevance, call)
        setup_dict = {
            "pe": (0, self._check_pe_dict),
            "hostgroup": (1, self._check_hostgroup_dict),
            "queueconf": (2, self._check_queueconf_dict),
            "complexes": (3, self._check_complexes_dict),
            "qhost": (4, self._check_qhost_dict),
            "qstat": (5, self._check_qstat_dict)
        }
        self.__valid_dicts = [
            v_key for _bla, v_key in sorted(
                [
                    (rel, key) for key, (rel, _s_call) in setup_dict.iteritems()
                ]
            ) if v_key not in kwargs.get("ignore_dicts", [])
        ]
        self.__update_call_dict = {
            key: s_call for key, (rel, s_call) in setup_dict.iteritems()
        }
        self.__timeout_dicts = {
            key: {
                "hostgroup": 300,
                "qstat": 2,
                "qhost": 2,
            }.get(key, 120) for key in self.__valid_dicts
        }
        if self.__is_active:
            self._sanitize_sge_dict()
        # dicts for running / waiting job additional infos (via qstat -j )
        self.__run_job_dict = {}
        self.__wait_job_dict = {}
        self._init_update()
        if _riu and self.__is_active:
            self.update()

    def __del__(self):
        if self.__0mq_socket:
            self.__0mq_socket.close()
        if self.__0mq_context:
            self.__0mq_context.term()
        if self._cache_socket:
            self._cache_socket.close()

    def _init_cache(self):
        if memcache:
            self._cache_socket = memcache.Client(["127.0.0.1:11211"], debug=0)
        else:
            self._cache_socket = None

    def get_cache(self, key):
        if self._cache_socket:
            return self._cache_socket.get(key)
        else:
            return None

    def set_cache(self, key, value):
        if self._cache_socket:
            self._cache_socket.set(key, value)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[si] {}".format(what), log_level)
        else:
            logging_tools.my_syslog("[si] {}".format(what), log_level)

    def get_tree(self, **kwargs):
        # return etree.fromstring(etree.tostring(self.__tree))
        r_tree = copy.deepcopy(self.__tree)
        if "file_dict" in kwargs:
            for job_id, file_dict in kwargs["file_dict"].iteritems():
                job_el = r_tree.xpath(".//job_list[@full_id='{}' and master/text() = \"MASTER\"]".format(job_id), smart_strings=False)
                if len(job_el):
                    job_el = job_el[0]
                    file_info = job_el.find(".//file_info")
                    if file_info is not None:
                        for sub_el in file_info:
                            file_info.remove(sub_el)
                        for _f_name, f_el in file_dict.iteritems():
                            file_info.append(f_el)
        return r_tree

    def get(self, key, def_value):
        return self.__act_dicts.get(key, def_value)
    # extended job id

    def add_run_job_info(self, job_id, qstat_com):
        job_key = "sgeinfo:job:r{}".format(job_id)
        _cache = self.get_cache(job_key)
        if _cache is None:
            _c_stat, c_out = self._execute_command("{} -u \* -xml -j {}".format(qstat_com, job_id))
            if _c_stat:
                job_xml = E.call_error(c_out, stat="{:d}".format(_c_stat))
            else:
                job_xml = etree.fromstring(c_out)  # @UndefinedVariable
            job_name = job_xml.findtext(".//JB_job_name")
            # check for non-standard path
            # get home
            home_var = job_xml.xpath(".//job_sublist/VA_variable[text() = 'HOME']", smart_strings=False)
            if len(home_var):
                home_dir = home_var[0].getnext().text
            else:
                # dummy pwd, FIXME
                home_dir = "/tmp/"
            # get pwd
            pwd_var = job_xml.xpath(".//job_sublist/VA_variable[text() = 'PWD']", smart_strings=False)
            if len(pwd_var):
                cur_pwd = pwd_var[0].getnext().text
            else:
                # dummy pwd, FIXME
                cur_pwd = "/tmp/"
            ext_xml = E.job_ext_info(E.file_info())
            for _std_type, _short in [("stdout", "o"), ("stderr", "e")]:
                if job_xml.find(".//JB_{}_path_list".format(_std_type)) is not None:
                    _pn_path = job_xml.findtext(".//JB_{}_path_list/path_list/PN_path".format(_std_type))
                    if _pn_path is not None:
                        ext_xml.append(
                            getattr(E, _std_type)(
                                _pn_path.replace("$HOME", home_dir).replace("$JOB_ID", job_id)
                            )
                        )
                else:
                    ext_xml.append(getattr(E, _std_type)(os.path.join(cur_pwd, "{}.{}{}".format(job_name, _short, job_id))))
            self.set_cache(job_key, etree.tostring(ext_xml))  # @UndefinedVariable
        else:
            ext_xml = etree.fromstring(_cache)  # @UndefinedVariable
        self.__run_job_dict[job_id] = ext_xml

    def add_wait_job_info(self, job_id, qstat_com):
        job_key = "sgeinfo:job:w{}".format(job_id)
        _cache = self.get_cache(job_key)
        if _cache is None:
            _c_stat, c_out = self._execute_command("{} -u \* -xml -j {}".format(qstat_com, job_id))
            if _c_stat:
                job_xml = E.call_error(c_out, stat="{:d}".format(_c_stat))
            else:
                job_xml = etree.fromstring(c_out)  # @UndefinedVariable
            # print etree.tostring(job_xml, pretty_print=True)
            ext_xml = E.job_ext_info()
            _exec_time_el = job_xml.find(".//JB_execution_time")
            if _exec_time_el is not None and int(_exec_time_el.text):
                _exec_time = datetime.datetime.fromtimestamp(int(_exec_time_el.text))
                ext_xml.append(E.execution_time(str(int(_exec_time_el.text))))
            self.set_cache(job_key, etree.tostring(ext_xml))  # @UndefinedVariable
        else:
            ext_xml = etree.fromstring(_cache)  # @UndefinedVariable
        self.__wait_job_dict[job_id] = ext_xml

    def get_run_job_info(self, job_id):
        return self.__run_job_dict.get(job_id, None)

    def del_run_job_info(self, job_id):
        del self.__run_job_dict[job_id]

    def get_wait_job_info(self, job_id):
        return self.__wait_job_dict.get(job_id, None)

    def del_wait_job_info(self, job_id):
        del self.__wait_job_dict[job_id]

    def get_run_time(self, cur_time):
        # returns time running
        run_time = abs(datetime.datetime.now() - cur_time)
        days = run_time.days
        secs = run_time.seconds
        return sec_to_str(24 * 3600 * days + secs)

    def get_left_time(self, start_time, h_rt):
        if h_rt:
            run_time = abs(datetime.datetime.now() - start_time)
            left_time = abs(run_time - datetime.timedelta(0, int(h_rt)))
            return sec_to_str(left_time.days * 24 * 3600 + left_time.seconds)
        else:
            return "???"

    def get_h_rt_time(self, h_rt):
        if h_rt:
            h_rt = datetime.timedelta(0, int(h_rt))
            return sec_to_str(h_rt.days * 24 * 3600 + h_rt.seconds)
        else:
            return "???"

    @property
    def tree(self):
        return self.__tree

    def _init_update(self):
        self.__tree = E.rms_info()
        for key in self.__valid_dicts:
            self.__tree.append(getattr(E, key)())

    def _direct_call(self, dict_name):
        s_time = time.time()
        new_el = self.__update_call_dict[dict_name]()
        new_el.attrib["last_update"] = "{:d}".format(int(time.time()))
        new_el.attrib["valid_until"] = "{:d}".format(int(time.time()) + self.__timeout_dicts[dict_name])
        e_time = time.time()
        if self.__verbose > 0:
            self.log(
                "{} (direct) took {}".format(
                    dict_name,
                    logging_tools.get_diff_time_str(e_time - s_time)
                )
            )
        return new_el

    def update(self, **kwargs):
        self.__counter += 1
        # self._init_update()
        upd_list = kwargs.get("update_list", self.__valid_dicts)
        if upd_list is None:
            upd_list = self.__valid_dicts
        # determine which dicts to update
        if self.__verbose:
            self.log("dicts to update (upd_list): {}".format(", ".join(upd_list) or "none"))
        dicts_to_update = set([dict_name for dict_name in upd_list if self._check_for_update(dict_name, kwargs.get("force_update", False))])
        if "qstat" in dicts_to_update:
            dicts_to_update.add("qhost")
        if self.__verbose:
            self.log("dicts to update after check: {}".format(", ".join(dicts_to_update) or "none"))
        # print "to update: ", dicts_to_update
        if self.__source in ["server"]:
            server_update = set(dicts_to_update)
        else:
            server_update = set()
        if self.__verbose:
            self.log("dicts to update from server: {}".format(", ".join(server_update) or "none"))
        # direct results
        _direct_results = {}
        # server contacted ?
        _sc = False
        if server_update:
            # get everything from server
            srv_name = self.__server
            s_time = time.time()
            # try server_update
            # new fancy 0MQ code
            if self.__persistent_socket:
                if not self.__0mq_context:
                    self.__0mq_context = zmq.Context(1)
                    client = self.__0mq_context.socket(zmq.DEALER)  # @UndefinedVariable
                    client.setsockopt(zmq.IDENTITY, "sge_tools:{:d}:{:d}".format(os.getpid(), int(time.time())))  # @UndefinedVariable
                    client.setsockopt(zmq.LINGER, 100)  # @UndefinedVariable
                    _conn_str = "tcp://{}:{:d}".format(srv_name, self.__server_port)
                    try:
                        client.connect(_conn_str)
                    except:
                        self.log("cannot connect to {}: {}".format(_conn_str, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        client = None
                    self.__0mq_socket = client
                client = self.__0mq_socket
            else:
                zmq_context = zmq.Context(1)
                client = zmq_context.socket(zmq.DEALER)  # @UndefinedVariable
                client.setsockopt(zmq.IDENTITY, "sge_tools:{:d}:{:d}".format(os.getpid(), int(time.time())))  # @UndefinedVariable
                client.setsockopt(zmq.LINGER, 100)  # @UndefinedVariable
                client.connect("tcp://{}:{:d}".format(srv_name, self.__server_port))
            if client is not None:
                srv_com = server_command.srv_command(command="get_config")
                srv_com["needed_dicts"] = list(server_update)
                # print srv_com.pretty_print()
                my_poller = zmq.Poller()
                my_poller.register(client, zmq.POLLIN)  # @UndefinedVariable
                client.send_unicode(unicode(srv_com))
                _sc = True
            else:
                _sc = False
        # server contacted, make direct calls
        if self.__source in ["local"]:
            if self.__verbose:
                self.log("dicts to update manually (s1): {}".format(", ".join(dicts_to_update - server_update)))
            for dict_name in dicts_to_update - server_update:
                _direct_results[dict_name] = self._direct_call(dict_name)
        if _sc:
            timeout_secs = kwargs.get("timeout", 5)
            try:
                poll_result = my_poller.poll(timeout=timeout_secs * 1000)
            except:
                poll_result = None
            if poll_result:
                recv = client.recv_unicode()
            else:
                print "timeout after {:d} seconds".format(timeout_secs)
                recv = None
            my_poller.unregister(client)
            del my_poller
            if not self.__persistent_socket:
                client.close()
                zmq_context.term()
            if recv is not None:
                try:
                    srv_reply = server_command.srv_command(source=recv)
                except:
                    pass
                else:
                    if "sge" in srv_reply:
                        self.__tree = etree.fromstring(etree.tostring(srv_reply["sge"][0]))  # @UndefinedVariable
                        # valid return
                    dicts_to_update -= server_update
            e_time = time.time()
            if self.__verbose > 0:
                self.log(
                    "{} (server {}) took {}".format(
                        ", ".join(server_update),
                        srv_name,
                        logging_tools.get_diff_time_str(e_time - s_time)))
        if self.__verbose:
            self.log(
                "before merge: tree size {:d}, memory usage {}".format(
                    len(etree.tostring(self.__tree)),  # @UndefinedVariable
                    logging_tools.get_size_str(process_tools.get_mem_info()),
                )
            )
        # copy direct results to tree
        for dict_name, new_el in _direct_results.iteritems():
            for prev_el in self.__tree.findall(dict_name):
                prev_el.getparent().remove(prev_el)
            self.__tree.append(new_el)
        if self.__verbose:
            self.log(
                "after merge : tree size {:d}, memory usage {}".format(
                    len(etree.tostring(self.__tree)),  # @UndefinedVariable
                    logging_tools.get_size_str(process_tools.get_mem_info()),
                )
            )
        # debug trees
        # if self.__counter < 3:
        #    file("/tmp/rms_tree_{:d}".format(self.__counter), "w").write(etree.tostring(self.__tree, pretty_print=True))
        # print self.__counter
        # s_time = time.time()
        # hm, fixes the memory issue but not very beautifull ...
        self.__tree = etree.fromstring(etree.tostring(self.__tree))  # @UndefinedVariable
        # e_time = time.time()
        # print e_time - s_time

    def _sanitize_sge_dict(self):
        for key_name, file_name, default_value in [
            ("SGE_ROOT", "/etc/sge_root", "NO_SGE_ROOT_SET"),
            ("SGE_CELL", "/etc/sge_cell", "NO_SGE_CELL_SET"),
        ]:
            if key_name not in self.__sge_dict:
                if key_name in os.environ:
                    # use SGE_ROOT/CELL from environment
                    self.__sge_dict[key_name] = os.environ[key_name]
                else:
                    try:
                        self.__sge_dict[key_name] = file(file_name, "r").read().split()[0]
                    except:
                        self.log(
                            "cannot read {}: {}".format(
                                key_name.lower(),
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        self.__sge_dict[key_name] = default_value

        if "SGE_ARCH" not in self.__sge_dict:
            arch_path = os.path.join(self.__sge_dict["SGE_ROOT"], "util", "arch")
            if os.path.exists(arch_path):
                c_stat, c_out = self._execute_command(arch_path)
                self.__sge_dict["SGE_ARCH"] = "NO_SGE_ARCH_SET" if c_stat else c_out
            else:
                self.__sge_dict["SGE_ARCH"] = "NO_SGE_ARCH_SET"

    def _check_for_update(self, d_name, force=False):
        cur_el = self.__tree.find(d_name)
        upd_cause = "unknown"
        cur_time = time.time()
        if cur_el is not None:
            if force:
                do_upd = True
                upd_cause = "forced update"
            elif "valid_until" not in cur_el.attrib:
                do_upd = True
                upd_cause = "first call"
            else:
                do_upd = abs(int(cur_el.get("valid_until", "0"))) < cur_time
                if do_upd:
                    # remove previous xml subtree
                    cur_el.getparent().remove(cur_el)
                    upd_cause = "timeout [valid until {:d} < cur_time {:d}]".format(
                        int(cur_el.get("valid_until", "0")),
                        int(cur_time)
                    )
        else:
            do_upd = True
            upd_cause = "missing"
        if self.__verbose:
            self.log(
                "update for {} is {}".format(
                    d_name,
                    "necessary ({})".format(upd_cause) if do_upd else "not necessary",
                )
            )
        return do_upd

    def _get_com_name(self, c_name):
        return os.path.join(
            self.__sge_dict["SGE_ROOT"],
            "bin",
            self.__sge_dict["SGE_ARCH"],
            c_name,
        )

    def _execute_command(self, command, **kwargs):
        # fancy, fancy
        os.environ["SGE_ROOT"] = self.__sge_dict["SGE_ROOT"]
        os.environ["SGE_CELL"] = self.__sge_dict["SGE_CELL"]
        os.environ["SGE_SINGLE_LINE"] = "1"
        base_com = command.split()[0]
        if os.path.exists(base_com):
            s_time = time.time()
            c_stat, c_out = commands.getstatusoutput(command)
            e_time = time.time()
            if c_stat:
                self.log(
                    "command '{}' gave ({:d}) in {}: {}".format(
                        command,
                        c_stat,
                        logging_tools.get_diff_time_str(e_time - s_time),
                        c_out
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            if kwargs.get("simple_split", False) and not c_stat:
                c_out = [line.split(None, 1) for line in c_out.split("\n") if len(line.split(None, 1)) == 2]
        else:
            c_stat, c_out = (1, "{} does not exist".format(base_com))
            self.log(c_out, logging_tools.LOG_LEVEL_ERROR)
        return c_stat, c_out

    def _check_queueconf_dict(self):
        all_queues = E.queueconf()
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command(
            "{} -sq \*".format(
                qconf_com
            ),
            simple_split=True
        )
        if not c_stat:
            cur_q = None
            for key, value in c_out:
                if key == "qname":
                    if cur_q is not None:
                        all_queues.append(cur_q)
                    cur_q = E.queue(name=value)
                else:
                    cur_q.append(getattr(E, key)(value))
            all_queues.append(cur_q)
        return all_queues

    def _check_pe_dict(self):
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("{} -spl".format(qconf_com))
        cur_pes = E.pe()
        if not c_stat:
            for pe_name in c_out.split("\n"):
                c_stat, c_out = self._execute_command(
                    "{} -sp {}".format(
                        qconf_com,
                        pe_name
                    ),
                    simple_split=True
                )
                if not c_stat:
                    new_pe = E.pe(name=pe_name)
                    for key, value in c_out:
                        value = {
                            "TRUE": "true",
                            "FALSE": "false",
                            "NONE": "none"
                        }.get(value, value)
                        new_pe.append(E.value(name=key, value=value))
                    cur_pes.append(new_pe)
        # print etree.tostring(cur_pes, pretty_print=True)
        return cur_pes

    def _check_hostgroup_dict(self):
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("{} -shgrpl".format(qconf_com))
        cur_hgroups = E.hostgroup()
        if not c_stat:
            for hgrp_name in c_out.split("\n"):
                c_stat, c_out = self._execute_command(
                    "{} -shgrp {}".format(
                        qconf_com,
                        hgrp_name
                    ),
                    simple_split=True
                )
                if not c_stat:
                    new_hg = E.hostgroup(name=c_out.pop(0)[1])
                    for host in c_out.pop(0)[1].split():
                        new_hg.append(E.host(host))
                    cur_hgroups.append(new_hg)
        return cur_hgroups

    def _check_complexes_dict(self):
        qconf_com = self._get_com_name("qconf")
        c_stat, c_out = self._execute_command("{} -sc".format(qconf_com))
        all_complexes = E.complexes()
        if not c_stat:
            for line_parts in [s_line.strip().split() for s_line in c_out.split("\n") if not s_line.strip().startswith("#")]:
                if len(line_parts) > 1:
                    all_complexes.append(E.complex(line_parts[0], short=line_parts[1]))
        return all_complexes

    def _check_qhost_dict(self):
        qhost_com = self._get_com_name("qhost")
        _c_stat, c_out = self._execute_command("{} -F -q -xml -j".format(qhost_com))
        if _c_stat:
            all_qhosts = E.call_error(c_out, stat="{:d}".format(_c_stat))
        else:
            all_qhosts = etree.fromstring(c_out)  # @UndefinedVariable
        for cur_host in all_qhosts.xpath(".//host", smart_strings=False):  # [not(@name='global')]"):
            cur_host.attrib["short_name"] = cur_host.attrib["name"].split(".")[0]
        for cur_job in all_qhosts.xpath(".//job", smart_strings=False):
            task_node = cur_job.find("jobvalue[@name='taskid']")
            if task_node is not None:
                cur_job.attrib["full_id"] = "{}.{}".format(cur_job.attrib["name"], task_node.text)
            else:
                cur_job.attrib["full_id"] = cur_job.attrib["name"]
        for state_el in all_qhosts.xpath(".//queue/queuevalue[@name='state_string']", smart_strings=False):
            state_el.addnext(E.queuevalue(",".join(["({}){}".format(
                cur_state,
                {
                    "-": "-",
                    "u": "unknown",
                    "a": "alarm",
                    "A": "alarm",
                    "C": "calendar suspended",
                    "s": "suspended",
                    "S": "subordinate",
                    "d": "disabled",
                    "D": "disabled",
                    "E": "error"
                }.get(cur_state, cur_state)[1:]) for cur_state in state_el.text or "-"]),
                name="long_state_string")
            )
        for qtype_el in all_qhosts.xpath(".//queue/queuevalue[@name='qtype_string']", smart_strings=False):
            qtype_el.addnext(E.queuevalue(",".join(["({}){}".format(
                cur_qtype,
                {
                    "B": "Batch",
                    "I": "Interactive",
                    "C": "Checkpointing",
                    "P": "Parallel",
                    "T": "Transfer"
                }[cur_qtype][1:]) for cur_qtype in qtype_el.text or "-"]),
                name="long_qtype_string")
            )
        return all_qhosts

    def _check_qstat_dict(self):
        qstat_com = self._get_com_name("qstat")
        # -u * is important to get all jobs
        _c_stat, c_out = self._execute_command("{} -u \* -r -t -ext -urg -pri -xml".format(qstat_com))
        if _c_stat:
            all_jobs = E.call_error(c_out, stat="{:d}".format(_c_stat))
        else:
            all_jobs = etree.fromstring(c_out)  # @UndefinedVariable
        all_jobs.tag = "qstat"
        # modify job_ids
        for cur_job in all_jobs.findall(".//job_list"):
            cur_job.attrib["full_id"] = "{}{}".format(
                cur_job.findtext("JB_job_number"),
                ".{}".format(cur_job.findtext("tasks")) if cur_job.find("tasks") is not None else ""
            )
        # print etree.tostring(all_jobs, pretty_print=True)
        # add info for running jobs
        run_job_ids = set(all_jobs.xpath(".//job_list[master/text() = \"MASTER\"]/@full_id", smart_strings=False))
        # print cur_job_ids, set(all_jobs.xpath(".//job_list/@full_id", smart_strings=False))
        present_ids = set(self.__run_job_dict.keys())
        for del_job_id in present_ids - run_job_ids:
            self.del_run_job_info(del_job_id)
        for add_job_id in run_job_ids - present_ids:
            self.add_run_job_info(add_job_id, qstat_com)
        for cur_job in all_jobs.xpath(".//job_list[@full_id and master/text() = \"MASTER\"]"):
            cur_job_id = cur_job.attrib["full_id"]
            job_info = self.get_run_job_info(cur_job_id)
            if job_info is not None:
                cur_job.append(job_info)
        # add info for waiting jobs
        waiting_ids = set(all_jobs.xpath(".//job_list[@state='pending']/JB_job_number/text()", smart_strings=False))
        present_ids = set(self.__wait_job_dict.keys())
        for del_job_id in present_ids - waiting_ids:
            self.del_wait_job_info(del_job_id)
        for add_job_id in waiting_ids - present_ids:
            self.add_wait_job_info(add_job_id, qstat_com)
        for cur_job in all_jobs.xpath(".//job_list[@state='pending' and JB_job_number]"):
            cur_job_id = cur_job.findtext("JB_job_number")
            if cur_job_id in waiting_ids:
                job_info = self.get_wait_job_info(cur_job_id)
                if job_info is not None:
                    cur_job.append(job_info)
        self._add_stdout_stderr_info(all_jobs)
        for state_el in all_jobs.xpath(".//job_list/state", smart_strings=False):
            state_el.addnext(E.state_long(",".join(["({}){}".format(
                cur_state,
                {
                    "q": "queued",
                    "d": "deleted",
                    "h": "hold",
                    "r": "running",
                    "R": "Restarted",
                    "s": "suspended",
                    "S": "Subordinated",
                    "t": "transfering",
                    "T": "Threshold",
                    "w": "waiting",
                    "o": "orphaned",
                    "E": "Error"
                }.get(cur_state, cur_state)[1:]) for cur_state in state_el.text or "-"])))
        for node_name, attr_name in [
            ("JAT_start_time", "start_time"),
            ("JB_submission_time", "submit_time")
        ]:
            for time_el in all_jobs.findall(".//{}".format(node_name)):
                time_el.getparent().attrib[attr_name] = datetime.datetime.strptime(time_el.text, "%Y-%m-%dT%H:%M:%S").strftime("%s")
        return all_jobs

    def _add_stdout_stderr_info(self, all_jobs):
        for entry in all_jobs.xpath(".//stdout|.//stderr", smart_strings=False):
            try:
                cur_stat = os.stat(entry.text)
            except:
                entry.attrib["found"] = "0"
                entry.attrib["error"] = process_tools.get_except_info()
                entry.attrib["size"] = "0"
            else:
                entry.attrib["found"] = "1"
                entry.attrib["error"] = "0"
                entry.attrib["size"] = "{:d}".format(cur_stat[stat.ST_SIZE])

    def _parse_sge_values(self, q_el, key_name, has_values):
        cur_el = q_el.find(key_name)
        if cur_el.text is None:
            return
        # print "*", q_el, key_name, has_values, cur_el, "parsed" in cur_el.attrib
        # old_dict = q_el[key_name]
        # parse values of form GLOBAL,[node_spec=LOCAL],...
        c_split = cur_el.text.split(",[", 1)
        global_part = c_split.pop(0)
        if has_values:
            if global_part != "NONE":
                cur_el.extend([E.conf_var(name=s_part.split("=", 1)[0], value=s_part.split("=", 1)[1]) for s_part in global_part.split(",")])
        else:
            if global_part != "NONE":
                cur_el.extend([E.conf_var(name=s_part) for s_part in global_part.split()])
        if c_split:
            c_split = c_split[0][:-1].split("],[")
            for node_spec in c_split:
                node_part, local_part = node_spec.split("=", 1)
                s_node = node_part.split(".")[0]
                if has_values:
                    cur_el.extend([E.conf_var(host=s_node, name=s_part.split("=", 1)[0], value=s_part.split("=", 1)[1]) for s_part in local_part.split(",")])
                else:
                    cur_el.extend([E.conf_var(host=s_node, name=s_part) for s_part in local_part.split(",")])
        # remove text
        cur_el.text = None

    def get_queue(self, q_id, default=None):
        return self.__queue_lut.get(q_id, default)

    def get_host(self, h_id, default=None):
        return self.__host_lut.get(h_id, default)

    def get_all_hosts(self):
        return self.__host_lut.itervalues()

    def get_all_queues(self):
        return self.__queue_lut.itervalues()

    def get_job(self, j_id, default=None):
        return self.__job_lut.get(j_id, default)

    def build_luts(self):
        # build look up tables for fast processing
        self.__job_lut, self.running_jobs, self.waiting_jobs = ({}, [], [])
        for cur_job in self.__tree.findall("qstat//job_list"):
            if cur_job.get("state") == "running":
                if cur_job.findtext("master") == "MASTER":
                    self.__job_lut[cur_job.get("full_id")] = cur_job
                    self.running_jobs.append(cur_job)
            else:
                self.__job_lut[cur_job.get("full_id")] = cur_job
                self.waiting_jobs.append(cur_job)
        self.__queue_lut = {}
        for queue in self.__tree.findall("queueconf/queue"):
            self.__queue_lut[queue.get("name")] = queue
            for exp_name, with_values in [
                ("complex_values", True),
                ("pe_list", False),
                ("user_lists", False),
                ("xuser_lists", False),
                ("projects", False),
                ("xprojects", False),
                ("seq_no", False)
            ]:
                self._parse_sge_values(queue, exp_name, with_values)
        self.__host_lut = {}
        for cur_host in self.__tree.findall("qhost/host"):
            self.__host_lut[cur_host.get("name")] = cur_host
        # expand host_list of queue q_name if not already expanded
        hg_lut = {cur_hg.get("name"): cur_hg for cur_hg in self.__tree.findall("hostgroup/hostgroup")}
        for queue in self.__queue_lut.itervalues():
            if not queue.findall("hosts"):
                hosts_el = E.hosts()
                queue.append(hosts_el)
                for cur_hlist in queue.findall("hostlist"):
                    for hg_name in cur_hlist.text.split():
                        if hg_name.startswith("@"):
                            if hg_name in hg_lut:
                                hosts_el.extend([E.host(str(name)) for name in hg_lut[hg_name].xpath(".//host/text()", smart_strings=False)])
                        else:
                            hosts_el.append(E.host(hg_name))


def get_running_headers(options):
    cur_job = E.job(
        E.job_id(),
        E.task_id(),
        E.name(),
        E.granted_pe(),
        E.owner(),
        E.state())
    if options.show_memory:
        cur_job.extend(
            [E.virtual_total(),
             E.virtual_free()])
    cur_job.extend([
        getattr(E, "complex")(),
        E.queue_name()])
    if not options.suppress_times:
        cur_job.extend([
            E.start_time(),
            E.run_time(),
            E.left_time()
        ])
    cur_job.append(E.load()),
    if options.show_stdoutstderr:
        cur_job.extend(
            [
                E.stdout(),
                E.stderr()
            ]
        )
    cur_job.append(E.files())
    if not options.suppress_nodelist:
        cur_job.append(E.nodelist())
    cur_job.append(E.action())
    return cur_job


def _load_to_float(in_value):
    try:
        cur_load = float(in_value)
    except:
        cur_load = 0.0
    return cur_load


def create_action_field(act_job, user):
    ret_el = E.action()
    if user is None:
        ret_el.text = "---"
    else:
        is_user = act_job.findtext(".//JB_owner") == user.login
        if is_user:
            ret_el.text = "delete:force_delete"
        else:
            ret_el.text = "---"
    return ret_el


def create_stdout_stderr(act_job, info):
    # add stdout  / stderr info
    ret_el = getattr(E, info)()
    stdoe_el = act_job.find(".//{}".format(info))
    if stdoe_el is not None:
        if int(stdoe_el.attrib["found"]):
            ret_el.text = logging_tools.get_size_str(int(stdoe_el.attrib["size"]))
        else:
            ret_el.text = "N/A"
    else:
        ret_el.text = "---"
    return ret_el


def create_file_content(act_job):
    return E.files("{:d}".format(len(act_job.xpath(".//file_info/file_content", smart_strings=False))))


def build_running_list(s_info, options, **kwargs):
    user = kwargs.get("user", None)
    # build various local luts
    # print s_info, etree.tostring(s_info.tree, pretty_print=True)
    r_jobs = sorted(s_info.running_jobs, key=lambda x: x.get("full_id"))
    job_host_lut, job_host_pe_lut = ({}, {})
    for cur_host in s_info.get_all_hosts():
        # print etree.tostring(cur_host, pretty_print=True)
        for cur_job in cur_host.xpath("job", smart_strings=False):
            job_host_lut.setdefault(cur_job.attrib["full_id"], []).append(cur_host.attrib["short_name"])
            job_host_pe_lut.setdefault(cur_job.attrib["full_id"], {}).setdefault(
                cur_job.findtext("jobvalue[@name='pe_master']"), []
            ).append(cur_host.attrib["short_name"])
    host_loads = {
        cur_host.attrib["short_name"]: _load_to_float(
            cur_host.findtext("hostvalue[@name='load_avg']")) for cur_host in s_info.get_all_hosts() if cur_host.attrib["short_name"] != "global"
    }
    job_list = E.job_list(total="{:d}".format(len(r_jobs)))
    for act_job in r_jobs:
        if options.users:
            if act_job.find("JB_owner").text not in options.users:
                continue
        i_reqs = set(act_job.xpath("hard_request/@name", smart_strings=False))
        if options.complexes:
            if not set(options.complexes) & i_reqs:
                continue
        queue_name = act_job.findtext("queue_name").split("@")[0]
        cur_job = E.job(
            E.job_id(act_job.findtext("JB_job_number")),
            E.task_id(act_job.findtext("tasks") or ""),
            E.name(act_job.findtext("JB_name")),
            E.granted_pe(
                "{}({})".format(
                    act_job.find("granted_pe").attrib["name"],
                    act_job.findtext("granted_pe")) if len(act_job.findall("granted_pe")) else "-"),
            E.owner(act_job.findtext("JB_owner")),
            E.state(act_job.findtext("state")),
        )
        if options.show_memory:
            master_h = s_info.get_host(act_job.findtext("queue_name").split("@")[-1])
            cur_job.extend(
                [E.virtual_total(master_h.findtext("resourcevalue[@name='virtual_total']")),
                 E.virtual_free(master_h.findtext("resourcevalue[@name='virtual_free']"))])
        cur_job.extend([
            getattr(E, "complex")(",".join(sorted(i_reqs)) or "---"),
            E.queue_name(queue_name)])
        if not options.suppress_times:
            start_time = datetime.datetime.fromtimestamp(int(act_job.attrib["start_time"]))
            cur_job.extend([
                E.start_time(logging_tools.get_relative_dt(start_time), raw=json.dumps(int(time.mktime(start_time.timetuple())))),
                E.run_time(s_info.get_run_time(start_time)),
                E.left_time(s_info.get_left_time(start_time, act_job.findtext("hard_request[@name='h_rt']")))
            ])
        if act_job.attrib["full_id"] in job_host_lut:
            load_list = [host_loads[h_name] for h_name in job_host_lut[act_job.attrib["full_id"]]]
        else:
            # due to dynamic updates the full_id may be missing in the job_host_lut
            load_list = [0.0]
        mean_load = sum(load_list) / len(load_list)
        num_nodes = len(load_list)
        if num_nodes == 1:
            eff = 100
        else:
            max_load = max(load_list)
            if max_load:
                eff = int((num_nodes / (max_load * float(num_nodes - 1)) * mean_load + 1. / float(1 - num_nodes)) * 100)
            else:
                eff = 0
        cur_job.append(E.load("{:.2f} ({:3d} %)".format(mean_load, eff)))
        if options.show_stdoutstderr:
            cur_job.append(create_stdout_stderr(act_job, "stdout"))
            cur_job.append(create_stdout_stderr(act_job, "stderr"))
        cur_job.append(create_file_content(act_job))
        if not options.suppress_nodelist:
            if act_job.get("full_id") in job_host_pe_lut:
                jh_pe_lut = job_host_pe_lut[act_job.get("full_id")]
                _raw_dict = {
                    # name of master device
                    "m": jh_pe_lut["MASTER"][0],
                    # number of master devices
                    "mc": len(jh_pe_lut["MASTER"]),
                    # set of all devices
                    "devs": list(set(sum(jh_pe_lut.values(), []))),
                }
                if options.compress_nodelist:
                    cur_job.append(
                        E.nodelist(
                            ",".join(
                                [
                                    compress_list(
                                        sorted(jh_pe_lut[key]),
                                        postfix="(M)" if key == "MASTER" else ""
                                    ) for key in ["MASTER", "SLAVE"] if key in jh_pe_lut
                                ]
                            ),
                            raw=json.dumps(_raw_dict),
                        )
                    )
                else:
                    cur_job.append(
                        E.nodelist(
                            ",".join(
                                [
                                    ",".join(
                                        [
                                            u"{}{}".format(_entry, "(M)" if key == "MASTER" else "") for _entry in sorted(jh_pe_lut[key])
                                        ]
                                    ) for key in ["MASTER", "SLAVE"] if key in jh_pe_lut
                                ]
                            ),
                            raw=json.dumps(_raw_dict),
                        )
                    )
            else:
                cur_job.append(E.nodelist("not found"))
        cur_job.append(create_action_field(act_job, user))
        job_list.append(cur_job)
    return job_list


def get_waiting_headers(options):
    cur_job = E.job(
        E.job_id(),
        E.task_id(),
        E.name(),
        E.requested_pe(),
        E.owner(),
        E.state(),
        getattr(E, "complex")(),
        E.queue()
    )
    if not options.suppress_times:
        cur_job.extend([
            E.queue_time(),
            E.wait_time(),
            E.left_time(),
            E.exec_time(),
        ])
    cur_job.extend([
        E.prio(),
        E.priority(),
        E.depends()
    ])
    cur_job.append(E.action())
    return cur_job


def get_done_headers():
    return E.job(
        E.job_id(),
        E.task_id(),
        E.name(),
        E.granted_pe(),
        E.owner(),
        E.queue_time(span="1"),
        E.start_time(),
        E.end_time(),
        E.wait_time(),
        E.run_time(),
        E.queue(),
        E.exit_status(),
        E.failed(span="2"),
        E.nodelist(),
    )


def build_waiting_list(s_info, options, **kwargs):
    user = kwargs.get("user", None)
    w_jobs = sorted(s_info.waiting_jobs, key=lambda x: x.get("full_id"))
    show_ids = []
    for act_job in w_jobs:
        show_job = True
        if options.only_valid_waiting:
            if "h" in act_job.findtext("state") or "E" in act_job.findtext("state"):
                show_job = False
        if show_job:
            show_ids.append((float(act_job.findtext("JAT_prio")), act_job.get("full_id"), act_job))
    show_ids.sort()
    show_ids.reverse()
    job_list = E.job_list(total="{:d}".format(len(w_jobs)))
    for _pri, _w_job_id, act_job in show_ids:
        if options.users and act_job.findtext("JB_owner") not in options.users:
            continue
        i_reqs = set(act_job.xpath("hard_request/@name", smart_strings=False))
        if options.complexes:
            if not set(options.complexes) & i_reqs:
                continue
        cur_job = E.job(
            E.job_id(act_job.findtext("JB_job_number")),
            E.task_id(act_job.findtext("tasks") or ""),
            E.name(act_job.findtext("JB_name")),
            E.requested_pe(
                "{}({})".format(
                    act_job.find("requested_pe").attrib["name"],
                    act_job.findtext("requested_pe")) if len(act_job.findall("requested_pe")) else "-"),
            E.owner(act_job.findtext("JB_owner")),
            E.state(act_job.findtext("state_long" if options.long_status else "state")),
            getattr(E, "complex")(",".join(i_reqs) or "---"),
            E.queue(act_job.findtext("hard_req_queue") or "---"),
        )
        if not options.suppress_times:
            submit_time = datetime.datetime.fromtimestamp(int(act_job.attrib["submit_time"]))
            cur_job.extend([
                E.queue_time(logging_tools.get_relative_dt(submit_time)),
                E.wait_time(s_info.get_run_time(submit_time)),
                E.runtime(s_info.get_h_rt_time(act_job.findtext("hard_request[@name='h_rt']"))),
            ])
            _exec_time = act_job.find(".//execution_time")
            if _exec_time is None:
                cur_job.append(E.exec_time(""))
            else:
                _exec_time = datetime.datetime.fromtimestamp(int(_exec_time.text))
                cur_job.append(E.exec_time(logging_tools.get_relative_dt(_exec_time)))
        dep_list = sorted(act_job.xpath(".//predecessor_jobs_req/text()", smart_strings=False))
        cur_job.extend([
            E.prio(act_job.findtext("JAT_prio")),
            E.priority(act_job.findtext("JB_priority")),
            E.depends(
                "{:d}: {}".format(
                    len(dep_list),
                    ",".join(dep_list)) if dep_list else ""),
        ])
        cur_job.append(create_action_field(act_job, user))
        job_list.append(cur_job)
    return job_list


def get_node_headers(options):
    cur_node = E.node()
    if options.merge_node_queue:
        cur_node.extend([
            E.host(),
            E.queues()
        ])
    else:
        cur_node.extend([
            E.queue(),
            E.host()
        ])
    if options.show_seq:
        cur_node.append(E.seqno())
    if not options.suppress_status:
        cur_node.append(E.state())
    if options.show_type or options.show_long_type:
        cur_node.append(E.type())
    if options.show_complexes:
        cur_node.append(E.complex())
    if options.show_pe:
        cur_node.append(E.pe_list())
    if options.show_memory:
        cur_node.extend([
            E.virtual_tot(),
            E.virtual_free()
        ])
    cur_node.extend([
        E.load(),
        E.slots_used(span="2"),
        E.slots_reserved(),
        E.slots_total()
    ])
    if options.show_acl:
        cur_node.extend([
            E.userlists(),
            E.projects()
        ])
    cur_node.append(E.jobs())
    return cur_node


def shorten_list(in_list, **kwargs):
    if "empty_str" in kwargs:
        in_list = [value if value else kwargs["empty_str"] for value in in_list]
    if kwargs.get("reduce", True):
        if len(set(in_list)) == 1:
            return in_list[0]
    return kwargs.get("sep", "/").join(in_list)


def build_node_list(s_info, options):
    job_host_lut, job_host_pe_lut = ({}, {})
    for cur_host in s_info.get_all_hosts():
        for cur_job in cur_host.xpath("job", smart_strings=False):
            job_host_lut.setdefault(cur_job.attrib["full_id"], []).append(cur_host.attrib["short_name"])
            job_host_pe_lut.setdefault(
                cur_host.attrib["short_name"], {}).setdefault(
                    cur_job.findtext("jobvalue[@name='qinstance_name']").split("@")[0], {}).setdefault(
                        cur_job.get("full_id"), []).append(cur_job.findtext("jobvalue[@name='pe_master']"))
    if options.merge_node_queue:
        d_list = sorted(
            [
                (
                    act_h.attrib["name"], sorted(
                        [
                            cur_q.attrib["name"] for cur_q in act_h.findall("queue")
                        ]
                    )
                ) for act_h in s_info.get_all_hosts() if act_h.attrib["short_name"] != "global"
            ]
        )
    else:
        d_list = []
        for act_q in s_info.get_all_queues():
            d_list.extend([(act_q.attrib["name"], h_name.text) for h_name in act_q.findall(".//host") if h_name.text != "NONE"])
        d_list = sorted(d_list, key=lambda node: node[1 if options.node_sort else 0])
    node_list = E.node_list()
    if options.merge_node_queue:
        for h_name, q_list in d_list:
            act_q_list, act_h = ([s_info.get_queue(q_name) for q_name in q_list], s_info.get_host(h_name))
            act_q_list = [_entry for _entry in act_q_list if _entry is not None]
            s_name = act_h.get("short_name")
            m_queue_list = [act_h.find("queue[@name='{}']".format(act_q.attrib["name"])) for act_q in act_q_list]
            if options.suppress_empty and all([int(m_queue.findtext("queuevalue[@name='slots_used']")) == 0 for m_queue in m_queue_list]):
                continue
            if options.show_nonstd:
                if all([m_queue.findtext("queuevalue[@name='state_string']") not in [""] for m_queue in m_queue_list]):
                    if all([m_queue.findtext("queuevalue[@name='state_string']") == "a" for m_queue in m_queue_list]) and options.show_nonstd > 1:
                        continue
            # check for user filters
            if options.users:
                h_users = set(
                    act_h.xpath("job[jobvalue[@name='qinstance_name' and text() = '{}@{}']]/jobvalue[@name='job_owner']/text()".format(
                        q_name,
                        h_name
                    ), smart_strings=False))
                if not set(options.users) & h_users:
                    continue
            # check for complex filters
            if options.complexes:
                q_job_complexes = set(
                    sum(
                        [
                            act_q.xpath(
                                "complex_values/conf_var[not(@host) or @host='{}']/@name".format(
                                    act_h.get("short_name")
                                ),
                                smart_strings=False
                            ) for act_q in act_q_list
                        ],
                        []
                    )
                )
                if not q_job_complexes & set(options.complexes):
                    continue
            cur_node = E.node(
                E.host(act_h.get("short_name")),
                E.queues(shorten_list(q_list))
            )
            if options.show_seq:
                seq_list = [
                    str(
                        act_q.xpath(
                            "seq_no/conf_var[not(@host) or @host='{}']/@name".format(
                                act_h.get("short_name")
                            ),
                            smart_strings=False
                        )[-1]
                    ) for act_q in act_q_list
                ]
                cur_node.append(E.seqno(shorten_list(seq_list)))
            if not options.suppress_status:
                _list = [
                    m_queue.findtext(
                        "queuevalue[@name='{}state_string']".format(
                            "long_" if options.long_status else ""
                        )
                    ) for m_queue in m_queue_list
                ]
                cur_node.append(
                    E.state(
                        shorten_list(
                            [_val or "-" for _val in _list]
                        ),
                        raw=json.dumps(_list)
                    )
                )
            if options.show_type or options.show_long_type:
                _list = [
                    m_queue.findtext(
                        "queuevalue[@name='{}qtype_string']".format(
                            "long_" if options.show_long_type else ""
                        )
                    ) for m_queue in m_queue_list
                ]
                cur_node.append(
                    E.type(
                        shorten_list(
                            _list
                        ),
                        raw=json.dumps(_list)
                    )
                )
            if options.show_complexes:
                cur_node.append(
                    E.complex(
                        shorten_list(
                            [
                                ",".join(
                                    sorted(
                                        set(
                                            act_q.xpath(
                                                "complex_values/conf_var[not(@host) or @host='{}']/@name".format(
                                                    act_h.get("short_name")
                                                ),
                                                smart_strings=False
                                            )
                                        )
                                    )
                                ) for act_q in act_q_list
                            ],
                            empty_str="-"
                        )
                    )
                )
            if options.show_pe:
                cur_node.append(
                    E.pe_list(
                        shorten_list(
                            [
                                ",".join(
                                    sorted(
                                        set(
                                            act_q.xpath(
                                                "pe_list/conf_var[not(@host) or @host='{}']/@name".format(
                                                    act_h.get("short_name")
                                                ),
                                                smart_strings=False
                                            )
                                        )
                                    )
                                ) for act_q in act_q_list
                            ],
                            empty_str="-"
                        )
                    )
                )
            if options.show_memory:
                cur_node.extend([
                    E.virtual_tot(act_h.findtext("resourcevalue[@name='virtual_total']") or ""),
                    E.virtual_free(act_h.findtext("resourcevalue[@name='virtual_free']") or "")
                ])
            cur_node.extend([
                E.load("{:2f}".format(_load_to_float(act_h.findtext("resourcevalue[@name='load_avg']"))), **{"type": "float", "format": "{:.2f}"}),
                E.slots_used(shorten_list([m_queue.findtext("queuevalue[@name='slots_used']") for m_queue in m_queue_list])),
                E.slots_reserved(shorten_list([m_queue.findtext("queuevalue[@name='slots_resv']") for m_queue in m_queue_list])),
                E.slots_total(shorten_list([m_queue.findtext("queuevalue[@name='slots']") for m_queue in m_queue_list])),
            ])
            if options.show_acl:
                acl_str_dict = {}
                for act_q in act_q_list:
                    for ref_name, header_name in [("user_list", "userlists"),
                                                  ("project", "projects")]:
                        pos_list = " or ".join(act_q.xpath(".//{}s/conf_var[not(@host) or @host='{}']/@name".format(
                            ref_name,
                            act_h.get("short_name")), smart_strings=False))
                        neg_list = " or ".join(act_q.xpath(".//x{}s/conf_var[not(@host) or @host='{}']/@name".format(
                            ref_name,
                            act_h.get("short_name")), smart_strings=False))
                        if not pos_list and not neg_list:
                            acl_str = "all"
                        elif not neg_list:
                            acl_str = pos_list
                        elif not pos_list:
                            acl_str = "not ({})".format(neg_list)
                        else:
                            acl_str = "{} and not ({})".format(pos_list, neg_list)
                        acl_str_dict.setdefault(header_name, []).append(acl_str)
                for header_name in ["userlists", "projects"]:
                    cur_node.append(getattr(E, header_name)(shorten_list(acl_str_dict.get(header_name, []))))
            job_list = []
            for q_name in q_list:
                type_dict = job_host_pe_lut.get(s_name, {}).get(q_name, {})
                cur_dict = {job_id: s_info.get_job(job_id) for job_id in sorted(type_dict.keys())}
                qstat_info = ", ".join(["{}{} {} ({:d}) {}{}".format(
                    "[" if "s" in cur_dict[key].findtext("state").lower() else "",
                    key,
                    cur_dict[key].findtext("JB_owner"),
                    int(cur_dict[key].findtext("granted_pe") or "1"),
                    (", ".join([
                        "{}{}".format(
                            ("{:d} x ".format(type_dict[key].count(s_key)) if type_dict[key].count(s_key) > 1 else ""),
                            s_key) for
                        s_key in ["MASTER", "SLAVE"] if s_key in type_dict[key]]) + ".").replace("MASTER.", "SINGLE.")[:-1],
                    "]" if "s" in cur_dict[key].findtext("state").lower() else "",
                ) for key in sorted(type_dict.keys()) if cur_dict.get(key, None) is not None])
                if qstat_info.strip():
                    job_list.append("{}::{}".format(q_name, qstat_info))
            cur_node.append(E.jobs("/".join(job_list)))
            node_list.append(cur_node)
    else:
        for q_name, h_name in d_list:
            act_q, act_h = (s_info.get_queue(q_name), s_info.get_host(h_name))
            if act_q is None or act_h is None:
                continue
            s_name = act_h.get("short_name")
            m_queue = act_h.find("queue[@name='{}']".format(act_q.attrib["name"]))
            if options.suppress_empty and int(m_queue.findtext("queuevalue[@name='slots_used']")) == 0:
                continue
            if m_queue is None:
                continue
            if options.show_nonstd:
                if m_queue.findtext("queuevalue[@name='state_string']") not in [""]:
                    if m_queue.findtext("queuevalue[@name='state_string']") == "a" and options.show_nonstd > 1:
                        continue
            # check for user filters
            if options.users:
                h_users = set(
                    act_h.xpath(
                        "job[jobvalue[@name='qinstance_name' and text() = '{}@{}']]/jobvalue[@name='job_owner']/text()".format(
                            q_name,
                            h_name
                        ),
                        smart_strings=False
                    )
                )
                if not set(options.users) & h_users:
                    continue
            # check for complex filters
            if options.complexes:
                q_job_complexes = set(
                    act_q.xpath(
                        "complex_values/conf_var[not(@host) or @host='{}']/@name".format(
                            act_h.get("short_name")
                        ),
                        smart_strings=False
                    )
                )
                if not q_job_complexes & set(options.complexes):
                    continue
            cur_node = E.node(
                E.queue(q_name),
                E.host(s_name))
            if options.show_seq:
                cur_node.append(
                    E.seqno(
                        str(
                            act_q.xpath(
                                "seq_no/conf_var[not(@host) or @host='{}']/@name".format(
                                    act_h.get("short_name")
                                ),
                                smart_strings=False
                            )[-1]
                        )
                    )
                )
            if not options.suppress_status:
                cur_node.append(E.state(m_queue.findtext("queuevalue[@name='{}state_string']".format(
                    "long_" if options.long_status else "")) or "-"))
            if options.show_type or options.show_long_type:
                cur_node.append(E.type(m_queue.findtext("queuevalue[@name='{}qtype_string']".format(
                    "long_" if options.show_long_type else ""))))
            if options.show_complexes:
                cur_node.append(
                    E.complex(
                        ",".join(sorted(set(act_q.xpath("complex_values/conf_var[not(@host) or @host='{}']/@name".format(
                            act_h.get("short_name")
                        ), smart_strings=False))))
                    )
                )
            if options.show_pe:
                cur_node.append(
                    E.pe_list(
                        ",".join(sorted(set(act_q.xpath("pe_list/conf_var[not(@host) or @host='{}']/@name".format(
                            act_h.get("short_name")
                        ), smart_strings=False))))
                    )
                )
            if options.show_memory:
                cur_node.extend(
                    [
                        E.virtual_tot(act_h.findtext("resourcevalue[@name='virtual_total']") or ""),
                        E.virtual_free(act_h.findtext("resourcevalue[@name='virtual_free']") or "")
                    ]
                )
            # print etree.tostring(act_h, pretty_print=True)
            cur_node.extend(
                [
                    E.load("{:.2f}".format(_load_to_float(act_h.findtext("resourcevalue[@name='load_avg']")))),
                    E.slots_used(m_queue.findtext("queuevalue[@name='slots_used']")),
                    E.slots_reserved(m_queue.findtext("queuevalue[@name='slots_resv']")),
                    E.slots_total(m_queue.findtext("queuevalue[@name='slots']")),
                ]
            )
            if options.show_acl:
                for ref_name, header_name in [("user_list", "userlists"),
                                              ("project", "projects")]:
                    pos_list = " or ".join(act_q.xpath(".//{}s/conf_var[not(@host) or @host='{}']/@name".format(
                        ref_name,
                        act_h.get("short_name")), smart_strings=False))
                    neg_list = " or ".join(act_q.xpath(".//x{}s/conf_var[not(@host) or @host='{}']/@name".format(
                        ref_name,
                        act_h.get("short_name")), smart_strings=False))
                    if not pos_list and not neg_list:
                        acl_str = "all"
                    elif not neg_list:
                        acl_str = pos_list
                    elif not pos_list:
                        acl_str = "not ({})".format(neg_list)
                    else:
                        acl_str = "{} and not ({})".format(pos_list, neg_list)
                    cur_node.append(getattr(E, header_name)(acl_str))
            type_dict = job_host_pe_lut.get(s_name, {}).get(q_name, {})
            cur_dict = {job_id: s_info.get_job(job_id) for job_id in sorted(type_dict.keys())}
            try:
                qstat_info = ", ".join(
                    [
                        "{}{} {} ({:d}) {}{}".format(
                            "[" if "s" in cur_dict[key].findtext("state").lower() else "",
                            key,
                            cur_dict[key].findtext("JB_owner"),
                            int(cur_dict[key].findtext("granted_pe") or "1"),
                            (
                                ", ".join(
                                    [
                                        "{}{}".format(
                                            ("{:d} x ".format(type_dict[key].count(s_key)) if type_dict[key].count(s_key) > 1 else ""),
                                            s_key
                                        ) for
                                        s_key in ["MASTER", "SLAVE"] if s_key in type_dict[key]
                                    ]
                                ) + "."
                            ).replace("MASTER.", "SINGLE.")[:-1],
                            "]" if "s" in cur_dict[key].findtext("state").lower() else "",
                        ) for key in sorted(type_dict.keys())
                    ]
                )
            except:
                # hm, not optimal ...
                qstat_info = ""
            cur_node.append(E.jobs(qstat_info))
            node_list.append(cur_node)
    return node_list


def _stress_test():
    a = sge_info(mode="local", verbose=True)
    _iters = 100
    for _x in xrange(_iters):
        a.update(force_update=True)
    print("{:d} iterations done".format(_iters))
    time.sleep(3600)


if __name__ == "__main__":
    _stress_test()
