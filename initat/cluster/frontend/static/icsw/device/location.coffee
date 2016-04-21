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
    "icsw.device.location",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).service("icswDeviceLocationTreeService",
[
    "icswTreeConfig",
(
    icswTreeConfig
) ->
    class location_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = false
            @show_childs = false
            @mode_entries = []
            @clear_tree()

        clear_tree: () =>
            @lut = {}

        create_mode_entries: (mode, loc_tree) =>
            @mode_entries.length = []
            for entry in loc_tree.list
                if entry.depth < 1 or entry.full_name.split("/")[1] == mode
                    @mode_entries.push(entry)

        get_selected_loc_pks: () =>
            return @get_selected(
                (node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
            )

        do_loc_selection: (entry) =>
            @set_selected(
                (node) =>
                    if node.obj.physical
                        if node.obj == entry.obj
                            return null
                        else
                            return false
                    else
                        # ignore structural entries
                        return null
            )
        selection_changed: (entry) =>
            @scope.new_selection(entry, @get_selected_loc_pks())

        pre_change_cb: (entry) =>
            # save selection before we toggle the checkbox
            @$pre_click_sel = @get_selected_loc_pks()
        
        reset_selection: () =>
            # set everything to $pre_click_sel
            @set_selected(
                (node) =>
                    return node.obj.idx in @$pre_click_sel
            )
            
        get_name : (t_entry) ->
            cat = t_entry.obj
            if cat.depth > 1
                if @scope.DEBUG
                    r_info = "[#{cat.idx}] "
                else
                    r_info = ""
                r_info = "#{cat.name}"
                num_sel = t_entry.$match_pks.length
                if num_sel and @$num_sel > 1
                    r_info = "#{r_info}, #{num_sel} of #{@$num_devs}"
                if cat.num_refs
                    r_info = "#{r_info} (refs=#{cat.num_refs})"
                num_locs = cat.$gfx_list.length
                if num_locs
                    r_info = "#{r_info}, #{num_locs} location gfx"
                if cat.physical
                    r_info = "#{r_info}, physical"
                else
                    r_info = "#{r_info}, structural"
                if cat.locked
                    r_info = "#{r_info}, locked"
                return r_info
            else if cat.depth
                return cat.full_name
            else
                return "TOP"

        handle_click: (t_entry, center_map=true) ->
            cat = t_entry.obj
            @clear_active()
            if cat.depth > 1
                if cat != @scope.struct.active_loc
                    @scope.struct.active_gfx = null
                # if cat.$gfx_list.length
                @scope.set_active_location(cat, center_map)
                # else
                #     @scope.struct.active_loc = null
                t_entry.active = true
            else
                @scope.struct.active_loc = null
                @scope.struct.active_gfx = null
            @show_active()
            # important to update frontend
            @scope.$digest()

]).controller("icswDeviceLocationCtrl",
[
    "$scope", "$q", "icswAcessLevelService", "icswDeviceTreeService",
    "icswCategoryTreeService", "$rootScope", "ICSW_SIGNALS", "blockUI",
    "icswDeviceLocationTreeService", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswToolsSimpleModalService";
(
    $scope, $q, icswAcessLevelService, icswDeviceTreeService,
    icswCategoryTreeService, $rootScope, ICSW_SIGNALS, blockUI,
    icswDeviceLocationTreeService, ICSW_URLS, icswSimpleAjaxCall,
    icswToolsSimpleModalService,
) ->
    icswAcessLevelService.install($scope)
    $scope.struct = {
        device_list_ready: false
        multi_device_mode: false
        loc_tree: new icswDeviceLocationTreeService($scope, {})
        # useable locations
        locations: []
        # selected devices
        devices: []
        # active location
        active_loc: null
        # active gfx
        active_gfx: null
        # google maps callback
        google_maps_fn: null
    }
    $scope.DEBUG = false

    $scope.$on("$destroy", () ->
        $scope.struct.device_list_ready = false
    )

    $scope.google_maps_cb_fn = (fn_name, args) ->
        if fn_name == "marker_clicked"
            _loc = args
            _lc = $scope.struct.loc_tree
            # active node
            _node = _lc.lut[_loc.idx]
            _lc.handle_click(_node, center_map=false)

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                device_tree = data[0]
                $scope.struct.device_list_ready = true
                $scope.struct.tree = data[1]
                $scope.struct.devices = (dev for dev in devs when not dev.is_meta_device)
                $scope.struct.multi_device_mode = if $scope.struct.devices.length > 1 then true else false
                $scope.struct.device_tree = device_tree
                # $scope.rebuild_dnt()
                $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"))
        )

    $scope.$watch("struct.active_gfx", (new_val) ->
        # console.log "gfx", new_val
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"), (event) ->
        $scope.rebuild_dnt()
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
        $scope.rebuild_dnt()
    )
    $scope.rebuild_dnt = () ->
        _ct = $scope.struct.loc_tree
        # build location list for google-maps
        $scope.struct.tree.build_location_list($scope.struct.locations)
        _ct.change_select = true
        for dev in $scope.struct.devices
            # check all devices and disable change button when not all devices are in allowed list
            if not $scope.acl_all(dev, "backbone.device.change_location", 7)
                console.log "ND"
                _ct.change_select = false
                break
        if _ct.$pre_sel?
            _cur_sel = _ct.$pre_sel
        else
            _cur_sel = []
        # console.log "pre=", _cur_sel
        _ct.clear_tree()
        _ct.clear_root_nodes()
        _ct.create_mode_entries("location", $scope.struct.tree)

        _ct.$num_devs = $scope.struct.devices.length
        _num_devs = $scope.struct.devices.length
        _dev_pks = (dev.idx for dev in $scope.struct.devices)
        _dev_pks.sort()

        # flag: disable select button or not
        # _disable_select_dml = false
        for entry in _ct.mode_entries
            # console.log entry.reference_dict.device, _num_devs
            # get pks of devices in current selection which have the category entry set
            _match_pks = (_val for _val in entry.reference_dict.device when _val in _dev_pks)
            _match_pks.sort()
            # console.log entry.idx, _match_pks, entry.idx in _cur_sel
            # console.log _match_pks, _dev_pks
            t_entry = _ct.new_node(
                {
                    folder: false
                    obj: entry
                    expand: (entry.depth < 2) or (entry.idx in _cur_sel) or _match_pks.length
                    selected: _match_pks.length == _num_devs
                    _show_select: entry.useable
                }
            )
            # check if selected devices have location-gfx link to this category
            _dml_dev_pks = (_dml.device for _dml in entry.$dml_list)
            # if _.intersection(_dml_dev_pks, _dev_pks).length and entry.physical
            #    _disable_select_dml = true
            # copy matching pks to tree entry (NOT entry because entry is global)
            t_entry.$match_pks = (_v for _v in _match_pks)
            _ct.lut[entry.idx] = t_entry
            if entry.parent and entry.parent of _ct.lut
                _ct.lut[entry.parent].add_child(t_entry)
                if t_entry.expand
                    # propagate expand level upwards
                    _t_entry = t_entry
                    while _t_entry.parent
                        _t_entry.expand = true
                        _t_entry = _t_entry.parent
                if entry.depth < 2
                    # hide top-level entry (==/location/)
                    t_entry._show_select = false
            else
                # hide selection from root nodes
                t_entry._show_select = false
                _ct.add_root_node(t_entry)
        _ct.show_select = true
        # _ct.disable_select = _disable_select_dml
        _ct.$pre_sel = _ct.get_selected_loc_pks()
        # _ct.show_selected(false)

    $scope.set_active_location = (loc, center_map=true) ->
        $scope.struct.active_loc = loc
        if loc.useable and $scope.struct.google_maps_fn and center_map
            $scope.struct.google_maps_fn("refresh", [loc.latitude, loc.longitude])
            $scope.struct.google_maps_fn("zoom", 11)
            
    $scope.is_any_location_defined = () ->
        if ! $scope.loc_tree_lut
            return true  # assume that they will arrive
        else
            return Object.keys($scope.loc_tree_lut).length > 1

    $scope.new_selection = (t_entry, sel_list) =>
        loc = t_entry.obj
        dev_pks = (dev.idx for dev in $scope.struct.devices)
        # check if we would loose some dmls (then ask the user)
        if t_entry.selected
            # select location, check all others
            check_locs = (o_loc for o_loc in $scope.struct.loc_tree.mode_entries when o_loc != loc)
        else
            check_locs = [loc]
        dml_lost = 0
        # iterate over check locations
        for c_loc in check_locs
            for gfx in c_loc.$gfx_list
                _to_delete = (dml for dml in gfx.$dml_list when dml.device in dev_pks)
                dml_lost += _to_delete.length
        defer = $q.defer()
        if dml_lost
            icswToolsSimpleModalService(
                "Really change location (#{dml_lost} Location settings would be lost) ?"
            ).then(
                (ok) ->
                    defer.resolve("go")
                (notok) ->
                    defer.reject("no")
            )
        else
            defer.resolve("go ahead")
        defer.promise.then(
            (ok) ->
                blockUI.start()
                icswSimpleAjaxCall(
                    url     : ICSW_URLS.BASE_CHANGE_CATEGORY
                    data    :
                        "dev_pks": angular.toJson(dev_pks)
                        "cat_pks": angular.toJson([loc.idx])
                        "set": if t_entry.selected then "1" else "0"
                ).then(
                    (xml) ->
                        # see code in category.coffee
                        change_dict = angular.fromJson($(xml).find("value[name='changes']").text())
                        [sync_pks, sync_locs, sync_gfxs] = [[], [], []]
                        for add_b in change_dict.added
                            $scope.struct.device_tree.add_category_to_device_by_pk(add_b[0], add_b[1])
                            sync_pks.push(add_b[0])
                            sync_locs.push(add_b[1])
                        for sub_b in change_dict.removed
                            $scope.struct.device_tree.remove_category_from_device_by_pk(sub_b[0], sub_b[1])
                            sync_pks.push(sub_b[0])
                            sync_locs.push(sub_b[1])
                        for sub_dml in change_dict.dml_removed
                            $scope.struct.tree.remove_dml_by_pk(sub_dml[3])
                            sync_pks.push(sub_dml[0])
                            sync_locs.push(sub_dml[1])
                        sync_pks = _.uniq(sync_pks)
                        sync_locs = _.uniq(sync_locs)
                        # add gfxs to sync
                        for sync_loc in sync_locs
                            for gfx in $scope.struct.tree.lut[sync_loc].$gfx_list
                                sync_gfxs.push(gfx.idx)
                        sync_gfxs = _.uniq(sync_gfxs)
                        if sync_pks.length
                            # sync devices
                            $scope.struct.tree.sync_devices(($scope.struct.device_tree.all_lut[_pk] for _pk in sync_pks))
                        if sync_gfxs.length
                            # sync locations
                            for gfx_loc_id in sync_gfxs
                                $scope.struct.tree.populate_gfx_location(
                                    $scope.struct.tree.gfx_lut[gfx_loc_id]
                                    $scope.struct.device_tree
                                    $scope.struct.devices
                                )
                        # set active gfx
                        if t_entry.selected
                            if t_entry.obj != $scope.struct.active_loc
                                $scope.struct.active_loc = t_entry.obj
                                $scope.struct.active_gfx = null
                        # deselect non-selected physical structure entries
                        $scope.struct.loc_tree.do_loc_selection(t_entry)
                        $scope.rebuild_dnt()
                        blockUI.stop()
                    (error) ->
                        blockUI.stop()
                )
            (notok) ->
                # reset settings
                $scope.struct.loc_tree.reset_selection()
        )

]).directive("icswDeviceLocationOverview", ["$templateCache", ($templateCache) ->
    return {
         restrict : "EA"
        template: $templateCache.get("icsw.device.location.overview")
        controller: "icswDeviceLocationCtrl"
    }
]).directive("icswDeviceLocationList",
[
    "$templateCache", "$compile", "$uibModal", "Restangular", "ICSW_URLS",
    "icswCategoryTreeService", "$q", "icswDeviceTreeService", "$rootScope",
    "ICSW_SIGNALS",
(
    $templateCache, $compile, $uibModal, Restangular, ICSW_URLS,
    icswCategoryTreeService, $q, icswDeviceTreeService, $rootScope,
    ICSW_SIGNALS,
) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.location.list")
        scope:
            # location category
            location: "=icswLocation"
            # active gfx
            active_gfx: "=icswActiveGfx"
            # selected devics
            devices: "=icswDevices"

        link : (scope, el, attrs) ->
            _tree_loaded = false
            scope.cat_tree = null
            scope.device_tree = null
            scope.active_gfx = null

            update = () ->
                # truncate list
                loc_defer = $q.defer()
                if _tree_loaded
                    loc_defer.resolve("init done")
                else
                    $q.all(
                        [
                            icswCategoryTreeService.load(scope.$id)
                            icswDeviceTreeService.load(scope.$id)
                        ]
                    ).then(
                        (data) ->
                            scope.cat_tree = data[0]
                            scope.device_tree = data[1]
                            loc_defer.resolve("loaded")
                    )
                loc_defer.promise.then(
                    (init_msg) ->
                        _tree_loaded = true
                        _clear_active = true
                        for gfx in scope.location.$gfx_list
                            if scope.active_gfx? and gfx.idx == scope.active_gfx.idx
                                # do not clear active_gfx when element is in current list
                                _clear_active = false
                            scope.cat_tree.populate_gfx_location(gfx, scope.device_tree, scope.devices)
                        if _clear_active
                            scope.active_gfx = null
                )

            scope.$watch("location", (new_loc) ->
                if new_loc
                    update()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"), (event) ->
                update()
            )
            scope.activate_loc_gfx = (loc_gfx) ->
                scope.active_gfx = loc_gfx

            scope.get_button_class = (loc_gfx) ->
                if scope.active_gfx == loc_gfx
                    # active gfx
                    return "btn btn-xs btn-success"
                # else if loc_gfx.$dml_list.length
                #    # not active but devices present
                #    return "btn btn-sm btn-primary"
                else
                    return "btn btn-xs btn-default"
    }
]).directive("icswDeviceMonitoringLocationList",
[
    "$templateCache", "$uibModal", "$q", "Restangular", "ICSW_URLS",
    "icswToolsSimpleModalService", "blockUI", "icswCategoryTreeService",
    "icswDeviceTreeService", "$rootScope", "ICSW_SIGNALS",
(
    $templateCache, $uibModal, $q, Restangular, ICSW_URLS,
    icswToolsSimpleModalService, blockUI, icswCategoryTreeService,
    icswDeviceTreeService, $rootScope, ICSW_SIGNALS,
) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.monitoring.location.list")
        scope:
            # active gfx
            active_gfx: "=icswActiveGfx"
            # selected devices
            devices: "=icswDevices"
        link : (scope, el, attrs) ->
            scope.cat_tree = null
            scope.device_tree = null
            _update = () ->
                if scope.devices and scope.active_gfx
                    defer = $q.defer()
                    if not scope.cat_tree
                        $q.all(
                            [
                                icswCategoryTreeService.load(scope.$id)
                                icswDeviceTreeService.load(scope.$id)
                            ]
                        ).then(
                            (data) ->
                                scope.cat_tree = data[0]
                                scope.device_tree = data[1]
                                defer.resolve("loaded")
                        )
                    else
                        defer.resolve("already there")
                    defer.promise.then(
                        (load_msg) ->
                            # console.log "new gfx", scope.devices, scope.active_gfx.$dml_list
                    )
                else
                    # cleanup
                    true
            scope.$watch("active_gfx", (new_val) ->
                _update()
            )
            scope.$watch("devices", (new_val) ->
                _update()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"), (event) ->
                _update()
            )
            scope.use_device = (dev) ->
                # add device to map
                blockUI.start()
                new_md = {
                    device: dev.idx
                    location_gfx: scope.active_gfx.idx
                    location: scope.active_gfx.location
                    pos_x: Math.min(scope.active_gfx.width / 2, 50)
                    pos_y: Math.min(scope.active_gfx.height / 2, 50)
                    changed: false
                }
                scope.cat_tree.create_device_mon_location_entry(new_md).then(
                    (is_ok) ->
                        scope.cat_tree.populate_gfx_location(
                            scope.active_gfx
                            scope.device_tree
                            scope.devices
                        )
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"))
                        blockUI.stop()
                    (not_ok) ->
                        blockUI.stop()
                )

            scope.remove_dml = (dml) ->
                # remove device (== dml entry) from map
                # icswToolsSimpleModalService("really delete location?").then(
                blockUI.start()
                scope.cat_tree.delete_device_mon_location_entry(dml).then(
                    (deleted) ->
                        scope.cat_tree.populate_gfx_location(
                            scope.active_gfx
                            scope.device_tree
                            scope.devices
                        )
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"))
                        blockUI.stop()
                    (not_del) ->
                        blockUI.stop()
                )

            scope.toggle_locked = (dml) ->
                # toggle dml locked state
                dml.locked = !dml.locked
                dml.put()
    }
]).directive("icswDeviceLocationMap",
[
    "d3_service", "$rootScope", "ICSW_SIGNALS",
(
    d3_service, $rootScope, ICSW_SIGNALS,
) ->
    return {
        restrict : "EA"
        scope:
            # active gfx
            active_gfx: "=icswActiveGfx"
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            d3 = null

            scope.rescale = () ->
                scope.$apply(
                    () -> scope.cur_scale = Math.max(Math.min(d3.event.scale, 1.0), 0.3)
                )
                scope.my_zoom.scale(scope.cur_scale)
                scope.vis.attr("transform", "scale(#{scope.cur_scale})")

            scope.add_symbols = (centers) ->
                centers.append("circle").attr
                    "r": (n) ->
                        return 50
                    "fill": (d) ->
                        return if d.locked then "#00ff00" else "#ffff00"
                    "stroke": "black"
                    "stroke-width": "1"
                centers.append("text")
                .attr
                    "text-anchor": "middle"
                    "alignment-baseline": "middle"
                    "stroke": "white"
                    "font-weight": "bold"
                    "stroke-width": "2"
                .text(
                    (d) ->
                        return d.$device.full_name
                )
                centers.append("text")
                .attr
                    "text-anchor": "middle"
                    "alignment-baseline": "middle"
                    "font-weight": "bold"
                    "fill": "black"
                    "stroke-width": "0"
                .text(
                    (d) ->
                        return d.$device.full_name
                )

            scope.draw_list = (dml_list) ->
                # need objectEquality == true
                scope.vis.selectAll(".pos").remove()
                scope.centers = scope.vis.selectAll(".pos").data(dml_list).enter()
                .append("g").call(scope.drag_node)
                .attr
                    "class": "pos"
                    "node_id": (n) ->
                        return n.device
                    "transform": (n) ->
                        return "translate(#{n.pos_x}, #{n.pos_y})"
                scope.add_symbols(scope.centers)

            _update = () ->
                scope.cur_scale = 1.0
                element.children().remove()
                if scope.active_gfx
                    width = scope.active_gfx.width
                    height = scope.active_gfx.height
                    svg = d3.select(element[0])
                        .append("svg:svg")
                        .attr(
                            "width": "100%" # #{width}px"
                            "height": "100%" # #{height}px"
                            "viewBox": "0 0 #{width} #{height}"
                        )
                    scope.my_zoom = d3.behavior.zoom()
                    scope.vis = svg.append("svg:g").call(scope.my_zoom.on("zoom", scope.rescale))
                    scope.vis.append("svg:image").attr(
                        "xlink:href": scope.active_gfx.image_url
                        "width": width
                        "height": height
                        "preserveAspectRatio": "none"
                    )
                    scope.draw_list(scope.active_gfx.$dml_list)

            d3_service.d3().then(
                (new_d3) ->
                    d3 = new_d3
                    scope.drag_node = d3.behavior.drag()
                    .on("dragstart", (d) -> )
                    .on("dragend", (d) ->
                        # console.log "dragend", d
                        d.put()
                    )
                    .on("drag", (d) ->
                        if not d.locked and d.$$selected
                            d.changed = true
                            x = Math.max(Math.min(d3.event.x, scope.active_gfx.width), 0)
                            y = Math.max(Math.min(d3.event.y, scope.active_gfx.height), 0)
                            d.pos_x = parseInt(x)
                            d.pos_y = parseInt(y)
                            d3.select(this).attr("transform": "translate(#{x},#{y})")
                    )

                    scope.$watch("active_gfx", (new_val) ->
                        _update()
                    )
                    $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"), (event) ->
                        _update()
                    )
            )
    }
])
