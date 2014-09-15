# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
""" creates the cluster fixtures """

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.crypto import get_random_string
from initat.cluster.backbone import factories
from initat.cluster.backbone.management.commands.fixtures import add_fixtures
from initat.cluster.backbone.models import ALL_LICENSES, get_license_descr, log_source, \
    get_related_models
from lxml import etree  # @UnresolvedImport
# from lxml.builder import E # @UnresolvedImport
import os
import sys

# old local_settings.py

LOCAL_CONFIG = "/etc/sysconfig/cluster/local_settings.py"


class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ("Creates the cluster fixtures.")

    def handle(self, **options):
        print("creating fixtures...")
        # global settings

        # default values
        LOGIN_SCREEN_TYPE = "big"
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
        SECRET_KEY = get_random_string(50, chars)
        if os.path.isfile(LOCAL_CONFIG):
            # try to read from LOCAL_CONFIG
            local_dir = os.path.dirname(LOCAL_CONFIG)
            sys.path.append(local_dir)
            from local_settings import SECRET_KEY  # @UnresolvedImport
            sys.path.remove(local_dir)
        cur_gs = factories.ClusterSetting(name="GLOBAL", secret_key=SECRET_KEY, login_screen_type=LOGIN_SCREEN_TYPE)
        LICENSE_FILE = "/etc/sysconfig/cluster/cluster_license"
        # default: disable all
        _lic_dict = {name: False for name in ALL_LICENSES}
        try:
            cur_lic = etree.fromstring(file(LICENSE_FILE, "r").read())  # @UndefinedVariable
        except:
            pass
        else:
            for lic_name in ALL_LICENSES:
                _lic = cur_lic.xpath(".//license[@short='{}']".format(lic_name))
                if len(_lic):
                    _lic = _lic[0]
                    _lic_dict[lic_name] = True if _lic.get("enabled", "no").lower() in ["yes"] else False
        # create fixtures
        for lic_name in ALL_LICENSES:
            factories.ClusterLicense(cluster_setting=cur_gs, name=lic_name, description=get_license_descr(lic_name), enabled=_lic_dict[lic_name])
        # remove duplicate entries due to bug in factories (sigh)
        cur_cusl = log_source.objects.filter(Q(identifier="user"))
        for _cc in cur_cusl:
            if not get_related_models(_cc):
                _cc.delete()
        # log source
        factories.LogSource(identifier="user", name="Cluster user", description="ClusterUser")
        # device type
        factories.DeviceType(identifier="H", description="Host", priority=0)
        factories.DeviceType(identifier="AM", description="APC Masterswitch", priority=10)
        factories.DeviceType(identifier="NB", description="Netbotz", priority=20)
        factories.DeviceType(identifier="S", description="Manageable Switch", priority=-10)
        factories.DeviceType(identifier="R", description="RAID box", priority=-20)
        factories.DeviceType(identifier="P", description="Printer", priority=-30)
        factories.DeviceType(identifier="MD", description="Meta device", priority=128)
        factories.DeviceType(identifier="IBC", description="IBM Blade center", priority=-40)
        factories.DeviceType(identifier="CD", description="Controlling Device", priority=30)
        # partition fs
        factories.PartitionFS(name="reiserfs", identifier="f", descr="ReiserFS Filesystem", hexid="83", kernel_module="reiserfs")
        factories.PartitionFS(name="ext2", identifier="f", descr="Extended 2 Fileystem", hexid="83", kernel_module="ext2")
        factories.PartitionFS(name="ext3", identifier="f", descr="Extended 3 Fileystem", hexid="83", kernel_module="ext3")
        factories.PartitionFS(name="ext4", identifier="f", descr="Extended 4 Fileystem", hexid="83", kernel_module="ext4")
        factories.PartitionFS(name="swap", identifier="s", descr="SwapSpace", hexid="82")
        factories.PartitionFS(name="ext", identifier="e", descr="Extended Partition", hexid="f")
        factories.PartitionFS(name="empty", identifier="d", descr="Empty Partition", hexid="0")
        factories.PartitionFS(name="lvm", identifier="l", descr="LVM Partition", hexid="8e", kernel_module="dm_map")
        factories.PartitionFS(name="xfs", identifier="f", descr="XFS Filesystem", hexid="83", kernel_module="xfs")
        factories.PartitionFS(name="btrfs", identifier="f", descr="BTRFS Filesystem", hexid="83", kernel_module="btrfs")
        factories.PartitionFS(name="ocfs2", identifier="f", descr="OCFS2 Filesystem", hexid="83", kernel_module="ocfs2")
        # log status
        factories.LogStatus(identifier="c", log_level=200, name="critical")
        factories.LogStatus(identifier="e", log_level=100, name="error")
        factories.LogStatus(identifier="w", log_level=50, name="warning")
        factories.LogStatus(identifier="i", log_level=0, name="info")
        factories.LogStatus(identifier="n", log_level=-50, name="notice")
        # status
        factories.Status(status="memtest", memory_test=True)
        factories.Status(status="boot_local", boot_local=True)
        factories.Status(status="boot_iso", boot_iso=True)
        factories.Status(status="boot_clean", prod_link=True, is_clean=True)
        factories.Status(status="installation_clean", prod_link=True, do_install=True, is_clean=True)
        factories.Status(status="boot", prod_link=True)  # # FIXME ?
        factories.Status(status="installation", prod_link=True, do_install=True)  # # FIXME ?
        # network device type
        factories.NetworkDeviceType(identifier="lo", name_re="^lo\d*$", description="loopback devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="eth", name_re="^eth\d+$", description="ethernet devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="myri", name_re="^myri\d+$", description="myrinet devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="xenbr", name_re="^xenbr\d+$", description="xen bridge devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="tun", name_re="^tun\d+$", description="ethernet tunnel devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="ib", name_re="^ib\d+$", description="infiniband devices", mac_bytes=20)
        factories.NetworkDeviceType(identifier="bridge", name_re="^.*bridge.*$", description="generic bridge", mac_bytes=6)
        factories.NetworkDeviceType(identifier="vlan", name_re="^vlan\d+$", description="VLAN device", mac_bytes=6)
        factories.NetworkDeviceType(identifier="en", name_re="^(em|en(s|p).*|p\d+p)\d+$", description="Ethernet new scheme", mac_bytes=6)
        # network types
        factories.NetworkType(identifier="b", description="boot network")
        factories.NetworkType(identifier="p", description="production network")
        factories.NetworkType(identifier="s", description="slave network")
        factories.NetworkType(identifier="o", description="other network")
        factories.NetworkType(identifier="l", description="local network")
        # netdevice speed
        factories.NetDeviceSpeed(speed_bps=10000000, check_via_ethtool=False, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=10000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=100000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=100000000, check_via_ethtool=True, full_duplex=False)
        factories.NetDeviceSpeed(speed_bps=1000000000, check_via_ethtool=False, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=1000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=10000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=40000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=56000000000, check_via_ethtool=True, full_duplex=True)
        # host check command
        factories.HostCheckCommand(name="check-host-alive", command_line="$USER2$ -m localhost ping $HOSTADDRESS$ 5 5.0")
        factories.HostCheckCommand(name="check-host-alive-2", command_line="$USER2$ -m $HOSTADDRESS$ version")
        factories.HostCheckCommand(name="check-host-ok", command_line="$USER1$/check_dummy 0 up")
        factories.HostCheckCommand(name="check-host-down", command_line="$USER1$/check_dummy 2 down")
        # hints

        _server_cfg = factories.ConfigHint(
            config_name="server",
            valid_for_meta=False,
            config_description="server device",
            help_text_short="activate device as a server",
            help_text_html="""
<h2>Use this option to activate server functionality</h2>
            """,
        )
        modules_cfg = factories.ConfigHint(
            config_name="modules_system",
            config_description="modules system (client part)",
            valid_for_meta=True,
            help_text_short="activate module system",
            help_text_html="""
<h2>Enable the module system<h2>
            """,
        )
        factories.ConfigScriptHint(
            config_hint=modules_cfg,
            script_name="client_modules",
            help_text_short="configures module access for clients",
            help_text_html="""
<h3>Enables the module system on a client</h3>
May be relative to the NFS4 root export
""",
            ac_flag=True,
            ac_description="config script",
            ac_value="""
# add link
config.add_link_object("/opt/modulefiles", "/.opt/modulefiles")
            """,
        )
        # modules export
        modules_export_cfg = factories.ConfigHint(
            config_name="modules_export",
            exact_match=False,
            config_description="export entry for the modules share (server)",
            valid_for_meta=True,
            help_text_short="export entry for the modules share",
            help_text_html="""
<h2>Configures an export entry for the modules system</h2>
Configures a cluster-wide filesystem share for the modules dir. Attach to
a device to create the according automounter entries
            """,
        )
        factories.ConfigVarHint(
            config_hint=modules_export_cfg,
            var_name="export",
            help_text_short="the directory to export",
            help_text_html="""
<h3>Define the directory to export</h3>
May be relative to the NFS4 root export
""",
            ac_flag=True,
            ac_type="str",
            ac_description="export path",
            ac_value="/opt/cluster/Modules/modulefiles",
        )
        factories.ConfigVarHint(
            config_hint=modules_export_cfg,
            var_name="import",
            help_text_short="the import path",
            help_text_html="""
<h3>Define the import path</h3>
Used for automounter maps
""",
            ac_flag=True,
            ac_type="str",
            ac_description="import path",
            ac_value="/.opt/modulefiles",
        )
        factories.ConfigVarHint(
            config_hint=modules_export_cfg,
            var_name="options",
            help_text_short="the mount options",
            help_text_html="""
<h3>Sets the mount options</h3>
Used for automounter maps
""",
            ac_flag=True,
            ac_type="str",
            ac_description="options",
            ac_value="-soft,tcp,lock,rsize=8192,wsize=8192,noac,lookupcache=none,vers=4,port=2049",
        )
        # export entries
        export_cfg = factories.ConfigHint(
            config_name="export",
            exact_match=False,
            config_description="export entry (share)",
            valid_for_meta=True,
            help_text_short="creates an export entry",
            help_text_html="""
<h2>Configures an export entry (for sharing)</h2>
Configures a cluster-wide filesystem share. Attach to
a device to create the according automounter entries
            """,
        )
        factories.ConfigVarHint(
            config_hint=export_cfg,
            var_name="export",
            help_text_short="the directory to export",
            help_text_html="""
<h3>Define the directory to export</h3>
May be relative to the NFS4 root export
""",
            ac_flag=True,
            ac_type="str",
            ac_description="export path",
            ac_value="/export",
        )
        factories.ConfigVarHint(
            config_hint=export_cfg,
            var_name="import",
            help_text_short="the import path",
            help_text_html="""
<h3>Define the import path</h3>
Used for automounter maps
""",
            ac_flag=True,
            ac_type="str",
            ac_description="import path",
            ac_value="/import",
        )
        factories.ConfigVarHint(
            config_hint=export_cfg,
            var_name="options",
            help_text_short="the mount options",
            help_text_html="""
<h3>Sets the mount options</h3>
Used for automounter maps
""",
            ac_flag=True,
            ac_type="str",
            ac_description="options",
            ac_value="-soft,tcp,lock,rsize=8192,wsize=8192,noac,lookupcache=none,vers=4,port=2049",
        )
        # home export entries
        homedir_export_cfg = factories.ConfigHint(
            config_name="homedir_export",
            exact_match=False,
            config_description="export entry (share) for home",
            valid_for_meta=True,
            help_text_short="creates an export entry for home",
            help_text_html="""
<h2>Configures an export entry (for sharing)</h2>
Configures a cluster-wide filesystem share. Attach to
a device to create the according automounter entries
            """,
        )
        factories.ConfigVarHint(
            config_hint=homedir_export_cfg,
            var_name="homeexport",
            help_text_short="the directory to export",
            help_text_html="""
<h3>Define the directory to export</h3>
May be relative to the NFS4 root export
""",
            ac_flag=True,
            ac_type="str",
            ac_description="export path",
            ac_value="/export_change_me",
        )
        factories.ConfigVarHint(
            config_hint=homedir_export_cfg,
            var_name="createdir",
            help_text_short="where to create the homes",
            help_text_html="""
<h3>Define the creation path</h3>
Used by the clusterserver, can be different from export_path (for example when NFSv4 is used)
""",
            ac_flag=True,
            ac_type="str",
            ac_description="create path",
            ac_value="/create_change_me",
        )
        factories.ConfigVarHint(
            config_hint=homedir_export_cfg,
            var_name="options",
            help_text_short="the mount options",
            help_text_html="""
<h3>Sets the mount options</h3>
Used for automounter maps
""",
            ac_flag=True,
            ac_type="str",
            ac_description="options",
            ac_value="-soft,tcp,lock,rsize=8192,wsize=8192,noac,lookupcache=none,vers=4,port=2049",
        )
        ldap_server_cfg = factories.ConfigHint(
            config_name="ldap_server",
            config_description="LDAP Server",
            valid_for_meta=False,
            help_text_short="device acts as an LDAP-server",
            help_text_html="""
<h2>Enable LDAP-server functionality</h2>
The following server command are available:
<ul>
<li><tt>init_ldap_config</tt> Create basic LDAP entries</li>
<li><tt>sync_ldap_config</tt> Syncs the LDAP tree with the Cluster database</li>
</ul>
"""
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="base_dn",
            help_text_short="define LDAP base DN",
            help_text_html="""
<h3>Define the base DN for the LDAP sync</h3>
""",
            ac_flag=True,
            ac_type="str",
            ac_description="Base DN",
            ac_value="dc=test,dc=ac,dc=at",
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="admin_cn",
            help_text_short="CN of the admin user",
            help_text_html="""
<h3>CN of the admin user</h3>
Enter without 'cn=', in most cases admin is enough
""",
            ac_flag=True,
            ac_type="str",
            ac_description="admin CN (relative to base DN without 'cn=')",
            ac_value="admin",
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="root_passwd",
            help_text_short="password of the admin user",
            help_text_html="""
<h3>Password of the admin user</h3>
Stored as cleartext password, handle with care.
""",
            ac_flag=True,
            ac_type="str",
            ac_description="LDAP admin password",
            ac_value="changeme",
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="user_object_classes",
            help_text_short="object classes for user objects",
            help_text_html="""
<h3>Object Classes to use for user objects</h3>
A space (or comma) separated list of object classes to use
for user objects. Can contain one or more of
<ul>
<li>account</li>
<li>posixAccount</li>
<li>shadowAccount</li>
<li>shadowAccount</li>
<li>top</li>
</ul>
"""
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="group_object_classes",
            help_text_short="object classes for group objects",
            help_text_html="""
<h3>Object Classes to use for group objects</h3>
A space (or comma) separated list of object classes to use
for group objects. Can contain one or more of
<ul>
<li>posixGroup</li>
<li>top</li>
<li>namedObject</li>
</ul>
"""
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="group_dn_template",
            help_text_short="template to create group dn",
            help_text_html="""
<h3>Template to specify group DN (distinguished name)</h3>
The template to create the group DN. Defaults to<br>
cn={GROUPNAME}<br>
where GROUPNAME extends to the name of the group.
"""
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="user_dn_template",
            help_text_short="template to create user dn",
            help_text_html="""
<h3>Template to specify user DN (distinguished name)</h3>
The template to create the user DN. Defaults to<br>
uid={USERNAME}<br>
where USERNAME extends to the login name of the user.
"""
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="group_base_template",
            help_text_short="template to create the group base dn",
            help_text_html="""
<h3>Template to specify the group base DN</h3>
This template define the DN for groups. A full group DN contains
of the group_dn_template plus the group_base template:<br>
GROUP_DN={GROUP_DN_TEMPLATE},{GROUP_BASE_TEMPLATE}
"""
        )
        factories.ConfigVarHint(
            config_hint=ldap_server_cfg,
            var_name="user_base_template",
            help_text_short="template to create the user base dn",
            help_text_html="""
<h3>Template to specify the user base DN</h3>
This template define the DN for users. A full user DN contains
of the user_dn_template plus the user_base template:<br>
USER_DN={USER_DN_TEMPLATE},{USER_BASE_TEMPLATE}
"""
        )
        add_fixtures(**options)
