import win32com.client
import json
import pywintypes


class Update:
    def __init__(self):
        self.title = None
        self.status = None
        self.date = None

    def __lt__(self, other):
        return self.date < other.date
        
    def __eg__(self, other):
        return self.date == other.date


if(__name__ == "__main__"):
    update = win32com.client.Dispatch('Microsoft.Update.Session')
    updateSearcher = update.CreateUpdateSearcher()
    count = updateSearcher.GetTotalHistoryCount()
    
    updateHistory = updateSearcher.QueryHistory(0, count)
  
    updates = []
  
    for i in range(updateHistory.Count):
        update = Update()
        update.title = updateHistory.Item(i).Title
        update.date = updateHistory.Item(i).Date
        try:
            update.status = updateHistory.Item(i).ResultCode
        except pywintypes.com_error:
            update.status = "Unknown"

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
        elif update.status == 5:
            update.status = "Aborted"

        updates.append(update)

    print(json.dumps([(update.title, update.date.isoformat(), update.status) for update in updates]))