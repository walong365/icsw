import sys
import time

INI_DATA = """# If you want to fill this file with all avalible options run the following command:
#   nscp settings --generate --add-defaults --load-all
# If you want to activate a module and bring in all its options use:
#   nscp settings --activate-module <MODULE NAME> --add-defaults
# For details run: nscp settings --help


; Undocumented section
[/settings/default]
allowed hosts = 192.168.1.193,192.168.1.48,127.0.0.1,192.168.1.0/24,192.168.1.178
allowed ciphers = ALL:!ADH:!LOW:!EXP:!MD5:@STRENGTH
timeout=6000
command_timeout=6000

; Undocumented key
port = 12489


; Undocumented section
[/modules]
NRPEServer = 1
check_nrpe = enabled
;NSClientServer = enabled
;NSCAServer=enabled
;PythonScript=enabled


; Undocumented key
CheckExternalScripts = 1

; Undocumented key
CheckHelpers = 1

; Undocumented key
CheckEventLog = 1

; Undocumented key
CheckNSCP = 1

; Undocumented key
CheckDisk = 1

; Undocumented key
CheckSystem = 1


[/settings/external scripts]
allow arguments = true
allow nasty characters =true
timeout = 6000
command_timeout=6000


[/settings/external scripts/scripts]
timeout=6000
command_timeout=6000
list-keys-py3=python\python.exe scripts\python\list-keys-py3.py
;
list-updates-py3=python\python.exe scripts\python\list-updates-py3.py
;
list-updates-alt-py3=python\python.exe scripts\python\list-updates-alt-py3.py
;
list-metrics-py3=python\python.exe scripts\python\list-metrics-py3.py
;
list-processes-py3=python\python.exe scripts\python\list-processes-py3.py
;
list-pending-updates-py3=python\python.exe scripts\python\list-pending-updates-py3.py
;
list-software-py3=python\python.exe scripts\python\list-software-py3.py
;
list-hardware-py3=python\python.exe scripts\python\list-hardware-py3.py
;
list-hardware-lstopo-py3=python\python.exe scripts\python\list-hardware-lstopo-py3.py
;
dmiinfo=python\python.exe scripts\python\list-dmiinfo-py3.py

[NRPE]
timeout=6000
command_timeout=6000

;[settings/NRPE/server]
;timeout=6000
;command_timeout=6000
;allow arguments = 1
;allow nasty characters = 1
;allowed hosts = 127.0.0.1,192.168.1.193,192.168.1.48
;port = 5666
;cache allowed hosts = 1
;use ssl = 1




[/settings/log]
file name = nsclient.log
level = debug


; Undocumented section
[/settings/NRPE/server]

; Undocumented key
verify mode = none

; Undocumented key
insecure = true
allow arguments = true
allow nasty characters = true
payload length = 1048576
use ssl = false"""

if __name__=="__main__":
    hostnames = sys.argv[1]
    ports     = sys.argv[2]
    servicename = sys.argv[3]

    lines = INI_DATA.split("\n")

    f = open("nsclient.ini", "w")
    
    for line in lines:
        if line.startswith("allowed hosts"):
            f.write("allowed hosts = {}".format(hostnames))
        else:
            f.write(line)
    
        f.write("\r\n")

    f.close()

