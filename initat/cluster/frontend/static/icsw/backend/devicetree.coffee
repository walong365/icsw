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
).service("icswDeviceTreeHelper", ["icswTools", (icswTools) ->
    # helper service for global (== selection-wide) luts and lists
    class icswDeviceTreeHelper
        constructor: (@tree, @devices) ->
            @netdevice_list = []
            @netdevice_lut = {}
            @net_ip_list = []
            @net_ip_lut = {}

        # global post calls
        post_g_network_info: () =>
            # FIXME, todo: remove entries when a device gets delete
            @netdevice_list.length = 0
            @net_ip_list.length = 0
            for dev in @devices
                for nd in dev.netdevice_set
                    nd.$$devicename = @tree.all_lut[nd.device].full_name
                    @netdevice_list.push(nd)
                    for ip in nd.net_ip_set
                        ip.$$devicename = nd.$$devicename
                        ip.$$devname = nd.devname
                        @net_ip_list.push(ip)
            @netdevice_lut = icswTools.build_lut(@netdevice_list)
            @net_ip_lut = icswTools.build_lut(@net_ip_list)
            @netdevice_list = _.orderBy(
                @netdevice_list,
                ["$$devicename", "devname"],
                ["asc", "asc"],
            )
            @net_ip_list = _.orderBy(
                @net_ip_list,
                ["$$devicename", "$$devname", "ip"],
                ["asc", "asc", "asc"],
            )

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
            return req in ["scan_info"]

        is_element: (req) =>
            return req in ["disk_info", "snmp_info"]

        is_loaded: (req) =>
            return req in @loaded

        get_setter_name: (req) =>
            _lut = {
                "scan_info": "set_scan_info"
            }
            if req of _lut
                return _lut[req]
            else
                throw new Error("Unknown EnrichmentKey #{req}")

        set_scan_info: (dev, scan_object) =>
            dev.active_scan = scan_object.active_scan

        get_attr_name: (req) =>
            _lut = {
                "network_info": "netdevice_set"
                "monitoring_hint_info": "monitoring_hint_set"
                "disk_info": "act_partition_table"
                "com_info": "com_capability_list"
                "snmp_info": "devicesnmpinfo"
                "snmp_schemes_info": "snmp_schemes"
                "scan_info": "active_scan"
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
                    else if @is_element(req)
                        @device[@get_attr_name(req)] = undefined
                    else
                        @device[@get_attr_name(req)].length = 0

        build_luts: (en_list, dth_obj) =>
            # build luts
            for req in en_list
                _call_name = "post_#{req}"
                if @[_call_name]?
                    @[_call_name]()

        build_g_luts: (en_list, dth_obj) =>
            # build luts
            for req in en_list
                _gp_call_name = "post_g_#{req}"
                if dth_obj[_gp_call_name]?
                    dth_obj[_gp_call_name]()

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

        build_request: (req_list, force) =>
            # returns a list (dev_pk, enrichments_to_load)
            fetch_list = []
            for req in req_list
                if req not in @loaded
                    fetch_list.push(req)
                    if @is_scalar(req)
                        @device[@get_attr_name(req)] = undefined
                    else if @is_element(req)
                        @device[@get_attr_name(req)] = undefined
                    else
                        @device[@get_attr_name(req)] = []
                else if force
                    # add request but do not clear current settings
                    fetch_list.push(req)
            return [@device.idx, fetch_list]

        add_netdevice: (new_nd) =>
            # insert the new netdevice nd to the local device
            dev = @device
            dev.netdevice_set.push(new_nd)
            @post_network_info()

        delete_netdevice: (del_nd) =>
            # insert the new netdevice nd to the local device
            dev = @device
            _.remove(dev.netdevice_set, (entry) -> return entry.idx == del_nd.idx)
            @post_network_info()

        add_netip: (new_ip, cur_nd) =>
            # insert the new IP new_ip to the local device
            cur_nd.net_ip_set.push(new_ip)
            @post_network_info()

        delete_netip: (del_ip, cur_nd) =>
            # insert the new netdevice nd to the local device
            _.remove(cur_nd.net_ip_set, (entry) -> return entry.idx == del_ip.idx)
            @post_network_info()

        feed_result: (key, result) =>
            if key not in @loaded
                @loaded.push(key)
            # store info
            if @is_scalar(key)
                @[@get_setter_name(key)](@device, result)
            else if @is_element(key)
                @device[@get_attr_name(key)] = result
            else
                @device[@get_attr_name(key)].push(result)

        feed_empty_result: (key) =>
            if key not in @loaded
                @loaded.push(key)

        merge_requests: (req_list) =>
            # merges all requests from build_request
            to_load = {}
            for d_req in req_list
                for req in d_req[1]
                    if req not of to_load
                        to_load[req] = []
                    to_load[req].push(d_req[0])
            return to_load

        feed_results: (result, en_req) =>
            # feed result into device_tree
            for key, obj_list of result
                devices_set = []
                for obj in obj_list
                    if obj.device?
                        _pk = obj.device
                        @device.all_lut[_pk].$$_enrichment_info.feed_result(key, obj)
                        # remember devices with a valid result
                        if _pk not in devices_set
                            devices_set.push(_pk)
                    else
                        console.log obj
                        throw new Error("No device attribute found in object")
                _missing = _.difference(en_req[key], devices_set)
                for _pk in _missing
                    @device.all_lut[_pk].$$_enrichment_info.feed_empty_result(key)

]).service("icswDeviceTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswEnrichmentInfo", "icswSimpleAjaxCall", "$rootScope", "$timeout",
    "ICSW_SIGNALS", "icswDeviceTreeHelper",
(
    icswTools, ICSW_URLS, $q, Restangular, icswEnrichmentInfo, icswSimpleAjaxCall, $rootScope, $timeout,
    ICSW_SIGNALS, icswDeviceTreeHelper
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

            # init scan infrastructure
            @init_device_scans()

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

        # create / delete functions

        # for group

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

        # for device

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

        # for netdevice

        create_netdevice: (new_nd) =>
            # create new netdevice
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).post(new_nd).then(
                (new_obj) =>
                    @_fetch_netdevice(new_obj.idx, defer, "created netdevice")
                (not_ok) ->
                    defer.reject("nd not created")
            )
            return defer.promise

        delete_netdevice: (del_nd) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_nd, ICSW_URLS.REST_NETDEVICE_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_nd.remove().then(
                (ok) =>
                    dev = @all_lut[del_nd.device]
                    dev.$$_enrichment_info.delete_netdevice(del_nd)
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_netdevice: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).get({"idx": pk}).then(
                (new_nd) =>
                    new_nd = new_nd[0]
                    dev = @all_lut[new_nd.device]
                    dev.$$_enrichment_info.add_netdevice(new_nd)
                    defer.resolve(msg)
            )

        # for netIP

        create_netip: (new_ip, cur_nd) =>
            # create new netIP
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_NET_IP_LIST.slice(1)).post(new_ip).then(
                (new_obj) =>
                    @_fetch_netip(new_obj.idx, defer, "created netip ", cur_nd)
                (not_ok) ->
                    defer.reject("ip not created")
            )
            return defer.promise

        delete_netip: (del_ip, cur_nd) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_ip, ICSW_URLS.REST_NET_IP_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_ip.remove().then(
                (ok) =>
                    dev = @all_lut[cur_nd.device]
                    dev.$$_enrichment_info.delete_netip(del_ip, cur_nd)
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_netip: (pk, defer, msg, cur_nd) =>
            Restangular.one(ICSW_URLS.REST_NET_IP_LIST.slice(1)).get({"idx": pk}).then(
                (new_ip) =>
                    new_ip = new_ip[0]
                    dev = @all_lut[cur_nd.device]
                    dev.$$_enrichment_info.add_netip(new_ip, cur_nd)
                    defer.resolve(msg)
            )

        # enrichment functions
        enrich_devices: (dth, en_list, force=false) =>
            # dth ... icswDeviceTreeHelper
            # en_list .. enrichment list
            defer  = $q.defer()
            # build request
            en_req = @enricher.merge_requests(
                (
                    dev.$$_enrichment_info.build_request(en_list, force) for dev in dth.devices
                )
            )
            _fetch = $q.defer()
            if _.isEmpty(en_req)
                # empty request, just feed to dth
                # console.log "enrichment:", en_list, "for", dth, "not needed"
                _fetch.resolve({})
            else
                # console.log "*** enrichment:", en_list, "for", dth, "resulted in non-empty", en_req
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
                    # console.log "clear previous enrichment values"
                    (dev.$$_enrichment_info.clear_infos(en_req) for dev in dth.devices)
                    # console.log "set new enrichment values"
                    # feed results back to enricher
                    @enricher.feed_results(result, en_req)
                    # build local luts
                    (dev.$$_enrichment_info.build_luts(en_list, dth) for dev in dth.devices)
                    # build global luts
                    @build_helper_luts(en_list, dth)
                    # resolve with device list
                    defer.resolve(dth.devices)
            )
            return defer.promise

        build_helper_luts: (en_list, dth) =>
            @enricher.build_g_luts(en_list, dth)

        # localised update functions
        update_boot_settings: (dev) =>
            defer = $q.defer()
            Restangular.one(ICSW_URLS.BOOT_UPDATE_DEVICE_SETTINGS.slice(1).slice(0, -2)).post(dev.idx, dev).then(
                (result) ->
                    defer.resolve("saved")
                () ->
                    defer.reject("not saved")
            )
            return defer.promise

        # device scan functions

        init_device_scans: () =>
            # devices with scans running (pk => scan)
            @scans_running = {}
            @scans_promise = {}
            @scan_timeout = undefined

        register_device_scan: (dev, scan_settings) =>
            defer = $q.defer()

            # register scan mode

            @set_device_scan(dev, scan_settings.scan_mode)

            if scan_settings.scan_mode != "base"
                # save defer function for later reference
                @scans_promise[dev.idx] = defer

            # start scan on server
            icswSimpleAjaxCall(
                url     : ICSW_URLS.DEVICE_SCAN_DEVICE_NETWORK
                data    :
                    "settings" : angular.toJson(scan_settings)
            ).then(
                (xml) =>
                    # scan startet (or already done for base-scan because base-scan is synchronous)
                    @check_scans_running()
                    if scan_settings.scan_mode == "base"
                        defer.resolve("scan done")
                (error) ->
                    defer.reject("scan not ok")
            )

            return defer.promise

        set_device_scan: (dev, scan_type) =>
            _changed = false
            dev.active_scan = scan_type
            if dev.idx not of @scans_running
                prev_mode = ""
                _changed = true
                @scans_running[dev.idx] = scan_type
            else
                prev_mode = @scans_running[dev.idx]
                if @scans_running[dev.idx] != scan_type
                    @scans_running[dev.idx] = scan_type
                    _changed = true
            if not @scans_running[dev.idx]
                # send no signal
                if prev_mode == "base"
                    _changed = false
                    # force update of com_info
                    @enrich_devices(new icswDeviceTreeHelper(@, [dev]), ["com_info"], true).then(
                        (result) =>
                            $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_SCAN_CHANGED"), dev.idx, "")
                    )
                else if @scans_promise[dev.idx]?
                    # rescan device network
                    @enrich_devices(new icswDeviceTreeHelper(@, [dev]), ["network_info"], true).then(
                        (result) =>
                            @scans_promise[dev.idx].resolve("scan done")
                            delete @scans_promise[dev.idx]
                    )
                delete @scans_running[dev.idx]
            if _changed
                # send signal if required
                $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_SCAN_CHANGED"), dev.idx, scan_type)

        check_scans_running: () =>
            if not _.isEmpty(@scans_running)
                Restangular.all(ICSW_URLS.NETWORK_GET_ACTIVE_SCANS.slice(1)).getList(
                    {
                        "pks" : angular.toJson(@scans_running)
                    }
                ).then(
                    (result) =>
                        for _res in result
                            @set_device_scan(@all_lut[_res.pk], _res.active_scan)
                        @scan_timeout = $timeout(@check_scans_running, 1000)
                )

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
