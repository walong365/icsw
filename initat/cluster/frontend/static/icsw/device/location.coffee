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
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    {span} = React.DOM
    class icswDeviceLoactionTree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @mode_entries = []
            @clear_tree()

        clear_tree: () =>
            @lut = {}
            @clear_root_nodes()

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
            return @scope.check_for_dml_leackage(entry)

        get_name: (t_entry) ->
            cat = t_entry.obj
            if cat.depth > 1
                # add spaces for display
                r_info = " #{cat.name} "
                # num_sel = t_entry.$match_pks.length
                # if num_sel and num_sel > 1
                #    r_info = "#{r_info}, #{num_sel} of #{@$num_devs}"
                # # console.log "cat=", cat.num_refs, cat
                # if cat.num_refs
                #    r_info = "#{r_info} (refs=#{cat.num_refs})"
                return r_info
            else if cat.depth
                return cat.full_name
            else
                return "TOP"

        get_pre_view_element: (entry) ->
            cat = entry.obj
            num_current_sel = entry.$match_pks.length
            num_total_sel = cat.num_refs
            if num_current_sel
                return span(
                    {
                        key: "_sd"
                        className: "label label-primary"
                        title: "Devices selected / total"
                    }
                    "#{num_current_sel} / #{num_total_sel}"
                )
            else if num_total_sel
                return span(
                    {
                        key: "_sd"
                        className: "label label-default"
                        title: "Devices selected"
                    }
                    "#{num_total_sel}"
                )
            else
                return null

        get_post_view_element: (entry) ->
            cat = entry.obj
            if cat.depth > 1
                return span(
                    {
                        key: "_info"
                    }
                    [
                        " "
                        if cat.$gfx_list.length then span({key: "gfx", className: "label label-success", title: "Attached Gfxs"}, cat.$gfx_list.length)
                        " "
                        span(
                            {
                                key: "_type"
                                className: if cat.physical then "glyphicon glyphicon-globe" else "glyphicon glyphicon-th-list"
                                title: if cat.pyhiscal then "Physical entry" else "Structural entry"
                            }
                        )
                        " "
                        if cat.locked then span({key: "lock", className: "fa fa-lock", title: "is locked"}) else null
                    ]
                )
            else
                return null

        handle_click: (event, t_entry, center_map=true) ->
            cat = t_entry.obj
            @clear_active()
            if cat.depth > 1
                if cat != @scope.struct.active_loc
                    @scope.struct.active_gfx = null
                # if cat.$gfx_list.length
                @scope.set_active_location(cat, center_map)
                t_entry.set_active(true)
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
    "icswToolsSimpleModalService", "icswCategoryLocationHelper",
(
    $scope, $q, icswAcessLevelService, icswDeviceTreeService,
    icswCategoryTreeService, $rootScope, ICSW_SIGNALS, blockUI,
    icswDeviceLocationTreeService, ICSW_URLS, icswSimpleAjaxCall,
    icswToolsSimpleModalService, icswCategoryLocationHelper,
) ->
    icswAcessLevelService.install($scope)
    my_proxy = icswCategoryLocationHelper.get_location_proxy()
    $scope.struct = {
        device_list_ready: false
        loc_tree: new icswDeviceLocationTreeService(
            $scope
            {
                name: "DeviceLocationTree"
                show_selection_buttons: false
                show_icons: false
                show_select: false
                show_descendants: false
                show_childs: false
            }
        )
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

    $scope.$on("$destroy", () ->
        $scope.struct.device_list_ready = false
    )

    $scope.google_maps_cb_fn = (fn_name, args) ->
        if fn_name == "marker_clicked"
            _loc = args
            _lc = $scope.struct.loc_tree
            # active node
            _node = _lc.lut[_loc.idx]
            _lc.handle_click(undefined, _node, center_map=false)

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
                $scope.struct.devices.length = 0
                for dev in devs
                    if not dev.is_meta_device
                        $scope.struct.devices.push(dev)
                $scope.struct.device_tree = device_tree
                # emit signal
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
        _list = []
        $scope.struct.tree.build_location_list(_list)
        $scope.struct.locations = (my_proxy.get(entry) for entry in _list)
        _ct.change_select = true
        for dev in $scope.struct.devices
            # check all devices and disable change button when not all devices are in allowed list
            if not $scope.acl_all(dev, "backbone.device.change_location", 7)
                _ct.update_flag("change_select", false)
                break

        _ct.stop_notify()
        _first_run = if _ct.root_nodes.length == 0 then true else false
        if not _first_run
            # update run
            _cur_exp = _ct.get_selected(
                (entry) ->
                    if entry.expand
                        return [entry.obj.idx]
                    else
                        return []
            )
            _cur_act = _ct.get_selected(
                (entry) ->
                    if entry.active
                        return [entry.obj.idx]
                    else
                        return []
            )

        _ct.clear_tree()
        _ct.create_mode_entries("location", $scope.struct.tree)

        if _first_run
            # first run
            _cur_exp = (entry.idx for entry in _ct.mode_entries when (entry.depth < 2))
            _cur_act = []

        # $scope.struct.active_loc = null
        # $scope.struct.active_gfx = null
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
            if _match_pks.length
                _exp = true
            else
                if _first_run
                    _exp = entry.depth < 2
                else
                    _exp = entry.idx in _cur_exp
            # console.log entry.idx, _match_pks, entry.idx in _cur_sel
            # console.log _match_pks, _dev_pks
            t_entry = _ct.create_node(
                {
                    folder: false
                    obj: entry
                    expand: _exp
                    active: entry.idx in _cur_act
                    selected: _match_pks.length == _num_devs
                    show_select: entry.useable
                }
            )
            # check if selected devices have location-gfx link to this category
            # _dml_dev_pks = (_dml.device for _dml in entry.$dml_list)
            # if _.intersection(_dml_dev_pks, _dev_pks).length and entry.physical
            #    _disable_select_dml = true
            # copy matching pks to tree entry (NOT entry because entry is global)
            t_entry.$match_pks = (_v for _v in _match_pks)
            _ct.lut[entry.idx] = t_entry
            if entry.parent and entry.parent of _ct.lut
                _ct.lut[entry.parent].add_child(t_entry)
                if t_entry.expand
                    # propagate expand level upwards
                    for _t_entry in _ct.get_parents(t_entry)
                        _t_entry.set_expand(true)
                if entry.depth < 2
                    # hide top-level entry (==/location/)
                    t_entry.update_flag("show_select", false)
            else
                # hide selection from root nodes
                t_entry.update_flag("show_select", false)
                _ct.add_root_node(t_entry)
        _ct.update_flag("show_select", true)
        # _ct.disable_select = _disable_select_dml
        _ct.start_notify()
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

    $scope.check_for_dml_leackage = (t_entry) =>
        # check if the selection / deselection of the current location would result in DML leackage
        loc = t_entry.obj
        dev_pks = (dev.idx for dev in $scope.struct.devices)
        # check if we would loose some dmls (then ask the user)
        if t_entry.selected
            _remove = true
            # check current location (loc will be deselected)
            check_locs = [loc]
        else
            _remove = false
            # select location, check all others for leackage (only if the new location is not structural)
            if loc.physical
                check_locs = (o_loc for o_loc in $scope.struct.loc_tree.mode_entries when o_loc.idx != loc.idx)
            else
                check_locs = []
        _dml_lost_physical = 0
        _dml_lost_structural = 0
        _gfx_lost = 0
        # iterate over check locations
        for c_loc in check_locs
            if c_loc.physical or _remove
                # only check for changes in physical locations (or removal of structural locations)
                for gfx in c_loc.$gfx_list
                    _to_delete = (dml for dml in gfx.$dml_list when dml.device in dev_pks)
                    if _to_delete.length
                        _gfx_lost++
                        if c_loc.physical
                            _dml_lost_physical += _to_delete.length
                        else
                            _dml_lost_structural += _to_delete.length
        defer = $q.defer()
        if _dml_lost_physical + _dml_lost_structural > 0
            _header =
            _lost_f = []
            if _dml_lost_physical
                _lost_f.push("#{_dml_lost_physical} physical")
            if _dml_lost_structural
                _lost_f.push("#{_dml_lost_structural} structural")
            _header =  "Modify will result in the lost of #{_lost_f.join(' and ')} placements on #{_gfx_lost} maps, continue ?"
            icswToolsSimpleModalService(
                _header
            ).then(
                (ok) ->
                    defer.resolve("go")
                (notok) ->
                    defer.reject("no")
            )
        else
            defer.resolve("go ahead")
        return defer.promise

    $scope.new_selection = (t_entry, sel_list) =>
        loc = t_entry.obj
        dev_pks = (dev.idx for dev in $scope.struct.devices)
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_CHANGE_CATEGORY
            data:
                obj_pks: angular.toJson(dev_pks)
                cat_pks: angular.toJson([loc.idx])
                set: if t_entry.selected then "1" else "0"
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

        link: (scope, el, attrs) ->
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
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_GFX_UPDATED"))
                )

            scope.$watch("location", (new_loc) ->
                if new_loc
                    update()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"), (event) ->
                update()
            )

            scope.activate_loc_gfx = ($event, loc_gfx) ->
                scope.active_gfx = loc_gfx
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
        controller: "icswDeviceMonitoringLocationListCtrl"
        link: (scope, element, attrs) ->
            scope.$watch("active_gfx", (new_val) ->
                scope.struct.active_gfx = new_val
                scope.update()
            )
            scope.$watch("devices", (new_val) ->
                scope.struct.devices = new_val
                scope.update()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"), (event) ->
                scope.update()
            )
    }
]).controller("icswDeviceMonitoringLocationListCtrl",
[
    "$q", "$scope", "icswCategoryTreeService", "icswDeviceTreeService", "blockUI",
    "ICSW_SIGNALS", "$rootScope",
(
    $q, $scope, icswCategoryTreeService, icswDeviceTreeService, blockUI,
    ICSW_SIGNALS, $rootScope,
) ->
    $scope.struct = {
        # data valid
        data_valid: false
        # category tree
        cat_tree: null
        # device tree
        device_tree: null
        # device list
        devices: []
        # active gfx
        active_gfx: null
    }
    $scope.update = () ->
        if $scope.struct.devices and $scope.struct.active_gfx
            $scope.struct.data_valid = false
            defer = $q.defer()
            if not $scope.struct.cat_tree
                $q.all(
                    [
                        icswCategoryTreeService.load($scope.$id)
                        icswDeviceTreeService.load($scope.$id)
                    ]
                ).then(
                    (data) ->
                        $scope.struct.cat_tree = data[0]
                        $scope.struct.device_tree = data[1]
                        defer.resolve("loaded")
                )
            else
                defer.resolve("already there")
            defer.promise.then(
                (load_msg) ->
                    $scope.struct.data_valid = true
            )

    # try load
    $scope.update()

    $scope.use_device = ($event, dev) ->
        # add device to map
        blockUI.start()
        _gfx = $scope.struct.active_gfx
        new_md = {
            device: dev.idx
            location_gfx: _gfx.idx
            location: _gfx.location
            pos_x: Math.min(_gfx.width / 2, 50)
            pos_y: Math.min(_gfx.height / 2, 50)
            changed: false
        }
        $scope.struct.cat_tree.create_device_mon_location_entry(new_md).then(
            (is_ok) ->
                $scope.struct.cat_tree.populate_gfx_location(
                    $scope.struct.active_gfx
                    $scope.struct.device_tree
                    $scope.struct.devices
                )
                $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"))
                blockUI.stop()
            (not_ok) ->
                blockUI.stop()
        )

    $scope.remove_dml = (dml) ->
        # remove device (== dml entry) from map
        # icswToolsSimpleModalService("really delete location?").then(
        blockUI.start()
        $scope.struct.cat_tree.delete_device_mon_location_entry(dml).then(
            (deleted) ->
                $scope.struct.cat_tree.populate_gfx_location(
                    $scope.struct.active_gfx
                    $scope.struct.device_tree
                    $scope.struct.devices
                )
                $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_CHANGED"))
                blockUI.stop()
            (not_del) ->
                blockUI.stop()
        )

    $scope.toggle_locked = (dml) ->
        # toggle dml locked state
        dml.locked = !dml.locked
        dml.put().then(
            (ok) ->
                $rootScope.$emit(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_GFX_UPDATED"))
        )

]).factory("icswDeviceLocationMapReactNode",
[
    "$q",
(
    $q,
) ->
    {g, circle, text} = React.DOM

    return React.createClass(
        propTypes: {
            dml: React.PropTypes.object
        }

        render: () ->
            dml = @props.dml
            # build node
            _id = dml.device
            if dml.$$selected
                if dml.locked
                    _fc = "#dddd44"
                    _opacity = 0.8
                else
                    _fc = "#44dd44"
                    _opacity = 0.8
            else
                _fc = "#aaaaaa"
                _opacity = 0.3
            return g(
                {
                    key: "c#{_id}"
                    transform: "translate(#{dml.pos_x}, #{dml.pos_y})"
                    className: "draggable"
                    id: _id
                }
                [
                    circle(
                        {
                            key: "c#{_id}"
                            r: 35
                            fill: _fc
                            stroke: "black"
                            opacity: _opacity
                            strokeWidth: 4
                        }
                    )
                    text(
                        {
                            key: "t#{_id}"
                            textAnchor: "middle"
                            alignmentBaseline: "middle"
                            stroke: "white"
                            paintOrder: "stroke"
                            fontWeight: "bold"
                            strokeWidth: 2
                        }
                        dml.$device.full_name
                    )

                ]
            )
    )
]).factory("icswDeviceLocationMapReact",
[
    "$q", "icswDeviceLocationMapReactNode", "svg_tools",
(
    $q, icswDeviceLocationMapReactNode, svg_tools,
) ->
    {div, h3, g, image, svg, polyline, circle, text} = React.DOM

    return React.createClass(
        propTypes: {
            location_gfx: React.PropTypes.object
            # monitoring_data: React.PropTypes.object
            # draw_parameters: React.PropTypes.object
            # device_tree: React.PropTypes.object
            # livestatus_filter: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                width: @props.location_gfx.width
                height: @props.location_gfx.height
                counter: 0
                zoom: 1.0
                dragging: false
                drag_node: false
            }

        componentWillMount: () ->
            # @umount_defer = $q.defer()

        componentWillUnmount: () ->
            # @umount_defer.reject("stop")

        force_redraw: () ->
            @setState(
                {counter: @state.counter + 1}
            )
            
        rescale: (point) ->
            point.x /= @state.zoom
            point.y /= @state.zoom
            return point

        render: () ->
            _gfx = @props.location_gfx
            {width, height} = @state
            _header = _gfx.name
            if _gfx.comment
                _header = "#{_header} (#{_gfx.comment})"
            _header = "#{_header} (Size: #{width} x #{height}, scale: #{_.round(@state.zoom, 3)}"

            # count
            _count = {locked: 0, unlocked: 0, unset: 0}
            for dml in _gfx.$dml_list
                # build node
                if dml.$$selected
                    if dml.locked
                        _count.locked++
                    else
                        _count.unlocked++
                else
                    _count.unset++
            _header = "#{_header}, " + ("#{value} #{key}" for key, value of _count when value).join(", ") + ")"
            _dml_list = [
                image(
                    {
                        key: "bgimage"
                        width: width
                        height: height
                        href: _gfx.image_url
                        preserveAspectRatio: "none"
                    }
                )
                polyline(
                    {
                        key: "imageborder"
                        style: {fill:"none", stroke:"black", strokeWidth:"3"}
                        points: "0,0 #{width},0 #{width},#{height} 0,#{height} 0 0"
                    }
                )
            ]
            for dml in _gfx.$dml_list
                _dml_list.push(
                    React.createElement(
                        icswDeviceLocationMapReactNode
                        {
                            dml: dml
                        }
                    )
                )
            return div(
                {
                    key: "top"
                    onWheel: (event) =>
                        if event.deltaY > 0
                            _fac = 0.95
                        else
                            _fac = 1.05
                        _zoom = _.max([_.min([@state.zoom * _fac, 3.0]), 0.1])
                        @setState({zoom: _zoom})
                        event.preventDefault()
                }
                [
                    h3(
                        {key: "header"}
                        _header
                    )
                    svg(
                        {
                            key: "svgouter"
                            width: "100%"
                            height: "100%"
                            # preserveAspectRatio: "xMidYMid meet"
                            viewBox: "0 0 #{width} #{height}"
                            onMouseDown: (event) =>
                                event.stopPropagation()
                                drag_el = svg_tools.find_draggable_element($(event.target))
                                if drag_el
                                    # get dml
                                    _id = parseInt(drag_el.attr("id"))
                                    dml = (entry for entry in @props.location_gfx.$dml_list when entry.device == _id)
                                    if dml.length
                                        dml = dml[0]
                                        if dml.$$selected and not dml.locked
                                            @setState({dragging: true, drag_node: dml})
                            onMouseMove: (event) =>
                                # if drag_el
                                if @state.dragging
                                    event.stopPropagation()
                                    event.preventDefault()
                                    _svg = $(ReactDOM.findDOMNode(@)).find("svg:first")[0]
                                    _cp = @rescale(svg_tools.get_abs_coordinate(_svg, event.clientX, event.clientY))
                                    @state.drag_node.pos_x = parseInt(_cp.x)
                                    @state.drag_node.pos_y = parseInt(_cp.y)
                                    @force_redraw()
                            onMouseUp: (event) =>
                                if @state.dragging
                                    # @props.drag_end(@props.dml)
                                    @state.drag_node.put()
                                    @setState({dragging: false, drag_node: null})

                        }
                        [
                            g(
                                {
                                    key: "gouter"
                                    transform: "scale(#{@state.zoom})"
                                }
                                _dml_list
                            )
                        ]
                    )

                ]
            )
    )
]).directive("icswDeviceLocationMap",
[
    "icswDeviceLocationMapReact", "$rootScope", "ICSW_SIGNALS",
(
    icswDeviceLocationMapReact, $rootScope, ICSW_SIGNALS,
) ->
    return {
        restrict: "EA"
        scope:
            # active gfx
            active_gfx: "=icswActiveGfx"
        link: (scope, element, attrs) ->
            react_el = undefined
            scope.$watch("active_gfx", (new_val) ->
                if new_val
                    react_el = ReactDOM.render(
                        React.createElement(
                            icswDeviceLocationMapReact
                            {
                                location_gfx: scope.active_gfx
                            }
                        )
                        element[0]
                    )
                else
                    element.children().remove()
                    react_el = undefined
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_LOCATION_SETTINGS_GFX_UPDATED"), (event) ->
                if react_el?
                    react_el.force_redraw()
            )
    }
])
