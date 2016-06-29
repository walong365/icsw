import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.new_md_config_server.constants import SERVER_COM_PORT

from initat.tools import cluster_location, configfile, process_tools
from initat.new_md_config_server.config import global_config

def run_code():
    from initat.new_md_config_server.server import server_process
    s = server_process()
    s.loop()

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()

    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ]
    )


    cluster_location.read_config_from_db(
        global_config,
        "new_md_config_server",
        [
            ("COM_PORT", configfile.int_c_var(SERVER_COM_PORT)),
        ]
    )

    run_code()
    configfile.terminate_manager()
    # exit
    os._exit(0)