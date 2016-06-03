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
    "icsw.device.category",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.categorytree",
            {
                url: "/categorytree"
                templateUrl: "icsw/main/category/tree.html"
                icswData: icswRouteExtensionProvider.create
                    pageTitle: "Category tree"
                    rights: ["user.modify_category_tree"]
                    menuEntry:
                        menukey: "dev"
                        name: "Device category"
                        icon: "fa-table"
                        ordering: 14
            }
    )
]).directive("icswDeviceCategoryOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        controller: "icswDeviceCategoryCtrl"
        scope: true
        template: $templateCache.get("icsw.device.category.overview")
    }
]).controller("icswDeviceCategoryCtrl",
[
    "$scope",
(
    $scope,
) ->
    $scope.selected_category = null
    $scope.struct = {
        # devices
        devices: []
    }

    $scope.new_devsel = (devs) ->
        $scope.struct.devices.length = 0
        for dev in devs
            if not dev.is_meta_device
                $scope.struct.devices.push(dev)
])
