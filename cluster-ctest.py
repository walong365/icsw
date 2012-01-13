#!/usr/bin/python-init -Ot

import sys

def file_del(name):
    print "file_del(%s)"%(name)

def main():
    test_lines=open("test.py","r").read()
    code=compile(test_lines,"<string>","exec")
    conf_dict={"d":4}
    exec code
    print "..."
    
if __name__=="__main__":
    main()
    
