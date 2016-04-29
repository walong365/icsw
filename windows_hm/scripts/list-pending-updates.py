import win32com
import win32com.client

if(__name__ == "__main__"):
    update = win32com.client.Dispatch('Microsoft.Update.Session')
    updateSearcher = update.CreateUpdateSearcher()
    
    search_result = updateSearcher.Search("( IsInstalled = 0 and IsHidden = 0 )")
   
    # Update items interface: IUpdate
    for i in xrange(search_result.Updates.Count):
        print search_result.Updates.Item(i).Title