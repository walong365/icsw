{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

_tree_node = '
<ul ng-class="{\'dynatree-container\' : (treedepth || 0) == 0}">
    <span ng-show="!treedepth && !(tree || treeconfig.root_nodes).length">No entries</span>
    <li ng-repeat="entry in (tree || treeconfig.root_nodes)" ng-class="{\'dynatree-lastsib\' : $last}">
        <span ng-class="treeconfig.get_span_class(entry, $last)">
            <span ng-show="!entry._num_childs" class="dynatree-connector"></span>
            <span ng-show="entry._num_childs" class="dynatree-expander" ng-click="treeconfig.toggle_expand_node(entry)"></span>
            <span ng-if="treeconfig.show_select" class="dynatree-checkbox" style="margin-left:2px;" ng-click="treeconfig.toggle_checkbox_node(entry)"></span>
            <span ng-show="dynatree.show_icons" class="dynatree-icon"></span>
            <div class="btn-group btn-group-xs" ng-show="entry._num_childs && treeconfig.show_selection_buttons">
                <input type="button" class="btn btn-success" value="S" ng-click="treeconfig.toggle_tree_state(entry, 1)" title="select subtree"></input>
                <input type="button" class="btn btn-primary" value="T" ng-click="treeconfig.toggle_tree_state(entry, 0)" title="toggle subtree selection"></input>
                <input type="button" class="btn btn-warning" value="C" ng-click="treeconfig.toggle_tree_state(entry, -1)" title="deselect subtree"></input>
            </div>
            <div ng-if="((treedepth || 0) == 0) && treeconfig.show_tree_expand_buttons" class="btn-group btn-group-xs">
                <input type="button" class="btn btn-success" value="e" ng-click="treeconfig.toggle_expand_tree(1, false)" title="expand all"></input>
                <input ng-if="treeconfig.show_select" type="button" class="btn btn-primary" value="s" ng-click="treeconfig.toggle_expand_tree(1, true)" title="expand selected"></input>
                <input type="button" class="btn btn-danger" value="c" ng-click="treeconfig.toggle_expand_tree(-1, false)" title="collapse all"></input>
            </div>
            <a ng-href="#" class="dynatree-title" ng-click="treeconfig.handle_click(entry, $event)">{{ treeconfig.get_name(entry) }}
                <span ng-if="treeconfig.show_childs && !treeconfig.show_descendants" ng-show="entry._num_childs">({{ entry._num_childs }}<span ng-show="entry._sel_childs"> / {{ entry._sel_childs }}</span>)</span>
                <span ng-if="treeconfig.show_descendants && !treeconfig.show_childs" ng-show="entry._num_descendants">({{ entry._num_descendants }}<span ng-show="entry._sel_descendants"> / {{ entry._sel_descendants }}</span>)</span>
            </a>
        </span>
        <tree ng-if="entry.expand && entry.children.length" tree="entry.children" treedepth="(treedepth || 0) + 1" treeconfig="treeconfig"></tree>
    </li>
</ul>
'

{% endverbatim %}

class tree_node
    constructor: (args) ->
        # is selected
        @selected = false
        # is expanded
        @expand = false
        # is folder
        @folder   = false
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
        # number of all direct children
        @_num_childs = 0
        # number of selected childs
        @_sel_childs = 0
        # number of selected descendants
        @_sel_descendants = 0
    set_selected: (flag, propagate=true) ->
        # console.log @selected, flag, flag != @selected
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
    add_child: (child) =>
        child.parent = @
        @_num_childs++
        @children.push(child)
        cur_p = @
        while cur_p
            cur_p._num_descendants += 1 + child._num_descendants
            cur_p = cur_p.parent
    recalc_num_descendants: () => 
        @_num_childs = @children.length
        @_num_descendants = @_num_childs
        for child in @children
            @_num_descendants += child.recalc_num_descendants()
        return @_num_descendants
    recalc_sel_descendants: () => 
        @_sel_descendants = (true for entry in @children when entry.selected).length
        for child in @children
            @_sel_descendants += child.recalc_sel_descendants()
        return @_sel_descendants
    recalc_sel_childs: () => 
        @_sel_childs = (true for entry in @children when entry.selected).length
        (child.recalc_sel_childs() for child in @children)

class tree_config
    constructor: (args) ->
        # not really needed, enter more flags here
        @show_selection_buttons = true
        @show_childs = false
        @show_descendants = false
        @show_tree_expand_buttons = true
        @show_icons = true
        @show_select = true
        for key, value of args
            @[key] = value
        @root_nodes = []
        @_node_idx = 0
        @_track_changes = false
    clear_root_nodes: () =>
        @root_nodes = []
    handle_click: () =>
        # override
    get_name: () =>
        # override
        return "node"
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
        new_node._idx = @_node_idx
        new_node.config = @
        return new_node
    add_root_node: (node) =>
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
        remove = true
        new_childs = []
        for sub_entry in entry.children
            keep = false
            if keep_func(sub_entry)
                keep = true
            if not @_prune(sub_entry, keep_func)
                keep = true
            if keep
                new_childs.push(sub_entry)
        entry.children = new_childs
        return if entry.children.length then false else true
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
        entry.set_selected(!entry.selected)
        @selection_changed()
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
                @selection_changed()
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
        entry.set_selection(false)
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
    get_span_class: (entry, last) ->
        r_class = ["dynatree-node"]
        if entry.folder
            r_class.push "dynatree-folder"
        if entry.active
            r_class.push "dynatree-active"
        if last
            r_class.push "dynatree-lastsib"
        if entry.selected
            r_class.push "dynatree-selected"
        if entry.children.length
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

add_tree_directive = (mod) ->
    mod.directive("tree", ["$compile",
        ($compile) ->
            return {
                restrict : "E"
                scope    : {
                    tree       : "="
                    treedepth  : "="
                    treeconfig : "="
                }
                replace : true
                #template : node_template 
                compile: (tElement, tAttr) ->
                    #contents = tElement.contents().remove()
                    #new_el = $compile(node_template)
                    #tElement.replaceWith(new_el)
                    #console.log "c"
                    return (scope, iElement, iAttr) ->
                        # console.log "l", iAttr
                        iElement.append($compile(_tree_node)(scope))
                } 
    ])

root = exports ? this
root.tree_config = tree_config
root.add_tree_directive = add_tree_directive

{% endinlinecoffeescript %}

</script>
