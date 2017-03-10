# Copyright (C) 2012-2017 init.at
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

angular.module(
    "icsw.config.domain_name_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select",
        "restangular", "icsw.backend.domain_name_tree",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.domaintree")
]).service("icswConfigDomainNameTreeService",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    class icswConfigDomainNameTree extends icswReactTreeConfig

        constructor: (@callback, args) ->
            super(args)

        clear_tree: () =>
            @lut = {}

        get_name: (t_entry) ->
            dtn = t_entry.obj
            if dtn.parent
                return "#{dtn.name} (*#{dtn.node_postfix}.#{dtn.full_name})"
            else
                return "TOP"

        toggle_active_obj: (obj) =>
            node = @lut[obj.idx]
            if obj.depth
                node.set_active(!node.active)
                @show_active()
                @callback("update_active")

        handle_click: (event, entry) =>
            @toggle_active_obj(entry.obj)
            @callback("call_digest")

        handle_context_menu: (event, entry) =>
            dtn = entry.obj
            if dtn.depth
                @callback("edit_entry", dtn)
            event.preventDefault()

]).controller("icswConfigDomainNameTreeCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "icswAccessLevelService", "ICSW_URLS", "icswConfigDomainNameTreeService",
    "icswDomainTreeService", "$rootScope", "ICSW_SIGNALS", "toaster",
    "icswDomainTreeNodeBackup", "icswComplexModalService", "icswToolsSimpleModalService",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, icswAccessLevelService, ICSW_URLS, icswConfigDomainNameTreeService,
    icswDomainTreeService, $rootScope, ICSW_SIGNALS, toaster,
    icswDomainTreeNodeBackup, icswComplexModalService, icswToolsSimpleModalService,
) ->
    $scope.struct = {
        # data valid
        data_valid: false
        # tree
        tree: undefined
        # display tree
        disp_tree: undefined
        # number active (selected)
        num_active: 0
    }
    $scope.reload = () ->
        $scope.struct.data_valid = false
        icswDomainTreeService.reload($scope.$id).then(
            (tree) ->
                $scope.struct.disp_tree = new icswConfigDomainNameTreeService(
                    (cmd, arg) =>
                        if cmd == "select_category"
                            $scope.struct.selected_category = arg
                        else if cmd == "call_digest"
                            $scope.$digest()
                        else if cmd == "update_active"
                            $scope.update_active()
                        else if cmd == "edit_entry"
                            $scope.create_or_edit(null, false, arg)
                        else
                            console.error "unkown callback command '#{cmd}'"
                    {
                        show_selection_buttons: false
                        show_select: false
                        show_descendants: true
                    }
                )
                $scope.struct.tree = tree
                # init struct for list-service
                $scope.struct.num_active = 0
                $scope.rebuild_dnt()
                $scope.struct.data_valid = true
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), (event) ->
        $scope.rebuild_dnt()

    )

    $scope.clear_active = () ->
        $scope.struct.disp_tree.clear_active()
        $scope.update_active()

    $scope.update_active = ()->
        $scope.struct.num_active = $scope.struct.disp_tree.get_active().length
        $scope.struct.disp_tree.show_active()

    $scope.rebuild_dnt = () ->
        # save previous active nodes
        active = (entry.obj.idx for entry in $scope.struct.disp_tree.get_active())
        $scope.struct.disp_tree.clear_tree()
        $scope.struct.disp_tree.clear_root_nodes()
        for entry in $scope.struct.tree.list
            t_entry = $scope.struct.disp_tree.create_node(
                {
                    folder: false
                    obj: entry
                    expand: entry.depth == 0
                }
            )
            $scope.struct.disp_tree.lut[entry.idx] = t_entry
            entry.$$leaf = t_entry
            if entry.parent
                $scope.struct.disp_tree.lut[entry.parent].add_child(t_entry)
            else
                $scope.struct.disp_tree.add_root_node(t_entry)
        # activate nodes
        $scope.struct.disp_tree.iter(
            (entry) ->
                if entry.obj.idx in active
                    entry.active = true
        )
        $scope.update_active()

    $scope.delete = ($event, obj) ->
        if $event
            $event.preventDefault()
            $event.stopPropagation()
        icswToolsSimpleModalService("Really delete DTN #{obj.full_name} ?").then(
            () =>
                $scope.struct.tree.delete_domain_tree_node_entry(obj).then(
                    () ->
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), $scope.struct.tree)
                )
        )

    $scope.delete_many = ($event) ->
        active = $scope.struct.disp_tree.get_active()
        icswToolsSimpleModalService("Really delete #{active.length} DomainTreeNodes ?").then(
            (doit) ->
                $q.allSettled(
                    ($scope.struct.tree.delete_domain_tree_node_entry(entry.obj) for entry in active)
                ).then(
                    (result) ->
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), $scope.struct.tree)
                )
        )

    $scope.create_or_edit = ($event, create, obj_or_parent) ->
        if $event
            $event.preventDefault()
            $event.stopPropagation()
        if create
            # _parent = (value for value in $scope.tree.lmode_entries when value.depth == 1 and value.full_name.split("/")[1] == top_level)[0]
            r_struct = {
                name: "super-new.domain.at"
                parent: $scope.struct.tree.tln.idx
                depth: 2
                create_short_names: true
                always_create_ip: false
                write_nameserver_config: false
                comment: "New Domain"
            }
            # all nodes are valid
            valid_parents = $scope.struct.tree.list
            obj_or_parent = r_struct
        else
            dbu = new icswDomainTreeNodeBackup()
            dbu.create_backup(obj_or_parent)
            # get valid parents
            # step 1: everything below myself
            _get_below = (_idx) ->
                _childs = (
                    node.idx for node in $scope.struct.tree.list when node.parent == _idx
                )
                r_list = [_idx]
                for _child in _childs
                    r_list = r_list.concat(_get_below(_child))
                return r_list

            not_idx = _get_below(obj_or_parent.idx)
            # step 2: everything else is a possible parent node
            valid_parents = (
                entry for entry in $scope.struct.tree.list when entry.idx not in not_idx
            )

        sub_scope = $scope.$new(true)
        sub_scope.tree = $scope.struct.tree
        sub_scope.edit_obj = obj_or_parent
        sub_scope.valid_parents = valid_parents
        show_delete_callback = if create then false else true

        ok_label = if create then "Create" else "Modify"

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.config.domain.tree.node.form"))(sub_scope)
                title: "#{ok_label} Domain tree node entry '#{obj_or_parent.name}'"
                # css_class: "modal-wide"
                ok_label: ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            $scope.struct.tree.create_domain_tree_node_entry(sub_scope.edit_obj).then(
                                (ok) ->
                                    $scope.struct.tree = undefined
                                    $scope.struct.disp_tree = undefined
                                    $scope.reload()
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            if sub_scope.edit_obj.name.match(/\./)
                                toaster.pop("warning", "no dots allowed in name", "")
                                d.reject("form invalid")
                            else
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        $scope.struct.tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                    return d.promise
                delete_ask: true
                show_delete_callback: show_delete_callback

                delete_callback: (modal) ->
                    d = $q.defer()
                    $scope.struct.tree.delete_domain_tree_node_entry(sub_scope.edit_obj).then(
                        (ok) ->
                            # sync with tree
                            $rootScope.$emit(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), $scope.struct.tree)
                            d.resolve("deleted")
                        (notok) ->
                            d.reject("not deleted")
                    )
                    return d.promise

                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(obj_or_parent)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "finish"
                $rootScope.$emit(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), $scope.struct.tree)
                sub_scope.$destroy()
        )

    $scope.reload()
]).controller("icswConfigDomainNameTreeRowCtrl",
[
    "$scope",
(
    $scope
) ->
    $scope.get_tr_class = (obj) ->
        if $scope.struct.disp_tree.lut[obj.idx].active
            return "danger"
        else
            return if obj.depth > 0 then "" else "success"

    $scope.get_space = (depth) ->
        return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")

    $scope.click_row = ($event, obj) ->
        $scope.struct.disp_tree.toggle_active_obj(obj)

]).directive("icswConfigDomainNameTreeRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.domain.name.tree.row")
        controller: "icswConfigDomainNameTreeRowCtrl"
    }
]).directive("icswConfigDomainNameTree",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.domain.name.tree")
        controller: "icswConfigDomainNameTreeCtrl"
    }
])
