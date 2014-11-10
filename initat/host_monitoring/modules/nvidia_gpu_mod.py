# Copyright (C) 2014 Andreas Lang-Nevyjel init.at
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
""" NVidia GPU monitoring """

from initat.host_monitoring import limits, hm_classes
import commands
import logging_tools
import process_tools
from lxml import etree  # @UnusedImport

COM_NAME = "nvidia-smi"
_DEBUG = False

TEST_OUT = """<?xml version="1.0" ?>
<!DOCTYPE nvidia_smi_log SYSTEM "nvsmi_device_v6.dtd">
<nvidia_smi_log>
        <timestamp>Mon Nov 10 11:39:35 2014</timestamp>
        <driver_version>340.24</driver_version>
        <attached_gpus>1</attached_gpus>
        <gpu id="0000:0D:00.0">
                <product_name>Tesla K20m</product_name>
                <product_brand>Tesla</product_brand>
                <display_mode>Disabled</display_mode>
                <display_active>Disabled</display_active>
                <persistence_mode>Disabled</persistence_mode>
                <accounting_mode>Disabled</accounting_mode>
                <accounting_mode_buffer_size>128</accounting_mode_buffer_size>
                <driver_model>
                        <current_dm>N/A</current_dm>
                        <pending_dm>N/A</pending_dm>
                </driver_model>
                <serial>0324713032958</serial>
                <uuid>GPU-215abf8a-9057-fd09-9b71-0efe081ca639</uuid>
                <minor_number>0</minor_number>
                <vbios_version>80.10.39.00.04</vbios_version>
                <multigpu_board>No</multigpu_board>
                <board_id>0xd00</board_id>
                <inforom_version>
                        <img_version>2081.0208.01.09</img_version>
                        <oem_object>1.1</oem_object>
                        <ecc_object>3.0</ecc_object>
                        <pwr_object>N/A</pwr_object>
                </inforom_version>
                <gpu_operation_mode>
                        <current_gom>Compute</current_gom>
                        <pending_gom>Compute</pending_gom>
                </gpu_operation_mode>
                <pci>
                        <pci_bus>0D</pci_bus>
                        <pci_device>00</pci_device>
                        <pci_domain>0000</pci_domain>
                        <pci_device_id>102810DE</pci_device_id>
                        <pci_bus_id>0000:0D:00.0</pci_bus_id>
                        <pci_sub_system_id>101510DE</pci_sub_system_id>
                        <pci_gpu_link_info>
                                <pcie_gen>
                                        <max_link_gen>2</max_link_gen>
                                        <current_link_gen>2</current_link_gen>
                                </pcie_gen>
                                <link_widths>
                                        <max_link_width>16x</max_link_width>
                                        <current_link_width>16x</current_link_width>
                                </link_widths>
                        </pci_gpu_link_info>
                        <pci_bridge_chip>
                                <bridge_chip_type>N/A</bridge_chip_type>
                                <bridge_chip_fw>N/A</bridge_chip_fw>
                        </pci_bridge_chip>
                </pci>
                <fan_speed>N/A</fan_speed>
                <performance_state>P0</performance_state>
                <clocks_throttle_reasons>
                        <clocks_throttle_reason_gpu_idle>Not Active</clocks_throttle_reason_gpu_idle>
                        <clocks_throttle_reason_applications_clocks_setting>Active</clocks_throttle_reason_applications_clocks_setting>
                        <clocks_throttle_reason_sw_power_cap>Not Active</clocks_throttle_reason_sw_power_cap>
                        <clocks_throttle_reason_hw_slowdown>Not Active</clocks_throttle_reason_hw_slowdown>
                        <clocks_throttle_reason_unknown>Not Active</clocks_throttle_reason_unknown>
                </clocks_throttle_reasons>
                <fb_memory_usage>
                        <total>4799 MiB</total>
                        <used>828 MiB</used>
                        <free>3971 MiB</free>
                </fb_memory_usage>
                <bar1_memory_usage>
                        <total>256 MiB</total>
                        <used>18 MiB</used>
                        <free>238 MiB</free>
                </bar1_memory_usage>
                <compute_mode>Default</compute_mode>
                <utilization>
                        <gpu_util>04 %</gpu_util>
                        <memory_util>01 %</memory_util>
                        <encoder_util>0 %</encoder_util>
                        <decoder_util>30 %</decoder_util>
                </utilization>
                <ecc_mode>
                        <current_ecc>Enabled</current_ecc>
                        <pending_ecc>Enabled</pending_ecc>
                </ecc_mode>
                <ecc_errors>
                        <volatile>
                                <single_bit>
                                        <device_memory>0</device_memory>
                                        <register_file>0</register_file>
                                        <l1_cache>0</l1_cache>
                                        <l2_cache>0</l2_cache>
                                        <texture_memory>0</texture_memory>
                                        <total>0</total>
                                </single_bit>
                                <double_bit>
                                        <device_memory>0</device_memory>
                                        <register_file>0</register_file>
                                        <l1_cache>0</l1_cache>
                                        <l2_cache>0</l2_cache>
                                        <texture_memory>0</texture_memory>
                                        <total>0</total>
                                </double_bit>
                        </volatile>
                        <aggregate>
                                <single_bit>
                                        <device_memory>0</device_memory>
                                        <register_file>0</register_file>
                                        <l1_cache>0</l1_cache>
                                        <l2_cache>0</l2_cache>
                                        <texture_memory>0</texture_memory>
                                        <total>0</total>
                                </single_bit>
                                <double_bit>
                                        <device_memory>0</device_memory>
                                        <register_file>0</register_file>
                                        <l1_cache>0</l1_cache>
                                        <l2_cache>0</l2_cache>
                                        <texture_memory>0</texture_memory>
                                        <total>0</total>
                                </double_bit>
                        </aggregate>
                </ecc_errors>
                <retired_pages>
                        <multiple_single_bit_retirement>
                                <retired_count>0</retired_count>
                                <retired_page_addresses>
                                </retired_page_addresses>
                        </multiple_single_bit_retirement>
                        <double_bit_retirement>
                                <retired_count>0</retired_count>
                                <retired_page_addresses>
                                </retired_page_addresses>
                        </double_bit_retirement>
                        <pending_retirement>No</pending_retirement>
                </retired_pages>
                <temperature>
                        <gpu_temp>32 C</gpu_temp>
                        <gpu_temp_max_threshold>95 C</gpu_temp_max_threshold>
                        <gpu_temp_slow_threshold>90 C</gpu_temp_slow_threshold>
                </temperature>
                <power_readings>
                        <power_state>P0</power_state>
                        <power_management>Supported</power_management>
                        <power_draw>48.05 W</power_draw>
                        <power_limit>225.00 W</power_limit>
                        <default_power_limit>225.00 W</default_power_limit>
                        <enforced_power_limit>225.00 W</enforced_power_limit>
                        <min_power_limit>150.00 W</min_power_limit>
                        <max_power_limit>225.00 W</max_power_limit>
                </power_readings>
                <clocks>
                        <graphics_clock>705 MHz</graphics_clock>
                        <sm_clock>705 MHz</sm_clock>
                        <mem_clock>2600 MHz</mem_clock>
                </clocks>
                <applications_clocks>
                        <graphics_clock>705 MHz</graphics_clock>
                        <mem_clock>2600 MHz</mem_clock>
                </applications_clocks>
                <default_applications_clocks>
                        <graphics_clock>705 MHz</graphics_clock>
                        <mem_clock>2600 MHz</mem_clock>
                </default_applications_clocks>
                <max_clocks>
                        <graphics_clock>758 MHz</graphics_clock>
                        <sm_clock>758 MHz</sm_clock>
                        <mem_clock>2600 MHz</mem_clock>
                </max_clocks>
                <clock_policy>
                        <auto_boost>N/A</auto_boost>
                        <auto_boost_default>N/A</auto_boost_default>
                </clock_policy>
                <supported_clocks>
                        <supported_mem_clock>
                                <value>2600 MHz</value>
                                <supported_graphics_clock>758 MHz</supported_graphics_clock>
                                <supported_graphics_clock>705 MHz</supported_graphics_clock>
                                <supported_graphics_clock>666 MHz</supported_graphics_clock>
                                <supported_graphics_clock>640 MHz</supported_graphics_clock>
                                <supported_graphics_clock>614 MHz</supported_graphics_clock>
                        </supported_mem_clock>
                        <supported_mem_clock>
                                <value>324 MHz</value>
                                <supported_graphics_clock>324 MHz</supported_graphics_clock>
                        </supported_mem_clock>
                </supported_clocks>
                <compute_processes>
                        <process_info>
                                <pid>5495</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>5494</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>5493</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>5496</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>6393</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>6392</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>6391</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                        <process_info>
                                <pid>6390</pid>
                                <process_name>/.opt/ansys_inc/v150/ansys/bin/linx64/ansys.e150</process_name>
                                <used_memory>98 MiB</used_memory>
                        </process_info>
                </compute_processes>
                <accounted_processes>
                </accounted_processes>
        </gpu>

</nvidia_smi_log>

"""


UTIL_LIST = ["gpu_util", "memory_util", "encoder_util", "decoder_util"]


class NVidiaGPU(object):
    def __init__(self, module, idx, parts):
        self.__module = module
        self.__idx = idx
        self.name = " ".join(parts[2:4])
        self.uuid = parts[-1][:-1]
        self.log("new GPU with uuid '{}'".format(self.uuid))
        self.__registered_memory_keys = set()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__module.log("[GPU{:d}] {}".format(self.__idx, what), log_level)

    def init_machine_vector(self, mv):
        for _util in UTIL_LIST:
            mv.register_entry("{}.{}".format(self.gpu_key, _util), 0, "percentage of {}".format(_util), "%", 1)
        mv.register_entry(self.processes_key, 0, "number of compute processes", "1", 1)
        mv.register_entry(self.temperature_key, 0, "current temperature", "C", 1)
        mv.register_entry(self.power_key, 0, "current power draw", "W", 1)

    @property
    def processes_key(self):
        return "{}.processes".format(self.gpu_key)

    @property
    def temperature_key(self):
        return "{}.temperature".format(self.gpu_key)

    @property
    def power_key(self):
        return "{}.power".format(self.gpu_key)

    @property
    def gpu_key(self):
        return "gpu.gpu{:d}".format(self.__idx)

    def memory_key(self, name):
        return "mem.gpu.gpu{:d}.{}".format(self.__idx, name)

    def _parse_memory(self, in_str):
        try:
            _num, _sstr = in_str.strip().split()
            _num = int(_num) * {"k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}[_sstr[0].lower()]
        except:
            self.log("error parsing {}: {}".format(in_str, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            _num = 0
        return _num

    def _parse_util(self, in_str):
        if in_str is not None:
            return int(float(in_str.strip().split()[0]))
        else:
            return 0

    def feed_xml(self, tree, mv):
        memory_els = tree.xpath(".//*[contains(name(), '_memory_usage') and used and total and free]")
        for memory_el in memory_els:
            name = memory_el.tag.split("_")[0]
            _pf = self.memory_key(name)
            if name not in self.__registered_memory_keys:
                self.__registered_memory_keys.add(name)
                for _part in ["total", "used", "free"]:
                    _key = "{}.{}".format(_pf, _part)
                    mv.register_entry(_key, 0, "{} Memory {} on {}".format(name, _part, self.name), "Byte", 1024)
            for _part in ["total", "used", "free"]:
                _key = "{}.{}".format(_pf, _part)
                mv[_key] = self._parse_memory(memory_el.findtext(_part))
            for _util in UTIL_LIST:
                mv["{}.{}".format(self.gpu_key, _util)] = self._parse_util(tree.findtext("utilization/{}".format(_util)))
            mv[self.processes_key] = len(tree.xpath(".//compute_processes/process_info"))
            mv[self.temperature_key] = int(tree.findtext(".//temperature/gpu_temp").split()[0])
            mv[self.power_key] = int(float(tree.findtext(".//power_readings/power_draw").split()[0]))


class _general(hm_classes.hm_module):
    def init_module(self):
        self._find_smi_command()

    def _find_smi_command(self):
        self.__smi_command = process_tools.find_file("true" if _DEBUG else COM_NAME)

    def _exec_command(self, com):
        if com.startswith("."):
            if self.__smi_command:
                com = "{} {}".format(self.__smi_command, com[1:])
            else:
                self.log(
                    "no {} command found".format(COM_NAME),
                    logging_tools.LOG_LEVEL_ERROR
                )
                com, out = ("", "")
        if com:
            c_stat, out = commands.getstatusoutput(com)
            if c_stat:
                self.log(
                    "cannot execute {} ({:d}): {}".format(
                        com, c_stat, out or "<NO OUTPUT>"
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                out = ""
        return out

    def init_machine_vector(self, mv):
        if _DEBUG:
            _out = "GPU 0: Tesla K20m (UUID: GPU-215abf8a-9057-fd09-9b71-0efe081ca639)\n"
        else:
            _out = self._exec_command("-L")
        self.__gpus = {}
        for _line in _out.split("\n"):
            self.log("parsing line {}".format(_line))
            try:
                _parts = _line.strip().split()
                _idx = int(_parts[1][:-1])
                new_gpu = NVidiaGPU(self, _idx, _parts)
                self.__gpus[_idx] = new_gpu
            except:
                self.log("error creating GPU: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                new_gpu.init_machine_vector(mv)

    def update_machine_vector(self, mv):
        if self.__smi_command:
            try:
                if _DEBUG:
                    out = TEST_OUT
                else:
                    out = self._exec_command("-q -x")
                _tree = etree.fromstring(out)  # @UndefinedVariable
            except:
                self.log("error parsing {}: {}".format(out, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                for _idx, _gpu in self.__gpus.iteritems():
                    _cur_tree = _tree.xpath(".//gpu[uuid[text()='{}']]".format(_gpu.uuid))
                    if len(_cur_tree):
                        _gpu.feed_xml(_cur_tree[0], mv)
