# Copyright (C) 2012-2017 init.at
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
angular.module(
    "icsw.device.monitoring.overview",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).directive("icswDeviceMonitoringOverviewInfo",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        scope: {
            devicelist: "=icswDeviceList"
        }
        restrict : "EA"
        template : $templateCache.get("icsw.device.monitoring.overview.info")
        controller: "icswDeviceMonitoringOverviewInfoCtrl"
        link: (scope, element, attrs) ->
            scope.do_init()

    }
]).controller("icswDeviceMonitoringOverviewInfoCtrl",
[
    "$scope", "Restangular", "$q", "ICSW_URLS",
    "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", "icswDeviceTreeService", "icswMonitoringBasicTreeService",
    "icswAccessLevelService", "icswActiveSelectionService", "icswDeviceBackup", "icswDeviceGroupBackup",
    "icswDeviceTreeHelperService", "icswComplexModalService", "toaster", "$compile", "$templateCache",
    "icswCategoryTreeService", "icswToolsSimpleModalService", "icswDialogDeleteService",
(
    $scope, Restangular, $q, ICSW_URLS,
    $rootScope, ICSW_SIGNALS, icswDomainTreeService, icswDeviceTreeService, icswMonitoringBasicTreeService,
    icswAccessLevelService, icswActiveSelectionService, icswDeviceBackup, icswDeviceGroupBackup,
    icswDeviceTreeHelperService, icswComplexModalService, toaster, $compile, $templateCache,
    icswCategoryTreeService, icswToolsSimpleModalService, icswDialogDeleteService,
) ->
    $scope.struct = {
        # data is valid
        data_valid: false
        # device object
        edit_obj: $scope.devicelist[0]
        # device tree
        device_tree: undefined
        # monitoring tree
        monitoring_tree: undefined
        # category tree
    }

    create_info_fields = (obj) ->
        if obj.monitoring_hint_set.length
            mhs = obj.monitoring_hint_set
            hints = "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
        else
            hints = "---"

        obj.$$monitoring_hint_info = hints

    icswAccessLevelService.install($scope)

    $scope.do_init = () ->
        $scope.struct.data_valid = false
        icswDeviceTreeService.load($scope.$id).then(
            (tree) ->
                $scope.struct.device_tree = tree
                trace_devices =  $scope.struct.device_tree.get_device_trace($scope.devicelist)
                dt_hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, trace_devices)
                $q.all(
                    [
                        icswMonitoringBasicTreeService.load($scope.$id)
                        $scope.struct.device_tree.enrich_devices(
                            dt_hs
                            [
                                "monitoring_hint_info"
                            ]
                        )
                   ]
                ).then(
                    (data) ->
                        $scope.struct.monitoring_tree = data[0]
                        $scope.edit_obj = $scope.struct.edit_obj
                        create_info_fields($scope.edit_obj)
                        $scope.struct.data_valid = true
                )
            )

        # return defer.promise

    $scope.modify = ($event) ->
        dbu = new icswDeviceBackup()
        template_name = "icsw.device.monitoring.overview.edit"
        title = "Modify Device Monitoring Settings"
        dbu.create_backup($scope.edit_obj)
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = $scope.edit_obj
        sub_scope.struct = $scope.struct

        # for fields, tree can be the basic or the cluster tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                title: title
                css_class: "modal-wide"
                ok_label: "Save"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        sub_scope.edit_obj.put().then(
                            (ok) ->
                                $scope.struct.device_tree.reorder()
                                d.resolve("updated")
                            (not_ok) ->
                                d.reject("not updated")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                # recreate info fields
                create_info_fields($scope.edit_obj)
        )

])