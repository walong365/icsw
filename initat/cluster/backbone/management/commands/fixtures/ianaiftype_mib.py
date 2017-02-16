# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
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
""" IANA IfType constants """


class IANAIfType(object):
    def __init__(self, idx, name, descr="", regex="", mac_bytes=6):
        self.idx = idx
        self.name = name
        self.description = descr
        self.regex = regex
        self.mac_bytes = mac_bytes


IANAIfTypes = [
    IANAIfType(1, "other", "none of the following", regex="^.*$"),
    IANAIfType(2, "regular1822"),
    IANAIfType(3, "hdh1822"),
    IANAIfType(4, "ddnX25"),
    IANAIfType(5, "rfc877x25"),
    IANAIfType(
        6,
        "ethernetCsmacd",
        "for all ethernet-like interfaces, regardless of speed, as per RFC3635",
        regex="^(eth|en).*$",
    ),
    IANAIfType(7, "iso88023Csmacd", "Deprecated via RFC3635 ethernetCsmacd (6) should be used instead"),
    IANAIfType(8, "iso88024TokenBus"),
    IANAIfType(9, "iso88025TokenRing"),
    IANAIfType(10, "iso88026Man"),
    IANAIfType(11, "starLan", "Deprecated via RFC3635 ethernetCsmacd (6) should be used instead"),
    IANAIfType(12, "proteon10Mbit"),
    IANAIfType(13, "proteon80Mbit"),
    IANAIfType(14, "hyperchannel"),
    IANAIfType(15, "fddi"),
    IANAIfType(16, "lapb"),
    IANAIfType(17, "sdlc"),
    IANAIfType(18, "ds1", "DS1-MIB"),
    IANAIfType(19, "e1", "Obsolete see DS1-MIB"),
    IANAIfType(20, "basicISDN", "no longer used see also RFC2127"),
    IANAIfType(21, "primaryISDN", "no longer used see also RFC2127"),
    IANAIfType(22, "propPointToPointSerial", "proprietary serial"),
    IANAIfType(23, "ppp"),
    IANAIfType(24, "softwareLoopback", regex="^lo.*$"),
    IANAIfType(25, "eon", "CLNP over IP"),
    IANAIfType(26, "ethernet3Mbit"),
    IANAIfType(27, "nsip", "XNS over IP"),
    IANAIfType(28, "slip", "generic SLIP"),
    IANAIfType(29, "ultra", "ULTRA technologies"),
    IANAIfType(30, "ds3", "DS3-MIB"),
    IANAIfType(31, "sip", "SMDS, coffee"),
    IANAIfType(32, "frameRelay", "DTE only."),
    IANAIfType(33, "rs232"),
    IANAIfType(34, "para", "parallel-port"),
    IANAIfType(35, "arcnet", "arcnet"),
    IANAIfType(36, "arcnetPlus", "arcnet plus"),
    IANAIfType(37, "atm", "ATM cells"),
    IANAIfType(38, "miox25"),
    IANAIfType(39, "sonet", "SONET or SDH"),
    IANAIfType(40, "x25ple"),
    IANAIfType(41, "iso88022llc"),
    IANAIfType(42, "localTalk"),
    IANAIfType(43, "smdsDxi"),
    IANAIfType(44, "frameRelayService", "FRNETSERV-MIB"),
    IANAIfType(45, "v35"),
    IANAIfType(46, "hssi"),
    IANAIfType(47, "hippi"),
    IANAIfType(48, "modem", "Generic modem"),
    IANAIfType(49, "aal5", "AAL5 over ATM"),
    IANAIfType(50, "sonetPath"),
    IANAIfType(51, "sonetVT"),
    IANAIfType(52, "smdsIcip", "SMDS InterCarrier Interface"),
    IANAIfType(53, "propVirtual", "proprietary virtual/internal"),
    IANAIfType(54, "propMultiplexor", "proprietary multiplexing"),
    IANAIfType(55, "ieee80212", "100BaseVG"),
    IANAIfType(56, "fibreChannel", "Fibre Channel"),
    IANAIfType(57, "hippiInterface", "HIPPI interfaces"),
    IANAIfType(58, "frameRelayInterconnect", "Obsolete, use either frameRelay(32) or frameRelayService(44)."),
    IANAIfType(59, "aflane8023", "ATM Emulated LAN for 802.3"),
    IANAIfType(60, "aflane8025", "ATM Emulated LAN for 802.5"),
    IANAIfType(61, "cctEmul", "ATM Emulated circuit"),
    IANAIfType(62, "fastEther", "Obsoleted via RFC3635 ethernetCsmacd (6) should be used instead"),
    IANAIfType(63, "isdn", "ISDN and X.25"),
    IANAIfType(64, "v11", "CCITT V.11/X.21"),
    IANAIfType(65, "v36", "CCITT V.36"),
    IANAIfType(66, "g703at64k", "CCITT G703 at 64Kbps"),
    IANAIfType(67, "g703at2mb", "Obsolete see DS1-MIB"),
    IANAIfType(68, "qllc", "SNA QLLC"),
    IANAIfType(69, "fastEtherFX", "Obsoleted via RFC3635 ethernetCsmacd (6) should be used instead"),
    IANAIfType(70, "channel", "channel"),
    IANAIfType(71, "ieee80211", "radio spread spectrum"),
    IANAIfType(72, "ibm370parChan", "IBM System 360/370 OEMI Channel"),
    IANAIfType(73, "escon", "IBM Enterprise Systems Connection"),
    IANAIfType(74, "dlsw", "Data Link Switching"),
    IANAIfType(75, "isdns", "ISDN S/T interface"),
    IANAIfType(76, "isdnu", "ISDN U interface"),
    IANAIfType(77, "lapd", "Link Access Protocol D"),
    IANAIfType(78, "ipSwitch", "IP Switching Objects"),
    IANAIfType(79, "rsrb", "Remote Source Route Bridging"),
    IANAIfType(80, "atmLogical", "ATM Logical Port"),
    IANAIfType(81, "ds0", "Digital Signal Level 0"),
    IANAIfType(82, "ds0Bundle", "group of ds0s on the same ds1"),
    IANAIfType(83, "bsc", "Bisynchronous Protocol"),
    IANAIfType(84, "async", "Asynchronous Protocol"),
    IANAIfType(85, "cnr", "Combat Net Radio"),
    IANAIfType(86, "iso88025Dtr", "ISO 802.5r DTR"),
    IANAIfType(87, "eplrs", "Ext Pos Loc Report Sys"),
    IANAIfType(88, "arap", "Appletalk Remote Access Protocol"),
    IANAIfType(89, "propCnls", "Proprietary Connectionless Protocol"),
    IANAIfType(90, "hostPad", "CCITT-ITU X.29 PAD Protocol"),
    IANAIfType(91, "termPad", "CCITT-ITU X.3 PAD Facility"),
    IANAIfType(92, "frameRelayMPI", "Multiproto Interconnect over FR"),
    IANAIfType(93, "x213", "CCITT-ITU X213"),
    IANAIfType(94, "adsl", "Asymmetric Digital Subscriber Loop"),
    IANAIfType(95, "radsl", "Rate-Adapt. Digital Subscriber Loop"),
    IANAIfType(96, "sdsl", "Symmetric Digital Subscriber Loop"),
    IANAIfType(97, "vdsl", "Very H-Speed Digital Subscrib. Loop"),
    IANAIfType(98, "iso88025CRFPInt", "ISO 802.5 CRFP"),
    IANAIfType(99, "myrinet", "Myricom Myrinet", regex="^myri.*$"),
    IANAIfType(100, "voiceEM", "voice recEive and transMit"),
    IANAIfType(101, "voiceFXO", "voice Foreign Exchange Office"),
    IANAIfType(102, "voiceFXS", "voice Foreign Exchange Station"),
    IANAIfType(103, "voiceEncap", "voice encapsulation"),
    IANAIfType(104, "voiceOverIp", "voice over IP encapsulation"),
    IANAIfType(105, "atmDxi", "ATM DXI"),
    IANAIfType(106, "atmFuni", "ATM FUNI"),
    IANAIfType(107, "atmIma", "ATM IMA"),
    IANAIfType(108, "pppMultilinkBundle", "PPP Multilink Bundle"),
    IANAIfType(109, "ipOverCdlc", "IBM ipOverCdlc"),
    IANAIfType(110, "ipOverClaw", "IBM Common Link Access to Workstn"),
    IANAIfType(111, "stackToStack", "IBM stackToStack"),
    IANAIfType(112, "virtualIpAddress", "IBM VIPA"),
    IANAIfType(113, "mpc", "IBM multi-protocol channel support"),
    IANAIfType(114, "ipOverAtm", "IBM ipOverAtm"),
    IANAIfType(115, "iso88025Fiber", "ISO 802.5j Fiber Token Ring"),
    IANAIfType(116, "tdlc", "IBM twinaxial data link control"),
    IANAIfType(117, "gigabitEthernet", "Obsoleted via RFC3635 ethernetCsmacd (6) should be used instead"),
    IANAIfType(118, "hdlc", "HDLC"),
    IANAIfType(119, "lapf", "LAP F"),
    IANAIfType(120, "v37", "V.37"),
    IANAIfType(121, "x25mlp", "Multi-Link Protocol"),
    IANAIfType(122, "x25huntGroup", "X25 Hunt Group"),
    IANAIfType(123, "transpHdlc", "Transp HDLC"),
    IANAIfType(124, "interleave", "Interleave channel"),
    IANAIfType(125, "fast", "Fast channel"),
    IANAIfType(126, "ip", "IP (for APPN HPR in IP networks)"),
    IANAIfType(127, "docsCableMaclayer", "CATV Mac Layer"),
    IANAIfType(128, "docsCableDownstream", "CATV Downstream interface"),
    IANAIfType(129, "docsCableUpstream", "CATV Upstream interface"),
    IANAIfType(130, "a12MppSwitch", "Avalon Parallel Processor"),
    IANAIfType(131, "tunnel", "Encapsulation interface", regex="^tun.*$"),
    IANAIfType(132, "coffee", "coffee pot"),
    IANAIfType(133, "ces", "Circuit Emulation Service"),
    IANAIfType(134, "atmSubInterface", "ATM Sub Interface"),
    IANAIfType(135, "l2vlan", "Layer 2 Virtual LAN using 802.1Q"),
    IANAIfType(136, "l3ipvlan", "Layer 3 Virtual LAN using IP"),
    IANAIfType(137, "l3ipxvlan", "Layer 3 Virtual LAN using IPX"),
    IANAIfType(138, "digitalPowerline", "IP over Power Lines"),
    IANAIfType(139, "mediaMailOverIp", "Multimedia Mail over IP"),
    IANAIfType(140, "dtm", "Dynamic syncronous Transfer Mode"),
    IANAIfType(141, "dcn", "Data Communications Network"),
    IANAIfType(142, "ipForward", "IP Forwarding Interface"),
    IANAIfType(143, "msdsl", "Multi-rate Symmetric DSL"),
    IANAIfType(144, "ieee1394", "IEEE1394 High Performance Serial Bus"),
    IANAIfType(145, "if-gsn", "HIPPI-6400"),
    IANAIfType(146, "dvbRccMacLayer", "DVB-RCC MAC Layer"),
    IANAIfType(147, "dvbRccDownstream", "DVB-RCC Downstream Channel"),
    IANAIfType(148, "dvbRccUpstream", "DVB-RCC Upstream Channel"),
    IANAIfType(149, "atmVirtual", "ATM Virtual Interface"),
    IANAIfType(150, "mplsTunnel", "MPLS Tunnel Virtual Interface"),
    IANAIfType(151, "srp", "Spatial Reuse Protocol"),
    IANAIfType(152, "voiceOverAtm", "Voice Over ATM"),
    IANAIfType(153, "voiceOverFrameRelay", "Voice Over Frame Relay"),
    IANAIfType(154, "idsl", "Digital Subscriber Loop over ISDN"),
    IANAIfType(155, "compositeLink", "Avici Composite Link Interface"),
    IANAIfType(156, "ss7SigLink", "SS7 Signaling Link"),
    IANAIfType(157, "propWirelessP2P", "Prop. P2P wireless interface"),
    IANAIfType(158, "frForward", "Frame Forward Interface"),
    IANAIfType(159, "rfc1483", "Multiprotocol over ATM AAL5"),
    IANAIfType(160, "usb", "USB Interface"),
    IANAIfType(161, "ieee8023adLag", "IEEE 802.3ad Link Aggregate"),
    IANAIfType(162, "bgppolicyaccounting", "BGP Policy Accounting"),
    IANAIfType(163, "frf16MfrBundle", "FRF .16 Multilink Frame Relay"),
    IANAIfType(164, "h323Gatekeeper", "H323 Gatekeeper"),
    IANAIfType(165, "h323Proxy", "H323 Voice and Video Proxy"),
    IANAIfType(166, "mpls", "MPLS"),
    IANAIfType(167, "mfSigLink", "Multi-frequency signaling link"),
    IANAIfType(168, "hdsl2", "High Bit-Rate DSL - 2nd generation"),
    IANAIfType(169, "shdsl", "Multirate HDSL2"),
    IANAIfType(170, "ds1FDL", "Facility Data Link 4Kbps on a DS1"),
    IANAIfType(171, "pos", "Packet over SONET/SDH Interface"),
    IANAIfType(172, "dvbAsiIn", "DVB-ASI Input"),
    IANAIfType(173, "dvbAsiOut", "DVB-ASI Output"),
    IANAIfType(174, "plc", "Power Line Communtications"),
    IANAIfType(175, "nfas", "Non Facility Associated Signaling"),
    IANAIfType(176, "tr008", "TR008"),
    IANAIfType(177, "gr303RDT", "Remote Digital Terminal"),
    IANAIfType(178, "gr303IDT", "Integrated Digital Terminal"),
    IANAIfType(179, "isup", "ISUP"),
    IANAIfType(180, "propDocsWirelessMaclayer", "Cisco proprietary Maclayer"),
    IANAIfType(181, "propDocsWirelessDownstream", "Cisco proprietary Downstream"),
    IANAIfType(182, "propDocsWirelessUpstream", "Cisco proprietary Upstream"),
    IANAIfType(183, "hiperlan2", "HIPERLAN Type 2 Radio Interface"),
    IANAIfType(
        184,
        "propBWAp2Mp",
        "PropBroadbandWirelessAccesspt2multipt use of this iftype for IEEE 802.16 WMAN interfaces as "
        "per IEEE Std 802.16f is deprecated and ifType 237 should be used instead."
    ),
    IANAIfType(185, "sonetOverheadChannel", "SONET Overhead Channel"),
    IANAIfType(186, "digitalWrapperOverheadChannel", "Digital Wrapper"),
    IANAIfType(187, "aal2", "ATM adaptation layer 2"),
    IANAIfType(188, "radioMAC", "MAC layer over radio links"),
    IANAIfType(189, "atmRadio", "ATM over radio links"),
    IANAIfType(190, "imt", "Inter Machine Trunks"),
    IANAIfType(191, "mvl", "Multiple Virtual Lines DSL"),
    IANAIfType(192, "reachDSL", "Long Reach DSL"),
    IANAIfType(193, "frDlciEndPt", "Frame Relay DLCI End Point"),
    IANAIfType(194, "atmVciEndPt", "ATM VCI End Point"),
    IANAIfType(195, "opticalChannel", "Optical Channel"),
    IANAIfType(196, "opticalTransport", "Optical Transport"),
    IANAIfType(197, "propAtm", "Proprietary ATM"),
    IANAIfType(198, "voiceOverCable", "Voice Over Cable Interface"),
    IANAIfType(199, "infiniband", "Infiniband", regex="^ib.*", mac_bytes=20),
    IANAIfType(200, "teLink", "TE Link"),
    IANAIfType(201, "q2931", "Q.2931"),
    IANAIfType(202, "virtualTg", "Virtual Trunk Group"),
    IANAIfType(203, "sipTg", "SIP Trunk Group"),
    IANAIfType(204, "sipSig", "SIP Signaling"),
    IANAIfType(205, "docsCableUpstreamChannel", "CATV Upstream Channel"),
    IANAIfType(206, "econet", "Acorn Econet"),
    IANAIfType(207, "pon155", "FSAN 155Mb Symetrical PON interface"),
    IANAIfType(208, "pon622", "FSAN622Mb Symetrical PON interface"),
    IANAIfType(209, "bridge", "Transparent bridge interface"),
    IANAIfType(210, "linegroup", "Interface common to multiple lines"),
    IANAIfType(211, "voiceEMFGD", "voice E&M Feature Group D"),
    IANAIfType(212, "voiceFGDEANA", "voice FGD Exchange Access North American"),
    IANAIfType(213, "voiceDID", "voice Direct Inward Dialing"),
    IANAIfType(214, "mpegTransport", "MPEG transport interface"),
    IANAIfType(215, "sixToFour", "6to4 interface (DEPRECATED)"),
    IANAIfType(216, "gtp", "GTP (GPRS Tunneling Protocol)"),
    IANAIfType(217, "pdnEtherLoop1", "Paradyne EtherLoop 1"),
    IANAIfType(218, "pdnEtherLoop2", "Paradyne EtherLoop 2"),
    IANAIfType(219, "opticalChannelGroup", "Optical Channel Group"),
    IANAIfType(220, "homepna", "HomePNA ITU-T G.989"),
    IANAIfType(221, "gfp", "Generic Framing Procedure (GFP)"),
    IANAIfType(222, "ciscoISLvlan", "Layer 2 Virtual LAN using Cisco ISL"),
    IANAIfType(223, "actelisMetaLOOP", "Acteleis proprietary MetaLOOP High Speed Link"),
    IANAIfType(224, "fcipLink", "FCIP Link"),
    IANAIfType(225, "rpr", "Resilient Packet Ring Interface Type"),
    IANAIfType(226, "qam", "RF Qam Interface"),
    IANAIfType(227, "lmp", "Link Management Protocol"),
    IANAIfType(228, "cblVectaStar", "Cambridge Broadband Networks Limited VectaStar"),
    IANAIfType(229, "docsCableMCmtsDownstream", "CATV Modular CMTS Downstream Interface"),
    IANAIfType(230, "adsl2", "Asymmetric Digital Subscriber Loop Version 2 (DEPRECATED/OBSOLETED - please use adsl2plus 238 instead)"),
    IANAIfType(231, "macSecControlledIF", "MACSecControlled"),
    IANAIfType(232, "macSecUncontrolledIF", "MACSecUncontrolled"),
    IANAIfType(233, "aviciOpticalEther", "Avici Optical Ethernet Aggregate"),
    IANAIfType(234, "atmbond", "atmbond"),
    IANAIfType(235, "voiceFGDOS", "voice FGD Operator Services"),
    IANAIfType(236, "mocaVersion1", "MultiMedia over Coax Alliance (MoCA) Interface as documented in information provided privately to IANA"),
    IANAIfType(237, "ieee80216WMAN", "IEEE 802.16 WMAN interface"),
    IANAIfType(238, "adsl2plus", "Asymmetric Digital Subscriber Loop Version 2, Version 2 Plus and all variants"),
    IANAIfType(239, "dvbRcsMacLayer", "DVB-RCS MAC Layer"),
    IANAIfType(240, "dvbTdm", "DVB Satellite TDM"),
    IANAIfType(241, "dvbRcsTdma", "DVB-RCS TDMA"),
    IANAIfType(242, "x86Laps", "LAPS based on ITU-T X.86/Y.1323"),
    IANAIfType(243, "wwanPP", "3GPP WWAN"),
    IANAIfType(244, "wwanPP2", "3GPP2 WWAN"),
    IANAIfType(245, "voiceEBS", "voice P-phone EBS physical interface"),
    IANAIfType(246, "ifPwType", "Pseudowire interface type"),
    IANAIfType(247, "ilan", "Internal LAN on a bridge per IEEE 802.1ap"),
    IANAIfType(248, "pip", "Provider Instance Port on a bridge per IEEE 802.1ah PBB"),
    IANAIfType(249, "aluELP", "Alcatel-Lucent Ethernet Link Protection"),
    IANAIfType(250, "gpon", "Gigabit-capable passive optical networks (G-PON) as per ITU-T G.948"),
    IANAIfType(251, "vdsl2", "Very high speed digital subscriber line Version 2 (as per ITU-T Recommendation G.993.2)"),
    IANAIfType(252, "capwapDot11Profile", "WLAN Profile Interface"),
    IANAIfType(253, "capwapDot11Bss", "WLAN BSS Interface"),
    IANAIfType(254, "capwapWtpVirtualRadio", "WTP Virtual Radio Interface"),
    IANAIfType(255, "bits", "bitsport"),
    IANAIfType(256, "docsCableUpstreamRfPort", "DOCSIS CATV Upstream RF Port"),
    IANAIfType(257, "cableDownstreamRfPort", "CATV downstream RF port"),
    IANAIfType(258, "vmwareVirtualNic", "VMware Virtual Network Interface"),
    IANAIfType(259, "ieee802154", "IEEE 802.15.4 WPAN interface"),
    IANAIfType(260, "otnOdu", "OTN Optical Data Unit"),
    IANAIfType(261, "otnOtu", "OTN Optical channel Transport Unit"),
    IANAIfType(262, "ifVfiType", "VPLS Forwarding Instance Interface Type"),
    IANAIfType(263, "g9981", "G.998.1 bonded interface"),
    IANAIfType(264, "g9982", "G.998.2 bonded interface"),
    IANAIfType(265, "g9983", "G.998.3 bonded interface"),
    IANAIfType(266, "aluEpon", "Ethernet Passive Optical Networks (E-PON)"),
    IANAIfType(267, "aluEponOnu", "EPON Optical Network Unit"),
    IANAIfType(268, "aluEponPhysicalUni", "EPON physical User to Network interface"),
    IANAIfType(269, "aluEponLogicalLink", "The emulation of a point-to-point link over the EPON layer"),
    IANAIfType(270, "aluGponOnu", "GPON Optical Network Unit"),
    IANAIfType(271, "aluGponPhysicalUni", "GPON physical User to Network interface"),
    IANAIfType(272, "vmwareNicTeam", "VMware NIC Team"),
    IANAIfType(277, "docsOfdmDownstream", "CATV Downstream OFDM interface"),
    IANAIfType(278, "docsOfdmaUpstream", "CATV Upstream OFDMA interface"),
    IANAIfType(279, "gfast", "G.fast port"),
    IANAIfType(280, "sdci", "SDCI (IO-Link)"),
    IANAIfType(281, "xboxWireless", "Xbox wireless"),
    IANAIfType(282, "fastdsl", "FastDSL"),
    IANAIfType(283, "docsCableScte55d1FwdOob", "Cable SCTE 55-1 OOB Forward Channel"),
    IANAIfType(284, "docsCableScte55d1RetOob", "Cable SCTE 55-1 OOB Return Channel"),
    IANAIfType(285, "docsCableScte55d2DsOob", "Cable SCTE 55-2 OOB Downstream Channel"),
    IANAIfType(286, "docsCableScte55d2UsOob", "Cable SCTE 55-2 OOB Upstream Channel"),
    IANAIfType(287, "docsCableNdf", "Cable Narrowband Digital Forward"),
    IANAIfType(288, "docsCableNdr", "Cable Narrowband Digital Return"),
    IANAIfType(289, "ptm", "Packet Transfer Mode"),
]
