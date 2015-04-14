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
create_module = angular.module(
    "icsw.device.create",
    [
        "ngSanitize", "ui.bootstrap", "restangular"
    ]
).controller("icswDeviceCreateCtrl", ["$scope", "$timeout", "$window", "$templateCache", "restDataSource", "$q", "blockUI", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $timeout, $window, $templateCache, restDataSource, $q, blockUI, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
        $scope.base_open = true
        $scope.resolve_pending = false
        $scope.device_data = {
            full_name        : ""
            comment          : "new device"
            device_group     : "newgroup"
            ip               : ""
            resolve_via_ip   : true
            routing_capable  : false
            peer             : 0
            icon_name        : "linux40"
        }
        $scope.peers = []
        $scope.rest_map = [
            {"short" : "device_group", "url" : ICSW_URLS.REST_DEVICE_GROUP_LIST}
            {"short" : "mother_server", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options" : {"all_mother_servers" : true}}
            {"short" : "monitor_server", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options" : {"monitor_server_type" : true}}
            {"short" : "domain_tree_node", "url" : ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST}
            {"short" : "peers", "url" : ICSW_URLS.REST_NETDEVICE_PEER_LIST},
            {"short" : "mon_ext_host", "url" : ICSW_URLS.REST_MON_EXT_HOST_LIST}
        ]
        $scope.rest_data = {}
        $scope.all_peers = [{"idx" : 0, "info" : "no peering", "device group name" : "---"}]
        $scope.reload = () ->
            blockUI.start()
            wait_list = []
            for value, idx in $scope.rest_map
                $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
                wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                for value, idx in data
                    $scope.rest_data[$scope.rest_map[idx].short] = value
                # build image lut
                $scope.img_lut = {}
                for value in $scope.rest_data.mon_ext_host
                    $scope.img_lut[value.name] = value.data_image
                # create info strings
                for entry in $scope.rest_data.peers
                    entry.info = "#{entry.devname} on #{entry.device_name}"
                $scope.peers = (entry for entry in $scope.rest_data.peers when entry.routing)
                r_list = [{"idx" : 0, "info" : "no peering", "device group name" : "---"}]
                for entry in $scope.peers 
                    r_list.push(entry)
                $scope.all_peers = r_list
                blockUI.stop()
            )
        $scope.get_image_src = () ->
            img_url = ""
            if $scope.img_lut?
                if $scope.device_data.icon_name of $scope.img_lut
                    img_url = $scope.img_lut[$scope.device_data.icon_name]
            return img_url
        $scope.device_name_changed = () ->
            if not $scope.resolve_pending and $scope.device_data.full_name and not $scope.device_data.ip
                $scope.resolve_name()
        $scope.resolve_name = () ->
            # clear ip
            $scope.device_data.ip = ""
            $scope.resolve_pending = true
            icswCallAjaxService
                url  : ICSW_URLS.MON_RESOLVE_NAME
                data : {
                    "fqdn" : $scope.device_data.full_name
                }
                success : (xml) =>
                    $scope.$apply(
                        $scope.resolve_pending = false
                    )
                    if icswParseXMLResponseService(xml)
                        if $(xml).find("value[name='ip']").length and not $scope.device_data.ip
                            $scope.$apply(
                                $scope.device_data.ip = $(xml).find("value[name='ip']").text()
                            )
        $scope.device_groups = () ->
            return (entry.name for entry in $scope.rest_data.device_group when entry.cluster_device_group == false and entry.enabled)
        $scope.any_peers = () ->
            return if $scope.peers.length > 0 then true else false
        $scope.build_device_dict = () ->
            return {
                "full_name" : $scope.full_name
                "comment"   : $scope.comment
                "device_group" : $scope.device_group
                "ip"           : $scope.ip
            }
        $scope.create_device = () ->
            d_dict = $scope.device_data
            blockUI.start()
            icswCallAjaxService
                url  : ICSW_URLS.MON_CREATE_DEVICE
                data : {
                    "device_data" : angular.toJson(d_dict)
                }
                success : (xml) =>
                    icswParseXMLResponseService(xml)
                    reload_sidebar_tree()
                    blockUI.stop()
                    $scope.reload()
        $scope.reload()
]).directive("icswDeviceCreateMask", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.create.mask")
    }
]).controller("form_ctrl", ["$scope",
    ($scope) ->
])
