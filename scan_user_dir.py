#!/usr/bin/python-init -Otu

import os
import stat
import pprint


def sub_sum(_dict):
    _size = _dict.size
    for _key, _value in _dict.iteritems():
        _size += sub_sum(_value)
    return _size


class sub_dir(dict):
    def __init__(self):
        self.size = 0
        dict.__init__(self)


def main():
    _size_dict = sub_dir()
    _start_dir = "/usr/local/share/home/local"
    _top_depth = _start_dir.count("/")
    for _main, _dirs, _files in os.walk(_start_dir):
        _cur_depth = _main.count("/")
        _parts = _main.split("/")
        _max_depth = min(_top_depth + 3, _cur_depth)
        _key = "/".join(_parts[:_max_depth + 1])
        cur_dict = _size_dict
        for _skey in _parts[_top_depth:_max_depth + 1]:
            cur_dict = cur_dict.setdefault(_skey, sub_dir())
        for _file in _files:
            try:
                cur_dict.size += os.stat(os.path.join(_main, _file))[stat.ST_SIZE]
            except:
                pass
    pprint.pprint(_size_dict)
    _tot = sub_sum(_size_dict)
    print _tot

if __name__ == "__main__":
    main()
