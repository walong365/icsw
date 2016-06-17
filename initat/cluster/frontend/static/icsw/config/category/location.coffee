# Copyright (C) 2015-2016 init.at
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
    "icsw.config.category.location",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular", "angularFileUpload"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.devlocation", {
            url: "/devlocation"
            templateUrl: "icsw/main/device/location.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Device location"
                rights: ["user.modify_category_tree"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-map-marker"
                    ordering: 40
        }
    )
]).directive("icswConfigCategoryLocationMapEdit",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.map.edit")
        scope: {
            preview_gfx: "=previewGfx"
            preview_close: "=previewClose"
            active_tab: "=activeTab"
            enhance_list: "=gfxEnhanceList"
        }
        controller: "icswConfigCategoryLocationCtrl"
        link: (scope, element, attrs) ->
            scope.set_mode("edit")
    }
]).directive("icswConfigCategoryLocationListEdit",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.list.edit")
    }
]).directive("icswConfigCategoryLocationListShow",
    # not needed right now
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.list.show")
    }
]).directive("icswConfigLocationTabHelper", [() ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.active_tab = ""
            scope.set_active_tab = (tab) ->
                scope.active_tab = tab
            scope.get_active_tab = () ->
                return scope.active_tab
    }
]).directive("icswConfigLocationGfxEnhanceHelper",
[
    "$timeout",
(
    $timeout,
) ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.gfx_list = []
            scope.remove_gfx = ($event, obj) ->
                $timeout(
                    () ->
                        _.remove(scope.gfx_list, (entry) -> return entry.idx == obj.idx)
                    10
                )
    }
]).service("icswCategoryLocationHelper",
[
    "$q",
(
    $q,
) ->
    # implements simple location proxy objects
    class LocationProxy
        # wrap location to add controller-specific filtered entries
        constructor: (@location) ->

    class LocationProxyHelper
        constructor: () ->
            @lut = {}

        get: (loc) ->
            if loc.idx not of @lut
                @lut[loc.idx] = new LocationProxy(loc)
            return @lut[loc.idx]


    return {
        get_location_proxy: () ->
            return new LocationProxyHelper()
    }
]).controller("icswConfigCategoryLocationCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular", "$timeout",
    "icswCSRFService", "$rootScope", "ICSW_SIGNALS", "icswDeviceTreeService",
    "$q", "icswAcessLevelService", "icswCategoryTreeService",
    "FileUploader", "blockUI", "icswTools", "ICSW_URLS", "icswCategoryBackup",
    "icswSimpleAjaxCall", "icswParseXMLResponseService", "toaster",
    "icswComplexModalService", "icswLocationGfxBackup", "icswToolsSimpleModalService",
    "icswCategoryLocationHelper",
(
    $scope, $compile, $templateCache, Restangular, $timeout,
    icswCSRFService, $rootScope, ICSW_SIGNALS, icswDeviceTreeService,
    $q, icswAcessLevelService, icswCategoryTreeService,
    FileUploader, blockUI, icswTools, ICSW_URLS, icswCategoryBackup,
    icswSimpleAjaxCall, icswParseXMLResponseService, toaster,
    icswComplexModalService, icswLocationGfxBackup, icswToolsSimpleModalService,
    icswCategoryLocationHelper,
) ->
    my_loc_helper = icswCategoryLocationHelper.get_location_proxy()
    
    $scope.struct = {
        # tree data valid
        tree_data_valid: false
        # device tree
        device_tree: null
        # category tree
        category_tree: null
        # locations, list of LocationProxy objects
        locations: []
        # orig list (for displaypipe filtering)
        orig_locations: []
        # google maps entry
        google_maps: null
        # mode
        mode: undefined
        # monitoring data
        monitoring_data: undefined
    }

    filter_list = () ->
        # filter location list (run through con_element)
        $scope.struct.locations.length = 0
        for loc in $scope.struct.orig_locations
            _proxy = my_loc_helper.get(loc)
            _dev_idxs = (entry.device for entry in loc.$dml_list)
            _local_idxs = []
            for dev in $scope.struct.monitoring_data.hosts
                if dev.$$icswDevice.idx in _dev_idxs
                    _local_idxs.push(dev.$$icswDevice.idx)
            _proxy.shown_devs = _local_idxs.length
            _proxy.num_devs = _dev_idxs.length 
            if _local_idxs.length
                $scope.struct.locations.push(_proxy)

    rebuild_list = () ->
        $scope.struct.category_tree.build_location_list($scope.struct.orig_locations)
        if $scope.struct.mode == "show"
            if $scope.struct.monitoring_datra?
                filter_list()
                # set new monitoring data
        else
            # copy all
            $scope.struct.locations.length = 0
            for entry in $scope.struct.orig_locations
                $scope.struct.locations.push(my_loc_helper.get(entry))

    reload = () ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.tree_data_valid = true
                $scope.struct.device_tree = data[0]
                $scope.struct.category_tree = data[1]
                rebuild_list()
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
        # force rebuild list because categories may have chagned
        rebuild_list()
    )

    # determine runmode, set by link function
    $scope.set_mode = (mode) ->
        $scope.struct.mode = mode
        reload()
        if $scope.struct.mode == "show"
            $scope.con_element.new_data_notifier.promise.then(
                (resolved) ->
                (rejected) ->
                    console.log "REJ", rejected
                (new_data) ->
                    if not $scope.struct.monitoring_data?
                        $scope.struct.monitoring_data = new_data
                    if $scope.struct.tree_data_valid
                        filter_list()
                        # console.log "nd", new_data
            )

    # utility functions

    $scope.select_location = ($event, loc) ->
        if loc.$$selected
            loc.$$selected = false
        else
            for entry in $scope.struct.locations
                entry.$$selected = false
            loc.$$selected = true

    $scope.toggle_expand = ($event, loc) ->
        if loc.location.$gfx_list.length
            loc.$$expanded = !loc.$$expanded
        else
            loc.$$expanded = false

    $scope.locate = ($event, loc) ->
        # loc is a real location (not a proxy location)
        # locate map on google-maps location
        if $scope.struct.google_maps_fn
            $scope.struct.google_maps_fn("refresh", [loc.latitude, loc.longitude])
            $scope.struct.google_maps_fn("zoom", 11)
        else
            console.error "no google_maps defined"

    # modifiers
    
    # for locations
    $scope.edit_location = ($event, obj) ->
        dbu = new icswCategoryBackup()
        dbu.create_backup(obj)
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = obj

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.category.location.form"))(sub_scope)
                title: "Location entry '#{obj.name}"
                # css_class: "modal-wide"
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2))
                        sub_scope.edit_obj.put().then(
                            (ok) ->
                                $scope.struct.category_tree.reorder()
                                d.resolve("updated")
                            (not_ok) ->
                                d.reject("not updated")
                        )
                    return d.promise

                cancel_callback: (modal) ->
                    dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), $scope.struct.category_tree)
                sub_scope.$destroy()
        )

    # for gfx
    
    $scope.create_or_edit = ($event, create_mode, parent, obj) ->
        if create_mode
            edit_obj = {
                name: "New gfx"
                location: parent.idx
            }
        else
            _.remove($scope.enhance_list, (entry) -> return entry.idx == obj.idx)
            dbu = new icswLocationGfxBackup()
            dbu.create_backup(obj)
            edit_obj = obj
        sub_scope = $scope.$new(false)
        # location references
        sub_scope.loc = parent
        sub_scope.edit_obj = edit_obj
        # copy flag
        sub_scope.create_mode = create_mode

        # init uploaded
        sub_scope.uploader = new FileUploader(
            scope: $scope
            url: ICSW_URLS.BASE_UPLOAD_LOCATION_GFX
            queueLimit: 1
            alias: "gfx"
            removeAfterUpload: true
        )
        icswCSRFService.get_token().then(
            (token) ->
                sub_scope.uploader.formData.push({"csrfmiddlewaretoken": token})
        )
        sub_scope.upload_list = []

        sub_scope.uploader.onBeforeUploadItem = (item) ->
            item.formData[0].location_gfx_id = sub_scope.upload_gfx.idx

        sub_scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            sub_scope.uploader.clearQueue()
            sub_scope.upload_defer.resolve("uploaded")
            return null

        sub_scope.uploader.onErrorItem = (item, response, status, headers) ->
            blockUI.stop()
            sub_scope.uploader.clearQueue()
            toaster.pop("error", "", "error uploading file, please check logs", 0)
            sub_scope.upload_defer.resolve("uploaded")
            return null

        sub_scope.upload_gfx = (gfx_obj) ->
            defer = $q.defer()
            # store gfx
            sub_scope.upload_gfx = gfx_obj
            if sub_scope.uploader.queue.length
                sub_scope.upload_defer = defer
                blockUI.start()
                sub_scope.uploader.uploadAll()
            else
                defer.resolve("done")
            return defer.promise

        sub_scope.uploader.onCompleteItem = (item, response, status, headers) ->
            xml = $.parseXML(response)
            if icswParseXMLResponseService(xml)
                $scope.struct.category_tree.reload_location_gfx_entry(sub_scope.upload_gfx).then(
                    (res) ->
                        sub_scope.upload_defer.resolve("gfx uploaded")
                )

        icswComplexModalService(
            {
                title: "Location Gfx"
                message: $compile($templateCache.get("icsw.location.gfx.form"))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else if sub_scope.uploader.queue.length == 0 and not sub_scope.edit_obj.image_stored
                        toaster.pop("warning", "No graphic defined", "", 0)
                        d.reject("no gfx defined")
                    else
                        if create_mode
                            $scope.struct.category_tree.create_location_gfx_entry(sub_scope.edit_obj).then(
                                (new_gfx) ->
                                    # upload gfx
                                    sub_scope.upload_gfx(new_gfx).then(
                                        (ok) ->
                                            $scope.struct.category_tree.build_luts()
                                            $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), $scope.struct.category_tree)
                                            d.resolve("created gfx")
                                    )
                                (notok) ->
                                    d.reject("not created gfx")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (ok) ->
                                    sub_scope.upload_gfx(sub_scope.edit_obj).then(
                                        (ok) ->
                                            $scope.struct.category_tree.build_luts()
                                            $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), $scope.struct.category_tree)
                                            d.resolve("updated")
                                    )
                                (not_ok) ->
                                    d.reject("not updated")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                # console.log "gfx closed"
                sub_scope.$destroy()
        )

    $scope.delete_gfx = ($event, gfx) ->
        _.remove($scope.enhance_list, (entry) -> return entry.idx == gfx.idx)
        icswToolsSimpleModalService("Really delete LocationGfx #{gfx.name} ?").then(
            (ok) ->
                $scope.struct.category_tree.delete_location_gfx_entry(gfx).then(
                    (ok) ->
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), $scope.struct.category_tree)
                )
        )

    $scope.show_gfx_preview = (gfx) ->
        # console.log $scope.enhance_list.length
        if gfx not in $scope.enhance_list
            $scope.enhance_list.push(gfx)
        # console.log $scope.enhance_list.length
        # console.log (entry.name for entry in $scope.enhance_list)

    # $scope.preview_close = () ->
    #     $scope.preview_gfx = undefined
    
]).directive("icswConfigCategoryTreeMapEnhance",
[
    "$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI",
(
    $templateCache, ICSW_URLS, icswSimpleAjaxCall, blockUI
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.map.enhance")
        scope: {
            preview_gfx: "=previewGfx"
        }
        link: (scope, element, attrs) ->

            scope.display_size = (ds) ->
                scope.display_style = ds
                if ds == "scaled"
                    scope.img_style = "width:100%;"
                else
                    scope.img_style = ""

            scope.display_size("scaled")

            scope.rotate = (degrees) ->
                scope.modify_image(
                    {
                        id: scope.preview_gfx.idx
                        mode: "rotate"
                        degrees: degrees
                    }
                )

            scope.resize = (factor) ->
                scope.modify_image(
                    {
                        id: scope.preview_gfx.idx
                        mode: "resize"
                        factor: factor
                    }
                )

            scope.brightness = (factor) ->
                scope.modify_image(
                    {
                        id: scope.preview_gfx.idx
                        mode: "brightness"
                        factor : factor
                    }
                )

            scope.sharpen = (factor) ->
                scope.modify_image(
                    {
                        id: scope.preview_gfx.idx
                        mode: "sharpen"
                        factor : factor
                    }
                )

            scope.restore = () ->
                scope.modify_image("restore")

            scope.undo = (obj) ->
                scope.modify_image("undo")

            scope.modify_image = (data) ->
                # scope.show_preview(obj)
                if angular.isString(data)
                    data = {
                        id: scope.preview_gfx.idx
                        mode: data
                    }
                blockUI.start()
                icswSimpleAjaxCall(
                    url: ICSW_URLS.BASE_MODIFY_LOCATION_GFX
                    data: data
                ).then(
                    (xml) ->
                        blockUI.stop()
                        scope.preview_gfx.image_url = $(xml).find("value[name='image_url']").text()
                        scope.preview_gfx.icon_url = $(xml).find("value[name='icon_url']").text()
                        scope.preview_gfx.width = parseInt($(xml).find("value[name='width']").text())
                        scope.preview_gfx.height = parseInt($(xml).find("value[name='height']").text())
                )
    }
])
