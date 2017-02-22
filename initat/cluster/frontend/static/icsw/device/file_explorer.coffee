# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

# variable related module

setup_progress = angular.module(
    "icsw.fileexplorer",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.fileexplorer")
]).directive("icswFileExplorer",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.file.explorer")
        controller: "icswFileExplorerCtrl"
        scope: true
    }
]).controller("icswFileExplorerCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI", "icswWebSocketService"
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions", "FileUploader"
    "icswDeviceTreeService", "$timeout"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI, icswWebSocketService
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions, FileUploader
    icswDeviceTreeService, $timeout
) ->
########################################################################################################################
# Explorer widget functions
########################################################################################################################

    $scope.treeData  = []

    $scope.start_node_id = 0

    $scope.nodes_to_wait_for = 0
    $scope.nodes_to_wait_for_start = 0

    $scope.file_lines = []

    $scope.treeConfig = {
            contextmenu: {
                show_at_node: false
                items: {
                    view_menu_entry: {
                        label: "View File"
                        action: (obj) ->
                            blockUI.start("Please wait...")
                            node_id = obj.reference.prevObject[0].id
                            for node in $scope.treeData
                                if node.id == node_id
                                    icswSimpleAjaxCall(
                                        {
                                            url: ICSW_URLS.DISCOVERY_LOAD_FILE_LINES
                                            data:
                                                file_path: node.full_path
                                            dataType: 'json'
                                        }
                                    ).then(
                                        (result) ->
                                            $timeout(() ->
                                                $scope.$apply(
                                                  () ->
                                                      $scope.file_lines = result.lines
                                                      blockUI.stop()
                                                )
                                                1
                                            )
                                    )
                                    return
                    }
                }
            }
            core : {
                multiple : false,
                animation: 0,
                check_callback : true,
                worker : true
                stripes: true
            },
            types : {
                folder : {
                    icon : "jstree-folder"
                },
                file : {
                    icon : "jstree-file"
                }
            },
            grid: {
                columns: [
                  {width: "100%", header: "Name"},
                  {width: "100%", value: "size", header: "Size", cellClass: "jstree-grid-line-height"},
                  {width: "100%", value: "type", header: "Type", cellClass: "jstree-grid-line-height"}
                ],
                resizable: true,
                draggable: false,
                contextmenu: false,
            },
            version: 1,
            plugins : ["core", "ui", "types", "sort", "grid", "contextmenu"]
    }

    blockUI.start("Loading data ... 0%")
    icswSimpleAjaxCall(
        {
            url: ICSW_URLS.DISCOVERY_GET_FILE_NODE_TREE
            data:
                directories: ["/home/kaufmann/"]
                start_node_id: $scope.start_node_id
            dataType: 'json'
        }
    ).then(
        (result) ->
            $scope.nodes_to_wait_for = result.tree_nodes.length
            $scope.nodes_to_wait_for_start = result.tree_nodes.length
            Array.prototype.push.apply($scope.treeData, result.tree_nodes)
            $scope.start_node_id = result.new_start_node_id
    )

    $scope.before_node_open = (event, root_node) ->
        root_node = root_node.node
        directories = []
        node_names = []

        for node in $scope.treeData
            if node.parent == root_node.id && !node.children_loaded
                node.children_loaded = true

                directories.push(node.full_path)
                node_names.push(node.id)

        if directories.length > 0
            blockUI.start("Loading data ... 0%")
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.DISCOVERY_GET_FILE_NODE_TREE
                    data:
                        directories: directories
                        node_names: node_names
                        start_node_id: $scope.start_node_id
                    dataType: 'json'
                }
            ).then(
                (result) ->
                    $scope.nodes_to_wait_for = result.tree_nodes.length
                    $scope.nodes_to_wait_for_start = result.tree_nodes.length
                    Array.prototype.push.apply($scope.treeData, result.tree_nodes)
                    $scope.start_node_id = result.new_start_node_id
            )

    $scope.node_created = () ->
        $scope.nodes_to_wait_for -= 1
        if $scope.nodes_to_wait_for == 0
            blockUI.stop()
        else
            load_percent = Math.round((1 - ($scope.nodes_to_wait_for / $scope.nodes_to_wait_for_start)) * 100)
            blockUI.message("Loading data ... " + load_percent + "%")
])
