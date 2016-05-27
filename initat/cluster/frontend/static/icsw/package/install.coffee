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

package_module = angular.module(
    "icsw.package.install",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "ui.select", "icsw.tools.table",
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.packageinstall", {
            url: "/packageinstall"
            template: "<icsw-package-install-overview ng-cloak/>"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Package install"
                rights: ["package.package_install"]
                licenses: ["package_install"]
                menuEntry:
                    menukey: "cluster"
                    icon: "fa-download"
                    ordering: 50
        }
    )
]).service("icswPackageInstallRepositoryTree",
[
    "Restangular", "ICSW_URLS", "$q",
(
    Restangular, ICSW_URLS, $q,
) ->
    class icswPackageInstallRepositoryTree
        constructor: (list, srv_list) ->
            @list = []
            @filtered_list = []
            @service_list = []

            # init repo filters
            @filters = {
                show_enabled_repos: false
                show_published_repos: false
            }

            @update(list, srv_list)

        update: (in_list, srv_list) =>
            @list.length = 0
            for entry in in_list
                @list.push(entry)
            @service_list.length = 0
            for entry in srv_list
                @service_list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @service_lut = _.keyBy(@service_list, "idx")
            @apply_filters()

        toggle_filter: (filter_name) ->
            @filters[filter_name] = !@filters[filter_name]
            @apply_filters()

        apply_filters: () ->
            @filtered_list.length = 0
            for entry in @list
                _show = true
                if @filters.show_enabled_repos and not entry.enabled
                    _show = false
                if @filters.show_published_repos and not entry.publish_to_nodes
                    _show = false
                if _show
                    @filtered_list.push(entry)
            @filtered_lut = _.keyBy(@filtered_list, "idx")

        delete_repository: (obj) =>
            d = $q.defer()
            obj.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (notok) =>
                    d.reject("not deleted")
            )
            return d.promise

]).service("icswPackageInstallRepositoryTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS",
    "icswPackageInstallRepositoryTree",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS,
    icswPackageInstallRepositoryTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_PACKAGE_REPO_LIST
            {}
        ]
        [
            ICSW_URLS.REST_PACKAGE_SERVICE_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client, reload) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** PackageRepoList tree loaded ***"
                if _result?
                    _result.update(data[0], data[1])
                else
                    _result = new icswPackageInstallRepositoryTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise

        reload: (client) ->
            return load_data(client).promise
    }

]).service("icswPackageInstallSearchTree",
[
    "Restangular", "ICSW_URLS", "$q", "icswSimpleAjaxCall",
(
    Restangular, ICSW_URLS, $q, icswSimpleAjaxCall,
) ->
    class icswPackageInstallSearchTree
        constructor: (list, srv_list) ->
            @list = []
            @any_pending = false
            @update(list)

        update: (in_list) =>
            @list.length = 0
            for entry in in_list
                @list.push(entry)
            @build_luts()
            @check_pending()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")

        check_pending: () =>
            # check for pending searches
            if (obj.current_state for obj in @list when obj.current_state != "done").length
                @any_pending = true
            else
                @any_pending = false
            return @any_pending

        create_search: (search_string, user_obj) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_PACKAGE_SEARCH_LIST.slice(1)).post(
                {
                    search_string: search_string
                    user: user_obj.idx
                }
            ).then(
                (data) ->
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.PACK_REPO_OVERVIEW
                        data: {
                            mode: "reload_searches"
                        }
                    ).then(
                        (xml) ->
                            defer.resolve("added")
                        (xml) ->
                            defer.resolve("added")
                    )
                (notok) ->
                    defer.reject("not created")
            )
            return defer.promise

        update_search: (obj) =>
            defer = $q.defer()
            obj.put().then(
                (ok) =>
                    @retry_search(obj).then(
                        (ok) ->
                            defer.resolve("done")
                        (noktok) ->
                            defer.reject("error retrying")
                    )
                (notok) ->
                    defer.reject("not saved")
            )
            return defer.promise

        retry_search: (obj) =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                url: ICSW_URLS.PACK_RETRY_SEARCH
                data: {
                    pk: obj.idx
                }
            ).then(
                (xml) ->
                    obj.current_state = "pending"
                    defer.resolve("retrying")
                (xml) ->
                    defer.reject("not ok")
            )
            return defer.promise

        delete_search: (obj) =>
            d = $q.defer()
            obj.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (notok) =>
                    d.reject("not deleted")
            )
            return d.promise

]).service("icswPackageInstallSearchTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS",
    "icswPackageInstallSearchTree",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS,
    icswPackageInstallSearchTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_PACKAGE_SEARCH_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client, reload) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** PackageSearchList tree loaded ***"
                if _result?
                    _result.update(data[0])
                else
                    _result = new icswPackageInstallSearchTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise

        reload: (client) ->
            return load_data(client).promise
    }

]).service("icswPackageInstallTree",
[
    "Restangular", "ICSW_URLS", "$q", "icswSimpleAjaxCall",
(
    Restangular, ICSW_URLS, $q, icswSimpleAjaxCall,
) ->
    # tree of installable packages
    class icswPackageInstallTree
        constructor: (list, srv_list) ->
            @list = []
            @filtered_list = []
            @filter = ""
            @update(list)

        set_filter: (new_filter) =>
            @filter = new_filter
            @filter_list()

        update: (in_list) =>
            @list.length = 0
            for entry in in_list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @filter_list()

        filter_list: () =>
            try
                filter_re = new RegExp(@filter, "gi")
            catch error
                filter_re = new RegExp(".", "gi")
            @filtered_list.length = 0
            for entry in @list
                if entry.name.match(filter_re)
                    @filtered_list.push(entry)
            @filtered_lut = _.keyBy(@filtered_list, "idx")

        delete_package: (obj) =>
            d = $q.defer()
            obj.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (notok) =>
                    d.reject("not deleted")
            )
            return d.promise

]).service("icswPackageInstallTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS",
    "icswPackageInstallTree",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS,
    icswPackageInstallTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_PACKAGE_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client, reload) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** PackageList tree loaded ***"
                if _result?
                    _result.update(data[0])
                else
                    _result = new icswPackageInstallTree(data[0])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise

        reload: (client) ->
            return load_data(client).promise
    }

]).directive("icswPackageInstallOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.overview")
        controller: "icswPackageInstallCtrl"
    }

]).controller("icswPackageInstallCtrl",
[
    "$scope", "$injector", "$compile", "$filter", "$templateCache", "icswToolsSimpleModalService",
    "Restangular", "$q", "$timeout", "blockUI", "icswTools", "icswDeviceTreeService",
    "ICSW_URLS", "icswUserService", "icswSimpleAjaxCall", "icswPackageInstallRepositoryTreeService",
(
    $scope, $injector, $compile, $filter, $templateCache, icswToolsSimpleModalService,
    Restangular, $q, $timeout, blockUI, icswTools, icswDeviceTreeService,
    ICSW_URLS, icswUserService, icswSimpleAjaxCall, icswPackageInstallRepositoryTreeService,
) ->
    # structure
    $scope.struct = {
        # Repository tree
        repo_tree: undefined
        # error info
        repo_info_str: ""
        # Search tree
        search_tree: undefined
        # base tree loaded
        tree_loaded: false
        # user
        user: undefined
    }
    # image / kernel list
    $scope.srv_image_list = []
    $scope.srv_kernel_list = []

    load = (reload) ->
        $scope.struct.tree_loaded = false
        $scope.struct.repo_info_str = "fetching data from server"
        w_list = [
            icswUserService.load($scope.$id)
        ]
        if reload
            w_list.push(icswPackageInstallRepositoryTreeService.reload($scope.$id))
        else
            w_list.push(icswPackageInstallRepositoryTreeService.load($scope.$id))
        $q.all(w_list).then(
            (data) ->
                $scope.struct.repo_info_str = ""
                $scope.struct.tree_loaded = true
                $scope.struct.user = data[0]
                $scope.struct.repo_tree = data[1]
        )

    load(false)

    $scope.toggle_repo_publish = ($event, repo) ->
        repo.publish_to_nodes = if repo.publish_to_nodes then false else true
        repo.put()
        $scope.struct.repo_tree.apply_filters()

    $scope.delete_repo = ($event, repo) ->
        icswToolsSimpleModalService("Really delete repository '#{repo.name}' ?").then(
            (del_yes) ->
                $scope.struct.repo_tree.delete_repository(repo).then(
                    (ok) ->
                        console.log "deleted repo"
                )
        )

    $scope.rescan_repos = ($event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_REPO_OVERVIEW
            data: {
                mode: "rescan_repos"
            }
        ).then(
            (xml) ->
                load(true)
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )

    $scope.toggle_filter = ($event, filter_name) ->
        $scope.struct.repo_tree.toggle_filter(filter_name)

    $scope.init_package_list = (scope) ->
        # true for device / pdc, false for pdc / device style
        $scope.dp_style = true
        $scope.package_list_scope = scope

    $scope.sync_repos = () ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_REPO_OVERVIEW
            data: {
                mode: "sync_repos"
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )

    $scope.clear_caches = () ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_REPO_OVERVIEW
            data: {
                mode: "clear_caches"
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )

    $scope.get_pdc_list = (pack) ->
        # list of devices
        dev_list = []
        # number of devices associated but not shown
        num_dns = 0
        for dev_pk of $scope.state_dict
            dev_pk = parseInt(dev_pk)
            if dev_pk of $scope.device_lut
                _dev = $scope.device_lut[dev_pk]
            else
                _dev = null
            dev_lut = $scope.state_dict[dev_pk]
            if dev_lut[pack.idx].idx?
                if _dev
                    dev_list.push(_dev)
                else
                    num_dns++
        if dev_list.length
            _rs = "#{dev_list.length}: " + (entry.name for entry in dev_list).join(", ")
        else
            _rs = "---"
        if num_dns
            _rs = "#{_rs} (#{num_dns})"
        return _rs

]).directive("icswPackageInstallRepositoryRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.repo.row")
    }
]).directive("icswPackageInstallRepositoryHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        replace: true
        template : $templateCache.get("icsw.package.install.package.repo.head")
    }
]).directive("icswPackageInstallSearchHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.search.head")
    }
]).directive("icswPackageInstallSearchRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.search.row")
    }
]).directive("icswPackageInstallSearchResultHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.search.result.head")
    }
]).directive("icswPackageInstallSearchResultRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.search.result.row")
    }
]).directive("icswPackageInstallSearchOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.search.overview")
        controller: "icswPackageInstallSearchController"
        scope: {
            repo_tree: "=icswRepositories"
        }
    }
]).controller("icswPackageInstallSearchController",
[
    "$scope", "$templateCache", "icswUserService", "ICSW_URLS", "icswSimpleAjaxCall", "Restangular",
    "blockUI", "$rootScope", "ICSW_SIGNALS", "icswUserGroupTreeService",
    "$timeout", "$q", "icswPackageInstallSearchTreeService",
    "icswToolsSimpleModalService", "icswComplexModalService", "$compile", "toaster",
(
    $scope, $templateCache, icswUserService, ICSW_URLS, icswSimpleAjaxCall, Restangular,
    blockUI, $rootScope, ICSW_SIGNALS, icswUserGroupTreeService,
    $timeout, $q, icswPackageInstallSearchTreeService,
    icswToolsSimpleModalService, icswComplexModalService, $compile, toaster,
) ->
    # structure
        
    $scope.struct = {
        search_string: ""
        # repo tree, set via wathcer
        repo_tree: undefined
        # search tree
        search_tree: undefined
        # tree valid
        tree_valid: false
        # reload timeout
        reload_timeout: undefined
        # active search
        active_search: undefined
        # search results
        search_results: []
        # user/group tree
        user_group_tree: undefined
    }

    $scope.$watch("repo_tree", (new_val) ->
        $scope.struct.repo_tree = new_val
    )
    # helper function
        
    clear_active_search = (search) ->
        if $scope.struct.active_search? and $scope.struct.active_search.idx == search.idx
            $scope.struct.active_search = undefined
        
    check_for_reload = () ->
        _stop = false
        if $scope.struct.search_tree.any_pending
            if not $scope.struct.reload_timeout?
                $scope.struct.reload_timeout = $timeout(
                    () ->
                        load(true)
                    5000
                )
        else
            _stop = true
        if _stop
            if $scope.struct.reload_timeout?
                $timeout.cancel($scope.struct.reload_timeout)
                $scope.struct.reload_timeout = undefined

    load = (reload) ->
        _w_list = [
            icswUserService.load($scope.$id)
            icswUserGroupTreeService.load($scope.$id)
        ]
        if reload
            _w_list.push(icswPackageInstallSearchTreeService.reload($scope.$id))
        else
            _w_list.push(icswPackageInstallSearchTreeService.load($scope.$id))
        $q.all(_w_list).then(
            (data) ->
                $scope.struct.user = data[0]
                $scope.struct.user_group_tree = data[1]
                $scope.struct.search_tree = data[2]
                $scope.struct.tree_valid = true
                check_for_reload()
        )
        
    load(false)

    # create new search

    $scope.create_search = () ->
        if $scope.struct.search_string
            blockUI.start()
            $scope.struct.search_tree.create_search($scope.struct.search_string, $scope.struct.user).then(
                (ok) ->
                    load(true)
                    $scope.struct.search_string = ""
                    blockUI.stop()
                (notok) ->
                    blockUI.stop()
            )

    # retry search

    $scope.retry = ($event, obj) ->
        clear_active_search(obj)

        blockUI.start()
        $scope.struct.search_tree.retry_search(obj).then(
            (ok) ->
                load(true)
                blockUI.stop()
            (notok) ->
                blockUI.stop()
        )

    # delete search

    $scope.delete = ($event, search) ->
        clear_active_search(search)
        icswToolsSimpleModalService("Really delete search '#{search.search_string}' ?").then(
            (del_yes) ->
                $scope.struct.search_tree.delete_search(search).then(
                    (ok) ->
                        console.log "deleted search"
                )
        )

    # edit search

    $scope.edit = ($event, search) ->
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = search
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.package.search.form"))(sub_scope)
                title: "Package search"
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        $scope.struct.search_tree.update_search(sub_scope.edit_obj).then(
                            (ok) ->
                                load(true)
                                d.resolve("updated")
                            (not_ok) ->
                                d.reject("not updated")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "finish"
                sub_scope.$destroy()
        )

    $scope.clear_active_search = (del_obj) ->
        if $scope.active_search and $scope.active_search.idx == del_obj.idx
            $scope.active_search = undefined

    $scope.show_search_result = ($event, obj) ->
        $scope.struct.active_search = obj
        if $scope.struct.active_search?
            blockUI.start()
            Restangular.all(ICSW_URLS.REST_PACKAGE_SEARCH_RESULT_LIST.slice(1)).getList(
                {
                    package_search: $scope.struct.active_search.idx
                }
            ).then(
                (new_data) ->
                    # gently rebuild list
                    $scope.struct.search_results.length = 0
                    for entry in new_data
                        entry.target_repo = null
                        $scope.struct.search_results.push(entry)
                    blockUI.stop()
            )
        else
            $scope.struct.search_results.length = 0

    # take search result

    $scope.take_search_result = ($event, obj, exact) ->
        blockUI.start()
        obj.copied = true
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_USE_PACKAGE
            data: {
                pk: obj.idx
                exact: if exact then 1 else 0
                target_repo: if obj.target_repo then obj.target_repo else 0
            }
        ).then(
            (xml) ->
                blockUI.stop()
                $scope.show_search_result($event, $scope.struct.active_search)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_PACKAGE_INSTALL_LIST_CHANGED"))
            (xml) ->
                obj.copied = false
                blockUI.stop()
        )
    
        
]).directive("icswPackageInstallPackageRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.list.row")
    }
]).directive("icswPackageInstallDevice",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.device.overview")
        controller: "icswPackageInstallDeviceCtrl"
        # create isolated scope, otherwise we screw the RepoView
        scope: {}
    }
]).service("icswPDCEntry",
[
    "$q",
(
    $q,
) ->
    class icswPDCEntry
        constructor: (@pdc_struct, device, pack) ->
            @device_idx = device.idx
            @package_idx = pack.idx
            # is selected
            @selected = false
            @clear_set()

        clear_set: () =>
            # is a valid package (== associated ?)
            @set = false
            @idx = undefined
            @$$td_class = "text-center"


        change_selection: (t_state) =>
            if t_state == 1
                @selected = true
            else if t_state == -1
                @selected = false
            else
                @selected = !@selected
            @build_info()
            @pdc_struct.update_selection()

        feed: (pdc) =>
            @set = true
            @idx = pdc.idx
            for attr_name in [
                "installed", "package", "response_str", "response_type",
                "target_state",
                "install_time", "installed_name",
                "installed_version", "installed_release"
            ]
                @[attr_name] = pdc[attr_name]
            @build_info()

        build_info: () =>
            if @set
                @_build_info_set()
            else
                @_build_info_unset()

        _build_info_unset: () =>
                @$$td_class = "text-center"

        _build_info_set: () =>
            if @target_state
                if @target_state == "keep"
                    _gc = "glyphicon glyphicon-minus"
                else if @target_state == "install"
                    _gc = "glyphicon glyphicon-ok"
                else if @target_state == "upgrade"
                    _gc = "glyphicon glyphicon-arrow-up"
                else if @target_state == "erase"
                    _gc = "glyphicon glyphicon-remove"
                else
                    # something strange ...
                    _gc = "glyphicon glyphicon-asterisk"
            else
                _gc = "glyphicon"
            @$$ts_class = _gc

            if @installed == "y"
                _bc = "btn-success"
            else if @installed == "u"
                _bc = "btn-warning"
            else if @installed == "n"
                _bc = "btn-danger"
            else
                _bc = "btn-active"
            @$$button_class = _bc

            if @installed == "y" and @installed_ame
                inst_name = @installed_nam
                if @installed_versio
                    inst_name = "#{inst_name}-#{installed_version}"
                else
                    inst_name = "#{inst_name}-?"
                if @installed_release
                    inst_name = "#{inst_name}-#{@installed_release}"
                else
                    inst_name = "#{inst_name}-?"
            else
                inst_name = "---"
            @$$installed_version = inst_name

            t_field = ["target state : #{@target_state}"]
            if @installed == "n"
                t_field.push("<br>installed: no")
            else if @installed == "u"
                t_field.push("<br>installed: unknown")
            else if @installed == "y"
                t_field.push("<br>installed: yes")
                if @install_time
                    t_field.push("<br>installtime: " + moment.unix(@install_time).format("ddd, D. MMM YYYY HH:mm:ss"))
                else
                    t_field.push("<br>installtime: unknown")
                if @installed_name
                    t_field.push("<br>installed: #{@$$installed_version}")
            else
                t_field.push("<br>unknown install state '#{@installed}")
            if @kernel_dep
                t_field.push("<hr>")
                t_field.push("kernel dependencies enabled (#{@kernel_list.length})")
                # for _idx in @kernel_list
                #    t_field.push("<br>" + (_k.name for _k in scope.parent.kernel_list when _k.idx == _idx)[0])
            if @image_dep
                t_field.push("<hr>")
                t_field.push("image dependencies enabled (#{@image_list.length})")
                # for _idx in @image_list
                #    t_field.push("<br>" + (_i.name for _i in scope.parent.image_list when _i.idx == _idx)[0])
            @$$tooltip = "<div class='text-left'>" + t_field.join("") + "<div>"

            _i = @installed
            _t = @target_state
            _k = "#{_i}.#{_t}"
            if _k in [
                "y.keep", "y.upgrade",
                "y.install", "n.erase", "n.keep"
            ]
                @$$td_class = "text-center success"
            else
                @$$td_class = "text-center danger"

]).service("icswPDCStruct",
[
    "$q", "icswPDCEntry",
(
    $q, icswPDCEntry,
) ->
    class icswPDCStruct
        constructor: (@devices, @package_tree) ->
            # build lut
            @lut = {}
            for dev in @devices
                @lut[dev.idx] = {}
                for pack in @package_tree.list
                    @lut[dev.idx][pack.idx] = new icswPDCEntry(@, dev, pack)
            @selected_pdcs = []
            @unset_selected_pdcs = []

        # package deleted
        package_deleted: (pack) =>
            # already reflected in the package_tree, we have to remove the package from the lut
            for dev in @devices
                delete @lut[dev.idx][pack.idx]

        feed: () =>
            # sync with devices
            # step 1: clear all set flags
            for dev in @devices
                for pack in @package_tree.list
                    @lut[dev.idx][pack.idx].clear_set()
            # step 2: check for set
            for dev in @devices
                for pdc in dev.package_set
                    @lut[dev.idx][pdc.package].feed(pdc)
            @update_selection()

        update_selection: () =>
            @selected_pdcs.length = 0
            @unset_selected_pdcs.length = 0
            for pack in @package_tree.list
                # reset flags
                pack.$$any_set = false
                pack.$$any_set_selected = false
                pack.$$any_unset_selected = false
            for dev in @devices
                for idx, pdc of @lut[dev.idx]
                    pack = @package_tree.lut[idx]
                    if pdc.selected
                        if pdc.set
                            # package is set and selected (==ok to remove)
                            pack.$$any_set_selected = true
                            @selected_pdcs.push(pdc)
                        else
                            # package is selected but unset (==ok to attach)
                            pack.$$any_unset_selected = true
                            @unset_selected_pdcs.push(pdc)
                    if pdc.set
                        pack.$$any_set = true
            # global flags
            for _fl in ["$$any_set_selected", "$$any_unset_selected", "$$any_set"]
                @[_fl] = _.some((pack[_fl] for pack in @package_tree.list))

        change_package_sel: (pack, t_state) =>
            for dev in @devices
                for idx, pdc of @lut[dev.idx]
                    if parseInt(idx) == parseInt(pack.idx) and idx of @package_tree.filtered_lut
                        pdc.change_selection(t_state)
            @_selection_changed()

        change_device_sel: (device, t_state) =>
            for idx, pdc of @lut[device.idx]
                if idx of @package_tree.filtered_lut
                    pdc.change_selection(t_state)
            @_selection_changed()

        _selection_changed: () =>
            @update_selection()

        get_attach_list: (pack) =>
            attach_list = []
            for dev in @devices
                for idx, pdc of @lut[dev.idx]
                    if pack?
                        if parseInt(idx) == parseInt(pack.idx)
                            if pdc.selected and not pdc.set
                                attach_list.push([dev.idx, pack.idx])
                    else if pdc.selected and not pdc.set
                        attach_list.push([dev.idx, pdc.package_idx])
            # console.log "a=", attach_list
            return attach_list

        get_remove_list: (pack) =>
            remove_list = []
            for dev in @devices
                for idx, pdc of @lut[dev.idx]
                    if pack?
                        if parseInt(idx) == parseInt(pack.idx)
                            if pdc.selected
                                remove_list.push(pdc.idx)
                    else if pdc.selected
                        remove_list.push(pdc.idx)
            # console.log "r=", remove_list
            return remove_list

]).controller("icswPackageInstallDeviceCtrl",
[
    "$scope", "icswPackageInstallTreeService", "$q", "icswDeviceTreeService", "blockUI",
    "icswUserService", "$rootScope", "ICSW_SIGNALS", "icswActiveSelectionService",
    "icswPackageInstallRepositoryTreeService", "icswToolsSimpleModalService", "$timeout",
    "icswDeviceTreeHelperService", "icswPDCStruct", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswComplexModalService", "toaster", "$compile", "$templateCache",
(
    $scope, icswPackageInstallTreeService, $q, icswDeviceTreeService, blockUI,
    icswUserService, $rootScope, ICSW_SIGNALS, icswActiveSelectionService,
    icswPackageInstallRepositoryTreeService, icswToolsSimpleModalService, $timeout,
    icswDeviceTreeHelperService, icswPDCStruct, ICSW_URLS, icswSimpleAjaxCall,
    icswComplexModalService, toaster, $compile, $templateCache,
) ->
    $scope.struct = {
        # package tree
        package_tree: undefined
        # package tree loaded
        package_tree_loaded: false
        # repo tree
        repo_tree: undefined
        # device tree loaded
        device_tree_loaded: false
        # device tree
        device_tree: undefined
        # package info str
        package_info_str: ""
        # device info str
        device_info_str: ""
        # devices
        devices: []
        # user
        user: undefined
        # reload timeout
        reload_timeout: undefined
        # pdc update running
        pdc_updating: false
        # pdc timeout
        pdc_update_timeout: undefined
        # pdc struct
        pdc_struct: undefined
        # package filter
        package_filter: ""
    }

    load = (reload) ->
        $scope.struct.package_info_str = "loading package list"
        w_list = [
            icswUserService.load($scope.$id)
            icswPackageInstallRepositoryTreeService.load($scope.$id)
        ]
        if reload
            w_list.push(icswPackageInstallTreeService.reload($scope.$id))
        else
            w_list.push(icswPackageInstallTreeService.load($scope.$id))
        $q.all(w_list).then(
            (data) ->
                $scope.struct.package_info_str = ""
                $scope.struct.user = data[0]
                $scope.struct.repo_tree = data[1]
                $scope.struct.package_tree = data[2]
                $scope.struct.package_tree_loaded = true
                $scope.struct.package_tree.set_filter($scope.struct.package_filter)
                if $scope.struct.device_tree_loaded
                    init_pdc()
        )


    load(false)

    $scope.$on("$destroy", () ->
        stop_pdc_update()
    )

    # watch packet filter

    _filter_to = undefined
    $scope.$watch("struct.package_filter", (new_val) ->
        if _filter_to?
            $timeout.cancel(_filter_to)
        _filter_to = $timeout(
            () ->
                if $scope.struct.package_tree_loaded
                    $scope.struct.package_tree.set_filter(new_val)
            500
        )
    )

    # pdc functions
    init_pdc = () ->
        # init new pdc structure
        stop_pdc_update()
        new_pdc = new icswPDCStruct($scope.struct.devices, $scope.struct.package_tree)
        $scope.struct.pdc_struct = new_pdc
        update_pdc()

    stop_pdc_update = () ->
        if $scope.struct.pdc_udpate_timeout
            $timeout.cancel($scope.struct.pdc_update_timeout)

    update_pdc = () ->
        if not $scope.struct.pdc_updating
            stop_pdc_update()
            $scope.struct.pdc_updating = true
            hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.device_tree.get_device_trace($scope.struct.devices))
            $scope.struct.device_tree.enrich_devices(hs, ["package_info", "variable_info"], true).then(
                (done) ->
                    for dev in $scope.struct.devices
                        # set variables
                        dev.$$package_client_version = "?.?"
                        dev.$$package_client_latest_contact = "never"
                        for d_var in dev.device_variable_set
                            if d_var.name == "package_server_last_contact"
                                dev.$$package_client_latest_contact = moment(d_var.val_date).fromNow(true)
                            else if d_var.name == "package_client_version"
                                dev.$$package_client_version = d_var.val_str
                    $scope.struct.pdc_struct.feed()
                    $scope.struct.pdc_timeout = $timeout(
                        () ->
                            update_pdc()
                        10000
                    )
                    # clear flag
                    $scope.struct.pdc_updating = false
            )

    # check for package list change

    $rootScope.$on(ICSW_SIGNALS("ICSW_PACKAGE_INSTALL_LIST_CHANGED"), () ->
        console.log "pl changed"
    )
    
    # manual resolving because icsw-sel-man is not working due to isolated scope

    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"), (event) ->
        # console.log "icsw_overview_emit_selection received"
        if $scope.struct.device_tree?
            $scope.new_devsel()
        else
            $scope.device_info_str = "loading devices from server"
            icswDeviceTreeService.load($scope.$id).then(
                (data) ->
                    $scope.struct.device_tree = data
                    $scope.device_info_str = ""
                    $scope.new_devsel()
            )
    )

    icswActiveSelectionService.register_receiver()

    $scope.new_devsel = () ->
        devs = ($scope.struct.device_tree.all_lut[pk] for pk in icswActiveSelectionService.current().tot_dev_sel when $scope.struct.device_tree.all_lut[pk]?)
        # console.log "nds", devs
        $scope.struct.device_info_str = "Loading devices"
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_info_str = ""
                $scope.struct.device_tree = data[0]
                $scope.struct.devices.length = 0
                for entry in devs
                    if not entry.is_meta_device
                        $scope.struct.devices.push(entry)
                if $scope.struct.package_tree_loaded
                    init_pdc()
        )

    # delete package

    $scope.delete = ($event, pack) ->
        icswToolsSimpleModalService("Really delete package '#{pack.name}' ?").then(
            (del_yes) ->
                blockUI.start()
                $scope.struct.package_tree.delete_package(pack).then(
                    (ok) ->
                        blockUI.stop()
                        $scope.struct.pdc_struct.package_deleted(pack)
                        console.log "deleted package"
                    (notok) ->
                        blockUI.stop()
                )
        )

    # selection functions

    $scope.change_package_sel = ($event, cur_p, t_state) ->
        $scope.struct.pdc_struct.change_package_sel(cur_p, t_state)
        
    $scope.change_device_sel = ($event, cur_d, t_state) ->
        $scope.struct.pdc_struct.change_device_sel(cur_d, t_state)

    # attach / detach calls

    $scope.attach = ($event, pack) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_ADD_PACKAGE
            data: {
                add_list: angular.toJson($scope.struct.pdc_struct.get_attach_list(pack))
            }
        ).then(
            (xml) ->
                blockUI.stop()
                update_pdc()
            (not_ok) ->
                blockUI.stop()
                update_pdc()
        )

    $scope.remove = ($event, pack) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_REMOVE_PACKAGE
            data: {
                remove_list: angular.toJson($scope.struct.pdc_struct.get_remove_list(pack))
            }
        ).then(
            (xml) ->
                blockUI.stop()
                update_pdc()
            (not_ok) ->
                blockUI.stop()
                update_pdc()
        )

    # helper functions

    $scope.send_sync = ($event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_REPO_OVERVIEW
            data: {
                mode: "new_config"
                pks: (_dev.idx for _dev in $scope.struct.devices)
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )

    $scope.send_clear_caches = ($event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.PACK_REPO_OVERVIEW
            data: {
                mode: "clear_caches"
                pks: (_dev.idx for _dev in $scope.struct.devices)
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )

    # PDC modify
    $scope.modify = ($event) ->
        stop_pdc_update()
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = {
            target_state: null
            nodeps_flag: null
            force_flag: null
            kernel_dep: null
            image_dep: null
            kernel_change: false
            image_change: false
            kernel_list: []
            image_list: []
        }
        sub_scope.target_states = [
            {state : "keep", info: "keep"}
            {state : "install", info: "install"}
            {state : "upgrade", info: "upgrade"}
            {state : "erase", info: "erase"}
        ]
        sub_scope.flag_states = [
            {idx: 1, info: "set"}
            {idx: 0, info: "clear"}
        ]
        sub_scope.dep_states = [
            {idx: 1, info: "enable"}
            {idx: 0, info: "disable"}
        ]
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.package.action.form"))(sub_scope)
                title: "Set PDC settings"
                ok_label: "save"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        # change selected pdcs
                        change_dict = {
                            edit_obj: sub_scope.edit_obj
                            pdc_list: []
                        }
                        for pdc in $scope.struct.pdc_struct.selected_pdcs
                            change_dict["pdc_list"].push(pdc.idx)
                            if sub_scope.edit_obj.target_state
                                pdc.target_state = sub_scope.edit_obj.target_state
                            for f_name in ["nodeps_flag", "force_flag", "image_dep", "kernel_dep"]
                                if sub_scope.edit_obj[f_name]
                                    pdc[f_name] = if parseInt(sub_scope.edit_obj[f_name]) then true else false
                            #if $scope.edit_obj.kernel_change
                            #    pdc["kernel_list"] = (_v for _v in $scope.edit_obj.kernel_list)
                            #if $scope.edit_obj.image_change
                            #    pdc["image_list"] = (_v for _v in $scope.edit_obj.image_list)
                        #console.log change_dict
                        icswSimpleAjaxCall(
                            url: ICSW_URLS.PACK_CHANGE_PDC
                            data: {
                                change_dict: angular.toJson(change_dict)
                            }
                        ).then(
                            (xml) ->
                                d.resolve("updated")
                            (not_ok) ->
                                d.resolve("not updates")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "finish"
                sub_scope.$destroy()
                # force reload of pdc
                update_pdc()
        )
]).directive("icswPdcState",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        scope:
            mode: "=mode"
            pdc: "=icswPdcState"
        replace: true
        link: (scope, iElement, iAttrs) ->
            scope.mode = "a"
            scope.change_sel = () ->
                scope.pdc.change_selection(0)
            _draw = () ->
                iElement.children().remove()
                if scope.mode == "a"
                    new_el = $compile($templateCache.get("icsw.package.install.pdc.state"))
                else #  if scope.mode == "v"
                    new_el = $compile($templateCache.get("icsw.package.install.pdc.version"))
                iElement.append(new_el(scope))
            # scope.$watch("mode", () ->
            #    scope.draw()
            # )

            _draw()
    }
])
