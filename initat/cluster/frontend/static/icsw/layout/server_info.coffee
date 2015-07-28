# Copyright (C) 2012-2015 init.at
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
).controller("icswServerInfoOverviewCtrl", ["$scope", "$timeout", "access_level_service", "blockUI", "$window", "ICSW_URLS", "icswLayoutServerInfoService", "icswCallAjaxService", "icswParseXMLResponseService", "icswSimpleAjaxCall",
    ($scope, $timeout, access_level_service, blockUI, $window, ICSW_URLS, icswLayoutServerInfoService, icswCallAjaxService, icswParseXMLResponseService, icswSimpleAjaxCall) ->
        access_level_service.install($scope)
        $scope.show_server = true
        $scope.show_roles = false
        $scope.server_info_list = []
        $scope.local_device = "---"
        $scope.routing_info = {}
        $scope.cur_to = null
        icswSimpleAjaxCall(
            {
                "url": ICSW_URLS.MAIN_ROUTING_INFO
                "force": 1
                "dataType": "json"
            }
        ).then(
            (json) ->
                $scope.local_device = json.local_device
                $scope.routing_info = json.routing
        )
        $scope.reload_server_info = () ->
            icswCallAjaxService
                url     : ICSW_URLS.MAIN_GET_SERVER_INFO
                hidden  : true
                success : (xml) =>
                    $scope.server_info_list = []
                    $scope.instance_list = []
                    $scope.runs_on = {}
                    $(xml).find("ics_batch").each (idx, res_xml) ->
                        res_xml = $(res_xml)
                        cur_si = new icswLayoutServerInfoService(res_xml)
                        $scope.server_info_list.push(cur_si)
                        _cur_inst = cur_si.instance_names()
                        for _name in _cur_inst
                            if _name not of $scope.runs_on
                                $scope.runs_on[_name] = res_xml.find("instance[name='#{_name}']").attr("runs_on")
                        $scope.instance_list = _.union($scope.instance_list, _cur_inst)
                    $scope.cur_to = $timeout($scope.reload_server_info, 15000)
                    $scope.$digest()
        $scope.get_runs_on = (instance) ->
            return $scope.runs_on[instance]
        $scope.num_roles = () ->
            return (key for key of $scope.routing_info).length
        $scope.get_roles = () ->
            return (key for key of $scope.routing_info)
        $scope.get_num_servers = (role) ->
            return $scope.routing_info[role].length
        $scope.get_servers = (role) ->
            return $scope.routing_info[role]
        $scope.get_config_names  = (srv_info) ->
            return srv_info[4].join(", ")
        $scope.do_action = (srv_info, instance, type) ->
            if $scope.cur_to
                $timeout.cancel($scope.cur_to)
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.MAIN_SERVER_CONTROL
                data    : {
                    "cmd" : angular.toJson(
                        "server_id" : srv_info.get_server_id()
                        "instance"  : instance
                        "type"      : type
                    )
                }
                success : (xml) =>
                    icswParseXMLResponseService(xml)
                    blockUI.stop()
                    $scope.cur_to = $timeout($scope.reload_server_info, 100)
            return false
        $scope.reload_server_info()
]).service("icswLayoutServerInfoService", () ->
    class server_info
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
                _state_info = _xml.find("state_info")
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
            _state_info = @xml.find("instance[name='#{instance}'] state_info")
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
            _state_info = _xml.find("state_info")
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
]).directive("icswServiceEnableDisable", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.service.enable.disable")
        link : (scope, element, attrs) ->
            scope.service_enabled = () ->
                return scope.srv_info.service_enabled(scope.instance)
            scope.service_disabled = () ->
                return scope.srv_info.service_disabled(scope.instance)
    }
]).directive("icswLayoutServerInfoOverview", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.server.info.overview")
    }
])
