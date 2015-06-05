# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
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

# from lxml.builder import E # @UnresolvedImport
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.crypto import get_random_string
from initat.cluster.backbone import factories
from initat.cluster.backbone.management.commands.fixtures import add_fixtures
from initat.cluster.backbone.models import ALL_LICENSES, get_license_descr, \
    get_related_models
from lxml import etree  # @UnresolvedImport
from initat.tools import logging_tools
import os
import sys

# old local_settings.py

LOCAL_CONFIG = "/etc/sysconfig/cluster/local_settings.py"

SNMP_NET_TYPES = [
    (1, 'other'),
    (2, 'regular1822'),
    (3, 'hdh1822'),
    (4, 'ddnX25'),
    (5, 'rfc877x25'),
    (6, 'ethernetCsmacd'),
    (7, 'iso88023Csmacd'),
    (8, 'iso88024TokenBus'),
    (9, 'iso88025TokenRing'),
    (10, 'iso88026Man'),
    (11, 'starLan'),
    (12, 'proteon10Mbit'),
    (13, 'proteon80Mbit'),
    (14, 'hyperchannel'),
    (15, 'fddi'),
    (16, 'lapb'),
    (17, 'sdlc'),
    (18, 'ds1'),
    (19, 'e1'),
    (20, 'basicISDN'),
    (21, 'primaryISDN'),
    (22, 'propPointToPointSerial'),
    (23, 'ppp'),
    (24, 'softwareLoopback'),
    (25, 'eon'),
    (26, 'ethernet3Mbit'),
    (27, 'nsip'),
    (28, 'slip'),
    (29, 'ultra'),
    (30, 'ds3'),
    (31, 'sip'),
    (32, 'frameRelay'),
    (33, 'rs232'),
    (34, 'para'),
    (35, 'arcnet'),
    (36, 'arcnetPlus'),
    (37, 'atm'),
    (38, 'miox25'),
    (39, 'sonet'),
    (40, 'x25ple'),
    (41, 'iso88022llc'),
    (42, 'localTalk'),
    (43, 'smdsDxi'),
    (44, 'frameRelayService'),
    (45, 'v35'),
    (46, 'hssi'),
    (47, 'hippi'),
    (48, 'modem'),
    (49, 'aal5'),
    (50, 'sonetPath'),
    (51, 'sonetVT'),
    (52, 'smdsIcip'),
    (53, 'propVirtual'),
    (54, 'propMultiplexor'),
    (55, 'ieee80212'),
    (56, 'fibreChannel'),
    (57, 'hippiInterface'),
    (58, 'frameRelayInterconnect'),
    (59, 'aflane8023'),
    (60, 'aflane8025'),
    (61, 'cctEmul'),
    (62, 'fastEther'),
    (63, 'isdn'),
    (64, 'v11'),
    (65, 'v36'),
    (66, 'g703at64k'),
    (67, 'g703at2mb'),
    (68, 'qllc'),
    (69, 'fastEtherFX'),
    (70, 'channel'),
    (71, 'ieee80211'),
    (72, 'ibm370parChan'),
    (73, 'escon'),
    (74, 'dlsw'),
    (75, 'isdns'),
    (76, 'isdnu'),
    (77, 'lapd'),
    (78, 'ipSwitch'),
    (79, 'rsrb'),
    (80, 'atmLogical'),
    (81, 'ds0'),
    (82, 'ds0Bundle'),
    (83, 'bsc'),
    (84, 'async'),
    (85, 'cnr'),
    (86, 'iso88025Dtr'),
    (87, 'eplrs'),
    (88, 'arap'),
    (89, 'propCnls'),
    (90, 'hostPad'),
    (91, 'termPad'),
    (92, 'frameRelayMPI'),
    (93, 'x213'),
    (94, 'adsl'),
    (95, 'radsl'),
    (96, 'sdsl'),
    (97, 'vdsl'),
    (98, 'iso88025CRFPInt'),
    (99, 'myrinet'),
    (100, 'voiceEM'),
    (101, 'voiceFXO'),
    (102, 'voiceFXS'),
    (103, 'voiceEncap'),
    (104, 'voiceOverIp'),
    (105, 'atmDxi'),
    (106, 'atmFuni'),
    (107, 'atmIma'),
    (108, 'pppMultilinkBundle'),
    (109, 'ipOverCdlc'),
    (110, 'ipOverClaw'),
    (111, 'stackToStack'),
    (112, 'virtualIpAddress'),
    (113, 'mpc'),
    (114, 'ipOverAtm'),
    (115, 'iso88025Fiber'),
    (116, 'tdlc'),
    (117, 'gigabitEthernet'),
    (118, 'hdlc'),
    (119, 'lapf'),
    (120, 'v37'),
    (121, 'x25mlp'),
    (122, 'x25huntGroup'),
    (123, 'transpHdlc'),
    (124, 'interleave'),
    (125, 'fast'),
    (126, 'ip'),
    (127, 'docsCableMaclayer'),
    (128, 'docsCableDownstream'),
    (129, 'docsCableUpstream'),
    (130, 'a12MppSwitch'),
    (131, 'tunnel'),
    (132, 'coffee'),
    (133, 'ces'),
    (134, 'atmSubInterface'),
    (135, 'l2vlan'),
    (136, 'l3ipvlan'),
    (137, 'l3ipxvlan'),
    (138, 'digitalPowerline'),
    (139, 'mediaMailOverIp'),
    (140, 'dtm'),
    (141, 'dcn'),
    (142, 'ipForward'),
    (143, 'msdsl'),
    (144, 'ieee1394'),
    (145, 'if-gsn'),
    (146, 'dvbRccMacLayer'),
    (147, 'dvbRccDownstream'),
    (148, 'dvbRccUpstream'),
    (149, 'atmVirtual'),
    (150, 'mplsTunnel'),
    (151, 'srp'),
    (152, 'voiceOverAtm'),
    (153, 'voiceOverFrameRelay'),
    (154, 'idsl'),
    (155, 'compositeLink'),
    (156, 'ss7SigLink'),
    (157, 'propWirelessP2P'),
    (158, 'frForward'),
    (159, 'rfc1483'),
    (160, 'usb'),
    (161, 'ieee8023adLag'),
    (162, 'bgppolicyaccounting'),
    (163, 'frf16MfrBundle'),
    (164, 'h323Gatekeeper'),
    (165, 'h323Proxy'),
    (166, 'mpls'),
    (167, 'mfSigLink'),
    (168, 'hdsl2'),
    (169, 'shdsl'),
    (170, 'ds1FDL'),
    (171, 'pos'),
    (172, 'dvbAsiIn'),
    (173, 'dvbAsiOut'),
    (174, 'plc'),
    (175, 'nfas'),
    (176, 'tr008'),
    (177, 'gr303RDT'),
    (178, 'gr303IDT'),
    (179, 'isup'),
    (180, 'propDocsWirelessMaclayer'),
    (181, 'propDocsWirelessDownstream'),
    (182, 'propDocsWirelessUpstream'),
    (183, 'hiperlan2'),
    (184, 'propBWAp2Mp'),
    (185, 'sonetOverheadChannel'),
    (186, 'digitalWrapperOverheadChannel'),
    (187, 'aal2'),
    (188, 'radioMAC'),
    (189, 'atmRadio'),
    (190, 'imt'),
    (191, 'mvl'),
    (192, 'reachDSL'),
    (193, 'frDlciEndPt'),
    (194, 'atmVciEndPt'),
    (195, 'opticalChannel'),
    (196, 'opticalTransport'),
    (197, 'propAtm'),
    (198, 'voiceOverCable'),
    (199, 'infiniband'),
    (200, 'teLink'),
    (201, 'q2931'),
    (202, 'virtualTg'),
    (203, 'sipTg'),
    (204, 'sipSig'),
    (205, 'docsCableUpstreamChannel'),
    (206, 'econet'),
    (207, 'pon155'),
    (208, 'pon622'),
    (209, 'bridge'),
    (210, 'linegroup'),
    (211, 'voiceEMFGD'),
    (212, 'voiceFGDEANA'),
    (213, 'voiceDID'),
    (214, 'mpegTransport'),
    (215, 'sixToFour'),
    (216, 'gtp'),
    (217, 'pdnEtherLoop1'),
    (218, 'pdnEtherLoop2'),
    (219, 'opticalChannelGroup'),
    (220, 'homepna'),
    (221, 'gfp'),
    (222, 'ciscoISLvlan'),
    (223, 'actelisMetaLOOP'),
    (224, 'fcipLink'),
    (225, 'rpr'),
    (226, 'qam'),
    (227, 'lmp'),
    (228, 'cblVectaStar'),
    (229, 'docsCableMCmtsDownstream'),
    (230, 'adsl2'),
    (231, 'macSecControlledIF'),
    (232, 'macSecUncontrolledIF'),
    (233, 'aviciOpticalEther'),
    (234, 'atmbond'),
    (235, 'voiceFGDOS'),
    (236, 'mocaVersion1'),
    (237, 'ieee80216WMAN'),
    (238, 'adsl2plus'),
    (239, 'dvbRcsMacLayer'),
    (240, 'dvbTdm'),
    (241, 'dvbRcsTdma'),
    (242, 'x86Laps'),
    (243, 'wwanPP'),
    (244, 'wwanPP2'),
    (245, 'voiceEBS'),
    (246, 'ifPwType'),
    (247, 'ilan'),
    (248, 'pip'),
    (249, 'aluELP'),
    (250, 'gpon'),
    (251, 'vdsl2'),
    (252, 'capwapDot11Profile'),
    (253, 'capwapDot11Bss'),
    (254, 'capwapWtpVirtualRadio'),
    (255, 'bits'),
    (256, 'docsCableUpstreamRfPort'),
    (257, 'cableDownstreamRfPort'),
    (258, 'vmwareVirtualNic'),
    (259, 'ieee802154'),
    (260, 'otnOdu'),
    (261, 'otnOtu'),
    (262, 'ifVfiType'),
    (263, 'g9981'),
    (264, 'g9982'),
    (265, 'g9983'),
    (266, 'aluEpon'),
    (267, 'aluEponOnu'),
    (268, 'aluEponPhysicalUni'),
    (269, 'aluEponLogicalLink'),
    (270, 'aluGponOnu'),
    (271, 'aluGponPhysicalUni'),
    (272, 'vmwareNicTeam'),
]


def _add_snmp_fixtures():
    def dummy_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        print "[{:d}] {}".format(log_level, what)

    # SNMP Network types
    for _if_type, _if_label in SNMP_NET_TYPES:
        factories.SNMPNetworkType(if_type=_if_type, if_label=_if_label)
    # SNMP fixtures
    factories.SNMPSchemeVendor(name="generic", company_info="generic schemes")
    factories.SNMPSchemeVendor(name="apc", company_info="American Power Conversion")
    try:
        from initat.snmp.handler.instances import handlers
    except ImportError:
        # not snmp handler instances found, ignore
        pass
    else:
        handlers = [_h(dummy_log) for _h in handlers]
        for _handler in handlers:
            cur_scheme = factories.SNMPScheme(
                name=_handler.Meta.name,
                version=_handler.Meta.version,
                description=_handler.Meta.description,
                collect=_handler.Meta.collect,
                initial=_handler.Meta.initial,
                priority=_handler.Meta.priority,
                power_control=_handler.Meta.power_control,
                mon_check=getattr(_handler.Meta, "mon_check", False),
                snmp_scheme_vendor=factories.SNMPSchemeVendor(name=_handler.Meta.vendor_name),
            )
            for tl_oid in _handler.Meta.tl_oids:
                factories.SNMPSchemeTLOID(
                    oid=tl_oid,
                    snmp_scheme=cur_scheme,
                )


class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ("Creates the cluster fixtures.")

    def handle(self, **options):
        print("creating fixtures...")
        # global settings

        # LogSource
        factories.LogSourceFactory(identifier="webfrontend", description="via Webfrontend", device=None)
        factories.LogSourceFactory(identifier="commandline", description="via CommandLine", device=None)
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
        # LogLevel
        factories.LogLevelFactory(identifier="c", level=logging_tools.LOG_LEVEL_CRITICAL, name="critical")
        factories.LogLevelFactory(identifier="e", level=logging_tools.LOG_LEVEL_ERROR, name="error")
        factories.LogLevelFactory(identifier="w", level=logging_tools.LOG_LEVEL_WARN, name="warning")
        factories.LogLevelFactory(identifier="o", level=logging_tools.LOG_LEVEL_OK, name="ok")
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
        factories.NetworkDeviceType(identifier="en", name_re="^(em|en)(s|p)\d*(s\d+)*(u\d+)*$", description="Ethernet new scheme", mac_bytes=6)
        factories.NetworkDeviceType(identifier="wl", name_re="^wl(p\d+)*(s\d+)*$", description="WLAN devices", mac_bytes=6)
        factories.NetworkDeviceType(identifier="other", name_re="^.*$", description="other interfaces (from SNMP)", mac_bytes=6, for_matching=False)
        # network types
        factories.NetworkType(identifier="b", description="boot network")
        factories.NetworkType(identifier="p", description="production network")
        factories.NetworkType(identifier="s", description="slave network")
        factories.NetworkType(identifier="o", description="other network")
        factories.NetworkType(identifier="l", description="local network")
        # netdevice speed

        factories.NetDeviceSpeed(speed_bps=0, check_via_ethtool=False, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=10000000, check_via_ethtool=False, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=10000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=100000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=100000000, check_via_ethtool=True, full_duplex=False)
        # 1GBit / se
        factories.NetDeviceSpeed(speed_bps=1000000000, check_via_ethtool=False, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=1000000000, check_via_ethtool=True, full_duplex=True)
        # Trunks with 2 and 4 GB/sec
        factories.NetDeviceSpeed(speed_bps=2000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=4000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=10000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=40000000000, check_via_ethtool=True, full_duplex=True)
        factories.NetDeviceSpeed(speed_bps=56000000000, check_via_ethtool=True, full_duplex=True)
        # host check command
        factories.HostCheckCommand(name="check-host-alive", command_line="$USER2$ -m localhost ping $HOSTADDRESS$ 5 5.0")
        factories.HostCheckCommand(name="check-host-alive-2", command_line="$USER2$ -m $HOSTADDRESS$ version")
        factories.HostCheckCommand(name="check-host-ok", command_line="$USER1$/check_dummy 0 up")
        factories.HostCheckCommand(name="check-host-down", command_line="$USER1$/check_dummy 2 down")
        # virtual desktop protocols
        factories.VirtualDesktopProtocol(name="vnc", description="VNC", binary="vncserver")
        factories.VirtualDesktopProtocol(name="rdc", description="Remote Desktop Connection", binary="")
        factories.VirtualDesktopProtocol(name="spice", description="SPICE", binary="")
        # window managers
        factories.WindowManager(name="kde", description="KDE", binary="startkde")
        factories.WindowManager(name="gnome", description="GNOME", binary="gnome-session")
        factories.WindowManager(name="windowmaker", description="Window Maker", binary="wmaker")

        # ComCapabilities
        factories.ComCapability(
            matchcode="hm",
            name="host-monitoring",
            info="init.at host-monitoring software",
            port_spec="2001/tcp",
        )
        factories.ComCapability(
            matchcode="snmp",
            name="SNMP",
            info="Simple Network Management Protocol",
            port_spec="161/tcp, 161/udp",
        )
        factories.ComCapability(
            matchcode="ipmi",
            name="IPMI",
            info="Intelligent Platform Management Interface",
            port_spec="623/udp",
        )
        factories.ComCapability(
            matchcode="wmi",
            name="WMI",
            info="Windows Management Instrumentation",
            port_spec="135/tcp",
        )
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
        _add_snmp_fixtures()
        add_fixtures(**options)
