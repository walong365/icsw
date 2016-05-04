import win32pdhutil

from cStringIO import StringIO
import sys


if __name__=="__main__":
    
    _stdout = sys.stdout
    p_info = StringIO()
    sys.stdout = p_info
    
    win32pdhutil.ShowAllProcesses()
    
    s = p_info.getvalue()
    sys.stdout = _stdout
    
    #f = open("C:/tmp.txt", "w")
    #f.write(s)
    #f.close()

    print s    




