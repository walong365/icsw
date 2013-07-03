#!/usr/bin/python-init -Otu

import time
import signal
import zmq
import threading
import multiprocessing
import collectd
import uuid_tools
import logging_tools
import process_tools
import server_command
from lxml import etree

IPC_SOCK = "ipc:///var/log/cluster/sockets/collect"
RECV_PORT = 8002
GRAPHER_PORT = 8003

class value(object):
    def __init__(self, name):
        self.name = name
        self.sane_name = self.name.replace("/", "_sl_")
    def update(self, entry):
        self.info = entry.attrib["info"]
        self.v_type = entry.attrib["v_type"]
        self.unit = entry.get("unit", "1")
        self.base = int(entry.get("base", "1"))
        self.factor = int(entry.get("factor", "1"))
    def transform(self, value):
        return value * self.factor

class host_info(object):
    def __init__(self, uuid, name):
        collectd.notice("init host_info for %s (%s)" % (name, uuid))
        self.name = name
        self.uuid = uuid
        self.__dict = {}
    def update(self, _xml):
        old_keys = set(self.__dict.keys())
        for entry in _xml.findall("mve"):
            cur_name = entry.attrib["name"]
            if cur_name not in self.__dict:
                self.__dict[cur_name] = value(cur_name)
            self.__dict[cur_name].update(entry)
        new_keys = set(self.__dict.keys())
        c_keys = old_keys ^ new_keys
        if c_keys:
            del_keys = old_keys - new_keys
            for del_key in del_keys:
                del self.__dict[del_key]
            collectd.warning("%s changed for %s" % (logging_tools.get_plural("key", len(c_keys)), self.name))
            return True
        else:
            return False
    def transform(self, key, value):
        if key in self.__dict:
            try:
                return (
                    self.__dict[key].sane_name,
                    self.__dict[key].transform(value),
                )
            except:
                collectd.error("error transforming %s: %s" % (key, process_tools.get_except_info()))
                return (None, None)
        else:
            # key not known, skip
            return (None, None)
    def get_values(self, _xml, simple):
        if simple:
            tag_name, name_name, value_name = ("m", "n", "v")
        else:
            tag_name, name_name, value_name = ("mve", "name", "value")
        values = [self.transform(entry.attrib[name_name], float(entry.attrib[value_name])) for entry in _xml.findall(tag_name)]
        return values
        
class net_receiver(multiprocessing.Process):
    def __init__(self):
        multiprocessing.Process.__init__(self, target=self._code, name="0MQ_net_receiver")
        self.zmq_id = "%s:collserver_plugin" % (process_tools.get_machine_name())
        self.grapher_id = "%s:rrd_grapher" % (uuid_tools.get_uuid().get_urn())
    def _init(self):
        self._init_vars()
        self._init_hosts()
        self._init_sockets()
    def _init_sockets(self):
        self.context = zmq.Context()
        self.receiver = self.context.socket(zmq.PULL)
        self.sender   = self.context.socket(zmq.PUSH)
        self.grapher  = self.context.socket(zmq.ROUTER)
        # set grapher flags
        for flag, value in [
            (zmq.IDENTITY, self.zmq_id),
            (zmq.SNDHWM, 256),
            (zmq.RCVHWM, 256),
            (zmq.TCP_KEEPALIVE, 1),
            (zmq.TCP_KEEPALIVE_IDLE, 300)]:
            self.grapher.setsockopt(flag, value)
        self.sender.connect(IPC_SOCK)
        self.receiver.bind("tcp://*:%d" % (RECV_PORT))
        self.grapher.connect("tcp://localhost:%d" % (GRAPHER_PORT))
        collectd.notice("listening on port %d" % (RECV_PORT))
    def _init_hosts(self):
        self.__hosts = {}
    def _init_vars(self):
        self.__start_time = time.time()
        self.__trees_read = 0
        self.__total_size = 0
        self.__distinct_hosts = set()
    def _close(self):
        self._log_stats()
        self._close_sockets()
    def _close_sockets(self):
        self.sender.close()
        self.receiver.close()
        self.grapher.close()
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
        b_rate = self.__trees_read / max(1, abs(self.__end_time - self.__start_time))
        s_rate = self.__total_size / max(1, abs(self.__end_time - self.__start_time))
        collectd.notice("read %s (%s) from %s in %s (rate [%.2f, %s] / sec)" % (
            logging_tools.get_plural("tree", self.__trees_read),
            logging_tools.get_size_str(self.__total_size),
            logging_tools.get_plural("host", len(self.__distinct_hosts)),
            logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
            b_rate,
            logging_tools.get_size_str(s_rate),
        ))
        self._init_vars()
    def _send(self, send_xml):
        self.grapher.send_unicode(self.grapher_id, zmq.SNDMORE)
        self.grapher.send_unicode(unicode(send_xml))
    def _loop(self):
        while True:
            in_data = self.receiver.recv()
            self.__trees_read += 1
            self.__total_size += len(in_data)
            p_data = self._process_tree(in_data)
            if p_data is not None:
                self.sender.send_pyobj(p_data)
            if abs(time.time() - self.__start_time) > 300:
                # periodic log stats
                self._log_stats()
    def _feed_host_info(self, host_uuid, host_name, _xml):
        if host_uuid not in self.__hosts:
            self.__hosts[host_uuid] = host_info(host_uuid, host_name)
        if self.__hosts[host_uuid].update(_xml):
            # something changed
            new_com = server_command.srv_command(command="mv_info")
            new_com["vector"] = _xml
            self._send(new_com)
    def _process_tree(self, in_tree):
        r_data = None
        # adopt tree format for faster handling in collectd loop
        try:
            _xml = etree.fromstring(in_tree)
        except:
            collectd.error("cannot parse tree: %s" % (process_tools.get_except_info()))
        else:
            simple, host_name, host_uuid, recv_time = (
                _xml.attrib["simple"] == "1",
                _xml.attrib["name"],
                # if uuid is not set use name as uuid (will not be sent to the grapher)
                _xml.attrib.get("uuid", _xml.attrib.get("name")),
                float(_xml.attrib["time"]),
            )
            self.__distinct_hosts.add(host_uuid)
            if simple and host_uuid not in self.__hosts:
                collectd.warning("no full info for host %s (%s) received, discarding data" % (
                    host_name,
                    host_uuid,
                ))
            else:
                if not simple:
                    self._feed_host_info(host_uuid, host_name, _xml)
                values = self.__hosts[host_uuid].get_values(_xml, simple)
                r_data = (host_name, recv_time, values)
        return r_data
    
class receiver(object):
    def __init__(self):
        self.context = zmq.Context()
        self.recv_sock = None
        self.lock = threading.Lock()
    def start_sub_proc(self):
        collectd.notice("start 0MQ process")
        self.sub_proc = net_receiver()
        self.sub_proc.start()
    def init_receiver(self):
        collectd.notice("init 0MQ IPC receiver at %s" % (IPC_SOCK))
        self.recv_sock = self.context.socket(zmq.PULL)
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
                        self._handle_tree(data)
        self.lock.release()
    def _handle_tree(self, data):
        host_name, time_recv, values = data
        #vl.plugin = "collserver"
        #vl.host = host_name
        #vl.time = time_recv
        #vl.type = "icval"
        for name, value in values:
            # name can be none for values with transform problems
            if name:
                vl = collectd.Values(plugin="collserver", host=host_name, time=time_recv, type="icval", type_instance=name)
                vl.dispatch(values=[value])
        
#== Our Own Functions go here: ==#
def configer(ObjConfiguration):
    pass
    #collectd.debug('Configuring Stuff')

def initer(my_recv):
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    my_recv.init_receiver()
    my_recv.start_sub_proc()

#== Hook Callbacks, Order is important! ==#

my_recv = receiver()

collectd.register_config(configer)
collectd.register_init(initer, my_recv)
# call every 15 seconds
collectd.register_read(my_recv.recv, 15.0)
