# Copyright (C) 2012-2016 init.at
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
]).service("icswVariableScopeService",
[
    "$compile", "$templateCache", "$rootScope", "$q",
    "icswComplexModalService", "icswFormTools", "icswDeviceVariableScopeBackup",
(
    $compile, $templateCache, $rootScope, $q,
    icswComplexModalService, icswFormTools, icswDeviceVariableScopeBackup,
) ->
    create_or_edit_scope = ($event, create, var_scope, dvs_tree) ->
        sub_scope = $rootScope.$new(true)
        console.log "cs"
        sub_scope.create = create
        if create
            sub_scope.edit_obj = {
                name: "varscope"
                description: "New Variable scope"
                priority: 50
                fixed: true
            }
        else
            dbu = new icswDeviceVariableScopeBackup()
            dbu.create_backup(var_scope)
            sub_scope.edit_obj = var_scope
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.variable.scope.form"))(sub_scope)
                title: "Variable Scope '#{sub_scope.edit_obj.name}'"
                ok_label: if create then "Create" else "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if icswFormTools.check_form(sub_scope.form_data, d)
                        if create
                            # single creation
                            sub_scope.edit_obj.editable = true
                            dvs_tree.create_variable_scope(sub_scope.edit_obj).then(
                                (new_conf) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            dvs_tree.update_variable_scope(sub_scope.edit_obj).then(
                                (new_var) ->
                                    d.resolve("updated")
                                (not_ok) ->
                                    d.reject("not updated")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(var_scope)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )
    return {
        create_or_edit_scope: (event, create, var_scope, dvs_tree) ->
            return create_or_edit_scope(event, create, var_scope, dvs_tree)
    }

]).controller("icswVariableScopeOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswDeviceVariableListService", "icswDeviceVariableScopeTreeService",
    "icswVariableScopeService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswDeviceVariableListService, icswDeviceVariableScopeTreeService,
    icswVariableScopeService,
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

    $scope.create_scope = ($event) ->
        icswVariableScopeService.create_or_edit_scope($event, true, null, $scope.struct.device_variable_scope_tree)

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
    "$scope", "$q", "icswToolsSimpleModalService", "blockUI", "toaster",
    "icswDeviceVariableScopeTreeService", "$templateCache", "$compile", "icswComplexModalService",
    "icswDeviceVariableFunctions", "icswDVSAllowedNameBackup", "icswVariableScopeService",
(
    $scope, $q, icswToolsSimpleModalService, blockUI, toaster,
    icswDeviceVariableScopeTreeService, $templateCache, $compile, icswComplexModalService,
    icswDeviceVariableFunctions, icswDVSAllowedNameBackup, icswVariableScopeService,
) ->
    $scope.struct = {
        # dvs tree
        dvs_tree: undefined
        # data_ready
        data_ready: false
    }
    _load = () ->
        $scope.struct.data_ready = false
        $q.all(
            [
                icswDeviceVariableScopeTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.dvs_tree = data[0]
                $scope.struct.data_ready = true
        )
    _load()

    $scope.edit_var_scope = ($event, var_scope) ->
        icswVariableScopeService.create_or_edit_scope(
            $event
            false
            var_scope
            $scope.struct.dvs_tree
        )

    $scope.delete_dvs_an = ($event, entry) ->
        icswToolsSimpleModalService("Really delete entry '#{entry.name}' in Scope '#{$scope.var_scope.name}' ?").then(
            (ok) ->
                blockUI.start()
                $scope.struct.dvs_tree.delete_dvs_an(entry).then(
                    (ok) ->
                        blockUI.stop()
                    (not_ok) ->
                        blockUI.stop()
                )

        )

    create_or_edit = ($event, var_scope, create, entry) ->
        sub_scope = $scope.$new(true)
        if create
            entry = {
                device_variable_scope: var_scope.idx
                name: "allowed_name"
                unique: false
                group: ""
                forced_type: icswDeviceVariableFunctions.get_form_dict("var_type")[0].idx
                description: "new allowed name"
            }
        else
            dbu = new icswDVSAllowedNameBackup()
            dbu.create_backup(entry)
        sub_scope.type_list = icswDeviceVariableFunctions.get_form_dict("var_type")
        sub_scope.$$forced_type_str = icswDeviceVariableFunctions.resolve("var_type", entry.forced_type)
        sub_scope.edit_obj = entry
        sub_scope.create = create
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.variable.scope.dvsan.form"))(sub_scope)
                title: "Allowed Scope Variable in Scope '#{var_scope.name}'"
                ok_label: if create then "Create" else "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            # single creation
                            sub_scope.edit_obj.editable = true
                            $scope.struct.dvs_tree.create_dvs_an(var_scope, sub_scope.edit_obj).then(
                                (new_conf) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            $scope.struct.dvs_tree.update_dvs_an(var_scope, sub_scope.edit_obj).then(
                                (new_var) ->
                                    d.resolve("updated")
                                (not_ok) ->
                                    d.reject("not updated")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(entry)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

    $scope.create_dvs_an = ($event, var_scope) ->
        create_or_edit($event, var_scope, true, null)

    $scope.edit_dvs_an = ($event, var_scope, entry) ->
        create_or_edit($event, var_scope, false, entry)
])
