#!/usr/bin/python-init -Otu

import commands
import time
import pprint

from initat.tools import process_tools


class IBDataResult(object):
    def __init__(self):
        self.__feed_time = None
        self._data = {}
        self._speed = {}
        self.speed_ok = False

    def feed(self, result):
        cur_time = time.time()
        if self.__feed_time is not None:
            diff_time = abs(cur_time - self.__feed_time)
            self._speed = {
                _key: _value / diff_time for _key, _value in result.iteritems()
            }
            self.speed_ok = True
        else:
            self.speed_ok = False
        self._data = result
        self.__feed_time = cur_time

    def show(self):
        _ret = []
        if self.speed_ok:
            for _key in sorted(self._speed.keys()):
                if self._speed[_key] > 1000:
                    _ret.append("{}={:.2f}".format(_key, self._speed[_key]))
        return ", ".join(_ret) or None


class IBDataStoreDevice(object):
    def __init__(self, guid, name):
        self.guid = guid
        self.name = name
        self.__ports = {}

    def show(self):
        _out = ["{} ({})".format(self.name, self.guid)]
        print " ".join(_out)
        for _port in sorted(self.__ports.keys()):
            _res = self.__ports[_port].show()
            if _res:
                print "   port {}: {}".format(_port, _res)

    def feed(self, key, result):
        _port = key[1]
        if _port not in self.__ports:
            self.__ports[_port] = IBDataResult()
        self.__ports[_port].feed(result)


class IBDataStore(object):
    def __init__(self):
        self.__guids = set()
        self.__devices = {}

    def show(self):
        for _key in sorted(self.__devices):
            self.__devices[_key].show()

    def feed(self, lines):
        self.__target = None
        for _line in lines.split("\n"):
            _line = _line.rstrip()
            if _line and _line[0] != "#":
                if _line.startswith("ibwarn"):
                    print "WARN: {}".format(_line)
                elif _line[0] != " ":
                    self._parse_src(_line)
                else:
                    _key, _result = self._parse_data(_line)
                    if self.__target and _key[0] == self.__target.guid:
                        self.__target.feed(_key, _result)

    def _rewrite_key(self, key):
        _trans = [
            ("port", "Port", True),
            ("data", "Data", False),
            ("pkts", "Pkts", False),
            ("unicast", "Unicast", False),
            ("multicast", "Multicast", False),
            ("xmit", "Xmit", False),
            ("recv", "Rcv", False),
        ]
        for _src, _dst, _ignore in _trans:
            key = key.replace(_dst, "{}.".format(_src))
        _parts = key.split(".")
        key = [_src for _src, _dst, _ignore in _trans if _src in _parts and not _ignore]
        return ".".join(key)

    def _parse_data(self, line):
        _src, _data = [_part.strip() for _part in line.split(":", 1)]
        if _data[0] == "[":
            _data = _data[1:-1]
        _res = {}
        for _part in _data.split("] ["):
            _parts = _part.strip().split()
            _key, _value = (_parts[0], _parts[2])
            _res[self._rewrite_key(_key)] = float(_value)
        _sp = _src.split()
        _key = (_sp[1].lower(), int(_sp[3]))
        return _key, _res

    def _parse_src(self, line):
        self.__target = None
        _parts = line.strip().split(None, 4)
        _guid = _parts[3].lower()
        _name = _parts[4]
        if _name[0] in ["'", '"']:
            _name = _name[1:-1]
        if _guid not in self.__guids:
            self.__guids.add(_guid)
            new_dev = IBDataStoreDevice(_guid, _name)
            self.__devices[_guid] = new_dev
        self.__target = self.__devices[_guid]


def main():
    ibd = IBDataStore()
    while True:
        _cmd = "{} --counters --errors --details -k -K 2>/dev/null".format(process_tools.find_file("ibqueryerrors"))
        _stat, _out = commands.getstatusoutput(_cmd)
        ibd.feed(_out)
        ibd.show()
        time.sleep(2)


if __name__ == "__main__":
    main()
