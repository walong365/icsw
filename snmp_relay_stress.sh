#!/bin/bash

while true ; do 
    ./csnmpclient -t 30 -m 192.168.1.228 eonstor_info > /dev/null
    ./csnmpclient > /dev/null
done
