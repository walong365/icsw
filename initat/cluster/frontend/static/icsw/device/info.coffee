# Copyright (C) 2012-2015 init.at
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
).controller("icswDeviceInfoOverviewCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$window", "msgbus", "access_level_service", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $window, msgbus, access_level_service, ICSW_URLS) ->
        access_level_service.install($scope)
        $scope.show = false
        $scope.permissions = undefined
        $scope.devicepk = undefined
        msgbus.emit("devselreceiver", "icswDeviceInfoOverviewCtrl")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.dev_pk_list = args[0]
            $scope.dev_pk_nmd_list = args[1]
            $scope.devg_pk_list = args[2]
            $scope.dev_pk_md_list = args[3]
            # console.log args
            $scope.addon_devices = []
            if $scope.dev_pk_list.length
                $scope.show = true
                $scope.fetch_info()
            else
                $scope.show = false
        )
        $scope.fetch_info = () ->
            wait_list = [
                Restangular.one(ICSW_URLS.REST_DEVICE_DETAIL.slice(1).slice(0, -2), $scope.dev_pk_list[0]).get()
                Restangular.one(ICSW_URLS.REST_MIN_ACCESS_LEVELS.slice(1)).get( {"obj_type": "device", "obj_list": angular.toJson($scope.dev_pk_list)})
            ]
            # access levels needed ?
            $q.all(wait_list).then((data) ->
                $scope.show_div(data[0], data[1])
            )
        $scope.show_div = (json, access_json) ->
            $scope.devicepk = json.idx
            $scope.permissions = access_json
            $scope.show = true
]).service(
    "DeviceOverviewService",
    [
        "Restangular", "$rootScope", "$templateCache", "$compile", "$modal", "$q", "access_level_service", "msgbus",
        (Restangular, $rootScope, $templateCache, $compile, $modal, $q, access_level_service, msgbus) ->
            return {
                "NewSingleSelection" : (dev) ->
                    if dev.is_meta_device
                        msgbus.emit("devicelist", [[dev.idx], [], [], [dev.idx]])
                    else
                        msgbus.emit("devicelist", [[dev.idx], [dev.idx], [], []])
                "NewOverview" : (event, dev) ->
                    # dev can also be a structure from a devicemap (where only name and id/idx are defined)
                    # create new modal for device
                    # device object with access_levels
                    sub_scope = $rootScope.$new()
                    access_level_service.install(sub_scope)
                    dev_idx = dev.idx
                    sub_scope.devicepk = dev_idx
                    if dev.is_meta_device
                        sub_scope.dev_pk_list = [dev_idx]
                        sub_scope.dev_pk_nmd_list = []
                    else
                        sub_scope.dev_pk_list = [dev_idx]
                        sub_scope.dev_pk_nmd_list = [dev_idx]
                    sub_scope.singledevicemode = 1
                    my_mixin = new angular_modal_mixin(
                        sub_scope,
                        $templateCache,
                        $compile
                        $q
                        "Device Info"
                    )
                    my_mixin.cssClass = "modal-wide"
                    my_mixin.template = "DeviceOverviewTemplate"
                    my_mixin.edit(null, dev_idx)
                    # todo: destroy sub_scope
            }
    ]
).run(["$templateCache", ($templateCache) ->
    $templateCache.put(
        "DeviceOverviewTemplate",
        "<deviceoverview devicepk='devicepk'></deviceoverview>"
    )
]).service("DeviceOverviewSettings", [() ->
    # default value
    def_mode = "general"
    return {
        "get_mode" : () ->
            return def_mode
        "set_mode": (mode) ->
            def_mode = mode
    }
]).directive("deviceoverview", ["$compile", "DeviceOverviewSettings", "$templateCache", ($compile, DeviceOverviewSettings, $templateCache) ->
    return {
        restrict: "EA"
        replace: true
        compile: (element, attrs) ->
            return (scope, iElement, iAttrs) ->
                if attrs["singledevicemode"]?
                    scope.singledevicemode = parseInt(attrs["singledevicemode"])
                scope.current_subscope = undefined
                scope.pk_list = {
                    "general": []
                    "category": []
                    "location": []
                    "network": []
                    "config": []
                    "partinfo": []
                    "variables": []
                    "status_history": []
                    "livestatus": []
                    "monconfig": []
                    "graphing": []
                }
                for key of scope.pk_list
                    scope["#{key}_active"] = false
                if DeviceOverviewSettings.get_mode()
                    _mode = DeviceOverviewSettings.get_mode()
                    scope["#{_mode}_active"] = true
                if scope.singledevicemode
                    scope.$watch(attrs["devicepk"], (new_val) ->
                        if new_val
                            scope.devicepk = new_val
                            scope.new_device_sel()
                    )
                else
                    # possibly multi-device view
                    scope.$watch("dev_pk_list", (new_val) ->
                        if new_val and new_val.length
                            scope.devicepk = new_val[0]
                            scope.new_device_sel()
                    )
                scope.new_device_sel = () ->
                    if scope.dev_pk_list.length > 1
                        scope.addon_text = " (#{scope.dev_pk_list.length})"
                    else
                        scope.addon_text = ""
                    if scope.dev_pk_nmd_list.length > 1
                        scope.addon_text_nmd = " (#{scope.dev_pk_nmd_list.length})"
                    else
                        scope.addon_text_nmd = ""
                    # destroy old subscope, important
                    if scope.current_subscope
                        # check for active div
                        if DeviceOverviewSettings.get_mode()
                            scope.activate(DeviceOverviewSettings.get_mode())
                    else
                        new_scope = scope.$new()
                        new_el = $compile($templateCache.get("icsw.device.info"))(new_scope)
                        iElement.children().remove()
                        iElement.append(new_el)
                        scope.current_subscope = new_scope
                scope.activate = (name) ->
                    DeviceOverviewSettings.set_mode(name)
                    if name in ["category", "location", "network", "partinfo", "status_history", "livestatus", "monconfig"]
                        scope.pk_list[name] = scope.dev_pk_nmd_list
                    else if name in ["config", "variables", "graphing"]
                        scope.pk_list[name] = scope.dev_pk_list
    }
]).controller("deviceinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "access_level_service", "toaster",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service, toaster) ->
        access_level_service.install($scope)
        $scope.show_uuid = false
        $scope.image_url = ""
        $scope.get_image_src = () ->
            img_url = ""
            if $scope._edit_obj.mon_ext_host
                for entry in $scope.mon_ext_host_list
                    if entry.idx == $scope._edit_obj.mon_ext_host
                        img_url = entry.data_image
            return img_url
        $scope.toggle_uuid = () ->
            $scope.show_uuid = !$scope.show_uuid
        $scope.get_full_name = () ->
            if $scope._edit_obj.is_meta_device
                return $scope._edit_obj.full_name.substr(8)
            else
                return $scope._edit_obj.full_name
        $scope.modify = () ->
            if not $scope.form.$invalid
                if $scope.acl_modify($scope._edit_obj, "backbone.device.change_basic")
                    if $scope._edit_obj.is_meta_device
                        $scope._edit_obj.name = "METADEV_" + $scope._edit_obj.name
                    $scope._edit_obj.put().then(() ->
                        if $scope._edit_obj.is_meta_device
                            $scope._edit_obj.name = $scope._edit_obj.name.substr(8)
                        # selectively reload sidebar tree
                        reload_sidebar_tree([$scope._edit_obj.idx])
                    )
            else
                toaster.pop("warning", "form validation problem", "", 0)
]).directive("icswSimpleDeviceInfo", ["$templateCache", "$compile", "$modal", "Restangular", "restDataSource", "$q", "ICSW_URLS", ($templateCache, $compile, $modal, Restangular, restDataSource, $q, ICSW_URLS) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            scope._edit_obj = null
            scope.device_pk = null
            scope.$on("$destroy", () ->
            )
            scope.new_devsel = (in_list) ->
                new_val = in_list[0]
                scope.device_pk = new_val
                wait_list = [
                    restDataSource.reload([ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, {}])
                    restDataSource.reload([ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST, {}])
                    restDataSource.reload([ICSW_URLS.REST_MON_EXT_HOST_LIST, {}])
                    restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_network" : true, "with_monitoring_hint" : true, "with_disk_info" : true, "pks" : angular.toJson([scope.device_pk]), "ignore_cdg" : false, "with_com_info": true}])
                ]
                $q.all(wait_list).then((data) ->
                    #form = data[0][0].form
                    scope.domain_tree_node = data[0]
                    scope.mon_device_templ_list = data[1]
                    scope.mon_ext_host_list = data[2]
                    scope._edit_obj = data[3][0]
                    if scope._edit_obj.is_meta_device
                        scope._edit_obj.name = scope._edit_obj.name.substr(8)
                    element.children().remove()
                    element.append($compile($templateCache.get("device.info.form"))(scope))
                )
            scope.is_device = () ->
                return not scope._edit_obj.is_meta_device
            scope.get_monitoring_hint_info = () ->
                if scope._edit_obj.monitoring_hint_set.length
                    mhs = scope._edit_obj.monitoring_hint_set
                    return "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
                else
                    return "---"
            scope.get_ip_info = () ->
                if scope._edit_obj?
                    ip_list = []
                    for _nd in scope._edit_obj.netdevice_set
                        for _ip in _nd.net_ip_set
                            ip_list.push(_ip.ip)
                    if ip_list.length
                        return ip_list.join(", ")
                    else
                        return "none"
                else
                    return "---"
            scope.get_snmp_scheme_info = () ->
                if scope._edit_obj?
                    _sc = scope._edit_obj.snmp_schemes
                    if _sc.length
                        return ("#{_entry.snmp_scheme_vendor.name}.#{_entry.name}" for _entry in _sc).join(", ")
                    else
                        return "none"
                else
                    return "---"
            scope.get_snmp_info = () ->
                if scope._edit_obj?
                    _sc = scope._edit_obj.DeviceSNMPInfo
                    if _sc
                        return _sc.description
                    else
                        return "none"
                else
                    return "---"
    }
])
