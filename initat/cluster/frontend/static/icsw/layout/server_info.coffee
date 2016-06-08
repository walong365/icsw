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
    "icsw.server.info",
    [
        "ngResource", "ngCookies", "ngSanitize", "init.csw.filters", "ui.bootstrap", "restangular"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.serverinfo",
        {
            url: "/serverinfo",
            templateUrl: "icsw/main/serverinfo.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Server info"
                rights: (user, acls) ->
                    if user.is_superuser
                        return true
                    else
                        return false
        }
    ).state(
        "main.statelist", {
            url: "/statelist"
            template: '<icsw-internal-state-list></icsw-internal-state-list>'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Internal State list"
                rights: (user, acls) ->
                    if user.is_superuser
                        return true
                    else
                        return false
                menuEntry:
                    preSpacer: true
                    menukey: "sys"
                    icon: "fa-bars"
                    ordering: 30
                    postSpacer: true
        }
    )
]).controller("icswServerInfoOverviewCtrl",
[
    "$scope", "$timeout", "icswAcessLevelService", "blockUI", "$window", "ICSW_URLS",
    "icswLayoutServerInfoService", "icswSimpleAjaxCall",
(
    $scope, $timeout, icswAcessLevelService, blockUI, $window, ICSW_URLS,
    icswLayoutServerInfoService, icswSimpleAjaxCall
) ->
    icswAcessLevelService.install($scope)
    $scope.struct = {
        # loading
        loading: false
        # show server
        show_server: true
        # show roles
        show_roles: false
        # server info list
        server_info_list: []
        # local device
        local_device: "---"
        # local device is ok
        local_device_ok: false
        # routing information
        routing_info: {}
        # current timeout object
        cur_to: null
        # unroutable config objects
        unroutable_configs: undefined 
        unroutable_config_names: []
    }
    $scope.$watch(
        () ->
            return icswAcessLevelService.acl_valid()
        (new_val) ->
            if new_val
                _ri = icswAcessLevelService.get_routing_info()
                $scope.struct.routing_info = _ri.routing
                if _ri.local_device
                    $scope.struct.local_device_ok = true
                    $scope.struct.local_device = _ri.local_device
                else
                    $scope.struct.local_device_ok = false
                    $scope.struct.local_device = _ri.internal_dict._server_info_str
                $scope.struct.unroutable_configs = _ri.unroutable_configs
                $scope.struct.unroutable_config_names =  []
                for key, v of _ri.unroutable_configs
                    $scope.struct.unroutable_config_names.push(key)
    )
    $scope.reload_server_info = () ->
        $scope.struct.loading = true
        icswSimpleAjaxCall(
            url: ICSW_URLS.MAIN_GET_SERVER_INFO
            hidden: true
            ignore_log_level: true
            show_error: false
        ).then(
            (xml) ->
                $scope.struct.server_info_list = []
                $scope.struct.instance_list = []
                $scope.struct.runs_on = {}
                $(xml).find("ics_batch").each (idx, res_xml) ->
                    res_xml = $(res_xml)
                    cur_si = new icswLayoutServerInfoService(res_xml)
                    $scope.struct.server_info_list.push(cur_si)
                    _cur_inst = cur_si.instance_names()
                    for _name in _cur_inst
                        if _name not of $scope.struct.runs_on
                            $scope.struct.runs_on[_name] = res_xml.find("instance[name='#{_name}']").attr("runs_on")
                    $scope.struct.instance_list = _.union($scope.instance_list, _cur_inst)
                $scope.struct.loading = false
                $scope.struct.cur_to = $timeout($scope.reload_server_info, 15000)
        )

    $scope.get_runs_on = (instance) ->
        return $scope.struct.runs_on[instance]

    $scope.num_roles = () ->
        return (key for key of $scope.struct.routing_info).length

    $scope.get_roles = () ->
        return (key for key of $scope.struct.routing_info)

    $scope.get_num_servers = (role) ->
        return $scope.struct.routing_info[role].length

    $scope.get_servers = (role) ->
        return $scope.struct.routing_info[role]

    $scope.get_config_names  = (srv_info) ->
        return srv_info[4].join(", ")

    $scope.do_action = (srv_info, instance, type) ->
        if $scope.struct.cur_to
            $timeout.cancel($scope.struct.cur_to)
        blockUI.start()
        icswSimpleAjaxCall(
            url     : ICSW_URLS.MAIN_SERVER_CONTROL
            data    : {
                cmd: angular.toJson(
                    server_id: srv_info.get_server_id()
                    instance: instance
                    type: type
                )
            }
        ).then(
            (xml) ->
                blockUI.stop()
                if $scope.struct.cur_tu
                    $timeout.cancel($scope.struct.cur_to)
                $scope.struct.cur_to = $timeout($scope.reload_server_info, 100)
        )
        return false

    $scope.$on("$destroy", () ->
        if $scope.struct.cur_tu
            $timeout.cancel($scope.struct.cur_to)
    )

    $scope.reload_server_info()
]).service("icswLayoutServerInfoService", () ->

    class icswLayoutServerInfoService
        constructor: (@xml) ->
            _round = 8 * 1024 * 1024
            @result = @xml.find("result")
            @server_state = parseInt(@result.attr("state"))
            @server_reply = @result.attr("reply")
            @valid = if @server_state == 0 then true else false
            _mem_vector = (parseInt($(mem_info).contents().first().text()) for mem_info in @xml.find("instance > result > memory_info") when $(mem_info).text())
            if _mem_vector.length
                @max_mem = _.max(_mem_vector)
                @sum_mem = _.reduce(_mem_vector, (sum, _val) -> return sum + _val)
            else
                @max_mem = 0
                @sum_mem = 0
            if @xml.find("version_info").length
                @version_set = true
                @version_models = @xml.find("version_info > sys").attr("models")
                @version_database = @xml.find("version_info > sys").attr("database")
                @version_software = @xml.find("version_info > sys").attr("software")
            else
                @version_set = false

        get_tr_class: () ->
            if @server_state
                return "danger"
            else
                return ""

        get_name: () ->
            return @xml.find("command").attr("server_name")

        get_server_id: () ->
            return parseInt(@xml.find("command").attr("server_id"))

        instance_names: () ->
            return ($(entry).attr("name") for entry in @xml.find("instance"))

        service_enabled: (instance) ->
            _meta_xml = @xml.find("metastatus > instances > instance[name='#{instance}']")
            if _meta_xml.length
                return if parseInt(_meta_xml.attr("target_state")) == 1 then true else false
            else
                return false

        service_disabled: (instance) ->
            _meta_xml = @xml.find("metastatus > instances > instance[name='#{instance}']")
            if _meta_xml.length
                return if parseInt(_meta_xml.attr("target_state")) == 0 then true else false
            else
                return false

        get_state: (instance) ->
            _xml = @xml.find("status > instances > instance[name='#{instance}']")
            if _xml.length
                _state_info = _xml.find("process_state_info")
                if parseInt(_state_info.attr("state")) == 5
                    # not installed
                    return 3
                else if parseInt(_state_info.attr("state")) == 6
                    # not configured
                    return 4
                else
                    if _xml.attr("check_type") == "simple"
                        if parseInt(_state_info.attr("state")) == 0
                            # running
                            return 1
                        else
                            # not running
                            return 2
                    else
                        if _state_info.attr("num_started")
                            # running
                            return 1
                        else
                            # not running
                            return 2
            else
                # nothing found
                return 0

        get_run_class: (instance) ->
            _state_info = @xml.find("instance[name='#{instance}'] process_state_info")
            _diff = parseInt(_state_info.attr("num_diff"))
            if _diff
                return "text-danger"
            else
                return "text-success"

        get_version_class: (instance) ->
            _xml = @xml.find("instance[name='#{instance}']")
            if _xml.find("result").attr("version_ok")?
                _vers_ok = parseInt(_xml.find("result").attr("version_ok"))
                if _vers_ok
                    return "text-success"
                else
                    return "text-danger"
            else
                return "text-warn"

        get_version: (instance) ->
            _xml = @xml.find("instance[name='#{instance}']")
            if _xml.find("result").attr("version_ok")?
                return _xml.find("result").attr("version").replace("-", "&ndash;")
            else
                return ""

        has_startstop: (instance) ->
            _xml = @xml.find("instance[name='#{instance}']")
            if _xml.attr("startstop")?
                return if parseInt(_xml.attr("startstop")) then true else false
            else
                return false
        get_run_info: (instance) ->
            _xml = @xml.find("instance[name='#{instance}']")
            _state_info = _xml.find("process_state_info")
            if _xml.attr("check_type") == "simple"
                return _xml.find("pids > pid").length
            else
                _started = parseInt(_state_info.attr("num_started"))
                _found = parseInt(_state_info.attr("num_found"))
                _diff = parseInt(_state_info.attr("num_diff"))
                if !_diff
                    return "#{_started}"
                else
                    if _diff > 0
                        return "#{_found} (#{-_diff} too much)"
                    else
                        return "#{_found} (#{-_diff} missing)"

        enable_disable_allowed: (instance) ->
            if instance in ["meta-server", "logging-server"]
                return false
            else
                return true

        get_mem_info: (instance) ->
            _xml = @xml.find("instance[name='#{instance}'] memory_info").contents().first()
            return _xml.text()

        get_mem_value: (instance) ->
            _mem = @xml.find("instance[name='#{instance}'] memory_info").contents().first().text()
            return parseInt((parseInt(_mem) * 100) / @max_mem)

        get_check_source: (instance) ->
            return @xml.find("instance[name='#{instance}']").attr("check_type")

).directive("icswLayoutServerInfoInstance", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            scope.get_state = () ->
                return scope.srv_info.get_state(scope.instance)
            scope.get_run_info = () ->
                return scope.srv_info.get_run_info(scope.instance)
            scope.get_run_class = () ->
                return scope.srv_info.get_run_class(scope.instance)
            scope.get_version_class = () ->
                return scope.srv_info.get_version_class(scope.instance)
            scope.has_startstop = () ->
                return scope.srv_info.has_startstop(scope.instance)
            scope.get_version = () ->
                return scope.srv_info.get_version(scope.instance)
            scope.get_mem_info = () ->
                return scope.srv_info.get_mem_info(scope.instance)
            scope.get_mem_value = () ->
                return scope.srv_info.get_mem_value(scope.instance)
            scope.enable_disable_allowed = () ->
                return scope.srv_info.enable_disable_allowed(scope.instance)
            scope.action = (type) ->
                scope.do_action(scope.srv_info, scope.instance, type)
            new_el = $compile($templateCache.get("icsw.layout.server.info.state"))
            element.append(new_el(scope))
    }
]).directive("icswServiceEnableDisable",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.service.enable.disable")
        link : (scope, element, attrs) ->
            scope.service_enabled = () ->
                return scope.srv_info.service_enabled(scope.instance)
            scope.service_disabled = () ->
                return scope.srv_info.service_disabled(scope.instance)
    }
]).directive("icswLayoutServerInfoOverview",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.server.info.overview")
        controller: "icswServerInfoOverviewCtrl"
    }
]).directive("icswInternalStateList",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.internal.state.list")
        controller: "icswInternalStateListCtrl"
    }
]).controller("icswInternalStateListCtrl",
[
    "$scope", "$timeout", "icswAcessLevelService", "blockUI", "$window", "ICSW_URLS",
    "icswLayoutServerInfoService", "icswSimpleAjaxCall", "$state", "icswRouteHelper",
(
    $scope, $timeout, icswAcessLevelService, blockUI, $window, ICSW_URLS,
    icswLayoutServerInfoService, icswSimpleAjaxCall, $state, icswRouteHelper,
) ->
    _struct = icswRouteHelper.get_struct()
    
    $scope.struct = {
        state_list: _struct.icsw_states 
    }

    $scope.get_header_class = (state) ->
        return "fa #{state.icswData.menuHeader.icon}"

    $scope.get_entry_class = (state) ->
        return "fa #{state.icswData.menuEntry.icon}"

    $scope.go = ($event, state) ->
        $state.go(state)

])
