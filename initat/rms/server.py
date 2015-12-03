# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

""" rms-server, process definitions """

from initat.cluster.backbone import db_tools
from initat.rms.accounting import AccountingProcess
from initat.rms.config import global_config
from initat.rms.license import LicenseProcess
from initat.rms.rmsmon import RMSMonProcess
from initat.tools import cluster_location, configfile, logging_tools, process_tools, \
    threading_tools, server_mixins


@server_mixins.RemoteCallProcess
class ServerProcess(
    server_mixins.ICSWBasePool,
    server_mixins.RemoteCallMixin,
):
    def __init__(self):
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
        )
        self.CC.init("rms-server", global_config)
        self.CC.check_config()
        self.__pid_name = global_config["PID_NAME"]
        self.__msi_block = self._init_msi_block()
        db_tools.close_connection()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        # dc.release()
        self._init_network_sockets()
        # self.add_process(db_verify_process("db_verify"), start=True)
        self.add_process(RMSMonProcess("rms_mon"), start=True)
        self.add_process(AccountingProcess("accounting"), start=True)
        self.add_process(LicenseProcess("license"), start=True)

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid global config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("rms_mon", "full_reload")

    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("rms_server", global_config)

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=5)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rms-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=5, process_name="manager")
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def _init_network_sockets(self):
        self.network_bind(
            server_type="rms",
            need_all_binds=False,
            pollin=self.remote_call,
        )

    @server_mixins.RemoteCall(target_process="rms_mon")
    def get_config(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="rms_mon")
    def job_control(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="rms_mon")
    def queue_control(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="accounting")
    def set_job_variable(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = kwargs["bind_id"]
        srv_com.set_result("0MQ_ID is {}".format(kwargs["bind_id"]))
        return srv_com

    @server_mixins.RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.__msi_block, global_config)

    @server_mixins.RemoteCall(target_process="license")
    def get_license_usage(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="license")
    def license(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="rms_mon", send_async_return=False)
    def file_watch_content(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="accounting", send_async_return=False, target_process_func="job_ss_info")
    def job_start(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="accounting", send_async_return=False, target_process_func="job_ss_info")
    def job_end(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="accounting", send_async_return=False, target_process_func="job_ss_info")
    def pe_start(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="accounting", send_async_return=False, target_process_func="job_ss_info")
    def pe_end(self, srv_com, **kwargs):
        return srv_com

    def loop_post(self):
        self.network_unbind()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        self.CC.close()
