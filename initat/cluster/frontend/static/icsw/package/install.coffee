
package_module = angular.module(
    "icsw.package.install",
    ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
    "icsw.tools.table", ]
).service("icswPackageInstallRepositoryService", ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    return {
        rest_url            : ICSW_URLS.REST_PACKAGE_REPO_LIST
        delete_confirm_str  : (obj) -> return "Really delete Package repository '#{obj.name}' ?"
        get_service_name : ($scope, repo) ->
            if repo.service
                return (entry for entry in $scope.rest_data["service"] when entry.idx == repo.service)[0].name
            else
                return "---"
        toggle : (obj) ->
            obj.publish_to_nodes = if obj.publish_to_nodes then false else true
            obj.put()
        filter_repo : (obj, $scope) ->
            _show = true
            if $scope.show_enabled and not obj.enabled
                _show = false
            if $scope.show_published and not obj.publish_to_nodes
                _show = false
            return _show
    }
]).service("icswPackageInstallSearchService", ["Restangular", "ICSW_URLS", "icswCallAjaxService", (Restangular, ICSW_URLS, icswCallAjaxService) ->
    user_rest = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1)).getList().$object
    return {
        user_rest           : user_rest
        rest_url            : ICSW_URLS.REST_PACKAGE_SEARCH_LIST
        edit_template       : "package.search.form"
        delete_confirm_str  : (obj) -> return "Really delete Package search '#{obj.name}' ?"
        entries_filter      : {deleted : false}
        post_delete : (scope, del_obj) ->
            scope.clear_active_search(del_obj)
        object_modified : (edit_obj, srv_data, $scope) ->
            icswCallAjaxService
                url     : ICSW_URLS.PACK_RETRY_SEARCH
                data    : {
                    "pk" : edit_obj.idx
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    $scope.reload()
        init_fn: (scope) ->
            scope.init_search(scope)
    }
]).service("icswPackageInstallPackageListService", ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url            : ICSW_URLS.REST_PACKAGE_LIST
        #edit_template       : "package_search.html"
        delete_confirm_str  : (obj) -> return "Really delete Package '#{obj.name}-#{obj.version}' ?"
        init_fn: (scope) ->
            scope.init_package_list(scope)
        after_reload: (scope) ->
            scope.salt_package_list()
        toggle_grid_style : ($scope) ->
            $scope.dp_style = !$scope.dp_style
        get_grid_style : ($scope) ->
            return if $scope.dp_style then "Dev/PDC grid" else "PDC/Dev grid"
    }
]).service("icswPackageInstallSearchResultService", ["ICSW_URLS", (ICSW_URLS)->
    return {
        edit_template       : "package_search.html"
        delete_confirm_str  : (obj) -> return "Really delete Package search result '#{obj.name}-#{obj.version}' ?"
    }
]).controller("icswPackageInstallCtrl", ["$scope", "$injector", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "sharedDataSource", "$q", "$timeout", "blockUI", "icswTools", "ICSW_URLS", "$window", "icswCallAjaxService",
    ($scope, $injector, $compile, $filter, $templateCache, Restangular, restDataSource, sharedDataSource, $q, $timeout, blockUI, icswTools, ICSW_URLS, $window, icswCallAjaxService) ->
        # flags
        $scope.show_enabled_repos = true
        $scope.show_published_repos = true
        # lists
        $scope.entries =
            "repos" : []
            "searches": []
            "searchresults": []
            # installable packages
            "packages" : []
        # active search
        $scope.active_search = undefined
        # devices
        $scope.devices = []
        # image / kernel list
        $scope.srv_image_list = []
        $scope.srv_kernel_list = []
        $scope.package_filter = ""
        # is mode
        $scope.is_mode = "a"
        # init state dict
        $scope.state_dict = {}
        $scope.selected_pdcs = {}
        $scope.shared_data = sharedDataSource.data
        $scope.device_tree_url = ICSW_URLS.REST_DEVICE_TREE_LIST
        wait_list = restDataSource.add_sources([
            [$scope.device_tree_url, {"ignore_meta_devices" : true}]
            [ICSW_URLS.REST_IMAGE_LIST, {}]
            [ICSW_URLS.REST_KERNEL_LIST, {}]
        ])
        $scope.inst_rest_data = {}
        $q.all(wait_list).then((data) ->
            $scope.set_devices(data[0])
            $scope.srv_image_list = data[1]
            $scope.srv_kernel_list = data[2]
        )
        $scope.rescan_repos = (reload_func) ->
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.PACK_REPO_OVERVIEW
                data    : {
                    "mode" : "rescan_repos"
                }
                success : (xml) ->
                    blockUI.stop()
                    if parse_xml_response(xml)
                        reload_func()
        $scope.clear_active_search = (del_obj) ->
            if $scope.active_search and $scope.active_search.idx == del_obj.idx
                $scope.active_search = undefined
        $scope.retry_search = (obj, reload_func) ->
            if $scope.active_search?
                $scope.active_search = undefined
            icswCallAjaxService
                url     : ICSW_URLS.PACK_RETRY_SEARCH
                data    : {
                    "pk" : obj.idx
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    reload_func()
        $scope.reload_searches = () ->
            # check all search states
            if (obj.current_state for obj in $scope.entries.searches when obj.current_state != "done").length and not $scope.modal_active
                $scope.search_scope.reload()
            $timeout($scope.reload_searches, 5000)
        $scope.show_search_result = (obj) ->
            $scope.active_search = obj
            if $scope.active_search?
                blockUI.start()
                Restangular.all(ICSW_URLS.REST_PACKAGE_SEARCH_RESULT_LIST.slice(1)).getList({"package_search" : $scope.active_search.idx}).then((new_data) ->
                    blockUI.stop()
                    $scope.entries.searchresults = new_data
                    for entry in $scope.entries
                        entry.target_repo = 0
                )
            else
                $scope.entries.searchresults = []
        $scope.create_search = () ->
            if $scope.search_scope.search_string
                Restangular.all(ICSW_URLS.REST_PACKAGE_SEARCH_LIST.slice(1)).post({"search_string" : $scope.search_scope.search_string, "user" : $window.CURRENT_USER.idx}).then((data) ->
                    icswCallAjaxService
                        url     : ICSW_URLS.PACK_REPO_OVERVIEW
                        data    : {
                            "mode" : "reload_searches"
                        }
                        success : (xml) ->
                            parse_xml_response(xml)
                            $scope.search_scope.reload()
                    $scope.search_scope.search_string = ""
                )
        $scope.init_search = (local_scope) ->
            local_scope.search_string = ""
            $scope.search_scope = local_scope
            $timeout($scope.reload_searches, 5000)
        $scope.take_search_result = (obj, exact) ->
            obj.copied = 1
            icswCallAjaxService
                url     : ICSW_URLS.PACK_USE_PACKAGE
                data    : {
                    "pk"          : obj.idx
                    "exact"       : if exact then 1 else 0
                    "target_repo" : if obj.target_repo then obj.target_repo else obj.package_repo
                }
                success : (xml) ->
                    if parse_xml_response(xml)
                        # reload package list
                        $scope.package_list_scope.reload()
                    else
                        obj.copied = 0
        $scope.show_repo = (obj) ->
            if obj.target_repo
                return (entry for entry in $scope.entries.repos when obj.target_repo == entry.idx)[0].name
            else
                return "ignore"
        $scope.init_package_list = (scope) ->
            # true for device / pdc, false for pdc / device style
            $scope.dp_style = true
            $scope.package_list_scope = scope
        $scope.sync_repos = () ->
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.PACK_REPO_OVERVIEW
                data    : {
                    "mode" : "sync_repos"
                }
                success : (xml) ->
                    blockUI.stop()
                    parse_xml_response(xml)
        $scope.clear_caches = () ->
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.PACK_REPO_OVERVIEW
                data    : {
                    "mode" : "clear_caches"
                }
                success : (xml) ->
                    blockUI.stop()
                    parse_xml_response(xml)
        #$scope.load_devices = (url, options) ->
        #    return Restangular.all(url.slice(1)).getList(options)
        $scope.reload_devices = () ->
            blockUI.start()
            restDataSource.reload([$scope.device_tree_url, {"ignore_meta_devices" : true}]).then((data) ->
                $scope.set_devices(data)
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
                            $scope.device_lut[dev.idx].latest_contact = dev.latest_contact
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
            icswCallAjaxService
                url     : ICSW_URLS.PACK_ADD_PACKAGE
                data    : {
                    "add_list" : angular.toJson(attach_list)
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    new_pdcs = angular.fromJson($(xml).find("value[name='result']").text())
                    for new_pdc in new_pdcs
                        new_pdc.selected = true
                        $scope.state_dict[new_pdc.device][new_pdc.package] = new_pdc
                    $scope.update_selected_pdcs()
                    $scope.$apply()
        $scope.remove = (obj) ->
            remove_list = []
            for dev_idx, dev_dict of $scope.state_dict
                for pack_idx, pdc of dev_dict
                    if pdc.selected and parseInt(pack_idx) == obj.idx and pdc.idx
                        remove_list.push(pdc.idx)
                        delete $scope.selected_pdcs[pdc.idx]
                        delete pdc.idx
                        #pdc.remove_pdc()
            icswCallAjaxService
                url     : ICSW_URLS.PACK_REMOVE_PACKAGE
                data    : {
                    "remove_list" : angular.toJson(remove_list)
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    # just to be sure
                    $scope.update_selected_pdcs()
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
            $.simplemodal.close()
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
            icswCallAjaxService
                url     : ICSW_URLS.PACK_CHANGE_PDC
                data    : {
                    "change_dict" : angular.toJson(change_dict)
                }
                success : (xml) ->
                    parse_xml_response(xml)
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
            $scope.action_div.simplemodal
                position     : [event.pageY, event.pageX]
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) => 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                onClose: (dialog) =>
                    $.simplemodal.close()
        $scope.get_td_class = (dev_idx, pack_idx) ->
            pdc = $scope.state_dict[dev_idx][pack_idx]
            if pdc and pdc.idx
                _i = pdc.installed
                _t = pdc.target_state
                _k = "#{_i}.#{_t}"
                if _k in ["y.keep", "y.upgrade", "y.install"
                  "n.erase", "n.keep"]
                    return "text-center success"
                else
                    return "text-center danger"
            else
                return "text-center"
        $scope.send_sync = (event) ->
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.PACK_REPO_OVERVIEW
                data    : {
                    "mode" : "new_config"
                }
                success : (xml) ->
                    blockUI.stop()
                    parse_xml_response(xml)
        $scope.send_clear_caches = (event) ->
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.PACK_REPO_OVERVIEW
                data    : {
                    "mode" : "clear_caches"
                }
                success : (xml) ->
                    blockUI.stop()
                    parse_xml_response(xml)
        $scope.latest_contact = (dev) ->
            if dev.latest_contact
                return moment.unix(dev.latest_contact).fromNow(true)
            else
                return "never"
]).directive("icswPackageInstallOverview", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.overview")
        link : (scope, el, attrs) ->
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    # args is not needed here, fix controller
                    scope.reload_devices(args[1])
                )
    }
).directive("icswPackageInstallRepositoryRow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.repo.row")
    }
).directive("icswPackageInstallRepositoryHead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.repo.head")
    }
).directive("icswPackageInstallSearchRow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.search.row")
    }
).directive("icswPackageInstallSearchHead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.search.head")
    }
).directive("icswPackageInstallSearchResultHead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.search.result.head")
    }
).directive("icswPackageInstallSearchResultRow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.search.result.row")
    }
).directive("icswPackageInstallPackageHead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.list.head")
    }
).directive("icswPackageInstallPackageRow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.package.install.package.list.row")
    }
).directive("istate", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        scope:
            pdc          : "=pdc"
            selected_pdcs: "=pdcs"
            parent       : "=parent"
            mode         : "=mode"
        replace  : true
        transclude : true
        compile : (tElement, tAttrs) ->
            #tElement.append($templateCache.get("pdc_state.html"))
            return (scope, iElement, iAttrs) ->
                #console.log "link", scope, iElement, iAttrs
                scope.show_pdc = () ->
                    #console.log scope.pdc
                    if scope.pdc and scope.pdc.idx
                        return true
                    else
                        return false
                scope.get_btn_class = () ->
                    if scope.pdc and scope.pdc.idx
                        cur = scope.pdc
                        if cur.installed == "y"
                            return "btn-success"
                        else if cur.installed == "u"
                            return "btn-warning"
                        else if cur.installed == "n"
                            return "btn-danger"
                        else
                            return "btn-active"
                    else
                        return ""
                scope.get_glyph_class = (val) ->
                    if val
                        if val == "keep"
                            return "glyphicon glyphicon-minus"
                        else if val == "install"
                            return "glyphicon glyphicon-ok"
                        else if val == "upgrade"
                            return "glyphicon glyphicon-arrow-up"
                        else if val == "erase"
                            return "glyphicon glyphicon-remove"
                        else
                            # something strange ...
                            return "glyphicon glyphicon-asterisk"
                    else
                        return "glyphicon"
                scope.change_sel = (pdc) ->
                    pdc.selected = !pdc.selected
                    if pdc.idx
                        if pdc.selected and pdc.idx not of scope.selected_pdcs
                            scope.selected_pdcs[pdc.idx] = pdc
                        else if not pdc.selected and pdc.idx of scope.selected_pdcs
                            delete scope.selected_pdcs[pdc.idx]
                scope.get_tooltip = () ->
                    if scope.pdc and scope.pdc.idx
                        pdc = scope.pdc
                        t_field = ["target state : #{pdc.target_state}"]
                        if pdc.installed == "n"
                            t_field.push("<br>installed: no")
                        else if pdc.installed == "u"
                            t_field.push("<br>installed: unknown")
                        else if pdc.installed == "y"
                            t_field.push("<br>installed: yes")
                            if pdc.install_time
                                t_field.push("<br>installtime: " + moment.unix(pdc.install_time).format("ddd, D. MMM YYYY HH:mm:ss"))
                            else
                                t_field.push("<br>installtime: unknown")
                            if pdc.installed_name
                                inst_name = scope.get_installed_version()
                                t_field.push("<br>installed: #{inst_name}")
                        else
                            t_field.push("<br>unknown install state '#{pdc.installed}")
                        if pdc.kernel_dep
                            t_field.push("<hr>")
                            t_field.push("kernel dependencies enabled (#{pdc.kernel_list.length})")
                            for _idx in pdc.kernel_list
                                t_field.push("<br>" + (_k.name for _k in scope.parent.kernel_list when _k.idx == _idx)[0])
                        if pdc.image_dep
                            t_field.push("<hr>")
                            t_field.push("image dependencies enabled (#{pdc.image_list.length})")
                            for _idx in pdc.image_list
                                t_field.push("<br>" + (_i.name for _i in scope.parent.image_list when _i.idx == _idx)[0])
                        return "<div class='text-left'>" + t_field.join("") + "<div>"
                    else
                        return ""
                scope.get_installed_version = () ->
                    if scope.pdc and scope.pdc.idx
                        pdc = scope.pdc
                        if pdc.installed == "y" and pdc.installed_name
                            inst_name = pdc.installed_name
                            if pdc.installed_version
                                inst_name = "#{inst_name}-#{pdc.installed_version}"
                            else
                                inst_name = "#{inst_name}-?"
                            if pdc.installed_release
                                inst_name = "#{inst_name}-#{pdc.installed_release}"
                            else
                                inst_name = "#{inst_name}-?"
                            return inst_name
                        else
                            return "---"
                    else
                        return "---"
                scope.draw = () ->
                    iElement.children().remove()
                    if scope.mode == "a"
                        new_el = $compile($templateCache.get("icsw.package.install.pdc.state"))
                    else if scope.mode == "v"
                        new_el = $compile($templateCache.get("icsw.package.install.pdc.version"))
                    iElement.append(new_el(scope))
                scope.$watch("mode", () ->
                    scope.draw()
                )
                scope.draw()
    }
)
