#
# Copyright (c) 2013-2015 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of collectd-init
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" connect to a given collectd-server and fetch some data """

import json
import re
import sys
import time

import memcache
import zmq

from initat.host_monitoring.hm_classes import mvect_entry
from initat.tools import logging_tools, process_tools, server_command


class BaseCom(object):
    def __init__(self, options, *args):
        self.options = options
        self.args = args
        if self.options.mode == "tcp":
            srv_com = server_command.srv_command(command=self.Meta.command)
            srv_com["identity"] = process_tools.zmq_identity_str(self.options.identity_string)
            for arg_index, arg in enumerate(args):
                if self.options.verbose:
                    print(" arg {:d}: {}".format(arg_index, arg))
                    srv_com["arguments:arg{:d}".format(arg_index)] = arg
            srv_com["arg_list"] = " ".join(args)
            srv_com["host_filter"] = self.options.host_filter
            srv_com["key_filter"] = self.options.key_filter
            self.srv_com = srv_com  #
        self.ret_state = 1

    def __getitem__(self, key):
        return self.srv_com[key]

    def __unicode__(self):
        return unicode(self.srv_com)

    def get_mc(self):
        return memcache.Client(["{}:{:d}".format(self.options.mc_addr, self.options.mc_port)])

    def compile_re(self, re_str):
        try:
            cur_re = re.compile(re_str)
        except:
            print("error transforming '{}' to re".format(re_str))
            cur_re = re.compile(".*")
        return cur_re

    def send_and_receive(self, client):
        # tcp (0MQ) mode
        conn_str = "tcp://{}:{:d}".format(self.options.host, self.options.port)
        if self.options.verbose:
            print(
                "Identity_string is '{}', connection_string is '{}'".format(
                    self.srv_com["identity"].text,
                    conn_str
                )
            )
        client.connect(conn_str)
        s_time = time.time()

        client.send_unicode(unicode(self.srv_com))
        if self.options.verbose:
            print self.srv_com.pretty_print()
        r_client = client
        if r_client.poll(self.options.timeout * 1000):
            recv_str = r_client.recv()
            if r_client.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                recv_id = recv_str
                recv_str = r_client.recv()
            else:
                recv_id = ""
            self.receive_tuple = (recv_id, recv_str)
            timeout = False
        else:
            print "error timeout ({:.2f} > {:d})".format(time.time() - s_time, self.options.timeout)
            timeout = True
        e_time = time.time()
        if self.options.verbose:
            if timeout:
                print "communication took {}".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            else:
                print "communication took {}, received {:d} bytes".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                    len(recv_str),
                )
        return True if not timeout else False

    def interpret_tcp(self):
        recv_id, recv_str = self.receive_tuple
        try:
            srv_reply = server_command.srv_command(source=recv_str)
        except:
            print("cannot interpret reply: {}".format(process_tools.get_except_info()))
            print("reply was: {}".format(recv_str))
            self.ret_state = 1
        else:
            if self.options.verbose:
                print
                print("XML response (id: '{}'):".format(recv_id))
                print
                print(srv_reply.pretty_print())
                print
            if "result" in srv_reply:
                if hasattr(self, "_interpret"):
                    # default value: everything OK
                    self.ret_state = 0
                    self._interpret(srv_reply)
                else:
                    print srv_reply["result"].attrib["reply"]
                    self.ret_state = int(srv_reply["result"].attrib["state"])
            else:
                print "no result tag found in reply"
                self.ret_state = 2


class HostListCom(BaseCom):
    class Meta:
        command = "host_list"

    def fetch(self):
        _mc = self.get_mc()
        hlist = json.loads(_mc.get("cc_hc_list"))
        h_re = self.compile_re(self.options.host_filter)
        v_dict = {key: value for key, value in hlist.iteritems() if h_re.match(value[1])}
        _h_uuid_dict = {_value[1]: _key for _key, _value in v_dict.iteritems()}
        _h_names = sorted(_h_uuid_dict.keys())
        print(
            "{} found : {}".format(
                logging_tools.get_plural("host", len(_h_names)),
                logging_tools.reduce_list(_h_names),
            )
        )
        for _h_name in _h_names:
            key = _h_uuid_dict[_h_name]
            value = v_dict[key]
            print "{:30s} ({}) : last updated {}".format(value[1], key, time.ctime(value[0]))
        # print v_list

    def _interpret(self, srv_com):
        h_list = srv_com.xpath(".//host_list", smart_strings=False)
        if len(h_list):
            h_list = h_list[0]
            num_hosts, num_keys = (0, 0)
            form_str = "{:<30s} ({:<40s}) : {:6d} keys, last update {}, store_to_disk is {}"
            print(
                "got result for {}:".format(
                    logging_tools.get_plural("host", int(h_list.attrib["entries"]))
                )
            )
            for host in h_list:
                print(
                    form_str.format(
                        host.attrib["name"],
                        host.attrib["uuid"],
                        int(host.attrib["keys"]),
                        time.ctime(int(host.attrib["last_update"])),
                        "enabled" if int(host.get("store_to_disk", "1")) else "disabled",
                    )
                )
                num_hosts += 1
                num_keys += int(host.attrib["keys"])
            if num_hosts:
                print(
                    form_str.format(
                        "total",
                        logging_tools.get_plural("host", num_hosts),
                        num_keys,
                        "never",
                        "ignored",
                    )
                )
        else:
            print "No host_list found in result"
            self.ret_state = 1


class KeyListCom(BaseCom):
    class Meta:
        command = "key_list"

    def fetch(self):
        _mc = self.get_mc()
        hlist = json.loads(_mc.get("cc_hc_list"))
        h_re = self.compile_re(self.options.host_filter)
        v_re = self.compile_re(self.options.key_filter)
        v_dict = {
            key: value for key, value in hlist.iteritems() if h_re.match(value[1])
        }
        print(
            "{} found : {}".format(
                logging_tools.get_plural("host", len(v_dict)),
                ", ".join(sorted([value[1] for value in v_dict.itervalues()]))
            )
        )
        k_dict = {
            key: json.loads(_mc.get("cc_hc_{}".format(key))) for key in v_dict.iterkeys()
        }
        _sorted_uuids = sorted(v_dict, cmp=lambda x, y: cmp(v_dict[x][1], v_dict[y][1]))
        for key in _sorted_uuids:
            value = v_dict[key]
            print "{:30s} ({}) : last updated {}".format(value[1], key, time.ctime(value[0]))
        out_f = logging_tools.new_form_list()
        # pprint.pprint(k_dict)
        max_num_keys = 0
        _list = []
        for h_uuid in _sorted_uuids:
            h_struct = k_dict[h_uuid]
            num_key = 0
            for entry in sorted(h_struct):
                if v_re.match(entry[1]):
                    num_key += 1
                    if entry[0] == 0:
                        # simple format
                        cur_mv = mvect_entry(
                            entry[1],
                            info=entry[2],
                            unit=entry[3],
                            v_type=entry[4],
                            value=entry[5],
                            base=entry[6],
                            factor=entry[7]
                        )
                    else:
                        print("no simple format?")
                        sys.exit(0)
                    _list.append((h_uuid, cur_mv))
                    max_num_keys = max(max_num_keys, cur_mv.num_keys)
        for h_uuid, entry in _list:
            out_f.append(
                [
                    logging_tools.form_entry(v_dict[h_uuid][1], header="device")
                ] + entry.get_form_entry(num_key, max_num_keys)
            )
        print unicode(out_f)
        # print v_list

    def _interpret(self, srv_com):
        h_list = srv_com.xpath(".//host_list", smart_strings=False)
        if len(h_list):
            h_list = h_list[0]
            out_f = logging_tools.new_form_list()
            print "got result for {}:".format(logging_tools.get_plural("host", int(h_list.attrib["entries"])))
            max_num_keys = 0
            _list = []
            for host in h_list:
                print "{:<30s} ({:<40s}) : {:4d} keys, last update {}".format(
                    host.attrib["name"],
                    host.attrib["uuid"],
                    int(host.attrib["keys"]),
                    time.ctime(int(host.attrib["last_update"]))
                )
                for num_key, key_el in enumerate(host):
                    cur_mv = mvect_entry(key_el.attrib.pop("name"), info="", **key_el.attrib)
                    _list.append((host.attrib["name"], cur_mv))
                    max_num_keys = max(max_num_keys, cur_mv.num_keys)
            for h_name, entry in _list:
                out_f.append(
                    [
                        logging_tools.form_entry(h_name, header="device")
                    ] + entry.get_form_entry(num_key, max_num_keys)
                )
            print unicode(out_f)
        else:
            print "No host_list found in result"
            self.ret_state = 1


def main(args):
    com_list = ["host_list", "key_list"]
    other_args = args.arguments
    ret_state = 1
    cc_name = "".join([sub_str.title() for sub_str in args.command.split("_")])
    try:
        cur_com = globals()["{}Com".format(cc_name)](args, *other_args)
    except:
        print "error init '{}': {}".format(args.command, process_tools.get_except_info())
        sys.exit(ret_state)
    if args.mode == "tcp":
        zmq_context = zmq.Context(1)
        client = zmq_context.socket(zmq.DEALER)
        client.setsockopt(zmq.IDENTITY, cur_com["identity"].text)
        client.setsockopt(zmq.LINGER, args.timeout)
        was_ok = cur_com.send_and_receive(client)
        if was_ok:
            cur_com.interpret_tcp()
        client.close()
        zmq_context.term()
    else:
        cur_com.fetch()
    sys.exit(cur_com.ret_state)
