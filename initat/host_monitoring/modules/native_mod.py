# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" native modules, dummy file to create json """

from initat.constants import PlatformSystemTypeEnum
from .. import hm_classes
from ..constants import HMAccessClassEnum, DynamicCheckServer, HMIPProtocolEnum


class ModuleDefinition(hm_classes.MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level0
        uuid = "a3f0e9e6-432e-4dd1-9ff7-ed655755fa94"


class check_http_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "fafb5e5d-961c-4aef-ac3c-2f8a87261016"
        description = "check http server on target host"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter(
                "-I",
                "ip_address",
                "",
                "IP Address or name",
                macro_name="$HOSTADDRESS$"
            ),
            hm_classes.MCParameter(
                "-p",
                "port",
                80,
                "Port to connect to",
                devvar_name="HTTP_CHECK_PORT",
            ),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 80),
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 443),
        )

class check_apt_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks for software updates on systems that use apt package manager"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-t", "timeout", 120, "Timeout Value", devvar_name="APT_TIMEOUT"),
        )

class check_tcp_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Check TCP"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname to connect to", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-p", "port", "", "Port to connect to", devvar_name="TCP_CHECK_PORT"),
                hm_classes.MCParameter("-w", "warning", 1, "Warning value", devvar_name="TCP_CHECK_PORT_WARN"),
                hm_classes.MCParameter("-c", "critical", 5, "Critical value", devvar_name="TCP_CHECK_PORT_CRIT"),
                hm_classes.MCParameter("-t", "timeout", 5, "Timeout value", devvar_name="TCP_CHECK_PORT_TIMEOUT"),
        )

class check_disk_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks the amount of used disk space on a mounted file system"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-u", "units", "GB", "Units: kB, MB, GB, TB", devvar_name="CHECK_DISK_UNITS"),
                hm_classes.MCParameter("-w", "warning", "10%", "Exit with WARNING status if less than", devvar_name="CHECK_DISK_WARN"),
                hm_classes.MCParameter("-c", "critical", "7%", "Exit with CRITICAL status if less than", devvar_name="CHECK_DISK_CRIT"),
                hm_classes.MCParameter("-p", "path", "/", "Mount point or block device path", devvar_name="CHECK_DISK_PATH"),
        )

class check_ldap_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks LDAP Server"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-p", "port", 389, "Port number", devvar_name="CHECK_LDAP_PORT"),
                hm_classes.MCParameter("-a", "attribute", "(objectclass=*)", "ldap attribute to search", devvar_name="CHECK_LDAP_ATTR"),
                hm_classes.MCParameter("-b", "base", "", "ldap base", devvar_name="CHECK_LDAP_BASE"),
                hm_classes.MCParameter("-D", "binddn", "", "ldap bind dn", devvar_name="CHECK_LDAP_BINDDN"),
                hm_classes.MCParameter("-P", "password", "", "ldap password", devvar_name="CHECK_LDAP_PASSWROD"),
                hm_classes.MCParameter("-t", "timeout", 5, "ldap timeout in sec", devvar_name="CHECK_LDAP_TIMEOUT"),
        )

class check_load_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks current system load average"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-w", "warning", "1,1,1", "Warning load avg value", devvar_name="CHECK_LOAD_WARN"),
                hm_classes.MCParameter("-c", "critical", "5,5,5", "Critical load avg value", devvar_name="CHECK_LOAD_CRIT"),
                hm_classes.MCParameter("-r", "percpu", "", "Divide load avg per CPU")
        )

class check_mailq_command(hm_classes.MonitoringCommand):
    class Meta:
        # check_mailq -w <warn> -c <crit>
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks the number of messages in the mail queue"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-w", "warning", 50, "Min. number of messages in queue to generate warning", devvar_name="CHECK_MAILQ_WARN"),
                hm_classes.MCParameter("-c", "critical", 100, "Min. number of messages in queue to generate critical alert", devvar_name="CHECK_MAILQ_CRIT"),
        )

class check_mrtg_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = ""
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-F", "logfile", "", "MRTG log file", devvar_name="CHECK_MRTG_LOGFILE"),
                hm_classes.MCParameter("-e", "expires", "", "Minutes before MRTG data is considered to be too old", devvar_name="CHECK_MRTG_EXPIRES"),
                hm_classes.MCParameter("-a", "aggregation", "MAX", "Should we check average(AVG) or maximum(MAX) values?", devvar_name="CHECK_MRTG_AGGR"),
                hm_classes.MCParameter("-v", "variable", 1, "Which variable set should we inspect? (1 or 2)", devvar_name="CHECK_MRTG_VAR"),
                hm_classes.MCParameter("-w", "warning", "", "Threshold value for data to result in WARNING status", devvar_name="CHECK_MRTG_WARN"),
                hm_classes.MCParameter("-c", "critical", "", "Threshold value for data to result in CRITICAL status", devvar_name="CHECK_MRTG_CRIT"),
                hm_classes.MCParameter("-l", "label", "", "Type label for data (Examples: Conns, \"Processor Load\", In, Out)", devvar_name="CHECK_MRTG_LABEL"),
                hm_classes.MCParameter("-u", "units", "", "Option units label for data (Example: Packets/Sec, Errors/Sec, \"Bytes Per Second\", \"% Utilization\")"),

        )

class check_mysql_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks MySQL Server"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-P", "port", 3306, "Port number", devvar_name="CHECK_MYSQL_PORT"),
                hm_classes.MCParameter("-s", "socket", "", "Use the specified socket (has no effect if -H is used)", devvar_name="CHECK_MYSQL_SOCKET"),
                hm_classes.MCParameter("-u", "username", "root", "Connect using the indicated username", devvar_name="CHECK_MYSQL_USERNAME"),
                hm_classes.MCParameter("-p", "password", "root", "Use the indicated password to authenticate the connection", devvar_name="CHECK_MYSQL_PASSWORD"),
                hm_classes.MCParameter("-d", "database", "information_schema", "Check database with indicated name", devvar_name="CHECK_MYSQL_DB"),
        )

class check_mysql_query_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks MySQL Server using SQL query"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-P", "port", 3306, "Port number", devvar_name="CHECK_MYSQL_PORT"),
                hm_classes.MCParameter("-s", "socket", "", "Use the specified socket (has no effect if -H is used)", devvar_name="CHECK_MYSQL_SOCKET"),
                hm_classes.MCParameter("-u", "username", "root", "Connect using the indicated username", devvar_name="CHECK_MYSQL_USERNAME"),
                hm_classes.MCParameter("-p", "password", "root", "Use the indicated password to authenticate the connection", devvar_name="CHECK_MYSQL_PASSWORD"),
                hm_classes.MCParameter("-d", "database", "information_schema", "Check database with indicated name", devvar_name="CHECK_MYSQL_DB"),
                hm_classes.MCParameter("-q", "query", "select VARIABLE_VALUE from information_schema.GLOBAL_STATUS where VARIABLE_NAME like \"UPTIME\";", "SQL query to run",
                    devvar_name="CHECK_MYSQL_QUERY"),
        )

class check_ntp_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks NTP Server"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-P", "port", 123, "Port number", devvar_name="CHECK_NTP_PORT"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NTP_TIMEOUT"),
                hm_classes.MCParameter("-w", "warning", 5, "Offset to result in warning status (seconds)", devvar_name="CHECK_NTP_WARN"),
                hm_classes.MCParameter("-c", "critical", 10, "Offset to result in critical status (seconds)", devvar_name="CHECK_NTP_CRIT"),
        )

class check_ntp_peer_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks NTP Peer"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-P", "port", 123, "Port number", devvar_name="CHECK_NTP_PORT"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NTP_TIMEOUT"),
                hm_classes.MCParameter("-w", "warning", 5, "Offset to result in warning status (seconds)", devvar_name="CHECK_NTP_WARN"),
                hm_classes.MCParameter("-c", "critical", 10, "Offset to result in critical status (seconds)", devvar_name="CHECK_NTP_CRIT"),
        )

class check_ntp_time_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks NTP Time"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-P", "port", 123, "Port number", devvar_name="CHECK_NTP_PORT"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NTP_TIMEOUT"),
                hm_classes.MCParameter("-w", "warning", 5, "Offset to result in warning status (seconds)", devvar_name="CHECK_NTP_WARN"),
                hm_classes.MCParameter("-c", "critical", 10, "Offset to result in critical status (seconds)", devvar_name="CHECK_NTP_CRIT"),
                hm_classes.MCParameter("-o", "offset", 1, "", devvar_name="CHECK_NTP_OFFSET"),
        )

class check_pgsql_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Test whether a PostgreSQL Database is accepting connections."
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Host name, IP Address, or unix socket (must be an absolute path)", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-P", "port", 5432, "Port number", devvar_name="CHECK_PGSQL_PORT"),
                hm_classes.MCParameter("-l", "username", "", "Login name of user", devvar_name="CHECK_PGSQL_LOGINNAME"),
                hm_classes.MCParameter("-p", "password", "", "Password", devvar_name="CHECK_PGSQL_PASSWORD"),
                hm_classes.MCParameter("-d", "database", "template1", "Database to check (default: template1)", devvar_name="CHECK_PGSQL_DB"),
                hm_classes.MCParameter("-w", "warning", "", "Response time to result in warning status (seconds)", devvar_name="CHECK_PGSQL_WARN"),
                hm_classes.MCParameter("-c", "critical", "", "Response time to result in critical status (seconds)", devvar_name="CHECK_PGSQL_CRIT"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_PGSQL_TIMEOUT"),
                hm_classes.MCParameter("-q", "query", "SELECT pg_database_size(current_database())", "SQL query to run", devvar_name="CHECK_PGSQL_QUERY"),
        )

class check_ping_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks Ping"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_PING_TIMEOUT"),
                hm_classes.MCParameter("-w", "warning", "100.0,20%", "warning threshold pair", devvar_name="CHECK_PING_WARN"),
                hm_classes.MCParameter("-c", "critical", "200.0,90%", "critical threshold pair", devvar_name="CHECK_PING_CRIT"),
                hm_classes.MCParameter("-p", "packets", 5, "number of ICMP ECHO packets to send (Default: 5)", devvar_name="CHECK_PING_PACKETS"),
        )

class check_procs_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks all processes and generates WARNING or CRITICAL states"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_PROCS_TIMEOUT"),
                hm_classes.MCParameter("-w", "warning", "100", "Generate warning state if metric is outside this range", devvar_name="CHECK_PROCS_WARN"),
                hm_classes.MCParameter("-c", "critical", "150", "Generate critical state if metric is outside this range", devvar_name="CHECK_PROCS_CRIT"),
                hm_classes.MCParameter("-m", "metric", "PROCS", "Check thresholds against metric. Valid types: PROCS, VSZ, RSS, CPU, ELAPSED", devvar_name="CHECK_PROCS_METRIC"),
        )

class check_rpc_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = ""
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-C", "command", "nfs", "The program name (or number). Default: nfs. (portmapper, nfs, mountd, status, nlockmgr, rquotad)", devvar_name="CHECK_RPC_COMMAND"),
        )

class check_rpc_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Check if a rpc service is registered and running"
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-C", "command", "nfs", "The program name (or number). Default: nfs. (portmapper, nfs, mountd, status, nlockmgr, rquotad)", devvar_name="CHECK_RPC_COMMAND"),
        )

class check_sensors_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Checks hardware status using the lm_sensors package."

class check_smtp_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "This plugin will attempt to open an SMTP connection with the host."
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-p", "port", 25, "Port Number (default: 25)", devvar_name="CHECK_SMTP_PORT"),
                hm_classes.MCParameter("-e", "expect", "220", "String to expect in first line of server response (default: '220')", devvar_name="CHECK_SMTP_STRING"),
                hm_classes.MCParameter("-C", "command", "", "SMTP command", devvar_name="CHECK_SMTP_COMMAND"),
                hm_classes.MCParameter("-R", "response", "", "Expected response to command", devvar_name="CHECK_SMTP_RESPONSE"),
                hm_classes.MCParameter("-f", "from", "monitoring@init.at", "FROM-address to include in MAIL command", devvar_name="CHECK_SMTP_FROM"),
                hm_classes.MCParameter("-F", "fqdn", "init.at", "FQDN used for HELO", devvar_name="CHECK_SMTP_FQDN"),
                #hm_classes.MCParameter("-S", "starttls", "", "Use STARTTLS for the connection.", devvar_name="CHECK_SMTP_STARTTLS"),
                #hm_classes.MCParameter("-D", "certificate", 30, "Minimum number of days a certificate has to be valid.", devvar_name="CHECK_SMTP_CERT_DAYS"),
                #hm_classes.MCParameter("-A", "authtye", "none", "SMTP AUTH type to check (default none, only LOGIN supported)", devvar_name="CHECK_SMTP_AUTH_TYPE"),
                #hm_classes.MCParameter("-U", "authuser", "", "SMTP AUTH username", devvar_name="CHECK_SMTP_AUTH_USER"),
                #hm_classes.MCParameter("-P", "authpass", "", "SMTP AUTH password", devvar_name="CHECK_SMTP_AUTH_PASS"),
                hm_classes.MCParameter("-w", "warning", 5, "Response time to result in warning status (seconds)", devvar_name="CHECK_SMTP_WARN"),
                hm_classes.MCParameter("-c", "critical", 10, "Response time to result in critical status (seconds)", devvar_name="CHECK_SMTP_CRIT"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_SMTP_TIMEOUT"),
        )

class check_ssh_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Try to connect to an SSH server at specified server and port."
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-H", "hostname", "", "Host name, IP Address, or unix socket (must be an absolute path)", macro_name="$HOSTADDRESS$"),
                hm_classes.MCParameter("-p", "port", 22, "Port number (default: 22)", devvar_name="CHECK_SSH_PORT"),
                hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_SSH_TIMEOUT"),
        )

class check_swap_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "Check swap space on local machine."
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-w", "warning", "20%", "Exit with WARNING status if less than PERCENT of swap space is free", devvar_name="CHECK_SWAP_WARN"),
                hm_classes.MCParameter("-c", "critical", "10%", "Exit with CRITICAL status if less than PERCENT of swap space is free", devvar_name="CHECK_SWAP_CRIT"),
        )

class check_users_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = ""
        description = "This plugin checks the number of users currently logged in on the local system."
        parameters = hm_classes.MCParameters(
                hm_classes.MCParameter("-w", "warning", 5, "Set WARNING status if more than INTEGER users are logged in.", devvar_name="CHECK_SWAP_WARN"),
                hm_classes.MCParameter("-c", "critical", 10, "Set CRITICAL status if more than INTEGER users are logged in.", devvar_name="CHECK_SWAP_CRIT"),
        )
