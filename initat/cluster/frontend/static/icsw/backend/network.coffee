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

    # network tree handling (including speed and types)

    "icsw.backend.network",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.tools.tree", "icsw.user",
    ]
).service("icswNetworkTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswSimpleAjaxCall",
(
    icswTools, ICSW_URLS, $q, Restangular, icswSimpleAjaxCall
) ->
    class icswNetworkTree
        constructor: (@nw_list, @nw_speed_list, @nw_type_list, @nw_device_type_list, @nw_snmp_type_list) ->
            @build_luts()

        update_all: (nw_list, nw_speed_list, nw_type_list, nw_device_type_list, nw_snmp_type_list) =>
            # overwrite all entries
            console.log "Overwrite all networktree entries"
            _dict = {
                "nw_list": nw_list
                "nw_speed_list": nw_speed_list
                "nw_type_list": nw_type_list
                "nw_device_type_list": nw_device_type_list
                "nw_snmp_type_list": nw_snmp_type_list
            }
            for key, val of _dict
                @[key].length = 0
                for entry in val
                    @[key].push(entry)
            @build_luts()

        build_luts: () =>
            for entry in ["nw", "nw_speed", "nw_type", "nw_device_type", "nw_snmp_type"]
                @["#{entry}_lut"] = icswTools.build_lut(@["#{entry}_list"])
            @link()

        reorder: () =>
            # called after structures have been created / updated / deleted
            @build_luts()

        link: () =>
            # create links between networks and types

        # create functions

        create_network_type: (obj_def) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_NETWORK_TYPE_LIST.slice(1)).post(obj_def).then(
                (new_obj) =>
                    @nw_type_list.push(new_obj)
                    @reorder()
                    d.resolve("created")
                (not_ok) =>
                    d.reject("create error")
            )
            return d.promise

        create_network_device_type: (obj_def) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST.slice(1)).post(obj_def).then(
                (new_obj) =>
                    @nw_device_type_list.push(new_obj)
                    @reorder()
                    d.resolve("created")
                (not_ok) =>
                    d.reject("create error")
            )
            return d.promise

        create_network: (obj_def) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).post(obj_def).then(
                (new_obj) =>
                    @nw_list.push(new_obj)
                    @reorder()
                    d.resolve("created")
                (not_ok) =>
                    d.reject("create error")
            )
            return d.promise

        # delete functions

        delete_network_type: (obj) =>
            d = $q.defer()
            obj.remove().then(
                (ok) =>
                    _.remove(@nw_type_list, (entry) -> return entry.idx == obj.idx)
                    @reorder()
                    d.resolve("deleted")
                (notok) =>
                    d.reject("not deleted")
            )
            return d.promise

        delete_network_device_type: (obj) =>
            d = $q.defer()
            obj.remove().then(
                (ok) =>
                    _.remove(@nw_device_type_list, (entry) -> return entry.idx == obj.idx)
                    @reorder()
                    d.resolve("deleted")
                (notok) =>
                    d.reject("not deleted")
            )
            return d.promise

        delete_network: (obj) =>
            d = $q.defer()
            obj.remove().then(
                (ok) =>
                    _.remove(@nw_list, (entry) -> return entry.idx == obj.idx)
                    @reorder()
                    d.resolve("deleted")
                (notok) =>
                    d.reject("not deleted")
            )
            return d.promise

]).service("icswNetworkTreeService", [
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", "icswNetworkTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools, icswNetworkTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_NETWORK_LIST, {}
        ]
        [
            ICSW_URLS.REST_NETDEVICE_SPEED_LIST, {}
        ]
        [
            ICSW_URLS.REST_NETWORK_TYPE_LIST, {}
        ]
        [
            ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST, {}
        ]
        [
            ICSW_URLS.REST_SNMP_NETWORK_TYPE_LIST, {}
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
                console.log "*** network tree loaded ***"
                if _result?
                    _result.update_all(data[0], data[1], data[2], data[3], data[4])
                else
                    _result = new icswNetworkTree(data[0], data[1], data[2], data[3], data[4])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_NETWORK_TREE_LOADED"), _result)
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
            # loads from server
            return load_data(client).promise
        "fetch": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "current": () ->
            return _result
    }
]).service("icswPeerInformation",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswSimpleAjaxCall",
(
    icswTools, ICSW_URLS, $q, Restangular, icswSimpleAjaxCall
) ->
    class icswPeerInformation
        constructor: () ->

]).service("icswPeerInformationService", [
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", "icswPeerInformation", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools, icswPeerInformation, $rootScope, ICSW_SIGNALS,
) ->
    load_data = (client) ->
        _defer = $q.defer()
        icswCachingCall.fetch(client, ICSW_URLS.REST_NETDEVICE_PEER_LIST, {}, []).then(
            (data) ->
                console.log "*** peer information loaded ***"
                _defer.resolve(new icswPeerInformation(data))
        )
        return _defer
    return {
        "load": (client, dev_list) ->
            # loads from server
            return load_data(client).promise
    }
])
