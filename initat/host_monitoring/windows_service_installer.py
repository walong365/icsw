import win32service
import win32serviceutil
import win32event

from initat.tools import configfile, process_tools
from initat.host_monitoring.server import ServerCode
from initat.client_version import VERSION_STRING

class PySvc(win32serviceutil.ServiceFramework):
    # you can NET START/STOP the service by the following name
    _svc_name_ = "NoctuaHostMonitoring"
    # this text shows up as the service name in the Service
    # Control Manager (SCM)
    _svc_display_name_ = "Noctua Host Monitoring"
    # this text shows up as the description in the SCM
    _svc_description_ = "Noctua Host Monitoring Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # create an event to listen for stop requests on
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        # core logic of the service

    def SvcDoRun(self):
        global_config = configfile.get_global_config(
            process_tools.get_programm_name(),
            single_process_mode=True
        )
        prog_name = "collserver"
        global_config.add_config_entries(
            [
                ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d",
                    only_commandline=True)),
                ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v",
                    only_commandline=True)),
            ]
        )
        options = global_config.handle_commandline(
            description="{}, version is {}".format(
                prog_name,
                VERSION_STRING
            ),
            positional_arguments=prog_name in ["collclient"],
            partial=prog_name in ["collclient"],
        )

        ret_state = ServerCode(global_config).loop()
        return ret_state

        # called when we're being shut down

    def SvcStop(self):
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.hWaitStop)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(PySvc)