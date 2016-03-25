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
    "icsw.config.category_location",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.devlocation", {
            url: "/devlocation"
            templateUrl: "icsw/main/device/location.html"
            data:
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
        }
        controller: "icswConfigCategoryLocationCtrl"
    }
]).directive("icswConfigCategoryLocationShow",
# not in use right now, was in Dashboard
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.show")
        scope: {
            ls_devsel: "=lsDevsel"
            ls_filter: "=lsFilter"
        }
        controller: "icswConfigCategoryLocationCtrl"
        link: (scope, element, attrs) ->
            if attrs["lsFilter"]?
                scope.$watch("ls_filter", (new_val) ->
                    if new_val
                        scope.$watch(
                            new_val.changed
                            (new_filter) ->
                                scope.redraw_svgs()
                        )
                )
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
]).controller("icswConfigCategoryLocationCtrl", [
    "$scope", "$compile", "$templateCache", "Restangular", "$timeout",
    "icswCSRFService", "$rootScope", "ICSW_SIGNALS", "icswDeviceTreeService",
    "$q", "icswAcessLevelService", "icswCategoryTreeService",
    "FileUploader", "blockUI", "icswTools", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswParseXMLResponseService", "toaster",
    "icswConfigCategoryTreeFetchService", "icswComplexModalService",
    "icswLocationGfxBackup",
(
    $scope, $compile, $templateCache, Restangular, $timeout,
    icswCSRFService, $rootScope, ICSW_SIGNALS, icswDeviceTreeService,
    $q, icswAcessLevelService, icswCategoryTreeService,
    FileUploader, blockUI, icswTools, ICSW_URLS,
    icswSimpleAjaxCall, icswParseXMLResponseService, toaster,
    icswConfigCategoryTreeFetchService, icswComplexModalService,
    icswLocationGfxBackup,
) ->
    # mixins
    $scope.gfx_mixin = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "gfx")
    $scope.gfx_mixin.use_modal = true
    $scope.gfx_mixin.use_promise = true
    $scope.gfx_mixin.new_object = (scope) -> return scope.new_location_gfx()
    $scope.gfx_mixin.delete_confirm_str = (obj) -> return "Really delete location graphic '#{obj.name}' ?"
    $scope.gfx_mixin.modify_rest_url = ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2)
    $scope.gfx_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_LOCATION_GFX_LIST.slice(1))
    $scope.gfx_mixin.create_template = "location.gfx.form"
    $scope.gfx_mixin.edit_template = "location.gfx.form"
    # edit mixin for cateogries
    $scope.locations = []
    $scope.map = null
    #msgbus.receive("icsw.config.locations.changed.tree", $scope, () ->
    #    # receiver for global changes from tree
    #    $scope.reload()
    #)
    $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_GOOGLE_MAPS_LOADED"), (event, map) ->
        $scope.map = map
    )
    $scope.struct = {
        device_tree: null
        category_tree: null
        locations: []
    }
    $scope.reload = () ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.category_tree = data[1]
                $scope.rebuild_list()
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
        $scope.rebuild_list()
    )

    $scope.rebuild_list = () ->
        $scope.struct.locations.length = []
        _ct = $scope.struct.category_tree
        for entry in _ct.list
            if _ct.is_location(entry, min_depth=2)
                if not entry.$$expanded?
                    entry.$$expanded = false
                if not entry.$gfx_list.length
                    entry.$$expanded = false
                $scope.struct.locations.push(entry)

    # utility functions
        
    $scope.toggle_expand = ($event, loc) ->
        if loc.$gfx_list.length
            loc.$$expanded = !loc.$$expanded
        else
            loc.$$expanded = false

    $scope.locate = ($event, loc) ->
        $scope.map.control.refresh(
            {
                latitude: loc.latitude
                longitude: loc.longitude
            }
        )
        $scope.map.control.getGMap().setZoom(11)

    # modifiers
    
    $scope.create_or_edit = ($event, create_mode, parent, obj) ->
        if create_mode
            edit_obj = {
                name: "New gfx"
                location: parent.idx
            }
        else
            dbu = new icswLocationGfxBackup()
            dbu.create_backup(obj)
            edit_obj = obj
        sub_scope = $scope.$new(false)
        sub_scope.loc = parent
        sub_scope.edit_obj = edit_obj

        # init uploaded
        sub_scope.uploader = new FileUploader(
            scope : $scope
            url : ICSW_URLS.BASE_UPLOAD_LOCATION_GFX
            queueLimit : 1
            alias : "gfx"
            removeAfterUpload : true
        )
        icswCSRFService.get_token().then(
            (token) ->
                sub_scope.uploader.formData.push({"csrfmiddlewaretoken": token})
        )
        sub_scope.upload_list = []
        # sub_scope.uploader.onBeforeUploadItem = (item) ->
        #    item.formData[0].location_id = $scope.cur_location_gfx.idx
        #    blockUI.start()
        sub_scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            sub_scope.uploader.clearQueue()
            return null
        sub_scope.uploader.onErrorItem = (item, response, status, headers) ->
            blockUI.stop()
            sub_scope.uploader.clearQueue()
            toaster.pop("error", "", "error uploading file, please check logs", 0)
            return null

        sub_scope.uploader.onCompleteItem = (item, response, status, headers) ->
            xml = $.parseXML(response)
            if icswParseXMLResponseService(xml)
                console.log xml
                Restangular.one(ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2), $scope.cur_location_gfx.idx).get().then(
                    (data) ->
                        for _copy in ["width", "height", "uuid", "content_type", "locked", "image_stored", "icon_url", "image_name", "image_url"]
                            $scope.cur_location_gfx[_copy] = data[_copy]
                )

        icswComplexModalService(
            {
                title: "Location Gfx"
                message: $compile($templateCache.get("icsw.location.gfx.form"))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                ok_callback: (modal) ->
                    console.log sub_scope.edit_obj
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else if sub_scope.uploader.queue.length == 0
                        toaster.pop("warning", "No graphic defined", "", 0)
                        d.reject("no gfx defined")
                    else
                        console.log sub_scope.uploader.queue.length
                        if create_mode
                            console.log "c", sub_scope.edit_obj
                        d.resolve("ok")
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
                console.log "gfx closed"
                sub_scope.$destroy()
        )
    _is_location = (obj) ->
        return (obj.depth > 1) and obj.full_name.split("/")[1] == "location"
    $scope.reloadx = () ->
        if $scope.ls_devsel?
            $scope.$watch(
                $scope.ls_devsel.changed
                (changed) ->
                    _dev_sel = $scope.ls_devsel.get()
                    $scope.reload_now(_dev_sel)
            )
        else
            $scope.reload_now(null)
    $scope.reload_now = (_dev_sel) ->
        $scope.dev_sel = _dev_sel
        icswConfigCategoryTreeFetchService.fetch($scope.$id, _dev_sel).then((data) ->
            $scope.entries = data[0]
            for entry in $scope.entries
                entry.open = false
            $scope.location_gfxs = data[1]
            $scope.dml_list = data[2]
            $scope.dtl_list = data[3]
            # device to location map
            $scope.dtl_map = {}
            for _entry in $scope.dtl_list
                # device -> location
                $scope.dtl_map[_entry[0]] = _entry[1]
            $scope.rebuild_cat()
    )
    $scope.rebuild_cat = () ->
        $scope.locations = (entry for entry in $scope.entries when _is_location(entry))
        $scope.gfx_lut = icswTools.build_lut($scope.location_gfxs)
        $scope.loc_lut = icswTools.build_lut($scope.locations)
        for entry in $scope.locations
            entry.dev_pks = []
        for entry in $scope.location_gfxs
            # entry.num_dml = 0
            entry.dev_pks = []
        for entry in $scope.dml_list
            $scope.gfx_lut[entry.location_gfx].dev_pks.push(entry.device)
            $scope.loc_lut[entry.location].dev_pks.push(entry.device)
        for entry in $scope.locations
            entry.location_gfxs = (_gfx for _gfx in $scope.location_gfxs when _gfx.location == entry.idx)
        for entry in $scope.dtl_list
            $scope.loc_lut[entry[1]].dev_pks.push(entry[0])
        if $scope.dev_sel
            # filter locations if dev_sel is set (not config)
            $scope.locations = (entry for entry in $scope.locations when entry.dev_pks.length)
            $scope.redraw_svgs()
    $scope.redraw_svgs = () ->
        if $scope.dtl_list? and $scope.dtl_list.length
            _wait_list = []
            for loc in $scope.locations
                if loc.dev_pks.length
                    _wait_list.push(_svg_to_png(loc.idx, loc.dev_pks))
            $q.all(_wait_list).then((data) ->
                for _tuple in data
                    $scope.loc_lut[_tuple[0]].svg_url = _tuple[1]
            )
    _svg_to_png = (loc_pk, dev_pks) ->
        defer = $q.defer()
        sub_scope = $scope.$new(true, $scope)
        sub_scope.response = {"drawn": 0}
        sub_scope.ls_filter = $scope.ls_filter
        pk_str = _.uniq(dev_pks).join(",")
        _el = $compile("<icsw-device-livestatus-map devicepk='#{pk_str}' is-drawn='response.drawn' ls-filter='ls_filter'></icsw-device-livestatus-map>")(sub_scope)
        sub_scope.$watch('response.drawn', (new_val) ->
            if new_val
                $timeout(
                    () ->
                        icswSimpleAjaxCall(
                            hidden: true
                            url : ICSW_URLS.MON_SVG_TO_PNG
                            data :
                                svg : _el[0].outerHTML
                        ).then((xml) ->
                            _url = ICSW_URLS.MON_FETCH_PNG_FROM_CACHE.slice(0, -1) + $(xml).find("value[name='cache_key']").text()
                            sub_scope.$destroy()
                            defer.resolve([loc_pk, _url])
                        )
                )
        )
        return defer.promise
    $scope.toggle_lock = ($event, loc) ->
        loc.locked = !loc.locked
        loc.put()
        if $event
            $event.stopPropagation()
            $event.preventDefault()
        # msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)
    $scope.close_modal = () ->
        if $scope.cur_edit
            $scope.cur_edit.close_modal()
    $scope.new_location_gfx = () ->
        # return empty location_gfx for current location
        return {
            "location" : $scope.loc_gfx_mother.idx
        }
    $scope.add_location_gfx = ($event, loc) ->
        $scope.preview_gfx = undefined
        # store for later reference in new_location_gfx
        $scope.loc_gfx_mother = loc
        $scope.gfx_mixin.create($event).then((data) ->
            data.num_dml = 0
            loc.location_gfxs.push(data)
        )
        $event.stopPropagation()
        $event.preventDefault()
    $scope.modify_location_gfx = ($event, loc) ->
        $scope.preview_gfx = undefined
        $scope.cur_location_gfx = loc
        $scope.gfx_mixin.edit(loc, $event).then((data) ->
        )
    $scope.delete_location_gfx = ($event, obj) ->
        # find location object via cat_lut
        loc = $scope.loc_lut[obj.location]
        $scope.preview_gfx = undefined
        $scope.gfx_mixin.delete_obj(obj).then((data) ->
            if data
                loc.location_gfxs = (entry for entry in loc.location_gfxs when entry.idx != obj.idx)
        )
    $scope.show_preview = (obj) ->
        $scope.preview_gfx = obj
    $scope.preview_close = () ->
        $scope.preview_gfx = undefined
    $scope.reload()
]).directive("icswConfigCategoryTreeGoogleMap",
[
    "$templateCache", "uiGmapGoogleMapApi", "$timeout", "$rootScope", "ICSW_SIGNALS",
(
    $templateCache, uiGmapGoogleMapApi, $timeout, $rootScope, ICSW_SIGNALS,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree.google.map")
        scope: {
            locations: "=locations"
            active_tab: "=activeTab"
        }
        link: (scope, element, attrs) ->
            console.log attrs
            scope.marker_lut = {}
            # scope.location_list = []
            scope.marker_list = []
            scope.map = {
                center: {}
                zoom: 6
                control: {}
                options: {
                    "streetViewControl": false
                    "minZoom" : 1
                    "maxZoom" : 20
                }
                bounds: {
                    "northeast" : {
                        "latitude": 4
                        "longitude": 4
                    }
                    "southwest": {
                        "latitude": 20
                        "longitude": 30
                    }
                }
            }
            scope.event_dict = {
                dragend: (marker, event_name, args) ->
                    _pos = marker.getPosition()
                    _cat = scope.marker_lut[marker.key]
                    _cat.latitude = _pos.lat()
                    _cat.longitude = _pos.lng()
                    _cat.put()
            }
            scope.zoom_to_locations = () ->
                # center map around the locations
                _bounds = null
                for entry in scope.locations
                    if not _bounds
                        _bounds = {
                            northeast: {
                                latitude: entry.latitude
                                longitude: entry.longitude
                            }
                            southwest: {
                                latitude: entry.latitude
                                longitude: entry.longitude
                            }
                        }
                    else
                        _bounds.northeast.latitude = Math.max(_bounds.northeast.latitude, entry.latitude)
                        _bounds.northeast.longitude = Math.max(_bounds.northeast.longitude, entry.longitude)
                        _bounds.southwest.latitude = Math.min(_bounds.southwest.latitude, entry.latitude)
                        _bounds.southwest.longitude = Math.min(_bounds.southwest.longitude, entry.longitude)
                scope.map.bounds = _bounds
                scope.map.center.latitude = (_bounds.northeast.latitude + _bounds.southwest.latitude) / 2.0
                scope.map.center.longitude = (_bounds.northeast.longitude + _bounds.southwest.longitude) / 2.0
                console.log scope.map
                # console.log _bounds

            scope.build_markers = () ->
                scope.marker_list.length = 0
                marker_lut = {}
                for _entry in scope.locations
                    comment = _entry.name
                    if _entry.comment
                        comment = "#{comment} (#{_entry.comment})"
                    if _entry.$gfx_list.length
                        comment = "#{comment}, #{_entry.$gfx_list.length} gfxs"
                    scope.marker_list.push(
                        {
                            "latitude": _entry.latitude
                            "longitude": _entry.longitude
                            "key": _entry.idx
                            "comment": comment
                            "options": {
                                "draggable": not _entry.locked
                                "title": comment
                                "opacity": if _entry.locked then 1.0 else 0.7
                            }
                            "icon": if _entry.svg_url then _entry.svg_url else null
                        }
                    )
                    marker_lut[_entry.idx] = _entry
                    scope.marker_lut = marker_lut
            scope.maps_ready = false
            scope.maps = undefined
            _update = () ->
                if scope.active_tab == "conf" and scope.locations and not scope.maps_ready
                    console.log "Zoom"
                    scope.zoom_to_locations()
                    scope.build_markers()
                    uiGmapGoogleMapApi.then(
                        (maps) ->
                            scope.maps_ready = true
                            scope.maps = maps
                            $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_GOOGLE_MAPS_LOADED"), scope.map)
                    )
                    $timeout(
                        () ->
                            _map = scope.map
                            _map.control.refresh(
                                {
                                    "latitude": _map.center.latitude
                                    "longitude": _map.center.longitude
                                }
                            )
                        100
                    )
            $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
                _update()
            )
            scope.$watch(
                "active_tab"
                (new_val) ->
                    _update()
            )
            scope.$watch(
                "locations",
                (new_val) ->
                    _update()
                true
            )
    }
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
            preview_close: "=previewClose"
        }
        link: (scope, element, attrs) ->
            scope.display_size = (ds) ->
                scope.display_style = ds
                if ds == "scaled"
                    scope.img_style = "width:100%;"
                else
                    scope.img_style = ""
            scope.display_size("scaled")
            scope.$watch(
                attrs["previewGfx"]
                (new_val) ->
                    scope.preview_gfx = new_val
            )
            scope.close_preview = () ->
                if attrs["previewClose"]
                    scope.preview_close()
            scope.rotate = (degrees) ->
                scope.modify_image(
                     {
                        "id": scope.preview_gfx.idx
                        "mode": "rotate"
                        "degrees" : degrees
                     }
                )
            scope.resize = (factor) ->
                scope.modify_image(
                     {
                        "id": scope.preview_gfx.idx
                        "mode": "resize"
                        "factor": factor
                     }
                )
            scope.brightness = (factor) ->
                scope.modify_image(
                     {
                        "id": scope.preview_gfx.idx
                        "mode": "brightness"
                        "factor" : factor
                     }
                )
            scope.sharpen = (factor) ->
                scope.modify_image(
                     {
                        "id": scope.preview_gfx.idx
                        "mode": "sharpen"
                        "factor" : factor
                     }
                )
            scope.restore = () ->
                scope.modify_image("restore")
            scope.undo = (obj) ->
                scope.modify_image("undo")
            scope.modify_image = (data) ->
                # scope.show_preview(obj)
                if angular.isString(data)
                    data = {"id" : scope.preview_gfx.idx, "mode": data}
                blockUI.start()
                icswSimpleAjaxCall(
                    url : ICSW_URLS.BASE_MODIFY_LOCATION_GFX
                    data: data
                ).then((xml) ->
                    blockUI.stop()
                    scope.preview_gfx.image_url = $(xml).find("value[name='image_url']").text()
                    scope.preview_gfx.icon_url = $(xml).find("value[name='icon_url']").text()
                    scope.preview_gfx.width = parseInt($(xml).find("value[name='width']").text())
                    scope.preview_gfx.height = parseInt($(xml).find("value[name='height']").text())
                )
    }
])
