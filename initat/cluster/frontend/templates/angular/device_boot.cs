{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

device_boot_template = """
<h2>
    Boot config for {{ devices.length }} devices<span ng-show="num_selected">, {{ num_selected }} selected</span>
</h2>
<form class="form-inline">
    <div class="btn-group">
        <input ng-repeat="entry in boot_options" type="button" ng-class="get_bo_class(entry[0])" value="{{ entry[1] }}" ng-click="toggle_bo(entry[0])"></input>
    </div>
    <input type="button" class="btn btn-sn btn-warning" ng-show="num_selected && any_type_1_selected" value="modify" ng-click="modify_many($event)"></input>
    <input class="form-control" ng-model="device_sel_filter" placeholder="selection..." ng-change="change_sel_filter()"></input>
</form>
<table ng-show="devices.length" class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <th>Group</th>
            <th>Device</th>
            <th>sel</th>
            <th>state</th>
            <th>network</th>
            <th ng-repeat="entry in boot_options" ng-show="bo_enabled[entry[0]] && entry[2] < 3">
                {{ entry[1] }}
            </th>
            <th ng-show="any_type_1_selected">
                action
            </th>
        </tr>
    </thead>
    <tbody>
        <tr devicerow ng-repeat-start="dev in devices"></tr>
        <tr ng-repeat-end ng-show="bo_enabled['l']">
            <td colspan="100">
                <devicelogs></devicelogs>
            </td>
        </tr>
    </tbody>
</table>
"""

device_row_template = """
    <td>{{ dev.device_group_name }}</td>
    <td>{{ dev.full_name }}</td>
    <td><input type="button" ng-class="get_dev_sel_class(dev)" ng-click="toggle_dev_sel(dev)" value="sel"></button></td>
    <td ng-class="dev.recvreq_state">{{ dev.recvreq_str }}</td>
    <td ng-class="dev.network_state">{{ dev.network }}</td>
    <td ng-repeat="entry in type_1_options()" ng-show="bo_enabled[entry[0]]" ng-class="get_td_class(entry)">
        {{ show_boot_option(entry) }}
    </td>
    <td ng-show="bo_enabled['s']">
        <div class="btn-group">
            <button type="button" class="btn btn-warning btn-xs dropdown-toggle" data-toggle="dropdown">
                action <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="soft_control(dev, 'reboot')"><a href="#">reboot</a></li>
                <li ng-click="soft_control(dev, 'halt')"><a href="#">halt</a></li>
                <li ng-click="soft_control(dev, 'poweroff')"><a href="#">poweroff</a></li>
            </ul>
        </div>
    </td>
    <td ng-show="bo_enabled['h']">
        <div class="btn-group" ng-repeat="cd_con in dev.slave_connections">
            <button type="button" class="btn btn-warning btn-xs dropdown-toggle" data-toggle="dropdown">
                {{ cd_con.parent.full_name }} <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="hard_control(cd_con, 'cycle')"><a href="#">cycle</a></li>
                <li ng-click="hard_control(cd_con, 'on')"><a href="#">on</a></li>
                <li ng-click="hard_control(cd_con, 'off')"><a href="#">off</a></li>
            </ul>
            <span ng-show="!$last">,</span>
        </div>
        <span ng-show="!dev.master_connections">
           not
        </span>
    </td>
    <td ng-show="any_type_1_selected">
        <input type="button" class="btn btn-xs btn-warning" value="modify" ng-click="modify_device(dev, $event)"></input>
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
                <select ng-model="num_show" class="form-control input-sm" ng-options="value as value for value in [5, 10, 20]">
                </select>
            </form>
        </th>
        <th>when</th>
    </tr>
    <tr ng-repeat="line in get_log_lines()">
        <td style="white-space:nowrap;">{{ line[2] | follow_fk:this:'log_source_lut':'name' }}</td>
        <td style="white-space:nowrap;">{{ line[3] || '---' }}</td>
        <td style="white-space:nowrap;">{{ line[4] | follow_fk:this:'log_status_lut':'name' }}</td>
        <td>{{ line[5] }}</td>
        <td style="white-space:nowrap;">{{ get_date(line[6]) }}</td>
    </tr>
</table>
"""

{% endverbatim %}

device_boot_module = angular.module("icsw.device.boot", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_boot_module])

device_boot_module.controller("boot_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        access_level_service.install($scope)
        $scope.enable_modal = true
        $scope.num_selected = 0
        $scope.any_type_1_selected = false
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
        $scope.change_sel_filter = () ->
            if $scope.cur_sel_timeout
                $timeout.cancel($scope.cur_sel_timeout)
            $scope.cur_sel_timeout = $timeout($scope.set_sel_filter, 500)
        $scope.set_sel_filter = () ->
            try
                cur_re = new RegExp($scope.device_sel_filter, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            for dev in $scope.devices
                dev.selected = if dev.name.match(cur_re) then true else false
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
        $scope.get_dev_sel_class = (dev) ->
            if dev.selected
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.toggle_dev_sel = (dev) ->
            dev.selected = !dev.selected
            if dev.selected
                $scope.num_selected++
            else
                $scope.num_selected--
        # mixins
        $scope.device_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.device_edit.edit_template = "boot_single_form.html"
        $scope.device_edit.modify_rest_url = "{% url 'boot:update_device' 1 %}".slice(1).slice(0, -2)
        $scope.device_edit.use_promise = true
        $scope.device_edit.modify_data_before_put = (data) ->
            # rewrite new_state / prod_link
            if data.target_state
                new_state = (entry for entry in $scope.valid_states when entry.idx == data.target_state)[0]
                data.new_state = new_state.status
                data.prod_link = new_state.network
            else
                data.new_state = null
                data.prod_link = null
            if $scope._edit_obj and $scope._edit_obj.bootnetdevice
                $scope._edit_obj.bootnetdevice.driver = $scope._edit_obj.driver
                $scope._edit_obj.bootnetdevice.macaddr = $scope._edit_obj.macaddr
        $scope.devsel_list = []
        $scope.devices = []
        # at least one boot_info received
        $scope.info_ok = false
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            if $scope.update_info_timeout
                $timeout.cancel($scope.update_info_timeout)
            $scope.info_ok = false
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload= () ->
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
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = (dev for dev in data[0])
                $scope.num_selected = 0
                for dev in $scope.devices
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
                $scope.device_lut = build_lut($scope.devices)
                $scope.kernels = data[1]
                $scope.images = data[2]
                $scope.partitions = data[3]
                $scope.kernel_lut = build_lut($scope.kernels)
                $scope.image_lut = build_lut($scope.images)
                $scope.partition_lut = build_lut($scope.partitions)
                if $scope.update_info_timeout
                    $timeout.cancel($scope.update_info_timeout)
                prod_nets = (entry for entry in data[5] when entry.network_type_identifier == "p")
                valid_states = []
                idx = 0
                for entry in data[4]
                    if not entry.prod_link
                        idx++
                        valid_states.push(
                            {
                                "idx"     : idx
                                "status"  : entry.idx
                                "network" : 0
                                "info"    : entry.info_string
                            }
                        )
                for prod_net in prod_nets
                    for entry in data[4]
                        if entry.prod_link
                            idx++
                            valid_states.push(
                                {
                                    "idx"     : idx
                                    "status"  : entry.idx
                                    "network" : prod_net.idx
                                    "info"    : "#{entry.info_string} into #{prod_net.info_string}"
                                }
                            )
                $scope.valid_states = valid_states
                $scope.valid_state_lut = build_lut($scope.valid_states)
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
                $.ajax
                    url     : "{% url 'boot:get_boot_info_json' %}"
                    data    : send_data
                    success : (xml) =>
                        $scope.update_info_timeout = $timeout($scope.update_info, 10000)
                        if parse_xml_response(xml)
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
                                dev.recvreq_state = tr_class
                                dev.network_state = tr_class
                                # target state
                                for _kv in ["new_state", "prod_link"]
                                    dev[_kv] = entry[_kv]
                                dev.target_state = 0
                                # rewrite device new_state / prod_link
                                if dev.new_state
                                    _list = (_entry for _entry in $scope.valid_states when _entry.status == dev.new_state)
                                    if dev.prod_link
                                        _list = (_entry for _entry in _list when _entry.network == dev.prod_link)
                                    dev.target_state = _list[0].idx
                                # copy image
                                for _kv in ["new_image", "act_image"]
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
                            $scope.$digest()
                if $scope.bo_enabled["l"]
                    send_data = {
                        "sel_list" : angular.toJson(([dev.idx, dev.latest_log] for dev in $scope.devices))
                    }
                    $.ajax
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
            $.ajax
                url     : "{% url 'boot:soft_control' %}"
                data    : {
                    "dev_pk" : dev.idx
                    "command" : command
                }
                success : (xml) =>
                    parse_xml_response(xml)
        $scope.hard_control = (cd_con, command) ->
            $.ajax
                url     : "{% url 'boot:hard_control' %}"
                data    : {
                    "cd_pk" : cd_con.idx
                    "command" : command
                }
                success : (xml) =>
                    parse_xml_response(xml)
        $scope.modify_device = (dev, event) ->
            $scope.device_info_str = dev.full_name
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
            dev = {
                "idx" : 0
                "bo_enabled" : $scope.bo_enabled
                # not really needed because bootnetdevice is not set
                "macaddr" : ""
                "driver" : ""
                "partition_table" : null
                "new_image" : null
                "new_kernel" : null
                "stage1_flavour" : "cpio"
                "kernel_append" : ""
                "dhcp_mac" : false
                "dhcp_write" : false
                "device_pks" : (dev.idx for dev in $scope.devices when dev.selected)
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
        install_devsel_link($scope.new_devsel, true, true, false)
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
            scope.show_boot_option = (entry) ->
                dev = scope.dev
                if scope.info_ok
                    if entry[0] == "t"
                        # target state
                        if dev.target_state
                            return scope.valid_state_lut[dev.target_state].info
                        else
                            return "---"
                        #console.log dev.new_state, dev.prod_link
                    else if entry[0] == "i"
                        # image
                        return scope.get_info_str(dev.act_image, dev.new_image, scope.image_lut)
                    else if entry[0] == "k"
                        # kernel
                        _k_str = scope.get_info_str(dev.act_kernel, dev.new_kernel, scope.kernel_lut)
                        if dev.act_kernel or dev.new_kernel
                            _k_str = "#{_k_str}, flavour is #{dev.stage1_flavour}"
                            if dev.kernel_append
                                _k_str = "#{_k_str} (append '#{dev.kernel_append}')"
                        return _k_str
                    else if entry[0] == "p"
                        # partition info
                        return scope.get_info_str(dev.act_partition_table, dev.partition_table, scope.partition_lut)
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
            scope.get_info_str = (act_val, new_val, lut) ->
                if act_val == new_val
                    if act_val
                        return lut[act_val].name
                    else
                        return "---"
                else
                    new_val_str = if new_val then lut[new_val].name else "---"
                    act_val_str = if act_val then lut[act_val].name else "---"
                    if act_val and new_val
                        return "#{act_val_str} (#{new_val_str})"
                    else if act_val
                        return act_val_str
                    else
                        return "[#{new_val_str}]"
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

