# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

monitoring_device_module = angular.module(
    "icsw.schedule.device",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button", "angular-ladda",
        "icsw.device.asset.dynamic", "icsw.device.report", "icsw.device.asset.static",
        "icsw.setup.progress", "icsw.device.log"
    ]
).service("icswDispatcherSettingTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswAssetHelperFunctions",
(
    $q, Restangular, ICSW_URLS, icswAssetHelperFunctions,
) ->
    class icswDispatcherSettingTree
        constructor: (list, schedule_list, sched_item_list, @com_cap_tree) ->
            @list = []
            @schedule_list = []
            @sched_item_list = []
            @update(list, schedule_list, sched_item_list)

        update: (list, schedule_list, sched_item_list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @schedule_list.length = 0
            for entry in schedule_list
                @schedule_list.push(entry)
            @sched_item_list.length = 0
            for entry in sched_item_list
                @sched_item_list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @schedule_lut = _.keyBy(@schedule_list, "idx")
            @sched_item_lut = _.keyBy(@sched_item_list, "idx")
            @link()

        link: () =>
            DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @schedule_list
                _take = false
                for _se in _cf
                    if _take
                        entry["$$filter_#{_se}"] = true
                    else
                        entry["$$filter_#{_se}"] = false
                    if entry.name == _se
                        _take = true

            # beautify schedule_item planned
            for entry in @sched_item_list
                entry.$$planned_date = moment(entry.planned_date).format(DT_FORM)
                # console.log "*", entry.source, entry
                # entry.$$source = icswAssetHelperFunctions.resolve("schedule_source", entry.source)

            # create some simple links
            for entry in @list
                # create reference for all sched_items
                entry.$$sched_item_list = (_sched for _sched in @sched_item_list when _sched.dispatch_setting == entry.idx)
                # link run_schedule
                entry.$$run_schedule = @schedule_lut[entry.run_schedule]
                offset = ""
                _rs = entry.$$run_schedule
                # to be beautified
                if _rs.$$filter_second
                    offset = "#{entry.sched_start_second}"
                if _rs.$$filter_minute
                    offset = "#{entry.sched_start_minute}:#{offset}"
                if _rs.$$filter_hour
                    offset = "#{entry.sched_start_hour}:#{offset}"
                if _rs.$$filter_day
                    offset = "#{entry.sched_start_day} #{offset}"
                if _rs.$$filter_week
                    offset = "#{entry.sched_start_week} #{offset}"
                if _rs.$$filter_month
                    offset = "#{entry.sched_start_month} #{offset}"
                entry.$$start_offset = offset
                # create comcap list
                if entry.com_capabilities.length
                    entry.$$com_caps = (@com_cap_tree.lut[_cc].name for _cc in entry.com_capabilities).join(", ")
                else
                    if entry.is_system
                        entry.$$com_caps = "all"
                    else
                        entry.$$com_caps = "---"

        create_dispatcher_setting: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_DISPATCHER_SETTING_LIST.slice(1)).post(new_obj).then(
                (created) =>
                    @list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        save_dispatcher_setting: (save_obj) =>
            d = $q.defer()
            save_obj.put().then(
                (saved) =>
                    _.remove(@list, (entry) -> return entry.idx == save_obj.idx)
                    @list.push(save_obj)
                    @build_luts()
                    d.resolve(saved)
                (not_cr) =>
                    d.reject("not saved")
            )
            return d.promise

        delete_dispatcher_setting: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.REST_DISPATCHER_SETTING_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@list, (entry) -> return entry.idx == del_obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

]).service("icswDispatcherSettingTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswDispatcherSettingTree", "$rootScope", "ICSW_SIGNALS", "icswComCapabilityTreeService",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswDispatcherSettingTree, $rootScope, ICSW_SIGNALS, icswComCapabilityTreeService,
) ->
    rest_map = [
        [
            # setting list
            ICSW_URLS.REST_DISPATCHER_SETTING_LIST
            {}
        ]
        [
            # setting schedule list
            ICSW_URLS.REST_DISPATCHER_SETTING_SCHEDULE_LIST
            {}
        ]
        [
            # planned schedules
            ICSW_URLS.REST_SCHEDULE_ITEM_LIST
            {}
        ]
        #[
        #    # past assetruns
        #    ICSW_URLS.ASSET_GET_PAST_ASSETRUNS
        #    {}
        #]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswComCapabilityTreeService.load(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                if _result?
                    _result.update(data[0], data[1], data[2])
                else
                    console.log "*** dispatcher setting tree loaded ***"
                    _result = new icswDispatcherSettingTree(data[0], data[1], data[2], data[3])
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
        "load": (client) ->
            # loads from server
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            return load_data(client).promise
    }
]).service("icswComCapabilityTree",
[
    "$q",
(
    $q,
) ->
    class icswComCapabilityTree
        constructor: (list) ->
            @list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @link()

        link: () =>

]).service("icswComCapabilityTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswComCapabilityTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswComCapabilityTree, $rootScope, ICSW_SIGNALS
) ->
    rest_map = [
        [
            # setting list
            ICSW_URLS.REST_COM_CAPABILITY_LIST
            {}
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
                console.log "*** ComCapability tree loaded ***"
                if _result?
                    _result.update(data[0])
                else
                    _result = new icswComCapabilityTree(data[0])
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
        "load": (client) ->
            # loads from server
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            return load_data(client).promise
    }
]).directive('icswScheduleOverview',
[
    "ICSW_URLS", "Restangular",
(
    ICSW_URLS, Restangular
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.schedule.overview"
        controller: "icswScheduleOverviewCtrl"
    }
]).controller("icswScheduleOverviewCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringBasicTreeService", "icswComplexModalService",
    "$templateCache", "$compile", "icswDispatcherSettingBackup", "toaster", "blockUI", "Restangular",
    "ICSW_URLS", "icswConfigTreeService", "icswDispatcherSettingTreeService", "icswComCapabilityTreeService",
    "icswToolsSimpleModalService", "icswUserService", "icswUserGroupRoleTreeService",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringBasicTreeService, icswComplexModalService,
    $templateCache, $compile, icswDispatcherSettingBackup, toaster, blockUI, Restangular,
    ICSW_URLS, icswConfigTreeService, icswDispatcherSettingTreeService, icswComCapabilityTreeService,
    icswToolsSimpleModalService, icswUserService, icswUserGroupRoleTreeService,
) ->
    $scope.struct = {
        # loading
        loading: false
        # dispatch tree
        dispatch_tree: undefined
        # comcap tree
        com_cap_tree: undefined
        # user
        user: undefined
        # user and group tree
        user_group_tree: undefined
    }
    _load = () ->
        $scope.struct.loading = true
        $q.all(
            [
                icswDispatcherSettingTreeService.load($scope.$id)
                icswUserService.load($scope.id)
                icswUserGroupRoleTreeService.load($scope.$id)
                icswComCapabilityTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.dispatch_tree = data[0]
                $scope.struct.user = data[1].user
                $scope.struct.user_group_tree = data[2]
                $scope.struct.com_cap_tree = data[3]
                # get monitoring masters and slaves
                $scope.struct.loading = false
        )
    _load()

    $scope.delete = ($event, obj) ->
        icswToolsSimpleModalService("Really delete Schedule '#{obj.name}' ?").then(
            () =>
                blockUI.start("deleting...")
                $scope.struct.dispatch_tree.delete_dispatcher_setting(obj).then(
                    (ok) ->
                        console.log "schedule deleted"
                        blockUI.stop()
                    (notok) ->
                        blockUI.stop()
                )
        )

    $scope.create_or_edit = ($event, obj, create) ->
        if create
            obj = {
                name: "new schedule"
                description: "New schedule"
                mult: 1
                user: $scope.struct.user.idx
                is_system: false
                run_schedule: (entry.idx for entry in $scope.struct.dispatch_tree.schedule_list when entry.name == "week")[0]
                sched_start_second: 0
                sched_start_minute: 0
                sched_start_hour: 0
                sched_start_day: 0
                sched_start_week: 1
                sched_start_month: 1
                com_capabilities: []
            }
            _ok_label = "Create"
        else
            dbu = new icswDispatcherSettingBackup()
            dbu.create_backup(obj)
            _ok_label = "Modify"

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = obj
        # copy references
        sub_scope.dispatch_tree = $scope.struct.dispatch_tree
        sub_scope.com_cap_tree = $scope.struct.com_cap_tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.schedule.dispatch.setting.form"))(sub_scope)
                title: "Dispatcher Settings for #{sub_scope.edit_obj.name}"
                ok_label: _ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            blockUI.start("creating schedule ...")
                            $scope.struct.dispatch_tree.create_dispatcher_setting(sub_scope.edit_obj).then(
                                (new_obj) ->
                                    blockUI.stop()
                                    d.resolve("created")
                                (notok) ->
                                    blockUI.stop()
                                    d.reject("not created")
                            )
                        else
                            blockUI.start("saving schedule ...")
                            # hm, maybe not working ...
                            $scope.struct.dispatch_tree.save_dispatcher_setting(sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                $scope.struct.dispatch_tree.link()
                sub_scope.$destroy()
        )
]).directive('icswScheduleDevice',
[
    "ICSW_URLS", "Restangular",
(
    ICSW_URLS, Restangular
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.schedule.device"
        controller: "icswScheduleDeviceCtrl"
    }
]).controller("icswScheduleDeviceCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringBasicTreeService", "icswComplexModalService",
    "$templateCache", "$compile", "toaster", "blockUI", "Restangular",
    "ICSW_URLS", "icswConfigTreeService", "icswDispatcherSettingTreeService", "icswDeviceTreeHelperService",
    "icswUserService", "$http", "$timeout", "icswSimpleAjaxCall",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringBasicTreeService, icswComplexModalService,
    $templateCache, $compile, toaster, blockUI, Restangular,
    ICSW_URLS, icswConfigTreeService, icswDispatcherSettingTreeService, icswDeviceTreeHelperService,
    icswUserService, $http, $timeout, icswSimpleAjaxCall,
) ->
    $scope.struct = {
        # loading
        loading: false
        # device_tree
        device_tree: undefined
        # base monitoring tree
        base_tree: undefined
        # dispatch tree
        dispatcher_tree: undefined
        # devices
        devices: []
        # monitor servers
        monitor_servers: []
        # user
        user: undefined
        # reload timeout
        _reload_timeout: null
        # updating flag
    }
    $scope.new_devsel = (devs) ->
        stop_timeout()
        $scope.struct.loading = true
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswMonitoringBasicTreeService.load($scope.$id)
                icswConfigTreeService.load($scope.$id)
                icswDispatcherSettingTreeService.load($scope.$id)
                icswUserService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.base_tree = data[1]
                $scope.struct.dispatcher_tree = data[3]
                config_tree = data[2]
                $scope.struct.user = data[4].user
                # get monitoring masters and slaves
                $scope.struct.devices.length = 0
                for entry in devs
                    if not entry.is_meta_device
                        if not entry.isSelected?
                            entry.isSelected = false
                        $scope.struct.devices.push(entry)
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["dispatcher_info", "past_assetrun_info"]).then(
                    (done) ->
                        $scope.struct.device_tree.salt_dispatcher_infos($scope.struct.devices, $scope.struct.dispatcher_tree)
                        $scope.struct.loading = false
                        start_timeout()
                )
        )

    reload = () ->
        stop_timeout()
        $scope.struct.updating = true
        $q.all(
            [
                icswDispatcherSettingTreeService.reload($scope.$id)
            ]
        ).then(
            (data) ->
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["dispatcher_info", "past_assetrun_info"], true).then(
                    (done) ->
                        $scope.struct.device_tree.salt_dispatcher_infos($scope.struct.devices, $scope.struct.dispatcher_tree)
                        $scope.struct.updating = false
                        start_timeout()
                )
        )

    start_timeout = () ->
        stop_timeout()
        $scope.struct._reload_timeout = $timeout(
            () ->
                reload()
            10000
        )

    stop_timeout = () ->
        if $scope.struct._reload_timeout?
            $timeout.cancel($scope.struct._reload_timeout)
            $scope.struct._reload_timeout = null

    $scope.$on("$destroy", () ->
        stop_timeout()
    )

    $scope.run_now = ($event, device) ->
        $event.preventDefault()
        $event.stopPropagation()
        blockUI.start("Init AssetRun")
        icswUserService.load($scope.$id).then(
            (user_tree) ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.DISCOVERY_CREATE_SCHEDULE_ITEM
                        data:
                            model_name: "device"
                            object_id: device.idx
                            schedule_handler: "asset_schedule_handler"
                            schedule_handler_data: null
                            user_id: user_tree.user.idx
                        dataType: "json"
                    }
                ).then(
                    (result) ->
                        toaster.pop("success", "", "Dynamic asset scan of  '" + device.full_name + "' was successfully scheduled.")
                        if result.discovery_server_state > 0
                            toaster.pop("warning", "", "Could not contact discovery server.")
                        blockUI.stop()
                )
        )

    $scope.edit = ($event, obj) ->
        stop_timeout()
        if not obj?
            # selected
            _dev_list = (entry for entry in $scope.struct.devices when entry.isSelected)
            if not _dev_list.length
                return
            _title = "#{_dev_list.length} Devices"
        else
            _dev_list = [obj]
            _title = obj.full_name
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = {
            $$dispatchers: _.uniq(
                _.flatten(
                    _.union(
                        (disp.dispatcher_setting for disp in obj.dispatcher_set) for obj in _dev_list
                    )
                )
            )
        }
        sub_scope.dispatcher_tree = $scope.struct.dispatcher_tree
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.schedule.device.form"))(sub_scope)
                title: "Dispatcher Settings for #{_title}"
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        blockUI.start("changing dispatchers ....")
                        _w_list = (
                            $scope.struct.device_tree.sync_dispatcher_links(
                                obj
                                $scope.struct.dispatcher_tree
                                sub_scope.edit_obj.$$dispatchers
                                $scope.struct.user
                            ) for obj in _dev_list
                        )
                        $q.all(_w_list).then(
                            (done) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                $scope.struct.device_tree.salt_dispatcher_infos($scope.struct.devices, $scope.struct.dispatcher_tree)
                sub_scope.$destroy()
                start_timeout()
        )
]).directive("myUiSelect", () ->
    return {
        require: 'uiSelect'
        link: (scope, element, attrs, $select) ->
            console.log($select)
    }
)
