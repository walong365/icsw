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
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.packageinstall", {
            url: "/packageinstall"
            template: "<icsw-package-install-overview ng-cloack/>"
            data:
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
            @update(list)

        update: (in_list) =>
            @list.length = 0
            for entry in in_list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")

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
    "Restangular", "restDataSource", "$q", "$timeout", "blockUI", "icswTools", "icswDeviceTreeService",
    "ICSW_URLS", "icswUserService", "icswSimpleAjaxCall", "icswPackageInstallRepositoryTreeService",
(
    $scope, $injector, $compile, $filter, $templateCache, icswToolsSimpleModalService,
    Restangular, restDataSource, $q, $timeout, blockUI, icswTools, icswDeviceTreeService,
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
    $scope.package_filter = ""
    # is mode
    $scope.is_mode = "a"
    # init state dict
    $scope.state_dict = {}
    $scope.selected_pdcs = {}

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

    $scope.reload_state = () ->
        update_pdc = (srv_pdc, client_pdc) ->
            for attr_name in [
                "installed", "package", "response_str", "response_type", "target_state", "install_time",
                "installed_name", "installed_version", "installed_release"
            ]
                client_pdc[attr_name] = srv_pdc[attr_name]

        Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList({"package_state" : true, "ignore_meta_devices" : true}).then(
            (data) ->
                for dev in data
                    # check if device is still in lut
                    if dev.idx of $scope.device_lut
                        $scope.device_lut[dev.idx].client_version = dev.client_version
                        for pdc in dev.package_device_connection_set
                            cur_pdc = $scope.state_dict[dev.idx][pdc.package]
                            # cur_pdc can be undefined, FIXME
                            if cur_pdc and cur_pdc.idx
                                # update only relevant fields
                                update_pdc(pdc, cur_pdc)
                            else
                                # use pdc from server
                                $scope.state_dict[dev.idx][pdc.package] = pdc
                $scope.reload_promise = $timeout($scope.reload_state, 10000)
        )

    $scope.salt_package_list = () ->
        # init dummy pdc entries when new packages are added / removed to / from the entries list
        for pack in $scope.entries.packages
            for dev_idx of $scope.device_lut
                dev_idx = parseInt(dev_idx)
                # dummy entry for newly added packages
                $scope.state_dict[dev_idx][pack.idx]  = {"device" : dev_idx, "package" : pack.idx}
    $scope.change_package_sel = (cur_p, t_state) ->
        for d_key, d_value of $scope.state_dict
            csd = d_value[cur_p.idx]
            $scope.change_sel(csd, t_state)
    $scope.change_device_sel = (cur_d, t_state) ->
        for d_key, d_value of $scope.state_dict
            if parseInt(d_key) == cur_d.idx
               for p_key, csd of d_value
                    $scope.change_sel(csd, t_state)
    $scope.change_sel = (csd, t_state) ->
        if t_state == undefined
            t_state = if csd.selected then 1 else -1
        if t_state == 1
            csd.selected = true
        else if t_state == -1
            csd.selected = false
        else
            csd.selected = not csd.selected
        if csd.idx
            if csd.selected and csd.idx not of $scope.selected_pdcs
                $scope.selected_pdcs[csd.idx] = csd
            else if not csd.selected and csd.idx of $scope.selected_pdcs
                delete $scope.selected_pdcs[csd.idx]
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
    $scope.update_selected_pdcs = () ->
        # after remove / attach
        for d_key, d_value of $scope.state_dict
            for p_key, pdc of d_value
                if pdc.idx
                   if pdc.selected and pdc.idx not of $scope.selected_pdcs
                       $scope.selected_pdcs[pdc.idx] = pdc
                   else if not pdc.selected and pdc.idx of $scope.selected_pdcs
                       delete $scope.selected_pdcs[pdc.idx]
    $scope.$watch("package_filter", (new_filter) ->
        for d_key, d_value of $scope.state_dict
            for p_key, pdc of d_value
                #console.log $scope.package_lut[pdc.package]
                if (not $filter("filter")([$scope.package_lut[pdc.package]], {"name" : $scope.package_filter}).length) and pdc.selected
                    pdc.selected = false
                    delete $scope.selected_pdcs[pdc.idx]
    )
    $scope.selected_pdcs_length = () ->
        sel = 0
        for key, value of $scope.selected_pdcs
            sel += 1
        return sel

    $scope.set_devices = (data) ->
        if $scope.reload_promise
            $timeout.cancel($scope.reload_promise)
        $scope.devices = data
        # device lookup table
        $scope.device_lut = icswTools.build_lut($scope.devices)
        # package lut
        $scope.package_lut = icswTools.build_lut($scope.entries.packages)
        #console.log $scope.entries.length, $scope.devices.length
        for dev in $scope.devices
            dev.latest_contact = 0
            dev.client_version = "?.?"
            if not (dev.idx of $scope.state_dict)
                $scope.state_dict[dev.idx] = {}
            dev_dict = $scope.state_dict[dev.idx]
            for pack in $scope.entries.packages
                if not (pack.idx of dev_dict)
                    dev_dict[pack.idx] = {"device" : dev.idx, "package" : pack.idx}
        $scope.salt_package_list()
        $scope.reload_state()
    # attach / detach calls
    $scope.attach = (obj) ->
        attach_list = []
        for dev_idx, dev_dict of $scope.state_dict
            for pack_idx, pdc of dev_dict
                if pdc.selected and parseInt(pack_idx) == obj.idx
                    attach_list.push([parseInt(dev_idx), obj.idx])
        icswSimpleAjaxCall(
            url     : ICSW_URLS.PACK_ADD_PACKAGE
            data    : {
                "add_list" : angular.toJson(attach_list)
            }
        ).then(
            (xml) ->
                new_pdcs = angular.fromJson($(xml).find("value[name='result']").text())
                for new_pdc in new_pdcs
                    new_pdc.selected = true
                    $scope.state_dict[new_pdc.device][new_pdc.package] = new_pdc
                $scope.update_selected_pdcs()
        )
    $scope.remove = (obj) ->
        remove_list = []
        for dev_idx, dev_dict of $scope.state_dict
            for pack_idx, pdc of dev_dict
                if pdc.selected and parseInt(pack_idx) == obj.idx and pdc.idx
                    remove_list.push(pdc.idx)
                    delete $scope.selected_pdcs[pdc.idx]
                    delete pdc.idx
                    #pdc.remove_pdc()
        icswSimpleAjaxCall(
            url     : ICSW_URLS.PACK_REMOVE_PACKAGE
            data    : {
                "remove_list" : angular.toJson(remove_list)
            }
        ).then(
            (xml) ->
                $scope.update_selected_pdcs()
            (xml) ->
                $scope.update_selected_pdcs()
        )
    $scope.target_states = [
        {"state" : "keep", "info": "keep"}
        {"state" : "install", "info": "install"}
        {"state" : "upgrade", "info": "upgrade"}
        {"state" : "erase", "info": "erase"}
    ]
    $scope.flag_states = [
        {"idx": "1", "info": "set"}
        {"idx": "0", "info": "clear"}
    ]
    $scope.dep_states = [
        {"idx": "1", "info": "enable"}
        {"idx": "0", "info": "disable"}
    ]
    $scope.modify = () ->
        $scope.my_modal.close()
        # change selected pdcs
        change_dict = {"edit_obj" : $scope.edit_obj, "pdc_list" : []}
        for pdc_idx, pdc of $scope.selected_pdcs
            change_dict["pdc_list"].push(parseInt(pdc_idx))
            if $scope.edit_obj["target_state"]
                pdc.target_state = $scope.edit_obj["target_state"]
            for f_name in ["nodeps_flag", "force_flag", "image_dep", "kernel_dep"]
                if $scope.edit_obj[f_name]
                    pdc[f_name] = if parseInt($scope.edit_obj[f_name]) then true else false
            if $scope.edit_obj.kernel_change
                pdc["kernel_list"] = (_v for _v in $scope.edit_obj.kernel_list)
            if $scope.edit_obj.image_change
                pdc["image_list"] = (_v for _v in $scope.edit_obj.image_list)
        #console.log change_dict
        icswSimpleAjaxCall(
            url     : ICSW_URLS.PACK_CHANGE_PDC
            data    : {
                "change_dict" : angular.toJson(change_dict)
            }
        ).then((xml) ->
        )
    $scope.action = (event) ->
        $scope.edit_obj = {
            "target_state" : ""
            "nodeps_flag" : ""
            "force_flag" : ""
            "kernel_dep" : ""
            "image_dep" : ""
            "kernel_change" : false
            "image_change" : false
            "kernel_list" : []
            "image_list" : []
        }
        $scope.action_div = $compile($templateCache.get("package.action.form"))($scope)
        $scope.my_modal = BootstrapDialog.show
            message: $scope.action_div
            draggable: true
            size: BootstrapDialog.SIZE_WIDE
            closable: true
            closeByBackdrop: false
            onshow: (modal) =>
                height = $(window).height() - 100
                modal.getModal().find(".modal-body").css("max-height", height)
    $scope.send_sync = (event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url     : ICSW_URLS.PACK_REPO_OVERVIEW
            data    : {
                "mode" : "new_config"
                "pks": (_dev.idx for _dev in $scope.devices)
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )
    $scope.send_clear_caches = (event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url     : ICSW_URLS.PACK_REPO_OVERVIEW
            data    : {
                "mode" : "clear_caches"
                "pks": (_dev.idx for _dev in $scope.devices)
            }
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )
]).service("icswPackageInstallPackageListService", ["ICSW_URLS", (ICSW_URLS) ->
    _scope = undefined
    return {
        rest_url            : ICSW_URLS.REST_PACKAGE_LIST
        delete_confirm_str  : (obj) -> return "Really delete Package '#{obj.name}-#{obj.version}' ?"
        init_fn: (scope) ->
            scope.init_package_list(scope)
        after_reload: (scope) ->
            scope.salt_package_list()
        toggle_grid_style : ($scope) ->
            $scope.dp_style = !$scope.dp_style
        get_grid_style : ($scope) ->
            return if $scope.dp_style then "Dev/PDC grid" else "PDC/Dev grid"
        reload: (scope) ->
            _scope.reload()
        init_fn: (scope) ->
            _scope = scope
    }
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
]).directive("icswPackageInstallPackageHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.list.head")
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
    "blockUI", "icswPackageInstallPackageListService", "$rootScope", "ICSW_SIGNALS",
    "$timeout", "$q", "icswPackageInstallSearchTreeService",
    "icswToolsSimpleModalService", "icswComplexModalService", "$compile", "toaster",
(
    $scope, $templateCache, icswUserService, ICSW_URLS, icswSimpleAjaxCall, Restangular,
    blockUI, icswPackageInstallPackageListService, $rootScope, ICSW_SIGNALS,
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
        ]
        if reload
            _w_list.push(icswPackageInstallSearchTreeService.reload($scope.$id))
        else
            _w_list.push(icswPackageInstallSearchTreeService.load($scope.$id))
        $q.all(_w_list).then(
            (data) ->
                $scope.struct.user = data[0]
                $scope.struct.search_tree = data[1]
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
        #link: (scope, element, attrs) ->
        #    console.log "Link inst"
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

        toggle_selection: () =>
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


            if @installed == "y" and @installed_name
                inst_name = @installed_name
                if @installed_version
                    inst_name = "#{inst_name}-#{@installed_version}"
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
            for dev in @devices
                for idx, pdc of @lut[dev.idx]
                    if pdc.selected
                        @selected_pdcs.push(pdc)

]).controller("icswPackageInstallDeviceCtrl",
[
    "$scope", "icswPackageInstallTreeService", "$q", "icswDeviceTreeService", "blockUI",
    "icswUserService", "$rootScope", "ICSW_SIGNALS", "icswActiveSelectionService",
    "icswPackageInstallRepositoryTreeService", "icswToolsSimpleModalService", "$timeout",
    "icswDeviceTreeHelperService", "icswPDCStruct",
(
    $scope, icswPackageInstallTreeService, $q, icswDeviceTreeService, blockUI,
    icswUserService, $rootScope, ICSW_SIGNALS, icswActiveSelectionService,
    icswPackageInstallRepositoryTreeService, icswToolsSimpleModalService, $timeout,
    icswDeviceTreeHelperService, icswPDCStruct,
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
                if $scope.struct.device_tree_loaded
                    init_pdc()
        )


    load(false)

    $scope.$on("$destroy", () ->
        if $scope.struct.pdc_udpate_timeout
            $timeout.cancel($scope.struct.pdc_update_timeout)
    )

    # pdc functions
    init_pdc = () ->
        # init new pdc structure
        if $scope.struct.pdc_udpate_timeout
            $timeout.cancel($scope.struct.pdc_update_timeout)
        new_pdc = new icswPDCStruct($scope.struct.devices, $scope.struct.package_tree)
        $scope.struct.pdc_struct = new_pdc
        update_pdc()
        
    update_pdc = () ->
        if not $scope.struct.pdc_updating
            if $scope.struct.pdc_udpate_timeout
                $timeout.cancel($scope.struct.pdc_update_timeout)
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
        console.log "nds", devs
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
                        console.log "deleted package"
                    (notok) ->
                        blockUI.stop()
                )
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
            scope.change_sel = (pdc) ->
                pdc.toggle_selection()
                # pdc.selected = !pdc.selected
                #if pdc.idx
                ##    if pdc.selected and pdc.idx not of scope.selected_pdcs
                #        scope.selected_pdcs[pdc.idx] = pdc
                #    else if not pdc.selected and pdc.idx of scope.selected_pdcs
                #        delete scope.selected_pdcs[pdc.idx]
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
