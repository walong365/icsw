# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

# network graphing tool, topology components

angular.module(
    "icsw.livestatus.comp.functions",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
    ]
).service("icswBurstDrawParameters", [
    "$q"
(
    $q,
) ->
    class icswBurstDrawParameters
        constructor: (args) ->
            # inner radius
            @inner_radius = 20
            # outer radius
            @outer_radius = 60
            # collapse rings with only one segment
            @collapse_one_element_rings = true
            # start ring, 0 ... system, 1 ... group, 2 ... device, 3 .... service
            @start_ring = 2
            # special parameter to filter mon_results
            @device_idx_filter = undefined
            # is interactive (show descriptions on mouseover)
            @is_interactive = false
            # show details on mouseover
            @show_details = false
            # check for too small segments
            @omit_small_segments = false
            # segment treshold, arc * outer_radius must be greater than this valu
            @small_segment_threshold = 3
            for _key, _value of args
                # console.info "BurstDrawParam", _key, _value
                if not @[_key]?
                    console.error "Unknown icswBurstDrawParameter", _key, _value
                else
                    @[_key] = _value

        create_ring_draw_list: (ring_keys) =>
            _idx = 0
            _results = []
            _num_rings = ring_keys.length
            _arc_offset = 0.0
            if _num_rings
                _width = @outer_radius - @inner_radius
                for _key in ring_keys
                    _inner_rad = @inner_radius + _idx * _width / _num_rings
                    _outer_rad = @inner_radius + (_idx + 1 ) * _width / _num_rings
                    _idx++
                    _results.push([_key, _inner_rad, _outer_rad, _arc_offset])
                    # always keep arc_offset at zero
                    _arc_offset += 0.0
            return _results

        start_feed: () =>
            @segments_omitted = 0
            @segments_drawn = 0

        draw_segment: (val) =>
            _draw = if @omit_small_segments and val < @small_segment_threshold then false else true
            if _draw
                @segments_drawn++
            else
                @segments_omitted++
            return _draw

        get_segment_info: () =>
            _r_str = "#{@segments_drawn} Segments"
            if @segments_omitted
                _r_str = "#{_r_str}, #{@segments_omitted} omitted"
                
            return _r_str
            
        do_layout: () =>
            # calc some settings for layout
            _outer = @outer_radius
            if @is_interactive
                @text_radius = 1.1 * _outer
                @text_width = 1.15 * _outer
                @total_width = 2 * _outer * 1.2 + 200
                @total_height = 2 * _outer * 1.2
            else
                @total_width = 2 * _outer
                @total_height = 2 * _outer
            

]).service("icswStructuredBurstNode", [
    "$q",
(
    $q,
) ->
    class icswStructuredBurstNode
        constructor: (@parent, @name, @idx, @check, @filter=false, @placeholder=false) ->
            # attributes:
            # o root (top level element)
            # o parent (parent element)
            # name
            # check (may also be a dummy dict)
            @value = 1
            # childre lookup table
            @lut = {}
            @children = []
            @depth = 0
            # show legend
            @show_legend = false
            # selection flags
            @sel_by_parent = false
            @sel_by_child = false
            # no longer used
            # @show = true
            @clicked = false
            if @depth == 0
                # only for root-nodes
                # flag, not in use right now
                @balanced = false
            # parent linking
            if @parent?
                @parent.add_child(@)
            else
                @root = @

        clear_focus: () ->
            # clear all show_legend flags downwards
            @show_legend = false
            @sel_by_parent = false
            @sel_by_child = false
            (_el.clear_focus() for _el in @children)

        # iterator functions
        iterate_upward: (cb_func) ->
            cb_func(@)
            if @parent?
                @parent.iterate_upward(cb_func)

        iterate_downward: (cb_func) ->
            cb_func(@)
            (_child.iterate_downward(cb_func) for _child in @children)

        set_clicked: () ->
            @root.iter_childs((node) -> node.clicked = false)
            @clicked = true
            
        set_focus: () ->
            @iterate_upward((node) -> node.sel_by_child = true)
            @iterate_downward((node) -> node.sel_by_parent = true)

            @show_legend = true
            for _el in @children
                _el.show_legend = true


        clear_clicked: () ->
            # clear all clicked flags
            @root.iter_childs((node) -> node.clicked = false)

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

        balance: () ->
            if @children.length
                _width = _.sum(_child.balance() for _child in @children)
            else
                # constant one or better use value ?
                _width = 1
            # the sum of all widths on any given level is (of course) the same
            @width = _width
            if @depth == 0
                # create ring lookup table
                @ring_lut = {}
                @iter_childs(
                    (node) ->
                        if node.depth not of node.root.ring_lut
                            node.root.ring_lut[node.depth] = []
                        node.root.ring_lut[node.depth].push(node)
                )
                @element_list = []
            return _width

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
            entry.root = @root
            entry.depth = @depth + 1
            @children.push(entry)
            @lut[entry.idx] = entry

        get_self_and_childs: () ->
            _r = [@]
            for node in @children
                _r = _.concat(_r, node.get_self_and_childs())
            return _r

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

]).service("icswDeviceLivestatusFunctions",
[
    "$q", "icswStructuredBurstNode", "icswSaltMonitoringResultService",
(
    $q, icswStructuredBurstNode, icswSaltMonitoringResultService,
) ->

    ring_path = (inner, outer) ->
        # return the SVG path for a ring with radi inner and outer
        _path = "M#{outer},0 " + \
        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
        "L#{outer},0 " + \
        "M#{inner},0 " + \
        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
        "L#{inner},0 " + \
        "Z"
        return _path

    ring_segment_path = (inner, outer, start_arc, end_arc) ->
        # returns the SVG path for a ring segment
        start_sin = Math.sin(start_arc)
        start_cos = Math.cos(start_arc)
        end_sin = Math.sin(end_arc)
        end_cos = Math.cos(end_arc)
        if end_arc > start_arc + Math.PI
            _large_arc_flag = 1
        else
            _large_arc_flag = 0
        _path = "M#{start_cos * inner},#{start_sin * inner} L#{start_cos * outer},#{start_sin * outer} " + \
            "A#{outer},#{outer} 0 #{_large_arc_flag} 1 #{end_cos * outer},#{end_sin * outer} " + \
            "L#{end_cos * inner},#{end_sin * inner} " + \
            "A#{inner},#{inner} 0 #{_large_arc_flag} 0 #{start_cos * inner},#{start_sin * inner} " + \
            "Z"
        return _path

    build_burst_ring = (inner, outer, arc_offset, key_prefix, r_data, draw_params) ->
        # offset
        # arc_offset = 0.2
        end_arc = arc_offset
        end_num = 0
        _ia = draw_params.is_interactive
        _len = _.sum((entry.width for entry in r_data))
        _result = []
        # flag if all segments are omitted
        all_omitted = true
        if _len
            _idx = 0
            for node in r_data
                srvc = node.check
                _idx++
                start_arc = end_arc
                end_num += node.width
                end_arc = 2 * Math.PI * end_num / _len + arc_offset
                if draw_params.draw_segment((end_arc - start_arc) * outer)
                    all_omitted = false
                    if _len == 1 and draw_params.collapse_one_element_rings
                        _path = ring_path(inner, outer)
                    else if _len == node.width
                        # full ring (no segment), to fix drawing issues
                        _path = ring_path(inner, outer)
                    else
                        _path = ring_segment_path(inner, outer, start_arc, end_arc)
                    # _el is a path element, (nearly) ready to be rendered via SVG
                    # $$segment is the pointer to the StructuredBurstNode and holds important flags and
                    #    structural information
                    # $$service is the pointer to the linked service check (may be a dummy check)
                    if not srvc.$$data?
                        console.warn "no $$data tag in", srvc
                    _el = {
                        key: "path.#{key_prefix}.#{_idx}"
                        d: _path
                        #classes : srvc.className #not needed any more?
                        className: "sb-lines #{srvc.$$data.svgClassName}"
                        $$segment: node
                        # link to check (node or device or devicegroup or system)
                        $$service: srvc
                    }
                    if _ia
                        # add values for interactive display
                        _el.$$mean_arc = (start_arc + end_arc) / 2.0
                        _el.$$mean_radius = (outer + inner) / 2.0
                    _result.push(_el)
                if all_omitted
                    # all segments omitted, draw dummy graph
                    _dummy = icswSaltMonitoringResultService.get_dummy_service_entry()
                    _result.push(
                        {
                            key: "path.#{key_prefix}.omit"
                            d: ring_path(inner, outer)
                            $$service: _dummy
                            className: "sb-lines"
                        }
                    )
        else
            _dummy = icswSaltMonitoringResultService.get_dummy_service_entry()
            # draw an empty (== grey) ring
            _result.push(
                {
                    key: "path.#{key_prefix}.empty"
                    d: ring_path(inner, outer)
                    $$service: _dummy
                    className: "sb-lines"
                }
            )
        return _result

    build_structured_burst = (mon_data, draw_params) ->
        _root_node = new icswStructuredBurstNode(
            null
            "System"
            0
            icswSaltMonitoringResultService.get_system_entry("System")
        )
        #if node.id of @props.monitoring_data.host_lut
        #    host_data = @props.monitoring_data.host_lut[node.id]
        #    if not host_data.$$show
        #        host_data = undefined
        #else
        #    host_data = undefined
        # service ids to show
        _sts = (entry.$$idx for entry in mon_data.services)
        for host in mon_data.hosts
            dev = host.$$icswDevice
            if not draw_params.device_idx_filter? or dev.idx == draw_params.device_idx_filter
                devg = host.$$icswDeviceGroup
                if devg.idx not of _root_node.lut
                    # add device group ring
                    _devg = new icswStructuredBurstNode(
                        _root_node
                        devg.name
                        devg.idx
                        icswSaltMonitoringResultService.get_device_group_entry(devg.name)
                    )
                else
                    _devg = _root_node.lut[devg.idx]
                # _devg holds now the structured node for the device group
                _dev = new icswStructuredBurstNode(
                    _devg
                    dev.name
                    dev.idx
                    host
                )
                for service in host.$$service_list
                    # check for filter
                    if service.$$idx in _sts
                        new icswStructuredBurstNode(_dev, service.description, service.$$idx, service, true)
                if not _dev.children.length
                    # add dummy service for devices without services
                    new icswStructuredBurstNode(
                        _dev
                        ""
                        0
                        icswSaltMonitoringResultService.get_dummy_service_entry("---")
                        false
                        true
                    )

        # balance nodes, set width of each segment, create ring lut

        _root_node.balance()

        # set states in ring 1 and 0
        for _ring_idx in [1, 0]
            if _ring_idx of _root_node.ring_lut
                for _entry in _root_node.ring_lut[_ring_idx]
                    if _entry.children.length
                        _entry.check.state = _.max((_child.check.state for _child in _entry.children))
                    else
                        _entry.check.state = 3
                    icswSaltMonitoringResultService.salt_device_state(_entry.check)

        # draw
        _ring_keys= (
            _entry for _entry in _.map(
                _.keys(_root_node.ring_lut)
                (_key) ->
                    return parseInt(_key)
            ).sort() when _entry >= draw_params.start_ring
        )

        # reset some draw parameters (omitted segments)
        draw_params.start_feed()

        for [_ring, _inner_rad, _outer_rad, _arc_offset] in draw_params.create_ring_draw_list(_ring_keys)
            _root_node.element_list = _.concat(_root_node.element_list, build_burst_ring(_inner_rad, _outer_rad, _arc_offset, "ring#{_ring}", _root_node.ring_lut[_ring], draw_params))
        return _root_node
        
    return {

        build_structured_burst: (mon_data, draw_params) ->
            # mon_data is a filtered instance of icswMonitoringResult
            return build_structured_burst(mon_data, draw_params)

        ring_segment_path: ring_segment_path
        ring_path: ring_path
    }

])
