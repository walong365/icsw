#!/usr/bin/python -Ot

import sys
import os

def main():
    rgb_file="/usr/X11R6/lib/X11/rgb.txt"
    if os.path.isfile(rgb_file):
        cf=open(rgb_file)
        c_lines=dict([("#%02x%02x%02x"%(tuple([int(y) for y in x.strip().split()[0:3]]))," ".join(x.strip().split()[3:]).lower()) for x in cf.readlines()[1:]])
        cf.close()
        i=0
        for k in c_lines.keys():
            i+=1
            print "%3d %12s %s"%(i,k,c_lines[k])
    else:
        print "Cannot read file %s"%(rgb_file)

if __name__=="__main__":
    main()
    
