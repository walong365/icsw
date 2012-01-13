#!/usr/bin/python -Ot

import sys,string,types

def main():
    aerror="aerror"
    try:
        #raise aerror,("o-j","o-j")
        raise aerror,"o-j"
    except aerror,what:
        print type(what)
        print "E:",what
        
if __name__=="__main__":
    main()
    
