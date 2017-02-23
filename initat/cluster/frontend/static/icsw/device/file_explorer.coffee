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

file_explorer = angular.module(
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

    $scope.root_path = undefined

    $scope.waiting_node = undefined
    $scope.nodes_to_wait_for = 0
    $scope.nodes_to_wait_for_start = 0
    $scope.node_id_to_node_data_cache = {}

    $scope.file_string = undefined

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
                                                      $scope.file_string = result.file_string
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

    $scope.after_node_open = (event, root_node) ->
        $scope.waiting_node = root_node
        root_node = $scope.node_id_to_node_data_cache[root_node.node.id]

        if !root_node.children_loaded
            blockUI.start("Loading data ... 0%")
            root_node.children_loaded = true

            $scope.treeInstance.jstree(true).close_node($scope.waiting_node.node, false)
            dummy_node = $scope.node_id_to_node_data_cache[root_node.dummy_node_id]
            _.pull($scope.treeData, dummy_node)

            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.DISCOVERY_GET_FILE_NODE_TREE
                    data:
                        directory: root_node.full_path
                        root_node_name: root_node.id
                        start_node_id: $scope.start_node_id
                        load_child_nodes: 1
                    dataType: 'json'
                }
            ).then(
                (result) ->
                    $scope.start_node_id = result.new_start_node_id
                    $scope.nodes_to_wait_for = result.child_nodes.length
                    $scope.nodes_to_wait_for_start = result.child_nodes.length

                    for node in result.child_nodes
                        $scope.node_id_to_node_data_cache[node.id] = node
                        $scope.treeData.push(node)
            )

    $scope.node_created = () ->
        $scope.nodes_to_wait_for -= 1
        if $scope.nodes_to_wait_for == 0
            $scope.treeInstance.jstree(true).open_node($scope.waiting_node.node, false)
            blockUI.stop()
        else
            load_percent = Math.round((1 - ($scope.nodes_to_wait_for / $scope.nodes_to_wait_for_start)) * 100)
            blockUI.message("Loading data ... " + load_percent + "%")

    $scope.root_path_changed = () ->
        blockUI.start("Loading ...")
        $scope.treeData.length = 0

        $scope.start_node_id = 0

        $scope.waiting_node = undefined
        $scope.nodes_to_wait_for = 0
        $scope.nodes_to_wait_for_start = 0
        $scope.node_id_to_node_data_cache = {}

        $scope.file_string = undefined

        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DISCOVERY_GET_FILE_NODE_TREE
                data:
                    node_text: "/"
                    directory: $scope.root_path
                    root_node_name: "#"
                    start_node_id: $scope.start_node_id
                    load_child_nodes: 0
                dataType: 'json'
            }
        ).then(
            (result) ->
                $scope.start_node_id = result.new_start_node_id
                $scope.treeData.push(result.new_root_node)
                $scope.node_id_to_node_data_cache[result.new_root_node.id] = result.new_root_node
                if result.dummy_node
                    $scope.treeData.push(result.dummy_node)
                    $scope.node_id_to_node_data_cache[result.dummy_node.id] = result.dummy_node

                blockUI.stop()
            )

])
