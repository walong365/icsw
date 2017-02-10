#
# Copyright (C) 2001-2006,2014-2017 Andreas Lang-Nevyjel
#
# this file is part of icsw-server-server
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

""" show config script for simple use in CSW """

import base64
import bz2
import datetime
import os
import stat
import sys

from initat.icsw import icsw_logging
from initat.icsw.service import instance
from initat.icsw.service.tools import query_local_meta_server
from initat.tools import logging_tools, process_tools, server_command


def _service_enum_show_command(options):

    from initat.cluster.backbone.server_enums import icswServiceEnum
    from initat.cluster.backbone.models import ConfigServiceEnum, config, config_catalog
    from initat.cluster.backbone import factories
    from django.core.exceptions import ValidationError
    from django.db.models import Q

    _c_dict = {entry.enum_name: entry for entry in ConfigServiceEnum.objects.all()}
    print("")
    print("ServiceEnums defined: {:d}".format(len(icswServiceEnum)))
    _list = logging_tools.NewFormList()
    for entry in icswServiceEnum:
        if entry.name not in _c_dict:
            if options.sync and (entry.value.server_service or entry.value.relayer_service):
                new_entry = ConfigServiceEnum.create_db_entry(entry)
                _c_dict[new_entry.enum_name] = new_entry
            else:
                _db_str = "no"
        if entry.name in _c_dict:
            if options.sync:
                _c_dict[entry.name].update_values(entry)
            _db_str = "yes ({:d})".format(_c_dict[entry.name].pk)
        if entry.value.server_service:
            _egg_action = ", ".join([str(_action) for _action in entry.value.egg_actions]) or "none"
        else:
            _egg_action = "---"
        _list.append(
            [
                logging_tools.form_entry(entry.name, header="EnumName"),
                logging_tools.form_entry(entry.value.name, header="Name"),
                logging_tools.form_entry_center("yes" if entry.value.root_service else "no", header="Root Service"),
                logging_tools.form_entry_center("yes" if entry.value.server_service else "no", header="Server"),
                logging_tools.form_entry_center("yes" if entry.value.relayer_service else "no", header="Relayer"),
                logging_tools.form_entry(entry.value.info, header="Info"),
                logging_tools.form_entry_center(_db_str, header="DB info"),
                logging_tools.form_entry(_egg_action, header="Egg actions"),
            ]
        )
    print(str(_list))
    if options.sync:
        _change_list = []
        # compat dict
        comp_dict = {
            "rrd_grapher": icswServiceEnum.grapher_server.name,
            "rrd_server": icswServiceEnum.collectd_server.name,
            "rrd_collector": icswServiceEnum.collectd_server.name,
            "server": icswServiceEnum.cluster_server.name,
            "ldap_server": icswServiceEnum.ldap_server.name,
        }
        for c_con in config.objects.all():
            if not c_con.config_service_enum_id:
                _check_names = [c_con.name]
                if c_con.name in comp_dict:
                    _check_names.append(comp_dict[c_con.name])
                for _check_name in _check_names:
                    if _check_name in _c_dict:
                        c_con.config_service_enum = _c_dict[_check_name]
                        try:
                            c_con.save(update_fields=["config_service_enum"])
                        except ValidationError:
                            print(
                                "cannot save {}: {}".format(
                                    str(c_con),
                                    process_tools.get_except_info()
                                )
                            )
                        else:
                            _change_list.append(c_con)
                            break
        _create_list = []
        sys_cc = config_catalog.objects.get(Q(system_catalog=True))
        for db_enum in _c_dict.values():
            if not db_enum.config_set.all().count():
                _create_list.append(
                    factories.Config(
                        name=db_enum.name,
                        description=db_enum.info,
                        config_service_enum=db_enum,
                        config_catalog=sys_cc,
                        server_config=True,
                        # system_config=True,
                    )
                )

        if len(_change_list):
            print("")
            print("{} moved to ConfigServiceEnum:".format(logging_tools.get_plural("Config", len(_change_list))))
            for entry in _change_list:
                print("    {} ({})".format(entry.name, str(entry.config_service_enum)))
        if len(_create_list):
            print("")
            print("{} created:".format(logging_tools.get_plural("Config", len(_create_list))))
            for entry in _create_list:
                print("    {} ({})".format(entry.name, str(entry.config_service_enum)))


def _domain_enum_show_command(options):
    from initat.cluster.backbone.domain_enum import icswDomainEnum
    from initat.cluster.backbone.models import DomainTypeEnum
    print("")
    print("DomainEnums defined: {:d}".format(len(icswDomainEnum)))
    _list = logging_tools.NewFormList()
    _c_dict = {entry.enum_name: entry for entry in DomainTypeEnum.objects.all()}
    for entry in icswDomainEnum:
        if entry.name not in _c_dict:
            if options.sync:
                new_entry = DomainTypeEnum.create_db_entry(entry)
                _c_dict[new_entry.enum_name] = new_entry
            else:
                _db_str = "no"
        if entry.name in _c_dict:
            # if options.sync:
            #     _c_dict[entry.name].update_values(entry)
            _db_str = "yes ({:d})".format(_c_dict[entry.name].pk)
        if entry.value.default_enum:
            _default_info = entry.value.default_enum.name
        else:
            _default_info = "---"
        if entry.value.domain_enum:
            _domain_info = entry.value.domain_enum.name
        else:
            _domain_info = "---"
        _list.append(
            [
                logging_tools.form_entry(entry.name, header="EnumName"),
                logging_tools.form_entry(entry.value.name, header="Name"),
                logging_tools.form_entry(entry.value.info, header="Info"),
                logging_tools.form_entry_center(_db_str, header="DB info"),
                logging_tools.form_entry(_default_info, header="Default Enum"),
                logging_tools.form_entry(_domain_info, header="Domain Enum"),
            ]
        )
    print(str(_list))


def enum_show_command(options):
    _service_enum_show_command(options)
    _domain_enum_show_command(options)


def show_command(options):
    for f_name in options.files:
        _obj_name = f_name if not options.short_path else os.path.basename(f_name)
        for _rc in ["/", ".", "-"]:
            _obj_name = _obj_name.replace(_rc, "_")
        while _obj_name.startswith("_"):
            _obj_name = _obj_name[1:]
        obj_name = "{}_object".format(_obj_name)
        try:
            f_stat = os.stat(f_name)
            content = open(f_name).read()
        except:
            print(
                "error reading file '{}': {}".format(
                    f_name,
                    process_tools.get_except_info()
                )
            )
        else:
            if not options.binary:
                f_lines = content.split("\n")
                _f_info = logging_tools.get_plural("line", f_lines)
            else:
                _f_info = "binary"
            out_lines = [
                "",
                "# from {} ({}, host {}, size was {}, {})".format(
                    f_name,
                    datetime.datetime.now(),
                    process_tools.get_machine_name(short=False),
                    logging_tools.get_size_str(f_stat[stat.ST_SIZE]),
                    _f_info,
                ),
                "",
                "{} = config.add_file_object('{}')".format(obj_name, f_name),
            ]
            if options.binary:
                out_lines.extend(
                    [
                        "import bz2",
                        "import base64",
                        "",
                        "{} += bz2.decompress(base.b64decode('{}'))".format(
                            obj_name,
                            base64.b64encode(bz2.compress(content)),
                        )
                    ]
                )
            else:
                if options.full_strip:
                    f_lines = [_line.strip() for _line in f_lines if _line.strip()]
                if options.remove_hashes:
                    f_lines = [_line for _line in f_lines if (not _line.startswith("#") or _line.startswith("#!"))]
                p_line = " " * 4
                try:
                    out_lines.append(
                        "{} += [\n{}]\n".format(
                            obj_name,
                            "".join(
                                [
                                    "{}'{}',\n".format(p_line, _line.replace("'", '"').replace("\\", "\\\\")) for _line in f_lines
                                ]
                            )
                        )
                    )
                except UnicodeDecodeError:
                    print()
                    print("'{}' seems to be a binary file, please use -b switch".format(f_name))
                    print()
                    sys.exit(3)
            out_lines.append(
                "{}.mode = 0o{:o}".format(
                    obj_name,
                    stat.S_IMODE(f_stat[stat.ST_MODE])
                )
            )
            print("\n".join(out_lines))


def role_command(options):
    from initat.icsw.config.create_role_fixtures import create_noctua_fixtures
    basic_services = [
        'logging-server',
        'meta-server'
    ]
    log_com = icsw_logging.get_logger("config", options)
    inst_xml = instance.InstanceXML(log_com)
    if options.role == "noctua":
        create_noctua_fixtures()
        services = basic_services + [
            "md-sync-server",
            "md-config-server",
            "icinga-init",
            "nginx",
            "uwsgi-init",
        ]
    print("starting necessary services...")
    _result = query_local_meta_server(
        inst_xml,
        "enable",
        services=services
    )


def upload_command(options):
    if not os.path.exists(options.filename):
        print("File '{}' does not exist".format(options.filename))
        sys.exit(-4)
    _content = open(options.filename, "rb").read()
    _size = len(_content)
    if options.mode == "cjson":
        _structure = server_command.decompress(_content, json=True)
    else:
        print("Unknown filemode '{}'".format(options.mode))
        sys.exit(-5)
    from initat.cluster.backbone.models.internal import BackendConfigFileTypeEnum, \
        BackendConfigFile
    from initat.tools import cluster_location
    _new = BackendConfigFile.store(
        structure=_structure,
        file_size=_size,
        file_type=BackendConfigFileTypeEnum(options.type),
        install_device=cluster_location.DeviceRecognition().device,
    )
    print("Current instance: {}".format(str(_new), _new.idx))


def main(opt_ns):
    if opt_ns.childcom == "show":
        show_command(opt_ns)
    elif opt_ns.childcom == "enum_show":
        enum_show_command(opt_ns)
    elif opt_ns.childcom == "role":
        role_command(opt_ns)
    elif opt_ns.childcom == "upload":
        upload_command(opt_ns)
    else:
        raise KeyError("Unknown mode '{}'".format(opt_ns.childcom))
