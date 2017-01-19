import win32serviceutil
import win32service
import win32event
import servicemanager
import socket

from initat.host_monitoring.server import ServerCode
from initat.tools import configfile, process_tools

class ServiceHandler(win32serviceutil.ServiceFramework):
    _svc_name_ = "NoctuaHostMonitoring"
    _svc_display_name_ = "Noctua Host Monitoring"

    def __init__(self,args):
        win32serviceutil.ServiceFramework.__init__(self,args)
        self.hWaitStop = win32event.CreateEvent(None,0,0,None)
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_,''))
        self.main()

    def main(self):
        global_config = configfile.get_global_config(
            process_tools.get_programm_name(),
            single_process_mode=True
        )
        ServerCode(global_config).loop()


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(ServiceHandler)