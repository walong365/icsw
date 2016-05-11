#    WindowsUpdateHistory
#    Copyright (C) 2015 Alex Richman
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import time
import datetime
import win32com
import win32com.client
import json

def Main():
    #Get raw update data (includes last 10 update history items)
    Process = os.popen("powershell $Ses = New-Object -Com 'Microsoft.Update.Session'; $Sea = $Ses.CreateUpdateSearcher(); $Sea.QueryHistory(0, 200)");
    time.sleep(5);
    RawData = Process.read();

    #Remove spaces
    RawData = RawData.replace(" ", "");

    #Split raw data into update list
    UpdateList = RawData.split("\n\n");

    #Filter empty items
    UpdateList = [Item for Item in UpdateList if Item != ""];

    #Split each update into list
    UpdateList = [Item.split("\n") for Item in UpdateList];

    #Replace date colons with hyphens (avoids parsing errors later on)
    NewUpdateList = [];
    for Update in UpdateList:
        NewUpdate = ["Date:" + Item.replace(":", "-")[5:] for Item in Update if "Date" in Item];
        NewUpdate += [Item for Item in Update if "Date" not in Item];
        NewUpdateList.append(NewUpdate);
        UpdateList = NewUpdateList;

    #Convert each update into dictionary
    NewUpdateList = [];
    for Update in UpdateList:
        UpdateDict = {};

        for Item in Update:
            try:
                Key, Value = Item.split(":");
            except ValueError:
                Value = None;
                pass;

            #Fix date format
            if(Key == "Date"):
                Value = Value[:10] + " " + Value[10:];

            UpdateDict[Key] = Value;

        NewUpdateList.append(UpdateDict);
    UpdateList = NewUpdateList;

    #Get latest date of updates
    DateList = [Item["Date"].split(" ")[0] for Item in UpdateList];
    DateList = sorted(DateList, key=lambda x: datetime.datetime.strptime(x, "%d/%m/%Y"), reverse=True);
    LatestDate = DateList[0];

    #Filter update list on latest date
    UpdateList = [Item for Item in UpdateList if Item["Date"].split(" ")[0] == LatestDate];

    print("Last batch of '{0}' items installed on '{1}'".format(len(UpdateList), LatestDate));

    for Update in UpdateList:
        print("Time:  %s" % Update["Date"]);
        print("Title: %s" % Update["Title"]);


class Update:
    def __init__(self):
        self.title = None
        self.status = None
        self.date = None

    def __cmp__(self, other):
        return cmp(self.date, other.date)


if(__name__ == "__main__"):
    update = win32com.client.Dispatch('Microsoft.Update.Session')
    updateSearcher = update.CreateUpdateSearcher()
    count = updateSearcher.GetTotalHistoryCount()
    
    updateHistory = updateSearcher.QueryHistory(0, count)
  
    updates = []
  
    for i in xrange(updateHistory.Count):
        update = Update()
        update.title = updateHistory.Item(i).Title
        update.date = updateHistory.Item(i).Date
        update.status = updateHistory.Item(i).ResultCode

        if update.status == 0:
            update.status = "NotStarted"
        elif update.status == 1:
            update.status = "InProgress"
        elif update.status == 2:
            update.status = "Succeeded"
        elif update.status == 3:
            update.status = "SucceededWithErrors"
        elif update.status == 4:
            update.status = "Failed"
        elif update.status ==5:
            update.status = "Aborted"


        updates.append(update)


    updates.sort()

    for update in updates:
        print "%s\t%s\t%s" % (update.date, update.title, update.status)