# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cluster-config-server
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
""" cluster-config-server, config control """

from django.db.models import Q
from initat.cluster.backbone.models import device, partition, kernel, image
from initat.cluster_config_server.config import global_config
from initat.cluster_config_server.simple_request import simple_request, var_cache
import config_tools
import crypt
import logging_tools
import module_dependency_tools
import os
import process_tools
import time


class config_control(object):
    """  struct to handle simple config requests """
    def __init__(self, cur_dev):
        self.__log_template = None
        self.device = cur_dev
        self.create_logger()
        config_control.update_router()
        self.__com_dict = {
            "get_kernel": self._handle_get_kernel,
            "get_kernel_name": self._handle_get_kernel_name,
            "get_syslog_server": self._handle_get_syslog_server,
            "get_package_server": self._handle_get_package_server,
            "hello": self._handle_hello,
            "get_init_mods": self._handle_get_init_mods,
            "get_autodetect_mods": self._handle_get_autodetect_mods,
            "locate_module": self._handle_locate_module,
            "get_target_sn": self._handle_get_target_sn,
            "get_partition": self._handle_get_partition,
            "get_image": self._handle_get_image,
            "create_config": self._handle_create_config,
            "ack_config": self._handle_ack_config,
            "get_add_group": self._handle_get_add_group,
            "get_add_user": self._handle_get_add_user,
            "get_del_group": self._handle_get_del_group,
            "get_del_user": self._handle_get_del_user,
            "get_start_scripts": self._handle_get_start_scripts,
            "get_stop_scripts": self._handle_get_stop_scripts,
            "get_root_passwd": self._handle_get_root_passwd,
            "get_additional_packages": self._handle_get_additional_packages,
            "set_kernel": self._handle_set_kernel,
            "modify_bootloader": self._handle_modify_bootloader,
        }

    def refresh(self):
        self.device = device.objects.get(Q(pk=self.device.pk))

    def create_logger(self):
        if self.__log_template is None:
            self.__log_template = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           self.device.full_name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=config_control.srv_process.zmq_context,
                init_logger=True)
            self.log("added client %s (%s)" % (unicode(self.device), self.device.uuid))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def complex_config_request(self, s_req, req_name):
        self.log("routing config_request '%s'" % (req_name))
        q_id = config_control.queue(self, s_req, req_name)
        config_control.srv_process.send_to_process(
            "build",
            "complex_request",
            q_id,
            self.device.name,
            req_name,
            s_req.data
        )

    def complex_config_result(self, s_req, req_name, result):
        ret_str = getattr(s_req, "%s_result" % (req_name))(result)
        if ret_str is not None:
            self.log("handled delayed '%s' (src_ip %s), returning %s" % (
                s_req.node_text,
                s_req.src_ip,
                ret_str))
            config_control.srv_process._send_simple_return(s_req.zmq_id, ret_str)
        else:
            self.log("got result for delayed '%s' (src_ip %s)" % (
                s_req.node_text,
                s_req.src_ip))
        del s_req

    def handle_nodeinfo(self, src_id, node_text):
        s_time = time.time()
        s_req = simple_request(self, src_id, node_text)
        com_call = self.__com_dict.get(s_req.command, None)
        if com_call:
            config_control.update_router()
            try:
                ret_str = com_call(s_req)
            except:
                ret_str = "error interpreting command {}: {}".format(
                    node_text,
                    process_tools.get_except_info(),
                )
        else:
            ret_str = "error unknown command '{}'".format(node_text)
        if ret_str is None:
            self.log("waiting for answer")
        else:
            e_time = time.time()
            self.log("handled nodeinfo '%s' (src_ip %s) in %s, returning %s" % (
                s_req.node_text,
                s_req.src_ip,
                logging_tools.get_diff_time_str(e_time - s_time),
                ret_str))
            config_control.srv_process._send_simple_return(s_req.zmq_id, ret_str)
            del s_req

    # command snippets
    def _handle_get_add_user(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("ADD_USER")))

    def _handle_get_add_group(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("ADD_GROUP")))

    def _handle_get_del_user(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("DEL_USER")))

    def _handle_get_del_group(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("DEL_GROUP")))

    def _handle_get_start_scripts(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("START_SCRIPTS")))

    def _handle_get_stop_scripts(self, s_req):
        return "ok %s" % (" ".join(s_req._get_config_str_vars("STOP_SCRIPTS")))

    def _handle_get_root_passwd(self, s_req):
        var_dict, _var_info = var_cache(config_control.cdg).get_vars(self.device)
        if self.device.root_passwd:
            r_pwd, pwd_src = (self.device.root_passwd.strip(), "device struct")
        elif "ROOT_PASSWORD" in var_dict:
            r_pwd, pwd_src = (crypt.crypt(var_dict["ROOT_PASSWORD"], self.device.name), "var_dict")
        else:
            r_pwd, pwd_src = (crypt.crypt("init4u", self.device.name), "default")
        self.log("got root password from %s" % (pwd_src))
        return "ok %s" % (r_pwd)

    def _handle_get_additional_packages(self, s_req):
        return "ok {}".format(" ".join(s_req._get_config_str_vars("ADDITIONAL_PACKAGES")))

    def _handle_ack_config(self, s_req):
        if self.device.name in config_control.done_config_requests:
            ret_str = config_control.done_config_requests[self.device.name]
            del config_control.done_config_requests[self.device.name]
            return ret_str
        if self.device.name not in config_control.pending_config_requests:
            self.log("strange, got ack but not in done nor pending list", logging_tools.LOG_LEVEL_ERROR)
            self._handle_create_config(s_req)
            return "warn waiting for config"
        else:
            return "warn waiting for config"

    def _handle_create_config(self, s_req):
        if self.device.name in config_control.pending_config_requests:
            return "warn already in pending list"
        elif self.device.name in config_control.done_config_requests:
            return "ok config already built"
        else:
            config_control.pending_config_requests[self.device.name] = True
            q_id = config_control.queue(self, s_req, "build_config")
            config_control.srv_process.create_config(q_id, s_req)
            return "ok started building config"

    def _handle_modify_bootloader(self, s_req):
        return "ok %s" % ("yes" if self.device.act_partition_table.modify_bootloader else "no")

    def _handle_get_image(self, s_req):
        cur_img = self.device.new_image
        if not cur_img:
            return "error no image set"
        else:
            if cur_img.build_lock:
                return "error image is locked"
            else:
                vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "image_server"])
                if vs_struct:
                    if vs_struct.config_name.startswith("mother"):
                        # is mother_server
                        dir_key = "TFTP_DIR"
                    else:
                        # is tftpboot_export
                        dir_key = "EXPORT"
                    vs_struct.fetch_config_vars()
                    if dir_key in vs_struct:
                        # save image versoin info
                        self.device.imageversion = cur_img.full_version
                        self.device.save(update_fields=["imageversion"])
                        return "ok {} {} {} {} {}".format(
                            s_req.server_ip,
                            os.path.join(vs_struct[dir_key], "images", cur_img.name),
                            cur_img.version,
                            cur_img.release,
                            cur_img.builds,
                        )
                    else:
                        return "error key {} not found".format(dir_key)
                else:
                    return "error resolving server"

    def _handle_get_target_sn(self, s_req):
        # get prod_net info
        prod_net = self.device.prod_link
        if not prod_net:
            self.log("no prod_link set", logging_tools.LOG_LEVEL_ERROR)
        vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "mother_server"])
        if vs_struct:
            # routing ok, get export directory
            if vs_struct.config_name.startswith("mother"):
                # is mother_server
                dir_key = "TFTP_DIR"
            else:
                # is tftpboot_export
                dir_key = "EXPORT"
            vs_struct.fetch_config_vars()
            if dir_key in vs_struct:
                _kernel_source_path = "%s/kernels/" % (vs_struct[dir_key])
                return "ok {} {} {:d} {:d} {} {} {}".format(
                    self.device.new_state.status,
                    prod_net.identifier.replace(" ", "_"),
                    self.device.rsync,
                    self.device.rsync_compressed,
                    self.device.name,
                    s_req.server_ip,
                    os.path.join(vs_struct[dir_key], "config")
                )
            else:
                return "error key {} not found".format(dir_key)
        else:
            return "error resolving server"

    def _handle_locate_module(self, s_req):
        dev_kernel = self.device.new_kernel
        if dev_kernel:
            kernel_name = dev_kernel.name
            # build module dict
            # mod_dict = dict([(key, None) for key in [key.endswith(".ko") and key[:-3] or (key.endswith(".o") and key[:-2] or key) for key in s_req.data]])
            kernel_dir = os.path.join(
                global_config["TFTP_DIR"],
                "kernels",
                kernel_name)
            dep_h = module_dependency_tools.dependency_handler(kernel_dir, log_com=self.log)
            dep_h.resolve(s_req.data.split(), firmware=False, resolve_module_dict=True)
            for key, value in dep_h.module_dict.iteritems():
                self.log("kmod mapping: %20s -> %s" % (key, value))
            for value in dep_h.auto_modules:
                self.log("dependencies: %20s    %s" % ("", value))
            # walk the kernel dir
            # mod_list = ["%s.o" % (key) for key in mod_dict.keys()] + ["%s.ko" % (key) for key in mod_dict.keys()]
            return "ok {}".format(" ".join([mod_name[len(global_config["TFTP_DIR"]):] for mod_name in dep_h.module_dict.itervalues()]))
        else:
            return "error no kernel set"

    def _handle_get_init_mods(self, s_req):
        db_mod_list = s_req._get_config_str_vars("INIT_MODS")
        return "ok {}".format(" ".join(db_mod_list))

    def _handle_get_autodetect_mods(self, s_req):
        low_pri_mods = s_req._get_config_str_vars("LOW_PRIORITY_MODS")
        dev_kernel = self.device.new_kernel
        if dev_kernel:
            kernel_name = dev_kernel.name
            # build module dict
            # mod_dict = dict([(key, None) for key in [key.endswith(".ko") and key[:-3] or (key.endswith(".o") and key[:-2] or key) for key in s_req.data]])
            kernel_dir = os.path.join(
                global_config["TFTP_DIR"],
                "kernels",
                kernel_name)
            dep_h = module_dependency_tools.dependency_handler(kernel_dir, log_com=self.log)
            in_parts = s_req.data.split()
            if len(in_parts):
                if in_parts[0] in ["disk", "all", "base"]:
                    _filter = in_parts.pop(0)
                    if _filter == "all":
                        _filter = None
                else:
                    _filter = None
                # generator code from stage2
                # pci_str=""
                # for dev in /sys/bus/pci/devices/* ; do
                #     pci_str="${pci_str}:::$(echo -n $(cat $dev/modalias)::$(cat $dev/class))" ;
                # done
                if _filter == "base":
                    # return list of base modules
                    unique_mods = ["sd_mod", "nfs", "nfsv3", "nfsv4"]
                    if self.device.partition_table:
                        disc_mods = partition.objects.filter(
                            Q(partition_disc__partition_table=self.device.partition_table)
                        ).values_list("partition_fs__kernel_module", flat=True)
                        disc_mods = [_entry for _entry in list(set(sum([cur_part.strip().split() for cur_part in disc_mods], []))) if _entry]
                        self.log(
                            "adding {}: {}".format(
                                logging_tools.get_plural("disc mod", len(disc_mods)),
                                ", ".join(disc_mods),
                            )
                        )
                        unique_mods.extend(disc_mods)
                else:
                    pci_list = [_entry.split("::") for _entry in in_parts if _entry.count("::")]
                    # apply filter
                    if _filter:
                        self.log("filter is '{}'".format(_filter))
                        filter_list = {"disk": ["0x01"]}.get(_filter, [])
                        if filter_list:
                            new_list = []
                            for _entry in pci_list:
                                if not any([_entry[1].startswith(_cur_f) for _cur_f in filter_list]):
                                    self.log("removed {} ({}) due to filter".format(_entry[0], _entry[1]))
                                else:
                                    new_list.append(_entry)
                            pci_list = new_list
                    m_dict = dep_h.find_module_by_modalias([_entry[0] for _entry in pci_list])
                    unique_mods = []
                    for _entry in pci_list:
                        self.log("{} ({}): {}".format(_entry[0], _entry[1], ", ".join(m_dict.get(_entry[0])) or "---"))
                        for _add_mod in m_dict.get(_entry[0], []):
                            if _add_mod not in unique_mods:
                                unique_mods.append(_add_mod)
                # put low-priority mods to the end of the list
                unique_mods = [_mod for _mod in unique_mods if _mod not in low_pri_mods] + [_mod for _mod in unique_mods if _mod in low_pri_mods]
                # unique_mods = sorted(list(set(sum(m_dict.values(), []))))
                self.log("unique mods: {}: {}".format(
                    logging_tools.get_plural("module", len(unique_mods)),
                    ", ".join(unique_mods),
                    )
                )
                return "ok {}".format(" ".join(unique_mods))
            else:
                return "error no data given"
        else:
            return "error no kernel set"

    def _handle_hello(self, s_req):
        return s_req.create_config_dir()

    def _handle_get_partition(self, s_req):
        return s_req.get_partition()

    def _handle_get_syslog_server(self, s_req):
        vs_struct = s_req._get_valid_server_struct(["syslog_server"])
        if vs_struct:
            return "ok {}".format(s_req.server_ip)
        else:
            return "error no syslog-server defined"

    def _handle_get_package_server(self, s_req):
        vs_struct = s_req._get_valid_server_struct(["package_server"])
        if vs_struct:
            return "ok {}".format(s_req.server_ip)
        else:
            return "error no package-server defined"

    def _handle_get_kernel(self, s_req):
        dev_kernel = self.device.new_kernel
        if dev_kernel:
            vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "kernel_server"])
            if not vs_struct:
                return "error no server found"
            else:
                vs_struct.fetch_config_vars()
                if vs_struct.config_name.startswith("mother"):
                    # is mother_server
                    dir_key = "TFTP_DIR"
                else:
                    # is tftpboot_export
                    dir_key = "EXPORT"
                if dir_key in vs_struct:
                    kernel_source_path = os.path.join(vs_struct[dir_key], "kernels")
                    if dev_kernel.full_version != self.device.kernelversion or self.device.act_kernel != self.device.new_kernel:
                        inst = 1
                    else:
                        inst = 0
                    return "ok {:d} {} {}/{} {} {}".format(
                        inst,
                        s_req.server_ip,
                        kernel_source_path,
                        dev_kernel.name,
                        dev_kernel.version,
                        dev_kernel.release,
                    )
                else:
                    return "error key {} not found".format(dir_key)
        else:
            return "error no kernel set"

    def _handle_get_kernel_name(self, s_req):
        dev_kernel = self.device.new_kernel
        if dev_kernel:
            vs_struct = s_req._get_valid_server_struct(["tftpboot_export", "kernel_server"])
            if not vs_struct:
                return "error no server found"
            else:
                # add NEW as dummy string (because get_kernel_name is called from stage1)
                return "ok NEW {} {}".format(
                    s_req.server_ip,
                    dev_kernel.name
                )
        else:
            return "error no kernel set"

    def _handle_set_kernel(self, s_req):
        # maybe we can do something better here
        _com, _k_name, _k_vers = s_req.node_text.split()
        self.device.act_kernel = kernel.objects.get(Q(name=_k_name))
        self.device.kernelversion = _k_vers
        self.device.save(update_fields=["act_kernel", "kernelversion"])
        return "ok set kernel and version"

    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()

    @staticmethod
    def close_clients():
        for cur_c in config_control.__cc_dict.itervalues():
            cur_c.close()

    @staticmethod
    def init(srv_process):
        # cluster device group
        config_control.cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        config_control.srv_process = srv_process
        config_control.cc_log("init config_control")
        config_control.__cc_dict = {}
        config_control.__lut_dict = {}
        config_control.__queue_dict = {}
        config_control.__queue_num = 0
        config_control.pending_config_requests = {}
        config_control.done_config_requests = {}
        config_control.router_last_update = time.time() - 3600
        config_control.router_obj = config_tools.router_object(config_control.cc_log)

    @staticmethod
    def update_router():
        cur_time = time.time()
        if abs(cur_time - config_control.router_last_update) > 5:
            config_control.router_last_update = cur_time
            config_control.router_obj.check_for_update()

    @staticmethod
    def queue(cc_obj, s_req, req_name):
        config_control.__queue_num += 1
        config_control.__queue_dict[config_control.__queue_num] = (cc_obj, s_req, req_name)
        return config_control.__queue_num

    @staticmethod
    def complex_result(queue_id, result):
        cc_obj, s_req, req_name = config_control.__queue_dict[queue_id]
        del config_control.__queue_dict[queue_id]
        cc_obj.complex_config_result(s_req, req_name, result)

    @staticmethod
    def cc_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        config_control.srv_process.log("[cc] %s" % (what), log_level)

    @staticmethod
    def has_client(search_spec):
        return search_spec in config_control.__lut_dict

    @staticmethod
    def get_client(search_spec):
        loc_cc = config_control.__lut_dict.get(search_spec, None)
        loc_cc.refresh()
        return loc_cc

    @staticmethod
    def add_client(new_dev):
        if new_dev.name not in config_control.__cc_dict:
            new_c = config_control(new_dev)
            config_control.__cc_dict[new_dev.name] = new_c
            for key in ["pk", "name", "uuid"]:
                config_control.__lut_dict[getattr(new_dev, key)] = new_c
            config_control.cc_log("added client %s" % (unicode(new_dev)))
        else:
            config_control.__cc_dict[new_dev.name].refresh()
        return config_control.__cc_dict[new_dev.name]
