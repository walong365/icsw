# Copyright (C) 2016 init.at
#
# Send feedback to: <g.kaufmann@init.at>
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

# device report module

device_report_module = angular.module(
    "icsw.device.report",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ngCsv"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", "$compileProvider", ($stateProvider, icswRouteExtensionProvider, $compileProvider) ->

    $compileProvider.aHrefSanitizationWhitelist(/^\s*(https?|ftp|mailto|tel|file|blob):/)

    icswRouteExtensionProvider.add_route("main.report")

]).directive("icswDeviceReportOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.report.overview")
        controller: "icswDeviceReportCtrl"
        scope: true
    }
]).controller("icswDeviceReportCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "FileUploader", "icswCSRFService"
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$timeout",
    "icswDispatcherSettingTreeService", "Restangular", "icswActiveSelectionService",
    "icswComplexModalService", "$interval", "icswUserService", "icswAssetHelperFunctions",
    "$http", "icswReportHelperFunctions", "icswToolsSimpleModalService", "DeviceOverviewService",
    "icswStatusHistorySettings"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, FileUploader, icswCSRFService
    icswDeviceTreeService, icswDeviceTreeHelperService, $timeout,
    icswDispatcherSettingTreeService, Restangular, icswActiveSelectionService,
    icswComplexModalService, $interval, icswUserService, icswAssetHelperFunctions,
    $http, icswReportHelperFunctions, icswToolsSimpleModalService, DeviceOverviewService,
    icswStatusHistorySettings
) ->
    $scope.struct = {
        # list of devices
        devices: []
        # device tree
        device_tree: undefined

        gfx_b64_data: undefined

        report_generating: false
        report_download_url: undefined
        report_download_name: undefined
        report_download_url_name: undefined
        report_id: undefined

        generate_button_disabled: false
        generate_interval: undefined
        generate_progress: 0

        selected: true

        network_report_overview_module_selected: false
        general_device_overview_module_selected: false
        user_group_overview_module_selected: false

        pdf_page_format: "landscape(A4)"

        user: undefined

        available_reports: []
        available_reports_dict: {}

        selected_report_history_objects: 0
    }

    refresh_available_reports = () ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.REPORT_REPORT_HISTORY_AVAILABLE
            dataType: 'json'
        }).then(
            (result) ->
                for report_id in result.report_ids
                    if $scope.struct.available_reports_dict.hasOwnProperty(report_id)
                       $scope.struct.available_reports_dict[report_id].number_of_downloads = result.report_history[report_id].number_of_downloads
                    else
                        prettier_time_string = moment(result.report_history[report_id].created_at_time).format("YYYY-MM-DD HH:mm:ss")
                        result.report_history[report_id].created_at_time_pretty = prettier_time_string
                        $scope.struct.available_reports.push(result.report_history[report_id])
                        $scope.struct.available_reports_dict[report_id] = result.report_history[report_id]
            (error) ->
                console.log(error)
        )

    refresh_available_reports()

    initialize_buttons = () ->
        for dev in $scope.struct.devices
            dev.$selected_for_report = false

            icswReportHelperFunctions.disable_device_buttons(dev)

        idx_list = []

        for _dev in $scope.struct.devices
            idx_list.push _dev.idx

        icswSimpleAjaxCall({
            url: ICSW_URLS.REPORT_REPORT_DATA_AVAILABLE
            data:
                idx_list: idx_list
            dataType: 'json'
        }).then(
            (result) ->
                for device in $scope.struct.devices
                    if result.pk_setting_dict.hasOwnProperty(device.idx)

                        device_info_obj = result.pk_setting_dict[device.idx]

                        icswReportHelperFunctions.enable_device_buttons(device, device_info_obj)

          (not_ok) ->
              console.log not_ok
          )

    b64_to_blob = (b64_data, content_type, slice_size) ->
        content_type = content_type or ''
        slice_size = slice_size or 512
        byte_characters = atob(b64_data)
        byte_arrays = []
        offset = 0
        while offset < byte_characters.length
            slice = byte_characters.slice(offset, offset + slice_size)
            byte_numbers = new Array(slice.length)
            i = 0

            while i < slice.length
                byte_numbers[i] = slice.charCodeAt(i)
                i++

            byte_array = new Uint8Array(byte_numbers)
            byte_arrays.push byte_array
            offset += slice_size

        blob = new Blob(byte_arrays, type: content_type)
        return blob


    $q.all(
        [
            icswUserService.load()
        ]
    ).then(
        (data) ->
            $scope.struct.user = data[0].user
    )

    $scope.show_device = ($event, dev) ->
        DeviceOverviewService($event, [dev])

    $scope.uploading = false
    $scope.percentage = 0
    $scope.getPercentage = () ->
        return $scope.percentage

    $scope.uploader = new FileUploader(
            url: ICSW_URLS.REPORT_UPLOAD_REPORT_GFX
            scope: $scope
            queueLimit: 1
            alias: "gfx"
            removeAfterUpload: true
            autoUpload: true
        )

    $scope.uploader.onCompleteAll = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.REPORT_GET_REPORT_GFX
                dataType: 'json'
            }
        ).then(
            (result) ->
                $scope.struct.gfx_b64_data = result.gfx
            (not_ok) ->
                console.log not_ok
        )

        angular.element("input[type='file']").val(null);
        $scope.percentage = 0
        $scope.uploading = false

    $scope.uploader.onProgressAll = (progress) ->
        $scope.uploading = true
        $scope.percentage = progress

    icswCSRFService.get_token().then(
        (token) ->
            $scope.uploader.formData.push({"csrfmiddlewaretoken": token})
    )

    $scope.select_general_module = (selector) ->
        if selector == 0
            $scope.struct.network_report_overview_module_selected = !$scope.struct.network_report_overview_module_selected
        else if selector == 1
            $scope.struct.general_device_overview_module_selected = !$scope.struct.general_device_overview_module_selected
        else if selector == 2
            $scope.struct.user_group_overview_module_selected = !$scope.struct.user_group_overview_module_selected

    select_salt_obj = (obj, attribute, button_disabled_attribute) ->
        obj[attribute] = !obj[attribute]
        if obj.is_meta_device
            for device in $scope.struct.devices
                if device.device_group == obj.device_group && !device[button_disabled_attribute]
                    device[attribute] = obj[attribute]

                    if obj[attribute]
                        device.$selected_for_report = true
        else
            selected = false
            for device in $scope.struct.devices
                if device.device_group == obj.device_group && !device.is_meta_device
                    selected = selected || device[attribute]

            for device in $scope.struct.devices
                if device.device_group == obj.device_group && device.is_meta_device
                    device[attribute] = selected
                    if selected
                        device.$selected_for_report = true

            if selected
                obj.$selected_for_report = selected

    $scope.select_device_modules = () ->
        selected = false
        for device in $scope.struct.devices
            selected = selected || device.$selected_for_report

        for device in $scope.struct.devices
            device.$selected_for_report = !selected


    $scope.select = (obj, selection_type) ->
        if selection_type == 0
            select_salt_obj(obj, "$packages_selected", "$packages_selected_button_disabled")
        else if selection_type == 1
            select_salt_obj(obj, "$licenses_selected", "$licenses_selected_button_disabled")
        else if selection_type == 2
            select_salt_obj(obj, "$installed_updates_selected", "$installed_updates_button_disabled")
        else if selection_type == 3
            select_salt_obj(obj, "$avail_updates_selected", "$avail_updates_button_disabled")
        else if selection_type == 4
            select_salt_obj(obj, "$process_report_selected", "$process_report_button_disabled")
        else if selection_type == 5
            select_salt_obj(obj, "$hardware_report_selected", "$hardware_report_button_disabled")
        else if selection_type == 6
            select_salt_obj(obj, "$dmi_report_selected", "$dmi_report_button_disabled")
        else if selection_type == 7
            select_salt_obj(obj, "$pci_report_selected", "$pci_report_button_disabled")
        else if selection_type == 8
            select_salt_obj(obj, "$lstopo_report_selected", "$lstopo_report_button_disabled")
        else if selection_type == 9
            select_salt_obj(obj, "$availability_overview_selected", "$availability_overview_button_disabled")
        else if selection_type == 10
            select_salt_obj(obj, "$availability_details_selected", "$availability_details_button_disabled")
            if obj.$availability_events_selected == true
                select_salt_obj(obj, "$availability_events_selected", "$availability_events_button_disabled")
        else if selection_type == 11
            select_salt_obj(obj, "$availability_events_selected", "$availability_events_button_disabled")
            if obj.$availability_details_selected != true
                select_salt_obj(obj, "$availability_details_selected", "$availability_details_button_disabled")

    icswSimpleAjaxCall({
                url: ICSW_URLS.REPORT_GET_REPORT_GFX
                dataType: 'json'
            }).then(
                (result) ->
                    $scope.struct.gfx_b64_data = result.gfx
                (not_ok) ->
                    console.log not_ok
            )

    $scope.new_devsel = (devs) ->
        blockUI.start("Loading Data...")
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                Restangular.all(ICSW_URLS.ASSET_GET_ASSETBATCH_LIST.slice(1)).getList(
                    {
                        device_pks: angular.toJson((dev.idx for dev in devs))
                        simple: angular.toJson(1)
                    }
                )
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.devices.length = 0

                idx_list = []

                device_to_scan_lut = {}

                data[1].sort(
                    (a, b) ->
                        return b.idx - a.idx
                )

                for scan in data[1]
                    if scan.is_finished_processing
                        if device_to_scan_lut[scan.device] == undefined
                            device_to_scan_lut[scan.device] = []

                        time_str = moment(scan.run_start_time).format("YYYY-MM-DD HH:mm:ss")

                        scan.$$report_option_string = "ID:" + scan.idx + " -- ScanTime:" + time_str

                        device_to_scan_lut[scan.device].push(scan)

                for dev in devs
                    dev.$$available_scans = []
                    dev.$$selected_assetbatch = "-1"
                    if device_to_scan_lut[dev.idx] != undefined
                        dev.$$available_scans = device_to_scan_lut[dev.idx]
                        dev.$$selected_assetbatch = "" + device_to_scan_lut[dev.idx][0].idx

                    if !dev.is_cluster_device_group
                        dev.$title_str = ""

                        dev.$selected_for_report = false

                        $scope.struct.devices.push(dev)
                        idx_list.push(dev.idx)

                    dev.$$reportstruct = {}
                    dev.$$reportstruct.startdate = undefined
                    dev.$$reportstruct.startdate_dp = undefined
                    dev.$$reportstruct.duration_type = undefined
                    dev.$$reportstruct.date_options = {
                        format: "dd.MM.yyyy"
                        formatYear: "yyyy"
                        maxDate: new Date()
                        minDate: new Date(2000, 1, 1)
                        startingDay: 1
                        minMode: "day"
                        datepickerMode: "day"
                        $$opened: false
                    }

                    dev.$$reportstruct.startdate = moment().startOf("day").subtract(1, "days")
                    $scope.set_duration_type("day", dev)
                    dev.$$reportstruct.startdate_dp = dev.$$reportstruct.startdate.toDate()

                initialize_buttons()
                blockUI.stop()
        )

    $scope.select_report_history = (report_history_obj) ->
        if report_history_obj.$$selected == undefined
            report_history_obj.$$selected = true
        else
            report_history_obj.$$selected = !report_history_obj.$$selected

        if report_history_obj.$$selected
            $scope.struct.selected_report_history_objects += 1
        else
            $scope.struct.selected_report_history_objects -= 1

    $scope.select_all_report_history_objects = () ->
        for report_obj in $scope.struct.available_reports
            report_obj.$$selected = true
        $scope.struct.selected_report_history_objects = $scope.struct.available_reports.length

    $scope.deselect_all_report_history_objects = () ->
        for report_obj in $scope.struct.available_reports
            report_obj.$$selected = false
        $scope.struct.selected_report_history_objects = 0

    $scope.inverse_report_history_object_selection = () ->
        $scope.struct.selected_report_history_objects = 0
        for report_obj in $scope.struct.available_reports
            if report_obj.$$selected == undefined
                report_obj.$$selected = true
            else
                report_obj.$$selected = !report_obj.$$selected

            if report_obj.$$selected
                $scope.struct.selected_report_history_objects += 1

    $scope.delete_selected_report_history_objects = () ->
        icswToolsSimpleModalService("Really delete " + $scope.struct.selected_report_history_objects + " items?").then(
            (_yes) ->
                blockUI.start("Please wait...")

                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.REPORT_DELETE_REPORT_HISTORY_OBJECTS
                        data:
                            idx_list: (report_history_obj.report_id for report_history_obj in $scope.struct.available_reports when report_history_obj.$$selected == true)
                        dataType: 'json'
                    }
                ).then(
                    (result) ->
                        if result.deleted == 0
                            toaster.pop("warning", "", "Could not contact report server.")
                        else
                            to_be_deleted_items = (report_history_obj for report_history_obj in $scope.struct.available_reports when report_history_obj.$$selected == true)
                            _.pullAll($scope.struct.available_reports, to_be_deleted_items)
                            $scope.struct.selected_report_history_objects = 0

                        blockUI.stop()
                )
            (_no) ->
        )

    $scope.get_tr_class = (obj) ->
        return if obj.is_meta_device then "success" else ""

    $scope.generate_report = (report_type) ->
        $scope.struct.generate_button_disabled = true
        $scope.struct.report_download_url = undefined
        $scope.struct.report_generating = true

        settings = []

        # special "device" setting used (with negative pk) for general report module settings
        setting = {
            pk: -1
            network_report_overview_module_selected: $scope.struct.network_report_overview_module_selected
            general_device_overview_module_selected: $scope.struct.general_device_overview_module_selected
            user_group_overview_module_selected: $scope.struct.user_group_overview_module_selected
            pdf_page_format: $scope.struct.pdf_page_format
            user_idx: $scope.struct.user.idx
        }
        settings.push(setting)

        for device in $scope.struct.devices
            if !device.is_meta_device && device.$selected_for_report
                setting = {
                    pk: device.idx
                    packages_selected: device.$packages_selected
                    licenses_selected: device.$licenses_selected
                    installed_updates_selected: device.$installed_updates_selected
                    avail_updates_selected: device.$avail_updates_selected
                    hardware_report_selected: device.$hardware_report_selected
                    process_report_selected: device.$process_report_selected
                    dmi_report_selected: device.$dmi_report_selected
                    pci_report_selected: device.$pci_report_selected
                    lstopo_report_selected: device.$lstopo_report_selected
                    availability_overview_selected: device.$availability_overview_selected
                    availability_details_selected: device.$availability_details_selected
                    availability_events_selected: device.$availability_events_selected
                    availability_timeframe_start: moment(device.$$reportstruct.startdate_dp).unix()
                    assetbatch_id: device.$$selected_assetbatch
                }
                settings.push(setting)

        if (report_type == 0)
            url_to_use = ICSW_URLS.REPORT_GENERATE_REPORT_PDF
        else
            url_to_use = ICSW_URLS.REPORT_GENERATE_REPORT_XLSX

        icswSimpleAjaxCall(
            {
                url: url_to_use
                data:
                    json: angular.toJson(settings)
                dataType: 'json'
            }
        ).then(
            (result) ->
                if result.report_id
                    $scope.struct.generate_interval = $interval(
                        () ->
                            icswSimpleAjaxCall(
                                {
                                    url: ICSW_URLS.REPORT_GET_PROGRESS
                                    data:
                                        id: result.report_id
                                    dataType: 'json'
                                }
                            ).then(
                                (data) ->
                                    if $scope.struct.report_generating
                                        if data.progress > $scope.struct.generate_progress
                                            $scope.struct.generate_progress = data.progress

                                        if data.progress == -1
                                            icswSimpleAjaxCall(
                                                {
                                                    url: ICSW_URLS.REPORT_GET_REPORT_DATA
                                                    data:
                                                        report_id: result.report_id
                                                    dataType: 'json'
                                                }
                                            ).then(
                                                (result) ->
                                                    if result.hasOwnProperty("pdf")
                                                        $scope.struct.report_download_url_name = "Download PDF Report"
                                                        $scope.struct.report_download_name = "Report.pdf"
                                                        blob = b64_to_blob(result.pdf, 'application/pdf')
                                                        $scope.struct.report_download_url = (window.URL || window.webkitURL).createObjectURL(blob)
                                                        $scope.struct.report_id = result.report_id

                                                    if result.hasOwnProperty("xlsx")
                                                        $scope.struct.report_download_url_name = "Download (zipped) XLSX Report"
                                                        $scope.struct.report_download_name = "Report.zip"
                                                        blob = b64_to_blob(result.xlsx, 'application/zip')
                                                        $scope.struct.report_download_url = (window.URL || window.webkitURL).createObjectURL(blob)
                                                        $scope.struct.report_id = result.report_id

                                                    $scope.struct.report_generating = false
                                                    $scope.struct.generate_button_disabled = false
                                                    $interval.cancel($scope.struct.generate_interval)
                                                    refresh_available_reports()
                                                    $scope.struct.generate_progress = 0
                                                (not_ok) ->
                                                    console.log not_ok

                                                    $scope.struct.report_generating = false
                                                    $scope.struct.generate_button_disabled = false
                                                    $interval.cancel($scope.struct.generate_interval)
                                                    $scope.struct.generate_progress = 0

                                            )
                                )
                        , 1000)
                else
                    # not ok
                    $scope.struct.report_generating = false
                    $scope.struct.generate_button_disabled = false
                    $scope.struct.generate_progress = 0
            (not_ok) ->
                $scope.struct.report_generating = false
                $scope.struct.generate_button_disabled = false
                $interval.cancel($scope.struct.generate_interval)
                $scope.struct.generate_progress = 0
                console.log not_ok
        )

    $scope.create_or_edit = ($event, create_mode, parent, obj) ->
        if create_mode
            edit_obj = {
                name: "New gfx"
                location: 0
            }
        sub_scope = $scope.$new(false)
        # location references
        sub_scope.loc = parent
        sub_scope.edit_obj = edit_obj
        # copy flag
        sub_scope.create_mode = create_mode

        # init uploaded
        sub_scope.uploader = new FileUploader(
            url: ICSW_URLS.REPORT_UPLOAD_REPORT_GFX
            scope: $scope
            queueLimit: 1
            alias: "gfx"
            removeAfterUpload: true
            autoUpload: true
        )

        icswCSRFService.get_token().then(
            (token) ->
                sub_scope.uploader.formData.push({"csrfmiddlewaretoken": token})
        )

        icswComplexModalService(
            {
                title: "Upload Logo"
                message: $compile($templateCache.get("icsw.device.report.upload.form"))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("created gfx")

                    icswSimpleAjaxCall({
                        url: ICSW_URLS.REPORT_GET_REPORT_GFX
                        dataType: 'json'
                    }).then(
                        (result) ->
                            $scope.struct.gfx_b64_data = result.gfx
                        (not_ok) ->
                            console.log not_ok
                    )

                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )


    $scope.column_selected = (column_id) ->
        for device in $scope.struct.devices
            if column_id == 0
                if device.$packages_selected == true
                    return true
            else if column_id == 1
                if device.$licenses_selected == true
                    return true
            else if column_id == 2
                if device.$installed_updates_selected == true
                    return true
            else if column_id == 3
                if device.$avail_updates_selected == true
                    return true
            else if column_id == 4
                if device.$process_report_selected == true
                    return true
            else if column_id == 5
                if device.$hardware_report_selected == true
                    return true
            else if column_id == 6
                if device.$dmi_report_selected == true
                    return true
            else if column_id == 7
                if device.$pci_report_selected == true
                    return true
            else if column_id == 8
                if device.$lstopo_report_selected == true
                    return true
            else if column_id == 9
                if device.$availability_overview_selected == true
                    return true
            else if column_id == 10
                if device.$availability_details_selected == true
                    return true
            else if column_id == 11
                if device.$availability_events_selected == true
                    return true

        return false

    $scope.select_column = (column_id) ->
        this_column_selected = $scope.column_selected(column_id)

        for device in $scope.struct.devices
            if column_id == 0
                if !device.$packages_selected_button_disabled
                    device.$packages_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 1
                if !device.$licenses_selected_button_disabled
                    device.$licenses_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 2
                if !device.$installed_updates_button_disabled
                    device.$installed_updates_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 3
                if !device.$avail_updates_button_disabled
                    device.$avail_updates_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 4
                if !device.$process_report_button_disabled
                    device.$process_report_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 5
                if !device.$hardware_report_button_disabled
                    device.$hardware_report_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 6
                if !device.$dmi_report_button_disabled
                    device.$dmi_report_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 7
                if !device.$pci_report_button_disabled
                    device.$pci_report_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 8
                if !device.$lstopo_report_button_disabled
                    device.$lstopo_report_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 9
                if !device.$availability_overview_button_disabled
                    device.$availability_overview_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
            else if column_id == 10
                if !device.$availability_details_button_disabled
                    device.$availability_details_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
                    else
                        device.$availability_events_selected = false
            else if column_id == 11
                if !device.$availability_events_button_disabled
                    device.$availability_events_selected = !this_column_selected
                    if !this_column_selected
                        device.$selected_for_report = true
                        device.$availability_details_selected = true

    $scope.select_software_information = () ->
        selected = false
        for device in $scope.struct.devices
            selected = selected || device.$packages_selected
            selected = selected || device.$licenses_selected
            selected = selected || device.$installed_updates_selected
            selected = selected || device.$avail_updates_selected
            selected = selected || device.$process_report_selected

        for device in $scope.struct.devices
            if !device.$packages_selected_button_disabled
                device.$packages_selected = !selected

            if !device.$licenses_selected_button_disabled
                device.$licenses_selected = !selected

            if !device.$installed_updates_button_disabled
                device.$installed_updates_selected = !selected

            if !device.$avail_updates_button_disabled
                device.$avail_updates_selected = !selected

            if !device.$process_report_button_disabled
                device.$process_report_selected = !selected


    $scope.select_hardware_information = () ->
        selected = false
        for device in $scope.struct.devices
            selected = selected || device.$hardware_report_selected
            selected = selected || device.$dmi_report_selected
            selected = selected || device.$pci_report_selected
            selected = selected || device.$lstopo_report_selected

        for device in $scope.struct.devices
            if !device.$hardware_report_button_disabled
                device.$hardware_report_selected = !selected

            if !device.$dmi_report_button_disabled
                device.$dmi_report_selected = !selected

            if !device.$pci_report_button_disabled
                device.$pci_report_selected = !selected

            if !device.$lstopo_report_button_disabled
                device.$lstopo_report_selected = !selected

    $scope.update_download_counter = (report_obj) ->
        if report_obj == undefined
            report_id = $scope.struct.report_id
        else
            report_id = report_obj.report_id

        icswSimpleAjaxCall({
            url: ICSW_URLS.REPORT_UPDATE_DOWNLOAD_COUNT
            data:
                idx: report_id
            dataType: 'json'
        }).then(
            (result) ->
                refresh_available_reports()
            (error) ->
                console.log(error)
        )

    $scope.downloadify_report_obj = (report_obj) ->
        report_obj.download_progress_percentage = 0
        report_obj.report_download_started = true

        $http.get(ICSW_URLS.REPORT_GET_REPORT_DATA,
            {
                params:
                    report_id: report_obj.report_id
                eventHandlers:
                    progress: (c) ->

                        report_obj.download_progress_percentage = (c.loaded / report_obj.raw_size) * 100
            }
        ).then(
            (result) ->
                result = result.data
                if result.hasOwnProperty("pdf")
                    report_obj.report_download_name = "Report.pdf"
                    blob = b64_to_blob(result.pdf, 'application/pdf')
                    report_obj.report_download_url = (window.URL || window.webkitURL).createObjectURL(blob)

                if result.hasOwnProperty("xlsx")
                    report_obj.report_download_name = "Report.zip"
                    blob = b64_to_blob(result.xlsx, 'application/zip')
                    report_obj.report_download_url = (window.URL || window.webkitURL).createObjectURL(blob)

            (error) ->
                console.log(error)
        )

    $scope.getReportHistoryDownloadPercentage = (report_obj) ->
        if report_obj.download_progress_percentage == undefined
            return 0

        return report_obj.download_progress_percentage

########################################################################################################################
# Timeframe setting functions
########################################################################################################################

    $scope.get_allowed_durations = () ->
        return icswStatusHistorySettings.get_allowed_durations()

    $scope.set_duration_type = (d, device) ->
        device.$$reportstruct.duration_type = d
        _mode = {
            day: "day"
            week: "day"
            month: "month"
            year: "year"
            decade: "year"
        }[d]
        device.$$reportstruct.date_options.minMode = _mode
        device.$$reportstruct.date_options.datepickerMode = _mode

    $scope.open_popup = (device) ->
        device.$$reportstruct.date_options.$$opened = true

]).directive("icswDeviceTreeReportRow",
[
    "$templateCache", "$compile", "icswActiveSelectionService", "icswDeviceTreeService", "icswSimpleAjaxCall",
    "ICSW_URLS", "icswReportHelperFunctions"
(
    $templateCache, $compile, icswActiveSelectionService, icswDeviceTreeService, icswSimpleAjaxCall, ICSW_URLS,
    icswReportHelperFunctions
) ->
    return {
        restrict: "EA"
        link: (scope, element, attrs) ->
            tree = icswDeviceTreeService.current()
            device = scope.$eval(attrs.device)
            group = tree.get_group(device)
            scope.device = device
            scope.group = group
            sel = icswActiveSelectionService.current()
            if device.is_meta_device
                if scope.struct.device_tree.get_group(device).cluster_device_group
                    new_el = $compile($templateCache.get("icsw.device.tree.cdg.report.row"))
                else
                    new_el = $compile($templateCache.get("icsw.device.tree.meta.report.row"))
            else
                new_el = $compile($templateCache.get("icsw.device.tree.report.row"))
            scope.get_dev_sel_class = () ->
                if device.$selected_for_report
                    return "btn btn-xs btn-success"
                else
                    return "btn btn-xs btn-default"
            scope.toggle_dev_sel = () ->
                device.$selected_for_report = !device.$selected_for_report

                group_device = undefined

                group_selected = false

                for entry in scope.struct.devices
                    if entry.device_group == device.device_group
                        if entry.is_meta_device == true
                            group_device = entry
                        else
                            group_selected = group_selected || entry.$selected_for_report


                if group_device != undefined
                    group_device.$selected_for_report = group_selected

            scope.change_dg_sel = () ->
                tree = icswDeviceTreeService.current()
                selected = false
                for entry in tree.all_list
                    if entry.device_group == device.device_group
                        selected = selected || entry.$selected_for_report

                for entry in tree.all_list
                    if entry.device_group == device.device_group
                        entry.$selected_for_report = !selected

            scope.assetbatch_selection_change = (device) ->
                icswReportHelperFunctions.disable_device_buttons(device)

                idx_list = [device.idx]

                icswSimpleAjaxCall({
                    url: ICSW_URLS.REPORT_REPORT_DATA_AVAILABLE
                    data:
                        idx_list: idx_list
                        assetbatch_id: device.$$selected_assetbatch
                    dataType: 'json'
                }).then(
                    (result) ->
                        device_info_obj = result.pk_setting_dict[device.idx]
                        icswReportHelperFunctions.enable_device_buttons(device, device_info_obj)
                )

            element.append(new_el(scope))
    }
]).service("icswReportHelperFunctions",
[
    "icswAssetHelperFunctions",
(
    icswAssetHelperFunctions,
) ->
    _disable_device_buttons = (device) ->
        device.$packages_selected = false
        device.$packages_selected_button_disabled = true

        device.$licenses_selected = false
        device.$licenses_selected_button_disabled = true

        device.$installed_updates_selected = false
        device.$installed_updates_button_disabled = true

        device.$avail_updates_selected = false
        device.$avail_updates_button_disabled = true

        device.$process_report_selected = false
        device.$process_report_button_disabled = true

        device.$hardware_report_selected = false
        device.$hardware_report_button_disabled = true

        device.$dmi_report_selected = false
        device.$dmi_report_button_disabled = true

        device.$pci_report_selected = false
        device.$pci_report_button_disabled = true

        device.$lstopo_report_selected = false
        device.$lstopo_report_button_disabled = true

        device.$availability_overview_selected = false
        device.$availability_overview_button_disabled = true

        device.$availability_details_selected = false
        device.$availability_details_button_disabled = true

        device.$availability_events_selected = false
        device.$availability_events_button_disabled = true

    _enable_device_buttons = (device, device_info_obj) ->
        # general device buttons are always enabled
        device.$availability_overview_button_disabled = false
        device.$availability_details_button_disabled = false
        device.$availability_events_button_disabled = false

        for obj in device_info_obj
            button_title_str = ""
            if obj.hasOwnProperty("length")
                asset_type = obj[0]
                asset_run_time = moment(obj[1]).format("YYYY-MM-DD HH:mm:ss")
                asset_batch_id = obj[2]

                button_title_str = "AssetBatchId: " + asset_batch_id + "\n" + "AssetRunTime: " + asset_run_time

            else
                asset_type = obj

            asset_type_name = icswAssetHelperFunctions.resolve("asset_type", asset_type)

            if asset_type_name == "Package"
                device.$packages_selected_button_disabled = false
                device.$packages_selected_button_title = button_title_str
            else if asset_type_name == "License"
                device.$licenses_selected_button_disabled = false
                device.$licenses_selected_button_title = button_title_str
            else if asset_type_name == "Update"
                device.$installed_updates_button_disabled = false
                device.$installed_updates_button_title = button_title_str
            else if asset_type_name == "Pending update"
                device.$avail_updates_button_disabled = false
                device.$avail_updates_button_title = button_title_str
            else if asset_type_name == "Process"
                device.$process_report_button_disabled = false
                device.$process_report_button_title = button_title_str
            else if asset_type_name == "Windows Hardware"
                device.$hardware_report_button_disabled = false
                device.$hardware_report_button_title = button_title_str
            else if asset_type_name == "DMI"
                device.$dmi_report_button_disabled = false
                device.$dmi_report_button_title = button_title_str
            else if asset_type_name == "PCI"
                device.$pci_report_button_disabled = false
                device.$pci_report_button_title = button_title_str
            else if asset_type_name == "Hardware"
                device.$lstopo_report_button_disabled = false
                device.$lstopo_report_button_title= button_title_str
            else if asset_type_name == "LSHW"
                device.$hardware_report_button_disabled = false
                device.$hardware_report_button_title = button_title_str

    return {
        disable_device_buttons: (device) ->
            return _disable_device_buttons(device)

        enable_device_buttons: (device, device_info_obj) ->
            return _enable_device_buttons(device, device_info_obj)
    }
]).filter('reportHistoryFilter'
[
    "$filter",
(
    $filter,
) ->
    return (input, predicate) ->
        strict = false

        strict_predicate_names = ["report_id", "number_of_pages", "number_of_downloads"]

        for strict_predicate_name in strict_predicate_names
            if predicate.hasOwnProperty(strict_predicate_name)
                strict = true
                predicate[strict_predicate_name] = parseInt(predicate[strict_predicate_name])

        return $filter('filter')(input, predicate, strict)
])