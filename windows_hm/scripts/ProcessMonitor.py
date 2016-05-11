from multiprocessing.connection import Listener

import win32pdh

counter_english_map = {}
def find_pdh_counter_localized_name(english_name, machine_name = None):
    if not counter_english_map:
        import win32api, win32con
        counter_reg_value = win32api.RegQueryValueEx(win32con.HKEY_PERFORMANCE_DATA,
                                                     "Counter 009")
        counter_list = counter_reg_value[0]
        for i in range(0, len(counter_list) - 1, 2):
            try:
                counter_id = int(counter_list[i])
            except ValueError:
                continue
            counter_english_map[counter_list[i+1].lower()] = counter_id
    return win32pdh.LookupPerfNameByIndex(machine_name, counter_english_map[english_name.lower()])

    
def GetProcessID( name ) :
    object = find_pdh_counter_localized_name("Process")

    hq = win32pdh.OpenQuery()
    item = "ID Process"
    path = win32pdh.MakeCounterPath( ( None, object, name, None, 0, item ) )
    hcs.append( win32pdh.AddCounter( hq, path ) )
    win32pdh.CollectQueryData( hq )
    time.sleep( 0.01 )
    win32pdh.CollectQueryData( hq )

    for hc in hcs:
        type, val = win32pdh.GetFormattedCounterValue( hc, win32pdh.PDH_FMT_LONG )
        win32pdh.RemoveCounter( hc )
    win32pdh.CloseQuery( hq )
    return val
    
    
import time
def monitor(name, instance_id):
    object = find_pdh_counter_localized_name("Process")
    
    print(name)
    print(instance_id)
    
    path = win32pdh.MakeCounterPath( (None, object, name, None, instance_id, "Page Faults/sec") )
    hq = win32pdh.OpenQuery()
    try:
        hc = win32pdh.AddCounter(hq, path)
        while True:
            win32pdh.CollectQueryData(hq)
            time.sleep(1)
            win32pdh.CollectQueryData(hq)
            type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG,)
    finally:
        win32pdh.RemoveCounter(hc)
        win32pdh.CloseQuery(hq)
    
import threading
if __name__=="__main__":
    object = find_pdh_counter_localized_name("Process")
    counter_names, process_instances = win32pdh.EnumObjectItems(None, None, object, win32pdh.PERF_DETAIL_WIZARD)
    
    for pn in process_instances:
        print(pn)
        t = threading.Thread(target=monitor, args=[pn, 0])
        t.start()
    
    
    # address = ('localhost', 6000)     # family is deduced to be 'AF_INET'
    # listener = Listener(address)
    # conn = listener.accept()
    # print('connection accepted from', listener.last_accepted)
    # while True:
        # msg = conn.recv()
        # print(msg)
        #do something with msg
        # if msg == 'close':
            # conn.close()
            # break
    # listener.close()