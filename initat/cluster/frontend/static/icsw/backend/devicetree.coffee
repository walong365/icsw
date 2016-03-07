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

    # device tree handling (including device enrichment)

    "icsw.backend.devicetree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.tools.tree", "icsw.user",
    ]
).service("icswDeviceTreeHelper", [() ->
    # helper service for global (== selection-wide) luts and lists
    class icswDeviceTreeHelper
        constructor: (@tree, @devices) ->
            @netdevice_list = []
            @netdevice_lut = {}
            @net_ip_list = []
            @net_ip_lut = {}

]).service("icswDeviceTreeHelperService", ["icswDeviceTreeHelper", (icswDeviceTreeHelper) ->

    return {
        "create": (tree, devices) ->
            return new icswDeviceTreeHelper(tree, devices)
    }

]).service("icswEnrichmentInfo", ["icswNetworkTreeService", "icswTools", (icswNetworkTreeService, icswTools) ->
    # stores info about already fetched additional info from server
    class icswEnrichmentInfo
        constructor: (@device) ->
            # device may be the device_tree for global instance
            @loaded = []
            @device.num_boot_ips = 0
            @device.num_netdevices = 0
            @device.num_netips = 0
            @device.num_peers = 0

        is_scalar: (req) =>
            return req in ["disk_info", "snmp_info"]

        clear_global_infos: (dth_obj, en_req) =>
            # clear global infos for devices where we requested new info
            for req, dev_pks of en_req
                cgi_name = "pre_g_#{req}"
                if @[cgi_name]?
                    @[cgi_name](dth_obj, dev_pks)

        is_loaded: (req) =>
            return req in @loaded

        # global pre calls
        pre_g_network_info: (dth_obj, dev_pks) =>
            # remove all references to devices in dev_list from the global nd_lut
            if dth_obj.netdevice_list?
                dev_pks = (dev.idx for dev in dth_obj.devices when dev.idx in dev_pks)
                _.remove(dth_obj.netdevice_list, (entry) -> return entry.device not in dev_pks)
                nd_pks = (nd.idx for nd in dth_obj.netdevice_list)
                _.remove(dth_obj.net_ip_list, (entry) -> return entry.netdevice not in nd_pks)
                dth_obj.netdevice_lut = icswTools.build_lut(dth_obj.netdevice_list)
                dth_obj.net_ip_lut = icswTools.build_lut(dth_obj.net_ip_list)

        # global post calls
        post_g_network_info: (local_en, dth_obj) =>
            # FIXME, todo: remove entries when a device gets delete
            for nd in local_en.device.netdevice_set
                nd.$$devicename = @device.all_lut[nd.device].full_name
                dth_obj.netdevice_lut[nd.idx] = nd
                dth_obj.netdevice_list.push(nd)
                for ip in nd.net_ip_set
                    ip.$$devicename = nd.$$devicename
                    ip.$$devname = nd.devname
                    dth_obj.net_ip_lut[ip.idx] = ip
                    dth_obj.net_ip_list.push(ip)
            dth_obj.netdevice_list = _.orderBy(
                dth_obj.netdevice_list,
                ["$$devicename", "devname"],
                ["asc", "asc"],
            )
            dth_obj.net_ip_list = _.orderBy(
                dth_obj.net_ip_list,
                ["$$devicename", "$$devname", "ip"],
                ["asc", "asc", "asc"],
            )

        get_attr_name: (req) =>
            _lut = {
                "network_info": "netdevice_set"
                "monitoring_hint_info": "monitoring_hint_set"
                "disk_info": "act_partition_table"
                "com_info": "com_capability_list"
                "snmp_info": "devicesnmpinfo"
                "snmp_schemes_info": "snmp_schemes"
            }
            if req of _lut
                return _lut[req]
            else
                throw new Error("Unknown EnrichmentKey #{req}")

        clear_infos: (en_req) =>
            # clear already present infos
            for req, dev_pks of en_req
                if @device.idx in dev_pks
                    if @is_scalar(req)
                        @device[@get_attr_name(req)] = undefined
                    else
                        @device[@get_attr_name(req)].length = 0

        build_luts: (req_list, g_en, dth_obj) =>
            # build luts
            for req in req_list
                _call_name = "post_#{req}"
                if @[_call_name]?
                    @[_call_name]()
                _gp_call_name = "post_g_#{req}"
                if g_en[_gp_call_name]?
                    g_en[_gp_call_name](@, dth_obj)

        # post calls

        post_network_info: () =>
            _net = icswNetworkTreeService.current()
            @device.netdevice_lut = icswTools.build_lut(@device.netdevice_set)
            @device.num_netdevices = 0
            @device.num_netips = 0
            num_bootips = 0
            # set values
            for net_dev in @device.netdevice_set
                @device.num_netdevices++
                net_dev.num_netips = 0
                net_dev.num_bootips = 0
                for net_ip in net_dev.net_ip_set
                    @device.num_netips++
                    net_dev.num_netips++
                    if _net.nw_lut[net_ip.network].network_type_identifier == "b"
                        num_bootips++
                        net_dev.num_bootips++
            @device.num_boot_ips = num_bootips
            # console.log "blni", @device.full_name, num_bootips

        build_request: (req_list) =>
            # returns a list (dev_pk, enrichments_to_load)
            fetch_list = []
            for req in req_list
                if req not in @loaded
                    fetch_list.push(req)
                    if @is_scalar(req)
                        @device[@get_attr_name(req)] = undefined
                    else
                        @device[@get_attr_name(req)] = []
            return [@device.idx, fetch_list]

        feed_result: (key, result) =>
            if key not in @loaded
                @loaded.push(key)
            # store info
            if @is_scalar(key)
                @device[@get_attr_name(key)] = result
            else
                @device[@get_attr_name(key)].push(result)

        merge_requests: (req_list) =>
            # merges all requests from build_request
            to_load = {}
            for d_req in req_list
                for req in d_req[1]
                    if req not of to_load
                        to_load[req] = []
                    to_load[req].push(d_req[0])
            return to_load

        feed_results: (result) =>
            # feed result into device_tree
            for key, obj_list of result
                for obj in obj_list
                    if obj.device?
                        _pk = obj.device
                        @device.all_lut[_pk].$$_enrichment_info.feed_result(key, obj)
                    else
                        console.log obj
                        throw new Error("No device attribute found in object")

]).service("icswDeviceTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswEnrichmentInfo", "icswSimpleAjaxCall",
(
    icswTools, ICSW_URLS, $q, Restangular, icswEnrichmentInfo, icswSimpleAjaxCall
) ->
    class icswDeviceTree
        constructor: (full_list, cat_list, group_list, domain_tree) ->
            @cat_list = cat_list
            @group_list = group_list
            @all_list = []
            @enabled_list = []
            @disabled_list = []
            @domain_tree = domain_tree
            @enricher = new icswEnrichmentInfo(@)
            @build_luts(full_list)

        reorder: () =>
            # device/group names or device <-> group relationships might have changed, sort
            for dev in @all_list
                group = @group_lut[dev.device_group]
                dev.device_group_name = group.name
                dev._nc_device_group_name = _.toLower(dev.device_group_name)
                dev.full_name = @domain_tree.get_full_name(dev)
                dev._nc_name = _.toLower(dev.name)
            # see code in rest_views
            @build_luts(
                _.orderBy(
                    @all_list
                    ["is_cluster_device_group", "_nc_device_group_name", "is_meta_device", "_nc_name"]
                    ["desc", "asc", "desc", "asc"]
                )
            )

        build_luts: (full_list) =>
            # build luts and create enabled / disabled lists
            @all_list.length = 0
            @enabled_list.length = 0
            @disabled_list.length = 0
            @enabled_lut = {}
            @disabled_lut = {}
            _disabled_groups = []
            for _entry in full_list
                @all_list.push(_entry)
                if not _entry.is_meta_device and _entry.device_group in _disabled_groups
                    @disabled_list.push(_entry)
                else if _entry.enabled
                    @enabled_list.push(_entry)
                else
                    if _entry.is_meta_device
                        _disabled_groups.push(_entry.device_group)
                    @disabled_list.push(_entry)
            @enabled_lut = icswTools.build_lut(@enabled_list)
            @disabled_lut = icswTools.build_lut(@disabled_list)
            @all_lut = icswTools.build_lut(@all_list)
            @group_lut = icswTools.build_lut(@group_list)
            @cat_lut = icswTools.build_lut(@cat_list)
            # console.log @enabled_list.length, @disabled_list.length, @all_list.length
            @link()

        link: () =>
            # create links between groups and devices
            for group in @group_list
                # reference to all devices
                group.devices = []
            for cat in @cat_list
                cat.devices = []
            for entry in @all_list
                # add enrichment info
                if not entry.$$_enrichment_info?
                    entry.$$_enrichment_info = new icswEnrichmentInfo(entry)
                # do not set group here to prevent circular dependencies in serializer
                # entry.group_object = @group_lut[entry.device_group]
                @group_lut[entry.device_group].devices.push(entry.idx)
                for cat in entry.categories
                    @cat_lut[cat].devices.push(entry.idx)
            for group in @group_list
                # num of all devices (enabled and disabled, also with md)
                group.num_devices_with_meta = group.devices.length
                group.num_devices = group.num_devices_with_meta - 1
            # create helper structures
            # console.log "link"

        get_meta_device: (dev) =>
            return @all_lut[@group_lut[dev.device_group].device]

        ignore_cdg: (group) =>
            # return true when group is not the CDG
            return !group.cluster_device_group

        get_group: (dev) =>
            return @group_lut[dev.device_group]

        get_category: (cat) =>
            return @cat_lut[cat]

        get_num_devices: (group) =>
            # return all enabled devices in group, not working ... ?
            console.log("DO NOT USE: get_num_devices()")
            return (entry for entry in @enabled_list when entry.device_group == group.idx).length - 1

        create_device_group: (new_dg) =>
            # create new device_group
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1)).post(new_dg).then(
                (new_obj) =>
                    # add new device_group to group_list
                    @group_list.push(new_obj)
                    # update group_lut
                    @group_lut[new_obj.idx] = new_obj
                    # fetch corresponding meta_device
                    @_fetch_device(new_obj.device, defer, "created device_group")
                (not_ok) ->
                    defer.reject("not created")
            )
            return defer.promise

        delete_device_group: (dg_pk) =>
            group = @group_lut[dg_pk]
            _.remove(@all_list, (entry) -> return entry.idx == group.device)
            _.remove(@group_list, (entry) -> return entry.idx == dg_pk)
            @reorder()

        create_device: (new_dev) =>
            # create new device
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).post(new_dev).then(
                (new_obj) =>
                    @_fetch_device(new_obj.idx, defer, "created device ")
                (not_ok) ->
                    defer.object("not created")
            )
            return defer.promise

        delete_device: (d_pk) =>
            _.remove(@all_list, (entry) -> return entry.idx == d_pk)
            @reorder()

        _fetch_device: (pk, defer, msg) =>
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList(
                {
                    "ignore_cdg": false
                    "tree_mode" : true
                    "with_categories" : true
                    "ignore_disabled": true
                    "pks": angular.toJson([pk])
                }
            ).then(
                (dev_list) =>
                    dev = dev_list[0]
                    @all_list.push(dev)
                    @reorder()
                    defer.resolve(msg)
            )

        apply_json_changes: (json) =>
            # apply changes from json changedict
            for entry in json
                dev = @all_lut[entry.device]
                dev[entry.attribute] = entry.value
            @reorder()

        # enrichment functions
        enrich_devices: (dth, en_list) =>
            # dth ... icswDeviceTreeHelper
            # en_list .. enrichment list
            defer  = $q.defer()
            # build request
            en_req = @enricher.merge_requests(
                (
                    dev.$$_enrichment_info.build_request(en_list) for dev in dth.devices
                )
            )
            _fetch = $q.defer()
            if _.isEmpty(en_req)
                # empty request, just feed to dth
                _fetch.resolve({})
            else
                # non-empty request, fetch from server
                icswSimpleAjaxCall(
                    "url": ICSW_URLS.DEVICE_ENRICH_DEVICES
                    "data": {
                        "enrich_request": angular.toJson(en_req)
                    }
                    dataType: "json"
                ).then(
                    (result) =>
                        _fetch.resolve(result)
                )
            _fetch.promise.then(
                (result) =>
                    # clear previous values
                    console.log "clear previous enrichment values"
                    @enricher.clear_global_infos(dth, en_req)
                    (dev.$$_enrichment_info.clear_infos(en_req) for dev in dth.devices)
                    console.log "set new enrichment values"
                    # feed results back to enricher
                    @enricher.feed_results(result)
                    # build results
                    (dev.$$_enrichment_info.build_luts(en_list, @enricher, dth) for dev in dth.devices)
                    # resolve with device list
                    defer.resolve(dth.devices)
            )
            return defer.promise

]).service("icswDeviceTreeService", ["$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", ($q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS, icswDomainTreeService) ->
    rest_map = [
        [
            ICSW_URLS.REST_DEVICE_TREE_LIST
            {
                "ignore_cdg" : false
                "tree_mode" : true
                "all_devices" : true
                "with_categories" : true
                "ignore_disabled": true
            }
        ]
        [
            ICSW_URLS.REST_CATEGORY_LIST
            {}
        ]
        [
            ICSW_URLS.REST_DEVICE_GROUP_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswDomainTreeService.fetch(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** device tree loaded ***"
                _result = new icswDeviceTree(data[0], data[1], data[2], data[3])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), _result)
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
])
