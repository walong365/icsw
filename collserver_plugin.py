#!/usr/bin/python-init -Otu

from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import logging_tools
import multiprocessing
import os
import process_tools
import re
import server_command
import signal
import threading
import time
import uuid_tools
import zmq
if __name__ != "__main__":
    import collectd # @UnresolvedImport

IPC_SOCK = "ipc:///var/log/cluster/sockets/collectd/com"
RECV_PORT = 8002
COMMAND_PORT = 8008
GRAPHER_PORT = 8003

class perfdata_value(object):
    PD_NAME = "unique_name"
    def __init__(self, name, info, unit="1", v_type="f", key="", rrd_spec="GAUGE:0:100"):
        self.name = name
        self.info = info
        self.unit = unit
        self.v_type = v_type
        self.key = key or name
        self.rrd_spec = rrd_spec
    def get_xml(self):
        return E.value(
            name=self.name,
            unit=self.unit,
            info=self.info,
            v_type=self.v_type,
            key=self.key,
            rrd_spec=self.rrd_spec,
        )

class perfdata_object(object):
    def _wrap(self, _xml, v_list, rsi=0):
        # rsi: report start index, used to skip values from v_list which should not be graphed
        # add name, host and timestamp values
        return [
            # name of instance (has to exist in init_types.db)
            self.PD_NAME,
            # instance type (for non-unique perfdata objects, PSUs on a bladecenterchassis for instance)
            self.get_type_instance(v_list),
            # hostname
            _xml.get("host"),
            # time
            int(_xml.get("time")),
            # report offset
            rsi,
            # list of variables
            v_list,
        ]
    def get_type_instance(self, v_list):
        return ""
    @property
    def default_xml_info(self):
        return self.get_pd_xml_info([])
    def get_pd_xml_info(self, v_list):
        return self.PD_XML_INFO
    def build_perfdata_info(self, mach_values):
        new_com = server_command.srv_command(command="perfdata_info")
        new_com["hostname"] = mach_values[2]
        new_com["pd_type"] = self.PD_NAME
        info = self.get_pd_xml_info(mach_values[5])
        if mach_values[1]:
            info.attrib["type_instance"] = mach_values[1]
        new_com["info"] = info
        return new_com

class load_pdata(perfdata_object):
    PD_RE = re.compile("^load1=(?P<load1>\S+)\s+load5=(?P<load5>\S+)\s+load15=(?P<load15>\S+)$")
    PD_NAME = "load"
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("load1", "mean load of the last minute", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("load5", "mean load of the 5 minutes", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("load15", "mean load of the 15 minutes", rrd_spec="GAUGE:0:10000").get_xml(),
    )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [
                float(in_dict[key]) for key in ["load1", "load5", "load15"]
            ]
        )

class smc_chassis_psu_pdata(perfdata_object):
    PD_RE = re.compile("^smcipmi\s+psu=(?P<psu_num>\d+)\s+temp=(?P<temp>\S+)\s+amps=(?P<amps>\S+)\s+fan1=(?P<fan1>\d+)\s+fan2=(?P<fan2>\d+)$")
    PD_NAME = "smc_chassis_psu"
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [int(in_dict["psu_num"]), float(in_dict["temp"]), float(in_dict["amps"]), int(in_dict["fan1"]), int(in_dict["fan2"])],
            rsi=1,
            )
    @property
    def default_xml_info(self):
        return self.get_pd_xml_info([0])
    def get_pd_xml_info(self, v_list):
        psu_num = v_list[0]
        return E.perfdata_info(
            perfdata_value("temp", "temperature of PSU %d" % (psu_num), v_type="f", unit="C", key="temp.psu%d" % (psu_num), rrd_spec="GAUGE:0:100").get_xml(),
            perfdata_value("amps", "amperes consumed by PSU %d" % (psu_num), v_type="f", unit="A", key="amps.psu%d" % (psu_num), rrd_spec="GAUGE:0:100").get_xml(),
            perfdata_value("fan1", "speed of FAN1 of PSU %d" % (psu_num), v_type="i", key="fan.psu%dfan1" % (psu_num), rrd_spec="GAUGE:0:10000").get_xml(),
            perfdata_value("fan2", "speed of FAN2 of PSU %d" % (psu_num), v_type="i", key="fan.psu%dfan2" % (psu_num), rrd_spec="GAUGE:0:10000").get_xml(),
        )
    def get_type_instance(self, v_list):
        # set PSU index as instance
        return "%d" % (v_list[0])

class ping_pdata(perfdata_object):
    PD_RE = re.compile("^rta=(?P<rta>\S+) min=(?P<min>\S+) max=(?P<max>\S+) sent=(?P<sent>\d+) loss=(?P<loss>\d+)$")
    PD_NAME = "ping"
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("sent", "packets sent", v_type="i", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("loss", "packets lost", v_type="i", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("rta", "mean package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("min", "minimum package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("max", "maximum package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
    )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [int(in_dict["sent"]), int(in_dict["loss"]), float(in_dict["rta"]), float(in_dict["min"]), float(in_dict["max"])]
        )

class value(object):
    # somehow resembles mvect_entry from hm_classes
    __slots__ = ["name", "sane_name", "info", "unit", "base", "value", "factor", "v_type", "last_update", "set_value"]
    def __init__(self, name):
        self.name = name
        self.sane_name = self.name.replace("/", "_sl_")
    def update(self, entry, cur_time):
        self.info = entry.attrib["info"]
        self.v_type = entry.attrib["v_type"]
        self.unit = entry.get("unit", "1")
        self.base = int(entry.get("base", "1"))
        self.factor = int(entry.get("factor", "1"))
        if self.v_type == "i":
            self.set_value = self._set_value_int
        elif self.v_type == "f":
            self.set_value = self._set_value_float
        else:
            self.set_value = self._set_value_str
        self.set_value(entry.attrib["value"], cur_time)
    def _set_value_int(self, value, cur_time):
        self.last_update = cur_time
        self.value = int(value)
    def _set_value_float(self, value, cur_time):
        self.last_update = cur_time
        self.value = float(value)
    def _set_value_str(self, value, cur_time):
        self.last_update = cur_time
        self.value = value
    def transform(self, value, cur_time):
        self.set_value(value, cur_time)
        return self.value * self.factor
    def get_key_info(self):
        return E.key(
            value=str(self.value),
            name=self.name,
            v_type=self.v_type,
            base="%d" % (self.base),
            factor="%d" % (self.factor),
            unit=self.unit,
            )

class host_info(object):
    def __init__(self, uuid, name):
        collectd.notice("init host_info for %s (%s)" % (name, uuid))
        self.name = name
        self.uuid = uuid
        self.__dict = {}
        self.last_update = None
        self.updates = 0
        self.stores = 0
    def get_host_info(self):
        return E.host_info(
            name=self.name,
            uuid=self.uuid,
            last_update="%d" % (self.last_update or 0),
            keys="%d" % (len(self.__dict)),
            # update calls (full info)
            updates="%d" % (self.updates),
            # store calls (short info)
            stores="%d" % (self.stores),
            )
    def get_key_list(self, key_filter):
        h_info = self.get_host_info()
        for key in sorted(self.__dict.keys()):
            if key_filter.match(key):
                h_info.append(self.__dict[key].get_key_info())
        return h_info
    def update(self, _xml):
        cur_time = time.time()
        old_keys = set(self.__dict.keys())
        for entry in _xml.findall("mve"):
            cur_name = entry.attrib["name"]
            if cur_name not in self.__dict:
                self.__dict[cur_name] = value(cur_name)
            self.__dict[cur_name].update(entry, cur_time)
        new_keys = set(self.__dict.keys())
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.updates += 1
            del_keys = old_keys - new_keys
            for del_key in del_keys:
                del self.__dict[del_key]
            collectd.warning("%s changed for %s" % (logging_tools.get_plural("key", len(c_keys)), self.name))
            return True
        else:
            return False
    def transform(self, key, value, cur_time):
        self.last_update = cur_time
        if key in self.__dict:
            try:
                return (
                    self.__dict[key].sane_name,
                    self.__dict[key].transform(value, cur_time),
                )
            except:
                collectd.error("error transforming %s: %s" % (key, process_tools.get_except_info()))
                return (None, None)
        else:
            # key not known, skip
            return (None, None)
    def get_values(self, _xml, simple):
        self.stores += 1
        if simple:
            tag_name, name_name, value_name = ("m", "n", "v")
        else:
            tag_name, name_name, value_name = ("mve", "name", "value")
        cur_time = time.time()
        values = [self.transform(entry.attrib[name_name], entry.attrib[value_name], cur_time) for entry in _xml.findall(tag_name)]
        return values

class net_receiver(multiprocessing.Process):
    def __init__(self):
        multiprocessing.Process.__init__(self, target=self._code, name="0MQ_net_receiver")
        self.zmq_id = "%s:collserver_plugin" % (process_tools.get_machine_name())
        self.grapher_id = "%s:rrd_grapher" % (uuid_tools.get_uuid().get_urn())
        self.poller = zmq.Poller()
    def _init(self):
        self._init_perfdata()
        self._init_vars()
        self._init_hosts()
        self._init_sockets()
    def _init_perfdata(self):
        re_list = []
        for key in globals().keys():
            obj = globals()[key]
            if type(obj) == type and obj != perfdata_object:
                if issubclass(obj, perfdata_object):
                    obj = obj()
                    re_list.append((obj.PD_RE, obj))
        self.__pd_re_list = re_list
    def _init_sockets(self):
        self.context = zmq.Context()
        self.receiver = self.context.socket(zmq.PULL)
        self.sender = self.context.socket(zmq.PUSH)
        self.grapher = self.context.socket(zmq.ROUTER)
        self.command = self.context.socket(zmq.ROUTER)
        # set grapher flags
        for flag, value in [
            (zmq.IDENTITY, self.zmq_id),
            (zmq.SNDHWM, 256),
            (zmq.RCVHWM, 256),
            (zmq.TCP_KEEPALIVE, 1),
            (zmq.TCP_KEEPALIVE_IDLE, 300)]:
            self.grapher.setsockopt(flag, value)
            self.command.setsockopt(flag, value)
        self.sender.connect(IPC_SOCK)
        listener_url = "tcp://*:%d" % (RECV_PORT)
        command_url = "tcp://*:%d" % (COMMAND_PORT)
        grapher_url = "tcp://localhost:%d" % (GRAPHER_PORT)
        self.receiver.bind(listener_url)
        self.command.bind(command_url)
        self.grapher.connect(grapher_url)
        collectd.notice("listening on %s, connected to grapher on %s, command_url is %s" % (
            listener_url,
            grapher_url,
            command_url,
            ))
        self.__poller_dict = {
            self.receiver : self._recv_data,
            self.command : self._recv_command,
            }
        self.poller.register(self.receiver, zmq.POLLIN)
        self.poller.register(self.command, zmq.POLLIN)
    def _init_hosts(self):
        # init host and perfdata structs
        self.__hosts = {}
        # counter when to send data to rrd-grapher
        self.__perfdatas_cnt = {}
    def _init_vars(self):
        self.__start_time = time.time()
        self.__trees_read, self.__pds_read = (0, 0)
        self.__total_size_trees, self.__total_size_pds = (0, 0)
        self.__distinct_hosts_mv = set()
        self.__distinct_hosts_pd = set()
    def _close(self):
        self._log_stats()
        self._close_sockets()
    def _close_sockets(self):
        self.sender.close()
        self.receiver.close()
        self.grapher.close()
        self.command.close()
        self.context.term()
        collectd.notice("0MQ process finished")
    def _code(self):
        self._init()
        try:
            self._loop()
        except:
            collectd.error("exception raised in loop, exiting")
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                collectd.error(line)
            self.sender.send("stop")
        self._close()
    def _log_stats(self):
        self.__end_time = time.time()
        diff_time = max(1, abs(self.__end_time - self.__start_time))
        bt_rate = self.__trees_read / diff_time
        st_rate = self.__total_size_trees / diff_time
        bp_rate = self.__pds_read / diff_time
        sp_rate = self.__total_size_pds / diff_time
        collectd.notice("read %s (%s) from %s (rate [%.2f, %s] / sec), %s (%s) from %s (rate [%.2f, %s] / sec) in %s" % (
            logging_tools.get_plural("tree", self.__trees_read),
            logging_tools.get_size_str(self.__total_size_trees),
            logging_tools.get_plural("host", len(self.__distinct_hosts_mv)),
            bt_rate,
            logging_tools.get_size_str(st_rate),
            logging_tools.get_plural("perfdata", self.__pds_read),
            logging_tools.get_size_str(self.__total_size_pds),
            logging_tools.get_plural("host", len(self.__distinct_hosts_pd)),
            bp_rate,
            logging_tools.get_size_str(sp_rate),
            logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
        ))
        self._init_vars()
    def _send_to_grapher(self, send_xml):
        self.grapher.send_unicode(self.grapher_id, zmq.SNDMORE)
        self.grapher.send_unicode(unicode(send_xml))
    def _loop(self):
        while True:
            try:
                rcv_list = self.poller.poll(timeout=1000)
            except zmq.error.ZMQError:
                collectd.error("got ZMQError, exiting")
                break
            else:
                for in_sock, in_type in rcv_list:
                    self.__poller_dict[in_sock](in_sock)
    def _recv_data(self, in_sock):
        in_data = in_sock.recv()
        self._process_data(in_data)
        if abs(time.time() - self.__start_time) > 300:
            # periodic log stats
            self._log_stats()
    def _recv_command(self, in_sock):
        in_uuid = in_sock.recv_unicode()
        in_xml = in_sock.recv_unicode()
        in_com = server_command.srv_command(source=in_xml)
        in_com.update_source()
        com_text = in_com["command"].text
        h_filter, k_filter = (
            in_com.get("host_filter", ".*"),
            in_com.get("key_filter", ".*")
            )
        collectd.info("got command %s from %s (host_filter: %s, key_filter: %s)" % (
            com_text,
            in_uuid,
            h_filter,
            k_filter,
            ))
        try:
            host_filter = re.compile(h_filter)
        except:
            host_filter = re.compile(".*")
            collectd.error("error interpreting '%s' as host re: %s" % (h_filter, process_tools.get_except_info()))
        try:
            key_filter = re.compile(k_filter)
        except:
            key_filter = re.compile(".*")
            collectd.error("error interpreting '%s' as key re: %s" % (k_filter, process_tools.get_except_info()))
        match_uuids = [_value[1] for _value in sorted([(self.__hosts[cur_uuid].name, cur_uuid) for cur_uuid in self.__hosts.keys() if host_filter.match(self.__hosts[cur_uuid].name)])]
        if com_text == "host_list":
            result = E.host_list(entries="%d" % (len(match_uuids)))
            for cur_uuid in match_uuids:
                result.append(self.__hosts[cur_uuid].get_host_info())
            in_com["result"] = result
        elif com_text == "key_list":
            result = E.host_list(entries="%d" % (len(match_uuids)))
            for cur_uuid in match_uuids:
                result.append(self.__hosts[cur_uuid].get_key_list(key_filter))
            in_com["result"] = result
        in_com.set_result("got command %s" % (com_text))
        in_sock.send_unicode(in_uuid, zmq.SNDMORE)
        in_sock.send_unicode(unicode(in_com))
    def _feed_host_info(self, host_uuid, host_name, _xml):
        if host_uuid not in self.__hosts:
            self.__hosts[host_uuid] = host_info(host_uuid, host_name)
        if self.__hosts[host_uuid].update(_xml):
            # something changed
            new_com = server_command.srv_command(command="mv_info")
            new_com["vector"] = _xml
            self._send_to_grapher(new_com)
    def _process_data(self, in_tree):
        # adopt tree format for faster handling in collectd loop
        try:
            _xml = etree.fromstring(in_tree)
        except:
            collectd.error("cannot parse tree: %s" % (process_tools.get_except_info()))
        else:
            xml_tag = _xml.tag.split("}")[-1]
            # collectd.error(xml_tag)
            handle_name = "_handle_%s" % (xml_tag)
            if hasattr(self, handle_name):
                try:
                    # loop
                    for p_data in getattr(self, handle_name)(_xml, len(in_tree)):
                        # collectd.info(str(p_data))
                        self.sender.send_pyobj(p_data)
                except:
                    collectd.error(process_tools.get_except_info())
            else:
                collectd.error("unknown handle_name '%s'" % (handle_name))
    def _check_for_ext_perfdata(self, mach_values):
        # unique tuple
        pd_tuple = (mach_values[0], mach_values[1])
        # init counter
        if pd_tuple not in self.__perfdatas_cnt:
            self.__perfdatas_cnt[pd_tuple] = 1
        # reduce by one
        self.__perfdatas_cnt[pd_tuple] -= 1
        if not self.__perfdatas_cnt[pd_tuple]:
            # zero reached, reset counter to 10 and send info to local rrd-grapher
            self.__perfdatas_cnt[pd_tuple] = 10
            pd_obj = globals()["%s_pdata" % (mach_values[0])]()
            self._send_to_grapher(pd_obj.build_perfdata_info(mach_values))
    def _handle_machine_vector(self, _xml, data_len):
        self.__trees_read += 1
        self.__total_size_trees += data_len
        simple, host_name, host_uuid, recv_time = (
            _xml.attrib["simple"] == "1",
            _xml.attrib["name"],
            # if uuid is not set use name as uuid (will not be sent to the grapher)
            _xml.attrib.get("uuid", _xml.attrib.get("name")),
            float(_xml.attrib["time"]),
        )
        self.__distinct_hosts_mv.add(host_uuid)
        if simple and host_uuid not in self.__hosts:
            collectd.warning(
                "no full info for host %s (%s) received, discarding data" % (
                    host_name,
                    host_uuid,
                )
            )
            raise StopIteration
        else:
            if not simple:
                self._feed_host_info(host_uuid, host_name, _xml)
            values = self.__hosts[host_uuid].get_values(_xml, simple)
            r_data = (host_name, recv_time, values)
            yield r_data
    def _handle_perf_data(self, _xml, data_len):
        self.__total_size_pds += data_len
        # iterate over lines
        for p_data in _xml:
            self.__pds_read += 1
            perf_value = p_data.get("perfdata", "").strip()
            if perf_value:
                self.__distinct_hosts_pd.add(p_data.attrib["host"])
                mach_values = self._find_matching_pd_handler(p_data, perf_value)
                if len(mach_values):
                    self._check_for_ext_perfdata(mach_values)
                    yield ("pdata", mach_values)
        raise StopIteration
    def _find_matching_pd_handler(self, p_data, perf_value):
        values = []
        for cur_re, re_obj in self.__pd_re_list:
            cur_m = cur_re.match(perf_value)
            if cur_m:
                values.extend(re_obj.build_values(p_data, cur_m.groupdict()))
                # stop loop
                break
        if not values:
            collectd.warning(
                "unparsed perfdata '%s' from %s" % (
                    perf_value,
                    p_data.get("host")
                )
            )
        return values

class receiver(object):
    def __init__(self):
        self.context = zmq.Context()
        self.recv_sock = None
        self.__last_sent = {}
        self.lock = threading.Lock()
    def start_sub_proc(self):
        collectd.notice("start 0MQ process")
        self.sub_proc = net_receiver()
        self.sub_proc.start()
    def init_receiver(self):
        collectd.notice("init 0MQ IPC receiver at %s" % (IPC_SOCK))
        self.recv_sock = self.context.socket(zmq.PULL)
        sock_dir = os.path.dirname(IPC_SOCK[6:])
        if not os.path.isdir(sock_dir):
            collectd.notice("creating directory %s" % (sock_dir))
            os.mkdir(sock_dir)
        self.recv_sock.bind(IPC_SOCK)
    def recv(self):
        self.lock.acquire()
        if self.recv_sock:
            while True:
                try:
                    data = self.recv_sock.recv_pyobj(zmq.DONTWAIT)
                except:
                    break
                else:
                    if data == "stop":
                        collectd.notice("0MQ process exited, closing sockets")
                        self.sub_proc.join()
                        self.recv_sock.close()
                        self.context.term()
                        self.recv_sock = None
                        break
                    else:
                        if len(data) == 3:
                            self._handle_tree(data)
                        else:
                            self._handle_perfdata(data)
        self.lock.release()
    def get_time(self, h_tuple, cur_time):
        cur_time = int(cur_time)
        if h_tuple in self.__last_sent:
            if cur_time <= self.__last_sent[h_tuple]:
                diff_time = self.__last_sent[h_tuple] + 1 - cur_time
                cur_time += diff_time
                collectd.notice("correcting time for %s (+%ds to %d)" % (str(h_tuple), diff_time, int(cur_time)))
        self.__last_sent[h_tuple] = cur_time
        return self.__last_sent[h_tuple]
    def _handle_perfdata(self, data):
        # print "***", data
        _type, type_instance, host_name, time_recv, rsi, v_list = data[1]
        s_time = self.get_time((host_name, "ipd_%s" % (_type)), time_recv)
        collectd.Values(plugin="perfdata", type_instance=type_instance, host=host_name, time=s_time, type="ipd_%s" % (_type), interval=5 * 60).dispatch(values=v_list[rsi:])
    def _handle_tree(self, data):
        host_name, time_recv, values = data
        # print host_name, time_recv
        s_time = self.get_time((host_name, "icval"), time_recv)
        for name, value in values:
            # name can be none for values with transform problems
            if name:
                collectd.Values(plugin="collserver", host=host_name, time=s_time, type="icval", type_instance=name).dispatch(values=[value])

if __name__ != "__main__":
    # Our Own Functions go here
    def configer(ObjConfiguration):
        pass
        # collectd.debug('Configuring Stuff')

    def initer(my_recv):
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        my_recv.init_receiver()
        my_recv.start_sub_proc()

    # == Hook Callbacks, Order is important! ==#

    my_recv = receiver()

    collectd.register_config(configer)
    collectd.register_init(initer, my_recv)
    # call every 15 seconds
    collectd.register_read(my_recv.recv, 15.0)
else:
    out_list = logging_tools.new_form_list()
    out_list.append([
        logging_tools.form_entry("icval"),
        logging_tools.form_entry("v:GAUGE:U:U"),
        ])
    for key in sorted(globals().keys()):
        obj = globals()[key]
        if type(obj) == type and obj != perfdata_object:
            if issubclass(obj, perfdata_object):
                obj = obj()
                out_list.append([
                    logging_tools.form_entry("ipd_%s" % (obj.PD_NAME)),
                    logging_tools.form_entry(" ".join(["%s:%s" % (_e.get("name"), _e.get("rrd_spec")) for _e in obj.default_xml_info.xpath(".//value[@rrd_spec]")])),
                ])
    print unicode(out_list)

