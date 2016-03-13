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
            # console.log "Overwrite all networktree entries"
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
                # console.log "*** network tree loaded ***"
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
        "reload": (client) ->
            # reloads from server
            return load_data(client).promise
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "current": () ->
            return _result
    }
]).service("icswPeerHelperObject", [() ->
    class icswPeerHelperObject
        constructor: () ->
            @info = "not set"
            @list = []
            @pks = []

        sort: () =>
            @list = _.orderBy(
                @list
                ["device_group_name", "info_string"]
                ["desc", "desc"]
            )
        feed: (obj) =>
            if obj.idx not in @pks
                @list.push(obj)
                @pks.push(obj.idx)

]).service("icswPeerInformation",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswSimpleAjaxCall", "icswPeerHelperObject",
(
    icswTools, ICSW_URLS, $q, Restangular, icswSimpleAjaxCall, icswPeerHelperObject
) ->
    class icswPeerInformation
        constructor: (@list, @peer_list, @device_pk_list) ->
            @build_luts()

        update_all: (list, peer_list) =>
            @list.length = 0
            @peer_list.length = 0
            for entry in list
                @list.push(entry)
            for entry in peer_list
                @peer_list.push(entry)
            @build_luts()

        build_luts: () =>
            # all peers
            @lut = icswTools.build_lut(@list)
            # all peerable netdevices (may shadow the enriched devices from tree, use only as a fallback)
            @peer_lut = icswTools.build_lut(@peer_list)
            @nd_lut = {}
            for entry in @list
                if entry.s_netdevice not of @nd_lut
                    @nd_lut[entry.s_netdevice] = []
                @nd_lut[entry.s_netdevice].push(entry)
                if entry.d_netdevice not of @nd_lut
                    @nd_lut[entry.d_netdevice] = []
                @nd_lut[entry.d_netdevice].push(entry)
            # console.log @nd_lut

        find_missing_devices: (dev_tree) =>
            # return a list of device pks which are missing from the device tree or where the network_info is missing
            _peer_list = _.union(
                (entry.s_device for entry in @list)
                (entry.d_device for entry in @list)
            )
            # console.log "1", _peer_list
            _present_list = (entry.idx for entry in dev_tree.all_list when entry.$$_enrichment_info.is_loaded("network_info"))
            # console.log "2", _present_list
            _diff_list = _.difference(_peer_list, _present_list)
            # console.log "3", _diff_list
            return _diff_list

        find_remote_devices: (dev_tree, local_devices) =>
            _local_pks = (dev.idx for dev in local_devices)
            # return the pks of all devices remote (== not local)
            _peer_list = _.union(
                (entry.s_device for entry in @list)
                (entry.d_device for entry in @list)
            )
            _remote_list = _.difference(_peer_list, _local_pks)
            return _remote_list

        enrich_device_tree: (dev_tree, local_ho, remote_ho) =>
            # set the peer information for all devices in dev_list
            # type: (l)ocal or (r)remote (for local and remote helper objects)
            # s/d_type: source / dest entries
            for iter_obj in [{"ho": local_ho, "type": "l"}, {"ho": remote_ho, "type": "r"}]
                ho = iter_obj.ho
                ho.peer_list = []
                peer_type = iter_obj.type
                for dev in ho.devices
                    dev.num_peers = 0
                    for nd in dev.netdevice_set
                        if nd.idx of @nd_lut
                            # netdevice part of a peer table
                            dev.num_peers += @nd_lut[nd.idx].length
                            for peer in @nd_lut[nd.idx]
                                ho.peer_list.push(peer)
                                # set peer flags
                                if peer.s_netdevice == nd.idx
                                    peer.$$s_type = peer_type
                                if peer.d_netdevice == nd.idx
                                    peer.$$d_type = peer_type

        build_peer_helper: (device_tree, cur_peer, local_ho, remote_ho, peer_side, helper_mode) =>
            # returns a sorted peer list for the frontend
            # peer_type : (s)ource or (d)estination
            # helper_mode may be one of
            # e ... edit existing peer
            # d ... create new peer for device
            get_netdevice = (nd_side) ->
                nd_idx = cur_peer["#{nd_side}_netdevice"]
                if cur_peer["$$#{nd_side}_type"] == "l"
                    return local_ho.netdevice_lut[nd_idx]
                else
                    return remote_ho.netdevice_lut[nd_idx]

            helper = new icswPeerHelperObject()
            # reference netdevice
            ref_nd = get_netdevice(peer_side)
            # if helper_mode == "d"
            if helper_mode == "e"
                if ref_nd.routing
                    # add netowrk topology central nodes
                    _add_ntcn = true
                    # add devices nodes
                    _add_device = false
                else
                    _add_ntcn = false
                    _add_device = false
            else if helper_mode == "d"
                if peer_side == "s"
                    _add_ntcn = false
                    _add_device = true
                else
                    _add_ntcn = true
                    _add_device = false
            else if helper_mode == "n"
                if peer_side == "s"
                    _add_ntcn = false
                    _add_device = false
                else
                    _add_ntcn = true
                    _add_device = false
            if _add_ntcn
                # step 1: collect all peerable netdevices from the device tree
                # (only if the reference netdevice is a routing node)
                for dev in device_tree.enabled_list
                    if dev.netdevice_set?
                        for nd in dev.netdevice_set
                            if nd.routing
                                nd.device_group_name = dev.device_group_name
                                nd.info_string = "#{nd.devname} (#{nd.penalty}) on #{dev.full_name}"
                                helper.feed(nd)
                # step 2: add possible peers for devices without the required enrichment info
                for nd_pk, nd_info of @peer_lut
                    nd_info.info_string = "#{nd_info.devname} (#{nd_info.penalty}) on #{nd_info.full_name}"
                    helper.feed(nd_info)
            ref_dev = device_tree.all_lut[ref_nd.device]
            if _add_device
                # step 3: add device local netdevices
                for nd in ref_dev.netdevice_set
                    nd.info_string = "#{nd.devname} (#{nd.penalty}) on #{ref_dev.full_name}"
                    helper.feed(nd)
            # step 4: add reference netdevice
            ref_nd.device_group_name = ref_dev.device_group_name
            ref_nd.info_string = "#{ref_nd.devname} (#{ref_nd.penalty}) on #{ref_dev.full_name}"
            helper.feed(ref_nd)
            helper.sort()
            return helper

    # peer creation / deletion
        create_peer: (new_peer, device_tree) =>
            # create new peer
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_PEER_INFORMATION_LIST.slice(1)).post(new_peer).then(
                (new_obj) =>
                    @_fetch_peer(new_obj.idx, defer, "created peer")
                (not_ok) ->
                    defer.reject("peer not created")
            )
            return defer.promise

        delete_peer: (del_peer) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_peer, ICSW_URLS.REST_PEER_INFORMATION_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_peer.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == del_peer.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_peer: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_PEER_INFORMATION_LIST.slice(1)).get({"idx": pk}).then(
                (new_peer) =>
                    new_peer = new_peer[0]
                    @list.push(new_peer)
                    @build_luts()
                    defer.resolve(msg)
            )


]).service("icswPeerInformationService", [
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", "icswPeerInformation", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools, icswPeerInformation, $rootScope, ICSW_SIGNALS,
) ->
    load_data = (client, dev_list) ->
        _defer = $q.defer()
        w_list = [
            icswCachingCall.fetch(
                client
                ICSW_URLS.REST_USED_PEER_LIST
                {
                    "primary_dev_pks": angular.toJson((dev.idx for dev in dev_list))
                }
                []
            )
            icswCachingCall.fetch(
                client
                ICSW_URLS.REST_PEERABLE_NETDEVICE_LIST
                {}
                []
            )
        ]
        $q.all(w_list).then(
            (data) ->
                # console.log "*** peer information loaded ***"
                _defer.resolve(new icswPeerInformation(data[0], data[1], (dev.idx for dev in dev_list)))
        )
        return _defer

    reload_data = (client, peer_info) ->
        _defer = $q.defer()
        w_list = [
            icswCachingCall.fetch(
                client
                ICSW_URLS.REST_USED_PEER_LIST
                {
                    "primary_dev_pks": angular.toJson(peer_info.device_pk_list)
                }
                []
            )
            icswCachingCall.fetch(
                client
                ICSW_URLS.REST_PEERABLE_NETDEVICE_LIST
                {}
                []
            )
        ]
        $q.all(w_list).then(
            (data) ->
                # console.log "*** peer information reloaded ***"
                peer_info.update_all(data[0], data[1])
                _defer.resolve(peer_info)
        )
        return _defer

    return {
        "load": (client, dev_list) ->
            # loads from server
            return load_data(client, dev_list).promise
        "reload": (client, peer_info) ->
            return reload_data(client, peer_info).promise
    }
])
