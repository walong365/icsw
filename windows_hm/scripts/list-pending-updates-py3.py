import win32com
import win32com.client
import json
import bz2
import base64

if(__name__ == "__main__"):
    update = win32com.client.Dispatch('Microsoft.Update.Session')
    updateSearcher = update.CreateUpdateSearcher()
    
    search_result = updateSearcher.Search("( IsInstalled = 0 and IsHidden = 0 )")
   

   
    update_list = []
    # Update items interface: IUpdate
    for i in range(search_result.Updates.Count):
        title = search_result.Updates.Item(i).Title
        optional = not search_result.Updates.Item(i).IsMandatory
        update_list.append((title, optional))
        
    print(base64.b64encode(bz2.compress(json.dumps(update_list))))