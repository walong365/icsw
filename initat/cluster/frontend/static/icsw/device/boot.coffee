# Copyright (C) 2012-2016 init.at
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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "restangular", "ui.select"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.deployboot", {
            url: "/deployboot"
            templateUrl: "icsw/main/deploy/boot.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Boot nodes"
                rights: ["device.change_boot"]
                service_types: ["mother"]
                licenses: ["netboot"]
                menuHeader:
                    key: "cluster"
                    name: "Cluster"
                    icon: "fa-cubes"
                    ordering: 80
                menuEntry:
                    menukey: "cluster"
                    icon: "fa-rocket"
                    ordering: 10
        }
    )
]).service("icswLogTree",
[
    "$q",
(
    $q,
) ->
    class icswLogTree
        constructor: (source_list, level_list) ->
            @source_list = []
            @level_list = []
            @update(source_list, level_list)

        update: (source_list, level_list) =>
            @source_list.length = 0
            for entry in source_list
                @source_list.push(entry)
            @level_list.length = 0
            for entry in level_list
                @level_list.push(entry)
            @build_luts()

        build_luts: () =>
            @source_lut = _.keyBy(@source_list, "idx")
            @level_lut = _.keyBy(@level_list, "idx")

]).service("icswLogTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS",
    "icswLogTree",
(
    $q, Restangular, ICSW_URLS, icswCachingCall,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS,
    icswLogTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_LOG_SOURCE_LIST, {}
        ]
        [
            ICSW_URLS.REST_LOG_LEVEL_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** log tree loaded ***"
                _result = new icswLogTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).service("icswBootStatusTree",
[
    "$q",
(
    $q,
) ->
    class icswBootStatusTree
        constructor: (status_list, @network_tree) ->
            @status_list = []
            @special_states_list = []
            @network_states_list = []
            @update(status_list)

        update: (status_list) =>
            @status_list.length = 0
            for entry in status_list
                @status_list.push(entry)
            # dummy index to make reference easy
            _idx = 0
            @special_states_list.length = 0
            @network_states_list.length = 0
            for entry in @status_list
                # console.log entry
                if not entry.prod_link
                    _idx++
                    @special_states_list.push(
                        {
                            idx: _idx
                            status: entry.idx
                            network: null
                            info: entry.info_string
                            full_info: entry.info_string
                        }
                    )
            for net in @network_tree.nw_list
                if net.network_type_identifier == "p"
                    net_list = {
                        info: "#{net.info_string}"
                        network: net.idx
                        states: []
                    }
                    @network_states_list.push(net_list)
                    for clean_flag in [false, true]
                        for entry in @status_list
                            if entry.prod_link and entry.is_clean == clean_flag
                                _idx++
                                new_state = {
                                    idx: _idx
                                    status: entry.idx
                                    network: net.idx
                                    info: "#{entry.info_string}"
                                    full_info: "#{entry.info_string} into #{net.info_string}"
                                }
                                net_list.states.push(new_state)
            @build_luts()

        build_luts: () =>
            @status_lut = _.keyBy(@status_list, "idx")
            @special_states_lut = _.keyBy(@special_states_list, "idx")
            # does not resolve to network_states_list but one level deeper
            @network_states_lut = {}
            # all states lut
            @all_states_lut = _.keyBy(@special_states_list, "idx")
            for net in @network_states_list
                for state in net.states
                    @all_states_lut[state.idx] = state
                    @network_states_lut[state.idx] = state

]).service("icswBootStatusTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS",
    "icswBootStatusTree", "icswNetworkTreeService",
(
    $q, Restangular, ICSW_URLS, icswCachingCall,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS,
    icswBootStatusTree, icswNetworkTreeService,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_STATUS_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswNetworkTreeService.load(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** BootStatus tree loaded ***"
                _result = new icswBootStatusTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).directive("icswDeviceBootTable", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.boot.table")
        controller: "icswDeviceBootCtrl"
    }
]).service("icswBootLogLine",
[
    "$q",
(
    $q,
) ->
    class icswBootLogLine
        constructor: (line, log_tree, user_tree) ->
            # format: pk, device_id, log_source_id, user_id, log_level_id, text, seconds
            @dt = line[6]
            @moment = moment.unix(@dt)
            @abs_dt = @moment.format(DT_FORM)
            @text = line[5]
            if line[2] of log_tree.source_lut
                @source = log_tree.source_lut[line[2]].description
            else
                @source = "---"
            if line[3] of user_tree.user_lut
                @user = user_tree.user_lut[line[3]].admin
            else
                @user = "---"
            if line[4] of log_tree.level_lut
                @log_level = log_tree.level_lut[line[4]].name
            else
                @log_level = "---"
            if @log_level == "error"
                @class = "danger"
            else if @log_level == "warn"
                @class = "warning"
            else
                @class = ""

        get_relative_date: () =>
            return @moment.fromNow()

]).service("icswDeviceBootHelper",
[
    "$q", "icswBootLogLine",
(
    $q, icswBootLogLine,
) ->
    class icswDeviceBootHelper
        constructor: (@device, @g_helper) ->
            # g_helper ist the global boothelper

            # network and states

            @network = undefined
            @net_state = "down"
            @valid_net_state = false
            @recvreq_state = "warning"
            @network_state = "warning"
            @recvreq_str = "---"

            # connections

            @slave_connections_valid = false
            @slave_connections_info = "waiting..."
            @slave_connections = []
            @master_connections = []

            # device logs

            @logs_received = false
            @show_logs = false
            @num_logs = 0
            @logs_present = 0
            @latest_log = 0
            @logs = []
            @set_log_classes()

        toggle_show_log: () =>
            @show_logs = !@show_logs
            @set_log_classes()
            return @show_logs

        set_log_classes: () =>
            if @show_logs
                @log_btn_class = "btn btn-xs btn-success"
                @log_btn_value = "hide"
            else
                @log_btn_class = "btn btn-xs"
                @log_btn_value = "show"

        feed: (data) =>
            # console.log "feed", data
            if data.hoststatus_str
                @recvreq_str = data.hoststatus_str +  "(" + data.hoststatus_source + ")"
            else
                @recvreq_str = "rcv: ---"
            @net_state = data.net_state
            @valid_net_state = @net_state == "up"
            tr_class = {
                down: "danger"
                unknown: "warning"
                ping: "warning"
                up: "success"
            }[@net_state]
            @network = "#{data.network} (#{data.net_state})"
            @recvreq_state = tr_class
            @network_state = tr_class

            dev = @device
            dev.target_state = 0
            # target state
            for _kv in ["new_state", "prod_link"]
                dev[_kv] = data[_kv]
            status_tree = @g_helper.struct.boot_status_tree
            if dev.new_state
                if dev.prod_link
                    _list = (_entry for _entry in status_tree.network_states_list when _entry.network == dev.prod_link)
                    if _list.length
                        _list = (_entry for _entry in _list[0].states when _entry.status == dev.new_state)
                else
                    _list = (_entry for _entry in status_tree.special_states_list when _entry.status == dev.new_state)
                if _list.length
                    dev.target_state = _list[0].idx
                    # console.log dev.idx, dev.target_state, dev.new_state, dev.prod_link

            # copy image, act_image is a tuple (idx, vers, release) or none
            for _kv in ["new_image", "act_image"]
                dev[_kv] = data[_kv]
            # copy kernel, act_kernel is a tuple (idx, vers, release) or none
            for _kv in ["new_kernel", "act_kernel", "stage1_flavour", "kernel_append"]
                dev[_kv] = data[_kv]
            # copy partition
            for _kv in ["act_partition_table", "partition_table"]
                dev[_kv] = data[_kv]
            # copy bootdevice
            for _kv in ["dhcp_mac", "dhcp_write", "dhcp_written", "dhcp_error", "bootnetdevice"]
                dev[_kv] = data[_kv]
            # master connections
            @slave_connections_valid = true
            for _kv in ["master_connections", "slave_connections"]
                @[_kv].length = 0
                for entry in data[_kv]
                    # TODO: make dynamic updates to suppress excessive redraw of dropdown lists
                    @[_kv].push(entry)
                    # console.log entry, @g_helper.cd_reachable

                    # set info

                    r_str = entry.parent.full_name
                    info_f = (entry["parameter_i#{i}"] for i in [1, 2, 3, 4])
                    info_f.reverse()
                    for i in [1..4]
                        if info_f.length and info_f[0] == 0
                            info_f.splice(0, 1)
                    info_f.reverse()
                    if info_f.length
                        info_str = info_f.join("/")
                        r_str = "#{r_str} (#{info_str})"
                    entry.$$info_str = r_str

                    # reachability / class

                    if entry.parent.idx of @g_helper.cd_reachable
                        if @g_helper.cd_reachable[entry.parent.idx]
                            [_d_flag, _class] = [false, "btn btn-success btn-xs dropdown-toggle"]
                        else
                            [_d_flag, _class] = [true, "btn btn-danger btn-xs dropdown-toggle"]
                    else
                        [_d_flag, _class] = [false, "btn btn-xs dropdown-toggle"]
                    entry.$$disabled = _d_flag
                    entry.$$btn_class = _class

            if @slave_connections.length
                @slave_connections_info = ""
            else
                @slave_connections_info = "---"

        feed_logs: (data) =>
            @logs_received = true
            @num_logs = data.total
            for line in data.lines
                @latest_log = Math.max(line[0], @latest_log)
                new_line = new icswBootLogLine(line, @g_helper.struct.log_tree, @g_helper.struct.user_group_tree)
                @logs.splice(0, 0, new_line)
            @logs_present = @logs.length

]).service("icswGlobalBootHelper",
[
    "$q", "$timeout", "icswSimpleAjaxCall", "ICSW_URLS", "icswDeviceBootHelper",
(
    $q, $timeout, icswSimpleAjaxCall, ICSW_URLS, icswDeviceBootHelper,
) ->
    class icswGlobalBootHelper
        constructor: (@struct, devices, @salt_callback) ->
            # @struct is the global boot structure
            @devices = []
            @fetch_running = false
            @fetch_timeout = undefined
            # connection problem counter
            @connection_problem_counter = 0
            @update(devices)

        update: (devices) =>
            @devices.length = 0
            for entry in devices
                @devices.push(entry)
                if not entry.$$boot_helper?
                    # install device boothelper
                    entry.$$boot_helper = new icswDeviceBootHelper(entry, @)
            @device_lut = _.keyBy(@devices, "idx")
            # console.log "GlobalBootHelper, devices=",  @devices.length

        stop_timeout: () =>
            if @fetch_timeout
                $timeout.cancel(@fetch_timeout)
                @fetch_timeout = undefined

        close: () =>
            @stop_timeout()

        fetch: () =>
            new_timeout = () =>
                @fetch_timeout = $timeout(@fetch, 10000)

            defer = $q.defer()
            @stop_timeout()

            if not @fetch_running
                # list of devices with devlog fetch
                log_fetch_list = []
                if @struct.boot_options.is_enabled("l")
                    for dev in @devices
                        if dev.$$boot_helper.show_logs
                            log_fetch_list.push([dev.idx, dev.$$boot_helper.latest_log])
                @fetch_running = true
                send_data = {
                    sel_list: (dev.idx for dev in @devices)
                    call_mother: 1
                }
                wait_list = [
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.BOOT_GET_BOOT_INFO_JSON
                        data: send_data
                    )
                ]
                if log_fetch_list.length
                    wait_list.push(
                        icswSimpleAjaxCall(
                            url: ICSW_URLS.BOOT_GET_DEVLOG_INFO
                            data: {
                                sel_list: angular.toJson(log_fetch_list)
                            }
                            dataType: "json"
                        )
                    )
                $q.all(wait_list).then(
                    (result) =>
                        xml = result[0]
                        @fetch_running = false
                        @connection_problem_counter = 0

                        # set cd_reachable result

                        cd_result = $(xml).find("value[name='cd_response']")
                        if cd_result.length
                            @cd_reachable = angular.fromJson(cd_result.text())
                        else
                            @cd_reachable = {}

                        # interpret state data

                        _resp = angular.fromJson($(xml).find("value[name='response']").text())
                        for entry in _resp
                            @device_lut[entry.idx].$$boot_helper.feed(entry)

                        # device logs (optional)

                        if result.length > 1
                            dev_logs = result[1]
                            if dev_logs.dev_logs
                                for dev_id, log_struct of dev_logs.dev_logs
                                    @device_lut[parseInt(dev_id)].$$boot_helper.feed_logs(log_struct)

                        @salt_callback()
                        new_timeout()
                        defer.resolve("fetched")
                    (notok) =>
                        @fetch_running = false
                        @connection_problem_counter++
                        new_timeout()
                        defer.reject("not fetched")
                )
            else
                defer.reject("already running")
            return defer.promise

]).service("icswBootDisplayOption",
[
    "$q",
(
    $q,
) ->
    class icswBootDisplayOption
        constructor: (@short, @name, @type) ->
            # type:
            # 1 ... option to modify globally
            # 2 ... local option
            # 3 ... appends a new line
            @enabled = false
            @display = false
            @set_class()

        toggle_enabled: () =>
            @enabled = !@enabled
            @display = @enabled && @type < 3
            @set_class()
            return @enabled

        set_class: () =>
            @$$input_class = if @enabled then "btn btn-sm btn-success" else "btn btn-sm"

]).service("icswBootDisplayOptions",
[
    "$q",
(
    $q,
) ->
    class icswBootDisplayOptions
        constructor: (opts...) ->
            @list = []
            @lut = {}
            for entry in opts
                @list.push(entry)
                @lut[entry.short] = entry
            @type_1_options = (entry for entry in @list when entry.type == 1)
            @build_selected_info()

        is_enabled: (short) =>
            return @lut[short].enabled

        toggle_enabled: (short) =>
            if short of @lut
                _ret = @lut[short].toggle_enabled()
                @build_selected_info()
            else
                console.error "unknown BootOptionType #{short}"
                _ret = false
            return _ret

        build_selected_info: () =>
            for _t_idx in [1..3]
                _attr_name = "any_type_#{_t_idx}_selected"
                @[_attr_name] = _.some(entry.type == _t_idx for entry in @list when entry.enabled)

        get_bo_enabled: () =>
            # helper function
            _bo = {}
            for _short, entry of @lut
                _bo[_short] = entry.enabled
            return _bo

]).controller("icswDeviceBootCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "ICSW_SIGNALS",
    "$q", "icswAcessLevelService", "$timeout", "$rootScope", "toaster",
    "icswTools", "ICSW_URLS", "icswSimpleAjaxCall", "icswDeviceTreeService",
    "icswActiveSelectionService", "icswConfigTreeService", "icswLogTreeService",
    "icswKernelTreeService", "icswImageTreeService", "icswUserGroupTreeService",
    "icswPartitionTableTreeService", "icswNetworkTreeService", "icswBootStatusTreeService",
    "icswGlobalBootHelper", "icswDeviceTreeHelperService", "icswBootDisplayOption",
    "icswBootDisplayOptions", "blockUI", "icswComplexModalService",
(
    $scope, $compile, $filter, $templateCache, Restangular, ICSW_SIGNALS,
    $q, icswAcessLevelService, $timeout, $rootScope, toaster,
    icswTools, ICSW_URLS, icswSimpleAjaxCall, icswDeviceTreeService,
    icswActiveSelectionService, icswConfigTreeService, icswLogTreeService,
    icswKernelTreeService, icswImageTreeService, icswUserGroupTreeService,
    icswPartitionTableTreeService, icswNetworkTreeService, icswBootStatusTreeService,
    icswGlobalBootHelper, icswDeviceTreeHelperService, icswBootDisplayOption,
    icswBootDisplayOptions, blockUI, icswComplexModalService,
) ->
    icswAcessLevelService.install($scope)

    $scope.boot_options = new icswBootDisplayOptions(
        new icswBootDisplayOption("t", "target_state", 1)
        new icswBootDisplayOption("k", "kernel", 1)
        new icswBootDisplayOption("i", "image", 1)
        new icswBootDisplayOption("p", "partition", 1)
        new icswBootDisplayOption("b", "bootdevice", 1)
        new icswBootDisplayOption("s", "soft control", 2)
        new icswBootDisplayOption("h", "hard control", 2)
        new icswBootDisplayOption("l", "devicelog", 3)
    )

    $scope.struct = {
        # tree is valid
        tree_valid: false
        # device tree
        device_tree: undefined
        # config tree
        config_tree: undefined
        # devices
        devices: []
        # mother servers
        mother_server_list: []
        mother_server_lut: {}
        # log tree
        log_tree: undefined
        # kernel tree
        kernel_tree: undefined
        # image tree
        image_tree: undefined
        # user/group tree
        user_group_tree: undefined
        # partition table tree
        partition_table_tree: undefined
        # network tree
        network_tree: undefined
        # boot status tree
        boot_status_tree: undefined
        # global bootserver info
        global_bootserver_info: ""
        # number of selected devices
        num_selected: 0
        # number of selected devices with connections
        num_selected_hc: 0
        # device selection strings
        device_sel_filter: ""
        # boot helper structur
        boot_helper: undefined
        # boot options, for icswGlobalBootHelper
        boot_options: $scope.boot_options
        # show macbootlog
        show_mbl: false
    }

    $scope.$on("$destroy", () ->
        if $scope.struct.boot_helper?
            $scope.struct.boot_helper.close()
    )

    $scope.new_devsel = (dev) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswConfigTreeService.load($scope.$id)
                icswLogTreeService.load($scope.$id)
                icswKernelTreeService.load($scope.$id)
                icswImageTreeService.load($scope.$id)
                icswUserGroupTreeService.load($scope.$id)
                icswPartitionTableTreeService.load($scope.$id)
                icswNetworkTreeService.load($scope.$id)
                icswBootStatusTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.config_tree = data[1]
                $scope.struct.log_tree = data[2]
                $scope.struct.kernel_tree = data[3]
                $scope.struct.image_tree = data[4]
                $scope.struct.user_group_tree = data[5]
                $scope.struct.partition_table_tree = data[6]
                $scope.struct.network_tree = data[7]
                $scope.struct.boot_status_tree = data[8]
                $scope.struct.devices.length = 0
                for _dev in dev
                    if not _dev.is_meta_device
                        $scope.struct.devices.push(_dev)
                # get mother masters and slaves
                _mother_list = []
                for config in $scope.struct.config_tree.list
                    if config.name in ["mother_server"]
                        for _dc in config.device_config_set
                            if _dc.device not in _mother_list
                                _mother_list.push(_dc.device)
                $scope.struct.mother_server_list = ($scope.struct.device_tree.all_lut[_dev] for _dev in _mother_list)
                $scope.struct.mother_server_lut = _.keyBy($scope.struct.mother_server_list, "idx")
                if $scope.struct.boot_helper?
                    $scope.struct.boot_helper.update($scope.struct.devices)
                else
                    $scope.struct.boot_helper = new icswGlobalBootHelper($scope.struct, $scope.struct.devices, salt_devices)
                salt_devices()
                # init boot_helper and fetch device network
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $q.allSettled(
                    [
                        $scope.struct.device_tree.enrich_devices(hs, ["network_info"])
                        $scope.struct.boot_helper.fetch()
                    ]
                ).then(
                    (result) ->
                        # console.log result
                        $scope.struct.tree_valid = true
                )
        )

    # helper functions
    salt_devices = () ->

        # global bootserver info

        _bs_list = _.uniq(dev.bootserver for dev in $scope.struct.devices when dev.bootserver)
        if _bs_list.length == 1
            if _bs_list[0] of $scope.struct.mother_server_lut
                bs_info = "on bootserver #{$scope.struct.mother_server_lut[_bs_list[0]].full_name}"
            else
                bs_info = "on bootserver with pk=#{_bs_list[0]}"
        else if _bs_list.length
            bs_inof = "on #{_bs_list.length} bootservers"
        else
            bs_info = "no bootserver info"
        $scope.struct.global_bootserver_info = bs_info

        # local bootserver info

        for dev in $scope.struct.devices
            if dev.bootserver
                dev.$$row_class = ""
                if dev.bootserver of $scope.struct.mother_server_lut
                    bs_info = "(#{$scope.struct.mother_server_lut[dev.bootserver].full_name})"
                    dev.$$boot_name_class= ""
                else
                    bs_info = "(N/A)"
                    dev.$$boot_name_class= "warning"
            else
                dev.$$row_class = "danger"
                dev.$$boot_name_class = ""
                bs_info = "(no BS)"

            dev.$$local_bootserver_info = bs_info

            salt_device(dev)

    get_lut_val = (s_type, val) ->
        if s_type == "i"
            lut = $scope.struct.image_tree.lut
            _attr_name = "name"
        else if s_type == "k"
            lut = $scope.struct.kernel_tree.lut
            _attr_name = "display_name"
        else if s_type == "p"
            lut = $scope.struct.partition_table_tree.lut
            _attr_name = "name"
        else if s_type == "i"
            lut = $scope.struct.image_tree.lut
            _attr_name = "name"
        if val of lut
            return lut[val][_attr_name]
        else
            return "? #{s_type}: #{val} ?"

    get_info_str = (s_type, act_val, act_vers, new_val, new_vers) ->
        if act_val == new_val
            if act_val
                if act_vers == new_vers
                    # everything ok, same version
                    if act_vers
                        return "<span class='label label-success'><span class='glyphicon glyphicon-ok'></span></span> " + get_lut_val(s_type, act_val) + " (#{act_vers})"
                    else
                        return "<span class='label label-success'><span class='glyphicon glyphicon-ok'></span></span> " + get_lut_val(s_type, act_val)
                else
                    return "<span class='label label-warning'><span class='glyphicon glyphicon-arrow-up'></span></span> " + get_lut_val(s_type, act_val) + " (#{act_vers} != #{new_vers})"
            else
                # both values are empty
                return "<span class='label label-danger'><span class='glyphicon glyphicon-ban-circle'></span></span>"
        else
            new_val_str = if new_val then get_lut_val(s_type, new_val) else "---"
            act_val_str = if act_val then get_lut_val(s_type, act_val) else "---"
            act_vers_str = if act_vers then " (#{act_vers})" else ""
            new_vers_str = if new_vers then " (#{new_vers})" else ""
            if act_val and new_val
                # show source and target value
                return "#{act_val_str}#{act_vers_str}<span class='label label-warning'><span class='glyphicon glyphicon-arrow-right'></span></span> #{new_val_str}#{new_vers_str}"
            else if act_val
                return "#{act_val_str}#{act_vers_str}<span class='label label-warning'><span class='glyphicon glyphicon-arrow-right'></span></span>"
            else
                return "<span class='label label-warning'><span class='glyphicon glyphicon-arrow-right'></span></span> #{new_val_str}#{new_vers_str}"

    resolve_version = (lut, idx, attr_name) ->
        if idx of lut
            _obj = lut[idx]
            if attr_name
                return _obj[attr_name]
            else
                return "#{_obj.version}.#{_obj.release}"
        else
            return null

    get_latest_entry = (hist_tuple, lut, key) ->
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

    salt_device = (dev) ->
        # clear selection flag if not set

        if not dev.$$boot_selected?
            dev.$$boot_selected = false
        if dev.$$boot_selected
            dev.$$boot_selection_class = "btn btn-xs btn-success"
        else
            dev.$$boot_selection_class = "btn btn-xs"

        # build info fields
        out_list = []
        for opt in $scope.boot_options.type_1_options
            _type = opt.short
            if opt.enabled
                # default values
                [_out, _class] = ["N/A", "danger"]
                if _type == "t"
                    # target state
                    _class = ""
                    if dev.target_state
                        _out = $scope.struct.boot_status_tree.all_states_lut[dev.target_state].full_info
                    else
                        _out = "---"
                else if _type == "i"
                    # format: idx, version, release
                    act_image = if dev.act_image then dev.act_image[0] else null
                    if act_image
                        _act_image_version = "#{dev.act_image[1]}.#{dev.act_image[2]}"
                    else
                        _act_image_version = ""
                    _new_image_version = resolve_version($scope.struct.image_tree.lut, dev.new_image)
                    _out = get_info_str("i", act_image, _act_image_version, dev.new_image, _new_image_version)
                    # attentions, _act_image_version changes
                    _act_image_version = get_latest_entry(dev.act_image, $scope.struct.image_tree.lut, "name")
                    _class = if _act_image_version == resolve_version($scope.struct.image_tree.lut, dev.new_image, "name") then "" else "warning"
                else if _type == "k"
                    # kernel
                    act_kernel = if dev.act_kernel then dev.act_kernel[0] else null
                    if act_kernel
                        _act_kernel_version = "#{dev.act_kernel[1]}.#{dev.act_kernel[2]}"
                    else
                        _act_kernel_version = ""
                    _new_kernel_version = resolve_version($scope.struct.kernel_tree.lut, dev.new_kernel)
                    _out = get_info_str("k", act_kernel, _act_kernel_version, dev.new_kernel, _new_kernel_version)
                    if dev.act_kernel or dev.new_kernel
                        _out = "#{_out}, flavour is #{dev.stage1_flavour}"
                        if dev.kernel_append
                            _out = "#{_out} (append '#{dev.kernel_append}')"
                    _act_kernel_version = get_latest_entry(dev.act_kernel, $scope.struct.kernel_tree.lut, "name")
                    _class = if _act_kernel_version == resolve_version($scope.struct.kernel_tree.lut, dev.new_kernel, "display_name") then "" else "warning"
                else if _type == "p"
                    _out = get_info_str("p", dev.act_partition_table, "", dev.partition_table, "")
                    _class = if dev.act_partition_table == dev.partition_table then "" else "warning"
                else if _type == "b"
                    if dev.bootnetdevice
                        nd = dev.netdevice_lut[dev.bootnetdevice]
                        _out = "MAC of #{nd.devname} (driver #{nd.driver}) is"
                        if nd.macaddr
                            _out = "#{_out} #{nd.macaddr}"
                        else
                            _out = "#{_out} empty"
                        if dev.dhcp_write
                            _out = "#{_out}, write"
                        else
                            _out = "#{_out}, no write"
                        if dev.dhcp_mac
                            _out = "#{_out}, greedy"
                        if nd.macaddr
                            _class = ""
                        else
                            # empty mac, very strange
                            _class = "danger"
                    else
                        _out = "N/A"
                        _class = "warning"

                out_list.push(
                    {
                        html: _out
                        cls: _class
                    }
                )
        dev.$$boot_info_fields = out_list

    update_selection = () ->
        $scope.struct.num_selected = 0
        $scope.struct.num_selected_hc = 0
        for dev in $scope.struct.devices
            if dev.$$boot_selected
                $scope.struct.num_selected++
            if dev.$$boot_helper.slave_connections_valid and dev.$$boot_helper.slave_connections.length
                $scope.struct.num_selected_hc += dev.$$boot_helper.slave_connections.length

    # selection functions

    _cur_sel_timeout = undefined

    $scope.change_sel_filter = () ->
        if _cur_sel_timeout
            $timeout.cancel(_cur_sel_timeout)
        _cur_sel_timeout = $timeout($scope.set_sel_filter, 500)

    $scope.set_sel_filter = () ->
        try
            cur_re = new RegExp($scope.struct.device_sel_filter, "gi")
        catch exc
            cur_re = new RegExp("^$", "gi")
        for dev in $scope.struct.devices
            dev.$$boot_selected = if dev.full_name.match(cur_re) then true else false
            salt_device(dev)
        update_selection()

    $scope.toggle_dev_sel = (dev, sel_mode) ->
        if dev
            if sel_mode == 1
                dev.$$boot_selected = true
            else if sel_mode == -1
                dev.$$boot_selected = false
            else if sel_mode == 0
                dev.$$boot_selected = !dev.$$boot_selected
            salt_device(dev)
            update_selection()
        else
            for dev in $scope.struct.devices
                $scope.toggle_dev_sel(dev, sel_mode)

    # toggle columns and addons

    $scope.toggle_boot_option = (short) ->
        $scope.boot_options.toggle_enabled(short)
        salt_devices()

    $scope.change_devlog_flag = (dev) ->
        if dev.$$boot_helper.toggle_show_log()
            $scope.struct.boot_helper.fetch()

    $scope.toggle_show_mbl = () ->
        $scope.struct.show_mbl = !$scope.struct.show_mbl

    # soft / hard control
    
    $scope.soft_control = ($event, dev, command) ->
        if dev
            dev_pk_list = [dev.idx]
        else
            dev_pk_list = (dev.idx for dev in $scope.devices when dev.$$boot_selected)
        blockUI.start("Sending soft control command #{command}...")
        icswSimpleAjaxCall(
            url: ICSW_URLS.BOOT_SOFT_CONTROL
            data: {
                dev_pk_list: angular.toJson(dev_pk_list)
                command: command
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (error) ->
                blockUI.stop()
        )

    $scope.hard_control = ($event, cd_con, command) ->
        if cd_con
            cd_pk_list = [cd_con.idx]
        else
            cd_pk_list = []
            for dev in $scope.struct.devices
                if dev.selected and dev.slave_connections.length
                    for slave_con in dev.slave_connections
                        cd_pk_list.push(slave_con.idx)
        blockUI.start("Sending hard control command #{command}...")
        icswSimpleAjaxCall(
            url: ICSW_URLS.BOOT_HARD_CONTROL
            data: {
                cd_pk_list: angular.toJson(cd_pk_list)
                command: command
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (error) ->
                blockUI.stop()
        )

    # modify functions

    _prepare_post_data = (sub_scope) ->
        dev = sub_scope.edit_obj
        bs = sub_scope.$$bs
        # rewrite new_state / prod_link
        if bs.ts_mode == "s"
            dev.prod_link = null
            dev.new_state = bs.target_state.s
        else
            dev.prod_link = bs.ts_mode
            dev.new_state = bs.target_state[bs.ts_mode]
        # copy to special fields
        if dev.bootnetdevice
            _bn = dev.netdevice_lut[dev.bootnetdevice]
            _bn.driver = bs.driver
            _bn.macaddr = bs.macaddr
        dev.bn_driver = bs.driver
        dev.bn_macaddr = bs.macaddr

    create_subscope = () ->
        sub_scope = $scope.$new(true)

        sub_scope.stage1_flavours = [
            {val: "cpio", name: "CPIO"}
            {val: "cramfs", name: "CramFS"}
            {val: "lo", name: "ext2 via Loopback"}
        ]
        sub_scope.boot_options = $scope.boot_options
        sub_scope.struct = $scope.struct
        # create boot select entries, used to gather info from subelements
        sub_scope.$$bs = {
            ts_mode: "s"
            target_state: {}
            macaddr: ""
            driver: ""
            stage1_flavour: "cpio"
            new_kernel: null
            new_image: null
            kernel_append: ""
            partition_table: null
            dhcp_mac: false
            dhcp_write: false
            # flag: bootnetdevice present
            bn_present: false
            change: {
                "b": true
                "p": true
                "i": true
                "k": true
                "t": true
            }
        }
        if $scope.struct.kernel_tree.list.length
            sub_scope.$$bs.new_kernel = $scope.struct.kernel_tree.list[0].idx
        if $scope.struct.image_tree.list.length
            sub_scope.$$bs.new_image = $scope.struct.image_tree.list[0].idx
        if $scope.struct.partition_table_tree.list.length
            sub_scope.$$bs.partition_table = $scope.struct.partition_table_tree.list[0].idx
        # set default values
        sub_scope.$$bs.target_state.s = $scope.struct.boot_status_tree.special_states_list[0].status
        for net in $scope.struct.boot_status_tree.network_states_list
            sub_scope.$$bs.target_state[net.network] = net.states[0].status
        return sub_scope

    $scope.modify_many = ($event) ->
        sel_devices = (dev for dev in $scope.struct.devices when dev.$$boot_selected)
        return $scope.modify_devices($event, sel_devices)

    $scope.modify_one = ($event, dev) ->
        return $scope.modify_devices($event, [dev])

    $scope.modify_devices = ($event, devs) ->

        if devs.length == 1
            title = "Boot settings for device #{devs[0].full_name}"
        else
            title = "Boot settings for #{devs.length} devices"
        sub_scope = create_subscope()
        # set current value
        _bs = sub_scope.$$bs

        _bs.pk_list = (dev.idx for dev in devs)

        # copy settings from first (or only) device
        dev = devs[0]
        if not dev.target_state
            # first run, init with first special mode
            _bs.ts_mode = "s"
        else
            if dev.target_state of $scope.struct.boot_status_tree.special_states_lut
                _bs.ts_mode = "s"
                _bs.target_state.s = dev.target_state
            else
                _bs.ts_mode = dev.prod_link
                _bs.ts_mode[dev.prod_link] = dev.target_state
        if dev.stage1_flavour
            _bs.stage1_flavour = _.toLower(dev.stage1_flavour)
        if dev.bootnetdevice
            _bn = dev.netdevice_lut[dev.bootnetdevice]
            _bs.bn_present = true
            _bs.macaddr = _bn.macaddr
            _bs.driver = _bn.driver
        else
            _bs.bn_present = false
        if dev.new_kernel
            _bs.new_kernel = dev.new_kernel
        else if dev.act_kernel
            _bs.new_kernel = dev.act_kernel
        if dev.kernel_append
            _bs.kernel_append = dev.kernel_append
        if dev.new_image
            _bs.new_image = dev.new_image
        else if dev.act_image
            _bs.new_image = dev.act_image
        if dev.partition_table
            _bs.partition_table = dev.partition_table
        _bs.dhcp_write = dev.dhcp_write
        _bs.dhcp_mac = dev.dhcp_mac
        # sub_scope.edit_obj = dev

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.boot.modify.form"))(sub_scope)
                ok_label: "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    # _prepare_post_data(sub_scope)
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        _bs.bo_enabled = $scope.struct.boot_options.get_bo_enabled()
                        defer = $q.defer()
                        blockUI.start("Saving data...")
                        icswSimpleAjaxCall(
                            {
                                url: ICSW_URLS.BOOT_UPDATE_DEVICE
                                data: 
                                    boot:
                                        angular.toJson(_bs)
                            }
                        ).then(
                            (done) ->
                                # console.log result
                                $scope.struct.boot_helper.fetch().then(
                                    (done) ->
                                        d.resolve("done")
                                        blockUI.stop()
                                    (error) ->
                                        d.reject("error")
                                        blockUI.stop()
                                )
                            (error) ->
                                d.reject("not saved")
                                blockUI.stop()
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "boot.devices closed"
                sub_scope.$destroy()
        )

]).directive("icswDeviceBootRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.boot.row")
    }
]).directive("icswDeviceBootLogTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.boot.log.table")
        scope:
            device: "=icswDevice"
    }
]).directive("icswBootMacBootlogInfo",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.boot.mac.bootlog.info")
        controller: "icswBootMacBootlogCtrl"
        scope: false
    }
]).controller("icswBootMacBootlogCtrl",
[
    "$scope", "$timeout", "Restangular", "ICSW_URLS", "icswUserGroupTreeService", "blockUI",
    "icswSimpleAjaxCall", "$q", "icswDeviceTreeService",
(
    $scope, $timeout, Restangular, ICSW_URLS, icswUserGroupTreeService, blockUI,
    icswSimpleAjaxCall, $q, icswDeviceTreeService,
) ->
    $scope.struct = {
        # any macs loaded
        data_valid: false
        # device tree
        device_tree: undefined
        # is updating
        updating: false
        # macbootlog timeout
        timeout: undefined
        # entries 
        boot_list: []
        # entries to ignore
        ignore_list: []
        # unique macs
        unique_list: []
        # user tree
        user_group_tree: undefined
    }
    $scope.$on("$destroy", () ->
        if $scope.struct.timeout?
            $timeout.cancel($scope.struct.timeout)
        $scope.struct.timeout = undefined
    )

    # locals
    # mac dictionary
    mac_dict = {}

    # functions

    build_unique_list = () ->

        class MacEntry
            constructor: (@macaddr) ->
                @reset()

            reset: () =>
                @usecount = 0
                @ignore = false

            salt: () =>
                if @ignore
                    @ignore_str = "yes"
                else
                    @ignore_str = "no"

        # reset usecounts
        (_mbi.reset() for _mbi in _.values(mac_dict))

        for _entry in $scope.struct.ignore_list
            if _entry.macaddr not of mac_dict
                mac_dict[_entry.macaddr] = new MacEntry(_entry.macaddr)
            mac_dict[_entry.macaddr].ignore = true

        for _entry in $scope.struct.boot_list
            if _entry.macaddr.match(/^([a-fA-F\d][a-fA-F\d+]:){5}[a-fA-F\d]+$/)
                if _entry.macaddr not of mac_dict
                    mac_dict[_entry.macaddr] = new MacEntry(_entry.macaddr)

                # copy ignore flag
                _entry.ignore = mac_dict[_entry.macaddr].ignore

                mac_dict[_entry.macaddr].usecount++

        _d_lut = $scope.struct.device_tree.all_lut
        # salt bootlist
        for entry in $scope.struct.boot_list
            if entry.ignore? and entry.ignore
                entry.ignore_str = "yes"
            else
                entry.ignore_str = "---"
            if entry.device of _d_lut
                entry.device_name = _d_lut[entry.device].full_name
            else
                entry.device_name = "---"
            entry.created_str = moment(entry.date).format(DT_FORM)

        _keys = _.keys(mac_dict)
        _keys.sort()

        $scope.struct.unique_list.length = 0
        for entry in (mac_dict[_key] for _key in _keys)
            # salt ignorelist
            entry.salt()
            $scope.struct.unique_list.push(entry)

    update = () ->
        $scope.struct.updating = true
        $q.all(
            [
                Restangular.all(ICSW_URLS.REST_MACBOOTLOG_LIST.slice(1)).getList(
                    {
                        _num_entries: 50
                        _order_by: "-pk"
                    }
                )
                Restangular.all(ICSW_URLS.REST_MAC_IGNORE_LIST.slice(1)).getList(
                    {
                        _order_by: "-pk"
                    }
                )
                icswUserGroupTreeService.load($scope.$id)
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.data_valid = true
                $scope.struct.updating = false
                $scope.struct.boot_list.length = 0
                for entry in data[0]
                    $scope.struct.boot_list.push(entry)
                $scope.struct.ignore_list.length = 0
                for entry in data[1]
                    $scope.struct.ignore_list.push(entry)
                $scope.struct.user_group_tree = data[2]
                $scope.struct.device_tree = data[3]
                build_unique_list()
                $scope.struct.timeout = $timeout(update, 5000)
        )
        
    update()
    
    $scope.modify_mbl = ($event, mbl, action) ->
        if $scope.struct.timeout
            $timeout.cancel($scope.struct.timeout)

        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.BOOT_MODIFY_MBL
            dataType: "json"
            data: {
                mbl: angular.toJson(mbl)
                action: action
            }
        ).then(
            (result) ->
                update()
                blockUI.stop()
            (error) ->
                update()
                blockUI.stop()
        )

])
