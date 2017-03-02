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
        uuid = "b683c590-4ee6-4730-96e8-810852931106"
        description = "Checks for software updates on systems that use apt package manager"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-t", "timeout", 120, "Timeout Value", devvar_name="APT_TIMEOUT"),
        )

class check_tcp_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "85b2fc85-98a6-44eb-abc7-e7374cc41f64"
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
        uuid = "438d4b6a-ab38-407d-9cad-6fa9828b918c"
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
        uuid = "65f9c708-6e5e-409b-9c2c-8d9849deec6e"
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
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 389),
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 636),
        )

class check_load_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "26d0ff5c-97e9-4e33-b070-493cbfb9c04a"
        description = "Checks current system load average"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-w", "warning", "1,1,1", "Warning load avg value", devvar_name="CHECK_LOAD_WARN"),
            hm_classes.MCParameter("-c", "critical", "5,5,5", "Critical load avg value", devvar_name="CHECK_LOAD_CRIT"),
            hm_classes.MCParameter("-r", "percpu", "", "Divide load avg per CPU")
        )

class check_mailq_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "e1798b8d-8488-41c5-82b8-52ecb4725923"
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
        uuid = "98883b40-bc1f-440f-b664-857c26130770"
        description = "check either the average or maximum value of one of the two variables recorded in an MRTG log file."
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
        uuid = "66d4b2e3-91c4-4e8f-81f9-d430422a6e8a"
        description = "Checks MySQL Server"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-P", "port", 3306, "Port number", devvar_name="CHECK_MYSQL_PORT"),
            hm_classes.MCParameter("-s", "socket", "", "Use the specified socket (has no effect if -H is used)", devvar_name="CHECK_MYSQL_SOCKET"),
            hm_classes.MCParameter("-u", "username", "root", "Connect using the indicated username", devvar_name="CHECK_MYSQL_USERNAME"),
            hm_classes.MCParameter("-p", "password", "root", "Use the indicated password to authenticate the connection", devvar_name="CHECK_MYSQL_PASSWORD"),
            hm_classes.MCParameter("-d", "database", "information_schema", "Check database with indicated name", devvar_name="CHECK_MYSQL_DB"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 3306),
        )

class check_mysql_query_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "502d2f6f-f579-4d0b-a73f-bf6bfe82057d"
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
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 3306),
        )

class check_ntp_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "e84a8008-c454-4759-a0b6-332984a02f19"
        description = "Checks NTP Server"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-P", "port", 123, "Port number", devvar_name="CHECK_NTP_PORT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NTP_TIMEOUT"),
            hm_classes.MCParameter("-w", "warning", 5, "Offset to result in warning status (seconds)", devvar_name="CHECK_NTP_WARN"),
            hm_classes.MCParameter("-c", "critical", 10, "Offset to result in critical status (seconds)", devvar_name="CHECK_NTP_CRIT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.udp, 123),
        )

class check_ntp_peer_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "76bbeeae-6494-4d41-9755-967c95b752e2"
        description = "Checks NTP Peer"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-P", "port", 123, "Port number", devvar_name="CHECK_NTP_PORT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NTP_TIMEOUT"),
            hm_classes.MCParameter("-w", "warning", 5, "Offset to result in warning status (seconds)", devvar_name="CHECK_NTP_WARN"),
            hm_classes.MCParameter("-c", "critical", 10, "Offset to result in critical status (seconds)", devvar_name="CHECK_NTP_CRIT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.udp, 123),
        )

class check_ntp_time_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "d234d841-8c36-4b89-a9c7-ea345ad0a99c"
        description = "Checks NTP Time"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-P", "port", 123, "Port number", devvar_name="CHECK_NTP_PORT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NTP_TIMEOUT"),
            hm_classes.MCParameter("-w", "warning", 5, "Offset to result in warning status (seconds)", devvar_name="CHECK_NTP_WARN"),
            hm_classes.MCParameter("-c", "critical", 10, "Offset to result in critical status (seconds)", devvar_name="CHECK_NTP_CRIT"),
            hm_classes.MCParameter("-o", "offset", 1, "", devvar_name="CHECK_NTP_OFFSET"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.udp, 123),
        )

class check_pgsql_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "12767471-fe55-4cc5-898d-12a2ef56c482"
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
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 5432),
        )

class check_ping_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "18df6f6a-0a82-431a-849c-d9a547041470"
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
        uuid = "339d030a-cc7a-46b1-8098-4f46c7f9a9cb"
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
        uuid = "07c710dc-e1c4-4b2b-b78a-00a0fa026c96"
        description = "Check if a rpc service is registered and running"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-C", "command", "nfs", "The program name (or number). Default: nfs. (portmapper, nfs, mountd, status, nlockmgr, rquotad)", devvar_name="CHECK_RPC_COMMAND"),
        )

class check_breeze_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "c9002e9f-1953-4085-a344-3948833bec72"
        description = "Reports the signal strength of a Breezecom wireless equipment"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Hostname/IP Addr", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-C", "community", "public", "SNMPv1 community (default public)", devvar_name="CHECK_BREEZE_COMMUNITY"),
            hm_classes.MCParameter("-w", "warning", "50", "Percentage strength below which a WARNING status will result", devvar_name="CHECK_BREEZE_WARN"),
            hm_classes.MCParameter("-c", "critical", "25", "Percentage strength below which a CRITICAL status will result", devvar_name="CHECK_BREEZE_CRIT"),
        )

class check_sensors_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "d552e5ce-170f-4e8a-81c0-27142c159f73"
        description = "Checks hardware status using the lm_sensors package."

class check_smtp_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "ccff647b-5f71-400d-a923-77f57b3086e5"
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
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 25),
        )

class check_ssh_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "613b4d81-553b-4a14-9016-a92b4bb04577"
        description = "Try to connect to an SSH server at specified server and port."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Host name, IP Address, or unix socket (must be an absolute path)", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-p", "port", 22, "Port number (default: 22)", devvar_name="CHECK_SSH_PORT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_SSH_TIMEOUT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 22),
        )

class check_swap_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "c4764ca8-c4dd-4423-a1ce-feb46665f452"
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
        uuid = "42b63019-3721-4c72-8c0b-a3a954e1bae2"
        description = "This plugin checks the number of users currently logged in on the local system."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-w", "warning", 5, "Set WARNING status if more than INTEGER users are logged in.", devvar_name="CHECK_SWAP_WARN"),
            hm_classes.MCParameter("-c", "critical", 10, "Set CRITICAL status if more than INTEGER users are logged in.", devvar_name="CHECK_SWAP_CRIT"),
        )

class check_by_ssh_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "71af1cc0-855b-4a9d-a24c-104bb36af3b9"
        description = "This plugin uses SSH to execute commands on a remote host."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Host name, IP Address, or unix socket (must be an absolute path)", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-p", "port", 22, "Port number (default: 22)", devvar_name="CHECK_BY_SSH_PORT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_BY_SSH_TIMEOUT"),
            hm_classes.MCParameter("-C", "command", "uptime", "command to execute on the remote machine (default: uptime)", devvar_name="CHECK_BY_SSH_COMMAND"),
            hm_classes.MCParameter("-l", "username", "root", "SSH user name on remote host", devvar_name="CHECK_BY_SSH_USERNAME"),
            hm_classes.MCParameter("-i", "identityfile", "/tmp/id_rsa", "identity of an authorized key", devvar_name="CHECK_BY_SSH_IDENTITY"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 22),
        )

class check_dig_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "b35f220e-6a63-4c6e-9a9e-6307961d1a57"
        description = "Test the DNS service on the specified host using dig"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Host name, IP Address, or unix socket (must be an absolute path)", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-p", "port", 53, "Port number (default: 53)", devvar_name="CHECK_DIG_PORT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_DIG_TIMEOUT"),
            hm_classes.MCParameter("-w", "warning", "5", "Response time to result in warning status (seconds)", devvar_name="CHECK_DIG_WARN"),
            hm_classes.MCParameter("-c", "critical", "10", "Response time to result in critical status (seconds)", devvar_name="CHECK_DIG_CRIT"),
            hm_classes.MCParameter("-T", "recordtype", "A", "Record type to lookup (default: A)", devvar_name="CHECK_DIG_RECORDTYPE"),
            hm_classes.MCParameter("-l", "lookup", "www.google.com", "Machine name to lookup", devvar_name="CHECK_DIG_LOOKUP"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.udp, 53),
        )

class check_dns_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "5e2f3ccc-583e-4cef-9cd4-789603291c28"
        description = "Uses the nslookup program to obtain the IP address for the given host/domain query."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "The name or address you want to query", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_DNS_TIMEOUT"),
            hm_classes.MCParameter("-w", "warning", "5", "Return warning if elapsed time exceeds value. Default off", devvar_name="CHECK_DNS_WARN"),
            hm_classes.MCParameter("-c", "critical", "10", "Return critical if elapsed time exceeds value. Default off", devvar_name="CHECK_DNS_CRIT"),
            hm_classes.MCParameter("-s", "server", "8.8.8.8", "Optional DNS server you want to use for the lookup", devvar_name="CHECK_DNS_SERVER"),
        )

class check_disk_smb_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "3ff35d20-6173-4747-8ed3-b4d14a6de873"
        description = "Perl Check SMB Disk plugin for monitoring"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "NetBIOS name of the server", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-s", "share", "", "Share name to be tested", devvar_name="CHECK_DISK_SMB_SHARE"),
            hm_classes.MCParameter("-W", "workgroup", "WORKGROUP", "Workgroup or Domain used (Defaults to 'WORKGROUP')", devvar_name="CHECK_DISK_SMB_WORKGROUP"),
            hm_classes.MCParameter("-w", "warning", "85%", "Percent of used space at which a warning will be generated (Default: 85%)", devvar_name="CHECK_DISK_SMB_WARN"),
            hm_classes.MCParameter("-c", "critical", "95%", "Percent of used space at which a critical will be generated (Defaults: 95%)", devvar_name="CHECK_DISK_SMB_CRIT"),
            hm_classes.MCParameter("-u", "username", "guest", "Username to log in to server. (Defaults to 'guest')", devvar_name="CHECK_DISK_SMB_USER"),
            hm_classes.MCParameter("-p", "password", "", "Password to log in to server. (Defaults to an empty password)", devvar_name="CHECK_DISK_SMB_PASS"),
            hm_classes.MCParameter("-P", "port", 445, "Port to be used to connect to. Some Windows boxes use 139, others 445 (Defaults to smbclient default)", devvar_name="CHECK_DISK_SMB_PORT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 139),
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 445),
        )

class check_file_age_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "ea5c2aef-aaa2-4a6d-a231-e206a6b73dfd"
        description = "Checks file age"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-W", "warningsize", 0, "File must be at least this many bytes long (default: crit 0 bytes)", devvar_name="CHECK_FILEAGE_WARNSIZE"),
            hm_classes.MCParameter("-C", "criticalsize", 0, "File must be at least this many bytes long (default: crit 0 bytes)", devvar_name="CHECK_FILEAGE_CRITSIZE"),
            hm_classes.MCParameter("-w", "warning", 240, "File must be no more than this many seconds old (default: warn 240 secs, crit 600)", devvar_name="CHECK_FILEAGE_WARN"),
            hm_classes.MCParameter("-c", "critical", 600, "File must be no more than this many seconds old (default: warn 240 secs, crit 600)", devvar_name="CHECK_FILEAGE_CRIT"),
            hm_classes.MCParameter("-f", "file", "", "File to be monitored", devvar_name="CHECK_FILEAGE_FILE"),
        )

class check_flexlm_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "c6ce3fb3-2d87-4039-b9ef-9361bed6d709"
        description = "Check available flexlm license managers"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-t", "timeout", 15, "Plugin time out in seconds (default = 15 )", devvar_name="CHECK_FLEXLM_TIMEOUT"),
            hm_classes.MCParameter("-F", "file", "license.dat", "Name of license file (usually license.dat)", devvar_name="CHECK_FLEXLM_FILE"),
        )

class check_ide_smart_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "2e7d980b-9de3-44fd-8c9d-53c2d2263c3d"
        description = "This plugin checks a local hard drive with the (Linux specific) SMART interface"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-d", "device", "", "Select device (ex: /dev/hda)", devvar_name="CHECK_IDE_SMART_DEV"),
        )

class check_ifoperstatus_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "d2a92f65-cc7f-40e5-813f-86e93977518b"
        description = "check_ifoperstatus plugin for monitoring operational status of a particular network interface on the target host"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "The name or address you want to query", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-C", "community" "public", "SNMP read community (defaults to public, used with SNMP v1 and v2c", devvar_name="CHECK_IFOPERSTATUS_COMMUNITY"),
            hm_classes.MCParameter("-v", "version", 1, "1 for SNMP v1 (default). 2 for SNMP v2c - default=1", devvar_name="CHECK_IFOPERSTATUS_VERSION"),
            hm_classes.MCParameter("-L", "seclevel", "noAuthNoPriv", "choice of 'noAuthNoPriv', 'authNoPriv', or 'authPriv' - default:noAuthNoPriv", devvar_name="CHECK_IFOPERSTATUS_SECLEVEL"),
            hm_classes.MCParameter("-U", "secname", "", "username for SNMPv3 context", devvar_name="CHECK_IFOPERSTATUS_SECNAME"),
            hm_classes.MCParameter("-c", "context", "", "SNMPv3 context name (default is empty string)", devvar_name="CHECK_IFOPERSTATUS_CONTEXT"),
            hm_classes.MCParameter("-A", "authpass", "", "authentication password (cleartext ascii or localized key in hex with 0x prefix generated by using 'snmpkey' utility auth password and authEngineID", devvar_name="CHECK_IFOPERSTATUS_SECLEVEL"),
            hm_classes.MCParameter("-a", "authproto", "SHA1", "Authentication protocol (MD5 or SHA1)", devvar_name="CHECK_IFOPERSTATUS_AUTHPROTO"),
            hm_classes.MCParameter("-X", "privpass", "", "privacy password (cleartext ascii or localized key in hex with 0x prefix generated by using 'snmpkey' utility privacy password and authEngineID", devvar_name="CHECK_IFOPERSTATUS_PRIVPASS"),
            hm_classes.MCParameter("-P", "privproto", "AES", "privacy protocol (DES or AES; default: AES)", devvar_name="CHECK_IFOPERSTATUS_PRIVPROTO"),
            hm_classes.MCParameter("-d", "ifdescr", "", "SNMP IfDescr value", devvar_name="CHECK_IFOPERSTATUS_IFDESCR"),
            hm_classes.MCParameter("-p", "port", 161, "SNMP port (default 161)", devvar_name="CHECK_IFOPERSTATUS_PORT"),
            hm_classes.MCParameter("-w", "warning", "c", "accepts: 'i' or 'w' or 'c' (ignore|warn|crit) if the interface is dormant (default critical)", devvar_name="CHECK_IFOPERSTATUS_WARN"),
            hm_classes.MCParameter("-D", "admindown", "w", "accepts: 'i' or 'w' or 'c' (ignore|warn|crit) administratively down interfaces (default warning)", devvar_name="CHECK_IFOPERSTATUS_ADMIN"),
            hm_classes.MCParameter("-M", "msgmaxsize", "", "Max message size - useful only for v1 or v2c", devvar_name="CHECK_IFOPERSTATUS_MSGSIZE"),
            hm_classes.MCParameter("-t", "timeout", 15, "seconds before the plugin times out (default=15)", devvar_name="CHECK_IFOPERSTATUS_TIMEOUT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.udp, 161),
        )

class check_ifstatus_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "f4ec1a2e-8bd5-473e-b113-c3c0a5210434"
        description = "check_ifstatus plugin for monitoring operational status of each network interface on the target host"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "The name or address you want to query", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-C", "community" "public", "SNMP read community (defaults to public, used with SNMP v1 and v2c", devvar_name="CHECK_IFSTATUS_COMMUNITY"),
            hm_classes.MCParameter("-v", "snmp_version", 1, "1 for SNMP v1 (default). 2 for SNMP v2c. 3 for SNMPv3 (requires -U option) - default=1", devvar_name="CHECK_IFSTATUS_VERSION"),
            hm_classes.MCParameter("-L", "seclevel", "noAuthNoPriv", "choice of 'noAuthNoPriv', 'authNoPriv', or 'authPriv' - default:noAuthNoPriv", devvar_name="CHECK_IFSTATUS_SECLEVEL"),
            hm_classes.MCParameter("-U", "secname", "", "username for SNMPv3 context", devvar_name="CHECK_IFSTATUS_SECNAME"),
            hm_classes.MCParameter("-c", "context", "", "SNMPv3 context name (default is empty string)", devvar_name="CHECK_IFSTATUS_CONTEXT"),
            hm_classes.MCParameter("-A", "authpass", "", "authentication password (cleartext ascii or localized key in hex with 0x prefix generated by using 'snmpkey' utility auth password and authEngineID", devvar_name="CHECK_IFSTATUS_SECLEVEL"),
            hm_classes.MCParameter("-a", "authproto", "SHA1", "Authentication protocol (MD5 or SHA1)", devvar_name="CHECK_IFOPERSTATUS_AUTHPROTO"),
            hm_classes.MCParameter("-X", "privpass", "", "privacy password (cleartext ascii or localized key in hex with 0x prefix generated by using 'snmpkey' utility privacy password and authEngineID", devvar_name="CHECK_IFSTATUS_PRIVPASS"),
            hm_classes.MCParameter("-P", "privproto", "AES", "privacy protocol (DES or AES; default: AES)", devvar_name="CHECK_IFSTATUS_PRIVPROTO"),
            hm_classes.MCParameter("-x", "exclude", "", "A comma separated list of ifType values that should be excluded from the report (default for an empty list is PPP(23).", devvar_name="CHECK_IFSTATUS_EXCLUDE"),
            hm_classes.MCParameter("-p", "port", 161, "SNMP port (default 161)", devvar_name="CHECK_IFSTATUS_PORT"),
            hm_classes.MCParameter("-n", "unused_ports_by_name", "", "A comma separated list of ifDescr values that should be excluded from the report (default is an empty exclusion list).", devvar_name="CHECK_IFSTATUS_UNUSED_BY_NAME"),
            hm_classes.MCParameter("-u", "unused_ports", "", "A comma separated list of ifIndex values that should be excluded from the report (default is an empty exclusion list).", devvar_name="CHECK_IFSTATUS_UNUSED_PORTS"),
            hm_classes.MCParameter("-M", "maximsgsize", "", "Max message size - useful only for v1 or v2c", devvar_name="CHECK_IFSTATUS_MSGSIZE"),
            hm_classes.MCParameter("-t", "timeout", 15, "seconds before the plugin times out (default=15)", devvar_name="CHECK_IFSTATUS_TIMEOUT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.udp, 161),
        )

class check_ircd_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "f577874c-4ac0-429c-8862-28c521a52d55"
        description = "Perl Check IRCD plugin for monitoring"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Name or IP address of host to check", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-w", "warning", 50, "Number of connected users which generates a warning state (Default: 50)", devvar_name="CHECK_IRCD_WARN"),
            hm_classes.MCParameter("-w", "critical", 100, "Number of connected users which generates a critical state (Default: 100)", devvar_name="CHECK_IRCD_CRIT"),
            hm_classes.MCParameter("-p", "port", 6667, "Port that the ircd daemon is running on <host> (Default: 6667)", devvar_name="CHECK_IRCD_PORT"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 6667),
        )

class check_log_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "df17a328-2336-4b44-80b4-1721cda86327"
        description = "Log file pattern detector plugin for monitoring"
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-F", "logfile", "", "Logfile to be scanned", devvar_name="CHECK_LOG_FILE"),
            hm_classes.MCParameter("-O", "oldlog", "", "Where to save copy of the log file from the previous", devvar_name="CHECK_LOG_OLDFILE"),
            hm_classes.MCParameter("-q", "query", "", "Scan log for this pattern", devvar_name="CHECK_LOG_QUERY"),
        )

class check_mrtgtraf_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "c254af78-5bc9-4560-866a-f4fd678c4ba1"
        description = "Check the incoming/outgoing transfer rates of a router, switch, etc recorded in an MRTG log."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-F", "filename", "", "File to read log from", devvar_name="CHECK_MRTGTRAF_FILE"),
            hm_classes.MCParameter("-e", "expires", "", "Minutes after which log expires", devvar_name="CHECK_MRTGTRAF_EXPIRES"),
            hm_classes.MCParameter("-a", "aggregation", "MAX", "Should we check average(AVG) or maximum(MAX) values?", devvar_name="CHECK_MRTGTRAG_AGGR"),
            hm_classes.MCParameter("-w", "warning", "", "Warning threshold pair <incoming>,<outgoing>", devvar_name="CHECK_MRTGTRAF_WARN"),
            hm_classes.MCParameter("-c", "critical", "", "Critical threshold pair <incoming>,<outgoing>", devvar_name="CHECK_MRTGTRAF_CRIT"),
        )

class check_ups_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "38ba3903-5f0e-4fc2-bb41-ddb5bb9b9533"
        description = "This plugin tests the UPS service on the specified host. Network UPS Tools from www.networkupstools.org must be running for this plugin to work."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Host name, IP Address, or unix socket (must be an absolute path)", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-p", "port", 3493, "Port number (default: 3493)", devvar_name="CHECK_UPS_PORT"),
            hm_classes.MCParameter("-u", "ups", "", "Name of UPS", devvar_name="CHECK_UPS_NAME"),
            hm_classes.MCParameter("-v", "variable", "LINE", "Valid values for STRING are LINE, TEMP, BATTPCT or LOADPCT", devvar_name="CHECK_UPS_VARIABLE"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_UPS_TIMEOUT"),
            hm_classes.MCParameter("-w", "warning", "", "Response time to result in warning status (seconds)", devvar_name="CHECK_UPS_WARN"),
            hm_classes.MCParameter("-c", "critical", "", "Response time to result in critical status (seconds)", devvar_name="CHECK_UPS_CRIT"),
        )

class check_nt_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        check_instance = DynamicCheckServer.native
        required_access = HMAccessClassEnum.level0
        uuid = "727e369f-9a1f-489c-870c-462ff7384594"
        description = "This plugin collects data from the NSClient service running on a Windows NT/2000/XP/2003 server."
        parameters = hm_classes.MCParameters(
            hm_classes.MCParameter("-H", "hostname", "", "Name of the host to check", macro_name="$HOSTADDRESS$"),
            hm_classes.MCParameter("-p", "port", 1248, "Optional port number (default: 1248)", devvar_name="CHECK_NT_PORT"),
            hm_classes.MCParameter("-s", "secret", "", "Password needed for the request", devvar_name="CHECK_NT_SECRET"),
            hm_classes.MCParameter("-w", "warning", "", "Threshold which will result in a warning status", devvar_name="CHECK_NT_WARN"),
            hm_classes.MCParameter("-c", "critical", "", "Threshold which will result in a critical status", devvar_name="CHECK_NT_CRIT"),
            hm_classes.MCParameter("-t", "timeout", 10, "Seconds before connection times out (default: 10)", devvar_name="CHECK_NT_TIMEOUT"),
            hm_classes.MCParameter("-v", "variable", "", "Variable to check", devvar_name="CHECK_NT_VARIABLE"),
            hm_classes.MCParameter("-l", "params", "", "Parameters passed to specified check", devvar_name="CHECK_NT_PARAMS"),
        )
        ports = hm_classes.MCPortList(
            hm_classes.MCPort(HMIPProtocolEnum.tcp, 1248),
        )
