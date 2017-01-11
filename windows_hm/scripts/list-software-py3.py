import winreg
import json
from common import nrpe_encode


UNINSTALL_PATH1 = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
UNINSTALL_PATH2 = "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"

class Package:
    def __init__(self):
        self.displayName = "Unknown"
        self.displayVersion = "Unknown"
        self.estimatedSize = "Unknown"
        self.installDate = "Unknown"
        
    def __lt__(self, other):
        return self.displayName < other.displayName
    
    def __eq__(self, other):
        return self.displayName == other.displayName

    def __hash__(self):
        return hash((self.displayName, self.displayVersion, self.estimatedSize, self.installDate))

def get_installed_packages_for_keypath(keypath):
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, keypath, 0, winreg.KEY_READ)
    
    packages = []
    
    i = 0
    
    while True:
        try:
            subkey_str = winreg.EnumKey(key, i)
            i += 1
            subkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, keypath + "\\" + subkey_str, 
                          0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            #print subkey_str

            j = 0

            package = Package()
            while True:
                try:
                    subvalue = winreg.EnumValue(subkey, j)
                    j += 1

                    _val, _data, _type = subvalue

                    _data = str(_data).split("\\u0000")[0]

                    if _val == "DisplayName":
                        package.displayName = _data
                    elif _val == "DisplayVersion":
                        package.displayVersion = _data
                    elif _val == "EstimatedSize":
                        package.estimatedSize = _data
                    elif _val == "InstallDate":
                        package.installDate = _data

                except WindowsError as e:
                    break

            if package.displayName != "Unknown":
                packages.append(package)
                
        except WindowsError as e:
            break

    return packages 

if __name__=="__main__":
    package_list1 = get_installed_packages_for_keypath(UNINSTALL_PATH1)
    package_list2 = get_installed_packages_for_keypath(UNINSTALL_PATH2)
    package_list1.extend(package_list2)

    package_list = list(set(package_list1))

    package_list.sort()

    output = json.dumps([(package.displayName, package.displayVersion, package.estimatedSize, package.installDate) for package in package_list])
    print((nrpe_encode(output)))
