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
DT_FORM = "YYYY-MM-DD HH:mm"

kernel_module = angular.module(
    "icsw.config.kernel",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).service("icswKernelTree",
[
    "ICSW_URLS", "$q", "$rootScope",
(
    ICSW_URLS, $q, $rootScope,
) ->
    class icswKernelTree
        constructor: (kernel_list) ->
            @list = []
            @update(kernel_list)

        update: (kernel_list) =>
            @list.length = 0
            for entry in kernel_list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")

        delete_kernel: (kernel) ->
            d = $q.defer()
            kernel.remove().then(
                (ok) =>
                    # partition table deleted
                    _.remove(@list, (entry) -> return entry.idx == kernel.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_ok) =>
                    d.reject("not deleted")
            )
            return d.promise

        update_kernel: (kernel) ->
            d = $q.defer()
            kernel.put().then(
                (ok) =>
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        resolve_devices: (dev_tree) ->
            for kern in @list
                _dev_list = []
                for _dev in kern.new_kernel
                    if _dev of dev_tree.all_lut
                        _dev_list.push(dev_tree.all_lut[_dev].full_name)
                if _dev_list.length
                    kern.$$new_kernel = _dev_list.join(", ")
                else
                    kern.$$new_kernel = "---"

]).service("icswKernelTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "$rootScope", "ICSW_SIGNALS", "icswKernelTree",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, $rootScope, ICSW_SIGNALS, icswKernelTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_KERNEL_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** kernel tree loaded ***"
                if _result
                    # for reload
                    _result.update(data[0])
                else
                    _result = new icswKernelTree(data[0])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), _result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            return load_data(client).promise
    }
]).directive("icswKernelOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        controller: "icswKernelOverviewCtrl"
        template: $templateCache.get("icsw.kernel.overview")
    }
]).controller("icswKernelOverviewCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular", "blockUI", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswKernelTreeService", "$q", "icswComplexModalService", "toaster", "icswKernelBackup",
    "icswToolsSimpleModalService", "icswDeviceTreeService",
(
    $scope, $compile, $templateCache, restangular, blockUI, ICSW_URLS, icswSimpleAjaxCall,
    icswKernelTreeService, $q, icswComplexModalService, toaster, icswKernelBackup,
    icswToolsSimpleModalService, icswDeviceTreeService,
) ->
    $scope.struct = {
        # loading flag
        loading: false
        # kernel tree
        kernel_tree: undefined
        # device tree
        device_tree: undefined
    }
    $scope.reload = (reload) ->
        $scope.struct.loading = true
        if reload
            _w_list = [icswKernelTreeService.reload($scope.$id)]
        else
            _w_list = [icswKernelTreeService.load($scope.$id)]
        _w_list.push(icswDeviceTreeService.load($scope.$id))
        $q.all(_w_list).then(
            (data) ->
                $scope.struct.kernel_tree = data[0]
                $scope.struct.device_tree = data[1]
                $scope.struct.kernel_tree.resolve_devices($scope.struct.device_tree)
                $scope.struct.loading = false
        )
    $scope.reload(false)

    $scope.bump_version = (obj) ->
        obj.version++
        obj.put()

    $scope.bump_release = (obj) ->
        obj.release++
        obj.put()

    # edit functions
    $scope.edit = ($event, kernel) ->
        dbu = new icswKernelBackup()
        dbu.create_backup(kernel)

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = kernel

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.kernel.form"))(sub_scope)
                title: "Settings for kernel #{kernel.name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving kernel data...")
                        $scope.struct.kernel_tree.update_kernel(kernel).then(
                            (ok) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup(kernel)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

    $scope.delete = ($event, kernel) ->
        icswToolsSimpleModalService("Really delete Kernel #{kernel.name} ?").then(
            () =>
                blockUI.start("deleting kernel")
                $scope.struct.kernel_tree.delete_kernel(kernel).then(
                    (ok) ->
                        blockUI.stop()
                    (not_ok) ->
                        blockUI.stop()
                )
        )

    $scope.scan_for_kernels = () =>
        blockUI.start("Scanning for new kernels")
        icswSimpleAjaxCall(
            url: ICSW_URLS.SETUP_RESCAN_KERNELS
            title: "scanning for new kernels"
        ).then(
            (xml) ->
                $scope.reload(true)
                blockUI.stop()
            (error) ->
                $scope.reload(true)
                blockUI.stop()
        )

]).directive("icswKernelHead",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.kernel.head")
    }
]).directive("icswKernelRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.kernel.row")
    }
])
