#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2010,2013-2015,2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone
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
""" shows command help """

from initat.tools import logging_tools
from initat.constants import PlatformSystemTypeEnum, PLATFORM_SYSTEM_TYPE
from initat.host_monitoring.constants import HMAccessClassEnum


def show_hm_help(options):
    from initat.host_monitoring.modules import local_mc

    def dummy_print(what, log_level=logging_tools.LOG_LEVEL_OK):
        print("{} {}".format(logging_tools.map_log_level_to_log_status(log_level), what))

    to_show = []
    local_mc.set_log_command(dummy_print)
    local_mc.build_structure()
    for com_name in sorted(local_mc.keys()):
        _show = True
        if options.args:
            _show = any([com_name.count(arg) for arg in options.args])
        if _show:
            to_show.append(com_name)
    print(
        "Modules defined            : {:d}".format(
            len(local_mc.module_list)
        )
    )
    print(
        "Commands defined / to show : {:d} / {:d}".format(
            len(local_mc.command_dict),
            len(to_show),
        )
    )
    valid_names = sorted(local_mc.command_dict.keys())
    if options.detail:
        _sep_len = 60
        for _idx, com_name in enumerate(to_show, 1):
            com = local_mc.command_dict[com_name]
            print(
                "\n{}\n{}\n{}\n".format(
                    "-" * _sep_len,
                    "command {:3d} of {:3d}: {} (module {})".format(
                        _idx,
                        len(to_show),
                        com_name,
                        com.module.name,
                    ),
                    "-" * _sep_len,
                )
            )
            print(
                "Icinga Command: {}\n".format(
                    com.build_icinga_command(),
                )
            )
            com.parser.print_help()
            print("\n")
    if options.overview:
        # show module overview
        out_list = logging_tools.NewFormList()
        for _idx, mod in enumerate(local_mc.module_list, 1):
            c_names = [name for name in valid_names if local_mc.command_dict[name].module == mod]
            local_valid_names = []
            for com_name in c_names:
                local_valid_names.append(com_name)
            local_valid_names = sorted(local_valid_names)
            out_list.append(
                [
                    logging_tools.form_entry_right(_idx, header="#"),
                    logging_tools.form_entry(mod.name, header="Module name"),
                    logging_tools.form_entry(mod.Meta.uuid, header="uuid"),
                    logging_tools.form_entry_center(mod.Meta.required_access.name, header="Access"),
                    logging_tools.form_entry_center(
                        ",".join(
                            [
                                _platform.name for _platform in mod.Meta.required_platform
                            ]
                        ),
                        header="Platform",
                    ),
                    logging_tools.form_entry_right(mod.Meta.priority, header="priority"),
                    logging_tools.form_entry_right(
                        "yes" if hasattr(mod, "init_machine_vector") else "no",
                        header="MachineVector"
                    ),
                    logging_tools.form_entry_right(len(local_valid_names), header="#coms"),
                    logging_tools.form_entry(", ".join(local_valid_names), header="commands"),
                ]
            )
        print("\nModule overview:\n{}".format(str(out_list)))
        cmd_list = logging_tools.NewFormList()
        for _idx, cmd_name in enumerate(sorted(local_mc.command_dict.keys()), 1):
            cmd = local_mc[cmd_name]
            cmd_list.append(
                [
                    logging_tools.form_entry_right(_idx, header="#"),
                    logging_tools.form_entry(cmd_name, header="Name"),
                    logging_tools.form_entry(cmd.module.name, header="Module name"),
                    logging_tools.form_entry(cmd.Meta.uuid, header="uuid"),
                    logging_tools.form_entry(cmd.Meta.check_instance.name, header="Server"),
                    logging_tools.form_entry_center(cmd.Meta.required_access.name, header="Access"),
                    logging_tools.form_entry_center(
                        ",".join(
                            [
                                _platform.name for _platform in cmd.Meta.required_platform
                                ]
                        ),
                        header="Platform",
                    ),
                    logging_tools.form_entry_center(
                        "yes" if cmd.Meta.has_perfdata else "no",
                        header="perfdata",
                    ),
                    logging_tools.form_entry_center(
                        "yes" if cmd.Meta.create_mon_check_command else "no",
                        header="create MCC",
                    ),
                    logging_tools.form_entry(
                        ", ".join(cmd.Meta.alternate_names) if cmd.Meta.alternate_names else "---",
                        header="Alternate names",
                    ),
                    logging_tools.form_entry(
                        cmd.Meta.description,
                        header="description",
                    ),
                ]
            )
        print("\nCommand overview:\n{}".format(str(cmd_list)))


def show_cs_help(options):
    import initat.cluster_server.modules
    com_names = initat.cluster_server.modules.command_names
    to_show = []
    for com_name in com_names:
        _show = True
        if options.args:
            _show = any([com_name.count(arg) for arg in options.args])
        if _show:
            to_show.append(com_name)
    print(
        "cluster-server commands defined / to show : {:d} / {:d}".format(
            len(com_names),
            len(to_show),
        )
    )
    if to_show:
        out_list = logging_tools.NewFormList()
        for _idx, com_name in enumerate(com_names, 1):
            com = initat.cluster_server.modules.command_dict[com_name]
            out_list.append(
                [
                    logging_tools.form_entry_right(_idx, header="#"),
                    logging_tools.form_entry(com_name, header="Command"),
                    logging_tools.form_entry(
                        "yes" if com.Meta.disabled else "no",
                        header="disabled",
                    ),
                    logging_tools.form_entry(
                        ", ".join([_cfg.name for _cfg in com.Meta.needed_configs]) or "---",
                        header="configs"
                    ),
                    logging_tools.form_entry(
                        ", ".join(com.Meta.needed_option_keys) or "---",
                        header="options"
                    ),
                ]
            )
        print("\n{}".format(str(out_list)))


def main(options):
    print(
        "Showing command info for subsystem '{}'".format(
            options.subsys
        )
    )
    {
        "host-monitoring": show_hm_help,
        "cluster-server": show_cs_help,
    }[options.subsys](options)
