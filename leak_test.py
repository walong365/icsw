#!/usr/bin/python-init -Ot

import cPickle
import pickle
import os
import bz2
import array
import struct
import random

def get_mem_info(pid):
    map_file_name = "/proc/%d/maps" % (pid)
    tot_size = 0
    if os.path.isfile(map_file_name):
        map_lines = [[y.strip() for y in x.strip().split()] for x in  file(map_file_name, "r").read().split("\n") if x.strip()]
        tot_size = 0
        for map_p in map_lines:
            mem_start, mem_end = map_p[0].split("-")
            mem_start, mem_end = (int(mem_start, 16),
                                  int(mem_end  , 16))
            mem_size = mem_end - mem_start
            perm, offset, dev, inode = (map_p[1], int(map_p[2], 16), map_p[3], int(map_p[4]))
            if not inode:
                tot_size += mem_size
    return tot_size

def main():
    def my_iter(in_dict):
        num_ints = 0
        if type(in_dict) == type({}):
            for k, v in in_dict.iteritems():
                if type(k) == type(0):
                    num_ints += 1
                num_ints += my_iter(v)
        elif type(in_dict) == type([]):
            for v in in_dict:
                num_ints += my_iter(v)
        elif type(in_dict) == type(()):
            for v in in_dict:
                num_ints += my_iter(v)
        elif type(in_dict) == type(""):
            pass
        elif type(in_dict) == type(0):
            num_ints += 1
        else:
            print type(in_dict)
            pass #print "value", in_dict
        
        return num_ints
    fname = ".scan_struct.bz2"
    print get_mem_info(os.getpid())
    in_str = []
    bz2_f = bz2.BZ2File(fname, "r", 16000)
    while True:
        in_str.append(bz2_f.read(16000))
        if not in_str[-1]:
            break
    print "strlen:", sum([len(x) for x in in_str]), len(in_str)
    r_str = "".join(in_str)
    a = cPickle.loads(r_str)
    del in_str
    del r_str
    num_ints = my_iter(a)
    print "ints:", num_ints * 12
    del a
    print get_mem_info(os.getpid())

class my_class:
    def __init__(self):
        self.__array = array.array("i")
        for i in xrange(100):
            self.__array.append(i)
    def __del__(self):
        del self.__array
        
def main2():
    i_mem = get_mem_info(os.getpid())
    f = []
    num_i = 2000
    for j in xrange(num_i):
        f.append(my_class())
    print "-"
    print get_mem_info(os.getpid()) - i_mem
    del f
    mem_d = get_mem_info(os.getpid()) - i_mem
    print mem_d, mem_d / num_i
    
def main3():
    print get_mem_info(os.getpid())
    t_len = 10000
    for q in xrange(40):
##         # struct stuff
        s_fmt = "l" * t_len
        l = [random.randint(1,2000) for x in xrange(t_len)]
        print len(l)
        print "0", get_mem_info(os.getpid()), struct.calcsize(s_fmt)
        c_str = struct.pack(s_fmt, *l)
        print len(c_str)
        print "1", get_mem_info(os.getpid())
        a_r = struct.unpack(s_fmt, c_str)
        print "2", get_mem_info(os.getpid())
        del c_str
        del a_r
        print "3", get_mem_info(os.getpid())
    # cPickle stuff
##         a = dict([(x, x**2) for x in xrange(t_len)])
##         print "0", get_mem_info(os.getpid())
##         c_str = cPickle.dumps(a)
##         print "1", get_mem_info(os.getpid())
##         a_r = cPickle.loads(c_str)
##         del c_str
##         del a_r
##         print "2", get_mem_info(os.getpid())
##         del a
##         print "3", get_mem_info(os.getpid())
    
if __name__ == "__main__":
    main3()
    
