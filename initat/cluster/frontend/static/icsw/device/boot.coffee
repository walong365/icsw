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

class logline
    constructor: (line, log_source_lut, user_lut, log_level_lut) ->
        # format: pk, device_id, log_source_id, user_id, log_level_id, text, seconds
        @dt = line[6]
        @moment = moment.unix(@dt)
        @abs_dt = @moment.format(DT_FORM)
        @text = line[5]
        if line[2] of log_source_lut
            @source = log_source_lut[line[2]].description
        else
            @source = "---"
        if line[3] of user_lut
            @user = user_lut[line[3]].admin
        else
            @user = "---"
        if line[4] of log_level_lut
            @log_level = log_level_lut[line[4]].name
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

angular.module(
    "icsw.device.boot",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.deployboot", {
            url: "/deployboot"
            templateUrl: "icsw/main/deploy/boot.html"
            data:
                pageTitle: "Boot nodes"
                rights: ["device.change_boot"]
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
            _idx = 0
            @special_states_list.length = 0
            @network_states_list.length = 0
            # does not resolve to network_states_list but one level deeper
            @network_states_lut = {}
            for entry in @status_list
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
                                @network_states_lut[_idx] = new_state
            @special_states_lut = _.keyBy(@special_states_list, "idx")


            @build_luts()

        build_luts: () =>
            @status_lut = _.keyBy(@status_list, "idx")

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
]).service("icswDeviceBootHelper",
[
    "$q",
(
    $q,
) ->
    class icswDeviceBootHelper
        constructor: (@device, @g_helper) ->
            # g_helper ist the global boothelper
            # device logs
            @logs_set = false
            @logs = []
            @network = undefined
            @net_state = "down"
            @recvreq_state = "warning"
            @network_state = "warning"
            @recvreq_str = "---"

        feed: (data) =>
            console.log "feed", data
            if data.hoststatus_str
                @recvreq_str = data.hoststatus_str +  "(" + data.hoststatus_source + ")"
            else
                @recvreq_str = "rcv: ---"
            @net_state = data.net_state
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
                    _list = (_entry for _entry in st.special_states_list when _entry.status == dev.new_state)
                if _list.length
                    dev.target_state = _list[0].idx

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
            console.log "GlobalBootHelper, devices=",  @devices.length

        fetch: () =>
            new_timeout = () =>
                @fetch_timeout = $timeout(@fetch, 10000)

            defer = $q.defer()
            if @fetch_timeout
                $timeout.cancel(@fetch_timeout)
                @fetch_timeout = undefined
            if not @fetch_running
                @fetch_running = true
                send_data = {
                    sel_list: (dev.idx for dev in @devices)
                    call_mother: 1
                }
                icswSimpleAjaxCall(
                    url: ICSW_URLS.BOOT_GET_BOOT_INFO_JSON
                    data: send_data
                ).then(
                    (xml) =>
                        @fetch_running = false
                        @connection_problem_counter = 0
                        _resp = angular.fromJson($(xml).find("value[name='response']").text())
                        for entry in _resp
                            @device_lut[entry.idx].$$boot_helper.feed(entry)
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

]).controller("icswDeviceBootCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "ICSW_SIGNALS",
    "$q", "icswAcessLevelService", "$timeout", "$rootScope",
    "icswTools", "ICSW_URLS", "icswSimpleAjaxCall", "icswDeviceTreeService",
    "icswActiveSelectionService", "icswConfigTreeService", "icswLogTreeService",
    "icswKernelTreeService", "icswImageTreeService", "icswUserGroupTreeService",
    "icswPartitionTableTreeService", "icswNetworkTreeService", "icswBootStatusTreeService",
    "icswGlobalBootHelper", "icswDeviceTreeHelperService",
(
    $scope, $compile, $filter, $templateCache, Restangular, ICSW_SIGNALS,
    $q, icswAcessLevelService, $timeout, $rootScope,
    icswTools, ICSW_URLS, icswSimpleAjaxCall, icswDeviceTreeService,
    icswActiveSelectionService, icswConfigTreeService, icswLogTreeService,
    icswKernelTreeService, icswImageTreeService, icswUserGroupTreeService,
    icswPartitionTableTreeService, icswNetworkTreeService, icswBootStatusTreeService,
    icswGlobalBootHelper, icswDeviceTreeHelperService,
) ->
    icswAcessLevelService.install($scope)
    $scope.mbl_entries = []
    $scope.num_selected = 0
    $scope.bootserver_list = []
    $scope.any_type_1_selected = false
    $scope.any_type_2_selected = false
    $scope.any_type_3_selected = false
    # dict of all macs
    $scope.mac_dict = {}

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
    $scope.type_1_options = (entry for entry in $scope.boot_options when entry[2] == 1)

    $scope.stage1_flavours = [
        {val: "cpio", name: "CPIO"}
        {val: "cramfs", name: "CramFS"}
        {val: "lo", name: "ext2 via Loopback"}
    ]

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
        # device selection strings
        device_sel_filter: ""
        # boot helper structur
        boot_helper: undefined
    }
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
                        console.log result
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
        for opt in $scope.type_1_options
            _type = opt[0]
            if $scope.bo_enabled[_type]
                # default values
                [_out, _class] = ["N/A", "danger"]
                if _type == "t"
                    # target state
                    _class = ""
                    if dev.target_state
                        _out = $scope.struct.boot_status_tree.network_states_lut[dev.target_state].full_info
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
                    console.log _type, dev
                    if dev.bootnetdevice
                        nd = dev.bootnetdevice
                        console.log "nd=", nd

                out_list.push(
                    {
                        html: _out
                        cls: _class
                    }
                )
        dev.$$boot_info_fields = out_list



    update_selection = () ->
        $scope.struct.num_selected = 0
        for dev in $scope.struct.devices
            if dev.$$boot_selected
                $scope.struct.num_selected++

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

    # toggle columns

    $scope.toggle_boot_option = (short) ->
        $scope.bo_enabled[short] = ! $scope.bo_enabled[short]
        $scope.any_type_1_selected = if (entry for entry in $scope.boot_options when entry[2] == 1 and $scope.bo_enabled[entry[0]] == true).length then true else false
        $scope.any_type_2_selected = if (entry for entry in $scope.boot_options when entry[2] == 2 and $scope.bo_enabled[entry[0]] == true).length then true else false
        $scope.any_type_3_selected = if (entry for entry in $scope.boot_options when entry[2] == 3 and $scope.bo_enabled[entry[0]] == true).length then true else false
        salt_devices()

    $scope.get_devlog_class = (dev) ->
        if dev.show_log
            return "btn btn-xs btn-success"
        else
            return "btn btn-xs"
    $scope.get_devlog_value = (dev) ->
        return if dev.show_log then "hide" else "show"

    $scope.change_devlog_flag = (dev) ->
        dev.show_log = !dev.show_log


    $scope.bo_enabled = {}

    for entry in $scope.boot_options
        $scope.bo_enabled[entry[0]] = false
    $scope.get_bo_class = (short) ->
        return (if $scope.bo_enabled[short] then "btn btn-sm btn-success" else "btn btn-sm")

    $scope.num_selected_hc = () ->
        num_hc = 0
        for dev in $scope.devices
            if dev.selected and dev.slave_connections and dev.slave_connections.length
                num_hc += dev.slave_connections.length
        return num_hc
    # mixins
    $scope.device_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q)
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
    $scope.reload = () ->
        wait_list = [
            # restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_network" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_boot"}]),
            # 1
            # restDataSource.reload([ICSW_URLS.REST_KERNEL_LIST, {}]),
            # restDataSource.reload([ICSW_URLS.REST_IMAGE_LIST, {}])
            # restDataSource.reload([ICSW_URLS.REST_PARTITION_TABLE_LIST, {}])
            # 4
            # restDataSource.reload([ICSW_URLS.REST_STATUS_LIST, {}])
            # restDataSource.reload([ICSW_URLS.REST_NETWORK_LIST, {}])
            # 6
            # restDataSource.reload([ICSW_URLS.REST_LOG_SOURCE_LIST, {}])
            # restDataSource.reload([ICSW_URLS.REST_LOG_LEVEL_LIST, {}])
            # 8
            # restDataSource.reload([ICSW_URLS.REST_USER_LIST, {}])
            # restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"all_mother_servers" : true}])
        ]
        $q.all(wait_list).then((data) ->
            $scope.devices = (dev for dev in data[0])
            $scope.num_selected = 0
            for dev in $scope.devices
                dev.show_log = false
                dev.selected = false
                dev.num_show = 5
                dev.recvreq_str = "waiting"
                dev.recvreq_state = "warning"
                dev.network = "waiting"
                dev.network_state = "warning"
                dev.latest_log = 0
                dev.num_logs = "?"
                dev.logs_set = false
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
                # restDataSource.reload([ICSW_URLS.REST_KERNEL_LIST, {}]),
                # restDataSource.reload([ICSW_URLS.REST_IMAGE_LIST, {}])
                # restDataSource.reload([ICSW_URLS.REST_PARTITION_TABLE_LIST, {}])
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
                icswSimpleAjaxCall(
                    url     : ICSW_URLS.BOOT_GET_BOOT_INFO_JSON
                    data    : send_data
                ).then(
                    (xml) ->
                        $scope.update_info_timeout = $timeout($scope.update_info, 10000)
                        $scope.conn_problems = 0
                        $scope.info_ok = true
                        _resp = angular.fromJson($(xml).find("value[name='response']").text())
                        for entry in _resp
                            dev = $scope.device_lut[entry.idx]
                            # copied from bootcontrol, seems strange to me now ...
                            if entry.hoststatus_str
                                 dev.recvreq_str = entry.hoststatus_str +  "(" + entry.hoststatus_source + ")"
                            else
                                 dev.recvreq_str = "rcv: ---"
                            net_state = entry.net_state
                            tr_class = {"down" : "danger", "unknown" : "warning", "ping" : "warning", "up" : "success"}[net_state]
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
                    (xml) ->
                        $scope.update_info_timeout = $timeout($scope.update_info, 10000)
                        $scope.conn_problems++
                )
            )
            if $scope.bo_enabled["l"]
                send_data = {
                    "sel_list" : angular.toJson(([dev.idx, dev.latest_log] for dev in $scope.devices))
                }
                icswSimpleAjaxCall(
                    url      : ICSW_URLS.BOOT_GET_DEVLOG_INFO
                    data     : send_data
                    dataType : "json"
                ).then((json) ->
                    if json.dev_logs
                        for dev_id of json.dev_logs
                            cur_dev = $scope.device_lut[dev_id]
                            json_dev = json.dev_logs[dev_id]
                            cur_dev.num_logs = json_dev["total"]
                            cur_dev.logs_set = true
                            for line in json_dev["lines"]
                                # format: pk, device_id, log_source_id, user_id, log_level_id, text, seconds
                                cur_dev.latest_log = Math.max(line[0], cur_dev.latest_log)
                                new_line = new logline(line, $scope.log_source_lut, $scope.user_lut, $scope.log_level_lut)
                                cur_dev.log_lines.splice(0, 0, new_line)
                )
    $scope.soft_control = (dev, command) ->
        if dev
            dev_pk_list = [dev.idx]
        else
            dev_pk_list = (dev.idx for dev in $scope.devices when dev.selected)
        icswSimpleAjaxCall(
            url     : ICSW_URLS.BOOT_SOFT_CONTROL
            data    : {
                "dev_pk_list" : angular.toJson(dev_pk_list)
                "command"     : command
            }
        ).then((xml) ->
        )
    $scope.hard_control = (cd_con, command) ->
        if cd_con
            cd_pk_list = [cd_con.idx]
        else
            cd_pk_list = []
            for dev in $scope.devices
                if dev.selected and dev.slave_connections.length
                    for slave_con in dev.slave_connections
                        cd_pk_list.push(slave_con.idx)
        icswSimpleAjaxCall(
            url     : ICSW_URLS.BOOT_HARD_CONTROL
            data    : {
                "cd_pk_list" : angular.toJson(cd_pk_list)
                "command"    : command
            }
        ).then((xml) ->
        )
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
        $q.all(
            [
                Restangular.all(ICSW_URLS.REST_MACBOOTLOG_LIST.slice(1)).getList({"_num_entries" : 50, "_order_by" : "-pk"}),
                Restangular.all(ICSW_URLS.REST_MAC_IGNORE_LIST.slice(1)).getList({"_order_by" : "-pk"}),
            ]
        ).then(
            (data) ->
                $scope.mbl_entries = data[0]
                $scope.mbi_entries = data[1]
                $scope.check_mbl()
                $scope.mbl_timeout = $timeout($scope.fetch_macbootlog_entries, 5000)
        )
    $scope.modify_mbl = (mbl, action) ->
        if $scope.mbl_timeout
            $timeout.cancel($scope.mbl_timeout)
        icswSimpleAjaxCall(
            "url": ICSW_URLS.BOOT_MODIFY_MBL,
            "dataType": "json"
            "data": {
                "mbl": angular.toJson(mbl)
                "action": action
            }
        ).then(
            (result) ->
                mbl.ignore = !mbl.ignore
                for _entry in $scope.mbl_entries
                    if _entry.macaddr == mbl.macaddr
                        _entry.ignore = mbl.ignore
        )
        $scope.fetch_macbootlog_entries()
    $scope.get_mac_ignored = (mbl) ->
        return if mbl.ignore then "yes" else "---"
    $scope.check_mbl = () ->
        class mbi_entry
            constructor: (@macaddr, @ignore) ->
                @usecount = 0
        # reset usecounts
        for _mbi in _.values($scope.mac_dict)
            _mbi.usecount = 0
        for _entry in $scope.mbi_entries
            if _entry.macaddr not of $scope.mac_dict
                $scope.mac_dict[_entry.macaddr] = new mbi_entry(_entry.macaddr, true)
            $scope.mac_dict[_entry.macaddr].ignore = true
        for _entry in $scope.mbl_entries
            if _entry.macaddr.match(/^([a-fA-F\d][a-fA-F\d+]:){5}[a-fA-F\d]+$/)
                if _entry.macaddr not of $scope.mac_dict
                    $scope.mac_dict[_entry.macaddr] = new mbi_entry(_entry.macaddr, false)
                _entry.ignore = $scope.mac_dict[_entry.macaddr].ignore
                $scope.mac_dict[_entry.macaddr].usecount++
        _keys = _.keys($scope.mac_dict)
        _keys.sort()
        $scope.mbi_list = ($scope.mac_dict[_key] for _key in _keys)
    $scope.get_mbl_created = (mbl) ->
        return moment.unix(mbl.created).format(DT_FORM)
]).directive("icswDeviceBootRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.boot.row")
        link: (scope, el, attrs) ->
            _resolve_i_lut_name = (entry, lut) ->
                if entry of lut
                    return lut[entry].name
                else
                    return null
            _resolve_k_lut_name = (entry, lut) ->
                if entry of lut
                    return lut[entry].display_name
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
                        _cls = scope._get_td_class(_get_latest_entry(dev.act_image, scope.image_lut, "name"), _resolve_i_lut_name(dev.new_image, scope.image_lut))
                    else if entry[0] == "p"
                        _cls = scope._get_td_class(dev.act_partition_table, dev.partition_table)
                    else if entry[0] == "k"
                        _cls = scope._get_td_class(_get_latest_entry(dev.act_kernel, scope.kernel_lut, "name"), _resolve_k_lut_name(dev.new_kernel, scope.kernel_lut))
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
                    if s_type == "k"
                        return lut[val].display_name
                    else
                        return lut[val].name
                else
                    return "? #{s_type}: #{val} ?"
            scope.get_info_str = (s_type, act_val, act_vers, new_val, new_vers, lut) ->
                if act_val == new_val
                    if act_val
                        if act_vers == new_vers
                            # everything ok, same version
                            if act_vers
                                return "<span class='label label-success'><span class='glyphicon glyphicon-ok'></span></span> " + scope.get_lut_val(s_type, lut, act_val) + " (#{act_vers})"
                            else
                                return "<span class='label label-success'><span class='glyphicon glyphicon-ok'></span></span> " + scope.get_lut_val(s_type, lut, act_val)
                        else
                            return "<span class='label label-warning'><span class='glyphicon glyphicon-arrow-up'></span></span> " + scope.get_lut_val(s_type, lut, act_val) + " (#{act_vers} != #{new_vers})"
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
])
