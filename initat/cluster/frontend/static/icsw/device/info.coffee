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
            template: '<icsw-simple-device-info icsw-sel-man="0" icsw-sel-man-sel-mode="D"></icsw-simple-device-info>'
            data:
                pageTitle: "Device info"
                rights: ["user.modify_tree"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-bars"
                    ordering: 10
        }
    )
]).service("DeviceOverviewService", ["Restangular", "$rootScope", "$templateCache", "$compile", "$uibModal", "$q", "icswAcessLevelService", "icswComplexModalSevice",
    (Restangular, $rootScope, $templateCache, $compile, $uibModal, $q, icswAcessLevelService, icswComplexModalSevice) ->
        return (event, devicelist) ->
            # devicelist is a list of fully populated devices
            # create new modal for device
            # device object with access_levels
            sub_scope = $rootScope.$new()
            console.log "devlist", devicelist
            icswAcessLevelService.install(sub_scope)
            # pk list of devices
            sub_scope.dev_pk_list = (dev.idx for dev in devicelist)
            # pk list of devices without meta-devices
            sub_scope.dev_pk_nmd_list = (dev.idx for dev in devicelist when !dev.is_meta_device)
            icswComplexModalSevice(
                {
                    message: $compile("<icsw-device-overview></icsw-device-overview>")(sub_scope)
                    title: "Device Info"
                    css_class: "modal-wide"
                    closable: true
                }
            ).then(
                (closeinfo) ->
                    console.log "close deviceoverview #{closeinfo}"
                    sub_scope.$destroy()
            )
            # my_mixin.edit(null, devicelist[0])
            # todo: destroy sub_scope
]).service("DeviceOverviewSettings", [() ->
    # default value
    def_mode = "general"
    return {
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
                _cur_mode = DeviceOverviewSettings.get_mode()
                scope["#{_cur_mode}_active"] = true
                scope.activate = (name) ->
                    DeviceOverviewSettings.set_mode(name)
                    if name in ["network", "status_history", "livestatus", "category"]
                        scope.pk_list[name] = scope.dev_pk_nmd_list
                    else if name in ["config", "graphing", "device_variable"]
                        scope.pk_list[name] = scope.dev_pk_list
                if scope.dev_pk_list.length > 1
                    scope.addon_text = " (#{scope.dev_pk_list.length})"
                else
                    scope.addon_text = ""
                if scope.dev_pk_nmd_list.length > 1
                    scope.addon_text_nmd = " (#{scope.dev_pk_nmd_list.length})"
                else
                    scope.addon_text_nmd = ""
                # destroy old subscope, important
                scope.$on("$destroy", () -> console.log "Destroy Device-overview scope")
                new_el = $compile($templateCache.get("icsw.device.info"))(scope)
                iElement.children().remove()
                iElement.append(new_el)
    }
]).controller("deviceinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "icswAcessLevelService", "toaster",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, icswAcessLevelService, toaster) ->
        icswAcessLevelService.install($scope)
        $scope.show_uuid = false
        $scope.image_url = ""
        $scope.get_image_src = () ->
            img_url = ""
            if $scope._edit_obj.mon_ext_host
                for entry in $scope.mon_ext_host_list
                    if entry.idx == $scope._edit_obj.mon_ext_host
                        img_url = entry.data_image
            return img_url
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
                        # FIXME, TODO
                        # reload_sidebar_tree([$scope._edit_obj.idx])
                    )
            else
                toaster.pop("warning", "form validation problem", "", 0)
]).directive("icswSimpleDeviceInfo", ["$templateCache", "$compile", "$uibModal", "Restangular", "restDataSource", "$q", "ICSW_URLS", ($templateCache, $compile, $uibModal, Restangular, restDataSource, $q, ICSW_URLS) ->
    return {
        restrict : "EA"
        controller: "deviceinfo_ctrl"
        link : (scope, element, attrs) ->
            scope._edit_obj = null
            scope.device_pk = null
            scope.$on("$destroy", () ->
            )
            scope.toggle_uuid = () ->
                scope.show_uuid = !scope.show_uuid
            scope.new_devsel = (in_list) ->
                if in_list.length > 0
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
                        element.append($compile($templateCache.get("icsw.device.info.form"))(scope))
                    )
                else
                    element.children().remove()
                    element.append($compile('<h2>Details</h2><alert type="warning" style="max-width: 500px">No devices selected.</alert>')(scope))
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
