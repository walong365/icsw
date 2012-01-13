#!/bin/bash

./test_client.py 172.17.5.204reboot
./test_client.py 172.17.5.204boot_maint
./test_client.py 172.17.5.204jump_to_normal_system
./test_client.py 172.17.5.204up_3
