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
""" base class for host-monitoring modules """

import argparse
import hashlib
import importlib
import inspect
import marshal
import os
import pickle

from .constants import HMAccessClassEnum, DynamicCheckServer
from initat.constants import PLATFORM_SYSTEM_TYPE, PlatformSystemTypeEnum
from initat.tools import logging_tools, process_tools


def net_to_sys(in_val):
    try:
        result = pickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise
    return result


def sys_to_net(in_val):
    return pickle.dumps(in_val)


# some definitions

HM_ALL_MODULES_KEY = "*"

MODULE_STATE_INIT_LIST = [
    ("register_server", True),
    ("init_module", False),
]


class MCPortList(object):
    def __init__(self, *port_specs):
        self.port_specs = port_specs

    def get_port_spec(self):
        if self.port_specs:
            return ", ".join([_ps.get_port_spec() for _ps in self.port_specs])
        else:
            return "none"


class MCPort(object):
    def __init__(self, protocol, start_port, end_port=None):
        self.protocol = protocol
        self.start_port = start_port
        self.end_port = end_port

    def get_port_spec(self):
        if self.end_port:
            return "{}/{:d}-{:d}".format(
                self.protocol.name,
                self.start_port,
                self.end_port,
            )
        else:
            return "{}/{:d}".format(
                self.protocol.name,
                self.start_port,
            )


class MCParameters(object):
    def __init__(self, *args):
        self.parameters = args

    def feed_parser(self, parser):
        for para in self.parameters:
            para.feed_parser(parser)

    def any_args_defined(self):
        return True if len(self.parameters) else False

    def build_icinga_command(self):
        return " ".join(
            [
                _para.build_icinga_command(index) for index, _para in enumerate(self.parameters, 1)
            ]
        )


class MCParameter(object):
    def __init__(self, arg_name, destination, default, description, devvar_name=None, expand=True):
        # for argument parsing (-w, -l, --speed for instance)
        self.arg_name = arg_name
        # destination for comandline parsing
        self.destination = destination
        # device variable name (or None for nothing)
        self.devvar_name = devvar_name
        # default value, can be string, integer or float
        if default is None:
            raise ValueError("None not allowed for default")
        self.default = default
        # description of parameter
        self.description = description
        # add magic icinga command expansion ($ARG$)
        self.expand = expand

    def build_icinga_command(self, index):
        def _to_string(value):
            if isinstance(value, float):
                return "{:.2f}".format(value)
            elif isinstance(value, int):
                return "{:d}".format(value)
            else:
                return value

        def _arg_name_str():
            if isinstance(self.arg_name, str) and len(self.arg_name):
                return self.arg_name
            else:
                return ""

        _r_v = [
            _arg_name_str()
        ]

        if self.devvar_name:
            _r_v.append(
                "${{ARG{:d}:{}:{}}}$".format(
                    index,
                    self.devvar_name,
                    _to_string(self.default),
                )
            )
        elif self.default not in [None, ""]:
            if self.expand:
                _r_v.append(
                    "${{ARG{:d}:{}}}$".format(
                        index,
                        _to_string(self.default),
                    )
                )
            else:
                _r_v.append(
                    _to_string(self.default),
                )
        else:
            _r_v.append(
                "${{ARG{:d}}}".format(index)
            )
        return " ".join(_r_v).strip()

    def feed_parser(self, parser):
        # add argument to parser
        _descr = "{} [%(default)s]".format(
            self.description
        )
        if self.arg_name:
            if isinstance(self.default, bool):
                if self.default:
                    parser.add_argument(
                        self.arg_name,
                        dest=self.destination,
                        default=True,
                        action="store_false",
                        help=_descr,
                    )
                else:
                    parser.add_argument(
                        self.arg_name,
                        dest=self.destination,
                        default=False,
                        action="store_true",
                        help=_descr,
                    )
            else:
                parser.add_argument(
                    self.arg_name,
                    default=self.default,
                    dest=self.destination,
                    type=type(self.default),
                    help=_descr,
                )
        else:
            parser.add_argument(
                self.destination,
                default=self.default,
                nargs="+" if self.arg_name == "" else "*",
                type=type(self.default),
                help=_descr,
            )


class ModuleContainer(object):
    # holds all available modules and commands
    def __init__(self, parent_module_name, root_dir):
        self.__log_com = None
        self.__log_cache = []
        self.__parent_module_name = parent_module_name
        self.__root_dir = root_dir
        self.log(
            "parent module is '{}, root_dir is {}, platform is {}".format(
                self.__parent_module_name,
                self.__root_dir,
                PLATFORM_SYSTEM_TYPE,
            )
        )
        self.read()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        _log_str = "[MC] {}".format(what)
        if self.__log_com:
            self.__log_com(_log_str, level)
        else:
            self.__log_cache.append((_log_str, level))

    def read(self):
        _all_files = [
            cur_entry for cur_entry in [
                entry.split(".")[0] for entry in os.listdir(
                    self.__root_dir
                ) if entry.endswith(".py")
            ] if cur_entry and not cur_entry.startswith("_")
        ]
        self.log(
            "{} found: {}".format(
                logging_tools.get_plural("file", len(_all_files)),
                ", ".join(sorted(_all_files)),
            )
        )
        import_errors = []
        hm_path_dict = {}
        _mod_list = []
        for mod_name in _all_files:
            mod_name_full = "{}.py".format(mod_name)
            mod_path = os.path.join(self.__root_dir, mod_name_full)
            hm_path_dict[mod_name_full] = mod_path

            try:
                new_mod = importlib.import_module(
                    "{}.{}".format(
                        self.__parent_module_name,
                        mod_name
                    )
                )
                if hasattr(new_mod, "ModuleDefinition"):
                    _mod_list.append(new_mod)
                else:
                    self.log(
                        "module {} is missing the 'ModuleDefinition' object".format(
                            mod_name
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
            except:
                exc_info = process_tools.icswExceptionInfo()
                for log_line in exc_info.log_lines:
                    import_errors.append((mod_name, "import", log_line))
        self.HM_PATH_DICT = hm_path_dict
        # list of modules
        self.__pure_module_list = _mod_list
        self.reload_module_checksum()
        self._log_import_errors(import_errors)

        # self.init_modules(import_errors)

    def reload_module_checksum(self):
        sha3_512_digester_all = hashlib.new("sha3_512")

        hm_checksums = {}
        for module_name in sorted(self.HM_PATH_DICT.keys()):
            mod_path = self.HM_PATH_DICT[module_name]
            sha3_512_digester = hashlib.new("sha3_512")
            try:
                with open(mod_path, "rb") as f:
                    data = f.read()
                    sha3_512_digester_all.update(data)
                    sha3_512_digester.update(data)
                    hm_checksums[module_name] = sha3_512_digester.hexdigest()
            except:
                self.log(
                    "error creating checksum for {}: {}".format(
                        mod_path,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
        hm_checksums[HM_ALL_MODULES_KEY] = sha3_512_digester_all.hexdigest()
        self.HM_MODULES_HEX_CHECKSUMS = hm_checksums

    def init_modules(self, import_errors):
        module_list = []
        command_dict = {}
        self.module_list = module_list
        self.command_dict = command_dict

    def _log_import_errors(self, log_list):
        for mod_name, scope, line in log_list:
            self.log("{}@{}: {}".format(scope, mod_name, line), logging_tools.LOG_LEVEL_ERROR)

    def set_log_command(self, log_com):
        self.__log_com = log_com
        for what, level in self.__log_cache:
            self.log(what, level)
        self.__log_cache = []

    def build_structure(self, platform: object=None, access_class: object =None):
        _init_mod_list = []
        used_uuids = set()

        # step 1: filter modules and create module list

        for mod_object in self.__pure_module_list:
            mod_name = mod_object.__name__
            short_name = mod_name.split(".")[-1]
            _mod_def = mod_object.ModuleDefinition
            # salt meta
            MonitoringModule.salt_meta(short_name, _mod_def)
            if MonitoringModule.verify_meta(_mod_def, platform, access_class):
                if _mod_def.Meta.uuid in used_uuids:
                    raise ValueError("UUID used twice")
                used_uuids.add(_mod_def.Meta.uuid)
                new_hm_mod = _mod_def(short_name, mod_object)
                # init state flags for correct handling of shutdown (do not call close_module when
                # init_module was not called)
                new_hm_mod.module_state = {_name: False for _name, _flag in MODULE_STATE_INIT_LIST}
                _init_mod_list.append((mod_object, new_hm_mod, mod_name))
            else:
                self.log(
                    "module {} not added because of {}".format(
                        mod_name,
                        _mod_def.Meta.reject_cause,
                    )
                )
        command_dict = {}
        module_list = []

        # set of primary command names
        pcom_names = set()
        # dict of secondary command names (pointing to primary names)
        scom_dict = {}

        # step 2: iterate over modules and add commands

        for mod_object, new_hm_mod, mod_name in sorted(
            _init_mod_list, reverse=True, key=lambda x: x[1].Meta.priority
        ):
            module_list.append(new_hm_mod)
            loc_coms = [
                entry for entry in dir(mod_object) if entry.endswith("_command") and inspect.isclass(
                    getattr(mod_object, entry)
                ) and issubclass(
                    getattr(mod_object, entry),
                    MonitoringCommand
                )
            ]
            if len(loc_coms):
                coms_added = []
                for loc_com in loc_coms:
                    com_obj = getattr(mod_object, loc_com)
                    if loc_com.endswith("_command"):
                        loc_com = loc_com[:-8]
                    MonitoringCommand.salt_meta(loc_com, com_obj)
                    if MonitoringCommand.verify_meta(com_obj, platform, access_class):
                        if com_obj.Meta.uuid in used_uuids:
                            raise ValueError("UUID {} used twice".format(com_obj.Meta.uuid))
                        if com_obj.Meta.name in pcom_names:
                            raise ValueError("name {} already used".format(com_obj.Meta.name))
                        pcom_names.add(com_obj.Meta.name)
                        used_uuids.add(com_obj.Meta.uuid)
                        try:
                            new_hm_mod.add_command(loc_com, com_obj)
                        except:
                            exc_info = process_tools.icswExceptionInfo()
                            self.log(
                                "error adding command {}@{}: {}".format(
                                    loc_com,
                                    mod_name,
                                    process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_CRITICAL
                            )
                            for log_line in exc_info.log_lines:
                                self.log(
                                    "    {}".format(
                                        log_line
                                    ),
                                    logging_tools.LOG_LEVEL_CRITICAL
                                )
                        else:
                            coms_added.append(loc_com)
                            # add secondary names
                            for other_name in com_obj.Meta.alternate_names:
                                if other_name in pcom_names:
                                    self.log(
                                        "alternate name {} for {} already used in primary names, ignoring".format(
                                            other_name,
                                            loc_com,
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR,
                                    )
                                elif other_name in scom_dict:
                                    self.log(
                                        "alternate name {} for {} already used in secondary dict for {}, ignoring".format(
                                            other_name,
                                            loc_com,
                                            scom_dict[other_name],
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR,
                                    )
                                else:
                                    scom_dict[other_name] = loc_com
                    else:
                        self.log(
                            "command {}@{} not added because of {}".format(
                                loc_com,
                                mod_name,
                                com_obj.Meta.reject_cause,
                            )
                        )
                command_dict.update(new_hm_mod.commands)
                self.log(
                    "{} added for module {}: {}".format(
                        logging_tools.get_plural("command", len(coms_added)),
                        mod_name,
                        ", ".join(coms_added),
                    )
                )
                not_added = set(loc_coms) - set(coms_added)
                if not_added:
                    self.log(
                        "{} not added for module {}: {}".format(
                            logging_tools.get_plural("command", len(not_added)),
                            mod_name,
                            ", ".join(sorted(list(not_added))),
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
            else:
                self.log("no commands found in module {}".format(mod_name), logging_tools.LOG_LEVEL_WARN)
        self.log(
            "{} added, {} added".format(
                logging_tools.get_plural("module", len(module_list)),
                logging_tools.get_plural("command", len(command_dict.keys())),
            )
        )
        self.module_list = module_list
        self.command_dict = command_dict
        self.secondary_names = scom_dict

    def init_commands(self, server_proc: object, verbose: bool) -> bool:
        _init_ok = True
        for call_name, add_server_proc in MODULE_STATE_INIT_LIST:
            for cur_mod in self.module_list:
                if verbose:
                    self.log(
                        "calling {} for module '{}'".format(
                            call_name,
                            cur_mod.name,
                        )
                    )
                try:
                    if add_server_proc:
                        getattr(cur_mod, call_name)(server_proc)
                    else:
                        getattr(cur_mod, call_name)()
                except:
                    exc_info = process_tools.icswExceptionInfo()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False
                    break
                else:
                    cur_mod.module_state[call_name] = True
            if not _init_ok:
                break
        return _init_ok

    def close_modules(self):
        for cur_mod in self.module_list:
            if hasattr(cur_mod, "stop_module"):
                self.log("calling stop_module() for {}".format(cur_mod.name))
                try:
                    cur_mod.stop_module()
                except:
                    exc_info = process_tools.icswExceptionInfo()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
            if cur_mod.module_state["init_module"]:
                cur_mod.close_module()

    # command access commands
    def __contains__(self, key):
        return key in self.command_dict or key in self.secondary_names

    def __getitem__(self, key):
        if key in self.secondary_names:
            # resolve to primary name
            key = self.secondary_names[key]
        return self.command_dict[key]

    def keys(self):
        return self.command_dict.keys()


class MMMCBase(object):
    class Meta:
        name = ""
        priority = 0
        required_access = HMAccessClassEnum.level2
        required_platform = PlatformSystemTypeEnum.NONE
        uuid = ""

    @classmethod
    def salt_meta(cls, name: str, obj: object) -> None:
        obj.Meta.name = name
        for _attr_name in ["name", "priority", "required_access", "required_platform", "uuid"]:
            if not hasattr(obj.Meta, _attr_name):
                # set default value
                setattr(obj.Meta, _attr_name, getattr(MMMCBase.Meta, _attr_name))
        if not isinstance(obj.Meta.required_platform, list):
            obj.Meta.required_platform = [obj.Meta.required_platform]

    @classmethod
    def verify_meta(cls, obj: object, platform: object, access_class: object) -> bool:
        # verifies the Meta class of the given class
        # - for validity
        # - if the required access-class and platform is given
        _reject_cause = []
        if platform is not None or access_class is not None:
            meta_platform = obj.Meta.required_platform
            meta_access = obj.Meta.required_access
            _allowed_classes = [access_class]
            if HMAccessClassEnum.level2 in _allowed_classes:
                _allowed_classes.append(HMAccessClassEnum.level1)
            if HMAccessClassEnum.level1 in _allowed_classes:
                _allowed_classes.append(HMAccessClassEnum.level0)
            if platform not in meta_platform and PlatformSystemTypeEnum.ANY not in meta_platform:
                _reject_cause.append(
                    "Platform {} not in [{}]".format(
                        platform,
                        ", ".join([_pf.name for _pf in meta_platform])
                    )
                )
            if PlatformSystemTypeEnum.NONE in meta_platform:
                _reject_cause.append(
                    "{} in [{}]".format(
                        PlatformSystemTypeEnum.NONE,
                        ", ".join([_pf.name for _pf in meta_platform])
                    )
                )
            if meta_access not in _allowed_classes:
                _reject_cause.append(
                    "{} not in [{}]".format(
                        meta_access,
                        ", ".join([_cl.name for _cl in _allowed_classes]),
                    )
                )
        if not obj.Meta.uuid.strip():
            _reject_cause.append("no UUID")
        obj.Meta.reject_cause = ", ".join(_reject_cause)
        return False if _reject_cause else True


class MonitoringModule(MMMCBase):
    def __init__(self, name, mod_obj):
        self.name = name
        self.obj = mod_obj
        self.enabled = True
        self.__commands = {}
        self.base_init()

    def add_command(self, com_name, call_obj):
        new_co = call_obj(com_name)
        new_co.module = self
        self.__commands[com_name] = new_co

    @property
    def commands(self):
        return self.__commands

    def register_server(self, main_proc):
        self.main_proc = main_proc
        for _com_name, _com in self.__commands.items():
            _com.flush_log_cache()

    def base_init(self):
        # called directly after init (usefull for collclient)
        pass

    def init_module(self):
        pass

    def close_module(self):
        pass

    def reload(self):
        return "N/A"

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.main_proc.log("[{}] {}".format(self.name, what), log_level)

    def __unicode__(self):
        return "module {}, priority {:d}".format(self.name, self.Meta.priority)


class MonitoringCommand(MMMCBase):
    class Meta:
        # Description
        description = "No description available"
        # emits Performancedata
        has_perfdata = False
        # parameters
        parameters = MCParameters()
        # which server to be used
        check_instance = DynamicCheckServer.collrelay
        # create a mon_check_command from this command
        create_mon_check_command = True
        # do not interact with remote device, instead send to localhost
        send_to_localhost = False
        # alternate names
        alternate_names = []
        # cache timeout, for some mixins
        cache_timeout = 0
        # ports for matching
        ports = MCPortList()

    def __init__(self, name, **kwargs):
        super(MonitoringCommand, self).__init__()
        self.__log_cache = []
        # argument parser
        self.parser = argparse.ArgumentParser(
            description="description: {}".format(self.Meta.description) if self.Meta.description else "",
            add_help=False,
            prog="collclient.py --host HOST {}".format(self.Meta.name),
        )

        if self.Meta.parameters.any_args_defined():
            self.Meta.parameters.feed_parser(self.parser)
        else:
            parg_flag = kwargs.get("positional_arguments", False)
            # used to pass commandline arguments to the server
            if parg_flag:
                self.parser.add_argument(
                    "arguments",
                    nargs="+",
                    help=kwargs.get("arguments_name", "additional arguments")
                )
            elif parg_flag is not False:
                raise ValueError("positional_argument flag not in [1, True, False]")
        # monkey patch parsers
        self.parser.exit = self._parser_exit
        self.parser.error = self._parser_error
        self.mc_init()

    @classmethod
    def salt_meta(cls, name: str, obj: object) -> None:
        def _get_attrs(meta):
            return {entry for entry in dir(meta) if not entry.startswith("_")}

        # salt baseclass
        super(MonitoringCommand, cls).salt_meta(name, obj)
        ALLOWED_ATTRS = _get_attrs(MonitoringCommand.Meta)
        # salt monitoringcommand
        for _attr_name in ALLOWED_ATTRS:
            if not hasattr(obj.Meta, _attr_name):
                # set default value
                setattr(obj.Meta, _attr_name, getattr(cls.Meta, _attr_name))
        SUPER_ATTRS = _get_attrs(MMMCBase.Meta)
        cur_attrs = _get_attrs(obj.Meta)
        extra_attrs = cur_attrs - ALLOWED_ATTRS - SUPER_ATTRS
        if extra_attrs:
            raise AttributeError(
                "unrecognized attributes found: {}".format(
                    ", ".join(sorted(list(extra_attrs)))
                )
            )

    def mc_init(self):
        # to be called after the command __init__ was called but before the command is added to the module
        pass

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if hasattr(self, "module"):
            self.module.main_proc.log("[{}] {}".format(self.Meta.name, what), log_level)
        else:
            self.__log_cache.append((what, log_level))

    def flush_log_cache(self):
        if self.__log_cache:
            for _what, _level in self.__log_cache:
                self.log(_what, _level)
                self.__log_cache = []

    def _parser_exit(self, status=0, message=None):
        raise ValueError(status, message)

    def _parser_error(self, message):
        raise ValueError(2, message)

    def handle_commandline(self, arg_list):
        # for arguments use "--" to separate them from the commandline arguments
        res_ns, unknown = self.parser.parse_args(arg_list), []
        if hasattr(res_ns, "arguments"):
            unknown.extend(res_ns.arguments)
        return res_ns, unknown

    def build_icinga_command(self):
        if self.Meta.check_instance == DynamicCheckServer.collrelay:
            _server = "$USER2$"
        elif self.Meta.check_instance == DynamicCheckServer.snmp_relay:
            _server = "$USER3$"
        if self.Meta.send_to_localhost:
            _target = "127.0.0.1"
        else:
            _target = "$HOSTADDRESS$"
        return "{} -m {} {} {}".format(
            _server,
            _target,
            self.Meta.name,
            self.Meta.parameters.build_icinga_command(),
        ).strip()


class MachineVectorEntry(object):
    __slots__ = [
        "name", "default", "info", "unit", "base", "value", "factor", "v_type", "valid_until"
    ]

    def __init__(self, name, **kwargs):
        self.name = name
        # info, description for user
        self.info = kwargs["info"]
        # unit, can be 1, B, ...
        self.unit = kwargs.get("unit", "1")
        # base, 1, 1000 or 1024
        self.base = int(kwargs.get("base", 1))
        # factor to multiply value with to get real value
        self.factor = int(kwargs.get("factor", 1))
        if "v_type" in kwargs:
            self.factor = int(self.factor)
            self.base = int(self.base)
            # value
            self.v_type = kwargs["v_type"]
            if self.v_type == "i":
                self.value = int(kwargs["value"])
            elif self.v_type == "f":
                self.value = float(kwargs["value"])
            else:
                self.value = kwargs["value"]
            self.default = self.value
        else:
            # default value, to get type
            self.default = kwargs["default"]
            # value
            self.value = kwargs.get("value", self.default)
            self.v_type = {
                type(0): "i",
                type(0): "i",
                type(0.0): "f",
            }.get(type(self.default), "s")
        self.valid_until = kwargs.get("valid_until", None)
        if self.valid_until:
            self.valid_until = int(self.valid_until)

    def update_from_mvec(self, in_mv):
        self.value = in_mv.value
        self.valid_until = in_mv.valid_until

    def update(self, value, **kwargs):
        if value is None:
            # unknown
            self.value = value
        elif isinstance(value, type(self.default)):
            self.value = value
        else:
            try:
                if self.v_type == "i":
                    # is integer
                    self.value = int(value)
                elif self.v_type == "f":
                    self.value = float(value)
                else:
                    self.value = value
            except:
                # cast to None
                self.value = None
        if "valid_until" in kwargs:
            self.valid_until = int(kwargs["valid_until"])

    def update_default(self):
        # init value with default value for entries without valid_until settings
        if not self.valid_until:
            self.value = self.default

    def check_timeout(self, cur_time):
        return True if (self.valid_until and cur_time > self.valid_until) else False

    @property
    def num_keys(self):
        return self.name.count(".") + 1

    def get_form_entry(self, idx, max_num_keys):
        act_line = []
        sub_keys = (self.name.split(".") + [""] * max_num_keys)[0:max_num_keys]
        for key_idx, sub_key in zip(range(max_num_keys), sub_keys):
            act_line.append(logging_tools.form_entry("{}{}".format("" if (key_idx == 0 or sub_key == "") else ".", sub_key), header="key{:d}".format(key_idx)))
        # check for unknow
        if self.value is None:
            # unknown value
            act_pf, val_str = ("", "<unknown>")
        else:
            act_pf, val_str = self._get_val_str(self.value * self.factor)
        act_line.extend(
            [
                logging_tools.form_entry_right(val_str, header="value"),
                logging_tools.form_entry_right(act_pf, header=" "),
                logging_tools.form_entry(self.unit, header="unit"),
                logging_tools.form_entry("({:3d})".format(idx), header="idx"),
                logging_tools.form_entry("{:d}".format(self.valid_until) if self.valid_until else "---", header="valid_until"),
                logging_tools.form_entry(self._build_info_string(), header="info")
            ]
        )
        return act_line

    def _get_val_str(self, val):
        act_pf = ""
        pf_list = ["k", "M", "G", "T", "E", "P"]
        _div = False
        if self.base != 1:
            while val > self.base * 4:
                _div = True
                if not pf_list:
                    # infinity
                    act_pf = "I"
                    break
                act_pf = pf_list.pop(0)
                val = float(val) / self.base
        if self.v_type == "f" or _div:
            val_str = "{:>14.3f}".format(val)
        elif self.v_type == "i":
            val_str = "{:>10d}    ".format(int(val))
        else:
            val_str = "{:<14s}".format(str(val))
        return act_pf, val_str

    def _build_info_string(self):
        ret_str = self.info
        ref_p = self.name.split(".")
        for idx in range(len(ref_p)):
            ret_str = ret_str.replace("${:d}".format(idx + 1), ref_p[idx])
        return ret_str

    def build_simple_xml(self, builder):
        return builder("m", n=self.name, v=str(self.value))

    def build_simple_json(self):
        return (self.name, str(self.value))

    def build_xml(self, builder):
        kwargs = {
            "name": self.name,
            "info": self.info,
            "unit": self.unit,
            "v_type": self.v_type,
            "value": str(self.value)
        }
        for key, ns_value in [
            ("valid_until", None),
            ("base", 1),
            ("factor", 1)
        ]:
            if getattr(self, key) != ns_value:
                kwargs[key] = "{:d}".format(int(getattr(self, key)))
        return builder("mve", **kwargs)

    def build_json(self):
        return {
            "name": self.name,
            "info": self.info,
            "unit": self.unit,
            "v_type": self.v_type,
            "value": str(self.value),
            "base": self.base,
            "factor": self.factor,
        }
