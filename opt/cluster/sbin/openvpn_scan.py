#!/usr/bin/python-init -Otu

import sys
import datetime
import pprint

from initat.tools import process_tools


class vpn_con(object):
    def __init__(self, name, src_ip, src_port):
        self.name = name
        self.ip = src_ip
        self.port = int(src_port)
        self.start_time, self.end_time = (None, None)

    def start(self, start_dt):
        self.start_time = start_dt

    def stop(self, end_dt):
        self.end_time = end_dt

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return u"VPN %s (from %s:%d), %s - %s" % (
            self.name,
            self.ip,
            self.port,
            str(self.start_time) if self.start_time else "not started",
            str(self.end_time) if self.end_time else "not ended",
        )
        

class scan_container(object):
    def __init__(self):
        self.lines = 0
        self.__con_lut = {}
        self.__cur_con = {}
        self.__con_dict = {}

    def feed(self, line):
        self.lines += 1
        parts = line.split()
        try:
            cur_ts = datetime.datetime.strptime(" ".join(parts[:5]), "%a %b %d %H:%M:%S %Y")
        except:
            pass
        else:
            if parts[5].startswith("us="):
                try:
                    content = " ".join(parts[6:])
                    if content.lower().count("peer connection"):
                        self._handle_peer_con(cur_ts, parts[6:])
                    elif content.lower().count("connection reset"):
                        self._close_peer_con(cur_ts, parts[6:])
                    elif content.lower().count("client-instance restarting"):
                        self._close_peer_con(cur_ts, parts[6:])
                    elif content.lower().count("inactivity timeout"):
                        print cur_ts, content
                    elif content.lower().count("restarting"):
                        print cur_ts, content
                except:
                    print "error parsing line %s: %s" % (line, process_tools.get_except_info())

    def _handle_peer_con(self, cur_ts, parts):
        c_name, src_ipp = (parts[1][1:-1], parts[0])
        src_ip, src_port = src_ipp.split(":")
        # self.__con_lut[(src_ip, src_port)] = c_name
        new_con = vpn_con(c_name, src_ip, src_port)
        new_con.start(cur_ts)
        self._add_connection(new_con)

    def _close_peer_con(self, cur_ts, parts):
        c_name, src_ipp = parts[0].split("/")
        src_ip, src_port = src_ipp.split(":")
        self._remove_connection(c_name, src_ip, src_port, cur_ts)

    def _remove_connection(self, c_nmae, src_ip, src_port, cur_ts):
        src_port = int(src_port)
        c_key = (src_ip, src_port)
        if c_key in self.__con_lut:
            self.__con_lut[c_key].stop(cur_ts)
            del self.__con_lut[c_key]
        else:
            print "connection_key %s not found" % (str(c_key))

    def _add_connection(self, n_con):
        self.__con_lut[(n_con.ip, n_con.port)] = n_con
        self.__con_dict.setdefault(n_con.name, []).append(n_con)

    def __unicode__(self):
        return "lines: %d" % (self.lines)

    @property
    def connection_dict(self):
        return self.__con_dict
    

def main():
    f_name = sys.argv[1]
    new_c = scan_container()
    for line in file(f_name, "r").readlines():
        new_c.feed(line.strip())
    pprint.pprint(new_c.connection_dict)

if __name__ == "__main__":
    main()
