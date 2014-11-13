{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

device_boot_template = """
<h2>
    <span class="label label-danger" ng-show="conn_problems" title="number of connection problems">{{ conn_problems }}</span> Boot config for {{ devices.length }} devices<span ng-show="num_selected">, {{ num_selected }} selected</span>{{ get_global_bootserver_info() }}
</h2>
<form class="form-inline">
    <div class="btn-group">
        <input ng-repeat="entry in boot_options" type="button" ng-class="get_bo_class(entry[0])" value="{{ entry[1] }}" ng-click="toggle_bo(entry[0])"></input>
    </div>
    <input class="form-control" ng-model="device_sel_filter" placeholder="selection..." ng-change="change_sel_filter()"></input>
</form>
<table ng-show="devices.length" class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <th>Group</th>
            <th>Device</th>
            <th class="center">sel</th>
            <th>state</th>
            <th>network</th>
            <th ng-repeat="entry in boot_options" ng-show="bo_enabled[entry[0]] && entry[2] < 3">
                {{ entry[1] }}
            </th>
            <th ng-show="any_type_1_selected">
                action
            </th>
            <th ng-show="any_type_3_selected">
                log
            </th>
        </tr>
    </thead>
    <tbody>
        <tr devicerow ng-repeat-start="dev in devices"></tr>
        <tr ng-repeat-end ng-show="bo_enabled['l'] && dev.show_log">
            <td colspan="100">
                <devicelogs></devicelogs>
            </td>
        </tr>
    </tbody>
    <tfoot ng-show="devices.length > 1">
        <tr>
            <td colspan="2">Global actions</td>
            <td>
                <div class="btn-group btn-group-xs">
                    <input type="button" class="btn btn-success" value="S" ng-click="toggle_gdev_sel(1)" title="select all devices"></input>
                    <input type="button" class="btn btn-primary" value="T" ng-click="toggle_gdev_sel(0)" title="toggle device selection"></input>
                    <input type="button" class="btn btn-warning" value="C" ng-click="toggle_gdev_sel(-1)" title="clear device selection"></input>
                </div>
            </td>
            <td></td>
            <td></td>
            <td ng-repeat="entry in type_1_options()" ng-show="bo_enabled[entry[0]]"></td>
            <td ng-show="bo_enabled['s']">
                <div class="btn-group" ng-show="num_selected">
                    <button type="button" class="btn btn-warning btn-xs dropdown-toggle" data-toggle="dropdown">
                        action ({{ num_selected }})<span class="caret"></span>
                    </button>
                    <ul class="dropdown-menu">
                        <li ng-click="soft_control('', 'reboot')"><a href="#">reboot</a></li>
                        <li ng-click="soft_control('', 'halt')"><a href="#">halt</a></li>
                        <li ng-click="soft_control('', 'poweroff')"><a href="#">poweroff</a></li>
                    </ul>
                </div>
            </td>
            <td ng-show="bo_enabled['h']">
                <div class="btn-group" ng-show="num_selected_hc()">
                    <button type="button" class="btn btn-xs btn-warning" data-toggle="dropdown">
                        control ({{ num_selected_hc() }}) <span class="caret"></span>
                    </button>
                    <ul class="dropdown-menu">
                        <li ng-click="hard_control('', 'cycle')"><a href="#">cycle</a></li>
                        <li ng-click="hard_control('', 'on')"><a href="#">on</a></li>
                        <li ng-click="hard_control('', 'off')"><a href="#">off</a></li>
                    </ul>
                </div>
            </td>
            <td>
                <input type="button" class="btn btn-xs btn-primary" ng-show="num_selected && any_type_1_selected" value="modify ({{ num_selected }})" ng-click="modify_many($event)"></input>
            </td>
        </tr>
    </tfoot>
</table>
<form class="form-inline">
    <div class="btn-group">
        <input type="button" ng-class="show_mbl && 'btn btn-sm btn-success' || 'btn btn-sm'" value="macbootlog" ng-click="toggle_show_mbl()">
        </input>
    </div>
</form>
<div ng-show="show_mbl">
    <h4>Showing {{ mbl_entries.length }} Macbootlog entries</h4>
    <table class="table table-condensed table-hover table-striped" style="width:auto;">
        <thead>
            <tr>
                <th>Device</th>
                <th>type</th>
                <th>IP</th>
                <th>MAC</th>
                <th>Logsource</th>
                <th>created</th>
            </tr>
        </thead>
        <tbody>
            <tr ng-repeat="mbl in mbl_entries">
                <td>{{ mbl.device_name }}</td>
                <td>{{ mbl.entry_type }}</td>
                <td>{{ mbl.ip_action }}</td>
                <td>{{ mbl.macaddr }}</td>
                <td style="white-space:nowrap;">{{ mbl.log_source | follow_fk:this:'log_source_lut':'name' }}</td>
                <td>{{ get_mbl_created(mbl) }}</td>
            </tr>
        </tbody>
    </table>
</div>
"""

device_row_template = """
    <td>{{ dev.device_group_name }}</td>
    <td ng-class="get_device_name_class(dev)">{{ dev.full_name }}{{ get_bootserver_info(dev) }}</td>
    <td class="center"><input type="button" ng-class="get_dev_sel_class(dev)" ng-click="toggle_dev_sel(dev, 0)" value="sel"></button></td>
    <td ng-class="dev.recvreq_state">{{ dev.recvreq_str }}</td>
    <td ng-class="dev.network_state">{{ dev.network }}</td>
    <td ng-repeat="entry in type_1_options()" ng-show="bo_enabled[entry[0]]" ng-class="get_td_class(entry)" ng-bind-html="show_boot_option(entry)">
    </td>
    <td ng-show="bo_enabled['s']">
        <div class="btn-group" ng-show="valid_net_state()">
            <button type="button" class="btn btn-warning btn-xs dropdown-toggle" data-toggle="dropdown">
                action <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="soft_control(dev, 'reboot')"><a href="#">reboot</a></li>
                <li ng-click="soft_control(dev, 'halt')"><a href="#">halt</a></li>
                <li ng-click="soft_control(dev, 'poweroff')"><a href="#">poweroff</a></li>
            </ul>
        </div>
        <span class='glyphicon glyphicon-ban-circle' ng-show="!valid_net_state()"></span>
    </td>
    <td ng-show="bo_enabled['h']">
        <div class="btn-group" ng-repeat="cd_con in dev.slave_connections">
            <button type="button" ng-class="get_hc_class(cd_con)" ng-disabled="get_hc_disabled(cd_con)" data-toggle="dropdown">
                {{ get_hc_info(cd_con) }} <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="hard_control(cd_con, 'cycle')"><a href="#">cycle</a></li>
                <li ng-click="hard_control(cd_con, 'on')"><a href="#">on</a></li>
                <li ng-click="hard_control(cd_con, 'off')"><a href="#">off</a></li>
            </ul>
            <span ng-show="!$last">,</span>
        </div>
        <span ng-show="!dev.slave_connections">
            waiting...
        </span>
        <span ng-show="dev.slave_connections && dev.slave_connections.length == 0">
            ---
        </span>
    </td>
    <td ng-show="any_type_1_selected">
        <input type="button" class="btn btn-xs btn-primary" value="modify" ng-click="modify_device(dev, $event)"></input>
    </td>
    <td ng-show="any_type_3_selected">
        <input type="button" ng-class="get_devlog_class(dev)" ng-value="get_devlog_value(dev)" ng-click="change_devlog_flag(dev)"></input>
    </td>
"""

device_log_row_template = """
<table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
    <tr>
        <th>Source</th>
        <th>User</th>
        <th>Status</th>
        <th>
            <form class="form-inline">
                Number of log lines: {{ dev.num_logs }}, show
                <select ng-model="num_show" class="form-control input-sm" ng-options="value as value for value in [5, 20, 50, 100]">
                </select>
            </form>
        </th>
        <th>when</th>
    </tr>
    <tr ng-repeat="line in get_log_lines()">
        <td style="white-space:nowrap;">{{ line[2] | follow_fk:this:'log_source_lut':'name' }}</td>
        <td style="white-space:nowrap;">{{ line[3] | follow_fk:this:'user_lut':'login':'---' }}</td>
        <td style="white-space:nowrap;">{{ line[4] | follow_fk:this:'log_status_lut':'name' }}</td>
        <td>{{ line[5] }}</td>
        <td style="white-space:nowrap;">{{ get_date(line[6]) }}</td>
    </tr>
</table>
"""

{% endverbatim %}

device_boot_module = angular.module("icsw.device.boot", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"])

angular_module_setup([device_boot_module])

device_boot_module.controller("boot_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        access_level_service.install($scope)
        $scope.enable_modal = true
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
        $scope.device_edit.modify_rest_url = "{% url 'boot:update_device' 1 %}".slice(1).slice(0, -2)
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
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_network" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_boot"}]),
                # 1
                restDataSource.reload(["{% url 'rest:kernel_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:image_list' %}", {}])
                restDataSource.reload(["{% url 'rest:partition_table_list' %}", {}])
                # 4
                restDataSource.reload(["{% url 'rest:status_list' %}", {}])
                restDataSource.reload(["{% url 'rest:network_list' %}", {}])
                # 6
                restDataSource.reload(["{% url 'rest:log_source_list' %}", {}])
                restDataSource.reload(["{% url 'rest:log_status_list' %}", {}])
                # 8
                restDataSource.reload(["{% url 'rest:user_list' %}", {}])
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"all_mother_servers" : true}])
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
                $scope.log_source_lut = build_lut(data[6])
                $scope.log_status_lut = build_lut(data[7])
                $scope.user_lut = build_lut(data[8])
                $scope.device_lut = build_lut($scope.devices)
                $scope.kernels = data[1]
                $scope.images = data[2]
                # only use entries valid for nodeboot
                $scope.partitions = (entry for entry in data[3] when entry.nodeboot and entry.valid and entry.enabled)
                $scope.kernel_lut = build_lut($scope.kernels)
                $scope.image_lut = build_lut($scope.images)
                $scope.partition_lut = build_lut($scope.partitions)
                $scope.mother_servers = build_lut(data[9])
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
                send_data = {
                    "sel_list" : $scope.devsel_list
                    "call_mother" : 1
                }
                call_ajax
                    url     : "{% url 'boot:get_boot_info_json' %}"
                    data    : send_data
                    success : (xml) =>
                        $scope.update_info_timeout = $timeout($scope.update_info, 10000)
                        if parse_xml_response(xml, 40, false)
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
                                # copy image
                                for _kv in ["new_image", "act_image", "imageversion"]
                                    dev[_kv] = entry[_kv]
                                # copy kernel
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
                if $scope.bo_enabled["l"]
                    send_data = {
                        "sel_list" : angular.toJson(([dev.idx, dev.latest_log] for dev in $scope.devices))
                    }
                    call_ajax
                        url      : "{% url 'boot:get_devlog_info' %}"
                        data     : send_data
                        dataType : "json"
                        success  : (json) =>
                            if json.devlog_lines
                                for entry in json.devlog_lines
                                    # format: pk, device_id, log_source_id, user_id, log_status_id, text, seconds
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
            call_ajax
                url     : "{% url 'boot:soft_control' %}"
                data    : {
                    "dev_pk_list" : angular.toJson(dev_pk_list)
                    "command"     : command
                }
                success : (xml) =>
                    parse_xml_response(xml)
        $scope.hard_control = (cd_con, command) ->
            if cd_con
                cd_pk_list = [cd_con.idx]
            else
                cd_pk_list = []
                for dev in $scope.devices
                    if dev.selected and dev.slave_connections.length
                        for slave_con in dev.slave_connections
                            cd_pk_list.push(slave_con.idx)
            call_ajax
                url     : "{% url 'boot:hard_control' %}"
                data    : {
                    "cd_pk_list" : angular.toJson(cd_pk_list)
                    "command"    : command
                }
                success : (xml) =>
                    parse_xml_response(xml)
        $scope.modify_device = (dev, event) ->
            $scope.device_info_str = dev.full_name
            $scope.device_edit.edit_template = "boot_single_form.html"
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
            $scope.device_edit.edit_template = "boot_many_form.html"
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
            Restangular.all("{% url 'rest:macbootlog_list' %}".slice(1)).getList({"_num_entries" : 50, "_order_by" : "-pk"}).then(
                (data) ->
                    $scope.mbl_entries = data
                    $scope.mbl_timeout = $timeout($scope.fetch_macbootlog_entries, 5000)
            )
        $scope.get_mbl_created = (mbl) ->
            return moment.unix(mbl.created).format(DT_FORM)
        install_devsel_link($scope.new_devsel, false)
]).directive("boottable", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("deviceboottable.html")
    }
).directive("devicerow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devicebootrow.html")
        link : (scope, el, attrs) ->
            scope.get_td_class = (entry) ->
                dev = scope.dev
                _cls = ""
                if scope.info_ok
                    if entry[0] == "i"
                        _cls = scope._get_td_class(dev.act_image, dev.new_image)
                    else if entry[0] == "p"
                        _cls = scope._get_td_class(dev.act_partition_table, dev.partition_table)
                    else if entry[0] == "k"
                        _cls = scope._get_td_class(dev.act_kernel, dev.new_kernel)
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
                        img_str = scope.get_info_str("i", dev.act_image, dev.new_image, scope.image_lut)
                        # check version
                        cur_vers = dev.imageversion
                        if dev.act_image
                            img_info = scope.image_lut[dev.act_image]
                            img_vers = "#{img_info.version}.#{img_info.release}"
                            if img_vers != cur_vers
                                img_str = "#{img_str} (#{cur_vers} / #{img_vers})"
                        return img_str
                    else if entry[0] == "k"
                        # kernel
                        _k_str = scope.get_info_str("k", dev.act_kernel, dev.new_kernel, scope.kernel_lut)
                        if dev.act_kernel or dev.new_kernel
                            _k_str = "#{_k_str}, flavour is #{dev.stage1_flavour}"
                            if dev.kernel_append
                                _k_str = "#{_k_str} (append '#{dev.kernel_append}')"
                        return _k_str
                    else if entry[0] == "p"
                        # partition info
                        return scope.get_info_str("p", dev.act_partition_table, dev.partition_table, scope.partition_lut)
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
            scope.get_info_str = (s_type, act_val, new_val, lut) ->
                if act_val == new_val
                    if act_val
                        # everything ok
                        return "<span class='glyphicon glyphicon-ok'></span> " + scope.get_lut_val(s_type, lut, act_val)  
                    else
                        # both values are empty
                        return "<span class='glyphicon glyphicon-ban-circle'></span>"
                else
                    new_val_str = if new_val then scope.get_lut_val(s_type, lut, new_val) else "---"
                    act_val_str = if act_val then scope.get_lut_val(s_type, lut, act_val) else "---"
                    if act_val and new_val
                        # show source and target value
                        return "#{act_val_str} <span class='glyphicon glyphicon-arrow-right'></span> #{new_val_str}"
                    else if act_val
                        return "#{act_val_str} <span class='glyphicon glyphicon-arrow-right'>"
                    else
                        return "<span class='glyphicon glyphicon-arrow-right'> #{new_val_str}"
    }
).directive("devicelogs", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devicelogrow.html")
        link : (scope, el, attrs) ->
            scope.num_show = 5
            scope.get_date = (ts) ->
                _t = moment.unix(ts)
                return _t.fromNow()
            scope.get_log_lines = () ->
                return scope.dev.log_lines[0..scope.num_show]
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("deviceboottable.html", device_boot_template)
    $templateCache.put("devicebootrow.html", device_row_template)
    $templateCache.put("devicelogrow.html", device_log_row_template)
)

{% endinlinecoffeescript %}

</script>

