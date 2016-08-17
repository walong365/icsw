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

angular.module(
    "icsw.device.info",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools", "icsw.device.variables"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.deviceinfo")
]).service("DeviceOverviewSelection",
[
    "$rootScope", "ICSW_SIGNALS",
(
    $rootScope, ICSW_SIGNALS,
) ->
    _selection = []
    set_selection = (sel) ->
        _selection = sel
        $rootScope.$emit(ICSW_SIGNALS("ICSW_OVERVIEW_SELECTION_CHANGED"), _selection)

    get_selection = (sel) ->
        return _selection

    return {
        set_selection: (sel) ->
            set_selection(sel)
        get_selection: (sel) ->
            return get_selection()
    }
]).service("DeviceOverviewService",
[
    "Restangular", "$rootScope", "$templateCache", "$compile", "$uibModal", "$q",
    "icswComplexModalService", "DeviceOverviewSelection", "DeviceOverviewSettings",
(
    Restangular, $rootScope, $templateCache, $compile, $uibModal, $q,
    icswComplexModalService, DeviceOverviewSelection, DeviceOverviewSettings
) ->
    return (event) ->
        # create new modal for device
        # device object with access_levels
        _defer = $q.defer()
        sub_scope = $rootScope.$new(true)
        # console.log "devlist", devicelist
        sub_scope.devicelist = DeviceOverviewSelection.get_selection()
        icswComplexModalService(
            {
                message: $compile("<icsw-device-overview icsw-popup-mode='1' icsw-device-list='devicelist'></icsw-device-overview>")(sub_scope)
                title: "Device Info"
                css_class: "modal-wide modal-tall"
                closable: true
                show_callback: (modal) ->
                    DeviceOverviewSettings.open()
                    _defer.resolve("show")
            }
        ).then(
            (closeinfo) ->
                console.log "close deviceoverview #{closeinfo}"
                DeviceOverviewSettings.close()
                sub_scope.$destroy()
        )
        return _defer.promise
        # my_mixin.edit(null, devicelist[0])
        # todo: destroy sub_scope
]).service("DeviceOverviewSettings", [() ->
    # default value
    def_mode = "general"
    is_active = false
    return {
        is_active: () ->
            return is_active
        open: () ->
            is_active = true
        close: () ->
            is_active = false
        get_mode : () ->
            return def_mode
        set_mode: (mode) ->
            def_mode = mode
    }
]).directive("icswDeviceOverview",
[
    "$compile", "DeviceOverviewSettings", "$templateCache", "icswAcessLevelService",
(
    $compile, DeviceOverviewSettings, $templateCache, icswAcessLevelService,
) ->
    return {
        restrict: "EA"
        replace: true
        scope: {
            devicelist: "=icswDeviceList"
            popupmode: "@icswPopupMode"
        }
        link: (scope, element, attrs) ->
            # console.log "LINK", scope.popupmode
            # console.log "DL=", scope.devicelist
            icswAcessLevelService.install(scope)
            # number of total devices
            scope.total_sel = scope.devicelist.length
            # number of normal (== non-meta) devices
            scope.normal_sel = (dev.idx for dev in scope.devicelist when !dev.is_meta_device).length
            scope.device_nmd_list = (dev for dev in scope.devicelist when !dev.is_meta_device)
            scope.activate = (name) ->
                # remember setting
                DeviceOverviewSettings.set_mode(name)
            if scope.total_sel > 1
                scope.addon_text = " (#{scope.total_sel})"
            else
                scope.addon_text = ""
            if scope.normal_sel > 1
                scope.addon_text_nmd = " (#{scope.normal_sel})"
            else
                scope.addon_text_nmd = ""
            # destroy old subscope, important
            scope.$on(
                "$destroy",
                () ->
                    console.log "Destroy Device-overview scope"
            )
            scope.active_tab = 0
            new_el = $compile($templateCache.get("icsw.device.info"))(scope)
            element.children().remove()
            element.append(new_el)
            console.log "Overview init"
    }
]).directive("icswSimpleDeviceInfo",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        controller: "icswSimpleDeviceInfoOverviewCtrl"
        template: $templateCache.get("icsw.device.info.overview")
        scope: true
    }
]).directive("icswDeviceInfoDevice",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        controller: "icswSimpleDeviceInfoCtrl"
        scope: {
            icsw_struct: "=icswStruct"
        }
        link: (scope, element, attrs) ->
            scope.do_init().then(
                (done) ->
                    if scope.icsw_struct.is_devicegroup
                        _t_name = "icsw.devicegroup.info.form"
                    else
                        _t_name = "icsw.device.info.form"
                    element.append($compile($templateCache.get(_t_name))(scope))
            )
    }
]).controller("icswSimpleDeviceInfoCtrl",
[
    "$scope", "Restangular", "$q", "ICSW_URLS",
    "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", "icswDeviceTreeService", "icswMonitoringBasicTreeService",
    "icswAcessLevelService", "icswActiveSelectionService", "icswDeviceBackup", "icswDeviceGroupBackup",
    "icswDeviceTreeHelperService", "icswComplexModalService", "toaster", "$compile", "$templateCache",
    "icswCategoryTreeService",
(
    $scope, Restangular, $q, ICSW_URLS,
    $rootScope, ICSW_SIGNALS, icswDomainTreeService, icswDeviceTreeService, icswMonitoringBasicTreeService,
    icswAcessLevelService, icswActiveSelectionService, icswDeviceBackup, icswDeviceGroupBackup,
    icswDeviceTreeHelperService, icswComplexModalService, toaster, $compile, $templateCache,
    icswCategoryTreeService,
) ->
    $scope.struct = {
        # data is valid
        data_valid: false
        # device tree
        device_tree: undefined
        # monitoring tree
        monitoring_tree: undefined
        # domain tree
        domain_tree: undefined
        # category tree
        category_tree: undefined
        # device group
        is_devicegroup: false
    }

    create_info_fields = (obj) ->
        if $scope.struct.is_devicegroup
            obj.$$full_device_name = obj.name.substr(8)
            # not really needed
            obj.$$snmp_scheme_info = "N/A"
            obj.$$snmp_info = "N/A"
            obj.$$ip_info = "N/A"
            hints = "---"
            cats = "---"
        else
            obj.$$full_device_name = obj.full_name
            _sc = obj.snmp_schemes
            if _sc.length
                obj.$$snmp_scheme_info = ("#{_entry.snmp_scheme_vendor.name}.#{_entry.name}" for _entry in _sc).join(", ")
            else
                obj.$$snmp_scheme_info = "none"
            ip_list = []
            for _nd in obj.netdevice_set
                for _ip in _nd.net_ip_set
                    ip_list.push(_ip.ip)
            obj.$$ip_info = if ip_list.length then ip_list.join(", ") else "none"
            _sc = obj.DeviceSNMPInfo
            if _sc
                obj.$$snmp_info = _sc.description
            else
                obj.$$snmp_info = "none"
            if obj.monitoring_hint_set.length
                mhs = obj.monitoring_hint_set
                hints = "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
            else
                hints = "---"

            # categories
            _cats = $scope.struct.category_tree.get_device_categories(obj)
            _asset_cats = (entry for entry in _cats when entry.asset)
            if _cats.length
                _cats_info = (entry.name for entry in _cats).join(", ")
            else
                _cats_info = "---"
            obj.$$category_info = _cats_info 
            if _asset_cats.length
                _asset_cats_info = (entry.name for entry in _asset_cats).join(", ")
            else
                _asset_cats_info = "---"
            obj.$$asset_category_info = _asset_cats_info 

        # monitoring image
        img_url = ""
        if obj.mon_ext_host
            for entry in $scope.struct.monitoring_tree.mon_ext_host_list
                if entry.idx == obj.mon_ext_host
                    img_url = entry.data_image
        obj.$$image_source = img_url
        obj.$$monitoring_hint_info = hints

    icswAcessLevelService.install($scope)

    _dereg_0 = $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), () ->
        if $scope.struct.data_valid
            create_info_fields($scope.edit_obj)
    )

    $scope.$on("$destroy", () ->
        _dereg_0()
    )

    $scope.do_init = () ->
        defer = $q.defer()
        $scope.struct.data_valid = false
        $scope.struct.is_devicegroup = $scope.icsw_struct.is_devicegroup
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswMonitoringBasicTreeService.load($scope.$id)
                icswDomainTreeService.load($scope.$id)
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.monitoring_tree = data[1]
                $scope.struct.domain_tree = data[2]
                $scope.struct.category_tree = data[3]
                if $scope.icsw_struct.is_devicegroup
                    $scope.edit_obj = $scope.struct.device_tree.get_group($scope.icsw_struct.edit_obj)
                else
                    $scope.edit_obj = $scope.icsw_struct.edit_obj
                create_info_fields($scope.edit_obj)
                $scope.struct.data_valid = true
                defer.resolve("done")
        )

        return defer.promise

    $scope.modify = () ->
        if $scope.struct.is_devicegroup
            dbu = new icswDeviceGroupBackup()
            template_name = "icsw.devicegroup.info.edit.form"
            title = "Modify Devicegroup settings"
        else
            dbu = new icswDeviceBackup()
            template_name = "icsw.device.info.edit.form"
            title = "Modify Device settings"
        dbu.create_backup($scope.edit_obj)
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = $scope.edit_obj

        # for fields, tree can be the basic or the cluster tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                title: title
                css_class: "modal-wide"
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        sub_scope.edit_obj.put().then(
                            (ok) ->
                                $scope.struct.device_tree.reorder()
                                d.resolve("updated")
                            (not_ok) ->
                                d.reject("not updated")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                # recreate info fields
                create_info_fields($scope.edit_obj)
        )

    $scope.modify_categories = (for_asset) ->
        dbu = new icswDeviceBackup()
        template_name = "icsw.device.category.edit"
        title = "Modify DeviceCategories"
        dbu.create_backup($scope.edit_obj)
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = $scope.edit_obj
        sub_scope.asset_filter = for_asset

        # for fields, tree can be the basic or the cluster tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                title: title
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("updated")
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                # recreate info fields
                create_info_fields($scope.edit_obj)
        )

]).controller("icswSimpleDeviceInfoOverviewCtrl",
[
    "$scope", "Restangular", "$q", "ICSW_URLS",
    "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", "icswDeviceTreeService", "icswMonitoringBasicTreeService",
    "icswAcessLevelService", "icswActiveSelectionService", "icswDeviceBackup", "icswDeviceGroupBackup",
    "icswDeviceTreeHelperService", "icswComplexModalService", "toaster", "$compile", "$templateCache",
(
    $scope, Restangular, $q, ICSW_URLS,
    $rootScope, ICSW_SIGNALS, icswDomainTreeService, icswDeviceTreeService, icswMonitoringBasicTreeService,
    icswAcessLevelService, icswActiveSelectionService, icswDeviceBackup, icswDeviceGroupBackup,
    icswDeviceTreeHelperService, icswComplexModalService, toaster, $compile, $templateCache,
) ->
    icswAcessLevelService.install($scope)

    $scope.struct = {
        # data is valid
        data_valid: false
        # waiting clients
        waiting_clients: 0
        # device tree
        device_tree: undefined
        # domain tree
        # devices
        devices: []
        # structured list, includes template name
        slist: []
    }
    # create info fields
    create_small_info_fields = (struct) ->
        obj = struct.edit_obj
        group = $scope.struct.device_tree.get_group(obj)
        if struct.is_devicegroup
            obj.$$full_device_name = obj.name.substr(8)
            # not really needed
            obj.$$snmp_scheme_info = "N/A"
            obj.$$snmp_info = "N/A"
            obj.$$ip_info = "N/A"
        else
            obj.$$full_device_name = group.full_name

    $scope.new_devsel = (in_list) ->
        $scope.struct.data_valid = false
        if in_list.length > 0
            $scope.struct.devices.length = 0
            $scope.struct.slist.length = 0
            icswDeviceTreeService.load($scope.$id).then(
                (tree) ->
                    $scope.struct.device_tree = tree
                    trace_devices =  $scope.struct.device_tree.get_device_trace(in_list)
                    dt_hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, trace_devices)
                    $q.all(
                        [
                            icswDomainTreeService.load($scope.$id)
                            $scope.struct.device_tree.enrich_devices(
                                dt_hs
                                [
                                    "network_info", "monitoring_hint_info", "disk_info", "com_info",
                                    "snmp_info", "snmp_schemes_info", "scan_lock_info",
                                ]
                            )
                       ]
                    ).then(
                        (data) ->
                            $scope.struct.domain_tree = data[0]
                            for dev in in_list
                                $scope.struct.devices.push(dev)
                                if dev.is_meta_device
                                    new_struct = {
                                        edit_obj: dev
                                        is_devicegroup: true
                                    }
                                else
                                    new_struct = {
                                        edit_obj: dev
                                        is_devicegroup: false
                                    }
                                $scope.struct.slist.push(new_struct)
                                create_small_info_fields(new_struct)
                            $scope.struct.data_valid = true
                    )
            )
        else
            $scope.struct.devices.length = 0
            $scope.struct.slist.length = 0
            $scope.struct.data_valid = true

])
