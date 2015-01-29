{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

package_module = angular.module("icsw.package", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"])

angular_add_simple_list_controller(
    package_module,
    "package_repo_base",
    {
        rest_url            : "{% url 'rest:package_repo_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Package repository '#{obj.name}' ?"
        template_cache_list : ["package_repo_row.html", "package_repo_head.html"]
        rest_map            : [
            {"short" : "service", "url" : "{% url 'rest:package_service_list' %}"}
        ]
        init_fn : ($scope, timeout) ->
            $scope.show_enabled = false
            $scope.show_published = false
        fn :
            get_service_name : ($scope, repo) ->
                if repo.service
                    return (entry for entry in $scope.rest_data["service"] when entry.idx == repo.service)[0].name
                else
                    return "---"
            toggle : (obj) ->
                obj.publish_to_nodes = if obj.publish_to_nodes then false else true
                obj.put()
            rescan : ($scope) ->
                # $.blockUI()
                call_ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "rescan_repos"
                    }
                    success : (xml) ->
                        # $.unblockUI()
                        if parse_xml_response(xml)
                            $scope.reload()
            sync : () ->
                # $.blockUI()
                call_ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "sync_repos"
                    }
                    success : (xml) ->
                        # $.unblockUI()
                        parse_xml_response(xml)
            clearcaches : () ->
                # $.blockUI()
                call_ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "clear_caches"
                    }
                    success : (xml) ->
                        # $.unblockUI()
                        parse_xml_response(xml)
            filter_repo : (obj, $scope) ->
                _show = true
                if $scope.show_enabled and not obj.enabled
                    _show = false
                if $scope.show_published and not obj.publish_to_nodes
                    _show = false
                return _show
    }
)

angular_add_simple_list_controller(
    package_module,
    "package_search_base",
    {
        rest_url            : "{% url 'rest:package_search_list' %}"
        edit_template       : "package_search.html"
        rest_map            : [
            {"short" : "user", "url" : "{% url 'rest:user_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Package search '#{obj.name}' ?"
        template_cache_list : ["package_search_row.html", "package_search_head.html"]
        entries_filter      : {deleted : false}
        post_delete : ($scope, del_obj) ->
            if $scope.shared_data.result_obj and $scope.shared_data.result_obj.idx == del_obj.idx
                $scope.shared_data.result_obj = undefined
        fn:
            object_modified : (edit_obj, srv_data, $scope) ->
                call_ajax
                    url     : "{% url 'pack:retry_search' %}"
                    data    : {
                        "pk" : edit_obj.idx
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
                        $scope.reload()
            retry : ($scope, obj) ->
                if $scope.shared_data.result_obj and $scope.shared_data.result_obj.idx == obj.idx
                    $scope.shared_data.result_obj = undefined
                call_ajax
                    url     : "{% url 'pack:retry_search' %}"
                    data    : {
                        "pk" : obj.idx
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
                        $scope.reload()
            show : ($scope, obj) ->
                $scope.shared_data.result_obj = obj
            create_search : ($scope) ->
                if $scope.search_string
                    $scope.Restangular.all("{% url 'rest:package_search_list' %}".slice(1)).post({"search_string" : $scope.search_string, "user" : {{ request.user.pk }}}).then((data) ->
                        call_ajax
                            url     : "{% url 'pack:repo_overview' %}"
                            data    : {
                                "mode" : "reload_searches"
                            }
                            success : (xml) ->
                                parse_xml_response(xml)
                                $scope.reload()
                        $scope.search_string = ""
                    )
        init_fn:
            ($scope, $timeout, Restangular) ->
                $scope.Restangular = Restangular
                $scope.search_string = ""
                $scope.$timeout = $timeout
                $scope.reload_searches = () ->
                    # check all search states
                    if (obj.current_state for obj in $scope.entries when obj.current_state != "done").length and not $scope.modal_active
                        $scope.reload()
                    $timeout($scope.reload_searches, 5000)
                $timeout(
                    $scope.reload_searches,
                    5000
                )
    }
)

angular_add_simple_list_controller(
    package_module,
    "package_base",
    {
        rest_url            : "{% url 'rest:package_list' %}"
        #edit_template       : "package_search.html"
        rest_map            : [
            {"short" : "package_repo", "url" : "{% url 'rest:package_repo_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Package '#{obj.name}-#{obj.version}' ?"
        template_cache_list : ["package_row.html", "package_head.html"]
        init_fn:
            ($scope) ->
                # true for device / pdc, false for pdc / device style
                $scope.dp_style = true
                $scope.shared_data.package_list_changed = 0
                $scope.$watch(
                    () -> return $scope.shared_data.package_list_changed
                    (new_el) ->
                        $scope.reload()
                )
        fn:
            toggle_grid_style : ($scope) ->
                $scope.dp_style = !$scope.dp_style
            get_grid_style : ($scope) ->
                return if $scope.dp_style then "Dev/PDC grid" else "PDC/Dev grid"
    }
)

angular_add_simple_list_controller(
    package_module,
    "package_search_result_base",
    {
        #rest_url            : "{% url 'rest:package_search_list' %}"
        edit_template       : "package_search.html"
        rest_map            : [
            {"short" : "package_repo", "url" : "{% url 'rest:package_repo_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Package search result '#{obj.name}-#{obj.version}' ?"
        template_cache_list : ["package_search_result_row.html", "package_search_result_head.html"]
        init_fn:
            ($scope) ->
                $scope.$watch(
                    () -> return $scope.shared_data.result_obj
                    (new_el) ->
                        if $scope.shared_data.result_obj
                            $scope.pagSettings.clear_filter()
                            # $.blockUI()
                            $scope.load_data(
                                "{% url 'rest:package_search_result_list' %}",
                                {"package_search" : $scope.shared_data.result_obj.idx}
                            ).then(
                                (data) ->
                                    # $.unblockUI()
                                    $scope.entries = data
                                    for entry in $scope.entries
                                        entry.target_repo = 0
                            )
                        else
                            $scope.entries = []
                )
        fn:
            show_repo : ($scope, obj) ->
                if obj.target_repo
                    return $scope.rest_data["package_repo"][obj.target_repo].name
                else
                    return "ignore"
            take : ($scope, obj, exact) ->
                obj.copied = 1
                call_ajax
                    url     : "{% url 'pack:use_package' %}"
                    data    : {
                        "pk"          : obj.idx
                        "exact"       : if exact then 1 else 0
                        "target_repo" : obj.target_repo
                    }
                    success : (xml) ->
                        if parse_xml_response(xml)
                            $scope.shared_data.package_list_changed += 1
                        else
                            obj.copied = 0
    }
)

update_pdc = (srv_pdc, client_pdc) ->
    for attr_name in ["installed", "package", "response_str", "response_type", "target_state", "install_time",
      "installed_name", "installed_version", "installed_release"] 
        client_pdc[attr_name] = srv_pdc[attr_name]
        
package_module.controller("install", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "sharedDataSource", "$q", "$timeout", "blockUI", "icswTools",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, sharedDataSource, $q, $timeout, blockUI, icswTools) ->
        # devices
        $scope.entries = []
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
        $scope.device_tree_url = "{% url 'rest:device_tree_list' %}"
        wait_list = restDataSource.add_sources([
            [$scope.device_tree_url, {"ignore_meta_devices" : true}]
            ["{% url 'rest:image_list' %}", {}]
            ["{% url 'rest:kernel_list' %}", {}]
        ])
        $scope.inst_rest_data = {}
        $q.all(wait_list).then((data) ->
            $scope.set_devices(data[0])
            $scope.srv_image_list = data[1]
            $scope.srv_kernel_list = data[2]
        )
        #$scope.load_devices = (url, options) ->
        #    return Restangular.all(url.slice(1)).getList(options)
        $scope.reload_devices = () ->
            blockUI.start()
            restDataSource.reload([$scope.device_tree_url, {"ignore_meta_devices" : true}]).then((data) ->
                $scope.set_devices(data)
                blockUI.stop()
            )
        # not working right now, f*ck, will draw to many widgets
        $scope.reload_state = () ->
            #console.log "rls"
            Restangular.all("{% url 'rest:device_tree_list' %}".slice(1)).getList({"package_state" : true, "ignore_meta_devices" : true}).then(
                (data) ->
                    #console.log "reload"
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
        $scope.$watch("entries", (new_val) ->
            # init dummy pdc entries when new packages are added / removed to / from the entries list
            for pack in $scope.entries
                for dev_idx of $scope.device_lut
                    dev_idx = parseInt(dev_idx)
                    # dummy entry for newly added packages
                    $scope.state_dict[dev_idx][pack.idx]  = {"device" : dev_idx, "package" : pack.idx}
        )
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
            $scope.package_lut = icswTools.build_lut($scope.entries)
            #console.log $scope.entries.length, $scope.devices.length
            for dev in $scope.devices
                dev.latest_contact = 0
                dev.client_version = "?.?"
                if not (dev.idx of $scope.state_dict)
                    $scope.state_dict[dev.idx] = {}
                dev_dict = $scope.state_dict[dev.idx]
                for pack in $scope.entries
                    if not (pack.idx of dev_dict)
                        dev_dict[pack.idx] = {"device" : dev.idx, "package" : pack.idx}
            $scope.reload_state()
        # attach / detach calls
        $scope.attach = (obj) ->
            attach_list = []
            for dev_idx, dev_dict of $scope.state_dict
                for pack_idx, pdc of dev_dict
                    if pdc.selected and parseInt(pack_idx) == obj.idx
                        attach_list.push([parseInt(dev_idx), obj.idx])
            call_ajax
                url     : "{% url 'pack:add_package' %}"
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
            call_ajax
                url     : "{% url 'pack:remove_package' %}"
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
            call_ajax
                url     : "{% url 'pack:change_pdc' %}"
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
            $scope.action_div = $compile($templateCache.get("package_action.html"))($scope)
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
            call_ajax
                url     : "{% url 'pack:repo_overview' %}"
                data    : {
                    "mode" : "new_config"
                }
                success : (xml) ->
                    blockUI.stop()
                    parse_xml_response(xml)
        $scope.send_clear_caches = (event) ->
            blockUI.start()
            call_ajax
                url     : "{% url 'pack:repo_overview' %}"
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
]).directive("packageinstall", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("package_install.html")
        link : (scope, el, attrs) ->
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    # args is not needed here, fix controller
                    scope.reload_devices(args[1])
                )
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
                        new_el = $compile($templateCache.get("pdc_state.html"))
                    else if scope.mode == "v"
                        new_el = $compile($templateCache.get("pdc_version.html"))
                    iElement.append(new_el(scope))
                scope.$watch("mode", () ->
                    scope.draw()
                )
                scope.draw()
    }
)

{% endinlinecoffeescript %}

</script>
