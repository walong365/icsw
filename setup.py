# Copyright (C) 2015-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

""" setup.py for icsw """

from distutils.core import setup

setup(
    name="icsw",
    version="3.0.0",
    description="The init.at Clustersoftware (CORUVS, NOCTUA, NESTOR)",
    license="GPL",
    url="http://www.init.at",
    author="Andreas Lang-Nevyjel",
    author_email="lang-nevyjel@init.at",
    packages=[
        "initat",
        "initat.icsw",
        "initat.icsw.logwatch",
        "initat.icsw.setup",
        "initat.icsw.service",
        "initat.icsw.license",
        "initat.icsw.device",
        "initat.icsw.error",
        "initat.icsw.info",
        "initat.icsw.cstore",
        "initat.icsw.relay",
        "initat.icsw.image",
        "initat.icsw.job",
        "initat.icsw.config",
        "initat.icsw.collectd",
        "initat.icsw.user",
        "initat.tools",
        "initat.tools.mock",
        "initat.tools.bgnotify",
        "initat.tools.bgnotify.tasks",
        "initat.tools.nameserver_tools",
        "initat.tools.prd_tools",
        "initat.tools.mongodb",
        "initat.rms",
        "initat.cluster",
        "initat.cluster.backbone",
        "initat.cluster.backbone.tools",
        "initat.cluster.backbone.0800_models",
        "initat.cluster.backbone.models",
        "initat.cluster.backbone.models.asset",
        "initat.cluster.backbone.exceptions",
        "initat.cluster.backbone.migrations",
        "initat.cluster.backbone.serializers",
        "initat.cluster.backbone.websockets",
        "initat.cluster.backbone.management",
        "initat.cluster.backbone.management.commands",
        "initat.cluster.backbone.management.commands.fixtures",
        "initat.cluster.frontend",
        "initat.cluster.frontend.ext",
        "initat.cluster.frontend.management",
        "initat.cluster.frontend.management.commands",
        "initat.cluster.frontend.rms_addons",
        "initat.cluster.urls",
        "initat.cluster_config_server",
        "initat.cluster_server",
        "initat.cluster_server.capabilities",
        "initat.cluster_server.modules",
        "initat.collectd",
        "initat.collectd.collectd_types",
        "initat.discovery_server",
        "initat.discovery_server.event_log",
        "initat.logcheck_server",
        "initat.logcheck_server.logcheck",
        "initat.logging_server",
        "initat.md_config_server",
        "initat.md_config_server.config",
        "initat.md_config_server.base_config",
        "initat.md_config_server.build",
        "initat.md_config_server.mixins",
        "initat.md_config_server.icinga_log_reader",
        "initat.md_config_server.special_commands",
        "initat.md_config_server.special_commands.instances",
        "initat.md_config_server.kpi",
        "initat.md_sync_server",
        "initat.package_install",
        "initat.package_install.server",
        "initat.package_install.client",
        "initat.rrd_grapher",
        "initat.rrd_grapher.graph",
        "initat.report_server",
        "initat.report_server.config",
        "initat.mother",
        "initat.snmp",
        "initat.snmp.handler",
        "initat.snmp.handler.instances",
        "initat.snmp.process",
        "initat.snmp.sink",
        "initat.snmp_relay",
        "initat.snmp_relay.schemes",
        "initat.snmp_relay.schemes.instances",
        "initat.meta_server",
        "initat.host_monitoring",
        "initat.host_monitoring.modules",
        "initat.host_monitoring.exe",
        "initat.host_monitoring.modules.raidcontrollers"
    ],
    data_files=[
        (
            "/opt/cluster/share/user_extensions.d",
            [
                "opt/cluster/share/user_extensions.d/README",
            ],
        ),
        (
            "/opt/cluster/share/user_extensions.d/logcheck_server.d",
            [
                "opt/cluster/share/user_extensions.d/logcheck_server.d/README",
                "opt/cluster/share/user_extensions.d/logcheck_server.d/example_check.xml",
            ],
        ),
        (
            "/opt/cluster/share/pci",
            [
                "opt/cluster/share/pci/pci.ids",
            ]
        ),
        (
            "/opt/cluster/share/json_defs",
            [
                "opt/cluster/share/json_defs/mon_defs.json",
            ]
        ),
        (
            "/opt/cluster/bin",
            [
                # cbc
                "opt/cluster/bin/compile_libgoto.py",
                "opt/cluster/bin/compile_openmpi.py",
                "opt/cluster/bin/compile_hpl.py",
                "opt/cluster/bin/compile_fftw.py",
                "opt/cluster/bin/compile_scalapack.py",
                "opt/cluster/bin/read_bonnie.py",
                "opt/cluster/bin/bonnie.py",
                "opt/cluster/bin/n_from_mem.py",
                "opt/cluster/bin/read_hpl_result.py",
                "opt/cluster/bin/check_vasp.py",
                # tools
                "opt/cluster/bin/get_cpuid.py",
                "opt/cluster/bin/load_firmware.sh",
                "opt/cluster/bin/populate_ramdisk.py",
                "opt/cluster/bin/change_cluster_var.py",
                # deprecated, use icsw config
                # "opt/cluster/bin/show_config_script.py",
                "opt/cluster/bin/resync_config.sh",
                "opt/cluster/bin/send_mail.py",
                "opt/cluster/bin/send_command_zmq.py",
                # repo tools
                # "opt/cluster/bin/migrate_repos.py",
                # icsw helper
                "opt/cluster/bin/ics_tools.sh",
                # license
                "opt/cluster/bin/license_server_tool.py",
                # set passive checkresult
                "opt/cluster/bin/set_passive_checkresult.py",
                "opt/cluster/bin/sgestat.py",
                "opt/cluster/bin/cluster-server.py",
                "opt/cluster/bin/license_progs.py",
                "opt/cluster/bin/loadsensor.py",
                "opt/cluster/bin/modify_object.py",
            ]
        ),
        (
            "/opt/cluster/sbin/pis",
            [
                "opt/cluster/sbin/pis/sge_post_install.sh",
                "opt/cluster/sbin/pis/modify_service.sh",
                "opt/cluster/sbin/pis/webfrontend_pre_start.sh",
                "opt/cluster/sbin/pis/daphne_pre_start.sh",
                "opt/cluster/sbin/pis/daphne_start_stop.sh",
                "opt/cluster/sbin/pis/hpc_library_post_install.py",
                "opt/cluster/sbin/pis/icsw_client_post_install.sh",
                "opt/cluster/sbin/pis/icsw_server_post_install.sh",
                "opt/cluster/sbin/pis/merge_client_configs.py",
                "opt/cluster/sbin/pis/check_content_stores_server.py",
                "opt/cluster/sbin/pis/check_content_stores_client.py",
                "opt/cluster/sbin/pis/icsw_pis_tools.sh",
            ]
        ),
        (
            "/opt/cluster/lcs",
            [
                "opt/cluster/lcs/stage1",
                "opt/cluster/lcs/stage2",
                "opt/cluster/lcs/stage3",
            ]
        ),
        (
            "/opt/cluster/sbin",
            [
                "opt/cluster/sbin/tls_verify.py",
                "opt/cluster/sbin/openvpn_scan.py",
                "opt/cluster/sbin/collclient.py",
                "opt/cluster/sbin/log_error.py",
                "opt/cluster/sbin/logging-client.py",
                "opt/cluster/sbin/tls_verify.py",
                "opt/cluster/sbin/check_rpm_lists.py",
                "opt/cluster/sbin/make_package.py",
                "opt/cluster/sbin/force_redhat_init_script.sh",
            ]
        ),
        (
            "/opt/cluster/sge",
            [
                "opt/cluster/sge/sge_editor_conf.py",
                "opt/cluster/sge/modify_sge_config.sh",
                "opt/cluster/sge/add_logtail.sh",
                "opt/cluster/sge/sge_request",
                "opt/cluster/sge/sge_qstat",
                "opt/cluster/sge/build_sge6x.sh",
                "opt/cluster/sge/create_sge_links.py",
                "opt/cluster/sge/proepilogue.py",
                "opt/cluster/sge/test_jsv_log_deny.py",
                "opt/cluster/sge/test_jsv_log_accept.py",
                "opt/cluster/sge/qlogin_wrapper.sh",
                "opt/cluster/sge/sge_starter.sh",
                "opt/cluster/sge/batchsys.sh_client",
                # info files
                "opt/cluster/sge/.sge_files",
                "opt/cluster/sge/.party_files",
            ]
        ),
        (
            "/opt/cluster/sge/init.d",
            [
                "opt/cluster/sge/init.d/sgemaster",
                "opt/cluster/sge/init.d/sgeexecd",
            ]
        ),
        (
            "/opt/cluster/share/collectd",
            [
                "opt/cluster/share/collectd/aggregates.xml",
            ]
        ),
        (
            "/opt/cluster/share/collectd/aggregates.d",
            [
            ]
        ),
        (
            "/opt/cluster/share/rrd_grapher",
            [   
                "opt/cluster/share/rrd_grapher/color_rules.xml",
                "opt/cluster/share/rrd_grapher/color_tables.xml",
                "opt/cluster/share/rrd_grapher/compound.xml",
            ]   
        ),  
        (
            "/opt/cluster/share/rrd_grapher/compound.d",
            [
            ]
        ),
        (
            "/opt/cluster/share/rrd_grapher/color_tables.d",
            [
            ]
        ),
        (
            "/opt/cluster/share/rrd_grapher/color_rules.d",
            [
            ]
        ),

    ],
    package_data={
        "initat.cluster.backbone": [
            "fixtures_deprecated/*.xml",
        ],
    }
)
