import os

from initat.laser_server.constants import SERVER_COM_PORT

from initat.tools import configfile
from initat.laser_server.config import global_config

def run_code():
    from initat.laser_server.server import server_process
    s = server_process()
    s.loop()

def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("COM_PORT", configfile.int_c_var(SERVER_COM_PORT)),
        ]
    )

    run_code()
    configfile.terminate_manager()
    # exit
    os._exit(0)