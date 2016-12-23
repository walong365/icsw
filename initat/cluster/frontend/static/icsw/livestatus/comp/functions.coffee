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
            #contains tooltip functions
            @tooltip = {}
            # segment treshold, arc * outer_radius must be greater than this valu
            @small_segment_threshold = 3
            for _key, _value of args
                # console.info "BurstDrawParam", _key, _value, @
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
            @segments_hidden = 0

        end_feed: () =>
            # dummy function (for now)

        draw_segment: (burst_node, val) =>
            if burst_node.no_display
                @segments_hidden++
                _draw = false
            else
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
            @total_width = 2 * _outer
            @total_height = 2 * _outer
            

]).service("icswStructuredBurstNode",
[
    "$q", "icswSaltMonitoringResultService",
(
    $q, icswSaltMonitoringResultService,
) ->
    ALLOWED_NODE_TYPES = ["system", "devicegroup", "device", "service", "category"]
    class icswStructuredBurstNode
        constructor: (@parent, @node_type, @name, @idx, @check, args) ->
            # attributes:
            # o root (top level element)
            # o parent (parent element)
            # node_type (one of system, devicegroup, device, service or category)
            # idx (unique for the burst or null / undefined)
            # name
            # check (may also be a dummy dict)
            #
            # check node_type
            if @node_type not in ALLOWED_NODE_TYPES
                throw new Error("node type '#{@node_type}' not allowed")
            # for balancing
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
            @filter = false
            @placeholder = false
            @no_display = false
            @category = null
            for key, value of args
                if key not of @
                    console.error "Unknown key/value pair '#{key}/#{value}' for icswStructuredBurstNode"
                else
                    @[key] = value
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
                # set global luts
                @root_lut = {}
                @name_lut = {}
                @root_lut[@idx] = @
                @name_lut[@name] = @

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

        iter_childs: (cb_f) ->
            cb_f(@)
            (_entry.iter_childs(cb_f) for _entry in @children)

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
            @root.root_lut[entry.idx] = entry
            @root.name_lut[entry.name] = entry

        get_self_and_childs: () ->
            _r = [@]
            for node in @children
                _r = _.concat(_r, node.get_self_and_childs())
            return _r

        get_childs: (filter_f) ->
            _field = []
            if filter_f(@)
                _field.push(@)
            for _entry in @children
                _field = _field.concat(_entry.get_childs(filter_f))
            return _field

        start_ds_feed: (state_type) ->
            @__state_type = state_type
            @state_dict = {}

        end_ds_feed: () ->
            if _.keys(@state_dict).length
                # get all state keys
                _state_keys = (parseInt(_key) for _key in _.keys(@state_dict))
                @_set_worst_state_from_list(_state_keys)

        set_state_from_children: () ->
            # get states from all children
            all_states = _.uniq((entry.check.state for entry in @get_self_and_childs()))
            @_set_worst_state_from_list(all_states)

        _set_worst_state_from_list: (in_list) ->
            # set it
            @check.state = icswSaltMonitoringResultService.get_worst_state(in_list, @__state_type)
            icswSaltMonitoringResultService["salt_#{@__state_type}_state"](@check)

        feed_service: (srv) ->
            return @_feed_ds(srv)

        feed_device: (dev) ->
            return @_feed_ds(dev)

        _feed_ds: (entry) ->
            state = entry.state
            if state not of @state_dict
                @state_dict[state] = 0
            @state_dict[state]++

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
        if _len
            _idx = 0
            _omit_idx = 0
            _omit_list = []
            for node in r_data
                srvc = node.check
                _idx++
                start_arc = end_arc
                end_num += node.width
                end_arc = 2 * Math.PI * end_num / _len + arc_offset
                if draw_params.draw_segment(node, (end_arc - start_arc) * outer)
                    if _len == 1 and draw_params.collapse_one_element_rings
                        _path = ring_path(inner, outer)
                    else if _len == node.width
                        # full ring (no segment), to fix drawing issues
                        _path = ring_path(inner, outer)
                    else
                        _path = ring_segment_path(inner, outer, start_arc, end_arc)
                    # _el is a path element, (nearly) ready to be rendered via SVG
                    # $$burstNode is the pointer to the StructuredBurstNode and holds important flags and
                    #    structural information
                    # $$service is the pointer to the linked service check (may be a dummy check)
                    if not srvc.$$data?
                        console.warn "no $$data tag in #{srvc}"
                    _el = {
                        key: "path.#{key_prefix}.#{_idx}"
                        d: _path
                        $$burstNode: node
                        # link to check (node or device or devicegroup or system)
                        $$service: srvc
                        className: srvc.$$data.svgClassName
                    }
                    if _ia
                        # add values for interactive display
                        _el.$$mean_arc = (start_arc + end_arc) / 2.0
                        _el.$$mean_radius = (outer + inner) / 2.0
                    _result.push(_el)
                    node.$$path = _el
                else if not node.no_display
                    _omit_list.push([end_num - node.width, end_num])
            if _omit_list.length
                _dummy = icswSaltMonitoringResultService.get_dummy_service_entry("omitted", 10)
                # any omitted ?
                if _omit_list.length == r_data.length
                    # all segments omitted, draw dummy graph
                    _omit_idx++
                    _el = {
                        key: "path.#{key_prefix}.omit#{_omit_idx}"
                        d: ring_path(inner, outer)
                        $$service: _dummy
                    }
                    _result.push(_el)
                    node.$$path = _el
                else
                    # not all omitted, get optimized omit-list
                    _new_omit_list = []
                    _prev_end = undefined
                    for entry in _omit_list
                        # console.log _new_omit_list
                        if _prev_end? and _prev_end == entry[0]
                            _prev = _new_omit_list.pop(-1)
                            _new_omit_list.push([_prev[0], entry[1]])
                        else
                            _new_omit_list.push(entry)
                        _prev_end = entry[1]
                    for [start_num, end_num] in _new_omit_list
                        _omit_idx++
                        _result.push(
                            {
                                key: "path.#{key_prefix}.omit#{_omit_idx}"
                                d: ring_segment_path(inner, outer, 2 * Math.PI * start_num / _len + arc_offset, 2 * Math.PI * end_num / _len + arc_offset)
                                $$service: _dummy
                            }
                        )
        else
            _dummy = icswSaltMonitoringResultService.get_dummy_service_entry("n/a", 4)
            # draw an empty (== grey) ring
            _result.push(
                {
                    key: "path.#{key_prefix}.empty"
                    d: ring_path(inner, outer)
                    $$service: _dummy
                }
            )
        return _result

    _recalc_burst = (root_node, draw_params) ->
        # draw
        _ring_keys= (
            _entry for _entry in _.map(
                _.keys(root_node.ring_lut)
                (_key) ->
                    return parseInt(_key)
            ).sort() when _entry >= draw_params.start_ring
        )

        # reset some draw parameters (omitted segments)
        draw_params.start_feed()

        # create the actual draw element list
        # maybe we should change this to salting the structured nodes with draw info
        # attention:
        # - some burstnodes have no element to draw
        # - some burstnodes are linked together
        # - ???
        for [_ring, _inner_rad, _outer_rad, _arc_offset] in draw_params.create_ring_draw_list(_ring_keys)
            # console.log "s", root_node.element_list.length
            root_node.element_list = _.concat(
                root_node.element_list
                build_burst_ring(_inner_rad, _outer_rad, _arc_offset, "ring#{_ring}", root_node.ring_lut[_ring], draw_params)
            )
            # console.log "e", root_node.element_list.length
        draw_params.end_feed()

    build_structured_burst = (mon_data, draw_params) ->
        # build burst for monitoring data (system -> group -> device -> check)
        _root_node = new icswStructuredBurstNode(
            null
            "system"
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
                        "devicegroup"
                        devg.name
                        devg.idx
                        icswSaltMonitoringResultService.get_device_group_entry(devg.name)
                    )
                else
                    _devg = _root_node.lut[devg.idx]
                # _devg holds now the structured node for the device group
                _dev = new icswStructuredBurstNode(
                    _devg
                    "device"
                    dev.name
                    dev.idx
                    host
                )
                for service in host.$$service_list
                    # check for filter
                    if service.$$idx in _sts
                        new icswStructuredBurstNode(
                            _dev
                            "service"
                            service.description
                            service.$$idx
                            service
                            {
                                filter: true
                            }
                        )
                if not _dev.children.length
                    # add dummy service for devices without services
                    new icswStructuredBurstNode(
                        _dev
                        "service"
                        ""
                        0
                        icswSaltMonitoringResultService.get_dummy_service_entry("---")
                        {
                            filter: false
                            placeholder: true
                        }
                    )

        # balance nodes, set width of each segment, create ring lut

        _root_node.balance()

        # set states in ring 1 and 0
        for _ring_idx in [1, 0]
            if _ring_idx of _root_node.ring_lut
                for _entry in _root_node.ring_lut[_ring_idx]
                    if _entry.children.length
                        _entry.check.state = icswSaltMonitoringResultService.get_worst_state((_child.check.state for _child in _entry.children), "device")
                    else
                        _entry.check.state = 3
                    icswSaltMonitoringResultService.salt_device_state(_entry.check)

        _recalc_burst(_root_node, draw_params)

        return _root_node

    build_structured_category_burst = (mon_data, sub_tree, cat_tree, draw_params, sum_childs) ->
        cat_pks = mon_data["used_#{sub_tree}_cats"]
        _display_pks = _.clone(cat_pks)
        _root_node = cat_tree.full_name_lut["/#{sub_tree}"]
        if _root_node.idx in _display_pks
            console.error "rootnode for #{sub_tree} already in list, strange ..."
        else
            _display_pks.push(_root_node.idx)
        for _cat_pk in cat_pks
            _node = cat_tree.lut[_cat_pk]
            while _node.parent
                _node = cat_tree.lut[_node.parent]
                if _node.idx not in _display_pks and _node.depth
                    _display_pks.push(_node.idx)
        root_pk = _root_node.idx
        _to_add = _.clone(_display_pks)
        _already_added = []
        # pks of parent ring
        parent_pks = []
        # dummy idx
        dummy_idx = -1
        # root node for unspecified categories
        uncat_root_node = new icswStructuredBurstNode(
            null
            "category"
            "uncat"
            0
            icswSaltMonitoringResultService.get_dummy_service_entry("uncategorized")
            {
                category: {idx: 0, depth: 0}
            }
        )
        # node lut
        node_lut = {}
        node_lut[0] = uncat_root_node
        while _to_add.length
            if not _already_added.length
                # get root pk
                _added = [root_pk]
            else
                # second and other
                # get all nodes which are direct parents
                _added = (_pk for _pk in _to_add when cat_tree.lut[_pk].parent in parent_pks)
            _to_add = _.difference(_to_add, _added)
            if not _already_added.length
                # build burst for category subtree (root_node -> sub_node -> ...)
                _cat = cat_tree.lut[root_pk]
                _root_node = new icswStructuredBurstNode(
                    uncat_root_node
                    "category"
                    _cat.full_name
                    root_pk
                    icswSaltMonitoringResultService.get_dummy_service_entry(_cat.full_name)
                    {
                        category: _cat
                    }
                )
                node_lut[root_pk] = _root_node
            else
                touched_parents = []
                for _pk in _added
                    _cat = cat_tree.lut[_pk]
                    _parent_pk = cat_tree.lut[_pk].parent
                    if _parent_pk not in touched_parents
                        touched_parents.push(_parent_pk)
                    sub_node = new icswStructuredBurstNode(
                        node_lut[_parent_pk]
                        "category"
                        _cat.full_name
                        _pk
                        icswSaltMonitoringResultService.get_dummy_service_entry(_cat.full_name)
                        {
                            category: _cat
                        }
                    )
                    node_lut[_pk] = sub_node
                for _dummy_pk in _.difference(parent_pks, touched_parents)
                    dummy_idx--
                    sub_node = new icswStructuredBurstNode(
                        node_lut[_dummy_pk]
                        "category"
                        "dummy"
                        dummy_idx
                        icswSaltMonitoringResultService.get_dummy_service_entry("omitted", 10)
                        {
                            filter: false
                            placeholder: true
                            no_display: true
                        }
                    )
                    _added.push(dummy_idx)
                    node_lut[dummy_idx] = sub_node
                    # console.log "d=", _dummy_pk
            if not _added.length
                break
            else
                _already_added = _.concat(_already_added, _added)
                parent_pks = _added
        # check categories
        # src list
        for pk, cat_node of node_lut
            # sigh ...
            pk = parseInt(pk)
            if pk >= 0
                # ignore dummy nodes
                cat_node.start_ds_feed(if sub_tree == "mon" then "service" else "device")
                # console.log pk, src_list.length
                if sub_tree == "mon"
                    for el in mon_data.services
                        if "cat_pks" of el.custom_variables
                            if pk in el.custom_variables.cat_pks
                                cat_node.feed_service(el)
                            else if pk == 0 and not el.custom_variables.cat_pks.length
                                # add to uncat service
                                uncat_root_node.feed_service(el)
                        else if pk == 0
                            # add to uncat service
                            uncat_root_node.feed_service(el)
                else
                    for el in mon_data.hosts
                        if pk in el.$$device_categories
                            cat_node.feed_device(el)
                        else if pk == 0 and not el.$$device_categories.length
                            # add to uncat service
                            uncat_root_node.feed_service(el)
                cat_node.end_ds_feed()
        if sum_childs
            for pk, cat_node of node_lut
                pk = parseInt(pk)
                if pk > 0
                    cat_node.set_state_from_children()
        uncat_root_node.balance()

        _recalc_burst(uncat_root_node, draw_params)

        return uncat_root_node

    return {

        build_structured_burst: (mon_data, draw_params) ->
            # mon_data is a filtered instance of icswMonitoringResult
            return build_structured_burst(mon_data, draw_params)

        build_structured_category_burst: (mon_data, sub_tree, cat_tree, draw_params, sum_childs) ->
            return build_structured_category_burst(mon_data, sub_tree, cat_tree, draw_params, sum_childs)

        ring_segment_path: ring_segment_path
        ring_path: ring_path
    }

])
