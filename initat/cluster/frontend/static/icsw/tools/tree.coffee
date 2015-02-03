
class tree_node
    constructor: (args) ->
        # is selected
        @selected = false
        # is expanded
        @expand = false
        # is folder
        @folder = false
        # list of children
        @children = []
        # list of nodes with the same content
        @linklist = []
        # active flag
        @active = false
        # link to parent
        @parent = null
        # link to config
        @config = null
        for key, value of args
            @[key] = value
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
        @notify_child_selection_changed()
    set_selected: (flag, propagate=true) ->
        # if _show_select is false ignore selection request
        if not @_show_select
            return
        change = flag != @selected
        if change
            if propagate and @linklist.length
                for other in @linklist
                    # only change if not already changed
                    if @config._track_changes
                        # track changes of linked items
                        if other._idx not in @config._change_list
                            @config._change_list.push(other._idx)
                            other.set_selected(flag, false)
                    # copy selected flags to nodes on the same level
                    else
                        other.set_selected(flag, false)
            else
                @selected = flag
            if not (propagate and @linklist.length)
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
            @select_button_class = "btn btn-success fa fa-check"
        else
            @select_button_class = "btn btn-default fa fa-check"
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
        return typeof(@_show_select) == "undefined" or @_show_select
    all_selectable_descendant_and_self_selected: () =>
        if @is_selectable() and not @selected
            return false
        for child in @children
            if ! child.all_selectable_descendant_and_self_selected()
                return false
        return true




class tree_config
    constructor: (args) ->
        # not really needed, enter more flags here
        @show_selection_buttons = true
        @show_childs = false
        @show_descendants = false
        @show_tree_expand_buttons = true
        @show_icons = true
        @show_select = true
        @change_select = true
        # show total descendants and not file-only entries
        @show_total_descendants = true
        # only one element can be selected
        @single_select = false
        for key, value of args
            @[key] = value
        @root_nodes = []
        @_node_idx = 0
        @_track_changes = false
    selection_changed: (entry) =>
    clear_root_nodes: () =>
        @root_nodes = []
    handle_click: () =>
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
    start_tracking_changes: () =>
        @_track_changes = true
        @_change_list = []
    stop_tracking_changes: () =>
        # console.log "stop", @_change_list
        @_track_changes = false
        @_change_list = []
    new_node: (args) =>
        @_node_idx++
        new_node = new tree_node(args)
        new_node._is_root_node = false
        if not new_node._show_select?
            # only set _show_select if _show_select is not already set
            new_node._show_select = true
        new_node._idx = @_node_idx
        new_node._depth = 0
        new_node.config = @
        return new_node
    add_root_node: (node) =>
        node._is_root_node = true
        @root_nodes.push(node)
    recalc: () =>
        (entry.recalc_sel_descendants() for entry in @root_nodes)
        (entry.recalc_num_descendants() for entry in @root_nodes)
        (entry.recalc_sel_childs() for entry in @root_nodes)
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
        entry.expand = not entry.expand
    toggle_checkbox_node: (entry) =>
        if @change_select
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

         @start_tracking_changes()
         if entry.all_selectable_descendant_and_self_selected()
             change_sel_rec(entry, false)
         else
             change_sel_rec(entry, true)
         @stop_tracking_changes()
         @selection_changed(entry)
    toggle_tree_state: (entry, flag, signal=true) =>
        if entry == undefined
            (@toggle_tree_state(_entry, flag, signal) for _entry in @root_nodes)
        else
            if signal and flag == 0
                @start_tracking_changes()
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
                @stop_tracking_changes()
                @selection_changed(entry)
    toggle_expand_tree: (flag, only_selected) ->
        exp_flag = if flag == 1 then true else false
        (@_toggle_expand_tree(entry, exp_flag, only_selected) for entry in @root_nodes)
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
        return _.unique(act_sel)
    _get_selected: (entry, sel_func) =>
        act_sel = sel_func(entry)
        for child in entry.children
            act_sel = act_sel.concat(@_get_selected(child, sel_func))
        return act_sel
    clear_selected: () =>
        (@_clear_selected(entry) for entry in @root_nodes)
    _clear_selected: (entry) =>
        entry.set_selected(false)
        (@_clear_selected(child) for child in entry.children)
    set_selected: (sel_func, sel_list) =>
        (@_set_selected(entry, sel_func, sel_list) for entry in @root_nodes)
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
    clear_active: () =>
        @iter((entry) -> entry.active=false)
    get_icon_class: (entry) ->
        # override
        return "dynatree-icon"
    get_span_class: (entry, last) ->
        r_class = []
        r_class.push "dynatree-node"
        if entry.folder
            r_class.push "dynatree-folder"
        if entry.active
            r_class.push "dynatree-active"
        if last
            r_class.push "dynatree-lastsib"
        if entry.selected
            r_class.push "dynatree-selected"
        if entry.children.length or entry.always_folder?
            r_class.push "dynatree-has-children"
            if entry.expand
                r_class.push "dynatree-expanded" 
                r_class.push "dynatree-ico-ef"
                if last # or not depth, depth was the 3rd argument, not needed ?
                    r_class.push "dynatree-exp-el"
                else
                    r_class.push "dynatree-exp-e"
            else
                r_class.push "dynatree-ico-cf"
                if last # or not depth
                    r_class.push "dynatree-exp-cl"
                else
                    r_class.push "dynatree-exp-cl"
        else
            r_class.push "dynatree-ico-c"
            r_class.push "dynatree-exp-c"
        return r_class

tree_module = angular.module("icsw.tools.tree",
    []
).directive("tree", ["$compile", "$templateCache",
        ($compile, $templateCache) ->
            return {
                restrict : "E"
                scope    : {
                    treeconfig : "="
                    # true: only one nesting level (device group tree)
                    single     : "="
                }
                replace : true
                compile: (tElement, tAttr) ->
                    return (scope, iElement, iAttr) ->
                        #console.log scope, iAttr["treeconfig"], tAttr, iAttr
                        #scope.treeconfig = scope.$eval(tAttr["treeconfig"])
                        #console.log scope.treeconfig
                        iElement.append($compile($templateCache.get("tree_root_node"))(scope))
                } 
    ]).directive("subtree", ["$compile", "$templateCache",
        ($compile, $templateCache) ->
            return {
                restrict : "E"
                scope    : {
                    tree       : "="
                    treeconfig : "="
                    single     : "="
                }
                replace : true
                compile: (tElement, tAttr) ->
                    return (scope, iElement, iAttr) ->
                        iElement.append($compile(if scope.single then $templateCache.get("tree_subtree_node_single") else $templateCache.get("tree_subtree_node"))(scope))
                } 
    ]).directive("subnode", ["$compile", "$templateCache",
        ($compile, $templateCache) ->
            return {
                restrict : "E"
                scope    : {
                    entry      : "="
                    treeconfig : "="
                }
                replace : true
                compile: (tElement, tAttr) ->
                    return (scope, iElement, iAttr) ->
                        iElement.append($compile($templateCache.get("tree_subnode"))(scope))
                } 
    ])

root = exports ? this
root.tree_config = tree_config
