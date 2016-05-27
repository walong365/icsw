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
    "icsw.config.image",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.imagekernel", {
            url: "/imagekernel"
            templateUrl: "icsw/main/imagekernel.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Images and Kernels"
                rights: ["image.modify_images", "kernel.modify_kernels"]
                licenses: ["netboot"]
                menuEntry:
                    menukey: "cluster"
                    icon: "fa-linux"
                    ordering: 25
        }
    )
]).service("icswImageTree",
[
    "ICSW_URLS", "$q", "$rootScope",
(
    ICSW_URLS, $q, $rootScope,
) ->
    class icswImageTree
        constructor: (image_list, arch_list) ->
            @list = []
            @arch_list =[]
            @update(image_list, arch_list)

        update: (image_list, arch_list) =>
            @list.length = 0
            for entry in image_list
                @list.push(entry)
            @arch_list.length = 0
            for entry in arch_list
                @arch_list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @arch_lut = _.keyBy(@arch_list, "idx")

        delete_image: (image) ->
            d = $q.defer()
            image.remove().then(
                (ok) =>
                    # partition table deleted
                    _.remove(@list, (entry) -> return entry.idx == image.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_ok) =>
                    d.reject("not deleted")
            )
            return d.promise

        update_image: (image) ->
            d = $q.defer()
            image.put().then(
                (ok) =>
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        resolve_devices: (dev_tree) ->
            for im in @list
                _dev_list = []
                for _dev in im.new_image
                    if _dev of dev_tree.all_lut
                        _dev_list.push(dev_tree.all_lut[_dev].full_name)
                if _dev_list.length
                    im.$$new_image = _dev_list.join(", ")
                else
                    im.$$new_image = "---"

]).service("icswImageTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "$rootScope", "ICSW_SIGNALS", "icswImageTree",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, $rootScope, ICSW_SIGNALS, icswImageTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_IMAGE_LIST, {}
        ]
        [
            ICSW_URLS.REST_ARCHITECTURE_LIST, {}
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
                console.log "*** image tree loaded ***"
                if _result
                    # for reload
                    _result.update(data[0], data[1])
                else
                    _result = new icswImageTree(data[0], data[1])
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
]).directive("icswImageOverview",
[
    "$templateCache",
 (
     $templateCache
 ) ->
     return {
         restrict: "EA"
         controller: "icswImageOverviewCtrl"
         template: $templateCache.get("icsw.image.overview")
     }
]).controller("icswImageOverviewCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular", "blockUI", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswImageTreeService", "$q", "icswComplexModalService",
    "toaster", "icswImageBackup", "icswToolsSimpleModalService", "icswDeviceTreeService",
(
    $scope, $compile, $templateCache, Restangular, blockUI, ICSW_URLS,
    icswSimpleAjaxCall, icswImageTreeService, $q, icswComplexModalService,
    toaster, icswImageBackup, icswToolsSimpleModalService, icswDeviceTreeService,
) ->
    $scope.struct = {
        # loading flag
        loading: false
        # image tree
        image_tree: undefined
        # device tree
        device_tree: undefined
        # new images found
        new_images: []
    }
    $scope.reload = (reload) ->
        $scope.struct.loading = true
        if reload
            _w_list = [icswImageTreeService.reload($scope.$id)]
        else
            _w_list = [icswImageTreeService.load($scope.$id)]
        _w_list.push(icswDeviceTreeService.load($scope.$id))
        $q.all(_w_list).then(
            (data) ->
                $scope.struct.image_tree = data[0]
                $scope.struct.device_tree = data[1]
                $scope.struct.image_tree.resolve_devices($scope.struct.device_tree)
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
    $scope.edit = ($event, image) ->
        dbu = new icswImageBackup()
        dbu.create_backup(image)

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = image

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.image.form"))(sub_scope)
                title: "Settings for image #{image.name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving image data...")
                        $scope.struct.image_tree.update_image(image).then(
                            (ok) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup(image)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

    $scope.delete = ($event, image) ->
        icswToolsSimpleModalService("Really delete Image #{image.name} ?").then(
            () =>
                blockUI.start("deleting image")
                $scope.struct.image_tree.delete_image(image).then(
                    (ok) ->
                        blockUI.stop()
                    (not_ok) ->
                        blockUI.stop()
                )
        )

    $scope.scan_for_images = () =>
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.SETUP_RESCAN_IMAGES
            title: "scanning for new images"
        ).then(
            (xml) ->
                blockUI.stop()
                $scope.struct.new_images.length = 0
                $(xml).find("found_images found_image").each (idx, new_img) =>
                    new_img = $(new_img)
                    new_obj = {
                        name: new_img.attr("name")
                        vendor: new_img.attr("vendor")
                        version: new_img.attr("version")
                        arch: new_img.attr("arch")
                        present: parseInt(new_img.attr("present"))
                    }
                    $scope.struct.new_images.push(new_obj)
            (error) ->
                $scope.struct.new_images.length = 0
                blockUI.stop()
        )

    $scope.take_image = (obj) =>
        blockUI.start("Take new image...")
        icswSimpleAjaxCall(
            url: ICSW_URLS.SETUP_USE_IMAGE
            data:
                img_name: obj.name
            title: "scanning for new images"
        ).then(
            (xml) ->
                blockUI.stop()
                $scope.struct.new_images.length = 0
                $scope.reload(true)
            (error) ->
                blockUI.stop()
        )

]).directive("icswImageHead",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.image.head")
    }
]).directive("icswImageRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.image.row")
    }
]).directive("icswImageBuildButton",
[
    "ICSW_URLS", "icswSimpleAjaxCall",
(
    ICSW_URLS, icswSimpleAjaxCall
) ->
    return {
        restrict: 'E'
        template: """
<icsw-tools-button type="image" size="xs" ng-click="build_image()"></icsw-tools-button>
"""
        scope:
            'reload': '='
            'image': '&'
        link: (scope, el, attrs) ->
            scope.build_image = () ->
                icswSimpleAjaxCall(
                    url: ICSW_URLS.SETUP_BUILD_IMAGE
                    data:
                        image_pk: scope.image().idx
                ).then(
                    (xml) ->
                        scope.reload()
                )
    }
]).directive("icswImageHeadNew",
[
    "$templateCache",
(
    $templateCache
) ->
    # used in new images table
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.image.head.new")
    }
]).directive("icswImageRowNew",
[
    "$templateCache",
(
    $templateCache
) ->
    # used in new images table
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.image.row.new")
    }
]).directive("icswImageNewImages",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: 'EA'
        template: $templateCache.get("icsw.image.new.images")
    }
])
