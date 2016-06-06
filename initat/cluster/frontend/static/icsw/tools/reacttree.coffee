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

# tree component
# should be rewritten in ReactJS

angular.module(
    "icsw.tools.reacttree",
    []
).factory("icswReactTreeDrawNode",
[
    "$q",
(
    $q,
) ->
    {div, input, span, ul, li} = React.DOM
    icswReactTreeDrawNode = React.createClass(
        propTypes: {
            parent_cb: React.PropTypes.func
            tree_node: React.PropTypes.object
            tree_config: React.PropTypes.object
        }

        get_span_class: () ->
            _tn = @props.tree_node
            r_class = ["fancytree-node"]
            if _tn.folder
                r_class.push "fancytree-folder"
            if _tn.active
                r_class.push "fancytree-active"
            if _tn.children.length or _tn.always_folder
                r_class.push "fancytree-has-children"
                if _tn.expand and _tn.children.length
                    r_class.push "fancytree-expanded"
                    r_class.push "fancytree-ico-ef"
                    r_class.push "fancytree-exp-el"
                else
                    r_class.push "fancytree-ico-cf"
                    r_class.push "fancytree-exp-c"
            else
                r_class.push "fancytree-ico-c"
                r_class.push "fancytree-exp-n"

            #r_class.push "fancytree-ico-c"
            #r_class.push "fancytree-exp-n"
            return r_class.join(" ")

        getInitialState: () ->
            # console.log @props
            return {
                draw_counter: 0
                expand: @props.tree_node.expand
                selected: @props.tree_node.selected
                num_sel_descendants: @props.tree_node._num_sel_descendants
                num_sel_childs: @props.tree_node._num_sel_childs
            }

        shouldComponentUpdate: () ->
            return @props.tree_node._dirty

        force_redraw: () ->
            @setState({draw_counter: @state.draw_counter + 1})

        parent_cb: () ->
            # copy flags from tree_node
            @setState(
                {
                    expand: @props.tree_node.expand
                    selected: @props.tree_node.selected
                    num_sel_descendants: @props.tree_node._num_sel_descendants
                    num_sel_childs: @props.tree_node._num_sel_childs
                }
            )
            @props.parent_cb()

        render: () ->
            _tc = @props.tree_config
            _tn = @props.tree_node
            _tn._dirty = false
            _main_spans = [
                span(
                    {
                        key: "exp"
                        className: "fancytree-expander"
                        onClick: (event) =>
                            if _tn.children.length
                                _tn.set_expand(!_tn.expand)
                                @setState({expand: _tn.expand})
                                @props.parent_cb()
                    }
                )
            ]
            if _tn.show_select and _tc.show_select
                # add selection button
                _main_spans.push(
                    input(
                        {
                            key: "selbutton"
                            className: "fancytree-checkbox"
                            type: "checkbox"
                            checked: if _tn.selected then "checked" else null
                            disabled: if _tn.disable_select or _tc.disable_select then "disabled" else null
                            style: {marginLeft: "2px"}
                            onClick: (event) =>
                                _tc.toggle_checkbox_node(_tn).then(
                                    (ok) =>
                                        @setState({selected: _tn.selected})
                                        @props.parent_cb()
                                )
                                event.preventDefault()
                        }
                    )
                )
            if _tc.show_selection_buttons and _tn.children.length
                _sub_set = _tn.all_selectable_descendant_and_self_selected()
                _main_spans.push(
                    div(
                        {
                            key: "selb"
                            className: "btn-group btn-group-xs"
                        }
                        input(
                            {
                                key: "selbi"
                                type: "button"
                                className: if _sub_set then "btn btn-warning" else "btn btn-success"
                                value: if _sub_set then "C" else "S"
                                onClick: (event) =>
                                    _tc.toggle_select_subtree(_tn)
                                    @setState({selected: _tn.selected})
                                    @props.parent_cb()
                            }
                        )
                    )
                )
                if _tn._depth == 0 and _tn.children.length and _tc.show_tree_expand_buttons
                    # add full selectin buttons
                    _top_spans = [
                        input(
                            {
                                key: "selbie"
                                type: "button"
                                className: "btn btn-success"
                                value: "e"
                                title: "expand tree"
                            }
                        )
                    ]
                    if _tn.show_select
                        _top_spans.push(
                            input(
                                {
                                    key: "selbis"
                                    type: "button"
                                    className: "btn btn-primary"
                                    value: "s"
                                    title: "expand selected"
                                }
                            )
                        )
                    _top_spans.push(
                        input(
                            {
                                key: "selbic"
                                type: "button"
                                className: "btn btn-warning"
                                value: "c"
                                title: "collapse tree"
                            }
                        )
                    )

                    _main_spans.push(
                        div(
                            {
                                key: "selb0"
                                className: "btn-group btn-group-xs"
                            }
                            _top_spans
                        )
                    )
            _name_span_list = [
                _tc.get_pre_view_element(_tn)
                span(
                    {
                        key: "main"
                        className: _tc.get_name_class(_tn)
                        title: _tc.get_title(_tn)
                    }
                    _tc.get_name(_tn)
                )
                _tc.get_post_view_element(_tn)
            ]
            if _tc.show_descendants and _tn._num_descendants
                if _tc.show_total_descendants
                    _desc = _tn._num_descendants
                else
                    _desc = _tn._num_nd_descendants
                if _tn._num_sel_descendants
                    _desc = "#{_desc} / #{_tn._num_sel_descendants}"
                # add descendants display
                _name_span_list.push(
                    span(
                        {
                            key: "desc"
                            className: if _tn._num_sel_descendants then "label label-primary" else "label label-default"
                        }
                        _desc
                    )
                )
            if _tc.debug_mode
                _name_span_list.push(
                    span(
                        {
                            key: "debug"
                            className: "label label-default"
                        }
                        "#{_tn._num_descendants} / #{_tn._num_nd_descendants} / #{_tn._num_sel_descendants} / #{_tn._num_sel_childs}"
                    )
                )
            # add name
            _main_spans.push(
                span(
                    {
                        key: "name"
                        className: "fancytree-title"
                        onClick: (event) =>
                            _tc.handle_click(event, _tn)
                            @force_redraw()
                            @props.parent_cb()
                        # onDoubleClick: (event) =>
                        #    console.log "DBL"
                        #    _tc.handle_dbl_click(event, _tn)
                    }
                    _name_span_list
                )
            )
            _sub_el = [
                span(
                    {
                        key: "comp"
                        className: @get_span_class()
                    }
                    _main_spans
                )
            ]
            if _tn.children.length and _tn.expand
                _sub_el.push(
                    ul(
                        {
                            key: "childs"
                        }
                        [
                            React.createElement(
                                icswReactTreeDrawNode
                                {
                                    parent_cb: @parent_cb
                                    tree_node: child
                                    tree_config: _tc
                                }
                            ) for child in _tn.children
                        ]
                    )
                )
            return li(
                {
                   key: "node"
                }
                _sub_el
            )
    )
    return icswReactTreeDrawNode
]).factory("icswReactTreeDrawContainer",
[
    "$q", "icswReactTreeDrawNode",
(
    $q, icswReactTreeDrawNode,
) ->
    # display of livestatus filter
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, ul} = React.DOM

    return React.createClass(
        propTypes: {
            tree_config: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                draw_counter: 0
                root_generation: 0
            }

        force_redraw: (root_gen) ->
            @setState({draw_counter: @state.draw_counter + 1, root_generation: root_gen})

        componentWillMount: () ->
            @props.tree_config.update_notifier.promise.then(
                () ->
                () ->
                (gen_list) =>
                    [_tree_gen, _root_gen] = gen_list
                    # console.log gen_list
                    # new generation, update
                    @force_redraw(_root_gen)
            )
            
        componentWillUnmount: () ->
            @props.tree_config.component_will_unmount()

        top_callback: () ->
            console.log "top_cb called"

        render: () ->
            _tc = @props.tree_config
            if not _tc.root_nodes.length
                return span(
                    {
                        key: "top"
                        className: "text-warning"
                    }
                    "No entries for #{_tc.name}"
                )
            else
                return ul(
                    {
                        key: "top#{@state.root_generation}"
                        className: "fancytree-container"
                    }
                    [
                        React.createElement(
                            icswReactTreeDrawNode
                            {
                                parent_cb: @top_callback
                                tree_node: root_node
                                tree_config: _tc
                            }
                        ) for root_node in _tc.root_nodes
                    ]
                )
    )
]).service("icswReactTreeNode",
[
    "$q",
(
    $q,
) ->
    class icswReactTreeNode
        constructor: (args, config) ->
            @_config = config
            # default values
            # node is selected
            @selected = false
            # node is active
            @active = false
            # children are shown (== expanded)
            @expand = false
            # node is a folder
            @folder = false
            # show select button
            @show_select = true
            # select button is disabled
            @disable_select = false
            # is always folder
            @always_folder = false
            # object
            @obj = null
            @children = []
            for key, value of args
                if key of @
                    @[key] = value
                else if key.substring(0, 1) == "_"
                    @[key] = value
                else if key in @_config.extra_args
                    @[key] = value
                else
                    console.error "unknown icswReactTreeNode arg #{key}=#{value}"
            # internal flags
            @_is_root_node = false
            @_parent = null
            @_depth = 0
            # will be automatically set
            @_node_idx = null
            # number of all nodes below this one
            @_num_descendants = 0
            # number of all nodes below this one which are not-folder nodes
            @_num_nd_descendants = 0
            # number of selected childs
            @_num_sel_childs = 0
            # selected descendants
            @_num_sel_descendants = 0
            # draw flag
            @_dirty = true

        update_flag: (key, value) =>
            if key of @
                @[key] = value
                @_dirty = true
            else
                console.error "unknown icswReactTreeNode arg #{key}=#{value}"
            
        add_child: (node, sort_func) =>
            node._depth = @_depth + 1
            node._parent = @
            if sort_func?
                idx = sort_func(@children, node)
                @children.splice(idx, 0, node)
            else
                @children.push(node)
            # iterate upwards
            p =  @
            while p
                p._dirty = true
                p._num_descendants += 1 + node._num_descendants
                p._num_nd_descendants += node._num_nd_descendants
                p._num_sel_descendants += node._num_sel_descendants
                if node.selected
                    p._num_sel_descendants++
                if not node.folder
                    p._num_nd_descendants++
                p = p._parent
            @_config.new_generation()

        all_selectable_descendant_and_self_selected: () =>
            if @show_select and not @selected
                return false
            if not @children.length
                if @show_select and @selected
                    return true
                else
                    return false
            else
                for child in @children
                    if !child.all_selectable_descendant_and_self_selected()
                        return false
                return true

        set_expand: (flag) ->
            return @_set_flag("expand", flag)

        set_active: (flag) ->
            return @_set_flag("active", flag)

        _set_flag: (name, value) ->
            # toggle expand / active flag if changed and return current value
            if @[name] != value
                @[name] = value
                @_dirty = true
                # propaget dirty flag upwards
                p = @_parent
                while p
                    p._dirty = true
                    p = p._parent
            return @[name]

        set_selected: (flag, propagate=true) ->
            # if _show_select is false ignore selection request
            if not @show_select
                return
            change = flag != @selected
            if change
                @_set_flag("selected", flag)
                # only update parent selection list if we have changed something in the local node
                p = @_parent
                diff = if @selected then 1 else -1
                first = true
                while p
                    p._dirty = true
                    if first
                        p._num_sel_childs += diff
                        first = false
                    p._num_sel_descendants += diff
                    p = p._parent

                # if propagate
                #    @notify_child_selection_changed()

]).service("icswReactTreeConfig",
[
    "icswReactTreeNode", "$q",
(
    icswReactTreeNode, $q,
) ->

    tree_idx = 0
    class icswReactTreeConfig
        constructor: (args) ->
            # count trees
            tree_idx++
            @tree_idx = tree_idx
            # default values
            @name = "dummy_name_#{@tree_idx}"
            # show subselecton button
            @show_selection_buttons = true
            @show_num_childs = true
            # expand nodes on selection
            @expand_on_selection = false
            @debug_mode = false
            # select button is disabled (global flag)
            @disable_select = false
            # allow change of selection
            @change_select = true
            # show select button (global flag)
            @show_select = true
            # show tree expand buttons
            @show_tree_expand_buttons = true
            # show descendants (with selection)
            @show_descendants = false
            # show total descendants and not non-folder-only entries
            @show_total_descendants = true
            # only one element can be selected
            @single_select = false
            # extra args for nodes
            @extra_args = []
            @root_nodes = []
            for key, value of args
                if not @[key]?
                    console.error "unknown icswReactTreeConfig #{key}=#{value}"
                else
                    @[key] = value
            # notify react component
            @_do_notify = true
            # internal flags
            @_tree_generation = 0
            # root node generation, forces rerender
            @_root_node_generation = 0
            # running node idx
            @_node_idx = 0
            # notifiers
            @update_notifier = $q.defer()

        update_flag: (key, value) =>
            if not @[key]?
                console.error "unknown icswReactTreeConfig #{key}=#{value}"
            else
                @[key] = value
                @new_generation()

        stop_notify: () =>
            @_do_notify = false
            
        start_notify: () =>
            @_do_notify = true
            @new_generation()
            
        new_generation: () =>
            @_tree_generation++
            if @_do_notify
                @update_notifier.notify([@_tree_generation, @_root_node_generation])
            
        component_will_unmount: () =>
            @update_notifier.reject("stop")

        clear_root_nodes: () =>
            @root_nodes.length = 0
            # reset tree generation
            @_tree_generation = 0
            # bump root node generation
            @_root_node_generation++
            @new_generation()
            
        create_node: (args) =>
            @_node_idx++
            new_node = new icswReactTreeNode(args, @)
            new_node._node_idx = @_node_idx
            return new_node

        add_root_node: (node) =>
            # set to root node
            node._is_root_node = true
            node._depth = 0
            @root_nodes.push(node)
            @new_generation()

        # recalc all root_nodes
        recalc: () =>
            (@_recalc_sel_descendants(entry) for entry in @root_nodes)
            (@_recalc_num_descendants(entry) for entry in @root_nodes)
            (@_recalc_sel_childs(entry) for entry in @root_nodes)
            @new_generation()

        _recalc_num_descendants: (entry) =>
            # @_num_childs = (_entry for _entry in entry.children when !_entry.pruned).length
            _num_childs = (_entry for _entry in entry.children).length
            entry._num_descendants = _num_childs
            entry._num_nd_descendants = _num_childs
            for child in entry.children
                _desc = @_recalc_num_descendants(child)
                entry._num_descendants += _desc[0]
                entry._num_nd_descendants += _desc[1]
            return [entry._num_descendants, entry._num_nd_descendants]

        _recalc_sel_descendants: (entry) =>
            entry._sel_descendants = (true for _entry in entry.children when _entry.selected).length
            for child in entry.children
                entry._sel_descendants += @_recalc_sel_descendants(child)
            return entry._sel_descendants

        _recalc_sel_childs: (entry) =>
            entry._sel_childs = (true for _entry in entry.children when _entry.selected).length
            (@_recalc_sel_childs(child) for child in entry.children)

        # toggle selection of single node
        toggle_checkbox_node: (node) =>
            _defer = $q.defer()
            if @change_select
                _doit = $q.defer()
                if @pre_change_cb?
                    @pre_change_cb(node).then(
                        (ok) ->
                            _doit.resolve("ok")
                        (notok) ->
                            _doit.reject("not ok")
                    )
                else
                    _doit.resolve("ok")
                _doit.promise.then(
                    (ok) =>
                        console.log "change"
                        node.set_selected(!node.selected)
                        if node.selected and @single_select
                            # remove all other selections
                            @iter(
                                (_entry) ->
                                    if _entry.selected and _entry._node_idx != node._node_idx
                                        _entry.set_selected(false)
                            )
                        @selection_changed(node)
                        _defer.resolve("changed")
                    (not_ok) =>
                        _defer.reject("not ok")
                )
            else
                _defer.reject("not enabled")
            return _defer.promise

        # change selection of subtrees
        toggle_select_subtree: (node) =>
             # if all selected, deselect
             # otherwise select all
             change_sel_rec = (node, flag) =>
                 node.set_selected(flag)
                 if flag and @expand_on_selection
                     node.set_expand(true)
                 for sub_node in node.children
                     change_sel_rec(sub_node, flag)

             if node.all_selectable_descendant_and_self_selected()
                 change_sel_rec(node, false)
             else
                 change_sel_rec(node, true)
             @selection_changed(node)


        toggle_tree_state: (entry, flag, signal=true) =>
            # entry: root node or undefined for iteration over all root nodes
            # flag: integer,
            #     1: expand and select entry
            #     0: toggle selected flag of entry
            #    -1: deselect entry
            if entry == undefined
                (@toggle_tree_state(_entry, flag, signal) for _entry in @root_nodes)
            else
                if flag == 1
                    entry.set_selected(true)
                    entry.set_expand(true)
                else if flag == 0
                    entry.set_selected(!entry.selected)
                else
                    entry.set_selected(false)
                for sub_entry in entry.children
                    @toggle_tree_state(sub_entry, flag, false)
                if signal
                    @selection_changed(entry)

        # general iterate function
        iter: (cb_func, cb_data) =>
            (@_iter(entry, cb_func, cb_data) for entry in @root_nodes)

        _iter: (entry, cb_func, cb_data) =>
            cb_func(entry, cb_data)
            (@_iter(child, cb_func, cb_data) for child in entry.children)

        # set selected flag according to sel_func
        set_selected: (sel_func, sel_list) =>
            (@_set_selected(entry, sel_func, sel_list) for entry in @root_nodes)
            @new_generation()

        _set_selected: (entry, sel_func, sel_list) =>
            do_sel = sel_func(entry, sel_list)
            if do_sel != null
                entry.set_selected(do_sel)
            (@_set_selected(child, sel_func, sel_list) for child in entry.children)

        # clear all selected
        clear_selected: () =>
            (@_clear_selected(entry) for entry in @root_nodes)
            @new_generation()

        _clear_selected: (entry) =>
            entry.set_selected(false)
            (@_clear_selected(child) for child in entry.children)

        # get selected according to sel_func
        get_selected: (sel_func) =>
            act_sel = []
            for entry in @root_nodes
                act_sel = act_sel.concat(@_get_selected(entry, sel_func))
            return _.uniq(act_sel)

        _get_selected: (entry, sel_func) =>
            act_sel = sel_func(entry)
            for child in entry.children
                act_sel = act_sel.concat(@_get_selected(child, sel_func))
            return act_sel

        # show all selected, keep-flag keeps already expanded nodes expanded
        show_selected: (keep=true) =>
            # make all selected nodes visible
            (@_show_selected(entry, keep) for entry in @root_nodes)
            @new_generation()

        _show_selected: (entry, keep) =>
            if (true for sub_entry in entry.children when @_show_selected(sub_entry, keep)).length
                show = true
            else
                # keep: keep expand state if already expanded
                if keep
                    show = entry.expand or entry.selected
                else
                    show = entry.selected
            return entry.set_expand(show)

        show_active: (keep=true) =>
            # make all selected nodes visible
            (@_show_active(entry, keep) for entry in @root_nodes)
            @new_generation()

        _show_active: (entry, keep) =>
            if (true for sub_entry in entry.children when @_show_active(sub_entry, keep)).length
                show = true
            else
                # keep: keep expand state if already expanded
                if keep
                    show = entry.expand or entry.active
                else
                    show = entry.active
            return entry.set_expand(show)

        # clear all active nodes
        clear_active: () =>
            @iter(
                (entry) ->
                    entry.set_active(false)
            )
            @new_generation()

        # get list of all active nodes
        get_active: () =>
            active = []
            @iter(
                (entry) ->
                    if entry.active
                        active.push(entry)
            )
            return active

        # helper functions
        get_parents: (node) =>
            _r_list = []
            _p = node._parent
            while _p
                _r_list.push(_p)
                _p = _p._parent
            return _r_list
            
        # accessor classes, to be overridden
        get_name: () =>
            return "node"

        get_name_class: () =>
            return ""

        get_title: () =>
            return ""

        # extra view elements
        get_pre_view_element: (entry) =>
            return null

        get_post_view_element: (entry) =>
            return null

        # selection changed callback
        selection_changed: (entry) =>
            console.warn "selection_changed not implemented for #{@name}"

]).directive("icswReactTree",
[
    "icswReactTreeDrawContainer", "icswReactTreeConfig",
(
    icswReactTreeDrawContainer, icswReactTreeConfig,
) ->
    return {
        restrict: "E"
        scope: {
            tree_config: "=icswTreeConfig"
        }
        replace: true
        link: (scope, element, attrs) ->
            if not attrs.icswTreeConfig?
                dummy_config = new icswReactTreeConfig(
                    {
                        name: "test"
                        debug_mode: true
                    }
                )
                nn = dummy_config.create_node({})
                dummy_config.add_root_node(nn)
                bench_outer = 10
                bench_inner = 1000
                for idx in [0..bench_outer]
                    sn = dummy_config.create_node({expand: false})
                    nn.add_child(sn)
                    for sidx in [0..bench_inner]
                        sn2 = dummy_config.create_node({expand: true})
                        sn.add_child(sn2)
                    # nn = sn
                tree_config = dummy_config
            else
                tree_config = scope.tree_config
            ReactDOM.render(
                React.createElement(
                    icswReactTreeDrawContainer
                    {
                        tree_config: tree_config
                    }
                )
                element[0]
            )
    }
])
