# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
    "icsw.backend.monitoring",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
        "icsw.tools.table", "icsw.tools.button"
    ]
).service("icswMonitoringBasicTree",
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
        "mon_ext_host", "icinga_command",
    ]
    NON_LUT_LIST = [
        "icinga_command"
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
                if entry not in NON_LUT_LIST
                    @["#{entry}_lut"] = _.keyBy(@["#{entry}_list"], "idx")
            # update icinga_command
            for entry in @icinga_command_list
                entry.$$arguments = (_val.name for _val in entry.args)
                # private command
                entry.$$private = false
                if _.some(_val.match(/_id$/) for _val in entry.$$arguments)
                    entry.$$private = true
                if _.some(_val in entry.$$arguments for _val in ["value", "varname", "varvalue"])
                    entry.$$private = true
                console.log entry.name, entry.$$arguments

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
        [
            ICSW_URLS.MON_ALL_ICINGA_CMDS, {}
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
])
