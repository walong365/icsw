import win32com.client 
from collections import OrderedDict
import sys
sys.path.append('"C:\\Python27_x86"')
strComputer = "." 
objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator") 
objSWbemServices = objWMIService.ConnectServer(strComputer,"root\cimv2") 
colItems = objSWbemServices.ExecQuery("Select * from Win32_Product")


f = open("C:/tmp.txt", "w")

 
for objItem in colItems:
    #print "Caption: ", objItem.Caption
    f.write("Caption: %s\n" % objItem.Caption)
    #print "Description: ", objItem.Description
    f.write("Description: %s\n" % objItem.Description) 
    #print "Identifying Number: ", objItem.IdentifyingNumber
    f.write("Identifying Number: %s\n" % objItem.IdentifyingNumber)
    #print "Install Date: ", objItem.InstallDate
    f.write("Install Date: %s\n" % objItem.InstallDate)
    #print "Install Date 2: ", objItem.InstallDate2
    f.write("Install Date 2: %s\n" % objItem.InstallDate2)
    #print "Install Location: ", objItem.InstallLocation
    f.write("Install Location: %s\n" % objItem.InstallLocation) 
    #print "Install State: ", objItem.InstallState 
    #print "Name: ", objItem.Name
    f.write("Name: %s\n" % objItem.Name)
    #print "Package Cache: ", objItem.PackageCache 
    #print "SKU Number: ", objItem.SKUNumber 
    #print "Vendor: ", objItem.Vendor 
    #print "Version: ", objItem.Version
    f.write("\n")

f.close()
print "ok"
 




