{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

package_module = angular.module("icsw.package", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([package_module])

angular_add_simple_list_controller(
    package_module,
    "package_repo_base",
    {
        rest_url            : "{% url 'rest:package_repo_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Package repository '#{obj.name}' ?"
        template_cache_list : ["package_repo_row.html", "package_repo_head.html"]
        fn :
            toggle : (obj) ->
                obj.publish_to_nodes = if obj.publish_to_nodes then false else true
                obj.put()
            rescan : ($scope) ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "rescan_repos"
                    }
                    success : (xml) ->
                        $.unblockUI()
                        if parse_xml_response(xml)
                            $scope.reload()
            sync : () ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "sync_repos"
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)
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
        new_object          : {"search_string" : "", "user" : {{ request.user.pk }}}
        post_delete : ($scope, del_obj) ->
            if $scope.shared_data.result_obj and $scope.shared_data.result_obj.idx == del_obj.idx
                $scope.shared_data.result_obj = undefined
        object_created  : (new_obj, srv_data) -> 
            new_obj.search_string = ""
            $.ajax
                url     : "{% url 'pack:repo_overview' %}"
                data    : {
                    "mode" : "reload_searches"
                }
                success : (xml) ->
                    parse_xml_response(xml)
        fn:
            object_modified : (edit_obj, srv_data, $scope) ->
                $scope.reload()
            retry : ($scope, obj) ->
                if $scope.shared_data.result_obj and $scope.shared_data.result_obj.idx == obj.idx
                    $scope.shared_data.result_obj = undefined
                $.ajax
                    url     : "{% url 'pack:retry_search' %}"
                    data    : {
                        "pk" : obj.idx
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
                        $scope.reload()
            show : ($scope, obj) ->
                $scope.shared_data.result_obj = obj
        init_fn:
            ($scope, $timeout) ->
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
                            $.blockUI()
                            $scope.load_data(
                                "{% url 'rest:package_search_result_list' %}",
                                {"package_search" : $scope.shared_data.result_obj.idx}
                            ).then(
                                (data) ->
                                    $.unblockUI()
                                    $scope.entries = data
                            )
                        else
                            $scope.entries = []
                )
        fn:
            take : ($scope, obj, exact) ->
                obj.copied = 1
                $.ajax
                    url     : "{% url 'pack:use_package' %}"
                    data    : {
                        "pk"    : obj.idx
                        "exact" : if exact then 1 else 0
                    }
                    success : (xml) ->
                        if parse_xml_response(xml)
                            $scope.shared_data.package_list_changed += 1
                        else
                            obj.copied = 0
    }
)

class pdc
    constructor: (@device, @package) ->
        @selected = false
    set_xml_pdc: (xml_pdc) =>
        # defaults
        for attr_name in ["installed", "target_state", "response_str", "response_type"]
            @[attr_name] = xml_pdc.attr(attr_name)
        @force_flag = parseInt(xml_pdc.attr("force_flag"))
        @nodeps_flag = parseInt(xml_pdc.attr("nodeps_flag"))
        @idx = parseInt(xml_pdc.attr("pk"))
        #console.log xml_pdc[0]
        #console.log @
    set_pdc: (pdc) =>
        for attr_name in ["force_flag", "nodeps_flag", "installed", "target_state", "response_str", "response_type", "idx"]
            @[attr_name] = pdc[attr_name]
    update: (pdc) =>
        for attr_name in ["installed", "package", "response_str", "response_type", "target_state"]
            @[attr_name] = pdc[attr_name]
    remove_pdc: =>
        # clears pdc state
        delete @idx
      
package_module.controller("install", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "sharedDataSource", "$q", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, sharedDataSource, $q, $timeout) ->
        # devices
        $scope.devices = []
        $scope.package_filter = ""
        # init state dict
        $scope.state_dict = {}
        $scope.selected_pdcs = {}
        $scope.shared_data = sharedDataSource.data
        $scope.device_tree_url = "{% url 'rest:device_tree_list' %}"
        wait_list = [restDataSource.add_sources([[$scope.device_tree_url, {"ignore_meta_devices" : true}]])[0]]
        $scope.inst_rest_data = {}
        $q.all(wait_list).then((data) ->
            for value, idx in data
                if idx == 0
                    $scope.set_devices(value)
                else
                    $scope.inst_rest_data[$scope.settings.rest_map[idx - 1].short] = value
        )
        #$scope.load_devices = (url, options) ->
        #    return Restangular.all(url.slice(1)).getList(options)
        $scope.reload_devices = () ->
            $.blockUI()
            restDataSource.reload([$scope.device_tree_url, {"ignore_meta_devices" : true}]).then((data) ->
                $scope.set_devices(data)
                $.unblockUI()
            )
        # not working right now, f*ck, will draw to many widgets
        install_devsel_link($scope.reload_devices, true)
        $scope.reload_state = () ->
            #console.log "rls"
            Restangular.all("{% url 'rest:device_tree_list' %}".slice(1)).getList({"package_state" : true, "ignore_meta_devices" : true}).then(
                (data) ->
                    #console.log "reload"
                    for dev in data
                        $scope.device_lut[dev.idx].latest_contact = dev.latest_contact
                        for pdc in dev.package_device_connection_set
                            cur_pdc = $scope.state_dict[dev.idx][pdc.package]
                            if cur_pdc.idx
                                # copy flags
                                cur_pdc.update(pdc)
                            else
                                # copy flags
                                cur_pdc.set_pdc(pdc)
                    $scope.reload_promise = $timeout($scope.reload_state, 10000)
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
            $scope.device_lut = build_lut($scope.devices)
            # package lut
            $scope.package_lut = build_lut($scope.entries)
            console.log $scope.entries.length, $scope.devices.length
            for dev in $scope.devices
                dev.latest_contact = 0
                if not (dev.idx of $scope.state_dict)
                    $scope.state_dict[dev.idx] = {}
                dev_dict = $scope.state_dict[dev.idx]
                for pack in $scope.entries
                    if not (pack.idx of dev_dict)
                        dev_dict[pack.idx] = new pdc(dev.idx, pack.idx)
            $scope.reload_state()
        # attach / detach calls
        $scope.attach = (obj) ->
            attach_list = []
            for dev_idx, dev_dict of $scope.state_dict
                for pack_idx, pdc of dev_dict
                    if pdc.selected and parseInt(pack_idx) == obj.idx
                        attach_list.push([parseInt(dev_idx), obj.idx])
            $.ajax
                url     : "{% url 'pack:add_package' %}"
                data    : {
                    "add_list" : angular.toJson(attach_list)
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    $(xml).find("entries package_device_connection").each (idx, cur_pdc) ->
                        cur_pdc = $(cur_pdc)
                        $scope.state_dict[cur_pdc.attr("device")][cur_pdc.attr("package")].set_xml_pdc(cur_pdc)
                    $scope.update_selected_pdcs()
                    $scope.$apply()
        $scope.remove = (obj) ->
            remove_list = []
            for dev_idx, dev_dict of $scope.state_dict
                for pack_idx, pdc of dev_dict
                    if pdc.selected and parseInt(pack_idx) == obj.idx and pdc.idx
                        remove_list.push(pdc.idx)
                        delete $scope.selected_pdcs[pdc.idx]
                        pdc.remove_pdc()
            $.ajax
                url     : "{% url 'pack:remove_package' %}"
                data    : {
                    "remove_list" : angular.toJson(remove_list)
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    # just to be sure
                    $scope.update_selected_pdcs()
        $scope.target_states = {
            "---"  : "---"
            "keep" : "keep",
            "install" : "install",
            "upgrade" : "upgrade",
            "erase" : "erase",
        }
        $scope.flag_states = {
            "---" : "---",
            "set" : "set",
            "clear" : "clear",
        }
        $scope.modify = () ->
            $.simplemodal.close()
            if $scope.edit_obj["target_state"] != "---" or $scope.edit_obj["nodeps_flag"] != "---" or $scope.edit_obj["force_flag"] != "---"
                # change selected pdcs
                change_dict = {"edit_obj" : $scope.edit_obj, "pdc_list" : []}
                for pdc_idx, pdc of $scope.selected_pdcs
                    change_dict["pdc_list"].push(pdc_idx)
                    if $scope.edit_obj["target_state"] != "---"
                        pdc.target_state = $scope.edit_obj["target_state"]
                    for f_name in ["nodeps_flag", "force_flag"]
                        if $scope.edit_obj[f_name] != "---"
                            pdc[f_name] = if $scope.edit_obj[f_name] == "set" then true else false
                $.ajax
                    url     : "{% url 'pack:change_pdc' %}"
                    data    : {
                        "change_dict" : angular.toJson(change_dict)
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
        $scope.action = (event) ->
            $scope.edit_obj = {"target_state" : "---", "nodeps_flag" : "---", "force_flag" : "---"} 
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
        $scope.send_sync = (event) ->
            $.blockUI()
            $.ajax
                url     : "{% url 'pack:repo_overview' %}"
                data    : {
                    "mode" : "new_config"
                }
                success : (xml) ->
                    $.unblockUI()
                    parse_xml_response(xml)
        $scope.latest_contact = (dev) ->
            if dev.latest_contact
                return moment.unix(dev.latest_contact).fromNow(true)
            else
                return "never"

]).directive("istate", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        scope:
            pdc: "=pdc"
            selected_pdcs: "=pdcs"
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
                    return "btn-" + scope.get_td_class()
                scope.get_td_class = () ->
                    if scope.pdc and scope.pdc.idx
                        cur = scope.pdc
                        if cur.installed == "y"
                            return "success"
                        else if cur.installed == "u"
                            return "warning"
                        else if cur.installed == "n"
                            return "danger"
                        else
                            return "active"
                    else
                        return ""
                scope.change_sel = () ->
                    pdc = scope.pdc
                    if pdc.idx
                        if pdc.selected and pdc.idx not of scope.selected_pdcs
                            scope.selected_pdcs[pdc.idx] = pdc
                        else if not pdc.selected and pdc.idx of scope.selected_pdcs
                            delete scope.selected_pdcs[pdc.idx]
                new_el = $compile($templateCache.get("pdc_state.html"))
                iElement.append(new_el(scope))
    }
)

{% endinlinecoffeescript %}

</script>
