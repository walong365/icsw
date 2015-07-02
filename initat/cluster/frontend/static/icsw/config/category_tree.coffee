# Copyright (C) 2012-2015 init.at
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
    "icsw.config.category_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload"
    ]
).service("icswConfigCategoryTreeFetchService", ["icswCachingCall", "$q", "ICSW_URLS", (icswCachingCall, $q, ICSW_URLS) ->
    _fetch = (id, pk_list) ->
        defer =$q.defer()
        _wait = [
            icswCachingCall.fetch(id, ICSW_URLS.REST_CATEGORY_LIST, {}, []),
            icswCachingCall.fetch(id, ICSW_URLS.REST_LOCATION_GFX_LIST, {"device_mon_location__device__in": "<PKS>", "_distinct": true}, pk_list),
            icswCachingCall.fetch(id, ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST, {"device__in": "<PKS>"}, pk_list)
            icswCachingCall.fetch(id, ICSW_URLS.DEVICE_GET_DEVICE_LOCATION, {"devices": "<PKS>"}, pk_list)
        ]
        $q.all(_wait).then((data) ->
            defer.resolve(data)
        )
        return defer.promise
    return {
        "fetch": (id, pk_list) ->
            return _fetch(id, pk_list)
    }
]).service("icswConfigCategoryTreeMapService", [() ->
    _map = null
    _map_id = 0
    return {
        "map_set": () ->
            return _map_id
        "get_map": () ->
            return _map
        "set_map": (map) ->
            _map_id++
            _map = map
    }
]).directive("icswConfigCategoryLocationEdit", ["$templateCache", "icswConfigCategoryTreeMapService", ($templateCache, icswConfigCategoryTreeMapService) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.edit")
        scope: {
            preview_gfx: "=previewGfx"
            preview_close: "=previewClose"
        }
        controller: "icswConfigCategoryLocationCtrl"
        link: (scope, element, attrs) ->
    }
]).directive("icswConfigCategoryLocationShow", ["$templateCache", "icswConfigCategoryTreeMapService", ($templateCache, icswConfigCategoryTreeMapService) ->
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
]).directive("icswConfigCategoryLocationListEdit", ["$templateCache", "icswConfigCategoryTreeMapService", ($templateCache, icswConfigCategoryTreeMapService) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.list.edit")
        link: (scope, element, attrs) ->
    }
]).directive("icswConfigCategoryLocationListShow", ["$templateCache", "icswConfigCategoryTreeMapService", ($templateCache, icswConfigCategoryTreeMapService) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.list.show")
        link: (scope, element, attrs) ->
    }
]).controller("icswConfigCategoryLocationCtrl", [
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$window", "$timeout",
    "$q", "$modal", "access_level_service", "FileUploader", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryTreeService",
    "icswCallAjaxService", "icswParseXMLResponseService", "toaster", "icswConfigCategoryTreeMapService", "icswConfigCategoryTreeFetchService", "msgbus",
   ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $window, $timeout, $q, $modal, access_level_service,
    FileUploader, blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService, icswCallAjaxService, icswParseXMLResponseService, toaster,
    icswConfigCategoryTreeMapService, icswConfigCategoryTreeFetchService, msgbus) ->
        $scope.entries = []
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
        msgbus.receive("icsw.config.locations.changed.tree", $scope, () ->
            # receiver for global changes from tree
            $scope.reload()
        )
        $scope.$watch(
            () -> return icswConfigCategoryTreeMapService.map_set()
            (new_val) ->
                $scope.map = icswConfigCategoryTreeMapService.get_map()
        )
        $scope.uploader = new FileUploader(
            scope : $scope
            url : ICSW_URLS.BASE_UPLOAD_LOCATION_GFX
            queueLimit : 1
            alias : "gfx"
            formData : [
                 "location_id" : 0
                 "csrfmiddlewaretoken" : $window.CSRF_TOKEN
            ]
            removeAfterUpload : true
        )
        $scope.upload_list = []
        $scope.uploader.onBeforeUploadItem = (item) ->
            item.formData[0].location_id = $scope.cur_location_gfx.idx
            blockUI.start()
        $scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            $scope.uploader.clearQueue()
            return null
        $scope.uploader.onErrorItem = (item, response, status, headers) ->
            blockUI.stop()
            $scope.uploader.clearQueue()
            toaster.pop("error", "", "error uploading file, please check logs", 0)
            return null
        $scope.uploader.onCompleteItem = (item, response, status, headers) ->
            xml = $.parseXML(response)
            if icswParseXMLResponseService(xml)
                Restangular.one(ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2), $scope.cur_location_gfx.idx).get().then((data) ->
                    for _copy in ["width", "height", "uuid", "content_type", "locked", "image_stored", "icon_url", "image_name", "image_url"]
                        $scope.cur_location_gfx[_copy] = data[_copy]
                )
        _is_location = (obj) ->
            return (obj.depth > 1) and obj.full_name.split("/")[1] == "location"
        $scope.reload = () ->
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
                            icswCallAjaxService
                                hidden: true
                                url : ICSW_URLS.MON_SVG_TO_PNG
                                data :
                                    svg : _el[0].outerHTML
                                success : (xml) ->
                                    if icswParseXMLResponseService(xml)
                                        _url = ICSW_URLS.MON_FETCH_PNG_FROM_CACHE.slice(0, -1) + $(xml).find("value[name='cache_key']").text()
                                        sub_scope.$destroy()
                                        defer.resolve([loc_pk, _url])
                    )
            )
            return defer.promise
        $scope.locate = (loc, $event) ->
            $scope.map.control.refresh({"latitude": loc.latitude, "longitude": loc.longitude})
            $scope.map.control.getGMap().setZoom(11)
            if $event
                $event.stopPropagation()
                $event.preventDefault()
        $scope.toggle_lock = ($event, loc) ->
            loc.locked = !loc.locked
            loc.put()
            if $event
                $event.stopPropagation()
                $event.preventDefault()
            msgbus.emit("icsw.config.locations.changed.map")
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
]).directive("icswConfigCategoryTreeGoogleMap", ["$templateCache", "icswConfigCategoryTreeMapService", ($templateCache, icswConfigCategoryTreeMapService) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree.google.map")
        scope: {
            locations: "=locations"
        }
        link: (scope, element, attrs) ->
            scope.marker_lut = {}
            scope.location_list = []
            scope.marker_list = []
            scope.map = {
                center: {
                    latitude: 4
                    longitude: 7
                }
                zoom: 2
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
                    "ne" : {
                        "latitude": 4
                        "longitude": 4
                    }
                    "sw": {
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
            icswConfigCategoryTreeMapService.set_map(scope.map)
            scope.build_markers = () ->
                if scope.location_list.length == scope.marker_list.length
                    # update list to reduce flicker
                    for _vt in _.zip(scope.location_list, scope.marker_list)
                        _entry = _vt[0]
                        marker = _vt[1]
                        marker.latitude = _entry.latitude
                        marker.longitude = _entry.longitude
                        marker.comment = if _entry.comment then "#{_entry.name} (#{_entry.comment})" else _entry.name
                        marker.options.opacity = if _entry.locked then 1.0 else 0.7
                        marker.icon = if _entry.svg_url then _entry.svg_url else null
                else
                    new_list = []
                    marker_lut = {}
                    for _entry in scope.location_list
                        new_list.push(
                            {
                                "latitude": _entry.latitude
                                "longitude": _entry.longitude
                                "key": _entry.idx
                                "comment": if _entry.comment then "#{_entry.name} (#{_entry.comment})" else _entry.name
                                "options": {
                                    "draggable": not _entry.locked
                                    "title": _entry.full_name
                                    "opacity": if _entry.locked then 1.0 else 0.7
                                }
                                "icon": if _entry.svg_url then _entry.svg_url else null
                            }
                        )
                        marker_lut[_entry.idx] = _entry
                    scope.marker_list = new_list
                    scope.marker_lut = marker_lut
            scope.$watch(
                "locations",
                (new_val) ->
                    if new_val
                        scope.location_list = new_val
                        scope.build_markers()
                true
            )
    }
]).controller("icswConfigCategoryTreeCtrl", [
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$window", "$timeout",
    "$q", "$modal", "access_level_service", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryTreeService", "msgbus",
    "icswCallAjaxService", "icswParseXMLResponseService", "toaster", "icswConfigCategoryTreeMapService", "icswConfigCategoryTreeFetchService",
    "icswToolsSimpleModalService",
   ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $window, $timeout, $q, $modal, access_level_service,
    blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService, msgbus, icswCallAjaxService, icswParseXMLResponseService, toaster,
    icswConfigCategoryTreeMapService, icswConfigCategoryTreeFetchService, icswToolsSimpleModalService) ->
        $scope.cat = new icswConfigCategoryTreeService($scope, {})
        $scope.pagSettings = paginatorSettings.get_paginator("cat_base", $scope)
        $scope.entries = []
        # mixins
        # edit mixin for cateogries
        $scope.edit_mixin = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "cat")
        $scope.edit_mixin.use_modal = false
        $scope.edit_mixin.use_promise = true
        $scope.edit_mixin.new_object = (scope) -> return scope.new_object()
        $scope.edit_mixin.delete_confirm_str = (obj) -> return "Really delete category node '#{obj.name}' ?"
        $scope.edit_mixin.modify_rest_url = ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2)
        $scope.edit_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_CATEGORY_LIST.slice(1))
        $scope.edit_mixin.edit_template = "category.form"
        $scope.form = {}
        msgbus.receive("icsw.config.locations.changed.map", $scope, () ->
            # receiver for global changes from map
            $scope.reload()
        )
        $scope.reload = () ->
            icswConfigCategoryTreeFetchService.fetch($scope.$id, null).then((data) ->
                $scope.entries = data[0]
                for entry in $scope.entries
                    entry.open = false
                $scope.dml_list = data[2]
                $scope.edit_mixin.create_list = $scope.entries
                $scope.edit_mixin.delete_list = $scope.entries
                $scope.rebuild_cat()
        )
        $scope.edit_obj = (cat, event) ->
            $scope.create_mode = false
            $scope.cat.clear_active()
            $scope.cat_lut[cat.idx].active = true
            $scope.cat.show_active()
            pre_parent = cat.parent
            $scope.edit_mixin.edit(cat, event).then((data) ->
                if data.parent == pre_parent
                    $scope.cat.iter(
                        (entry) ->
                            if entry.parent and entry.parent.obj.name
                                entry.obj.full_name = "#{entry.parent.obj.full_name}/#{entry.obj.name}"
                            else
                                entry.obj.full_name = "/#{entry.obj.name}"
                    )
                else
                    $scope.reload()
                msgbus.emit("icsw.config.locations.changed.tree")
            )
        $scope.delete_obj = (obj) ->
            $scope.edit_mixin.delete_obj(obj).then((data) ->
                if data
                    $scope.rebuild_cat()
                    $scope.cat.clear_active()
                    msgbus.emit("icsw.config.locations.changed.tree")
            )
        $scope.rebuild_cat = () ->
            # check location gfx refs
            cat_lut = {}
            $scope.cat.clear_root_nodes()
            for entry in $scope.entries
                t_entry = $scope.cat.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.immutable})
                cat_lut[entry.idx] = t_entry
                if entry.parent
                    cat_lut[entry.parent].add_child(t_entry)
                else
                    $scope.cat.add_root_node(t_entry)
            $scope.cat_lut = cat_lut
        $scope.new_object = () ->
            if $scope.new_top_level
                _parent = (value for value in $scope.entries when value.depth == 1 and value.name == $scope.new_top_level)[0]
                _name = "new_#{_parent.name}"
                r_struct = {"name" : _name, "parent" : _parent.idx, "depth" : 2, "full_name" : "/#{$scope.new_top_level}/#{_name}"}
                if $scope.new_top_level == "location"
                    r_struct["latitude"] = 48.1
                    r_struct["longitude"] = 16.3
                return r_struct
            else
                return {"name" : "new_cat", "depth" : 2, "full_name" : ""}
        $scope.create_new = ($event, top_level) ->
            $scope.create_mode = true
            $scope.new_top_level = top_level
            $scope.cat.clear_active()
            $scope.edit_mixin.create($event).then((data) ->
                $scope.reload()
                msgbus.emit("icsw.config.locations.changed.tree")
            )
        $scope.get_valid_parents = (obj) ->
            # called from formular code
            if obj.idx
                # object already saved, do not move beteen top categories
                top_cat = new RegExp("^/" + obj.full_name.split("/")[1])
                p_list = (value for value in $scope.entries when value.depth and top_cat.test(value.full_name))
                # remove all nodes below myself
                r_list = []
                add_list = [$scope._edit_obj.idx]
                while add_list.length
                    r_list = r_list.concat(add_list)
                    add_list = (value.idx for value in p_list when (value.parent in r_list and value.idx not in r_list))
                p_list = (value for value in p_list when value.idx not in r_list)
            else
                # new object, allow all values
                p_list = (value for value in $scope.entries when value.depth)
            return p_list
        $scope.is_location = (obj) ->
            # called from formular code
            # full_name.match leads to infinite digest cycles
            return (obj.depth > 1) and obj.full_name.split("/")[1] == "location"
        $scope.close_modal = () ->
            $scope.cat.clear_active()
            if $scope.cur_edit
                $scope.cur_edit.close_modal()
        $scope.prune_tree = () ->
            $scope.cat.clear_active()
            $scope.close_modal()
            icswToolsSimpleModalService("Really prune tree (delete empty elements) ?").then(() ->
                blockUI.start()
                icswCallAjaxService
                    url     : ICSW_URLS.BASE_PRUNE_CATEGORIES
                    success : (xml) ->
                        icswParseXMLResponseService(xml)
                        $scope.reload()
                        blockUI.stop()
            )
        $scope.reload()
]).service("icswConfigCategoryTreeService", ["icswTreeConfig", (icswTreeConfig) ->
    class category_tree_edit extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = true
            @show_childs = false
            @location_re = new RegExp("^/location/.*$")
        get_name : (t_entry) ->
            cat = t_entry.obj
            is_loc = @location_re.test(cat.full_name)
            if cat.depth > 1
                r_info = "#{cat.full_name} (#{cat.name})"
                if cat.num_refs
                    r_info = "#{r_info} (refs=#{cat.num_refs})"
                if is_loc
                    if cat.physical
                        r_info = "#{r_info}, physical"
                    else
                        r_info = "#{r_info}, structural"
                    if cat.locked
                        r_info = "#{r_info}, locked"
            else if cat.depth
                r_info = cat.full_name
            else
                r_info = "TOP"
            return r_info
        handle_click: (entry, event) =>
            @clear_active()
            cat = entry.obj
            if cat.depth > 1
                @scope.edit_obj(cat, event)
            else if cat.depth == 1
                @scope.create_new(event, cat.full_name.split("/")[1])
            @scope.$digest()

]).directive("icswConfigCategoryTreeMapEnhance", ["$templateCache", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", "blockUI", ($templateCache, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService, blockUI) ->
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
                icswCallAjaxService
                    url : ICSW_URLS.BASE_MODIFY_LOCATION_GFX
                    data: data
                    success: (xml) ->
                        blockUI.stop()
                        if icswParseXMLResponseService(xml)
                            scope.$apply(() ->
                                scope.preview_gfx.image_url = $(xml).find("value[name='image_url']").text()
                                scope.preview_gfx.icon_url = $(xml).find("value[name='icon_url']").text()
                                scope.preview_gfx.width = parseInt($(xml).find("value[name='width']").text())
                                scope.preview_gfx.height = parseInt($(xml).find("value[name='height']").text())
                            )

    }

]).directive("icswConfigCategoryTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.head")
    }
]).directive("icswConfigCategoryTreeRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.row")
        link : (scope, el, attrs) ->
            scope.get_tr_class = (obj) ->
                return if obj.depth > 1 then "" else "success"
            scope.get_space = (depth) ->
                return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")
    }
]).directive("icswConfigCategoryTreeEditTemplate", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("category.form")
        link : (scope, element, attrs) ->
            scope.form_error = (field_name) ->
                if scope.form[field_name].$valid
                    return ""
                else
                    return "has-error"
    }
]).directive("icswConfigCategoryTree", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree")
    }
]).directive("icswConfigCategoryContentsViewer", ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.config.category.contents_viewer"
        scope:
            categoryObject: '='
        link : (scope, elements, attrs) ->
            scope.$watch('categoryObject', () ->
                Restangular.all(ICSW_URLS.BASE_CATEGORY_CONTENTS.slice(1)).getList({category_pk: scope.categoryObject.idx}).then((new_data) ->
                    scope.new_data = new_data
                )
            )
    }
])
