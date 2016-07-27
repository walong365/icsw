# Copyright (C) 2016 init.at
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

# variable related module

device_report_module = angular.module(
    "icsw.device.report",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ngCsv"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", "$compileProvider", ($stateProvider, icswRouteExtensionProvider, $compileProvider) ->

    $compileProvider.aHrefSanitizationWhitelist(/^\s*(https?|ftp|mailto|tel|file|blob):/)

    $stateProvider.state(
        "main.report", {
            url: "/report"
            templateUrl: 'icsw/device/report/overview'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Device Reporting"
                menuEntry:
                    menukey: "dev"
                    icon: "fa-book"
                    ordering: 100
                dashboardEntry:
                    size_x: 3
                    size_y: 3
                    allow_state: true
        }
    )
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
    "icswComplexModalService", "$interval"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, FileUploader, icswCSRFService
    icswDeviceTreeService, icswDeviceTreeHelperService, $timeout,
    icswDispatcherSettingTreeService, Restangular, icswActiveSelectionService,
    icswComplexModalService, $interval
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

        generate_button_disabled: false
        generate_interval: undefined
        generate_progress: 0

        selected: true
    }

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
        icswSimpleAjaxCall({
                    url: ICSW_URLS.REPORT_GET_REPORT_GFX
                    dataType: 'json'
                }).then(
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

    $scope.select = (obj, selection_type) ->
        if selection_type == 0
            obj.$packages_selected = !obj.$packages_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$packages_selected = obj.$packages_selected

        else if selection_type == 1
            obj.$licenses_selected = !obj.$licenses_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$licenses_selected = obj.$licenses_selected

        else if selection_type == 2
            obj.$installed_updates_selected = !obj.$installed_updates_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$installed_updates_selected = obj.$installed_updates_selected

        else if selection_type == 3
            obj.$avail_updates_selected = !obj.$avail_updates_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$avail_updates_selected = obj.$avail_updates_selected

        else if selection_type == 4
            obj.$process_report_selected = !obj.$process_report_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$process_report_selected = obj.$process_report_selected

        else if selection_type == 5
            obj.$hardware_report_selected = !obj.$hardware_report_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$hardware_report_selected = obj.$hardware_report_selected

        else if selection_type == 6
            obj.$dmi_report_selected = !obj.$dmi_report_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$dmi_report_selected = obj.$dmi_report_selected

        else if selection_type == 7
            obj.$pci_report_selected = !obj.$pci_report_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$pci_report_selected = obj.$pci_report_selected

        else if selection_type == 8
            obj.$lstopo_report_selected = !obj.$lstopo_report_selected
            if obj.is_meta_device
                for device in $scope.struct.devices
                    if device.device_group == obj.device_group
                        device.$lstopo_report_selected = obj.$lstopo_report_selected
        

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
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.devices.length = 0
                for dev in devs
                    dev.$packages_selected = true
                    dev.$licenses_selected = true
                    dev.$installed_updates_selected = true
                    dev.$avail_updates_selected = true
                    dev.$hardware_report_selected = true
                    dev.$process_report_selected = true
                    dev.$dmi_report_selected = true
                    dev.$pci_report_selected = true
                    dev.$lstopo_report_selected = true
                    $scope.struct.devices.push(dev)
        )
        
    $scope.get_tr_class = (obj) ->
        return if obj.is_meta_device then "success" else ""

    $scope.downloadPdf = ->
        $scope.struct.generate_button_disabled = true
        $scope.struct.report_download_url = undefined
        $scope.struct.report_generating = true

        selected_devices = icswActiveSelectionService.current().dev_sel

        settings = []

        for device in $scope.struct.devices
            for pk in selected_devices
                if !device.is_meta_device && device.idx == pk
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
                    }
                    settings.push(setting)

        icswSimpleAjaxCall({
            url: ICSW_URLS.REPORT_GENERATE_REPORT_PDF
            data:
                pks: settings
            dataType: 'json'
        }
        ).then(
            (result) ->
                $scope.struct.generate_interval = $interval(
                    () ->
                        icswSimpleAjaxCall({
                            url: ICSW_URLS.REPORT_GET_PROGRESS
                            data:
                                id: result.id
                            dataType: 'json'
                        }).then(
                            (data) ->
                                console.log(data)
                                if $scope.struct.report_generating
                                    if data.progress > $scope.struct.generate_progress
                                        $scope.struct.generate_progress = data.progress

                                    if data.progress == 100
                                        icswSimpleAjaxCall({
                                            url: ICSW_URLS.REPORT_GET_REPORT_PDF
                                            data:
                                                id: result.id
                                            dataType: 'json'
                                        }).then(
                                            (result) ->
                                                $scope.struct.report_download_name = "Report.pdf"
                                                blob = new Blob([ atob(result.pdf) ], { type : 'application/pdf' })
                                                $scope.struct.report_download_url = (window.URL || window.webkitURL).createObjectURL(blob)

                                                $scope.struct.report_generating = false
                                                $scope.struct.generate_button_disabled = false
                                                $interval.cancel($scope.struct.generate_interval)
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

        return false

    $scope.select_column = (column_id) ->
        this_column_selected = $scope.column_selected(column_id)

        for device in $scope.struct.devices
            if column_id == 0
                device.$packages_selected = !this_column_selected
            else if column_id == 1
                device.$licenses_selected = !this_column_selected
            else if column_id == 2
                device.$installed_updates_selected = !this_column_selected
            else if column_id == 3
                device.$avail_updates_selected = !this_column_selected
            else if column_id == 4
                device.$process_report_selected = !this_column_selected
            else if column_id == 5
                device.$hardware_report_selected = !this_column_selected
            else if column_id == 6
                device.$dmi_report_selected = !this_column_selected
            else if column_id == 7
                device.$pci_report_selected = !this_column_selected
            else if column_id == 8
                device.$lstopo_report_selected = !this_column_selected



]).directive("icswDeviceTreeReportRow",
[
    "$templateCache", "$compile", "icswActiveSelectionService", "icswDeviceTreeService",
(
    $templateCache, $compile, icswActiveSelectionService, icswDeviceTreeService
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
                if sel.device_is_selected(device)
                    return "btn btn-xs btn-success"
                else
                    return "btn btn-xs btn-default"
            scope.toggle_dev_sel = () ->
                sel.toggle_selection(device)
            scope.change_dg_sel = (flag) ->
                tree = icswDeviceTreeService.current()
                for entry in tree.all_list
                    if entry.device_group == device.device_group
                        if flag == 1
                            sel.add_selection(entry)
                        else if flag == -1
                            sel.remove_selection(entry)
                        else
                            sel.toggle_selection(entry)
            element.append(new_el(scope))
    }
])