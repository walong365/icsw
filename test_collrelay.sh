#!/bin/bash

./send_command_zmq.py -P ipc -S collrelay -H receiver -v --kv host:localhost --kv port:2001 uptime
