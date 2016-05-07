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
    {div, h4, select, option, p, input, span, ul, li} = React.DOM
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
                    selected: @props.tree_node.selected
                    num_sel_descendants: @props.tree_node._num_sel_descendants
                    num_sel_childs: @props.tree_node._num_sel_childs
                }
            )
            @props.parent_cb()

        render: () ->
            console.log "r"
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
                            disabled: if _tn.disable_select then "disabled" else null
                            style: {marginLeft: "2px"}
                            onChange: (event) =>
                                _tn.set_selected(!_tn.selected)
                                @setState({selected: _tn.selected})
                                console.log "par"
                                @props.parent_cb()
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
                if _tn._depth == 0
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

            _main_spans.push(
                span(
                    {
                        key: "main"
                        className: "text-danger"
                    }
                    "test"
                )
            )
            if _tc.debug_mode
                _main_spans.push(
                    span(
                        {
                            key: "debug"
                            className: "label label-default"
                        }
                        "#{_tn._num_descendants} / #{_tn._num_nd_descendants} / #{_tn._num_sel_descendants} / #{_tn._num_sel_childs}"
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
            }

        force_redraw: () ->
            @setState({draw_counter: @state.draw_counter + 1})

        componentWillMount: () ->
            @props.tree_config.update_notifier.promise.then(
                () ->
                () ->
                (gen) =>
                    # new generation, update
                    @force_redraw()
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
                        key: "top"
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
        constructor: (args) ->
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
            @children = []
            # default values
            for key, value of args
                if not @[key]?
                    console.error "unknown icswReactTreeNode #{key}=#{value}"
                else
                    @[key] = value
            # internal flags
            @_is_root_node = false
            @_parent = null
            @_depth = 0
            # will be automatically set
            @_config = null
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

        add_child: (node) =>
            node._depth = @_depth + 1
            node._parent = @
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
            @children.push(node)
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
            # toggle expand flag if changed and return current value
            if @expand != flag
                @expand = flag
                @_dirty = true
            return @expand

        set_selected: (flag, propagate=true) ->
            # if _show_select is false ignore selection request
            if not @show_select
                return
            change = flag != @selected
            if change
                @_dirty = true
                @selected = flag
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

    class icswReactTreeConfig
        constructor: (args) ->
            # default values
            @name = "dummy_name"
            # show subselecton button
            @show_selection_buttons = true
            @show_num_childs = true
            # expand nodes on selection
            @expand_on_selection = false
            @debug_mode = false
            # show select button (global flag)
            @show_select = true
            @root_nodes = []
            for key, value of args
                if not @[key]?
                    console.error "unknown icswReactTreeConfig #{key}=#{value}"
                else
                    @[key] = value
            # internal flags
            @_tree_generation = 0
            # running node idx
            @_node_idx = 0
            # notifiers
            @update_notifier = $q.defer()

        new_generation: () =>
            @_tree_generation++
            @update_notifier.notify(@_tree_generation)
            
        component_will_unmount: () =>
            console.log "stop"
            @update_notifier.reject("stop")

        create_node: (args) =>
            @_node_idx++
            new_node = new icswReactTreeNode(args)
            new_node._config = @
            new_node._node_idx = @_node_idx
            return new_node

        add_root_node: (node) =>
            # set to root node
            node._is_root_node = true
            node._depth = 0
            @root_nodes.push(node)
            @new_generation()
            
        toggle_select_subtree: (node) =>
             # if all selected, deselect
             # otherwise select all
             change_sel_rec = (node, flag) ->
                 node.set_selected(flag)
                 if flag and @expand_on_selection
                     node.expand = true
                 for sub_node in node.children
                     change_sel_rec(sub_node, flag)

             if node.all_selectable_descendant_and_self_selected()
                 change_sel_rec(node, false)
             else
                 change_sel_rec(node, true)
             # @selection_changed(entry)

        # general iterate function
        iter: (cb_func, cb_data) =>
            (@_iter(entry, cb_func, cb_data) for entry in @root_nodes)

        _iter: (entry, cb_func, cb_data) =>
            cb_func(entry, cb_data)
            (@_iter(child, cb_func, cb_data) for child in entry.children)

        # set selected flag according to sel_func
        set_selected: (sel_func, sel_list) =>
            (@_set_selected(entry, sel_func, sel_list) for entry in @root_nodes)
            @redraw_tree()

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

        # clear all active nodes
        clear_active: () =>
            @iter(
                (entry) ->
                    if entry.active
                        entry.active = false
                        entry._dirty = true
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

]).directive("icswReactTree",
[
    "icswReactTreeDrawContainer", "icswReactTreeConfig",
(
    icswReactTreeDrawContainer, icswReactTreeConfig,
) ->
    return {
        restrict: "E"
        scope: {
            treeconfig: "="
        }
        replace: true
        link: (scope, element, attr) ->
            dummy_config = new icswReactTreeConfig(
                {
                    show_num_childs: 4
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
            ReactDOM.render(
                React.createElement(
                    icswReactTreeDrawContainer
                    {
                        tree_config: dummy_config
                    }
                )
                element[0]
            )
    }
])
