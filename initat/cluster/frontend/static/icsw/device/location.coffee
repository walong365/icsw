angular.module(
    "icsw.device.location",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).service("icswDeviceLocationTreeService", () ->
    class location_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = false
            @show_childs = false
            @single_select = true
            @location_re = new RegExp("^/location/.*$")
        selection_changed: (entry) =>
            if @scope.multi_device_mode
                @scope.new_md_selection(entry)
            else
                sel_list = @get_selected((node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
                )
                @scope.new_selection(sel_list)
        get_name : (t_entry) ->
            cat = t_entry.obj
            is_loc = @location_re.test(cat.full_name)
            if cat.depth > 1
                if @scope.DEBUG
                    r_info = "[#{cat.idx}] "
                else
                    r_info = ""
                r_info = "#{r_info}#{cat.full_name} (#{cat.name})"
                num_sel = @scope.sel_dict[cat.idx].length
                if num_sel and num_sel < @scope.num_devices
                    r_info = "#{r_info}, #{num_sel} of #{@scope.num_devices}"
                if cat.num_refs
                    r_info = "#{r_info} (refs=#{cat.num_refs})"
                num_locs = cat.location_gfxs.length
                if num_locs
                    r_info = "#{r_info}, #{num_locs} location gfx"
                if is_loc
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
        handle_click: (t_entry) ->
            cat = t_entry.obj
            @clear_active()
            if cat.depth > 1 and cat.location_gfxs.length
                if cat != @scope.gfx_cat
                    @scope.active_loc_gfx = undefined
                @scope.gfx_cat = cat
                t_entry.active = true
            else
                @scope.active_loc_gfx = undefined
                @scope.gfx_cat = undefined
            @show_active()
).controller("icswDeviceLocationCtrl", ["$scope", "restDataSource", "$q", "access_level_service", "icswDeviceLocationTreeService", "ICSW_URLS", "icswCallAjaxService",
    ($scope, restDataSource, $q, access_level_service, icswDeviceLocationTreeService, ICSW_URLS, icswCallAjaxService) ->
        access_level_service.install($scope)
        $scope.DEBUG = false
        $scope.loc_tree = new icswDeviceLocationTreeService($scope, {})
        # category with gfx 
        $scope.gfx_cat = undefined
        $scope.active_loc_gfx = undefined
        $scope.reload = (pk_list) ->
            $scope.device_pks = pk_list
            $scope.multi_device_mode = if $scope.device_pks.length > 1 then true else false
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_CATEGORY_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_mon_locations": true, "pks" : angular.toJson($scope.device_pks), "with_categories" : true}])
                restDataSource.reload([ICSW_URLS.REST_LOCATION_GFX_LIST, {}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = data[1]
                $scope.location_gfxs = data[2]
                $scope.num_devices = $scope.devices.length
                # build lut
                $scope.dev_lut = {}
                for _dev in $scope.devices
                    $scope.dev_lut[_dev.idx] = _dev
                $scope.loc_tree.change_select = true
                for dev in $scope.devices
                    # check all devices and disable change button when not all devices are in allowed list
                    if not $scope.acl_all(dev, "backbone.device.change_location", 7)
                        $scope.loc_tree.change_select = false
                loc_tree_lut = {}
                $scope.loc_tree.clear_root_nodes()
                # selection dict
                sel_dict = {}
                for entry in data[0]
                    if entry.full_name.match(/^\/location/)
                        sel_dict[entry.idx] = []
                        entry.location_gfxs = (loc_gfx.idx for loc_gfx in $scope.location_gfxs when loc_gfx.location == entry.idx)
                for dev in $scope.devices
                    for _sel in dev.categories
                        if _sel of sel_dict
                            sel_dict[_sel].push(dev.idx)
                $scope.sel_dict = sel_dict
                for entry in data[0]
                    if entry.full_name.match(/^\/location/)
                        t_entry = $scope.loc_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: sel_dict[entry.idx].length == $scope.num_devices})
                        if not entry.physical
                            # do not show select entry for structural entries
                            t_entry._show_select = false
                        loc_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of loc_tree_lut
                            loc_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            t_entry._show_select = false
                            $scope.loc_tree.add_root_node(t_entry)
                $scope.loc_tree_lut = loc_tree_lut
                $scope.update_monloc_count()
                $scope.loc_tree.show_selected(false)
            )
        $scope.new_md_selection = (entry) ->
            # for multi-device selection
            cat = entry.obj
            icswCallAjaxService
                url     : ICSW_URLS.BASE_CHANGE_CATEGORY
                data    :
                    "obj_type" : "device"
                    "multi"    : "1"
                    "obj_pks"  : angular.toJson((_entry.idx for _entry in $scope.devices))
                    "set"      : if entry.selected then "1" else "0"
                    "cat_pk"   : cat.idx
                success : (xml) =>
                    parse_xml_response(xml)
                    $scope.$apply(
                        $scope.update_tree(angular.fromJson($(xml).find("value[name='changes']").text()))
                        reload_sidebar_tree((_dev.idx for _dev in $scope.devices))
                    )
        $scope.new_selection = (sel_list) =>
            icswCallAjaxService
                url     : ICSW_URLS.BASE_CHANGE_CATEGORY
                data    :
                    "obj_type" : "device"
                    "obj_pk"   : $scope.device_pks[0]
                    "subtree"  : "/location"
                    "cur_sel"  : angular.toJson(sel_list)
                success : (xml) =>
                    parse_xml_response(xml)
                    # selectively reload sidebar tree
                    $scope.$apply(
                        $scope.update_tree(angular.fromJson($(xml).find("value[name='changes']").text()))
                        reload_sidebar_tree([$scope.devices[0].idx])
                   )
        $scope.update_monloc_count = () ->
            _gfx_lut = {}
            for _loc_gfx in $scope.location_gfxs
                _loc_gfx.num_devices = 0
                _loc_gfx.devices = []
                _gfx_lut[_loc_gfx.idx] = _loc_gfx
            _count = 0
            for _dev in $scope.devices
                for _entry in _dev.device_mon_location_set
                    _mon_loc = _gfx_lut[_entry.location_gfx]
                    if $scope.loc_tree_lut[_mon_loc.location].obj.physical
                        _count++
                    _mon_loc.num_devices++
                    _mon_loc.devices.push(_dev.idx)
            $scope.monloc_count = _count
            $scope.loc_tree.show_select = if $scope.monloc_count then false else true
        $scope.update_tree = (changes) ->
            $scope.active_loc_gfx = null
            for add in changes.added
                _dev = add[0]
                _cat = add[1]
                $scope.dev_lut[_dev].categories.push(_cat)
                $scope.sel_dict[_cat].push(_dev)
                $scope.loc_tree_lut[_cat].obj.num_refs++
            for rem in changes.removed
                _dev = rem[0]
                _cat = rem[1]
                _.remove($scope.sel_dict[_cat], (num) -> return num == _dev)
                _.remove($scope.dev_lut[_dev].categories, (num) -> return num == _cat)
                $scope.loc_tree_lut[_cat].obj.num_refs--
        $scope.get_location_gfxs = (cat) ->
            if cat
                return (entry for entry in $scope.location_gfxs when entry.idx in cat.location_gfxs and entry.image_stored)
            else
                return []
]).directive("icswDeviceLocationOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.location.overview")
        link : (scope, el, attrs) ->
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val and new_val.length
                    scope.reload(new_val)
            )
    }
]).directive("icswDeviceLocationList", ["$templateCache", "$compile", "$modal", "Restangular", "ICSW_URLS", ($templateCache, $compile, $modal, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.location.list")
        link : (scope, el, attrs) ->
            scope.activate_loc_gfx = (loc_gfx) ->
                scope.dml_list = undefined
                scope.active_loc_gfx = loc_gfx
                scope.dml_list = []
                scope.extra_dml_list = []
                # fetch list of all 
                Restangular.all(ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST.slice(1)).getList({"location_gfx": scope.active_loc_gfx.idx}).then((data) ->
                    # fill list
                    for _dev in scope.devices
                        _loc_list = (entry for entry in _dev.device_mon_location_set when entry.location_gfx == scope.active_loc_gfx.idx)
                        scope.dml_list = scope.dml_list.concat(_loc_list)
                    for _entry in scope.dml_list
                        _entry.is_extra = false
                        Restangular.restangularizeElement(null, _entry, ICSW_URLS.REST_DEVICE_MON_LOCATION_DETAIL.slice(1).slice(0, -2))
                    # extra data (not currently displayed)
                    _loc_pk = (entry.idx for entry in scope.dml_list)
                    _ext_list = (entry for entry in data when entry.idx not in _loc_pk)
                    for _entry in _ext_list
                        _entry.is_extra = true
                    scope.extra_dml_list = _ext_list
                )
            scope.get_device_list = (loc_gfx) ->
                return (scope.dev_lut[_entry].full_name for _entry in loc_gfx.devices).join("<br>")
            scope.get_num_devices = (loc_gfx) ->
                return loc_gfx.num_devices
            scope.get_button_class = (loc_gfx) ->
                if scope.active_loc_gfx? and loc_gfx.idx == scope.active_loc_gfx.idx
                    return "btn btn-sm btn-success"
                else if loc_gfx.num_devices
                    return "btn btn-sm btn-primary"
                else
                    return "btn btn-sm btn-default"
    }
]).directive("icswDeviceMonitoringLocationList", ["$templateCache", "$modal", "$q", "Restangular", "ICSW_URLS", ($templateCache, $modal, $q, Restangular, ICSW_URLS) ->
        restrict : "EA"
        template: $templateCache.get("icsw.device.monitoring.location.list")
        link : (scope, el, attrs) ->
            scope.dev_pks = []
            scope.set_pks = []
            scope.unset_pks = []
            scope.$watch("dml_list", (new_val) ->
                if new_val?
                    scope.dev_pks = []
                    for entry in scope.devices
                        # check if this device is really associated with the location 
                        _location = scope.loc_tree_lut[scope.active_loc_gfx.location].obj
                        if scope.active_loc_gfx.location in entry.categories and _location.physical
                            # allow addition if location is in categorie list and location is physical
                            scope.dev_pks.push(entry.idx)
                        else if not _location.physical
                            # always allow structural entries
                            scope.dev_pks.push(entry.idx)
                    scope.update_set_pks()
            )
            scope.update_set_pks = () ->
                scope.set_lut = {}
                for entry in scope.dml_list
                    scope.set_lut[entry.device] = entry
                scope.set_pks = (entry.device for entry in scope.dml_list when entry.device in scope.dev_pks)
                scope.unset_pks = (entry for entry in scope.dev_pks when entry not in scope.set_pks)
                scope.update_monloc_count()
            scope.use_device = (pk) ->
                Restangular.all(ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST.slice(1)).post({
                    "device" : pk
                    "location_gfx": scope.active_loc_gfx.idx
                    "location": scope.active_loc_gfx.location
                    "pos_x" : Math.min(scope.active_loc_gfx.width / 2, 50)
                    "pos_y" : Math.min(scope.active_loc_gfx.height / 2, 50)
                    "changed": false
                }).then((new_data) ->
                    # add to local list
                    scope.dml_list.push(new_data)
                    _dev = (_entry for _entry in scope.devices when _entry.idx == new_data.device)[0]
                    _dev.device_mon_location_set.push(new_data)
                    scope.update_set_pks()
                )
            scope.is_locked = (pk) ->
                # catch error (due to angular timing ?)
                if pk in scope.set_pks
                    return scope.set_lut[pk].locked
                else
                    return true    
            scope.remove = (pk) ->
                obj = scope.set_lut[pk]
                if obj.changed
                    simple_modal($modal, $q, "really delete location?").then(
                        () ->
                            scope.remove_dml(obj)
                    )
                else
                    scope.remove_dml(obj)
            scope.remove_dml = (obj) ->
                pk = obj.device
                obj.remove().then(
                    # remove from local list and device list
                    _dev = (_entry for _entry in scope.devices when _entry.idx == obj.device)[0]
                    _.remove(scope.dml_list, (_entry) -> return _entry.device == pk)
                    _.remove(_dev.device_mon_location_set, (_entry) -> return _entry.idx == obj.idx)
                    scope.update_set_pks()
                )
            scope.toggle_locked = (pk) ->
                dml = scope.set_lut[pk]
                dml.locked = !dml.locked
                dml.put()
]).directive("icswDeviceLocationMap", ["d3_service", "$templateCache", "$compile", "$modal", "Restangular", (d3_service, $templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            d3_service.d3().then((d3) ->
                scope.drag_node = d3.behavior.drag().on("dragstart", (d) ->
                    ).on("dragend", (d) ->
                        scope.dml_lut[d.idx].put()
                    ).on("drag", (d) ->
                        if not d.locked
                            d.changed = true
                            x = Math.max(Math.min(d3.event.x, scope.active_loc_gfx.width), 0)
                            y = Math.max(Math.min(d3.event.y, scope.active_loc_gfx.height), 0)
                            d.pos_x = parseInt(x)
                            d.pos_y = parseInt(y)
                            d3.select(this).attr("transform": "translate(#{x},#{y})")
                    )
                scope.rescale = () ->
                    scope.$apply(() -> scope.cur_scale = Math.max(Math.min(d3.event.scale, 1.0), 0.3))
                    scope.my_zoom.scale(scope.cur_scale)
                    scope.vis.attr("transform", "scale(#{scope.cur_scale})")
                scope.$watch("active_loc_gfx", (new_val) ->
                    scope.cur_scale = 1.0
                    element.children().remove()
                    if new_val?
                        width = new_val.width
                        height = new_val.height
                        svg = d3.select(element[0])
                            .append("svg:svg")
                            .attr(
                                "width": "#{width}px"
                                "height": "#{height}px"
                                "viewBox": "0 0 #{width} #{height}"
                            )
                        scope.my_zoom = d3.behavior.zoom()
                        scope.vis = svg.append("svg:g").call(scope.my_zoom.on("zoom", scope.rescale))
                        scope.vis.append("svg:image").attr(
                            "xlink:href": new_val.image_url
                            "width": width
                            "height": height
                            "preserveAspectRatio": "none"
                        )
                )
                scope.add_symbols = (centers) ->
                    centers.append("circle").attr
                        "r" : (n) -> return 18
                        "fill" : (d) -> return if d.locked then "white" else "#ff8888"
                        "stroke" : "black"
                        "stroke-width" : "1"
                    centers.append("text")
                        .attr
                            "text-anchor": "middle"
                            "alignment-baseline": "middle"
                            "stroke" : "white"
                            "font-weight": "bold"
                            "stroke-width": "2"
                        .text((d) -> return d.device_name)
                    centers.append("text")
                        .attr
                            "text-anchor": "middle"
                            "alignment-baseline": "middle"
                            "font-weight": "bold"
                            "fill" : "black"
                            "stroke-width": "0"
                        .text((d) -> return d.device_name)
                scope.$watch(
                    # need objectEquality == true
                    "dml_list",
                    (new_val) ->
                        if new_val?
                            # build lut
                            scope.dml_lut = {}
                            for entry in new_val
                                scope.dml_lut[entry.idx] = entry
                            scope.vis.selectAll(".pos").remove()
                            scope.centers = scope.vis.selectAll(".pos").data(scope.dml_list).enter()
                                .append("g").call(scope.drag_node)
                                .attr
                                    "class" : "pos"
                                    "node_id" : (n) -> return n.device
                                    "transform": (n) ->
                                        return "translate(#{n.pos_x}, #{n.pos_y})"
                            scope.add_symbols(scope.centers)
                    true
                )
                scope.$watch(
                    # need objectEquality == true
                    "extra_dml_list",
                    (new_val) ->
                        if new_val?
                            scope.vis.selectAll(".extra").remove()
                            scope.extra_centers = scope.vis.selectAll(".extra").data(scope.extra_dml_list).enter()
                                .append("g")
                                .attr
                                    "class" : "extra"
                                    "node_id" : (n) -> return n.device
                                    "transform": (n) ->
                                        return "translate(#{n.pos_x}, #{n.pos_y})"
                            scope.add_symbols(scope.extra_centers)
                    true
                )
            )
    }
])
