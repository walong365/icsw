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
:moo = scripts\moo.bat
:check_updates=C:\Windows\System32\cscript.exe //T:6000 //NoLogo scripts\\lib\\wrapper.vbs scripts\\check_updates.vbs
:check_printer=C:\Windows\System32\cscript.exe //T:30 //NoLogo scripts\\lib\\wrapper.vbs scripts\\check_printer.vbs
:check_battery=C:\Windows\System32\cscript.exe //T:30 //NoLogo scripts\\lib\\wrapper.vbs scripts\\check_battery.vbs
:check_time=C:\\Windows\System32\cscript.exe //T:30 //NoLogo scripts\\lib\\wrapper.vbs scripts\\op5\\check_time.vbs
:check_files=C:\Windows\System32\cscript.exe //T:30 //NoLogo scripts\\lib\\wrapper.vbs scripts\\check_files.vbs
moo=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list_registry.py
;
list-keys=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-keys.py
list-keys-py3=python\python.exe scripts\python\list-keys-py3.py
;
list-updates=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-updates.py
list-updates-py3=python\python.exe scripts\python\list-updates-py3.py
;
list-updates-alt=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-updates-alt.py
list-updates-alt-py3=python\python.exe scripts\python\list-updates-alt-py3.py
;
list-metrics=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-metrics.py
list-metrics-py3=python\python.exe scripts\python\list-metrics-py3.py
;
list-processes=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-processes.py
list-processes-py3=python\python.exe scripts\python\list-processes-py3.py
;
list-pending-updates=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-pending-updates.py
list-pending-updates-py3=python\python.exe scripts\python\list-pending-updates-py3.py
;
list-software=movpy-2.0.0-py2.5.1\movpy\movpy.exe scripts\python\list-software.py
list-software-py3=python\python.exe scripts\python\list-software-py3.py


;custom python scripts
;test-python = python scripts\python\list_registry.py $ARG1$ $ARG2$
;list-software=python scripts\python\list-software.py
;list-basic-info=python scripts\python\list-basic-info.py
;list-netshares=python scripts\python\list-netshares.py
;list-os-properties=python scripts\python\list-os-properties.py
:list-user-data=python scripts\python\list-user-data.py
:list-registry=python scripts\python\list-registry.py
:list-domain-info=python scripts\python\list-domain-info.py
:check_wmi=python scripts\python\sample\list_all_wmi_objects.py
:list-keys=python scripts\python\list-keys.py
:list-updates=python scripts\python\list-updates.py
:list-updates-alt=python scripts\python\list-updates-alt.py
:list-uptime=python scripts\python\list-uptime.py
:list-metrics=python scripts\python\list-metrics.py
:list-processes=python scripts\python\list-processes.py
:list-pending-updates=python scripts\python\list-pending-updates.py

;[settings/external scripts/wrappings]
;vbs=C:\Windows\System32\cscript.exe //T:30 //NoLogo scripts\lib\wrapper.vbs %SCRIPT% %ARGS%


;[settings/external scripts/wrapped scripts]
;check_updates = script\check_updates.vbs
;check_printer = script\check_printer.vbs
 
;[/settings/external scripts/alias]
;alias_updates=check_updates -warning 0 -critical 0 ShowAll=long
;alias_printer=check_printer -warning 0 -critical 0
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

