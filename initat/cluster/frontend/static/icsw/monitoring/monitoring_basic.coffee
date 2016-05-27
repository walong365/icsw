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

monitoring_basic_module = angular.module(
    "icsw.monitoring.monitoring_basic",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
        "icsw.tools.table", "icsw.tools.button"
    ]
).directive("icswMonitoringBasic",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict:"EA"
        template: $templateCache.get("icsw.monitoring.basic")
        controller: "icswMonitoringBasicCtrl"
    }
]).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.monitorbasics", {
            url: "/monitorbasics"
            template: "<icsw-monitoring-basic></icsw-monitoring-basic>"
            icswData: icswRouteExtensionProvider.create
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
    ).state(
        "main.monitorredirect", {
            url: "/monitorredirect"
            template: "<h2>Redirecting...</h2>"
            icswData: icswRouteExtensionProvider.create
                    redirect_to_from_on_error: true
                    menuEntry:
                        menukey: "mon"
                        name: "Icinga"
                        icon: "fa-share-alt"
                        ordering: 120
                    rights: ["mon_check_command.redirect_to_icinga"]
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
    ).state(
        "main.monitorb0", {
            url: "/monitorb0"
            icswData: icswRouteExtensionProvider.create
                redirect_to_from_on_error: true
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config cached"
                    icon: "fa-share-alt"
                    labelClass: "label-success"
                    ordering: 101
                    preSpacer: true
                rights: ["mon_check_command.create_config"]
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    console.log "REDIR"
                    # todo: add icswMenuProgressService
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            cache_mode: "ALWAYS"
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
    ).state(
        "main.monitorb1", {
            url: "/monitorb1"
            icswData: icswRouteExtensionProvider.create
                redirect_to_from_on_error: true
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config dynamic"
                    icon: "fa-share-alt"
                    labelClass: "label-warning"
                    ordering: 102
                rights: ["mon_check_command.create_config"]
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            cache_mode: "DYNAMIC"
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
    ).state(
        "main.monitorb2", {
            url: "/monitorb2"
            icswData: icswRouteExtensionProvider.create
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config refresh"
                    icon: "fa-share-alt"
                    labelClass: "label-danger"
                    ordering: 103
                    postSpacer: true
                rights: ["mon_check_command.create_config"]
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            cache_mode: "REFRESH"
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
]).service("icswMonitoringBasicTree",
[
    "$q", "Restangular", "ICSW_URLS", "ICSW_SIGNALS", "icswTools",
(
    $q, Restangular, ICSW_URLS, ICSW_SIGNALS, icswTools
) ->
    ELIST = [
        "mon_period", "mon_notification",
        "host_check_command", "mon_check_command",
        "mon_check_command_special",
        "mon_service_templ", "mon_device_templ",
        "mon_contact", "mon_contactgroup",
        "mon_ext_host"
    ]
    class icswMonitoringBasicTree
        constructor: (args...) ->
            for entry in ELIST
                @["#{entry}_list"] = []
            @update(args...)
            @missing_info = {
                "mon_contact": [
                    ["mon_period", "period"]
                ]
                "mon_service_templ": [
                    ["mon_period", "period"]
                ]
                "mon_device_templ": [
                    ["mon_period", "period"]
                    ["mon_service_templ", "service template"]
                    ["host_check_command", "host check command"]
                ]
            }

        update: (args...) =>
            for [entry, _list] in _.zip(ELIST, args)
                @["#{entry}_list"].length = 0
                for _el in _list
                    @["#{entry}_list"].push(_el)
            @build_luts()

        build_luts: () =>
            for entry in ELIST
                @["#{entry}_lut"] = _.keyBy(@["#{entry}_list"], "idx")

        # create / delete mon_period

        create_mon_period: (new_per) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1)).post(new_per).then(
                (created) =>
                    @mon_period_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_period: (del_per) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_per, ICSW_URLS.REST_MON_PERIOD_DETAIL.slice(1).slice(0, -2))
            del_per.remove().then(
                (removed) =>
                    _.remove(@mon_period_list, (entry) -> return entry.idx == del_per.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_period

        create_mon_notification: (new_not) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_NOTIFICATION_LIST.slice(1)).post(new_not).then(
                (created) =>
                    @mon_notification_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_notification: (del_not) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_not, ICSW_URLS.REST_MON_NOTIFICATION_DETAIL.slice(1).slice(0, -2))
            del_not.remove().then(
                (removed) =>
                    _.remove(@mon_notification_list, (entry) -> return entry.idx == del_not.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_service_templ

        create_mon_service_templ: (new_st) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1)).post(new_st).then(
                (created) =>
                    @mon_service_templ_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_service_templ: (del_st) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_st, ICSW_URLS.REST_MON_SERVICE_TEMPL_DETAIL.slice(1).slice(0, -2))
            del_st.remove().then(
                (removed) =>
                    _.remove(@mon_service_templ_list, (entry) -> return entry.idx == del_st.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_device_templ

        create_mon_device_templ: (new_dt) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST.slice(1)).post(new_dt).then(
                (created) =>
                    @mon_device_templ_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_device_templ: (del_dt) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_dt, ICSW_URLS.REST_MON_DEVICE_TEMPL_DETAIL.slice(1).slice(0, -2))
            del_dt.remove().then(
                (removed) =>
                    _.remove(@mon_device_templ_list, (entry) -> return entry.idx == del_dt.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete host_check_command

        create_host_check_command: (new_hcc) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_HOST_CHECK_COMMAND_LIST.slice(1)).post(new_hcc).then(
                (created) =>
                    @host_check_command_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_host_check_command: (del_hcc) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_hcc, ICSW_URLS.REST_HOST_CHECK_COMMAND_DETAIL.slice(1).slice(0, -2))
            del_hcc.remove().then(
                (removed) =>
                    _.remove(@host_check_command_list, (entry) -> return entry.idx == del_hcc.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_contact

        create_mon_contact: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_CONTACT_LIST.slice(1)).post(new_obj).then(
                (created) =>
                    @mon_contact_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_contact: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.REST_MON_CONTACT_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@mon_contact_list, (entry) -> return entry.idx == del_obj.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_contactgroup

        create_mon_contactgroup: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_CONTACTGROUP_LIST.slice(1)).post(new_obj).then(
                (created) =>
                    @mon_contactgroup_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_contactgroup: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.REST_MON_CONTACTGROUP_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@mon_contactgroup_list, (entry) -> return entry.idx == del_obj.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

]).service("icswMonitoringBasicTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "$rootScope",
    "ICSW_SIGNALS", "icswMonitoringBasicTree",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTools, $rootScope,
    ICSW_SIGNALS, icswMonitoringBasicTree
) ->
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
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** basic monitoring tree loaded ***"
                _result = new icswMonitoringBasicTree(data...)
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
    }
]).controller("icswMonitoringBasicCtrl",
[
    "$scope", "$q", "icswMonitoringBasicTreeService",
(
    $scope, $q, icswMonitoringBasicTreeService
) ->
    $scope.struct = {
        # tree valid
        tree_valid: false
        # basic tree
        basic_tree: undefined
    }
    $scope.reload = () ->
        icswMonitoringBasicTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.basic_tree = data
                $scope.struct.tree_valid = true
                # console.log $scope.struct
        )
    $scope.reload()

]).service("icswMonitoringUtilService",
[
    "icswComplexModalService", "$compile", "$templateCache", "$q", "toaster",
    "Restangular", "ICSW_URLS",
(
    icswComplexModalService, $compile, $templateCache, $q, toaster,
    Restangular, ICSW_URLS,
) ->
    # helper functions for monitoring_basic
    _device_list_warned = false

    return {
        get_data_incomplete_error: (tree, table) ->
            if not tree?
                return "missing tree"
            if not table of tree.missing_info
                ret = ""
            else
                missing = []
                for _tuple in tree.missing_info[table]
                    if _tuple.length == 3
                        # handle extra reference name
                        [_ref, model_name, human_name] = _tuple
                        _ref = tree[_ref]
                    else
                        _ref = tree
                        [model_name, human_name] = _tuple
                    _list_name = "#{model_name}_list"
                    if _list_name of _ref
                        if not _ref[_list_name].length
                            missing.push(human_name)
                    else
                        if _list_name == "device_list"
                            if not _device_list_warned
                                console.warn "device_list is not set in cluster_tree, fixme"
                                _device_list_warned = true
                        else
                            console.error "missing list #{_list_name}"

                if missing.length
                    missing_str = ("a #{n}" for n in missing).join(" and ")
                    ret = "Please add #{missing_str}"
                else
                    ret = ""
            return ret

        create_or_edit: (tree, scope, create, obj, obj_name, bu_def, template_name, template_title)  ->
            if not create
                dbu = new bu_def()
                dbu.create_backup(obj)
            # new sub_scope
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj

            # for fields, tree can be the basic or the cluster tree
            sub_scope.tree = tree
            if scope.user_group_tree?
                sub_scope.user_group_tree = scope.user_group_tree
            if scope.device_tree?
                sub_scope.device_tree = scope.device_tree
            if tree.basic_tree?
                sub_scope.basic_tree = tree.basic_tree

            # form error
            sub_scope.form_error = (field_name) ->
                if sub_scope.form_data[field_name].$valid
                    return ""
                else
                    return "has-error"

            icswComplexModalService(
                {
                    message: $compile($templateCache.get(template_name))(sub_scope)
                    title: template_title
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                tree["create_#{obj_name}"](sub_scope.edit_obj).then(
                                    (new_period) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                _URL = ICSW_URLS["REST_" + _.toUpper(obj_name) + "_DETAIL"].slice(1).slice(0, -2)
                                Restangular.restangularizeElement(null, sub_scope.edit_obj, _URL)
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        tree.build_luts()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    sub_scope.$destroy()
            )

    }
]).service("icswMonitoringBasicPeriodService",
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonPeriodBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonPeriodBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_period_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    alias: "new period"
                    mon_range: "00:00-24:00"
                    tue_range: "00:00-24:00"
                    wed_range: "00:00-24:00"
                    thu_range: "00:00-24:00"
                    fri_range: "00:00-24:00"
                    sat_range: "00:00-24:00"
                    sun_range: "00:00-24:00"
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_period"
                icswMonPeriodBackup
                "icsw.mon.period.form"
                "Monitoring Period"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringPeriod '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_period(obj).then(
                        () ->
                            console.log "mon_period deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_period")
    }
]).service('icswMonitoringBasicNotificationService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonNotificationBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonNotificationBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_notification_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    channel: "mail"
                    not_type: "service"
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_notification"
                icswMonNotificationBackup
                "icsw.mon.notification.form"
                "Monitoring Notification"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringNotification '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_notification(obj).then(
                        () ->
                            console.log "mon_not deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_notification")
    }
]).service('icswMonitoringBasicServiceTemplateService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonServiceTemplBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonServiceTemplBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_service_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    nsn_period: basic_tree.mon_period_list[0].idx
                    nsc_period: basic_tree.mon_period_list[0].idx
                    max_attempts: 1
                    ninterval: 2
                    check_interval: 2
                    retry_interval: 2
                    nrecovery: true
                    ncritical: true
                    low_flap_threshold: 20
                    high_flap_threshold: 80
                    freshness_threshold: 60
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_service_templ"
                icswMonServiceTemplBackup
                "icsw.mon.service.templ.form"
                "Monitoring Service Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringServiceTemplate '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_service_templ(obj).then(
                        () ->
                            console.log "mon_service_templ deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_service_templ")
    }
]).service('icswMonitoringBasicDeviceTemplateService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonDeviceTemplBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonDeviceTemplBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_device_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    mon_service_templ: basic_tree.mon_service_templ_list[0].idx
                    host_check_command: basic_tree.host_check_command_list[0].idx
                    mon_period: basic_tree.mon_period_list[0].idx
                    not_period: basic_tree.mon_period_list[0].idx
                    max_attempts: 1
                    ninterval: 5
                    check_interval: 2
                    retry_interval: 2
                    nrecovery: true
                    ndown: true
                    ncritical: true
                    low_flap_threshold: 20
                    high_flap_threshold: 80
                    freshness_threshold: 60
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_device_templ"
                icswMonDeviceTemplBackup
                "icsw.mon.device.templ.form"
                "Monitoring Device Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringDeviceTemplate '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_device_templ(obj).then(
                        () ->
                            console.log "mon_device_templ deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_device_templ")
    }
]).service('icswMonitoringBasicHostCheckCommandService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswHostCheckCommandBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswHostCheckCommandBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.host_check_command_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    command_line: ""
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "host_check_command"
                icswHostCheckCommandBackup
                "icsw.host.check.command.form"
                "Monitoring HostCheck Command"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete HostCheckCommand '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_host_check_command(obj).then(
                        () ->
                            console.log "host_check_command deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "host_check_command")
    }
]).service('icswMonitoringBasicMonContactService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular", "icswUserGroupTreeService",
    "icswToolsSimpleModalService", "icswMonContactBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular, icswUserGroupTreeService,
    icswToolsSimpleModalService, icswMonContactBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    user_group_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringBasicTreeService.load(scope.$id)
                    icswUserGroupTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    basic_tree = data[0]
                    user_group_tree = data[1]
                    scope.basic_tree = basic_tree
                    scope.user_group_tree = user_group_tree
                    defer.resolve(basic_tree.mon_contact_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    user: user_group_tree.user_list[0].idx
                    snperiod: basic_tree.mon_period_list[0].idx
                    hnperiod: basic_tree.mon_period_list[0].idx
                    snrecovery: true
                    sncritical: true
                    hnrecovery: true
                    hndown: true
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_contact"
                icswMonContactBackup
                "icsw.mon.contact.form"
                "Monitoring Contact"
            )

        get_notifications: (obj) ->
            _list = []
            for mnt in obj.notifications
                mnt = basic_tree.mon_notification_lut[mnt]
                _list.push(mnt.name)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringContact '#{obj.idx}' ?").then(
                () =>
                    basic_tree.delete_mon_contact(obj).then(
                        () ->
                            console.log "mon_contact deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_contact")
    }
]).service('icswMonitoringBasicMonContactgroupService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular", "icswUserGroupTreeService",
    "icswToolsSimpleModalService", "icswMonContactgroupBackup", "icswMonitoringUtilService",
    "icswDeviceTreeService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular, icswUserGroupTreeService,
    icswToolsSimpleModalService, icswMonContactgroupBackup, icswMonitoringUtilService,
    icswDeviceTreeService,
) ->
    basic_tree = undefined
    user_group_tree = undefined
    device_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringBasicTreeService.load(scope.$id)
                    icswUserGroupTreeService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    basic_tree = data[0]
                    user_group_tree = data[1]
                    device_tree = data[2]
                    scope.basic_tree = basic_tree
                    scope.user_group_tree = user_group_tree
                    scope.device_tree = device_tree
                    defer.resolve(basic_tree.mon_contactgroup_list)
            )
            return defer.promise
            
        get_members: (obj) ->
            _list = []
            for member in obj.members
                user = user_group_tree.user_lut[basic_tree.mon_contact_lut[member].user]
                _list.push(user.login)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        get_device_groups: (obj) ->
            _list = []
            for dg in obj.device_groups
                dg = device_tree.group_lut[dg]
                _list.push(dg.name)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        get_service_templates: (obj) ->
            _list = []
            for mst in obj.service_templates
                mst = basic_tree.mon_service_templ_lut[mst]
                _list.push(mst.name)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    alias: ""
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_contactgroup"
                icswMonContactgroupBackup
                "icsw.mon.contactgroup.form"
                "Monitoring ContactGroup"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete ContactGroup '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_contactgroup(obj).then(
                        () ->
                            console.log "mon_contactgroup deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "host_contactgroup")
    }
])
