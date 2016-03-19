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

angular.module(
    "icsw.config.domain_name_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select",
        "restangular", "icsw.backend.domain_name_tree",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.domaintree", {
            url: "/domaintree"
            templateUrl: "icsw/main/device/domaintree.html"
            data:
                pageTitle: "Domain name tree"
                rights: ["user.modify_domain_name_tree"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-list-alt"
                    ordering: 45
        }
    )
]).service("icswConfigDomainNameTreeService",
[
    "icswTreeConfig",
(
    icswTreeConfig
) ->
    class icswConfigDomainNameTree extends icswTreeConfig

        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = true
            @show_childs = false

        clear_tree: () =>
            @lut = {}

        get_name : (t_entry) ->
            dtn = t_entry.obj
            if dtn.parent
                return "#{dtn.name} (*#{dtn.node_postfix}.#{dtn.full_name})"
            else
                return "TOP"

        handle_click: (entry, event) =>
            if not entry.active
                # i am not the active node, clear others
                @clear_active()
            dtn = entry.obj
            if dtn.depth
                if entry.active
                    @scope.create_or_edit(event, false, dtn)
                else
                    entry.active = true
                    @show_active()

]).controller("icswConfigDomainNameTreeCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "icswAcessLevelService", "ICSW_URLS", "icswConfigDomainNameTreeService",
    "icswDomainTreeService", "icswComplexModalService", "toaster", "icswDomainTreeNodeBackup",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, icswAcessLevelService, ICSW_URLS, icswConfigDomainNameTreeService,
    icswDomainTreeService, icswComplexModalService, toaster, icswDomainTreeNodeBackup,
) ->
    $scope.tree = undefined
    $scope.reload = () ->
        $scope.dn_tree = new icswConfigDomainNameTreeService($scope)
        icswDomainTreeService.load($scope.$id).then(
            (tree) ->
                $scope.tree = tree
                $scope.rebuild_dnt()
        )

    $scope.rebuild_dnt = () ->
        # save previous active nodes
        active = (entry.obj.idx for entry in $scope.dn_tree.get_active())
        $scope.dn_tree.clear_tree()
        $scope.dn_tree.clear_root_nodes()
        for entry in $scope.tree.list
            t_entry = $scope.dn_tree.new_node(
                {
                    folder: false
                    obj: entry
                    expand: entry.depth == 0
                }
            )
            $scope.dn_tree.lut[entry.idx] = t_entry
            if entry.parent
                $scope.dn_tree.lut[entry.parent].add_child(t_entry)
            else
                $scope.dn_tree.add_root_node(t_entry)
        # activate nodes
        $scope.dn_tree.iter(
            (entry) ->
                if entry.obj.idx in active
                    entry.active = true
        )
        $scope.dn_tree.show_active()

    $scope.create_or_edit = (event, create, obj_or_parent) ->
        if create
            # _parent = (value for value in $scope.tree.lmode_entries when value.depth == 1 and value.full_name.split("/")[1] == top_level)[0]
            r_struct = {
                name: "super-new.domain.at"
                parent: $scope.tree.tln.idx
                depth: 2
                create_short_names: true
                always_create_ip: false
                write_nameserver_config: false
                comment: "New Domain"
            }
            # all nodes are valid
            valid_parents = $scope.tree.list
            obj_or_parent = r_struct
        else
            dbu = new icswDomainTreeNodeBackup()
            dbu.create_backup(obj_or_parent)
            # get valid parents
            # step 1: everything below myself
            _get_below = (_idx) ->
                _childs = (node.idx for node in $scope.tree.list when node.parent == _idx)
                r_list = [_idx]
                for _child in _childs
                    r_list = r_list.concat(_get_below(_child))
                return r_list

            not_idx = _get_below(obj_or_parent.idx)
            # step 2: everything else is a possible parent node
            valid_parents = (entry for entry in $scope.tree.list when entry.idx not in not_idx)

        sub_scope = $scope.$new(false)
        sub_scope.tree = $scope.tree
        sub_scope.edit_obj = obj_or_parent
        sub_scope.valid_parents = valid_parents

        ok_label = if create then "Create" else "Modify"

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.config.domain.tree.node.form"))(sub_scope)
                title: "#{ok_label} Domain tree node entry '#{obj_or_parent.name}"
                # css_class: "modal-wide"
                ok_label: ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        if create
                            $scope.tree.create_domain_tree_node_entry(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            if sub_scope.edit_obj.name.match(/\./)
                                toaster.pop("warning", "no dots allowed in name", "", 0)
                                d.reject("form invalid")
                            else
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        $scope.tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                    return d.promise
                delete_ask: true

                delete_callback: (modal) ->
                    d = $q.defer()
                    $scope.tree.delete_domain_tree_node_entry(sub_scope.edit_obj).then(
                        (ok) ->
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
                $scope.rebuild_dnt()
                sub_scope.$destroy()
        )

    $scope.reload()
]).directive("icswConfigDomainNameTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.domain.name.tree.head")
    }
]).directive("icswConfigDomainNameTreeRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.domain.name.tree.row")
        link : (scope, el, attrs) ->
            scope.get_space = (depth) ->
                return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")
    }
]).directive("icswConfigDomainNameTreeEditTemplate", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("domain.tree.node.form")
        link : (scope, element, attrs) ->
            scope.form_error = (field_name) ->
                if scope.form[field_name].$valid
                    return ""
                else
                    return "has-error"
    }
]).directive("icswConfigDomainNameTree", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.domain.name.tree")
        controller: "icswConfigDomainNameTreeCtrl"
    }
])
