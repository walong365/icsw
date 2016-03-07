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
).controller("icswDeviceInfoOverviewCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "msgbus", "icswAcessLevelService", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, msgbus, icswAcessLevelService, ICSW_URLS) ->
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
]).service("DeviceOverviewSelection", ["$rootScope", "ICSW_SIGNALS", ($rootScope, ICSW_SIGNALS) ->
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
                css_class: "modal-wide"
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
                    "general": []
                    "network": []
                    "config": []
                    "status_history": []
                    "livestatus": []
                    "graphing": []
                    "device_variable": []
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
                    if name in ["network", "status_history", "livestatus", "category"]
                        scope.pk_list[name] = scope.device_nmd_list
                    else if name in ["config", "graphing", "device_variable"]
                        scope.pk_list[name] = scope.devicelist
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
    "$scope", "$uibModal", "Restangular", "restDataSource", "$q", "ICSW_URLS",
    "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", "icswDeviceTreeService", "icswMonitoringTreeService",
    "icswAcessLevelService", "icswActiveSelectionService", "icswDeviceBackup", "icswDeviceGroupBackup",
    "icswDeviceTreeHelperService",
(
    $scope, $uibModal, Restangular, restDataSource, $q, ICSW_URLS,
    $rootScope, ICSW_SIGNALS, icswDomainTreeService, icswDeviceTreeService, icswMonitoringTreeService,
    icswAcessLevelService, icswActiveSelectionService, icswDeviceBackup, icswDeviceGroupBackup,
    icswDeviceTreeHelperService
) ->
    icswAcessLevelService.install($scope)
    $scope.data_valid = false
    $scope.$on("$destroy", () ->
        console.log "close req"
        if $scope.bu_obj
            $scope.bu_obj.restore_backup($scope.edit_obj)
    )
    $scope.toggle_uuid = () ->
        $scope.show_uuid = !$scope.show_uuid
    console.log "SDI init"
    $scope.show_uuid = false
    $scope.image_url = ""
    $scope.new_devsel = (in_list) ->
        if in_list.length > 0
            icswDeviceTreeService.fetch($scope.$id).then(
                (tree) ->
                    $scope.dev_tree = tree
                    edit_obj = in_list[0]
                    console.log "start enrichment"
                    dt_hs = icswDeviceTreeHelperService.create($scope.dev_tree, [edit_obj])
                    $q.all(
                        [
                            icswDomainTreeService.fetch($scope.$id)
                            icswMonitoringTreeService.fetch($scope.$id)
                            $scope.dev_tree.enrich_devices(dt_hs, ["network_info", "monitoring_hint_info", "disk_info", "com_info", "snmp_info", "snmp_schemes_info"])
                        ]
                    ).then(
                        (data) ->
                            console.log "******", data
                            $scope.data_valid = true
                            $scope.domain_tree = data[0]
                            $scope.monitoring_tree = data[1]
                            edit_obj = data[2][0]
                            if edit_obj.is_meta_device
                                edit_obj = $scope.dev_tree.get_group(edit_obj)
                                bu_obj = new icswDeviceGroupBackup()
                                template_name = "icsw.devicegroup.info.form"
                            else
                                bu_obj = new icswDeviceBackup()
                                template_name = "icsw.device.info.form"
                            $scope.edit_obj = edit_obj
                            $scope.bu_obj = bu_obj
                            # create backup
                            $scope.bu_obj.create_backup($scope.edit_obj)
                            $scope.template_name = template_name
                    )
            )
        else
            $scope.edit_obj = undefined
            $scope.bu_obj = undefined
            $scope.template_name = "icsw.deviceempty.info.form"

    $scope.modify = () ->
        if not $scope.form.$invalid
            if $scope.acl_modify($scope.edit_obj, "backbone.device.change_basic")
                console.log $scope.edit_obj
                $scope.edit_obj.put().then(
                    (recv) ->
                        # overwrite current backup
                        $scope.bu_obj.create_backup($scope.edit_obj)
                        # rebalance tree
                        $scope.dev_tree.reorder()
                        console.log "saved", recv
                )
        else
            toaster.pop("warning", "form validation problem", "", 0)

    # helper functions

    $scope.get_monitoring_hint_info = () ->
        if $scope.edit_obj.monitoring_hint_set.length
            mhs = $scope.edit_obj.monitoring_hint_set
            return "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
        else
            return "---"

    $scope.get_ip_info = () ->
        if $scope.edit_obj?
            ip_list = []
            for _nd in $scope.edit_obj.netdevice_set
                for _ip in _nd.net_ip_set
                    ip_list.push(_ip.ip)
            if ip_list.length
                return ip_list.join(", ")
            else
                return "none"
        else
            return "---"

    $scope.get_snmp_scheme_info = () ->
        if $scope.edit_obj?
            _sc = $scope.edit_obj.snmp_schemes
            if _sc.length
                return ("#{_entry.snmp_scheme_vendor.name}.#{_entry.name}" for _entry in _sc).join(", ")
            else
                return "none"
        else
            return "---"

    $scope.get_snmp_info = () ->
        if $scope.edit_obj?
            _sc = $scope.edit_obj.DeviceSNMPInfo
            if _sc
                return _sc.description
            else
                return "none"
        else
            return "---"

    $scope.get_image_src = () ->
        img_url = ""
        if $scope.edit_obj.mon_ext_host
            for entry in $scope.monitoring_tree.mon_ext_host_list
                if entry.idx == $scope.edit_obj.mon_ext_host
                    img_url = entry.data_image
        return img_url

    $scope.get_full_name = () ->
        if $scope.edit_obj.is_meta_device
            return $scope.edit_obj.full_name.substr(8)
        else
            return $scope.edit_obj.full_name

])
