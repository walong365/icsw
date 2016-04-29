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
    "icsw.tools.tree",
    []
).directive("tree",
[
    "$compile", "$templateCache", "$injector",
(
    $compile, $templateCache, $injector,
) ->
    return {
        restrict: "E"
        scope: {
            treeconfig: "="
            maxHeight  : "&"
            icswConfigObject: "="
        }
        replace: true
        link: (scope, element, attr) ->
            scope.$watch("treeconfig", (new_val) ->
                # setup a list of nodes (with all subtrees)
                if new_val
                    if "configService" of attr
                        cservice = $injector.get(attr.configService)
                        new_val.config_service = cservice
                        new_val.config_object = scope.icswConfigObject
                    element.children().remove()
                    _root_el = angular.element($templateCache.get("icsw.tree.root.node"))
                    if scope.maxHeight?
                        _root_el.css("max-height", scope.maxHeight() + "px")
                    element.append(_root_el)
                    _root_el.append(angular.element("<span>No entries</span>"))
                    _num_root_nodes = 0
                    scope.$watch(
                        "treeconfig.tree_generation",
                        (r_nodes) ->
                            r_nodes = scope.treeconfig.root_nodes
                            if r_nodes.length != _num_root_nodes
                                if _num_root_nodes
                                    console.log "redraw tree with new number of nodes"
                                else
                                    _root_el.find("span").remove()
                            _tc = scope.treeconfig
                            _tc.setup_nodes(r_nodes)
                            if r_nodes.length
                                for _node in r_nodes
                                    _root_el.append(_node._tne)
                    )
            )
    }
]).service("icswTreeNode",
[
    "$q",
(
    $q,
) ->

    class TreeNode
        constructor: (args) ->
            # tree node element (li)
            @_tne = undefined
            # subtree element
            @_ste = undefined
            # is selected
            @selected = false
            # is expanded
            @expand = false
            # is folder
            @folder = false
            # list of children
            @children = []
            # active flag
            @active = false
            # link to parent
            @parent = null
            # link to config
            @config = null
            # always shown as folder ?
            @always_folder = false
            # idx
            @_idx = 0
            # number of all nodes below this
            @_num_descendants = 0
            # number of all non-directory descendants
            @_num_nd_descendants = 0
            # number of all direct children
            @_num_childs = 0
            # number of selected childs
            @_sel_childs = 0
            # number of selected descendants
            @_sel_descendants = 0
            # pruned (currently not shown)
            @pruned = false
            # show selection entry
            @_show_select = true
            for key, value of args
                @[key] = value
            @notify_child_selection_changed()
        set_selected: (flag, propagate=true) ->
            # if _show_select is false ignore selection request
            if not @_show_select
                return
            change = flag != @selected
            if change
                @selected = flag
                # only update parent selection list if we have changed something in the local node
                cur_p = @parent
                diff = if @selected then 1 else -1
                first = true
                while cur_p
                    if first
                        cur_p._sel_childs += diff
                        first = false
                    cur_p._sel_descendants += diff
                    cur_p = cur_p.parent

                if propagate
                    @notify_child_selection_changed()
        notify_child_selection_changed: () ->
            # notify self and all parents: a child selection has changed (self is also a child)
            if @parent?
                @parent.notify_child_selection_changed()
            #if @self_and_descendants_selected()
            if @all_selectable_descendant_and_self_selected()
                @select_button_letter = "C"
                @select_button_class = "btn btn-warning"
            else
                @select_button_letter = "S"
                @select_button_class = "btn btn-success"
        add_child: (child, sort_func) =>
            child.parent = @
            child._depth = @_depth + 1
            @_num_childs++
            if sort_func?
                idx = sort_func(@children, child)
                @children.splice(idx, 0, child)
            else
                @children.push(child)
            cur_p = @
            while cur_p
                cur_p._num_descendants += 1 + child._num_descendants
                cur_p._num_nd_descendants += child._num_nd_descendants
                cur_p._sel_descendants += child._sel_descendants
                if child.selected
                    cur_p._sel_descendants += 1
                if not child.folder
                   cur_p._num_nd_descendants += 1
                cur_p = cur_p.parent
            @notify_child_selection_changed()
        remove_child: (child) ->
            @children = (entry for entry in @children when entry != child)
            cur_p = @
            while cur_p
                cur_p._num_descendants -= 1 + child._num_descendants
                cur_p._num_nd_descendants -= child._num_nd_descendants
                cur_p._sel_descendants -= child._sel_descendants
                if child.selected
                    cur_p._sel_descendants -= 1
                if not child.folder
                   cur_p._num_nd_descendants -= 1
                cur_p = cur_p.parent
            @notify_child_selection_changed()
        recalc_num_descendants: () =>
            @_num_childs = (_entry for _entry in @children when !_entry.pruned).length
            @_num_descendants = @_num_childs
            @_num_nd_descendants = @_num_childs
            for child in @children
                _desc = child.recalc_num_descendants()
                @_num_descendants += _desc[0]
                @_num_nd_descendants += _desc[1]
            return [@_num_descendants, @_num_nd_descendants]
        recalc_sel_descendants: () =>
            @_sel_descendants = (true for entry in @children when entry.selected).length
            for child in @children
                @_sel_descendants += child.recalc_sel_descendants()
            return @_sel_descendants
        recalc_sel_childs: () =>
            @_sel_childs = (true for entry in @children when entry.selected).length
            (child.recalc_sel_childs() for child in @children)
        get_label_class: () =>
            if @_sel_descendants
                return "label label-primary"
            else
                return "label label-default"
        is_selectable: () =>
            return @_show_select
        all_selectable_descendant_and_self_selected: () =>
            if @is_selectable() and not @selected
                return false
            if not @children.length
                if @is_selectable and @selected
                    return true
                else
                    return false
            else
                for child in @children
                    if !child.all_selectable_descendant_and_self_selected()
                        return false
                return true

]).service("icswTreeConfig",
[
    "icswTreeNode",
(
    icswTreeNode,
) ->

    class TreeConfig
        constructor: (args) ->
            # not really needed, enter more flags here
            @show_selection_buttons = true
            @show_childs = false
            @show_descendants = false
            @show_tree_expand_buttons = true
            @show_icons = true
            @show_select = true
            @disable_select = false
            @change_select = true
            # show total descendants and not file-only entries
            @show_total_descendants = true
            # only one element can be selected
            @single_select = false
            for key, value of args
                @[key] = value
            @root_nodes = []
            @tree_generation = 0
            @_node_idx = 0
        selection_changed: (entry) =>
        clear_root_nodes: () =>
            @root_nodes = []
            @tree_generation++
        handle_click: () =>
            # override
        handle_dblclick: () =>
            # override
        get_name: () =>
            # override
            return "node"
        get_title: () =>
            # override
            return ""
        get_name_class: () =>
            # override
            return ""
        new_node: (args) =>
            @_node_idx++
            new_node = new icswTreeNode(args)
            new_node._is_root_node = false
            new_node._idx = @_node_idx
            new_node._depth = 0
            new_node.config = @
            return new_node
        add_root_node: (node) =>
            node._is_root_node = true
            @root_nodes.push(node)
            @tree_generation++
        recalc: () =>
            (entry.recalc_sel_descendants() for entry in @root_nodes)
            (entry.recalc_num_descendants() for entry in @root_nodes)
            (entry.recalc_sel_childs() for entry in @root_nodes)
            @redraw_tree()
        prune: (keep_func) =>
            # prune tree according to keep_func(entry)
            for entry in @root_nodes
                @_prune(entry, keep_func)
        _prune: (entry, keep_func) =>
            any_shown = keep_func(entry)
            if not any_shown
                for sub_entry in entry.children
                    if not @_prune(sub_entry, keep_func)
                        any_shown = true
            entry.pruned = !any_shown
            return entry.pruned
        show_active: (keep=true) =>
            # make all selected nodes visible
            (@_show_active(entry, keep) for entry in @root_nodes)
            @redraw_tree()

        redraw_tree: () =>
            for node in @root_nodes
                @update_nodes_to_bottom(node)

        update_nodes_to_bottom: (start_node) =>
            if start_node.expand
                @_expand_node(start_node)
            else
                @_hide_node(start_node)
            @update_node(start_node)
            if start_node.children.length
                [@update_nodes_to_bottom(_sub_node) for _sub_node in start_node.children]

        update_nodes_to_top: (start_node) =>
            @update_node(start_node)
            if start_node.parent
                @update_nodes_to_top(start_node.parent)

        _hide_node: (node) =>
            if node._ste
                node._ste.hide()

        _expand_node: (node) =>
            if not node._tne
                @populate_node(node)
            if not node._ste
                node._ste = angular.element("<ul/>")
                @setup_nodes(node.children)
                for _node in node.children
                    node._ste.append(_node._tne)
                node._tne.append(node._ste)
            node._ste.show()

        setup_nodes: (node_list) =>
            _node_num = 0
            _node_len = node_list.length
            for _node in node_list
                _node_num++
                last = if _node_num == _node_len then true else false
                first = if _node_num == 1 then true else false
                if not _node._tne
                    @populate_node(_node, first, last)
                if _node.expand
                    @_expand_node(_node)

        _jq_toggle_checkbox_node: (node) =>
            @toggle_checkbox_node(node)
            _top_span = node._tne.find("span:first")
            _top_span.removeClass()
            for _class in @get_span_class(node, node._last)
                _top_span.addClass(_class)
            if @single_select
                @redraw_tree()
            else
                @update_nodes_to_top(node)

        _jq_toggle_select_subtree: (node) =>
            @toggle_select_new(node)
            if node.expand
                @_expand_node(node)
            @update_nodes_to_top(node)
            @update_nodes_to_bottom(node)

        populate_node: (node, first, last) =>
            # store last flag
            node._last = last
            li_node = angular.element("<li/>")
            if last
                li_node.addClass("fanytree-lastsib")
            # copy settings from node to li_node
            _top_span = angular.element("<span/>")
            # main classes now handled in update_node
            for _class in @get_span_class(node, last)
                _top_span.addClass(_class)
            # selection box, icons and other stuff
            _exp = angular.element("<span class='fancytree-expander'/>")
            _exp.on("click", () =>
                if node.expand
                    node.expand = false
                    @_hide_node(node)
                else
                    node.expand = true
                    @_expand_node(node)
                _top_span = node._tne.find("span:first")
                _top_span.removeClass()
                for _class in @get_span_class(node, last)
                    _top_span.addClass(_class)
            )
            _top_span.append(_exp)
            if @show_select and node._show_select
                _sel_span = angular.element("<input type='checkbox' class='fancytree-checkbox' style='margin-left:2px;'/>")
                if @disable_select
                    _sel_span.attr("disabled", "disabled")
                _sel_span.on("click", () => @_jq_toggle_checkbox_node(node))
                node._sel_span = _sel_span
                _top_span.append(_sel_span)
            else
                node._sel_span = undefined
            if @show_icons
                _icon_span = angular.element("<span style='width: 16px; margin-left: 0px;'/>")
                _icon_span.addClass(@get_icon_class(node))
                _top_span.append(_icon_span)
            if @show_selection_buttons and node._num_childs
                _sel_button = angular.element("<div class='btn-group btn-group-xs'><input type='button' class=\"#{node.select_button_class}\" value=\"#{node.select_button_letter}\"/></div>")
                node._sel_button_span = _sel_button
                _sel_button.bind("click", () => @_jq_toggle_select_subtree(node))
                _top_span.append(_sel_button)
            else
                node._sel_button_span = undefined
            if node._depth == 0 and node._num_childs and @show_tree_expand_buttons
                _sel2_button = angular.element("<div class='btn-group btn-group-xs'></div>")
                _expand_all_button = angular.element("<input type='button' class='btn btn-success' value='e' title='expand all'></input>")
                _sel2_button.append(_expand_all_button)
                _expand_all_button.bind("click", () =>
                    @toggle_expand_tree(1, false)
                )
                if @show_select
                    _expand_selected_button = angular.element("<input type='button' class='btn btn-primary' value='s' title='expand selected'></input>")
                    _sel2_button.append(_expand_selected_button)
                    _expand_selected_button.bind("click", () =>
                        @toggle_expand_tree(1, true)
                    )
                _expand_collapse_button = angular.element("<input type='button' class='btn btn-warning' value='c' title='collapse all'></input>")
                _expand_collapse_button.bind("click", () =>
                    @toggle_expand_tree(-1, false)
                )
                _sel2_button.append(_expand_collapse_button)
                _top_span.append(_sel2_button)
            # name
            _a_node = angular.element("<span class='fancytree-title'></span>")
            # binds name and select spand
            _bind_span = angular.element("<span></span>")
            _ex_span = @add_extra_span(node)
            node._extra_span = _ex_span
            if _ex_span
                _bind_span.append(_ex_span)
            _name_span = angular.element("<span></span>")
            _bind_span.append(_name_span)
            node._name_span = _name_span
            if @show_childs and !@show_descendants
                _childs_span = angular.element("<span>(<span>xx</span>)</span>")
                # _childs_span.hide()
                _bind_span.append(_childs_span)
            else
                _childs_span = undefined
            if !@show_childs and @show_descendants
                _descendants_span = angular.element("<span><span></span><span></span></span>")
                _descendants_span.hide()
                _bind_span.append(_descendants_span)
            else
                _descendants_span = undefined
            node._childs_span = _childs_span
            node._descendants_span = _descendants_span
            _a_node.append(_bind_span)
            _a_node.bind("click", (event) =>
                @handle_click(node, event)
            )
            _a_node.bind("dblclick", (event) =>
                @handle_dblclick(node, event)
            )
            _top_span.append(_a_node)
            li_node.append(_top_span)
            node._top_span = _top_span
            node._tne = li_node
            @update_node(node)
            return node._tne

        update_node: (node) =>
            _update_childs_span = (node) =>
                node._childs_span.text = "4"

            _update_sel_button_span = (node) =>
                node._sel_button_span.find("input:first").val(node.select_button_letter)
                node._sel_button_span.find("input:first").removeClass()
                node._sel_button_span.find("input:first").addClass(node.select_button_class)

            _update_top_span = (node) =>
                _top_span = node._top_span
                _top_span.removeClass()
                for _class in @get_span_class(node, node._last)
                    _top_span.addClass(_class)

            _update_descendants_span = (node) =>
                _spn = node._descendants_span
                if node._num_descendants
                    _spn.show()
                    _spn.removeClass()
                    if node._sel_descendants
                        _spn.addClass("label label-primary")
                    else
                        _spn.addClass("label label-default")
                    if @show_total_descendants
                        _spn.find("span:first").text(node._num_descendants)
                    else
                        _spn.find("span:first").text(node._num_nd_descendants)
                    if node._sel_descendants
                        _spn.find("span:last").text(" / " + node._sel_descendants)
                    else
                        _spn.find("span:last").text("")
                else
                    _spn.hide()

            _update_name_span = (node) =>
                _sp = node._name_span
                _sp.removeClass()
                _sp.addClass(@get_name_class(node))
                _sp.attr("title", @get_title(node))
                _sp.text(@get_name(node))

            if node._top_span
                _update_top_span(node)
            if node._sel_button_span
                _update_sel_button_span(node)
            if node._childs_span
                _update_childs_span(node)
            if node._descendants_span
                _update_descendants_span(node)
            if node._tne
                # tne has to be present for name_span
                _update_name_span(node)
            if node._extra_span
                @update_extra_span(node, node._extra_span)

        _show_active: (entry, keep) =>
            if (true for sub_entry in entry.children when @_show_active(sub_entry, keep)).length
                show = true
            else
                # keep: keep expand state if already expanded
                if keep
                    show = entry.expand or entry.active
                else
                    show = entry.active
            entry.expand = show
            return entry.expand

        show_selected: (keep=true) =>
            # make all selected nodes visible
            (@_show_selected(entry, keep) for entry in @root_nodes)
            @redraw_tree()

        _show_selected: (entry, keep) =>
            if (true for sub_entry in entry.children when @_show_selected(sub_entry, keep)).length
                show = true
            else
                # keep: keep expand state if already expanded
                if keep
                    show = entry.expand or entry.selected
                else
                    show = entry.selected
            entry.expand = show
            return entry.expand

        toggle_expand_node: (entry) ->
            if entry.children.length
                entry.expand = not entry.expand
        toggle_checkbox_node: (entry) =>
            if @change_select
                if @pre_change_cb?
                    @pre_change_cb(entry)
                entry.set_selected(!entry.selected)
                if entry.selected and @single_select
                    # remove all other selections
                    cur_idx = entry._idx
                    @iter(
                        (_entry) ->
                            if _entry.selected and _entry._idx != cur_idx
                                _entry.selected = false
                    )
                @selection_changed(entry)

        toggle_select_new: (entry) =>
             # if all selected, deselect
             # otherwise select all
             change_sel_rec = (entry, flag) ->
                 entry.set_selected(flag)
                 if flag
                    entry.expand = true
                 for sub_entry in entry.children
                     change_sel_rec(sub_entry, flag)

             if entry.all_selectable_descendant_and_self_selected()
                 change_sel_rec(entry, false)
             else
                 change_sel_rec(entry, true)
             @selection_changed(entry)
        toggle_tree_state: (entry, flag, signal=true) =>
            if entry == undefined
                (@toggle_tree_state(_entry, flag, signal) for _entry in @root_nodes)
            else
                if flag == 1
                    entry.set_selected(true)
                    entry.expand = true
                else if flag == 0
                    entry.set_selected(!entry.selected)
                else
                    entry.set_selected(false)
                for sub_entry in entry.children
                    @toggle_tree_state(sub_entry, flag, false)
                if signal
                    @selection_changed(entry)
        toggle_expand_tree: (flag, only_selected) ->
            exp_flag = if flag == 1 then true else false
            (@_toggle_expand_tree(entry, exp_flag, only_selected) for entry in @root_nodes)
            @redraw_tree()
        _toggle_expand_tree: (entry, flag, only_selected) =>
            if only_selected
                exp = entry.selected
                for child in entry.children
                    if @_toggle_expand_tree(child, flag, only_selected)
                        exp = true
                entry.expand = exp
            else
                entry.expand = flag
                (@_toggle_expand_tree(child, flag) for child in entry.children)
            return entry.expand
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
        clear_selected: () =>
            (@_clear_selected(entry) for entry in @root_nodes)
            @redraw_tree()
        _clear_selected: (entry) =>
            entry.set_selected(false)
            (@_clear_selected(child) for child in entry.children)
        set_selected: (sel_func, sel_list) =>
            (@_set_selected(entry, sel_func, sel_list) for entry in @root_nodes)
            @redraw_tree()
        _set_selected: (entry, sel_func, sel_list) =>
            do_sel = sel_func(entry, sel_list)
            if do_sel != null
                entry.set_selected(do_sel)
            (@_set_selected(child, sel_func, sel_list) for child in entry.children)
        iter: (cb_func, cb_data) =>
            (@_iter(entry, cb_func, cb_data) for entry in @root_nodes)
        _iter: (entry, cb_func, cb_data) =>
            cb_func(entry, cb_data)
            (@_iter(child, cb_func, cb_data) for child in entry.children)
        get_active: () =>
            active = []
            @iter(
                (entry) ->
                    if entry.active
                        active.push(entry)
            )
            return active
        clear_active: () =>
            @iter(
                (entry) ->
                    entry.active = false
            )
            @redraw_tree()

        get_icon_class: (entry) ->
            # override
            return "fancytree-icon"

        get_span_class: (entry, last) ->
            r_class = []
            r_class.push "fancytree-node"
            if entry.folder
                r_class.push "fancytree-folder"
            if entry.active
                r_class.push "fancytree-active"
            if entry._sel_span?
                if entry.selected
                    entry._sel_span.prop("checked", true)
                else
                    entry._sel_span.prop("checked", false)
            if entry.children.length or entry.always_folder
                r_class.push "fancytree-has-children"
                if entry.expand and entry.children.length
                    r_class.push "fancytree-expanded"
                    r_class.push "fancytree-ico-ef"
                    if last
                        r_class.push "fancytree-exp-el"
                    else
                        r_class.push "fancytree-exp-e"
                else
                    r_class.push "fancytree-ico-cf"
                    if last
                        r_class.push "fancytree-exp-cl"
                    else
                        r_class.push "fancytree-exp-c"
            else
                r_class.push "fancytree-ico-c"
                r_class.push "fancytree-exp-n"
            return r_class

        add_extra_span: (entry) ->
            # override
            return null

])
