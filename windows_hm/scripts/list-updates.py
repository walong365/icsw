#---------------------------------------
# FileTime Handling
#---------------------------------------
#
# Copyright (c) 2009, David Buxton <david@gasmark6.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""Tools to convert between Python datetime instances and Microsoft times.
"""
from datetime import datetime, timedelta, tzinfo
from calendar import timegm


# http://support.microsoft.com/kb/167296
# How To Convert a UNIX time_t to a Win32 FILETIME or SYSTEMTIME
EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
HUNDREDS_OF_NANOSECONDS = 10000000


ZERO = timedelta(0)
HOUR = timedelta(hours=1)


class UTC(tzinfo):
    """UTC"""
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


utc = UTC()


def dt_to_filetime(dt):
    """Converts a datetime to Microsoft filetime format. If the object is
    time zone-naive, it is forced to UTC before conversion.

    >>> "%.0f" % dt_to_filetime(datetime(2009, 7, 25, 23, 0))
    '128930364000000000'

    >>> "%.0f" % dt_to_filetime(datetime(1970, 1, 1, 0, 0, tzinfo=utc))
    '116444736000000000'

    >>> "%.0f" % dt_to_filetime(datetime(1970, 1, 1, 0, 0))
    '116444736000000000'
    
    >>> dt_to_filetime(datetime(2009, 7, 25, 23, 0, 0, 100))
    128930364000001000
    """
    if (dt.tzinfo is None) or (dt.tzinfo.utcoffset(dt) is None):
        dt = dt.replace(tzinfo=utc)
    ft = EPOCH_AS_FILETIME + (timegm(dt.timetuple()) * HUNDREDS_OF_NANOSECONDS)
    return ft + (dt.microsecond * 10)


def filetime_to_dt(ft):
    """Converts a Microsoft filetime number to a Python datetime. The new
    datetime object is time zone-naive but is equivalent to tzinfo=utc.

    >>> filetime_to_dt(116444736000000000)
    datetime.datetime(1970, 1, 1, 0, 0)

    >>> filetime_to_dt(128930364000000000)
    datetime.datetime(2009, 7, 25, 23, 0)
    
    >>> filetime_to_dt(128930364000001000)
    datetime.datetime(2009, 7, 25, 23, 0, 0, 100)
    """
    # Get seconds and remainder in terms of Unix epoch
    (s, ns100) = divmod(ft - EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS)
    # Convert to datetime object
    dt = datetime.utcfromtimestamp(s)
    # Add remainder in as microseconds. Python 3.2 requires an integer
    dt = dt.replace(microsecond=(ns100 // 10))
    return dt


import sys
import _winreg
import win32com.client
import struct


def KB958644(OS, servername):
   HKLM_remote = _winreg.ConnectRegistry (r"\\%s" % servername, _winreg.HKEY_LOCAL_MACHINE)
   KEY_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\KB958644"
   ValueName = 'InstallDate'
   hKeyRemote = _winreg.OpenKey (HKLM_remote, KEY_PATH, 0, _winreg.KEY_READ)
   value, type = _winreg.QueryValueEx (hKeyRemote, ValueName)
   print 'KB958644: ', value
   return value 


def regkey_value(path, name="", start_key = None):
    if isinstance(path, str):
        path = path.split("\\")
    if start_key is None:
        start_key = getattr(_winreg, path[0])
        return regkey_value(path[1:], name, start_key)
    else:
        subkey = path.pop(0)
    with _winreg.OpenKey(start_key, subkey) as handle:
        assert handle
        if path:
	    print handle
            return regkey_value(path, name, handle)
        else:
            desc, i = None, 0
            while not desc or desc[0] != name:
                desc = _winreg.EnumValue(handle, i)
                i += 1
            return desc[1]

def main(key_arg, start_key_arg):
    print key_arg, start_key_arg
    print regkey_value(r"%s" % (key_arg), start_key_arg)


def regtest(): 
    explorer = _winreg.OpenKey(
        _winreg.HKEY_LOCAL_MACHINE,
        "SOFTWARE\\Microsoft\\Microsoft SQL Server\\100\\BIDS\\Setup"
        )

    # list values owned by this registry key
    try:
        i = 0
        while 1:
            name, value, type = _winreg.EnumValue(explorer, i)
            if repr(name) == "'DigitalProductID'":
                print repr(name)
                print repr(value)
                #print repr(type)
            i += 1
    except WindowsError:
        print

    #value, type = _winreg.QueryValueEx(explorer, "Logon User Name")

    print
    #print "user is", repr(value)


def subkeys(key):
    i = 0
    while True:
        try:
            subkey = _winreg.EnumKey(key, i)
            yield subkey
            i+=1
        except WindowsError as e:
            break

def traverse_registry_tree(hkey, keypath, tabs=0):
    key = _winreg.OpenKey(hkey, keypath, 0, _winreg.KEY_READ)
    for subkeyname in subkeys(key):
        print '\t'*tabs + subkeyname
        subkeypath = "%s\\%s" % (keypath, subkeyname)
        traverse_registry_tree(hkey, subkeypath, tabs+1)

def DecodeKey(rpk):
    rpkOffset = 52
    i = 28
    szPossibleChars = "BCDFGHJKMPQRTVWXY2346789"
    szProductKey = ""
    
    while i >= 0:
        dwAccumulator = 0
        j = 14
        while j >= 0:
            dwAccumulator = dwAccumulator * 256
            d = rpk[j+rpkOffset]
            if isinstance(d, str):
                d = ord(d)
            dwAccumulator = d + dwAccumulator
            rpk[j+rpkOffset] =  (dwAccumulator / 24) if (dwAccumulator / 24) <= 255 else 255 
            dwAccumulator = dwAccumulator % 24
            j = j - 1
        i = i - 1
        szProductKey = szPossibleChars[dwAccumulator] + szProductKey
        
        if ((29 - i) % 6) == 0 and i != -1:
            i = i - 1
            szProductKey = "-" + szProductKey
            
    return szProductKey

def GetKeyFromRegLoc(key, value="DigitalProductID"):
    key = _winreg.OpenKey(
    _winreg.HKEY_LOCAL_MACHINE,key)

    value, type = _winreg.QueryValueEx(key, value)
    
    return DecodeKey(list(value))

def GetIEKey():
    return GetKeyFromRegLoc("SOFTWARE\Microsoft\Internet Explorer\Registration")

def GetNTKey():
    return GetKeyFromRegLoc("SOFTWARE\Microsoft\Windows NT\CurrentVersion")

def GetSQLKey():
    return GetKeyFromRegLoc("SOFTWARE\\Microsoft\\Microsoft SQL Server\\100\\DTS\\Setup")

def GetSQLKey2():
    return GetKeyFromRegLoc("SOFTWARE\\Microsoft\\Microsoft SQL Server\\100\\BIDS\\Setup")

def GetDefaultKey():
    return GetKeyFromRegLoc("SOFTWARE\Microsoft\Windows NT\CurrentVersion\DefaultProductKey")


PACKAGE_PATH = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\Packages"


class Package:
    def __init__(self):
        self.installTimeHigh = None
        self.installTimeLow  = None
        self.installTime     = None
        self.installClient   = None
        self.currentState    = None
        self.installName     = None
        self.keyName         = None

import re 

if __name__=="__main__":
    key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, PACKAGE_PATH, 
                          0, _winreg.KEY_READ | _winreg.KEY_WOW64_64KEY)

    packages = {}
    package_names = []
    package_names_package_dict = {}

    i = 0
    while True:
        try:
            subkey_str = _winreg.EnumKey(key, i)
            subkey = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, PACKAGE_PATH + "\\" + subkey_str, 
                          0, _winreg.KEY_READ | _winreg.KEY_WOW64_64KEY)
            i += 1

            #print subkey_str
            
            package = Package()
            package.keyName = subkey_str

            package_names.append(subkey_str)


            j = 0
            while True:
                try:
                    subvalue = _winreg.EnumValue(subkey, j)
                    j += 1

                    _val, _data, _type = subvalue
                    if _val == "InstallTimeHigh":
                        package.installTimeHigh = _data
                    elif _val == "InstallTimeLow":
                        package.installTimeLow = _data
                    elif _val == "InstallClient":
                        package.installClient = _data
                    elif _val == "InstallName":
                        package.installName = _data
                    elif _val == "CurrentState":
                        package.currentState = _val

                    #print "%s: %s" % (_val, _data)
                except WindowsError as e:
                    break

            if package.installTimeHigh and package.installTimeLow:
                ft = "%x:%x" % (package.installTimeLow, package.installTimeHigh)
                h2, h1 = [int(h, base=16) for h in ft.split(':')]
                ft_dec = struct.unpack('>Q', struct.pack('>LL', h1, h2))[0]
                package.installTime = filetime_to_dt(ft_dec)
                if package.installTime == None:
                    print "xxx"
                
                if package.installTime not in packages:
                    packages[package.installTime] = []

                packages[package.installTime].append(package)

            package_names_package_dict[subkey_str] = package
 
              
        except WindowsError as e:
            break


    #for _name in package_names:
    #    kb = "3135996"
    #    if kb in _name:
    #        print _name
    
    kb_db = {}
    matcher = re.compile(".*(KB\d+).*")
    
    for _name in package_names:
        match = matcher.match(_name)
        if match:
            kbname = match.group(1)
            kb_db[kbname] = []


    for _k in kb_db:
        for _name in package_names:
            if _k in _name:
                kb_db[_k].append(package_names_package_dict[_name])

    
    time_kb_dict = {} 
    
    for _k in kb_db:
        _installTime = "Unknown"
        for _package in kb_db[_k]:
            if _package.installTime:
                _installTime = _package.installTime

        time_kb_dict[str(_installTime)] = _k

    time_kb_dict_keys = time_kb_dict.keys()
  
    f = open("C:/tmp.txt", "w")
    time_kb_dict_keys.sort()
    for _t in reversed(time_kb_dict_keys):
        print "%s: %s" % (_t, time_kb_dict[_t])    
 
        #f.write("%s: %s\n" % (_t, time_kb_dict[_t]))

    f.close()

    #timekeys = packages.keys()
    #timekeys.sort()
    #print timekeys[-10]
    #print packages[timekeys[-10]][0].keyName
    #print
    #print timekeys[-11]
    #print packages[timekeys[-11]][0].keyName

