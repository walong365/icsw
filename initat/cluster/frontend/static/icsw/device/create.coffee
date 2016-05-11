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
    "icsw.device.create",
    [
        "ngSanitize", "ui.bootstrap", "restangular"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.devicecreate"
        {
            url: "/devicecreate"
            templateUrl: "icsw/main/device/create.html"
            icswData:
                pageTitle: "Create new Device"
                menuHeader:
                    key: "dev"
                    name: "Device"
                    icon: "fa-hdd-o"
                    ordering: 0
                rights: ["user.modify_tree"]
                menuEntry:
                    menukey: "dev"
                    name: "Create new device"
                    icon: "fa-plus-circle"
                    ordering: 5
        }
    )
]).controller("icswDeviceCreateCtrl",
[
    "$scope", "$timeout", "$window", "$templateCache", "$q", "blockUI", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceTreeService", "icswPeerInformationService",
(
    $scope, $timeout, $window, $templateCache, $q, blockUI, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceTreeService, icswPeerInformationService,
) ->
    $scope.base_open = true
    $scope.resolve_pending = false
    $scope.device_data = {
        full_name: "www.orf.at"
        comment: "new device, created at " + moment().format()
        device_group: "newgroup"
        ip: ""
        resolve_via_ip: true
        routing_capable: false
        peer: 0
        icon_name: "linux40"
    }
    $scope.data_ready = false

    $scope.reload = () ->
        blockUI.start("Fetching data from server")
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswPeerInformationService.load($scope.$id, [])
            ]
        ).then(
            (data) ->
                $scope.device_tree = data[0]
                $scope.peer_tree = data[1]
                $scope.device_data.device_group = (entry for entry in $scope.device_tree.group_list when $scope.device_tree.ignore_cdg(entry))[0].name
                if $scope.peer_tree.peer_list.length
                    $scope.device_data.peer = $scope.peer_tree.peer_list[0].idx

                # to speed up testing

                $scope.resolve_name()
                blockUI.stop()
                $scope.data_ready = true
        )
    $scope.reload()

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
        if $scope.device_data.full_name
            $scope.device_data.ip = ""
            $scope.resolve_pending = true
            icswSimpleAjaxCall(
                url  : ICSW_URLS.MON_RESOLVE_NAME
                data : {
                    fqdn: $scope.device_data.full_name
                }
            ).then(
                (xml) ->
                    $scope.resolve_pending = false
                    $scope.device_data.ip = $(xml).find("value[name='ip']").text()
            )

    $scope.create_device = () ->
        d_dict = $scope.device_data
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.DEVICE_CREATE_DEVICE
            data: {
                "device_data" : angular.toJson(d_dict)
            }
        ).then(
            (xml) =>
                if $(xml).find("value[name='device_pk']").length
                    $scope.device_data.full_name = ""
                    defer = $q.defer()
                    $scope.device_tree._fetch_device(
                        parseInt($(xml).find("value[name='device_pk']").text())
                        defer
                        "new device"
                    )
                    defer.promise.then(
                        (ok) ->
                            blockUI.stop()
                        (not_ok) ->
                            blockUI.stop()
                    )
                else
                    blockUI.stop()
        )
]).directive("icswDeviceCreateMask", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.create.mask")
        controller: "icswDeviceCreateCtrl"
    }
])
