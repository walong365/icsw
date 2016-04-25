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
).controller("icswDeviceInfoOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout",
    "icswAcessLevelService", "ICSW_URLS",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $timeout,
    icswAcessLevelService, ICSW_URLS
) ->
    icswAcessLevelService.install($scope)
]).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.deviceinfo", {
            url: "/deviceinfo"
            template: '<icsw-simple-device-info icsw-sel-man="0"></icsw-simple-device-info>'
            data:
                pageTitle: "Device info"
                rights: ["user.modify_tree"]
                menuEntry:
                    preSpacer: true
                    menukey: "dev"
                    icon: "fa-bars"
                    ordering: 10
                    postSpacer: true
        }
    )
]).service("DeviceOverviewSelection",
[
    "$rootScope", "ICSW_SIGNALS",
(
    $rootScope, ICSW_SIGNALS
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
    "Restangular", "$rootScope", "$templateCache", "$compile", "$uibModal", "$q", "icswAcessLevelService",
    "icswComplexModalService", "DeviceOverviewSelection", "DeviceOverviewSettings",
(
    Restangular, $rootScope, $templateCache, $compile, $uibModal, $q, icswAcessLevelService,
    icswComplexModalService, DeviceOverviewSelection, DeviceOverviewSettings
) ->
    return (event) ->
        # create new modal for device
        # device object with access_levels
        _defer = $q.defer()
        devicelist = DeviceOverviewSelection.get_selection()
        sub_scope = $rootScope.$new()
        console.log "devlist", devicelist
        icswAcessLevelService.install(sub_scope)
        sub_scope.popupmode = 1
        sub_scope.devicelist = devicelist
        icswComplexModalService(
            {
                message: $compile("<icsw-device-overview></icsw-device-overview>")(sub_scope)
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
]).directive("icswDeviceOverview", ["$compile", "DeviceOverviewSettings", "$templateCache", ($compile, DeviceOverviewSettings, $templateCache) ->
    return {
        restrict: "EA"
        replace: true
        scope: false
        compile: (element, attrs) ->
            return (scope, iElement, Attrs) ->
                scope.pk_list = {
                    general: []
                    network: []
                    config: []
                    status_history: []
                    livestatus: []
                    graphing: []
                    device_variable: []
                }
                scope.dev_list = {
                    general: []
                    network: []
                    config: []
                    status_history: []
                    livestatus: []
                    graphing: []
                    device_variable: []
                }
                for key of scope.pk_list
                    scope["#{key}_active"] = false
                # pk list of devices
                scope.dev_pk_list = (dev.idx for dev in scope.devicelist)
                # pk list of devices without meta-devices
                scope.dev_pk_nmd_list = (dev.idx for dev in scope.devicelist when !dev.is_meta_device)
                scope.device_nmd_list = (dev for dev in scope.devicelist when !dev.is_meta_device)
                _cur_mode = DeviceOverviewSettings.get_mode()
                scope["#{_cur_mode}_active"] = true
                scope.activate = (name) ->
                    DeviceOverviewSettings.set_mode(name)
                    if name in ["network", "status_history", "livestatus", "category", "location"]
                        scope.pk_list[name] = scope.device_nmd_list
                        scope.dev_list[name] = scope.devicelist
                    else if name in ["config", "graphing", "device_variable"]
                        scope.pk_list[name] = scope.devicelist
                        scope.dev_list[name] = scope.devicelist
                if scope.dev_pk_list.length > 1
                    scope.addon_text = " (#{scope.devicelist.length})"
                else
                    scope.addon_text = ""
                if scope.dev_pk_nmd_list.length > 1
                    scope.addon_text_nmd = " (#{scope.device_nmd_list.length})"
                else
                    scope.addon_text_nmd = ""
                # destroy old subscope, important
                scope.$on("$destroy", () -> console.log "Destroy Device-overview scope")
                new_el = $compile($templateCache.get("icsw.device.info"))(scope)
                iElement.children().remove()
                iElement.append(new_el)
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
        controller: "icswSimpleDeviceInfoCtrl"
        link: (scope, element, attrs) ->
            scope.$watch("template_name", (new_val) ->
                if new_val
                    element.children().remove()
                    element.append($compile($templateCache.get(new_val))(scope))
            )
    }
]).controller("icswSimpleDeviceInfoCtrl",
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
    $scope.data_valid = false
    $scope.$on("$destroy", () ->
        console.log "close req"
        if $scope.bu_obj
            $scope.bu_obj.restore_backup($scope.edit_obj)
    )
    console.log "SDI init"
    $scope.show_uuid = false
    $scope.image_url = ""

    # create info fields
    create_info_fields = () ->
        obj = $scope.edit_obj
        if $scope.is_devicegroup
            obj.$$full_device_name = obj.name.substr(8)
            # not really needed
            obj.$$snmp_scheme_info = "N/A"
            obj.$$snmp_info = "N/A"
            obj.$$ip_info = "N/A"
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
        img_url = ""
        if obj.mon_ext_host
            for entry in $scope.monitoring_tree.mon_ext_host_list
                if entry.idx == obj.mon_ext_host
                    img_url = entry.data_image
        obj.$$image_source = img_url

    $scope.new_devsel = (in_list) ->
        if in_list.length > 0
            icswDeviceTreeService.load($scope.$id).then(
                (tree) ->
                    $scope.dev_tree = tree
                    edit_obj = in_list[0]
                    console.log "start enrichment"
                    dt_hs = icswDeviceTreeHelperService.create($scope.dev_tree, [edit_obj])
                    $q.all(
                        [
                            icswDomainTreeService.load($scope.$id)
                            icswMonitoringBasicTreeService.load($scope.$id)
                            $scope.dev_tree.enrich_devices(dt_hs, ["network_info", "monitoring_hint_info", "disk_info", "com_info", "snmp_info", "snmp_schemes_info", "scan_info"])
                        ]
                    ).then(
                        (data) ->
                            $scope.data_valid = true
                            $scope.domain_tree = data[0]
                            $scope.monitoring_tree = data[1]
                            edit_obj = data[2][0]
                            if edit_obj.is_meta_device
                                edit_obj = $scope.dev_tree.get_group(edit_obj)
                                $scope.is_devicegroup = true
                                template_name = "icsw.devicegroup.info.form"
                            else
                                $scope.is_devicegroup = false
                                template_name = "icsw.device.info.form"
                            $scope.edit_obj = edit_obj
                            # create backup
                            $scope.template_name = template_name
                            create_info_fields()
                    )
            )
        else
            $scope.edit_obj = undefined
            $scope.template_name = "icsw.deviceempty.info.form"

    $scope.modify = () ->
        if $scope.is_devicegroup
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
                                $scope.dev_tree.reorder()
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
                create_info_fields()
        )

    # helper functions

    $scope.get_monitoring_hint_info = () ->
        if $scope.edit_obj.monitoring_hint_set.length
            mhs = $scope.edit_obj.monitoring_hint_set
            return "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
        else
            return "---"

])
