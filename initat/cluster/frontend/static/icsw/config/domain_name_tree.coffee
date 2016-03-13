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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular"
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
]).service("icswDomainTree", ["icswTools", (icswTools) ->
    class icswDomainTree
        constructor: () ->
            @data_set = false
            @list = []
            @lut = {}

        link: () =>
            # create helper entries

        update: (new_list) =>
            @data_set = true
            @list.length = 0
            for entry in new_list
                @list.push(entry)
            @lut = icswTools.build_lut(@list)
            # set top level node
            @tln = (entry for entry in @list when entry.depth == 0)[0]
            @link()

        get_full_name: (dev) =>
            if dev.domain_tree_node
                node = @lut[dev.domain_tree_node]
                _name = "#{dev.name}#{node.node_postfix}"
                if node.depth
                    _name = "#{_name}.#{node.full_name}"
                return _name
            else
                return dev.name

        show_dtn: (dev) =>
            if dev.domain_tree_node
                node = @lut[dev.domain_tree_node]
            else
                node = @tln
            r_str = if node.node_postfix then "#{node.node_postfix}" else ""
            if node.depth
                r_str = "#{r_str}.#{node.full_name}"
            else
                r_str = "#{r_str} [TLN]"
            return r_str

]).service('icswDomainTreeService', ["Restangular", "$q", "icswTools", "icswCachingCall", "ICSW_URLS", "icswDomainTree", (Restangular, $q, icswTools, icswCachingCall, ICSW_URLS, icswDomainTree) ->
    # domain_rest = Restangular.all(ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST.slice(1)).getList().$object
    _fetch_dict = {}
    _result = new icswDomainTree()
    load_called = false
    load_data = (client) ->
        load_called = true
        _wait_list = []
        if client
            _defer = $q.defer()
        icswCachingCall.fetch(client, ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, [], []).then(
            (data) ->
                _result.update(data)
                if client
                    _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        if client
            return _defer
    trigger_reload = () ->
        # this code works in principle but is not recommended because we will overwrite all local settings
        load_data(null)
    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result.data_set
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]
    return {
        "trigger_reload": () ->
            trigger_reload()
        "load": (client) ->
            # load from server when first load or return result
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).controller("icswConfigDomainNameTreeCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "$q", "$uibModal", "icswAcessLevelService", "ICSW_URLS", "icswConfigDomainNameTreeService", "icswDomainTreeService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, $q, $uibModal, icswAcessLevelService, ICSW_URLS, icswConfigDomainNameTreeService, icswDomainTreeService) ->
        $scope.dnt = new icswConfigDomainNameTreeService($scope, {})
        $scope.pagSettings = paginatorSettings.get_paginator("dtn_base", $scope)
        $scope.entries = []
        $scope.edit_mixin = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q)
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
            icswDomainTreeService.load($scope.$id).then((data) ->
                $scope.entries = data
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
]).service("icswConfigDomainNameTreeService", ["icswTreeConfig", (icswTreeConfig) ->
    class domain_name_tree extends icswTreeConfig
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
            @scope.$digest()
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
    }
])
