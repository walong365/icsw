import sys
import _winreg
import win32com.client

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
    key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, key)

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


if __name__=="__main__":
    try:
        print "Internet Explorer: %s" % GetIEKey()
    except:
        pass

    try:
        print "Windows NT: %s" % GetNTKey()
    except:
        pass

    try:
        print "Windows NT (DefaultProductKey): %s" % GetDefaultKey()
    except:
        pass
    try:
        print "Microsoft SQL Server: %s" % GetSQLKey()
    except:
        pass
