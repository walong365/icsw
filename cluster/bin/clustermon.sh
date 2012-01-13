#!/bin/bash

while read line ; do 
    xmessage -nearmouse -buttons ok:0 $line
done < /tmp/bla
