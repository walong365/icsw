angular.module(
    "icsw.config.domain_name_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular"
    ]
).controller("icswConfigDomainNameTreeCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "ICSW_URLS", "icswConfigDomainNameTreeService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, ICSW_URLS, icswConfigDomainNameTreeService) ->
        $scope.dnt = new icswConfigDomainNameTreeService($scope, {})
        $scope.pagSettings = paginatorSettings.get_paginator("dtn_base", $scope)
        $scope.entries = []
        $scope.edit_mixin = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.edit_mixin.use_modal = false
        $scope.edit_mixin.use_promise = true
        $scope.edit_mixin.new_object = (scope) -> return {
            "name" : "new"
            "parent" : (entry.idx for entry in $scope.entries when entry.depth == 0)[0]
            "create_short_names" : true
        }
        $scope.edit_mixin.delete_confirm_str = (obj) -> return "Really delete domain tree node '#{obj.name}' ?"
        $scope.edit_mixin.modify_rest_url = ICSW_URLS.REST_DOMAIN_TREE_NODE_DETAIL.slice(1).slice(0, -2)
        $scope.edit_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST.slice(1))
        $scope.edit_mixin.edit_template = "icsw.config.domain.tree.node"
        $scope.form = {}
        $scope.reload = () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, {}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.entries = data[0]
                $scope.edit_mixin.create_list = $scope.entries
                $scope.edit_mixin.delete_list = $scope.entries
                $scope.rebuild_dnt()
            )
        $scope.edit_obj = (dtn, event) ->
            $scope.dnt.clear_active()
            $scope.dnt_lut[dtn.idx].active = true
            $scope.dnt.show_active()
            pre_parent = dtn.parent
            $scope.edit_mixin.edit(dtn, event).then((data) ->
                if data.parent == pre_parent
                    $scope.dnt.iter(
                        (entry) ->
                            if entry.parent and entry.parent.obj.name
                                entry.obj.full_name = "#{entry.obj.name}.#{entry.parent.obj.full_name}"
                            else
                                entry.obj.full_name = entry.obj.name
                    )
                else
                    $scope.reload()
            )
        $scope.delete_obj = (obj) ->
            $scope.edit_mixin.delete_obj(obj).then((data) ->
                if data
                    $scope.rebuild_dnt()
                    $scope.dnt.clear_active()
            )
        $scope.rebuild_dnt = () ->
            dnt_lut = {}
            $scope.dnt.clear_root_nodes()
            for entry in $scope.entries
                t_entry = $scope.dnt.new_node({folder:false, obj:entry, expand:entry.depth == 0})
                dnt_lut[entry.idx] = t_entry
                if entry.parent
                    #$scope.fqdn_lut[entry.parent].fqdn_childs.push(entry)
                    dnt_lut[entry.parent].add_child(t_entry)
                else
                    $scope.dnt.add_root_node(t_entry)
            $scope.dnt_lut = dnt_lut
        $scope.create_new = ($event) ->
            $scope.dnt.clear_active()
            $scope.edit_mixin.create($event).then((data) ->
                $scope.reload()
            )
        $scope.get_valid_parents = (obj) ->
            p_list = (value for value in $scope.entries)
            if obj.idx
                # remove all nodes below myself
                r_list = []
                add_list = [obj.idx] 
                while add_list.length
                    r_list = r_list.concat(add_list)
                    add_list = (value.idx for value in p_list when (value.parent in r_list and value.idx not in r_list))
                p_list = (value for value in p_list when value.idx not in r_list)
            return p_list
        $scope.close_modal = () ->
            $scope.dnt.clear_active()
            if $scope.cur_edit
                $scope.cur_edit.close_modal()
        $scope.reload()
]).service("icswConfigDomainNameTreeService", () ->
    class domain_name_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = true
            @show_childs = false
        get_name : (t_entry) ->
            dtn = t_entry.obj
            if dtn.parent
                return "#{dtn.name} (*#{dtn.node_postfix}.#{dtn.full_name})"
            else
                return "TOP"
        handle_click: (entry, event) =>
            @clear_active()
            entry.active = true
            dtn = entry.obj
            if dtn.parent
                @scope.edit_obj(dtn, event)
).directive("icswConfigDomainNameTreeHead", ["$templateCache", ($templateCache) ->
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
    }
])
