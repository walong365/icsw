# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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
DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

angular.module(
    "icsw.device.boot",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).controller("icswDeviceBootCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "access_level_service", "$timeout", "msgbus", "icswTools", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service, $timeout, msgbus, icswTools, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
        access_level_service.install($scope)
        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.new_devsel(args[1])
        )
        $scope.mbl_entries = []
        $scope.num_selected = 0
        $scope.bootserver_list = []
        $scope.any_type_1_selected = false
        $scope.any_type_2_selected = false
        $scope.any_type_3_selected = false
        $scope.device_sel_filter = ""
        $scope.boot_options = [
            # 1 ... option to modify globally
            # 2 ... local option
            # 3 ... appends a new line
            ["t", "target state", 1],
            ["k", "kernel"      , 1],
            ["i", "image"       , 1],
            ["p", "partition"   , 1],
            ["b", "bootdevice"  , 1],
            ["s", "soft control", 2],
            ["h", "hard control", 2],
            ["l", "devicelog"   , 3],
        ]
        $scope.stage1_flavours = [
            {"val" : "cpio", "name" : "CPIO"},
            {"val" : "cramfs", "name" : "CramFS"},
            {"val" : "lo", "name" : "ext2 via Loopback"},
        ]
        $scope.get_global_bootserver_info = () ->
            if $scope.bootserver_list.length
                if $scope.bootserver_list.length == 1
                    return " on bootserver " + $scope.mother_servers[$scope.bootserver_list[0]].full_name
                else
                    return ", " + $scope.bootserver_list.length + " bootservers"
            else
                return ""
        $scope.get_devlog_class = (dev) ->
            if dev.show_log
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.get_devlog_value = (dev) ->
            return if dev.show_log then "hide" else "show"
        $scope.change_devlog_flag = (dev) ->
            dev.show_log = !dev.show_log
        $scope.change_sel_filter = () ->
            if $scope.cur_sel_timeout
                $timeout.cancel($scope.cur_sel_timeout)
            $scope.cur_sel_timeout = $timeout($scope.set_sel_filter, 500)
        $scope.set_sel_filter = () ->
            try
                cur_re = new RegExp($scope.device_sel_filter, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            $scope.num_selected = 0
            for dev in $scope.devices
                dev.selected = if dev.name.match(cur_re) then true else false
                if dev.selected
                    $scope.num_selected++
        $scope.bo_enabled = {}
        $scope.type_1_options = () ->
            return (entry for entry in $scope.boot_options when entry[2] == 1)
        for entry in $scope.boot_options
            $scope.bo_enabled[entry[0]] = false
        $scope.get_bo_class = (short) ->
            return (if $scope.bo_enabled[short] then "btn btn-sm btn-success" else "btn btn-sm")
        $scope.toggle_bo = (short) ->
            $scope.bo_enabled[short] = ! $scope.bo_enabled[short]
            $scope.any_type_1_selected = if (entry for entry in $scope.boot_options when entry[2] == 1 and $scope.bo_enabled[entry[0]] == true).length then true else false
            $scope.any_type_2_selected = if (entry for entry in $scope.boot_options when entry[2] == 2 and $scope.bo_enabled[entry[0]] == true).length then true else false
            $scope.any_type_3_selected = if (entry for entry in $scope.boot_options when entry[2] == 3 and $scope.bo_enabled[entry[0]] == true).length then true else false
        $scope.get_dev_sel_class = (dev) ->
            if dev.selected
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.get_device_name_class = (dev) ->
            if dev.bootserver of $scope.mother_servers
                return ""
            else
                return "warning"
        $scope.get_bootserver_info = (dev) ->
            if dev.bootserver
                if $scope.bootserver_list.length > 1
                    if dev.bootserver of $scope.mother_servers
                        return " (" + $scope.mother_servers[dev.bootserver].full_name + ")"
                    else
                        return " (N/A)"
                else
                    return ""
            else
                return " (no BS)"
        $scope.get_row_class = (dev) ->
            if dev.bootserver
                return ""
            else
                return "danger"
        $scope.num_selected_hc = () ->
            num_hc = 0
            for dev in $scope.devices
                if dev.selected and dev.slave_connections and dev.slave_connections.length
                    num_hc += dev.slave_connections.length
            return num_hc
        $scope.toggle_gdev_sel = (sel_mode) ->
            ($scope.toggle_dev_sel(dev, sel_mode) for dev in $scope.devices)
        $scope.toggle_dev_sel = (dev, sel_mode) ->
            if sel_mode == 1
                dev.selected = true
            else if sel_mode == -1
                dev.selected = false
            else if sel_mode == 0
                dev.selected = !dev.selected
            $scope.num_selected = (dev for dev in $scope.devices when dev.selected).length
        # mixins
        $scope.device_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.device_edit.modify_rest_url = ICSW_URLS.BOOT_UPDATE_DEVICE.slice(1).slice(0, -2)
        $scope.device_edit.use_promise = true
        $scope.device_edit.modify_data_before_put = (data) ->
            # rewrite new_state / prod_link
            if data.target_state
                new_state = $scope.state_lut[data.target_state]
                data.new_state = new_state.status
                data.prod_link = new_state.network
            else
                data.new_state = null
                data.prod_link = null
            if $scope._edit_obj and $scope._edit_obj.bootnetdevice
                $scope._edit_obj.bootnetdevice.driver = $scope._edit_obj.driver
                $scope._edit_obj.bootnetdevice.macaddr = $scope._edit_obj.macaddr
        $scope.devsel_list = []
        # dict if controlling devices are reachable
        $scope.cd_reachable = {}
        $scope.devices = []
        # macbootlog timeout
        $scope.mbl_timeout = undefined
        # at least one boot_info received
        $scope.info_ok = false
        # number of unsuccessfull connections
        $scope.conn_problems = 0
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            if $scope.update_info_timeout
                $timeout.cancel($scope.update_info_timeout)
            $scope.info_ok = false
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_network" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_boot"}]),
                # 1
                restDataSource.reload([ICSW_URLS.REST_KERNEL_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_IMAGE_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_PARTITION_TABLE_LIST, {}])
                # 4
                restDataSource.reload([ICSW_URLS.REST_STATUS_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_NETWORK_LIST, {}])
                # 6
                restDataSource.reload([ICSW_URLS.REST_LOG_SOURCE_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_LOG_LEVEL_LIST, {}])
                # 8
                restDataSource.reload([ICSW_URLS.REST_USER_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"all_mother_servers" : true}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = (dev for dev in data[0])
                $scope.num_selected = 0
                for dev in $scope.devices
                    dev.show_log = false
                    dev.selected = false
                    dev.recvreq_str = "waiting"
                    dev.recvreq_state = "warning"
                    dev.network = "waiting"
                    dev.network_state = "warning"
                    dev.latest_log = 0
                    dev.num_logs = 0
                    dev.log_lines = []
                $scope.log_source_lut = icswTools.build_lut(data[6])
                $scope.log_level_lut = icswTools.build_lut(data[7])
                $scope.user_lut = icswTools.build_lut(data[8])
                $scope.device_lut = icswTools.build_lut($scope.devices)
                $scope.kernels = data[1]
                $scope.images = data[2]
                # only use entries valid for nodeboot
                $scope.partitions = (entry for entry in data[3] when entry.nodeboot and entry.valid and entry.enabled)
                $scope.kernel_lut = icswTools.build_lut($scope.kernels)
                $scope.image_lut = icswTools.build_lut($scope.images)
                $scope.partition_lut = icswTools.build_lut($scope.partitions)
                $scope.mother_servers = icswTools.build_lut(data[9])
                if $scope.update_info_timeout
                    $timeout.cancel($scope.update_info_timeout)
                prod_nets = (entry for entry in data[5] when entry.network_type_identifier == "p")
                # check for number of bootservers
                $scope.bootserver_list = _.uniq(entry.bootserver for entry in $scope.devices when entry.bootserver)
                network_states = []
                special_states = []
                # state lookup table
                state_lut = []
                idx = 0
                for entry in data[4]
                    if not entry.prod_link
                        idx++
                        new_state = {
                            "idx"       : idx
                            "status"    : entry.idx
                            "network"   : 0
                            "info"      : entry.info_string
                            "full_info" : entry.info_string
                        } 
                        special_states.push(new_state)
                        state_lut[idx] = new_state
                for prod_net in prod_nets
                    net_list = {
                       "info"    : "#{prod_net.info_string}"
                       "network" : prod_net.idx
                       "states"  : []
                    }
                    network_states.push(net_list)
                    for clean_flag in [false, true]
                        for entry in (_entry for _entry in data[4] when _entry.prod_link and _entry.is_clean == clean_flag)
                            idx++
                            new_state = {
                                "idx"       : idx
                                "status"    : entry.idx
                                "network"   : prod_net.idx
                                "info"      : "#{entry.info_string}"
                                "full_info" : "#{entry.info_string} into #{prod_net.info_string}"
                            }
                            net_list.states.push(new_state)
                            state_lut[idx] = new_state
                $scope.network_states = network_states
                $scope.special_states = special_states
                $scope.state_lut = state_lut
                $scope.update_info_timeout = $timeout($scope.update_info, 500)
            )
            $scope.update_info = () ->
                if $scope.modal_active
                    # do not update while a modal is active
                    $scope.update_info_timeout = $timeout($scope.update_info, 10000)
                    return
                wait_list = [
                    restDataSource.reload([ICSW_URLS.REST_KERNEL_LIST, {}]),
                    restDataSource.reload([ICSW_URLS.REST_IMAGE_LIST, {}])
                    restDataSource.reload([ICSW_URLS.REST_PARTITION_TABLE_LIST, {}])
                ]
                $q.all(wait_list).then((data) ->
                    $scope.kernels = data[0]
                    $scope.images = data[1]
                    $scope.kernel_lut = icswTools.build_lut($scope.kernels)
                    $scope.image_lut = icswTools.build_lut($scope.images)
                    send_data = {
                        "sel_list" : $scope.devsel_list
                        "call_mother" : 1
                    }
                    icswCallAjaxService
                        url     : ICSW_URLS.BOOT_GET_BOOT_INFO_JSON
                        data    : send_data
                        success : (xml) =>
                            $scope.update_info_timeout = $timeout($scope.update_info, 10000)
                            if icswParseXMLResponseService(xml, 40, false)
                                $scope.conn_problems = 0
                                $scope.info_ok = true
                                _resp = angular.fromJson($(xml).find("value[name='response']").text())
                                for entry in _resp
                                    dev = $scope.device_lut[entry.idx]
                                    # copied from bootcontrol, seems strange to me now ...
                                    valid_str = "#{entry.valid_state}state"
                                    if entry[valid_str]
                                         dev.recvreq_str = entry[valid_str] +  "(" + entry.valid_state + ")"
                                    else
                                         dev.recvreq_str = "rcv: ---"
                                    net_state = entry.net_state
                                    tr_class = {"down" : "danger", "unknown" : "danger", "ping" : "warning", "up" : "success"}[net_state]
                                    dev.network = "#{entry.network} (#{net_state})"
                                    dev.net_state = net_state
                                    dev.recvreq_state = tr_class
                                    dev.network_state = tr_class
                                    # target state
                                    for _kv in ["new_state", "prod_link"]
                                        dev[_kv] = entry[_kv]
                                    dev.target_state = 0
                                    # rewrite device new_state / prod_link
                                    if dev.new_state
                                        if dev.prod_link
                                            _list = (_entry for _entry in $scope.network_states when _entry.network == dev.prod_link)
                                            if _list.length
                                                _list = (_entry for _entry in _list[0]["states"] when _entry.status == dev.new_state)
                                        else
                                            _list = (_entry for _entry in $scope.special_states when _entry.status == dev.new_state)
                                        # _list can be empty when networks change theirs types
                                        if _list.length
                                            dev.target_state = _list[0].idx
                                    # copy image, act_image is a tuple (idx, vers, release) or none
                                    for _kv in ["new_image", "act_image"]
                                        dev[_kv] = entry[_kv]
                                    # copy kernel, act_kernel is a tuple (idx, vers, release) or none
                                    for _kv in ["new_kernel", "act_kernel", "stage1_flavour", "kernel_append"]
                                        dev[_kv] = entry[_kv]
                                    # copy partition
                                    for _kv in ["act_partition_table", "partition_table"]
                                        dev[_kv] = entry[_kv]
                                    # copy bootdevice
                                    for _kv in ["dhcp_mac", "dhcp_write", "dhcp_written", "dhcp_error", "bootnetdevice"]
                                        dev[_kv] = entry[_kv]
                                    # master connections
                                    for _kv in ["master_connections", "slave_connections"]
                                        dev[_kv] = entry[_kv]
                                cd_result = $(xml).find("value[name='cd_response']")
                                if cd_result.length
                                    $scope.cd_reachable = angular.fromJson(cd_result.text())
                                else
                                    $scope.cd_reachable = {}
                                $scope.$digest()
                            else
                                $scope.$apply(
                                    $scope.conn_problems++
                                )
                                #console.log $scope.conn_problems, xml
                )
                if $scope.bo_enabled["l"]
                    send_data = {
                        "sel_list" : angular.toJson(([dev.idx, dev.latest_log] for dev in $scope.devices))
                    }
                    icswCallAjaxService
                        url      : ICSW_URLS.BOOT_GET_DEVLOG_INFO
                        data     : send_data
                        dataType : "json"
                        success  : (json) =>
                            if json.devlog_lines
                                for entry in json.devlog_lines
                                    # format: pk, device_id, log_source_id, user_id, log_level_id, text, seconds
                                    cur_dev = $scope.device_lut[entry[1]]
                                    cur_dev.num_logs++
                                    cur_dev.latest_log = Math.max(entry[0], cur_dev.latest_log)
                                    cur_dev.log_lines.splice(0, 0, entry)
                                    cur_dev.log_lines = cur_dev.log_lines
                                $scope.$digest()
        $scope.soft_control = (dev, command) ->
            if dev
                dev_pk_list = [dev.idx]
            else
                dev_pk_list = (dev.idx for dev in $scope.devices when dev.selected)
            icswCallAjaxService
                url     : ICSW_URLS.BOOT_SOFT_CONTROL
                data    : {
                    "dev_pk_list" : angular.toJson(dev_pk_list)
                    "command"     : command
                }
                success : (xml) =>
                    icswParseXMLResponseService(xml)
        $scope.hard_control = (cd_con, command) ->
            if cd_con
                cd_pk_list = [cd_con.idx]
            else
                cd_pk_list = []
                for dev in $scope.devices
                    if dev.selected and dev.slave_connections.length
                        for slave_con in dev.slave_connections
                            cd_pk_list.push(slave_con.idx)
            icswCallAjaxService
                url     : ICSW_URLS.BOOT_HARD_CONTROL
                data    : {
                    "cd_pk_list" : angular.toJson(cd_pk_list)
                    "command"    : command
                }
                success : (xml) =>
                    icswParseXMLResponseService(xml)
        $scope.modify_device = (dev, event) ->
            $scope.device_info_str = dev.full_name
            $scope.device_edit.edit_template = "boot.single.form"
            dev.bo_enabled = $scope.bo_enabled
            if dev.bootnetdevice
                dev.macaddr = dev.bootnetdevice.macaddr
                dev.driver = dev.bootnetdevice.driver
            $scope.device_edit.edit(dev, event).then(
                (mod_dev) ->
                    true
                () ->
                    true
            )
        $scope.modify_many = (event) ->
            $scope.device_info_str = "#{$scope.num_selected} devices"
            $scope.device_edit.edit_template = "boot.many.form"
            sel_devices = (dev for dev in $scope.devices when dev.selected)
            dev = {
                "idx" : 0
                "bo_enabled" : $scope.bo_enabled
                # not really needed because bootnetdevice is not set
                "macaddr" : ""
                "target_state" : (dev.target_state for dev in sel_devices)[0]
                "driver" : (dev.bootnetdevice.driver for dev in sel_devices when dev.bootnetdevice).concat((""))[0]
                "partition_table" : (dev.partition_table for dev in sel_devices)[0]
                "new_image" : (dev.new_image for dev in sel_devices)[0]
                "new_kernel" : (dev.new_kernel for dev in sel_devices)[0]
                "stage1_flavour" : (dev.stage1_flavour for dev in sel_devices).concat(("cpio"))[0]
                "kernel_append" : (dev.kernel_append for dev in sel_devices).concat((""))[0]
                "dhcp_mac" : (dev.dhcp_mac for dev in sel_devices).concat((""))[0]
                "dhcp_write" : (dev.dhcp_write for dev in sel_devices).concat((""))[0]
                "device_pks" : (dev.idx for dev in sel_devices)
            }
            $scope.device_edit.edit(dev, event).then(
                (mod_dev) ->
                    # force update to get data from server
                    if $scope.update_info_timeout
                        $timeout.cancel($scope.update_info_timeout)
                    $scope.update_info_timeout = $timeout($scope.update_info, 50)
                () ->
                    true
            )
        $scope.get_hc_class = (cd_con) ->
            if cd_con.parent.idx of $scope.cd_reachable
                if $scope.cd_reachable[cd_con.parent.idx]
                    return "btn btn-success btn-xs dropdown-toggle"
                else
                    return "btn btn-danger btn-xs dropdown-toggle"
            else          
                return "btn btn-xs dropdown-toggle"
        $scope.get_hc_disabled = (cd_con) ->
            if cd_con.parent.idx of $scope.cd_reachable
                if $scope.cd_reachable[cd_con.parent.idx]
                    return false
                else
                    return true
            else
                return false
        $scope.get_hc_info = (cd_con) ->
            r_str = cd_con.parent.full_name
            info_f = (cd_con["parameter_i#{i}"] for i in [1, 2, 3, 4])
            info_f.reverse()
            for i in [1..4]
                if info_f.length and info_f[0] == 0
                    info_f.splice(0, 1)
            info_f.reverse()
            if info_f.length
                info_str = info_f.join("/")
                return "#{r_str} (#{info_str})"
            else
                return r_str
        $scope.toggle_show_mbl = () ->
            if $scope.mbl_timeout
                $timeout.cancel($scope.mbl_timeout)
                $scope.mbl_timeout = undefined
            $scope.show_mbl = !$scope.show_mbl
            if $scope.show_mbl
                $scope.fetch_macbootlog_entries()
        $scope.fetch_macbootlog_entries = () ->
            Restangular.all(ICSW_URLS.REST_MACBOOTLOG_LIST.slice(1)).getList({"_num_entries" : 50, "_order_by" : "-pk"}).then(
                (data) ->
                    $scope.mbl_entries = data
                    $scope.mbl_timeout = $timeout($scope.fetch_macbootlog_entries, 5000)
            )
        $scope.get_mbl_created = (mbl) ->
            return moment.unix(mbl.created).format(DT_FORM)
]).directive("icswDeviceBootTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.boot.table")
    }
]).directive("icswDeviceBootRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.boot.row")
        link : (scope, el, attrs) ->
            _resolve_lut_name = (entry, lut) ->
                if entry of lut
                    return lut[entry].name
                else
                    return null
            _get_latest_entry = (hist_tuple, lut, key) ->
                if hist_tuple?
                    _idx = hist_tuple[0]
                    if _idx of lut
                        if key?
                            return lut[_idx][key]
                        else
                            return lut[_idx]
                    else
                        return null
                else
                    return null
            _resolve_version = (lut, idx) ->
                if idx of lut
                    _obj = lut[idx]
                    return "#{_obj.version}.#{_obj.release}"
                else
                    return null
            scope.get_td_class = (entry) ->
                dev = scope.dev
                _cls = ""
                if scope.info_ok
                    if entry[0] == "i"
                        _cls = scope._get_td_class(_get_latest_entry(dev.act_image, scope.image_lut, "name"), _resolve_lut_name(dev.new_image, scope.image_lut))
                    else if entry[0] == "p"
                        _cls = scope._get_td_class(dev.act_partition_table, dev.partition_table)
                    else if entry[0] == "k"
                        _cls = scope._get_td_class(_get_latest_entry(dev.act_kernel, scope.kernel_lut, "name"), _resolve_lut_name(dev.new_kernel, scope.kernel_lut))
                return _cls
            scope._get_td_class = (act_val, new_val) ->
                if act_val == new_val
                    return ""
                else
                    return "warning"
            scope.valid_net_state = () ->
                return scope.dev.net_state == "up"
            scope.show_boot_option = (entry) ->
                dev = scope.dev
                if scope.info_ok
                    if entry[0] == "t"
                        # target state
                        if dev.target_state
                            return scope.state_lut[dev.target_state].full_info
                        else
                            return "---"
                        #console.log dev.new_state, dev.prod_link
                    else if entry[0] == "i"
                        # image
                        act_image = if dev.act_image then dev.act_image[0] else null
                        if act_image
                            act_image_version = "#{dev.act_image[1]}.#{dev.act_image[2]}"
                        else
                            act_image_version = ""
                        img_str = scope.get_info_str("i", act_image, act_image_version, dev.new_image, _resolve_version(scope.image_lut, dev.new_image), scope.image_lut)
                        return img_str
                    else if entry[0] == "k"
                        # kernel
                        act_kernel = if dev.act_kernel then dev.act_kernel[0] else null
                        if act_kernel
                            act_kernel_version = "#{dev.act_kernel[1]}.#{dev.act_kernel[2]}"
                        else
                            act_kernel_version = ""
                        _k_str = scope.get_info_str("k", act_kernel, act_kernel_version, dev.new_kernel, _resolve_version(scope.kernel_lut, dev.new_kernel), scope.kernel_lut)
                        if dev.act_kernel or dev.new_kernel
                            _k_str = "#{_k_str}, flavour is #{dev.stage1_flavour}"
                            if dev.kernel_append
                                _k_str = "#{_k_str} (append '#{dev.kernel_append}')"
                        return _k_str
                    else if entry[0] == "p"
                        # partition info
                        return scope.get_info_str("p", dev.act_partition_table, "", dev.partition_table, "", scope.partition_lut)
                    else if entry[0] == "b"
                        # bootdevice
                        if dev.bootnetdevice
                            nd = dev.bootnetdevice
                            _n_str = "MAC of #{nd.devname} (driver #{nd.driver}) is #{nd.macaddr}"
                            if dev.dhcp_write
                                _n_str = "#{_n_str}, write"
                            else
                                _n_str = "#{_n_str}, no write"
                            if dev.dhcp_mac
                                _n_str = "#{_n_str}, greedy"
                            return _n_str
                        else
                            # none available
                            return "N/A"
                    else
                        return "---"
                else
                    return "..."
            scope.get_lut_val = (s_type, lut, val) ->
                if val of lut
                    return lut[val].name
                else
                    return "? #{s_type}: #{val} ?"
            scope.get_info_str = (s_type, act_val, act_vers, new_val, new_vers, lut) ->
                if act_val == new_val
                    if act_val
                        if act_vers == new_vers
                            # everything ok, same version
                            if act_vers
                                return "<span class='label label-success'><span class='glyphicon glyphicon-ok'></span></span> " + scope.get_lut_val(s_type, lut, act_val) + "(#{act_vers})"
                            else
                                return "<span class='label label-success'><span class='glyphicon glyphicon-ok'></span></span> " + scope.get_lut_val(s_type, lut, act_val)
                        else
                            return "<span class='label label-warning'><span class='glyphicon glyphicon-arrow-up'></span></span> " + scope.get_lut_val(s_type, lut, act_val) + "(#{act_vers} != #{new_vers})"
                    else
                        # both values are empty
                        return "<span class='label label-danger'><span class='glyphicon glyphicon-ban-circle'></span></span>"
                else
                    new_val_str = if new_val then scope.get_lut_val(s_type, lut, new_val) else "---"
                    act_val_str = if act_val then scope.get_lut_val(s_type, lut, act_val) else "---"
                    act_vers_str = if act_vers then " (#{act_vers})" else ""
                    new_vers_str = if new_vers then " (#{new_vers})" else ""
                    if act_val and new_val
                        # show source and target value
                        return "#{act_val_str}#{act_vers_str}<span class='label label-warning'><span class='glyphicon glyphicon-arrow-right'></span></span> #{new_val_str}#{new_vers_str}"
                    else if act_val
                        return "#{act_val_str}#{act_vers_str}<span class='label label-warning'><span class='glyphicon glyphicon-arrow-right'></span></span>"
                    else
                        return "<span class='label label-warning'><span class='glyphicon glyphicon-arrow-right'></span></span> #{new_val_str}#{new_vers_str}"
    }
]).directive("icswDeviceBootLogTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.boot.log.table")
        link : (scope, el, attrs) ->
            scope.num_show = 5
            scope.get_date = (ts) ->
                _t = moment.unix(ts)
                return _t.fromNow()
            scope.get_log_lines = () ->
                return scope.dev.log_lines[0..scope.num_show]
    }
])