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
import winreg
import struct





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
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PACKAGE_PATH, 
                          0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)

    packages = {}
    package_names = []
    package_names_package_dict = {}

    i = 0
    while True:
        try:
            subkey_str = winreg.EnumKey(key, i)
            subkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, PACKAGE_PATH + "\\" + subkey_str, 
                          0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            i += 1

            #print subkey_str
            
            package = Package()
            package.keyName = subkey_str

            package_names.append(subkey_str)


            j = 0
            while True:
                try:
                    subvalue = winreg.EnumValue(subkey, j)
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
                    print("xxx")
                
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
  
    for _t in reversed(sorted(time_kb_dict_keys)):
        print("{}: {}".format(_t, time_kb_dict[_t]))

