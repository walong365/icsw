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

monitoring_basic_module = angular.module("icsw.monitoring.monitoring_basic",
[
    "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
    "icsw.tools.table", "icsw.tools.button"
]).directive("icswMonitoringBasic", () ->
    return {
        restrict:"EA"
        templateUrl: "icsw.monitoring.basic"
    }
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.monitorbasics", {
            url: "/monitorbasics"
            template: "<icsw-monitoring-basic></icsw-monitoring-basic>"
            data:
                pageTitle: "Monitoring Basic setup"
                menuHeader:
                    key: "mon"
                    name: "Monitoring"
                    icon: "fa-gears"
                    ordering: 70
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Basic setup"
                    icon: "fa-bars"
                    ordering: 0
        }
    )
    $stateProvider.state(
        "main.monitorredirect", {
            url: "/monitorredirect"
            template: "<h2>Redirecting...</h2>"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "Icinga"
                    icon: "fa-share-alt"
                    ordering: 120
            resolve:
                redirect: ["$window", "icswSimpleAjaxCall", "ICSW_URLS", "$q", ($window, icswSimpleAjaxCall, ICSW_URLS, $q) ->
                    _defer = $q.defer()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CALL_ICINGA
                        dataType: "json"
                    ).then(
                        (json) ->
                            url = json["url"]
                            $window.open(url, "_blank")
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
    $stateProvider.state(
        "main.monitorb0", {
            url: "/monitorb0"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config cached"
                    icon: "fa-share-alt"
                    ordering: 101
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    # todo: add icswMenuProgressService
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            "cache_mode": "ALWAYS"
                        title: "create config"
                    ).then(
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
    $stateProvider.state(
        "main.monitorb1", {
            url: "/monitorb1"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config dynamic"
                    icon: "fa-share-alt"
                    ordering: 102
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            "cache_mode": "DYNAMIC"
                        title: "create config"
                    ).then(
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
    $stateProvider.state(
        "main.monitorb2", {
            url: "/monitorb2"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config refresh"
                    icon: "fa-share-alt"
                    ordering: 103
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            "cache_mode": "REFRESH"
                        title: "create config"
                    ).then(
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
]).service("icswMonitoringTree", ["$q", "Restangular", "ICSW_URLS", "ICSW_SIGNALS", "icswTools", ($q, Restangular, ICSW_URLS, ICSW_SIGNALS, icswTools) ->
    class icswMonitoringTree
        constructor: (
            @mon_period_list, @mon_notification_list, @host_check_command_list,
            @mon_check_command_list, @mon_check_command_special_list,
            @mon_service_templ_list, @mon_device_templ_list,
            @mon_contact_list, @mon_contactgroup_list, @mon_ext_host_list
        ) ->
            @link()

        link: () =>
            for entry in [
                "mon_period", "mon_notification", "host_check_command",
                "mon_check_command", "mon_check_command_special",
                "mon_service_templ", "mon_device_templ",
                "mon_contact", "mon_contactgroup", "mon_ext_host"
            ]
                @["#{entry}_lut"] = icswTools.build_lut(@["#{entry}_list"])

]).service("icswMonitoringTreeService", ["$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "$rootScope", "ICSW_SIGNALS", "icswMonitoringTree", ($q, Restangular, ICSW_URLS, icswCachingCall, icswTools, $rootScope, ICSW_SIGNALS, icswMonitoringTree) ->
    # loads the monitoring tree
    rest_map = [
        [
            ICSW_URLS.REST_MON_PERIOD_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_NOTIFICATION_LIST, {}
        ]
        [
            ICSW_URLS.REST_HOST_CHECK_COMMAND_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CHECK_COMMAND_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CHECK_COMMAND_SPECIAL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CONTACT_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CONTACTGROUP_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_EXT_HOST_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false
    load_data = (client) ->
        console.log "load called from", client
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** monitoring tree loaded ***"
                _result = new icswMonitoringTree(data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_MON_TREE_LOADED"), _result)
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
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "current": () ->
            return _result
    }
]).service('icswMonitoringUtilService', () ->
    return {
        get_data_incomplete_error: (data, tables) ->
            missing = []
            for table_data in tables
                [model_name, human_name] = table_data
                if not data[model_name].length
                    missing.push(human_name)

            if missing.length
                missing_str = ("a #{n}" for n in missing).join(" and ")
                ret = "Please add #{missing_str}"
            else
                ret = ""
            return ret
    }
).service('icswMonitoringBasicRestService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url) ->
        console.log "get url (monitoringbasicrestservice)", url
        return Restangular.all(url).getList().$object
    data = {
        mon_period         : get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
        user               : get_rest(ICSW_URLS.REST_USER_LIST.slice(1))
        mon_notification   : get_rest(ICSW_URLS.REST_MON_NOTIFICATION_LIST.slice(1))
        mon_service_templ  : get_rest(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1))
        host_check_command : get_rest(ICSW_URLS.REST_HOST_CHECK_COMMAND_LIST.slice(1))
        mon_contact        : get_rest(ICSW_URLS.REST_MON_CONTACT_LIST.slice(1))
        device_group       : get_rest(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1))
        mon_device_templ   : get_rest(ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST.slice(1))
        mon_contactgroup   : get_rest(ICSW_URLS.REST_MON_CONTACTGROUP_LIST.slice(1))
    }
    return data
]).service('icswMonitoringBasicService', ["ICSW_URLS", "icswMonitoringBasicRestService", (ICSW_URLS, icswMonitoringBasicRestService) ->
    get_use_count =  (obj) ->
        return obj.service_check_period.length   # + obj.mon_device_templ_set.length
    return {
        rest_handle        : icswMonitoringBasicRestService.mon_period
        delete_confirm_str : (obj) ->
            return "Really delete monitoring period '#{obj.name}' ?"
        edit_template      : "mon.period.form"
        new_object         : {
            "alias": "new period"
            "mon_range": "00:00-24:00"
            "tue_range": "00:00-24:00"
            "sun_range": "00:00-24:00",
            "wed_range": "00:00-24:00"
            "thu_range": "00:00-24:00"
            "fri_range": "00:00-24:00"
            "sat_range": "00:00-24:00"
        }
        object_created     : (new_obj) -> new_obj.name = ""
        get_use_count      : get_use_count
        delete_ok          : (obj) ->
            return get_use_count(obj) == 0
    }
]).service('icswMonitoringNotificationService', ["ICSW_URLS", "icswMonitoringBasicRestService", (ICSW_URLS, icswMonitoringBasicRestService) ->
    return {
        rest_handle         : icswMonitoringBasicRestService.mon_notification
        edit_template       : "mon.notification.form"
        delete_confirm_str  : (obj) ->
            return "Really delete monitoring notification '#{obj.name}' ?"
        new_object          : {"name" : "", "channel" : "mail", "not_type" : "service"}
        object_created      : (new_obj) -> new_obj.name = ""
    }
]).service('icswMonitoringContactService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", "icswMonitoringUtilService", (ICSW_URLS, Restangular, icswMonitoringRestService, icswMonitoringUtilService) ->
    ret = {
        rest_handle: icswMonitoringRestService.mon_contact
        edit_template: "mon.contact.form"
        delete_confirm_str: (obj) ->
            return "Really delete monitoring contact '#{obj.user}' ?"
        new_object: () ->
            return {
            "user": (entry.idx for entry in icswMonitoringRestService.user)[0]
            "snperiod": (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
            "hnperiod": (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
            "snrecovery": true
            "sncritical": true
            "hnrecovery": true
            "hndown": true
            }
        object_created: (new_obj) -> new_obj.user = null
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringRestService,
                [["mon_period", "period"], ["user", "user"]])
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
]).service('icswMonitoringServiceTemplateService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", "icswMonitoringUtilService", (ICSW_URLS, Restangular, icswMonitoringRestService, icswMonitoringUtilService) ->
    return {
        rest_handle         : icswMonitoringRestService.mon_service_templ
        edit_template       : "mon.service.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete service template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "nsn_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "nsc_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 2
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created    : (new_obj) -> new_obj.name = null
        mon_period        : icswMonitoringRestService.mon_period
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringRestService,
                [["mon_period", "period"]])
    }
]).service('icswMonitoringDeviceTemplateService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", "icswMonitoringUtilService", (ICSW_URLS, Restangular, icswMonitoringRestService, icswMonitoringUtilService) ->
    ret = {
        rest_handle         : icswMonitoringRestService.mon_device_templ
        edit_template       : "mon.device.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete device template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "mon_service_templ" : (entry.idx for entry in icswMonitoringRestService.mon_service_templ)[0]
                "host_check_command" : (entry.idx for entry in icswMonitoringRestService.host_check_command)[0]
                "mon_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "not_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 5
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ndown"     : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created  : (new_obj) -> new_obj.name = null
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringRestService,
                [["mon_period", "period"], ["mon_service_templ", "service template"], ["host_check_command", "host check command"]])
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
]).service('icswMonitoringHostCheckCommandService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    return {
        rest_handle: icswMonitoringRestService.host_check_command
        edit_template: "host.check.command.form"
        delete_confirm_str: (obj) ->
            return "Really delete host check command '#{obj.name}' ?"
        new_object: {"name": ""}
        object_created: (new_obj) -> new_obj.name = null
    }
]).service('icswMonitoringContactgroupService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    ret = {
        rest_handle: icswMonitoringRestService.mon_contactgroup
        edit_template: "mon.contactgroup.form"
        delete_confirm_str: (obj) ->
            "Really delete Contactgroup '#{obj.name}' ?"
        new_object: {"name": ""}
        object_created: (new_obj) -> new_obj.name = null
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
])
