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

# Scope variable related module

device_variable_module = angular.module(
    "icsw.variable.scope"
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).directive("icswVariableScopeOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.variable.scope.overview")
        controller: "icswVariableScopeOverviewCtrl"
    }
]).controller("icswVariableScopeOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswDeviceVariableListService", "icswDeviceVariableScopeTreeService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswDeviceVariableListService, icswDeviceVariableScopeTreeService,
) ->
    $scope.struct = {
        # device variable scope tree
        device_variable_scope_tree: undefined
        # data loaded
        loaded: false
    }

    $scope.reload = (devs) ->
        $scope.struct.loaded = false
        $q.all(
            [
                icswDeviceVariableScopeTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_variable_scope_tree = data[0]
                $scope.struct.loaded = true
        )
    $scope.reload()

]).directive("icswVariableScopeTable",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        scope: {
            var_scope: "=icswVariableScope"
        }
        template: $templateCache.get("icsw.variable.scope.table.overview")
        controller: "icswVariableScopeTableCtrl"
    }
]).controller("icswVariableScopeTableCtrl",
[
    "$scope", "$q",
(
    $scope, $q,
) ->
    $scope.struct = {

    }
])
