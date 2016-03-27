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
).service("icswDeviceTreeHelper",
[
    "icswTools",
(
    icswTools
) ->
    ref_ctr = 0
    # helper service for global (== selection-wide) luts and lists
    class icswDeviceTreeHelper
        constructor: (@tree, @devices) ->
            # just for testing
            ref_ctr++
            @ref_ctr = ref_ctr
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

        post_g_device_connection_info: () ->
            dev_pks = (dev.idx for dev in @devices)
            dev_lut = _.keyBy(@devices, "idx")
            for dev in @devices
                if not dev.$$master_list?
                    dev.$$master_list = []
                    dev.$$slave_list = []
                else
                    dev.$$master_list.length = 0
                    dev.$$slave_list.length = 0
            for dev in @devices
                for cd in dev.device_connection_set
                    if cd.parent of dev_lut
                        if cd.idx not in (_cd.idx for _cd in dev_lut[cd.parent].$$slave_list)
                            dev_lut[cd.parent].$$slave_list.push(cd)
                    if cd.child of dev_lut
                        if cd.idx not in (_cd.idx for _cd in dev_lut[cd.child].$$master_list)
                            dev_lut[cd.child].$$master_list.push(cd)
            
        post_g_variable_info: () ->

            if not @var_name_filter?
                @var_name_filter = ""
            for dev in @devices
                if not dev.$vars_expanded?
                    dev.$vars_expanded = false
            @filter_device_variables()

        set_var_filter: (new_filter) =>
            @var_name_filter = new_filter
            @filter_device_variables()

        filter_device_variables: () =>
            try
                filter_re = new RegExp(@var_name_filter, "gi")
            catch
                filter_re = new RegExp("^$", "gi")
            # step 1: filter variables
            for dev in @devices
                dev.$var_filter_active = false
                if dev.device_variables_filtered?
                    dev.device_variables_filtered.length = 0
                else
                    dev.device_variables_filtered = []
                if dev.is_cluster_device_group
                    v_source = "c"
                else if dev.is_meta_device
                    v_source = "m"
                else
                    v_source = "d"
                dev.$num_vars_total = dev.device_variable_set.length
                dev.$num_vars_parent = 0
                dev.$num_vars_shadowed = 0
                for d_var in dev.device_variable_set
                    if not d_var.$selected?
                        d_var.$selected = false
                    # set var_type
                    if d_var.var_type == "s"
                        d_var.$var_type = "string"
                        d_var.$var_value = d_var.val_str
                    else if d_var.var_type == "i"
                        d_var.$var_type = "integer"
                        d_var.$var_value = d_var.val_int
                    else if d_var.var_type == "b"
                        d_var.$var_type = "blob"
                        d_var.$var_value = d_var.val_blob.length + "bytes"
                    else if d_var.var_type == "t"
                        d_var.$var_type = "time"
                        d_var.$var_value = d_var.val_time
                    else if d_var.var_type == "d"
                        d_var.$var_type = "datetime"
                        d_var.$var_value = moment(d_var.val_date).format("dd, D. MMM YYYY HH:mm:ss")
                    else
                        d_var.$var_type = "VarType #{d_var.var_type}"
                        d_var.$var_value = "unknown type #{d_var.var_type}"

                    # source is device
                    d_var.$source = v_source
                    if d_var.name.match(filter_re)
                        dev.device_variables_filtered.push(d_var)
                    else
                        dev.$var_filter_active = true
                dev.$local_var_names = (d_var.name for d_var in dev.device_variables_filtered)
                dev.$local_meta_var_names = []
            # step 2: add meta-vars to devices
            for dev in @devices
                if not dev.is_meta_device
                    meta = @tree.get_meta_device(dev)
                    for d_var in meta.device_variables_filtered
                        if d_var.inherit
                            if d_var.name in dev.$local_var_names
                                # var locally set, ignore
                                dev.$num_vars_shadowed++
                            else
                                dev.device_variables_filtered.push(d_var)
                                dev.$num_vars_total++
                                dev.$num_vars_parent++
                            # store in local_meta_var_names
                            dev.$local_meta_var_names.push(d_var.name)
            # step 3: add cdg vars to rest
            cdg_dev = @tree.cluster_device_group_device
            for dev in @devices
                if dev.idx != cdg_dev.idx
                    for d_var in cdg_dev.device_variables_filtered
                        if d_var.inherit
                            if d_var.name in dev.$local_var_names
                                if d_var not in dev.$local_meta_var_names
                                    dev.$num_vars_shadowed++
                                else
                                    # var already shadowed via meta, ignore
                                    true
                            else
                                dev.device_variables_filtered.push(d_var)
                                dev.$num_vars_total++
                                dev.$num_vars_parent++
                dev.$num_vars_filtered = dev.device_variables_filtered.length
            # step 4: sort variables
            for dev in @devices
                icswTools.order_in_place(
                    dev.device_variables_filtered
                    ["name"]
                    ["asc"]
                )


]).service("icswDeviceTreeHelperService",
[
    "icswDeviceTreeHelper",
(
    icswDeviceTreeHelper
) ->

    return {
        "create": (tree, devices) ->
            return new icswDeviceTreeHelper(tree, devices)
    }

]).service("icswEnrichmentInfo",
[
    "icswNetworkTreeService", "icswTools",
(
    icswNetworkTreeService, icswTools
) ->
    # stores info about already fetched additional info from server
    class icswEnrichmentInfo
        constructor: (@device) ->
            # device may be the device_tree for global instance
            @loaded = []
            @device.num_boot_ips = 0
            @device.num_netdevices = 0
            @device.num_netips = 0
            @device.num_peers = 0
            # hm, not optimal, should be done
            if not @device.device_connection_set?
                @device.device_connection_set = []

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
                "variable_info": "device_variable_set"
                "device_connection_info": "device_connection_set"
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
                _setter_name = @get_setter_name(key)
                @[_setter_name](@device, result)
            else
                _attr_name = @get_attr_name(key)
                if @device[_attr_name]?
                    if @is_element(key)
                        @device[_attr_name] = result
                    else
                        @device[_attr_name].push(result)
                else
                    # this can happen for device-connections
                    console.warn "device #{@device.full_name} has no attribute #{_attr_name}"

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
                    _pks = []
                    if obj.device?
                        _pks.push(obj.device)
                    # parent / child
                    else if obj.parent? and obj.child?
                        _pks.push(obj.parent)
                        _pks.push(obj.child)
                    if _pks.length
                        for _pk in _pks
                            @device.all_lut[_pk].$$_enrichment_info.feed_result(key, obj)
                            # remember devices with a valid result
                            if _pk not in devices_set
                                devices_set.push(_pk)
                    else
                        console.error "feed_results, ", obj
                        throw new Error("No device / parent / child attribute found in object")
                _missing = _.difference(en_req[key], devices_set)
                for _pk in _missing
                    @device.all_lut[_pk].$$_enrichment_info.feed_empty_result(key)

]).service("icswDeviceTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswEnrichmentInfo",
    "icswSimpleAjaxCall", "$rootScope", "$timeout",
    "ICSW_SIGNALS", "icswDeviceTreeHelper", "icswNetworkTreeService",
(
    icswTools, ICSW_URLS, $q, Restangular, icswEnrichmentInfo,
    icswSimpleAjaxCall, $rootScope, $timeout,
    ICSW_SIGNALS, icswDeviceTreeHelper, icswNetworkTreeService
) ->
    class icswDeviceTree
        constructor: (full_list, group_list, domain_tree, cat_tree) ->
            @group_list = group_list
            @all_list = []
            @enabled_list = []
            @disabled_list = []
            @domain_tree = domain_tree
            @cat_tree = cat_tree
            @enricher = new icswEnrichmentInfo(@)
            @build_luts(full_list)

            # install global signal handlers
            $rootScope.$on(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), (event, domain_tree) =>
                # domain name tree changed, build full_names and reorder
                @reorder()
            )
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

        dnt_changed: () =>
            console.log "DNT CHANGED", @domain_tree

        build_luts: (full_list) =>
            # build luts and create enabled / disabled lists
            @all_list.length = 0
            @enabled_list.length = 0
            @disabled_list.length = 0
            @enabled_lut = {}
            @disabled_lut = {}
            @cluster_device_group_device = undefined
            @cluster_device_group = undefined
            _disabled_groups = []
            for _entry in full_list
                if _entry.is_cluster_device_group
                    # oh what a name ...
                    @cluster_device_group_device = _entry
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
            # set the clusterDevice Group
            if @cluster_device_group_device
                @cluster_device_group = @group_lut[@cluster_device_group_device.device_group]
            # console.log @enabled_list.length, @disabled_list.length, @all_list.length
            @link()

        link: () =>
            # create links between groups and devices
            for group in @group_list
                # reference to all devices
                group.devices = []
            for entry in @all_list
                # add enrichment info
                if not entry.$$_enrichment_info?
                    entry.$$_enrichment_info = new icswEnrichmentInfo(entry)
                # do not set group here to prevent circular dependencies in serializer
                # entry.group_object = @group_lut[entry.device_group]
                @group_lut[entry.device_group].devices.push(entry.idx)
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
            return @cat_tree.lut[cat]

        get_num_devices: (group) =>
            # return all enabled devices in group, not working ... ?
            console.error "DO NOT USE: get_num_devices()"
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
                    if dev.device_group of @group_lut
                        @reorder()
                        defer.resolve(msg)
                    else
                        # new device-group added (at least the group is missing), fetch group
                        Restangular.one(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1)).get({"idx": dev.device_group}).then(
                            (new_obj) =>
                                new_group = new_obj[0]
                                # add new device_group to group_list
                                @group_list.push(new_group)
                                # update group_lut
                                @group_lut[new_group.idx] = new_group
                                # and now the meta-device
                                @_fetch_device(new_group.device, defer, "created device_group")
                        )
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
                    @_fetch_netip(new_obj.idx, defer, "created netip", cur_nd)
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

        # for device Variables

        create_device_variable: (new_var) =>
            # create new netIP
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1)).post(new_var).then(
                (new_obj) =>
                    @_fetch_device_variable(new_obj.idx, defer, "created variable")
                (not_ok) ->
                    defer.reject("variable not created")
            )
            return defer.promise

        delete_device_variable: (del_var) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_var, ICSW_URLS.REST_DEVICE_VARIABLE_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_var.remove().then(
                (ok) =>
                    dev = @all_lut[del_var.device]
                    console.log del_var, dev.device_variable_set
                    _.remove(dev.device_variable_set, (entry) -> return entry.idx == del_var.idx)
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_device_variable: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1)).get({"idx": pk}).then(
                (new_var) =>
                    new_var = new_var[0]
                    dev = @all_lut[new_var.device]
                    dev.device_variable_set.push(new_var)
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
                    # fetch missing requirements
                    # FIXME: make this more dynamic
                    _reqs = $q.defer()
                    if "network_info" in en_list
                        icswNetworkTreeService.load("enr").then(
                            (done) =>
                                _reqs.resolve("loaded")
                        )
                    else
                        _reqs.resolve("not needed")
                    _reqs.promise.then(
                        (ok) =>
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

        # device trace functions
        get_device_trace: (devs)  =>
            # get all devices (including meta-devices and the cluster device group)
            # for devs
            # intermediate result, as pks
            _res = (dev.idx for dev in devs)

            for _dev in devs
                _md = @get_meta_device(_dev)
                if _md.idx not in _res
                    _res.push(_md.idx)

            # add the cluster device group
            _res.push(@cluster_device_group_device.idx)
            # console.log "trace: in #{devs.length}, out #{_res.length}"
            return (@all_lut[idx] for idx in _res)

        # category functions
        add_category_to_device_by_pk: (dev_pk, cat_pk) =>
            dev = @all_lut[dev_pk]
            dev.categories.push(cat_pk)

        remove_category_from_device_by_pk: (dev_pk, cat_pk) =>
            dev = @all_lut[dev_pk]
            _.remove(dev.categories, (entry) -> return entry == cat_pk)

        # device connection calls
        create_device_connection: (new_cd, hs) =>
            # create new netdevice
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_CD_CONNECTION_LIST.slice(1)).post(new_cd).then(
                (new_obj) =>
                    @_fetch_device_connection(new_obj.idx, defer, "created devc", hs)
                (not_ok) ->
                    defer.reject("devc not created")
            )
            return defer.promise

        delete_device_connection: (del_cd, hs) ->
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_cd, ICSW_URLS.REST_CD_CONNECTION_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_cd.remove().then(
                (ok) =>
                    p_dev = @all_lut[del_cd.parent]
                    s_dev = @all_lut[del_cd.child]
                    _.remove(p_dev.device_connection_set, (cd) -> return cd.idx == del_cd.idx)
                    _.remove(s_dev.device_connection_set, (cd) -> return cd.idx == del_cd.idx)
                    hs.post_g_device_connection_info()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_device_connection: (pk, defer, msg, hs) =>
            Restangular.one(ICSW_URLS.REST_CD_CONNECTION_LIST.slice(1)).get({"idx": pk}).then(
                (new_cd) =>
                    new_cd = new_cd[0]
                    p_dev = @all_lut[new_cd.parent]
                    s_dev = @all_lut[new_cd.child]
                    p_dev.device_connection_set.push(new_cd)
                    s_dev.device_connection_set.push(new_cd)
                    hs.post_g_device_connection_info()
                    defer.resolve(msg)
            )

]).service("icswDeviceTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS",
    "icswDomainTreeService", "icswCategoryTreeService",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS,
    icswDomainTreeService, icswCategoryTreeService
) ->
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
        _wait_list.push(icswDomainTreeService.load(client))
        _wait_list.push(icswCategoryTreeService.load(client))
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
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "current": () ->
            return _result
    }
])
