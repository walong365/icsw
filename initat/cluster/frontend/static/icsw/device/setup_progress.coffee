# Copyright (C) 2016 init.at
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

# variable related module

setup_progress = angular.module(
    "icsw.setup.progress",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.setupprogress")
]).directive("icswSetupProgress",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.setup.progress")
        controller: "icswSetupProgressCtrl"
        scope: true
    }
]).controller("icswSetupProgressCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI", "icswWebSocketService"
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions", "FileUploader"
    "icswDeviceTreeService", "$timeout", "DeviceOverviewService", "icswUserGroupRoleTreeService",
    "icswToolsSimpleModalService", "SetupProgressHelper", "ICSW_SIGNALS", "$rootScope", "toaster", "icswCSRFService"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI, icswWebSocketService
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions, FileUploader
    icswDeviceTreeService, $timeout, DeviceOverviewService, icswUserGroupRoleTreeService,
    icswToolsSimpleModalService, SetupProgressHelper, ICSW_SIGNALS, $rootScope, toaster, icswCSRFService
) ->
    $scope.struct = {
        # selected devices
        devices: []
        device_pks: []
        # device tree
        device_tree: undefined
        ugr_tree: undefined
        data_loaded: false

        devices: []
        device_ids_needing_refresh: []

        tabs: []

        reload_timer: undefined

        active_tab_index: 0

        system_completion: 0

        show_extended_information_button_value: "Off"
        show_extended_information_button_class: "btn btn-default"
        show_extended_information_button_enabled: false

        tasks: []

        device_task_headers: []

        push_graphing_config_device: undefined

        local_hm_module_fingerprint: "N/A"
        local_linux_version: "N/A"
        local_windows_version: "N/A"

        update_file_version: undefined
        update_file_platform_bits: undefined
        update_file_module_fingerprint: undefined

        hm_status_websocket: undefined

        host_monitor_refresh_button_counter: 10
        host_monitor_refresh_button_text: "Refresh (10)"
        host_monitor_refresh_button_timeout: undefined
    }

    ws_handle_func = (data) ->
        device = $scope.struct.device_tree.all_lut[data.device_pk]
        result_type = data.command
        result = data.result

        # salt devices with values
        if result
            if result_type == "version"
                device.$$host_monitor_version = result
            else if result_type == "platform"
                device.$$host_monitor_platform = result
                device.$$host_monitor_platform_bits = data.platform_bits
            else if result_type == "modules_fingerprint"
                device.$$host_monitor_fingerprint = result
            else if result_type == "full_update_status"
                if result == -1
                    toaster.pop("error", "", "Full update of device '" + device.full_name + "' failed with: " + data.error_string)
                else
                    toaster.pop("success", "", "Full update of device '" + device.full_name + "' done!")
                    device.$$host_monitor_fingerprint = data.update_file_checksum
                    device.$$host_monitor_version = data.update_file_version
                    device.$$host_monitor_platform = data.update_file_platform
                    device.$$host_monitor_platform_bits = data.update_file_platform_bits

        # salt devices with color information
        if device.$$host_monitor_version == $scope.struct.local_linux_version || device.$$host_monitor_version == $scope.struct.local_windows_version
            device.$$host_monitor_version_class = "alert-success"
        else
            device.$$host_monitor_version_class = "alert-danger"

        if $scope.struct.local_hm_module_fingerprint == device.$$host_monitor_fingerprint
            device.$$host_monitor_fingerprint_class = "alert-success"
        else
            device.$$host_monitor_fingerprint_class = "alert-danger"


        # enable/disable buttons
        if device.$$host_monitor_version != "N/A" && device.$$host_monitor_platform != "N/A" && device.$$host_monitor_fingerprint != "N/A"
            maj_device = parseInt(device.$$host_monitor_version.split(".")[0])
            min_device = parseInt(device.$$host_monitor_version.split(".")[1].split("-")[0])
            rel_device = parseInt(device.$$host_monitor_version.split(".")[1].split("-")[1])

            if device.$$host_monitor_platform == "WINDOWS"
                version_str = $scope.struct.local_windows_version
            else if device.$$host_monitor_platform == "LINUX"
                version_str = $scope.struct.local_linux_version

            maj_local = parseInt(version_str.split(".")[0])
            min_local = parseInt(version_str.split(".")[1].split("-")[0])
            rel_local = parseInt(version_str.split(".")[1].split("-")[1])

            if maj_local >= maj_device && min_local >= min_device && rel_local >= rel_device && $scope.struct.local_hm_module_fingerprint != device.$$host_monitor_fingerprint
                device.$$update_modules_disabled = false

        if $scope.struct.update_file_version != undefined && $scope.struct.update_file_module_fingerprint != undefined && $scope.struct.update_file_platform_bits != undefined
            if device.$$host_monitor_platform == "WINDOWS" && device.$$host_monitor_platform_bits == $scope.struct.update_file_platform_bits
                device.$$hm_full_update_disabled = false

        $timeout(angular.noop)

    icswWebSocketService.get_ws("hm_status", ws_handle_func).then(
        (ws) ->
            $scope.struct.websocket = ws
    )

    $scope.update_modules = (device) ->
        icswToolsSimpleModalService("WARNING: This process might fail if there is a large mismatch between the local and client version!").then(
            (ok) ->
                device.$$update_modules_disabled = true
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.DISCOVERY_CREATE_SCHEDULE_ITEM
                        data:
                            schedule_handler: "hostmonitor_update_modules_handler"
                            schedule_handler_data: "" + device.idx
                        dataType: "json"
                    }
                ).then(
                    (result) ->
                        toaster.pop("success", "", "Module update of device '" + device.full_name + "' was successfully scheduled.")
                        if result.discovery_server_state > 0
                            toaster.pop("warning", "", "Could not contact discovery server.")
                )
        )

    push_graphing_config = (_yes) ->
        blockUI.start("Please wait...")
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_SIMPLE_GRAPH_SETUP
                data:
                    device_pk: $scope.struct.push_graphing_config_device.idx
                dataType: "json"
            }
        ).then(
            (data) ->
                $scope.struct.device_ids_needing_refresh.push($scope.struct.push_graphing_config_device.idx)
                perform_refresh_for_device_status(true)
                blockUI.stop()

                if data == true
                    toaster.pop("success", "", "Graphing initialized for [" + $scope.struct.push_graphing_config_device.full_name + "]")
                else
                    toaster.pop("error", "", "Failed to initialize graphing for [" + $scope.struct.push_graphing_config_device.full_name + "]")

        )

    start_timer = (refresh_time) ->
        stop_timer()
        $scope.struct.reload_timer = $timeout(
            () ->
                perform_refresh_for_device_status(true)
            refresh_time
        )

    stop_timer = () ->
        # check if present and stop timer
        if $scope.struct.reload_timer?
            $timeout.cancel($scope.struct.reload_timer)
            $scope.struct.reload_timer = undefined

    $scope.new_devsel = (devs) ->
        $scope.struct.devices.length = 0
        $scope.struct.device_pks.length = 0
        for entry in devs
            if not entry.is_meta_device
                $scope.struct.devices.push(entry)
                $scope.struct.device_pks.push(entry.idx)

        perform_refresh_for_device_status(false)
        perform_refresh_for_system_status()
        schedule_refresh_for_host_monitor_status()

    perform_refresh_for_device_status = (partial_refresh) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswUserGroupRoleTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.ugr_tree = data[1]

                if partial_refresh
                    device_id_list = (idx for idx in $scope.struct.device_ids_needing_refresh)
                else
                    device_id_list = (device.idx for device in $scope.struct.devices)

                if device_id_list.length > 0
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.DEVICE_DEVICE_COMPLETION
                            data:
                                device_pks: device_id_list
                            dataType: "json"
                        }
                    ).then(
                        (data) ->
                            $scope.struct.device_ids_needing_refresh.length = 0

                            for device_id in device_id_list
                                device = $scope.struct.device_tree.all_lut[device_id]

                                salt_device(device, data[device.idx])

                            $scope.struct.data_loaded = true
                            if $scope.struct.device_ids_needing_refresh.length > 0
                                start_timer(15000)
                    )
                else
                    $scope.struct.data_loaded = true
        )

    perform_refresh_for_system_status = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_SYSTEM_COMPLETION
                dataType: "json"
            }
        ).then(
            (data) ->
                $scope.struct.system_completion = data.overview.completed
        )

    salt_device = (device, tasks) ->
        device.$$date_created = moment(device.date).format("YYYY-MM-DD HH:mm:ss")
        if device.creator
            device.$$creator = $scope.struct.ugr_tree.user_lut[device.creator].$$long_name
        else
            device.$$creator = "N/A"

        device.$$device_tasks = tasks

        device.$$overview_completion_percentage = 0

        available_points = 0
        fulfilled_points = 0
        for task in tasks
            available_points += task.points
            if task.fulfilled == true || task.ignore == true
                fulfilled_points += task.points

            if task.refresh == true
                $scope.struct.device_ids_needing_refresh.push(device.idx)

            found = false
            for obj in $scope.struct.device_task_headers
                header = obj[0]
                name = obj[1]

                if header == task.header && name == task.name
                    found = true

            if !found
                $scope.struct.device_task_headers.push([task.header, task.name])

            device["device_status_sort_hint_" + task.name] = task.fulfilled == true || task.ignore == true

        device.$$overview_completion_percentage = Math.round((fulfilled_points / available_points) * 100)

    $scope.open_in_new_tab_for_devices = (task, device, force_open) ->
        if force_open == undefined
            force_open = false
        setup_type = task.setup_type
        heading = task.header

        if setup_type == 3
            if !force_open
                if task.fulfilled != true
                    $scope.struct.push_graphing_config_device = device
                    icswToolsSimpleModalService("Enable graphing for this device? [Requires installed host-monitoring]").then(
                        push_graphing_config
                        (_no) ->
                            console.log("no")
                    )
                    return
                else if task.rrd_age_in_seconds != undefined && task.rrd_age_in_seconds > (60 * 60)
                    $scope.struct.push_graphing_config_device = device
                    icswToolsSimpleModalService("Stale/Old Graphing Data Found. Try to re-enable graphing?").then(
                        push_graphing_config
                        (_no) ->
                            $scope.open_in_new_tab_for_devices(task, device, true)
                    )
                    return

        o = {
            global: false
            type: setup_type
            heading: heading + " (" + device.name + ")"
            device_id: device.idx
        }

        for tab in $scope.struct.tabs
            if tab.device_id == o.device_id && tab.heading == o.heading
                return

        $scope.struct.tabs.push(o)
        $timeout(
            () ->
                $scope.struct.active_tab_index = $scope.struct.tabs.length + 2
            0
        )

    $scope.open_in_new_tab_for_system = (task) ->
        heading = task.header

        o = {
            global: true
            task: task
            heading: heading
        }

        if task.name == "devices"
            if task.fulfilled
                o.devices_available = true
                o.heading = "Device Tree"
            else
                o.devices_available = false
                o.heading = "Create new Device"

        for tab in $scope.struct.tabs
            if tab.heading == o.heading
                return

        $scope.struct.tabs.push(o)
        $timeout(
            () ->
                $scope.struct.active_tab_index = $scope.struct.tabs.length + 2
            0
        )

    $scope.close_tab = (to_be_closed_tab) ->
        $timeout(
            () ->
                _.remove($scope.struct.tabs, (el) -> return el.type == to_be_closed_tab.type)
                if $scope.struct.tabs.length == 0
                    perform_refresh_for_device_status(true)
            0
        )

    $scope.mark_unfresh = (tab) ->
        if tab["device_id"] != undefined
            $scope.struct.device_ids_needing_refresh.push(tab.device_id)

    $scope.show_device = ($event, dev) ->
        DeviceOverviewService($event, [dev])

    $scope.system_overview_tab_clicked = () ->
        perform_refresh_for_system_status()

    $scope.device_overview_tab_clicked = () ->
        perform_refresh_for_device_status(true)

    $scope.setup_tasks_tab_clicked = () ->
        setup_tasks()

    $scope.show_extended_information_button_pressed = () ->
        $scope.struct.show_extended_information_button_enabled = !$scope.struct.show_extended_information_button_enabled

        if $scope.struct.show_extended_information_button_enabled
            $scope.struct.show_extended_information_button_value = "On"
            $scope.struct.show_extended_information_button_class = "btn btn-success"
        else
            $scope.struct.show_extended_information_button_value = "Off"
            $scope.struct.show_extended_information_button_class = "btn btn-default"

        for device in $scope.struct.devices
            device.$$device_status_show_details = $scope.struct.show_extended_information_button_enabled

    setup_tasks = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_SYSTEM_COMPLETION
                dataType: "json"
            }
        ).then(
            (data) ->
                $scope.struct.tasks.length = 0

                for _result in data.list
                    $scope.struct.tasks.push(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_OPEN_SETUP_TASKS_CHANGED"))
        )

    setup_tasks()

    $scope.$on("$destroy", () ->
        if $scope.struct.hm_status_websocket?
            $scope.struct.hm_status_websocket.close()
            $scope.struct.hm_status_websocket = undefined

        $rootScope.$emit(ICSW_SIGNALS("ICSW_OPEN_SETUP_TASKS_CHANGED"))
        stop_timer()
    )

    $scope.ignore_issue = (task) ->
        blockUI.start("Please wait...")
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_SYSTEM_COMPLETION_IGNORE_TOGGLE
                data:
                    system_component_name: task.name
                dataType: "json"
            }
        ).then(
            (data) ->
                setup_tasks()
                blockUI.stop()
        )

    $scope.ignore_device_issue = (task, device) ->
        blockUI.start("Please wait...")
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_DEVICE_TASK_IGNORE_TOGGLE
                data:
                    device_component_name: task.name
                    device_pk: device.idx
                dataType: "json"
            }
        ).then(
            (data) ->
                $scope.struct.device_ids_needing_refresh.push(device.idx)
                perform_refresh_for_device_status(true)
                blockUI.stop()
        )

    $scope.device_status_show_details = (obj) ->
        if obj.$$device_status_show_details == undefined
            obj.$$device_status_show_details = true
        else
            obj.$$device_status_show_details = !obj.$$device_status_show_details

    # implement special action for tasks here
    $scope.perform_special_action = (task, device) ->
        if task.setup_type == 3
            $scope.struct.push_graphing_config_device = device
            icswToolsSimpleModalService("Push graphing settings for this device? [Requires installed host-monitoring]").then(
                push_graphing_config
                (_no) ->
                    console.log("no")
            )

    $scope.show_device = ($event, dev) ->
        DeviceOverviewService($event, [dev])

    $scope.upload_percentage = 0
    $scope.uploading = false
    $scope.getPercentage = () ->
        return $scope.upload_percentage

    $scope.uploader = new FileUploader(
            url: ICSW_URLS.DISCOVERY_UPLOAD_UPDATE_FILE
            scope: $scope
            queueLimit: 1
            alias: "update_file"
            removeAfterUpload: true
            autoUpload: true
        )

    $scope.uploader.onCompleteAll = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DISCOVERY_UPDATE_FILE_HANDLER
                data:
                    command: "status"
                dataType: "json"
            }
        ).then(
            (data) ->
                if data.update_file_version && data.update_file_checksum && data.update_file_platform_bits
                    $scope.struct.update_file_version = data.update_file_version
                    $scope.struct.update_file_module_fingerprint = data.update_file_checksum
                    $scope.struct.update_file_platform_bits = data.update_file_platform_bits

                    for device in $scope.struct.devices
                        if device.$$host_monitor_platform == "WINDOWS" && device.$$host_monitor_platform_bits == $scope.struct.update_file_platform_bits
                            device.$$hm_full_update_disabled = false
        )
        angular.element("input[type='file']").val(null);
        $scope.upload_percentage = 0
        $scope.uploading = false

    $scope.uploader.onBeforeUploadItem = (item) ->
        for device in $scope.struct.devices
            device.$$hm_full_update_disabled = true

    $scope.uploader.onProgressAll = (progress) ->
        $scope.upload_percentage = progress
        $scope.uploading = true

    icswCSRFService.get_token().then(
        (token) ->
            $scope.uploader.formData.push({"csrfmiddlewaretoken": token})
    )

    $scope.perform_full_update = (device) ->
        device.$$update_modules_disabled = true
        device.$$hm_full_update_disabled = true
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DISCOVERY_UPDATE_FILE_HANDLER
                data:
                    command: "perform_update"
                    device_ids: [device.idx]
                dataType: "json"
            }
        ).then(
            (result) ->
                toaster.pop("success", "", "Full update of device '" + device.full_name + "' was successfully scheduled.")
                if result.discovery_server_state > 0
                    toaster.pop("warning", "", "Could not contact discovery server.")
        )

    $scope.perform_host_monitor_status_refresh = () ->
        schedule_refresh_for_host_monitor_status()

    schedule_refresh_for_host_monitor_status = () ->
        if $scope.struct.host_monitor_refresh_button_timeout != undefined
            $scope.struct.host_monitor_refresh_button_timeout.cancel()
        $scope.struct.host_monitor_refresh_button_counter = 10
        $scope.struct.host_monitor_refresh_button_text = "Refresh (10)"

        for device in $scope.struct.devices
            device.$$host_monitor_version = "N/A"
            device.$$host_monitor_version_class = ""
            device.$$host_monitor_platform = "N/A"
            device.$$host_monitor_fingerprint = "N/A"
            device.$$host_monitor_fingerprint_class = ""
            device.$$host_monitor_platform_bits = "N/A"
            device.$$update_modules_disabled = true
            device.$$hm_full_update_disabled = true

        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DISCOVERY_HOST_MONITORING_STATUS_LOADER
                data:
                    device_pks: $scope.struct.device_pks
                dataType: "json"
            }
        ).then(
            (data) ->
                $scope.struct.local_hm_module_fingerprint = data.checksum
                $scope.struct.local_linux_version = data.linux_version
                $scope.struct.local_windows_version = data.windows_version

                schedule_handler_payload = "["
                for pk in $scope.struct.device_pks
                    schedule_handler_payload += pk + ","
                schedule_handler_payload += "]"

                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.DISCOVERY_CREATE_SCHEDULE_ITEM
                        data:
                            schedule_handler: "hostmonitor_status_schedule_handler"
                            schedule_handler_data: schedule_handler_payload
                        dataType: "json"
                    }
                ).then(
                    (result) ->
                        if result.discovery_server_state > 0
                            toaster.pop("warning", "", "Could not contact discovery server.")
                )

                decrease_refresh_button_counter = () ->
                    $scope.struct.host_monitor_refresh_button_timeout = $timeout(
                        () ->
                            if $scope.struct.host_monitor_refresh_button_counter > 0
                                $scope.struct.host_monitor_refresh_button_text = "Refresh (" + $scope.struct.host_monitor_refresh_button_counter + ")"
                                $scope.struct.host_monitor_refresh_button_counter -= 1
                                decrease_refresh_button_counter()
                            else
                                $scope.struct.host_monitor_refresh_button_counter = -1
                                $scope.struct.host_monitor_refresh_button_text = "Refresh"
                                $scope.struct.host_monitor_refresh_button_timeout = undefined
                        1000
                    )

                decrease_refresh_button_counter()
        )

]).service("SetupProgressHelper",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswMenuSettings",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswMenuSettings,
) ->

    _unfulfilled_setup_tasks = () ->
        defer = $q.defer()
        if icswMenuSettings.get_settings().user_loggedin
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.DEVICE_SYSTEM_COMPLETION
                    dataType: "json"
                }
            ).then(
                (data) ->
                    unfilled_tasks = 0
                    for entry in data.list
                        if not entry.fulfilled and not entry.ignore
                            unfilled_tasks++
                    defer.resolve(unfilled_tasks)
            )
        else
            defer.resolve(0)

        return defer.promise

    return {
        unfulfilled_setup_tasks: () ->
            return _unfulfilled_setup_tasks()
    }
]).directive("icswSetupProgressTab",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile,
) ->
    return {
        restrict: "EA"
        scope: {
            tab: "=icswTab"
        }
        link: (scope, element, attrs) ->
            if scope.tab.global
                _tn = "icsw.setup.tab.type.#{scope.tab.task.name}"
                console.log "*", _tn
                element.append($compile($templateCache.get(_tn))(scope))
    }
])
