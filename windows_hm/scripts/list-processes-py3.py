import win32pdhutil
import win32pdh

import io
import sys
import time

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

def ShowAllProcesses():
    object = find_pdh_counter_localized_name("Process")
    items, instances = win32pdh.EnumObjectItems(None,None,object,
                                                win32pdh.PERF_DETAIL_WIZARD)
    # Need to track multiple instances of the same name.
    instance_dict = {}
    for instance in instances:
        try:
            instance_dict[instance] = instance_dict[instance] + 1
        except KeyError:
            instance_dict[instance] = 0
			
    # Bit of a hack to get useful info.
    items = [find_pdh_counter_localized_name("ID Process")] + items[:5]
    print("Process Name", ",".join(items))
    for instance, max_instances in instance_dict.items():
        for inum in range(max_instances+1):
            hq = win32pdh.OpenQuery()
            hcs = []
            for item in items:
                print(item)
                print(inum)
                print(instance)
                path = win32pdh.MakeCounterPath( (None,object,instance,
                                                  None, inum, item) )
                hcs.append(win32pdh.AddCounter(hq, path))
            win32pdh.CollectQueryData(hq)
            # as per http://support.microsoft.com/default.aspx?scid=kb;EN-US;q262938, some "%" based
            # counters need two collections
            time.sleep(0.01)
            win32pdh.CollectQueryData(hq)
            print("%-15s\t" % (instance[:15]), end=' ')
            for hc in hcs:
                type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
                print("%5d" % (val), end=' ')
                win32pdh.RemoveCounter(hc)
            print()
            win32pdh.CloseQuery(hq)

import time
def main():
	time.sleep(10)
    
import multiprocessing
import json
from multiprocessing.connection import Client

if __name__=="__main__":
    object = find_pdh_counter_localized_name("Process")
    counter_names, process_instances = win32pdh.EnumObjectItems(None, None, object, win32pdh.PERF_DETAIL_WIZARD)
    
    # for _counter in counter_names:
        # print("Counter: {}".format(_counter))
        
    # for _process in process_instances:
        # print("Process: {}".format(_process))
        
    instance_dict = {}
    for process_instance in process_instances:
        try:
            instance_dict[process_instance] = instance_dict[process_instance] + 1
        except KeyError:
            instance_dict[process_instance] = 0
            
    pname_pid_list = []
    for instance_name, instance_count in instance_dict.items():
        for instance_number in range(instance_count + 1):
            hq = win32pdh.OpenQuery()
            path = win32pdh.MakeCounterPath((None, object, instance_name, None, instance_count, "ID Process"))
            hc = win32pdh.AddCounter(hq, path)
            win32pdh.CollectQueryData(hq)
            type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
            pname_pid_list.append((instance_name, val))
            win32pdh.RemoveCounter(hc)
            
    print(json.dumps(pname_pid_list))
#    for pname, pid in sorted(pname_pid_list, key=lambda pnamepid: pnamepid[0]):
#        print("PNAME/PID: {} {}".format(pname, pid))
    # instances = 0
    # for process_instance in process_instances:
        # if process_instance == "python":
            # instances += 1

    # hq = win32pdh.OpenQuery()
    
    
    
    # path = win32pdh.MakeCounterPath( (None, object, "python",
                                      # None, 0, "ID Process") )
                                      
    # hc = win32pdh.AddCounter(hq, path)     
    # win32pdh.CollectQueryData(hq)
    # time.sleep(0.01)
    # win32pdh.CollectQueryData(hq)
    # type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
    # print("PID: {}".format(val))
    # win32pdh.RemoveCounter(hc)
    
    # path = win32pdh.MakeCounterPath( (None, object, "python",
                                      # None, 0, "Page Faults/sec") )
    
    # hc = win32pdh.AddCounter(hq, path)     
    # win32pdh.CollectQueryData(hq)
    # time.sleep(1)
    # win32pdh.CollectQueryData(hq)
    # type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
    # print("PageFaults: {}".format(val))
    # win32pdh.RemoveCounter(hc)
    
    # path = win32pdh.MakeCounterPath( (None, object, "python",
                                      # None, 0, "% Processor Time") )
    
    # hc = win32pdh.AddCounter(hq, path)     
    # win32pdh.CollectQueryData(hq)
    # time.sleep(1)
    # win32pdh.CollectQueryData(hq)
    # type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
    # print("ProcessorTime: {}".format(val))
    # win32pdh.RemoveCounter(hc)
    
    
    
    
    
    #win32pdh.CloseQuery(hq)
    
    # address = ('localhost', 6000)
    # try:
        # conn = Client(address)
        # conn.send("lel")
        # conn.send("close")
    # except ConnectionRefusedError as e:
        # print(e)
    
    # hq = win32pdh.OpenQuery()
    # path = win32pdh.MakeCounterPath( (None, object, "python",
                                      # None, 1, "ID Process") )
                                      
    # hc = win32pdh.AddCounter(hq, path)     
    # win32pdh.CollectQueryData(hq)
    # time.sleep(1)
    # win32pdh.CollectQueryData(hq)
    # type, val = win32pdh.GetFormattedCounterValue(hc, win32pdh.PDH_FMT_LONG)
    # print("{} {}".format(type, val))
    # win32pdh.RemoveCounter(hc)
    # win32pdh.CloseQuery(hq)
    
    #ShowAllProcesses()
        
    # _stdout = sys.stdout
    # p_info = io.StringIO()
    # sys.stdout = p_info
    
    # ShowAllProcesses()
    
    # s = p_info.getvalue()
    # sys.stdout = _stdout
    # print(s)




