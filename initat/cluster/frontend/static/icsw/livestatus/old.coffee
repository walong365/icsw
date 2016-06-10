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

class hs_node
    # hierarchical structure node
    constructor: (@name, @check, @filter=false, @placeholder=false, @dummy=false) ->
        # name
        # check (may also be a dummy dict)
        @value = 1
        @root = @
        @children = []
        @show = true
        @depth = 0
        @clicked = false
    valid_device: () ->
        _r = false
        if @children.length == 1
            if @children[0].children.length == 1
                _r = true
        return _r
    reduce: () ->
        if @children.length
            return @children[0]
        else
            return @
    add_child: (entry) ->
        entry.root = @
        entry.depth = @depth + 1
        entry.parent = @
        @children.push(entry)
    iter_childs: (cb_f) ->
        cb_f(@)
        (_entry.iter_childs(cb_f) for _entry in @children)
    get_childs: (filter_f) ->
        _field = []
        if filter_f(@)
            _field.push(@)
        for _entry in @children
            _field = _field.concat(_entry.get_childs(filter_f))
        return _field
    clear_clicked: () ->
        # clear all clicked flags
        @clicked = false
        @show = true
        (_entry.clear_clicked() for _entry in @children)
    any_clicked: () ->
        res = @clicked
        if not res
            for _entry in @children
                res = res || _entry.any_clicked()
        return res
    handle_clicked: () ->
        # find clicked entry
        _clicked = @get_childs((obj) -> return obj.clicked)[0]
        @iter_childs(
            (obj) ->
                obj.show = false
        )
        parent = _clicked
        while parent?
            parent.show = true
            parent = parent.parent
        _clicked.iter_childs((obj) -> obj.show = true)
    
angular.module(
    "icsw.livestatus.livestatus.OLD",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).directive("newburst",
[
    "$compile", "$templateCache",
(
    $compile, $templateCache,
) ->
    return {
        restrict : "E"
        replace: true
        templateNamespace: "svg"
        template: $templateCache.get("icsw.device.livestatus.network_graph")
        controller: "icswDeviceLivestatusBurstCtrl"
        scope:
            filter: "=icswLivestatusFilter"
            data: "=icswMonitoringData"
            # device: "=icswDevice"
            # serviceFocus: "=serviceFocus"
            omitted_segments: "=omittedSegments"
            #ls_filter: "=lsFilter"
            #ls_devsel: "=lsDevsel"
            #is_drawn: "=isDrawn"
        link: (scope, element, attrs) ->
            scope.$watch("data", (new_val) ->
                scope.struct.monitoring_data = new_val
            )
            scope.$watch("filter", (new_val) ->
                scope.struct.filter = new_val
                if new_val
                    scope.start_loop()
            )

            scope.nodes = []
            scope.inner = parseInt(attrs["innerradius"] or 20)
            scope.outer = parseInt(attrs["outerradius"] or 120)
            scope.zoom = parseInt(attrs["zoom"] or 0)
            scope.font_stroke = parseInt(attrs["fontstroke"] or 0)
            scope.show_name = parseInt(attrs["showname"] or 0)
            scope.zoom_level = attrs["zoomLevel"] ? "s"
            scope.noninteractive = attrs["noninteractive"]  # defaults to false
            scope.active_part = null
            scope.propagate_filter = if attrs["propagateFilter"] then true else false
            #if not attrs["devicePk"]
            #    scope.$watch(
            #        scope.ls_devsel.changed
            #        (changed) ->
            #            scope.burst_sel(scope.ls_devsel.get(), false)
            #    )
            #scope.$watch("device_pk", (new_val) ->
            #    if new_val
            #        if angular.isString(new_val)
            #            data = (parseInt(_v) for _v in new_val.split(","))
            #        else
            #            data = [new_val]
            #        scope.burst_sel(data, true)
            #)
            # scope.burst_sel([scope.device], true)
            if attrs["drawAll"]?
                scope.draw_all = true
            else
                scope.draw_all = false
            scope.create_node = (name, settings) ->
                ns = 'http://www.w3.org/2000/svg'
                node = document.createElementNS(ns, name)
                for attr of settings
                    value = settings[attr]
                    if value?
                        node.setAttribute(attr, value)
                return node
            scope.get_children = (node, depth, struct) ->
                _num = 0
                if node.children.length
                    for _child in node.children
                        _num += scope.get_children(_child, depth+1, struct)
                else
                    if node.value?
                        _num = node.value
                node.width = _num
                if not struct[depth]?
                    struct[depth] = []
                struct[depth].push(node)
                return _num
            scope.set_focus_service = (srvc) ->
                if "serviceFocus" of attrs
                    scope.serviceFocus = srvc
            scope.set_data = (data, name) ->
                scope.sunburst_data = data
                scope.name = name
                # struct: dict of concentric circles, beginning with the innermost
                struct = {}
                scope.get_children(scope.sunburst_data, 0, struct)
                scope.max_depth = (idx for idx of struct).length
                scope.nodes = []
                omitted_segments = 0
                for idx of struct
                    if struct[idx].length
                        omitted_segments += scope.add_circle(parseInt(idx), struct[idx])
                # console.log "nodes", scope.nodes
                if attrs["omittedSegments"]?
                    scope.omittedSegments = omitted_segments
                if attrs["isDrawn"]?
                    scope.is_drawn = 1
            scope.add_circle = (idx, nodes) ->
                _len = _.reduce(
                    nodes,
                    (sum, obj) ->
                        return sum + obj.width
                    0
                )
                omitted_segments = 0
                outer = scope.get_inner(idx)
                inner = scope.get_outer(idx)
                # no nodes defined or first node is a dummy node (== no devices / checks found)
                if not _len or nodes[0].dummy
                    # create a dummy part
                    dummy_part = {}
                    dummy_part.children = {}
                    dummy_part.path = "M#{outer},0 " + \
                        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                        "L#{outer},0 " + \
                        "M#{inner},0 " + \
                        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                        "L#{inner},0 " + \
                        "Z"
                    scope.nodes.push(dummy_part)
                else
                    end_arc = 0
                    end_num = 0
                    # legend radii
                    inner_legend = (outer + inner) / 2
                    outer_legend = scope.outer * 1.125
                    local_omitted = 0
                    for part in nodes
                        if part.width
                            start_arc = end_arc #+ 1 * Math.PI / 180
                            start_sin = Math.sin(start_arc)
                            start_cos = Math.cos(start_arc)
                            end_num += part.width
                            end_arc = 2 * Math.PI * end_num / _len
                            if (end_arc - start_arc) * outer < 3 and not scope.draw_all
                                # arc is too small, do not draw
                                omitted_segments++
                                local_omitted++
                            else if part.placeholder
                                true
                            else
                                # console.log end_arc - start_arc
                                mean_arc = (start_arc + end_arc) / 2
                                mean_sin = Math.sin(mean_arc)
                                mean_cos = Math.cos(mean_arc)
                                end_sin = Math.sin(end_arc)
                                end_cos = Math.cos(end_arc)
                                if end_arc > start_arc + Math.PI
                                    _large_arc_flag = 1
                                else
                                    _large_arc_flag = 0
                                if mean_cos < 0
                                    legend_x = -outer_legend * 1.2
                                    part.legend_anchor = "end"
                                else
                                    legend_x = outer_legend * 1.2
                                    part.legend_anchor = "start"
                                part.legend_x = legend_x
                                part.legend_y = mean_sin * outer_legend
                                part.legendpath = "#{mean_cos * inner_legend},#{mean_sin * inner_legend} #{mean_cos * outer_legend},#{mean_sin * outer_legend} " + \
                                    "#{legend_x},#{mean_sin * outer_legend}"
                                if part.width == _len
                                    # trick: draw 2 semicircles
                                    part.path = "M#{outer},0 " + \
                                        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                                        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                                        "L#{outer},0 " + \
                                        "M#{inner},0 " + \
                                        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                                        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                                        "L#{inner},0 " + \
                                        "Z"
                                else
                                    part.path = "M#{start_cos * inner},#{start_sin * inner} L#{start_cos * outer},#{start_sin * outer} " + \
                                        "A#{outer},#{outer} 0 #{_large_arc_flag} 1 #{end_cos * outer},#{end_sin * outer} " + \
                                        "L#{end_cos * inner},#{end_sin * inner} " + \
                                        "A#{inner},#{inner} 0 #{_large_arc_flag} 0 #{start_cos * inner},#{start_sin * inner} " + \
                                        "Z"
                                scope.nodes.push(part)
                    if local_omitted
                        # some segmens were omitted, draw a circle
                        dummy_part = {children: {}, omitted: true}
                        dummy_part.path = "M#{outer},0 " + \
                            "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                            "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                            "L#{outer},0 " + \
                            "M#{inner},0 " + \
                            "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                            "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                            "L#{inner},0 " + \
                            "Z"
                        scope.nodes.push(dummy_part)
                return omitted_segments
            scope.get_inner = (idx) ->
                _inner = scope.inner + (scope.outer - scope.inner) * idx / scope.max_depth
                return _inner
            scope.get_outer = (idx) ->
                _outer = scope.inner + (scope.outer - scope.inner) * (idx + 1) / scope.max_depth
                return _outer
            scope.get_fill_color = (part) ->
                if part.check?
                    if part.check.ct == "system"
                        color = {
                            0 : "#66dd66"
                            1 : "#ff7777"
                            2 : "#ff0000"
                            4 : "#eeeeee"
                        }[part.check.state]
                    else if part.check.ct == "host"
                        color = {
                            0 : "#66dd66"
                            1 : "#ff7777"
                            2 : "#ff0000"
                        }[part.check.state]
                    else
                        color = {
                            0 : "#66dd66"
                            1 : "#dddd88"
                            2 : "#ff7777"
                            3 : "#ff0000"
                        }[part.check.state]
                else if part.omitted?
                    color = "#ffffff"
                else
                    color = "#dddddd"
                return color
            scope.get_fill_opacity = (part) ->
                if part.mouseover? and part.mouseover
                    return 0.4
                else if part.omitted
                    return 0
                else
                    return 0.8
            scope.mouse_enter = (part) ->
                if !scope.noninteractive
                    # console.log "enter"
                    if scope.active_part
                        # console.log "leave"
                        scope._mouse_leave(scope.active_part)
                    scope.set_focus_service(part.check)
                    if part.children.length
                        for _entry in part.children
                            if _entry.value
                                _entry.legend_show = true
                    else
                        if part.value
                            part.legend_show = true
                    scope.active_part = part
                    scope.set_mouseover(part, true)
            scope.mouse_click = (part) ->
                if scope.zoom and !scope.noninteractive
                    scope.sunburst_data.clear_clicked()
                    part.clicked = true
                    scope.handle_section_click()
            scope.mouse_leave = (part) ->
            scope._mouse_leave = (part) ->
                if !scope.noninteractive
                    if part.children.length
                        for _entry in part.children
                            _entry.legend_show = false
                    else
                        part.legend_show = false
                    scope.set_mouseover(part, false)
            scope.set_mouseover = (part, flag) ->
                while true
                    part.mouseover = flag
                    if part.parent?
                        part = part.parent
                    else
                        break
    }
]).controller("icswDeviceLivestatusBurstCtrl",
[
    "$scope", "icswDeviceTreeService", "icswDeviceLivestatusDataService", "$q",
    "icswDeviceLivestatusFunctions",
(
    $scope, icswDeviceTreeService, icswDeviceLivestatusDataService, $q,
    icswDeviceLivestatusFunctions,
) ->
    # $scope.host_entries = []
    # $scope.service_entries = []
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # filter
        filter: undefined
    }

    $scope.start_loop = () ->
        # console.log "start loop"
        $scope.struct.filter.change_notifier.promise.then(
            (ok) ->
            (error) ->
            (gen) ->
                b_data = icswDeviceLivestatusFunctions.build_structured_burst($scope.struct.monitoring_data)
                # console.log b_data
                $scope.set_data(b_data, "bla")
        )
    $scope._burst_data = null
    filter_propagated = false
    filter_list = []
    ignore_filter = false
    $scope.burst_sel = (_dev_list, single_selection) ->
        $scope.single_selection = single_selection
        $scope._burst_sel = _dev_list
        wait_list = [
            icswDeviceTreeService.load($scope.$id)
            icswDeviceLivestatusDataService.retain($scope.$id, _dev_list)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.dev_tree_lut = data[0].enabled_lut
                $scope.new_data(data[1])
                $scope.$watch(
                    () ->
                        return data[1].generation
                    () ->
                        $scope.new_data(data[1])
                )
        )
        $scope.new_data = (mres) ->
            $scope.host_entries = mres.hosts
            $scope.service_entries = mres.services
            $scope.burst_data = $scope.build_sunburst(
                $scope.host_entries
                $scope.service_entries
            )
            $scope.md_filter_changed()

        $scope.$watch("ls_filter", (new_val) ->
            if new_val
                # wait until ls_filter is set
                $scope.$watch(
                    new_val.changed
                    (new_filter) ->
                        $scope.md_filter_changed()

                )
        )
        $scope.apply_click_filter = (check) ->
            if filter_list.length and check._srv_id not in filter_list
                return false
            else
                return true

        $scope.handle_section_click = () ->
            # handle click on a defined section
            if $scope.burst_data? and $scope.dev_tree_lut?
                if $scope.burst_data.any_clicked()
                    $scope.burst_data.handle_clicked()
                if $scope.propagate_filter and not filter_propagated
                    filter_propagated = true
                    # register filter function
                    $scope.ls_filter.register_filter_func($scope.apply_click_filter)
                # create a list of all unique ids which are actually displayed
                filter_list = (entry.check._srv_id for entry in $scope.burst_data.get_childs((node) -> return node.show))
                # trigger filter change
                $scope.ls_filter.trigger()

        $scope.md_filter_changed = () ->
            # filter entries for table
            if $scope.ls_filter?
                # filter burstData
                if $scope.burst_data? and $scope.dev_tree_lut?
                    (_check_filter(_v) for _v in $scope.burst_data.get_childs(
                        (node) -> return node.filter)
                    )
                    if $scope.single_selection
                        $scope.set_data($scope.burst_data, $scope._burst_sel[0].full_name)
                    else
                        $scope.set_data($scope.burst_data, "")

        $scope.build_sunburst = (host_entries, service_entries) ->
            # build burst data
            _bdat = new hs_node(
                "System"
                # state 4: not set
                {"state": 4, "idx" : 0, "ct": "system"}
            )
            _devg_lut = {}
            # lut: dev idx to hs_nodes
            dev_hs_lut = {}
            for entry in host_entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _dev = $scope.dev_tree_lut[entry.custom_variables.device_pk]
                    if _dev.device_group_name not of _devg_lut
                        # we use the same index for devicegroups and services ...
                        _devg = new hs_node(
                            _dev.device_group_name
                            {
                                "ct"    : "group"
                                "state" : 0
                                "group_name" : _dev.device_group_name
                            }
                        )
                        _bdat.check.state = 0
                        _devg_lut[_devg.name] = _devg
                        _bdat.add_child(_devg)
                    else
                        _devg = _devg_lut[_dev.device_group_name]
                    # sunburst struct for device
                    entry.group_name = _dev.device_group_name
                    _dev_sbs = new hs_node(_dev.full_name, entry)
                    _devg.add_child(_dev_sbs)
                    # set devicegroup state
                    _devg.check.state = Math.max(_devg.check.state, _dev_sbs.check.state)
                    # set system state
                    _bdat.check.state = Math.max(_bdat.check.state, _devg.check.state)
                    dev_hs_lut[_dev.idx] = _dev_sbs
            for entry in service_entries
                # sanitize entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    dev_hs_lut[entry.custom_variables.device_pk].add_child(new hs_node(entry.description, entry, true))
            for idx, dev of dev_hs_lut
                if not dev.children.length
                    # add placeholder for non-existing services
                    dev.add_child(new hs_node("", {}, true, true))
            if $scope.zoom_level == "d"
                if _bdat.valid_device()
                    # valid device substructure, add dummy
                    return _bdat.reduce().reduce()
                else
                    _dev = new hs_node("", {}, false, true, true)
                    return _dev
            else if $scope.zoom_level == "g"
                return _bdat.reduce()
            else
                return _bdat

        _check_filter = (entry) ->
            show = $scope.ls_filter.apply_filter(entry.check, entry.show)
            entry.value = if show then 1 else 0
            return show

        $scope.$on("$destroy", () ->
            icswDeviceLivestatusDataService.destroy($scope.$id)
        )

]).directive("icswDeviceLivestatus",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.livestatus.livestatus.overview")
        controller: "icswDeviceLiveStatusCtrl"
    }
]).directive("icswDeviceLivestatusMap", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.map")
        controller: "icswDeviceLiveStatusCtrl"
        scope:
             devicepk: "@devicepk"
             # flag when svg is finished
             is_drawn: "=isDrawn"
             # external filter
             ls_filter: "=lsFilter"
        replace: true
        link : (scope, element, attrs) ->
            scope.$watch("devicepk", (data) ->
                if data
                    data = (parseInt(_v) for _v in data.split(","))
                    scope.new_devsel(data, [])
            )
    }
]).directive("icswDeviceLivestatusDeviceNode", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        replace: true
        template: $templateCache.get("icsw.device.livestatus.device.node")
        scope: {
            "dml": "=dml"
            "ls_filter": "=lsFilter"
        }
        link: (scope, element, attrs) ->
            # for network with connections
            dml = scope.dml
            scope.transform = "translate(#{dml.pos_x},#{dml.pos_y})"
    }
])