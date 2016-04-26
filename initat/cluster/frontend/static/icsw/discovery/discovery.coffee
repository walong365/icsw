# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <mallinger@init.at>
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
    "icsw.discovery",
    [
    ]
).directive("icswDiscoveryOverview", ['icswDiscoveryDataService', 'icswDiscoveryDialogService', (icswDiscoveryDataService, icswDiscoveryDialogService) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.discovery.overview'
        link: (scope, el, attrs) ->
            scope.data = icswDiscoveryDataService
            scope.dialog_service = icswDiscoveryDialogService

            scope.selected_device_pks = []
            scope.selected_devices = []
            scope.selected_dispatch_settings = []

            update_selected_devices = () ->
                scope.selected_devices = (dev for dev in icswDiscoveryDataService.device when dev.idx in scope.selected_device_pks)
                scope.selected_dispatch_settings = (ds for ds in icswDiscoveryDataService.dispatch_setting when ds.device in scope.selected_device_pks)
                device_pks_with_dispatch_settings = _.uniq(ds.device for ds in icswDiscoveryDataService.dispatch_setting)
                scope.selected_devices_without_dispatch_settings =
                    (dev for dev in scope.selected_devices when dev.idx not in device_pks_with_dispatch_settings)

            scope.$watch('data.reload_observable', update_selected_devices)
            scope.$watchCollection('selected_device_pks', update_selected_devices)

            scope.new_devsel = (_dev_sel, _devg_sel) ->
                scope.selected_device_pks = _dev_sel

            # msgbus.emit("devselreceiver")
            # msgbus.receive("devicelist", scope, (name, args) ->
            #     scope.new_devsel(args[1])
            # )
    }
]).service("icswDiscoveryDialogService",
    ["Restangular", "ICSW_URLS", "$rootScope", "$q", "$compile", "$templateCache",
    (Restangular, ICSW_URLS, $rootScope, $q, $compile, $templateCache) ->
        CREATE_MODE = 1
        MODIFY_MODE = 1

        show_dialog = (mode, objs) ->
            child_scope = $rootScope.$new()
            child_scope.is_create_mode = mode == CREATE_MODE
            edit_div = $compile($templateCache.get("icsw.discovery.edit_dialog"))(child_scope)
            modal = BootstrapDialog.show
                title: if mode == CREATE_MODE then "Create dispatch setting" else "Edit dispatch setting"
                message: edit_div
                draggable: true
                closable: true
                closeByBackdrop: false
                closeByKeyboard: false,
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
            child_scope.modal = modal

        return {
            show_create_dispatch_setting: () ->
                show_dialog(CREATE_MODE)
            show_modify_dispatch_setting: () ->
                show_dialog(MODIFY_MODE)
        }
]).service("icswDiscoveryDataService", ["Restangular", "ICSW_URLS", "$rootScope", "$q", (Restangular, ICSW_URLS, $rootScope, $q) ->
    rest_map = {
        dispatch_setting: ICSW_URLS.REST_DISPATCH_SETTING_LIST.slice(1)
        device: ICSW_URLS.REST_DEVICE_LIST.slice(1)
    }
    data = {
        reload_observable: 0
    }

    promises = []
    for name, url of rest_map
        data[name] = []

        defer = $q.defer()
        promises.push defer.promise
        do (name, defer) ->
            Restangular.all(url).getList().then((new_data) ->
                defer.resolve([name, new_data])
            )

    $q.all(promises).then((all_new_data) ->
        for entry in all_new_data
            [name, new_data] = entry
            data[name] = new_data

        data.reload_observable += 1
    )

    return data
])
