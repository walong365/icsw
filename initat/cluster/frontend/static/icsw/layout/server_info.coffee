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
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.serverinfo")
    icswRouteExtensionProvider.add_route("main.statelist")
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
                    cur_si = new icswLayoutServerInfoService($scope, res_xml)
                    $scope.struct.server_info_list.push(cur_si)
                    _cur_inst = cur_si.$$instance_names
                    for _name in _cur_inst
                        if _name not of $scope.struct.runs_on
                            $scope.struct.runs_on[_name] = res_xml.find("instance[name='#{_name}']").attr("runs_on")
                    $scope.struct.instance_list = _.uniq(_.concat($scope.struct.instance_list, _cur_inst))
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
                    server_id: srv_info.$$srv_id
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
        if $scope.struct.cur_to
            $timeout.cancel($scope.struct.cur_to)
    )

    $scope.reload_server_info()
]).service("icswLayoutServerInfoService", () ->

    class icswLayoutServerInfoService
        constructor: (@scope, @xml) ->
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
            @service_lut = {}
            @salt()

        has_service: (name) ->
            return name of @service_lut

        get_service: (name) ->
            return @service_lut[name]

        salt: () ->
            @$$srv_name = @xml.find("command").attr("server_name")
            @$$srv_id = parseInt(@xml.find("command").attr("server_id"))
            if @valid
                @_salt_ok()
            else
                @_salt_error()

        _salt_error: () =>
            @$$tr_class = "danger"
            @$$instance_names = []

        _salt_ok: () =>
            @$$tr_class = ""
            @$$instance_names = ($(entry).attr("name") for entry in @xml.find("instance"))
            for name in @$$instance_names
                @service_lut[name] = @_salt_service(name)

        do_action: (instance, action) =>
            @scope.do_action(@, instance, action)

        _salt_service: (instance) ->
            _meta_xml = @xml.find("metastatus > instances > instance[name='#{instance}']")
            _xml = @xml.find("status > instances > instance[name='#{instance}']")
            salted = {
                name: instance
                meta_xml: _meta_xml
                xml: _xml
                $$enable_disable_allowed: instance not in ["meta-server", "logging-server"]
            }
            console.log instance, _meta_xml[0]
            if _meta_xml.length
                salted.$$enabled = if parseInt(_meta_xml.attr("target_state")) == 1 then true else false
                salted.$$disabled = !salted.$$enabled
                salted.$$ignore = if parseInt(_meta_xml.attr("ignore")) == 1 then true else false
                salted.$$monitor = !salted.$$ignore
            else
                salted.$$enabled = false
                salted.$$disabled = false
                salted.$$ignore = false
                salted.$$monitor = false
            if _xml.length
                salted.$$startstop = if parseInt(_xml.attr("startstop")) then true else false
                salted.$$version_class = if parseInt(_xml.find("result").attr("version_ok")) then "text-success" else "text-danger"
                if _xml.find("result").attr("version")?
                    salted.$$version = _xml.find("result").attr("version").replace("-", "&ndash;")
                else
                    salted.$$version = ""
                _state_info = _xml.find("process_state_info")
                _diff = parseInt(_state_info.attr("num_diff"))
                if _diff
                    salted.$$run_class = "text-danger"
                else
                    salted.$$run_class = "text-success"
                if _xml.attr("check_type") == "simple"
                    salted.$$run_info = _xml.find("pids > pid").length
                else
                    if _state_info.attr("num_started")?
                        _started = parseInt(_state_info.attr("num_started"))
                        _found = parseInt(_state_info.attr("num_found"))
                        _diff = parseInt(_state_info.attr("num_diff"))
                        if !_diff
                            salted.$$run_info = "#{_started}"
                        else
                            if _diff > 0
                                salted.$$run_info = "#{_found} (#{-_diff} too much)"
                            else
                                salted.$$run_info = "#{_found} (#{-_diff} missing)"
                    else
                        salted.$$run_info = "N/A"
                salted.$$mem_value = @xml.find("instance[name='#{instance}'] memory_info").contents().first().text()
                salted.$$mem_percent = parseInt((parseInt(salted.$$mem_value) * 100) / @max_mem)
                if parseInt(_state_info.attr("state")) == 5
                    # not installed
                    salted.$$state = 3
                else if parseInt(_state_info.attr("state")) == 6
                    # not configured
                    salted.$$state = 4
                else
                    if _xml.attr("check_type") == "simple"
                        if parseInt(_state_info.attr("state")) == 0
                            # running
                            salted.$$state = 1
                        else
                            # not running
                            salted.$$state = 2
                    else
                        if _state_info.attr("num_started")
                            # running
                            salted.$$state = 1
                        else
                            # not running
                            salted.$$state = 2
            else
                salted.$$state = 0
                salted.$$startstop = false
                salted.$$version_class = "text-warn"
                salted.$$version = ""
                salted.$$run_class = ""
                salted.$$run_info = "---"
                salted.$$mem_value = 0
                salted.$$mem_percent = 0
            return salted

        get_check_source: (instance) ->
            return @xml.find("instance[name='#{instance}']").attr("check_type")

).directive("icswLayoutServerInfoInstance",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict : "EA"
        scope:
            server_info: "=icswServerInfo"
            service_name: "=icswServiceName"
        template: $templateCache.get("icsw.layout.server.info.state")
        controller: "icswLayoutServerInfoInstanceCtrl"
    }
]).controller("icswLayoutServerInfoInstanceCtrl",
[
    "$scope", "icswAcessLevelService",
(
    $scope, icswAcessLevelService,
) ->

    icswAcessLevelService.install($scope)
    if $scope.server_info.has_service($scope.service_name)
        $scope.service = $scope.server_info.get_service($scope.service_name)
    else
        $scope.service = {
            "$$state": 0
        }

    $scope.do_action = (action) ->
        $scope.server_info.do_action($scope.service_name, action)

    $scope.$on("$destroy", () ->
    )
]).directive("icswServiceEnableDisable",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.service.enable.disable")
    }
]).directive("icswServiceMonitorIgnore",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.service.monitor.ignore")
    }
]).directive("icswLayoutServerInfoOverview",
[
    "$templateCache",
(
    $templateCache,
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
