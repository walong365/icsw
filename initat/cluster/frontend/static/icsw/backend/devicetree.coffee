# Copyright (C) 2012-2017 init.at
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

angular.module(

    # device tree handling (including device enrichment)

    "icsw.backend.devicetree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.user", "icsw.backend.variable",
    ]
).service("icswDeviceClassTree",
[
    "$q",
(
    $q,
) ->
    class icswDeviceClassTree
        constructor: (list) ->
            @list =[]
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                if entry.default_system_class
                    @__dsc = entry
                if not entry.$$enabled?
                    entry.$$enabled = false
                @list.push(entry)
            @enabled_idx_list = []
            @enabled_fp = ""
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")

        get_fingerprint: () =>
            return @enabled_fp

        validate_device_class_filter: (dcf) =>
            # dcf ... dict with class.idx => class.$$enabled
            _changed = false

            # check for new values
            for entry in @list
                if entry.idx not of dcf
                    dcf[entry.idx] = entry.$$enabled
                    _changed = true
                else
                    entry.$$enabled = dcf[entry.idx]

            # validate
            if not _.some(_.values(dcf))
                @__dsc.$$enabled = true
                dcf[@__dsc.idx] = @__dsc.$$enabled
                _changed = true
            # build enabled_idx_list
            @enabled_idx_list = (entry.idx for entry in @list when entry.$$enabled)
            @enabled_fp = ("#{_val}" for _val in @enabled_idx_list).join("::")
            return _changed

        read_device_class_filter: (dcf) =>
            # syncs entries from dcf
            _changed = false
            for entry in @list
                if entry.$$enabled != dcf[entry.idx]
                    entry.$$enabled = dcf[entry.idx]
                    _changed = true
            if @validate_device_class_filter(dcf)
                _changed = true
            return _changed

        write_device_class_filter: (dcf) =>
            # syncs dcf from entries
            # dcf ... dict with class.idx => class.$$enabled
            # step one: copy
            _changed = false
            for entry in @list
                if entry.$$enabled != dcf[entry.idx]
                    dcf[entry.idx] = entry.$$enabled
                    _changed = true
            if @validate_device_class_filter(dcf)
                _changed = true
            return _changed

        get_filter_name: () =>
            _fv = (entry.$$enabled for entry in @list)
            if _.every(_fv)
                return "all"
            else if not _.some(_fv)
                return "none"
            else
                _enabled = (1 for entry in @list when entry.$$enabled).length
                return "#{_enabled} / #{_fv.length}"

]).service("icswDeviceClassTreeService",
[
    "$q", "icswDeviceClassTree", "icswTreeBase", "ICSW_URLS",
(
    $q, icswDeviceClassTree, icswTreeBase, ICSW_URLS,
) ->
    rest_map = [
        ICSW_URLS.DEVICE_DEVICE_CLASS_LIST
    ]
    return new icswTreeBase(
        "DeviceClassTree"
        icswDeviceClassTree
        rest_map
        ""
    )
]).service("icswDeviceTreeHelper",
[
    "icswTools",
(
    icswTools,
) ->
    ref_ctr = 0
    # helper service for global (== selection-wide) luts and lists
    class icswDeviceTreeHelper
        constructor: (@tree, devices) ->
            # just for testing
            @helper_id = icswTools.get_unique_id("icswHelper")
            ref_ctr++
            @ref_ctr = ref_ctr
            @netdevice_list = []
            @netdevice_lut = {}
            @net_ip_list = []
            @net_ip_lut = {}
            @devices = []
            @update(devices)
            
        update: (dev_list) =>
            @devices.length = 0
            for dev in dev_list
                @devices.push(dev)
            @build_luts()
        
        add_device: (dev) =>
            @devices.push(dev)
            @build_luts()
            
        build_luts: () =>
            @device_lut = _.keyBy(@devices, "idx")

        # global post calls

        post_g_network_info: () =>
            _net = @tree.network_tree
            _dom = @tree.domain_tree

            # FIXME, todo: remove entries when a device gets deleted
            @netdevice_list.length = 0
            @net_ip_list.length = 0

            # FIXME, todo: remove temporary lists. find out why netdevice_set is populated with duplicate entries first
            netdevice_list_tmp = []
            net_ip_list_tmp = []

            for dev in @devices
                for nd in dev.netdevice_set
                    nd.$$devicename = @tree.all_lut[nd.device].full_name
                    nd.$$device = @tree.all_lut[nd.device]
                    netdevice_list_tmp.push(nd)
                    for ip in nd.net_ip_set
                        ip.$$devicename = nd.$$devicename
                        ip.$$devname = nd.devname
                        ip.$$network = _net.nw_lut[ip.network]
                        ip.$$domain_tree_node = _dom.lut[ip.domain_tree_node]
                        # console.log ip.ip, ip.$$network
                        # link
                        ip.$$netdevice = nd
                        ip.$$device = nd.$$device
                        net_ip_list_tmp.push(ip)

            @netdevice_lut = icswTools.build_lut(netdevice_list_tmp)
            @net_ip_lut = icswTools.build_lut(net_ip_list_tmp)

            for net_device_key in Object.keys(@netdevice_lut)
                @netdevice_list.push(@netdevice_lut[net_device_key])

            for net_ip_key in Object.keys(@net_ip_lut)
                @net_ip_list.push(@net_ip_lut[net_ip_key])

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

        post_g_static_asset_info: () ->
            console.log "post_g static_asset_info"

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
            # if not @var_name_filter?
            #     @var_name_filter = ""
            # for dev in @devices
            #    if not dev.$$vars_expanded?
            #        dev.$$vars_expanded = false
            @salt_device_variables()

            
        # set_var_filter: (new_filter) =>
        #    @var_name_filter = new_filter
        #    @filter_device_variables()

        replace_device_variable: (new_var) =>
            for dev in @devices
                if dev.idx == new_var.device
                    _.remove(dev.device_variable_set, (entry) -> return entry.idx == new_var.idx)
                    dev.device_variable_set.push(new_var)
                    
        salt_device_variables: () =>
            _dvst = @tree.device_variable_scope_tree
            # step 1: filter variables
            for dev in @devices
                # dev.$var_filter_active = false
                if dev.device_variables?
                    dev.device_variables.length = 0
                else
                    dev.device_variables = []
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
                    d_var.$$from_server = true
                    d_var.$$device = dev
                    d_var.$$source = "direct"
                    d_var.$$inherited = false
                    d_var.$$created_mom = moment(d_var.date)
                    d_var.$$created_str = d_var.$$created_mom.format("dd, D. MMM YYYY HH:mm:ss")
                    if not d_var.$selected?
                        d_var.$selected = false
                        d_var.$$rep = 0
                    d_var.$$rep++
                    d_var.$$scope_name = _dvst.lut[d_var.device_variable_scope].name
                    # how oftens is this variable shadowed
                    d_var.$$shadow_count = 0
                    # is a shadow of an inherited variable
                    d_var.$$shadow = false
                    # set var_type
                    if d_var.var_type == "s"
                        d_var.$$var_type = "string"
                        d_var.$$var_value = d_var.val_str
                    else if d_var.var_type == "i"
                        d_var.$$var_type = "integer"
                        d_var.$$var_value = d_var.val_int
                    else if d_var.var_type == "b"
                        d_var.$$var_type = "blob"
                        d_var.$$var_value = d_var.val_blob.length + "bytes"
                    else if d_var.var_type == "t"
                        d_var.$$var_type = "time"
                        d_var.$$var_value = d_var.val_time
                    else if d_var.var_type == "d"
                        d_var.$$var_type = "datetime"
                        d_var.$$var_value = moment(d_var.val_date).format("dd, D. MMM YYYY HH:mm:ss")
                    else if d_var.var_type == "D"
                        d_var.$$var_type = "date"
                        d_var.$$var_value = moment(d_var.val_date).format("dd, D. MMM YYYY")
                    else
                        d_var.$$var_type = "VarType #{d_var.var_type}"
                        d_var.$$var_value = "unknown type #{d_var.var_type}"

                    d_var.$$filter_field = "#{d_var.name} #{d_var.$$var_value}"

                    # source is device
                    d_var.$source = v_source
                    # edit flags
                    d_var.$$delete_ok = not d_var.protected
                    d_var.$$edit_ok = d_var.is_public
                    d_var.$$local_copy_ok = false
                    # if d_var.name.match(filter_re)
                    dev.device_variables.push(d_var)
                    # else
                    #    dev.$var_filter_active = true
                dev.$local_var_names = (d_var.name for d_var in dev.device_variables)

            _copy_var = (new_dev, s_var, cdg_mode) ->
                new_var = angular.copy(s_var)
                new_var.$$device = new_dev
                new_var.$$delete_ok = false
                new_var.$$edit_ok = false
                new_var.$$local_copy_ok = true
                new_var.$$original = s_var
                new_var.$$from_server = false
                new_var.$$shadow_count = 0
                new_var.$$shadow = false
                new_var.$$inherited = true
                new_var.uuid = "---"
                if cdg_mode
                    new_var.$$source = "system"
                else
                    new_var.$$source = "group"
                return new_var

            # step 2: add cdg vars to meta, then meta to normal
            cdg_dev = @tree.cluster_device_group_device
            for _cdg_mode in [true, false]
                for dev in @devices
                    _check = false
                    if _cdg_mode
                        if dev.idx != cdg_dev.idx and dev.is_meta_device
                            src_dev = cdg_dev
                            _check = true
                    else
                        if not dev.is_meta_device
                            src_dev = @tree.get_meta_device(dev)
                            _check = true
                    if _check
                        for d_var in src_dev.device_variables
                            if d_var.inherit
                                if d_var.name in dev.$local_var_names
                                    dev.$num_vars_shadowed++
                                    _local_var = (l_var for l_var in dev.device_variables when l_var.name == d_var.name)[0]
                                    _local_var.$$shadow = true
                                    if d_var.$$inherited
                                        d_var.$$original.$$shadow_count++
                                    else
                                        d_var.$$shadow_count++
                                else
                                    # create a copy and append to device_variables
                                    if d_var.$$inherited
                                        # var is already inherited, take original var
                                        dev.device_variables.push(_copy_var(dev, d_var.$$original, _cdg_mode))
                                    else
                                        # var is inherited from meta
                                        dev.device_variables.push(_copy_var(dev, d_var, _cdg_mode))
                                    # dev.$local_var_names.push(d_var.name)
                                    dev.$num_vars_total++
                                    dev.$num_vars_parent++


]).service("icswDeviceTreeHelperService",
[
    "icswDeviceTreeHelper",
(
    icswDeviceTreeHelper
) ->

    return {
        create: (tree, devices) ->
            return new icswDeviceTreeHelper(tree, devices)
    }

]).service("icswEnrichmentRequest",
[
    "$q", "icswTools", "icswNetworkTreeService",
(
    $q, icswTools, icswNetworkTreeService,
) ->
    class icswEnrichmentRequest
        constructor: () ->
            @idx = 0
            @defer_lut = {}
            @all_lut = {}
            @all_devs = {}
            @dev_reqs = {}
            @start_time = new Date().getTime()

        feed: (dth, en_list, en_req, defer) =>
            # device_tree_helper, enrichment_list, enrichment_request, defer
            @idx++
            @defer_lut[@idx] = [defer, dth, en_list, en_req]
            @join_requests(en_req)
            req_keys = _.keys(en_req)
            # merge devices
            for dev in dth.devices
                if dev.idx not of @all_devs
                    @all_devs[dev.idx] = dev
                    @dev_reqs[dev.idx] = []
                @dev_reqs[dev.idx] = _.union(@dev_reqs[dev.idx], req_keys)
            # console.log "+", @dev_reqs

        join_requests: (l_req) =>
            # merge local_requests into global_requests
            for _key, _value of l_req
                if _key not of @all_lut
                    @all_lut[_key] = _value
                else
                    @all_lut[_key] = _.union(@all_lut[_key], l_req[_key])

        feed_result: (enricher, result) =>
            _end = new Date().getTime()
            _reqs = $q.defer()
            if "network_info" of @all_lut
                icswNetworkTreeService.load("enr").then(
                    (done) =>
                        _reqs.resolve("loaded")
                )
            else
                _reqs.resolve("not needed")
            _reqs.promise.then(
                (done) =>
                    # runtime in milliseconds
                    _run_time = icswTools.get_diff_time_ms(_end - @start_time)
                    if _.keys(@all_lut).length
                        # request was not empty
                        console.log "*** enrichment_request for #{_.keys(@all_lut)} took #{_run_time}"
                        # step 1: clear all infos
                        for _pk, _dev of @all_devs
                            _dev.$$_enrichment_info.clear_infos(@all_lut)
                        # step 2: feed results
                        for _key, _list of @defer_lut
                            [defer, dth, en_list, en_req] = _list
                            # filtering is done in feed_results
                            enricher.feed_results(result, dth, en_req)
                        # step 3: build luts
                        for _key, _list of @defer_lut
                            [defer, dth, en_list, en_req] = _list
                            # build local luts
                            (dev.$$_enrichment_info.build_luts(en_list) for dev in dth.devices)
                            # build global luts
                            enricher.build_g_luts(en_list, dth)
                            # resolve
                            defer.resolve(dth.devices)
                    else
                        # in case of an empty enrichment requests the result
                        # object is the empty object ({})
                        console.warn "*** empty enrichment_request took #{_run_time}"
                        # step 1: build luts
                        for _key, _list of @defer_lut
                            [defer, dth, en_list, en_req] = _list
                            # build local luts
                            (dev.$$_enrichment_info.build_luts(en_list) for dev in dth.devices)
                            # build global luts
                            enricher.build_g_luts(en_list, dth)
                            # resolve
                            defer.resolve(dth.devices)
            )
]).service("icswEnrichmentInfo",
[
    "icswNetworkTreeService", "icswTools", "$q",
(
    icswNetworkTreeService, icswTools, $q,
) ->
    # stores info about already fetched additional info from server
    class icswEnrichmentInfo
        constructor: (@device) ->
            # device may be the device_tree for global instance
            @loaded = []
            @device.$$num_boot_ips = 0
            @device.$$num_netdevices = 0
            @device.$$num_netips = 0
            @device.$$num_peers = 0
            # hm, not optimal, should be done
            if not @device.device_connection_set?
                @device.device_connection_set = []
            if not @device.sensor_threshold_set?
                @device.sensor_threshold_set = []
            if not @device.devicescanlock_set?
                @device.devicescanlock_set = []

        is_scalar: (req) =>
            return req in []

        is_element: (req) =>
            return req in ["disk_info", "snmp_info"]

        is_loaded: (req) =>
            return req in @loaded

        get_setter_name: (req) =>
            _lut = {}
            if req of _lut
                return _lut[req]
            else
                throw new Error("Unknown EnrichmentKey in get_setter_name(): #{req}")

        get_attr_name: (req) =>
            _lut = {
                network_info: "netdevice_set"
                monitoring_hint_info: "monitoring_hint_set"
                disk_info: "act_partition_table"
                com_info: "com_capability_list"
                snmp_info: "devicesnmpinfo"
                snmp_schemes_info: "snmp_schemes"
                variable_info: "device_variable_set"
                device_connection_info: "device_connection_set"
                sensor_threshold_info: "sensor_threshold_set"
                package_info: "package_set"
                asset_info: "assetrun_set"
                dispatcher_info: "dispatcher_set"
                # shallow version for info
                past_assetrun_info: "past_assetrun_set"
                static_asset_info: "staticasset_set"
            }
            if req of _lut
                return _lut[req]
            else
                throw new Error("Unknown EnrichmentKey in get_attr_name(): #{req}")

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

        build_luts: (en_list) =>
            # build luts
            for req in en_list
                _call_name = "post_#{req}"
                if @[_call_name]?
                    @[_call_name]()

        build_g_luts: (en_list, dth_obj) =>
            # build luts
            for req in en_list
                _gp_call_name = "post_g_#{req}"
                if dth_obj?
                    if dth_obj[_gp_call_name]?
                        dth_obj[_gp_call_name]()
                else
                    console.warn "build_g_luts problem", en_list, dth_obj

        # post calls

        post_network_info: () =>
            _net = icswNetworkTreeService.current()
            # simple lut for master devices
            @device.netdevice_lut = icswTools.build_lut(@device.netdevice_set)
            @device.$$num_netdevices = 0
            @device.$$num_netips = 0
            @device.$$create_peer_ok = if @device.netdevice_set.length > 0 then true else false
            @device.$$create_netip_ok = if (_net.nw_list.length > 0 and @device.$$create_peer_ok) then true else false
            num_bootips = 0
            # set values
            for net_dev in @device.netdevice_set
                @device.$$num_netdevices++
                net_dev.$$num_netips = 0
                net_dev.$$num_bootips = 0
                # info string (with vlan ID and master device)
                info_string = net_dev.devname
                if net_dev.description
                    info_string = "#{info_string} (#{net_dev.description})"
                if net_dev.vlan_id
                    info_string = "#{info_string}, VLAN #{net_dev.vlan_id}"
                if net_dev.master_device
                    info_string = "#{info_string} on #{@device.netdevice_lut[net_dev.master_device].devname}"
                net_dev.$$info_string = info_string

                # speed
                if net_dev.netdevice_speed of _net.nw_speed_lut
                    net_dev.$$speed_info_string = _net.nw_speed_lut[net_dev.netdevice_speed].info_string
                else
                    net_dev.$$speed_info_string = "-"

                # flags infostring
                _f = []
                if net_dev.routing
                    _f.push("extrouting")
                if net_dev.inter_device_routing
                    _f.push("introuting")
                if !net_dev.enabled
                    _f.push("disabled")
                net_dev.$$flags_info_string = _f.join(", ")

                # desired status
                net_dev.$$desired_status = {
                    "i": "ignore"
                    "u": "up"
                    "d": "down"
                }[net_dev.desired_status]

                # snmp status
                as = net_dev.snmp_admin_status
                os = net_dev.snmp_oper_status
                if as == 0 and os == 0
                    net_dev.$$snmp_ao_status = "-"
                    net_dev.$$snmp_ao_status_class = ""
                else if as == 1 and os == 1
                    net_dev.$$snmp_ao_status = "up"
                    net_dev.$$snmp_ao_status_class = "success text-center"
                else
                    _r_f = []
                    _r_f.push(
                        {
                            1: "up"
                            2: "down"
                            3: "testing"
                        }[as]
                    )
                    _r_f.push(
                        {
                            1: "up"
                            2: "down"
                            3: "testing"
                            4: "unknown"
                            5: "dormant"
                            6: "notpresent"
                            7: "lowerLayerDown"
                        }[os]
                    )
                    net_dev.$$snmp_ao_status = _r_f.join(", ")
                    net_dev.$$snmp_ao_status_class = "warning text-center"

                # bond info
                if net_dev.is_bond
                    slaves = (sub_nd.devname for sub_nd in @device.netdevice_set when sub_nd.bond_master == net_dev.idx)
                    if slaves.length
                        net_dev.$$bond_info_string = "master (" + slaves.join(", ") + ")"
                    else
                        net_dev.$$bond_info_string = "master"
                else
                    net_dev.$$bond_info_string = "-"

                # bridge info
                if net_dev.is_bridge
                    slaves = (sub_nd.devname for sub_nd in @device.netdevice_set when sub_nd.bridge_device == net_dev.idx)
                    if slaves.length
                        net_dev.$$bridge_info_string = "bridge" + " (" + slaves.join(", ") + ")"
                    else
                        net_dev.$$bridge_info_string = "bridge"
                else if net_dev.bridge_device
                    net_dev.$$bridge_info_string = "slave (" + @device.netdevice_lut[net_dev.bridge_device].devname + ")"
                else
                    net_dev.$$bridge_info_string = "-"

                # network type
                net_dev.$$type_string = _net.nw_snmp_type_lut[net_dev.snmp_network_type].if_label

                for net_ip in net_dev.net_ip_set
                    @device.$$num_netips++
                    net_dev.$$num_netips++
                    if _net.nw_lut[net_ip.network].network_type_identifier == "b"
                        num_bootips++
                        net_dev.$$num_bootips++
            @device.$$num_boot_ips = num_bootips

            # bootdevice info class

            if @device.dhcp_error
                @device.$$bootdevice_info_class = "btn-danger"
            else
                if num_bootips == 0
                    @device.$$bootdevice_info_class = "btn-warning"
                else if num_bootips == 1
                    @device.$$bootdevice_info_class = "btn-success"
                else
                    @device.$$bootdevice_info_class = "btn-danger"
            if @device.dhcp_write
                w_state = "write"
            else
                w_state = "no write"
            if @device.dhcp_mac
                g_state = "greedy"
            else
                g_state = "not greedy"
            r_val = "#{num_bootips} IPs (#{w_state}) / #{g_state})"
            if @device.dhcp_error
                r_val = "#{r_val}, #{@device.dhcp_error}"
            if @device.dhcp_write != @device.dhcp_written
                r_val = "#{r_val}, DHCP is " + (if @device.dhcp_written then "" else "not") + " written"
            @device.$$boot_info_value = r_val

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
            defer = $q.defer()
            # insert the new netdevice nd to the local device
            dev = @device
            dev.netdevice_set.push(new_nd)
            @post_network_info()
            defer.resolve("done")
            return defer.promise

        delete_netdevice: (del_nd) =>
            # insert the new netdevice nd to the local device
            dev = @device
            _.remove(dev.netdevice_set, (entry) -> return entry.idx == del_nd.idx)
            @post_network_info()

        replace_netdevice: (del_nd, new_nd) =>
            # replace the netdevice del_nd with new_nd
            _.remove(@device.netdevice_set, (entry) -> return entry.idx == del_nd.idx)
            return @add_netdevice(new_nd)

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
                if @is_element(key)
                    @device[_attr_name] = result
                else
                    if @device[_attr_name]?
                        if !(result in @device[_attr_name])
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

        feed_results: (result, dth, en_req) =>
            # result is a global result
            # feed result into device_tree
            for key, obj_list of result
                # filter according to local result
                if key of en_req
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
                                # filter according to device_tree_helper
                                if _pk of dth.device_lut
                                    # @device is the device tree
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
    "icswSimpleAjaxCall", "$rootScope", "$timeout", "icswDeviceTreeGraph",
    "ICSW_SIGNALS", "icswDeviceTreeHelper", "icswNetworkTreeService", "ICSW_ENUMS",
    "icswEnrichmentRequest", "icswDomainTreeService", "icswWebSocketService",
(
    icswTools, ICSW_URLS, $q, Restangular, icswEnrichmentInfo,
    icswSimpleAjaxCall, $rootScope, $timeout, icswDeviceTreeGraph,
    ICSW_SIGNALS, icswDeviceTreeHelper, icswNetworkTreeService, ICSW_ENUMS,
    icswEnrichmentRequest, icswDomainTreeService, icswWebSocketService,
) ->
    class icswDeviceTree
        constructor: (full_list, group_list, domain_tree, network_tree, cat_tree, device_variable_scope_tree, device_class_tree) ->
            @tree_id = icswTools.get_unique_id("DeviceTree")
            @group_list = group_list
            @all_list = []
            @enabled_list = []
            # enabled non-system group list
            @enabled_ns_group_list = []
            # enabled non-meta device list
            @enabled_nm_list = []
            @disabled_list = []
            @domain_tree = domain_tree
            @network_tree = network_tree
            @cat_tree = cat_tree
            @device_variable_scope_tree = device_variable_scope_tree
            @device_class_tree = device_class_tree
            @enricher = new icswEnrichmentInfo(@)
            @build_luts(full_list)

            # install global signal handlers
            $rootScope.$on(ICSW_SIGNALS("ICSW_DOMAIN_NAME_TREE_CHANGED"), (event, domain_tree) =>
                # domain name tree changed, build full_names and reorder
                @reorder()
            )
            # init scan infrastructure via websockets, we never close this stream ...
            icswWebSocketService.add_stream(
                ICSW_ENUMS.WSStreamEnum.device_scan_lock
                (msg) ->
                    @add_scanlock_to_device(msg)
            ).then(
                (stream_id) =>
                    @stream_id = stream_id
            )

        reorder: () =>
            # device/group names or device <-> group relationships might have changed, sort
            for dev in @all_list
                group = @group_lut[dev.device_group]
                dev.device_group_name = group.name
                dev._nc_device_group_name = _.toLower(dev.device_group_name)
                dev.full_name = @domain_tree.get_full_name(dev)
                dev._nc_name = _.toLower(dev.name)
            for group in @group_list
                group.full_name = @domain_tree.get_full_name(dev)
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
            @enabled_ns_group_list.length = 0
            @enabled_lut = {}
            @enabled_nm_list.length = 0
            @disabled_lut = {}
            @cluster_device_group_device = undefined
            @cluster_device_group = undefined
            _disabled_groups = []
            for _entry in full_list
                if _entry.is_meta_device
                    # used in moncheckdevdep
                    _entry.$$non_md_name = _entry.name.substring(8)
                    _entry.$$print_name = _entry.full_name.substring(8)
                else
                    _entry.$$print_name = _entry.full_name
                if not _entry.$$delete_pending?
                    _entry.$$delete_pending = false
                # pseudo flag from backend
                if _entry.is_cluster_device_group
                    # oh what a name ...
                    @cluster_device_group_device = _entry
                @all_list.push(_entry)
                if not _entry.is_meta_device and _entry.device_group in _disabled_groups
                    @disabled_list.push(_entry)
                else if _entry.enabled
                    @enabled_list.push(_entry)
                    if not _entry.is_meta_device
                        @enabled_nm_list.push(_entry)
                else
                    if _entry.is_meta_device
                        _disabled_groups.push(_entry.device_group)
                    @disabled_list.push(_entry)
            for _group in @group_list
                if not _group.$$delete_pending?
                    _group.$$delete_pending = false
                if _group.enabled and not _group.cluster_device_group
                    @enabled_ns_group_list.push(_group)
            @enabled_lut = icswTools.build_lut(@enabled_list)
            @disabled_lut = icswTools.build_lut(@disabled_list)
            @all_lut = icswTools.build_lut(@all_list)
            @group_lut = icswTools.build_lut(@group_list)
            # set the clusterDevice Group
            if @cluster_device_group_device
                @cluster_device_group = @group_lut[@cluster_device_group_device.device_group]
            # init enrich requests
            @enrich_requests = []
            # console.log @enabled_list.length, @disabled_list.length, @all_list.length
            @link()

        link: () =>
            # create links between groups and devices
            for group in @group_list
                # reference to all devices
                group.devices = []
                group.$$meta_device = @all_lut[group.device]
            for entry in @all_list
                @salt_device(entry)
            for group in @group_list
                # num of all devices (enabled and disabled, also with md)
                group.num_devices_with_meta = group.devices.length
                group.num_devices = group.num_devices_with_meta - 1
            # create helper structures
            # console.log "link"

        salt_device: (device) =>
            # add info to device after loading
            # add enrichment info
            if not device.$$_enrichment_info?
                device.$$_enrichment_info = new icswEnrichmentInfo(device)
            # do not set group here to prevent circular dependencies in serializer
            # entry.group_object = @group_lut[entry.device_group]
            _group = @group_lut[device.device_group]
            if _group.devices == undefined
                _group.devices = []
            if device.idx not in _group.devices
                _group.devices.push(device.idx)
            device.$$group = _group
            device.$$meta_device = _group.$$meta_device
            # lock info
            @_update_scan_lock_info(device)

        _update_scan_lock_info: (device) =>
            device.$$active_scan_locks = (entry for entry in device.devicescanlock_set when entry.active).length
            device.$$any_scan_locks = if device.$$active_scan_locks then true else false

        device_class_is_enabled: (dev) =>
            return dev.device_class in @device_class_tree.enabled_idx_list

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

        # modification functions
        set_device_flags: (pk, kwargs) =>
            dev = @all_lut[pk]
            for key, value of kwargs
                dev[key] = value

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

        update_group: (upd_group) =>
            console.log "***", upd_group
            # is update group but in fact we update the corresponding meta device
            defer = $q.defer()
            Restangular.restangularizeElement(null, upd_group, ICSW_URLS.REST_DEVICE_GROUP_DETAIL.slice(1).slice(0, -2))
            upd_group.put().then(
                (data) =>
                    # console.log "***", upd_group
                    # replace device
                    _.remove(@all_list, (entry) -> return entry.idx == upd_group.device)
                    _.remove(@group_list, (entry) -> return entry.idx == upd_group.idx)
                    @group_list.push(data)
                    s1_defer = $q.defer()
                    @_fetch_device(data.device, s1_defer, "updated meta")
                    s1_defer.promise.then(
                        (done) =>
                            @reorder()
                            defer.resolve(data)
                    )
                (notok) ->
                    defer.reject("not saved")
            )
            return defer.promise

        delete_device_group: (dg_pk) =>
            if dg_pk of @group_lut
                group = @group_lut[dg_pk]
                _.remove(@all_list, (entry) -> return entry.idx == group.device)
                _.remove(@group_list, (entry) -> return entry.idx == dg_pk)
                @reorder()
            else
                console.error "trying to delete no longer existing device_group with pk=#{dg_pk}"

        # for device

        update_device: (upd_dev) =>
            defer = $q.defer()
            Restangular.restangularizeElement(null, upd_dev, ICSW_URLS.REST_DEVICE_TREE_DETAIL.slice(1).slice(0, -2))
            upd_dev.put().then(
                (data) =>
                    # replace device
                    _.remove(@all_list, (entry) -> return entry.idx == upd_dev.idx)
                    @all_list.push(data)
                    # root password magic
                    if upd_dev.root_passwd
                        upd_dev.root_passwd_set = true
                    s1_defer = $q.defer()
                    # reload meta device
                    _group = @group_lut[data.device_group]
                    _meta = _group.device
                    @_fetch_device(_group.device, s1_defer, "updated device")
                    s1_defer.promise.then(
                        (done) =>
                            @reorder()
                            defer.resolve(data)
                    )
                (notok) ->
                    defer.reject("not saved")
            )
            return defer.promise

        create_device: (new_dev) =>
            # create new device
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).post(new_dev).then(
                (new_obj) =>
                    @_fetch_device(new_obj.idx, defer, "created device ")
                (not_ok) ->
                    defer.reject("not created")
            )
            return defer.promise

        delete_device: (d_pk) =>
            console.warn "delete device with pk=#{d_pk}"
            _.remove(@all_list, (entry) -> return entry.idx == d_pk)
            @reorder()

        _fetch_device: (pk, defer, msg) =>
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList(
                {
                    pks: angular.toJson([pk])
                }
            ).then(
                (dev_list) =>
                    dev = dev_list[0]
                    _.remove(@all_list, (entry) -> return entry.idx == dev.idx)
                    # check if domain name tree is consistent
                    dnt_defer = $q.defer()
                    if dev.domain_tree_node of @domain_tree.lut
                        dnt_defer.resolve("done")
                    else
                        icswDomainTreeService.reload(@tree_id).then(
                            (reloaded) ->
                                dnt_defer.resolve("ok")
                        )
                    dnt_defer.promise.then(
                        (dnt_ok) =>
                            @salt_device(dev)
                            @all_list.push(dev)
                            if dev.device_group of @group_lut
                                @reorder()
                                defer.resolve(msg)
                            else
                                # new device-group added (at least the group is missing), fetch group
                                Restangular.one(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1)).get({idx: dev.device_group}).then(
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

        modify_netdevice: (mod_obj) =>
            # modify netdevice
            defer = $q.defer()
            Restangular.restangularizeElement(null, mod_obj, ICSW_URLS.REST_NETDEVICE_DETAIL.slice(1).slice(0, -2))
            mod_obj.put().then(
                (new_obj) =>
                    # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                    dev = @all_lut[new_obj.device]
                    dev.$$_enrichment_info.replace_netdevice(mod_obj, new_obj).then(
                        (done) =>
                            defer.resolve("save")
                    )
                (reject) =>
                    defer.reject("not saved")
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
            Restangular.one(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).get({idx: pk}).then(
                (new_nd) =>
                    new_nd = new_nd[0]
                    dev = @all_lut[new_nd.device]
                    dev.$$_enrichment_info.add_netdevice(new_nd).then(
                        (done) =>
                            defer.resolve(msg)
                    )
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
            Restangular.one(ICSW_URLS.REST_NET_IP_LIST.slice(1)).get({idx: pk}).then(
                (new_ip) =>
                    new_ip = new_ip[0]
                    dev = @all_lut[cur_nd.device]
                    dev.$$_enrichment_info.add_netip(new_ip, cur_nd)
                    defer.resolve(msg)
            )

        # for device Variables
        
        update_device_variable: (cur_var, helper) =>
            defer = $q.defer()
            Restangular.restangularizeElement(
                null
                cur_var
                ICSW_URLS.DEVICE_DEVICE_VARIABLE_DETAIL.slice(1).slice(0, -2)
            )
            cur_var.put().then(
                (mod_var) =>
                    helper.replace_device_variable(mod_var)
                    helper.salt_device_variables()
                    defer.resolve("updated")
                (not_ok) =>
                    defer.reject("not ok")
            )
            return defer.promise
            
        create_device_variable: (new_var, helper) =>
            # create new netIP
            defer = $q.defer()
            Restangular.all(ICSW_URLS.DEVICE_DEVICE_VARIABLE_LIST.slice(1)).post(new_var).then(
                (new_obj) =>
                    @_fetch_device_variable(new_obj.idx, defer, "created variable", helper)
                (not_ok) ->
                    defer.reject("variable not created")
            )
            return defer.promise

        delete_device_variable: (del_var, helper) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_var, ICSW_URLS.DEVICE_DEVICE_VARIABLE_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_var.remove().then(
                (ok) =>
                    dev = @all_lut[del_var.device]
                    # console.log del_var, dev.device_variable_set.length
                    _.remove(dev.device_variable_set, (entry) -> return entry.idx == del_var.idx)
                    # salt vars
                    helper.salt_device_variables()
                    # console.log del_var, dev.device_variable_set.length
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_device_variable: (pk, defer, msg, helper) =>
            Restangular.one(ICSW_URLS.DEVICE_DEVICE_VARIABLE_LIST.slice(1)).get({pk: pk}).then(
                (new_var) =>
                    dev = @all_lut[new_var.device]
                    dev.device_variable_set.push(new_var)
                    helper.salt_device_variables()
                    defer.resolve(msg)
            )

        # enrichment functions
        enrich_devices: (dth, en_list, force=false) =>
            # dth ... icswDeviceTreeHelper
            # en_list .. enrichment list
            defer  = $q.defer()
            @enrich_requests.push([dth, en_list, force, defer])
            # use timeout to merge all requests done in one $digest-cycle
            $timeout(
                () =>
                    # may be zero due to request merging
                    if @enrich_requests.length
                        # console.log "go", @enrich_requests.length
                        all_reqs = new icswEnrichmentRequest()
                        for [dth, en_list, force, defer] in @enrich_requests
                            # console.log "build"
                            # build request
                            en_req = @enricher.merge_requests(
                                (
                                    dev.$$_enrichment_info.build_request(en_list, force) for dev in dth.devices
                                )
                            )
                            if _.isEmpty(en_req)
                                # console.log "enrichment:", en_list, "for", dth, "not needed"
                                # empty request, just feed to dth
                                # resolve directly
                                # console.log "empty", en_req, en_list
                                _local_req = new icswEnrichmentRequest()
                                # feed info
                                _local_req.feed(dth, en_list, en_req, defer)
                                # console.log "empty"
                                # resolve with empty result
                                _local_req.feed_result(@enricher, {})
                            else
                                all_reqs.feed(dth, en_list, en_req, defer)
                        # reset list
                        @enrich_requests.length = 0
                        #console.log "*** enrichment:", en_list, "for", dth, "resulted in non-empty", en_req
                        # non-empty request, fetch from server
                        icswSimpleAjaxCall(
                            url: ICSW_URLS.DEVICE_ENRICH_DEVICES
                            data: {
                                enrich_request: angular.toJson(all_reqs.all_lut)
                            }
                            dataType: "json"
                        ).then(
                            (result) =>
                                all_reqs.feed_result(@enricher, result)
                            (error) ->
                                console.error "enrich error"
                        )
                0
            )
            return defer.promise

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

        register_device_scan: (dev, scan_settings) =>
            defer = $q.defer()

            # start scan on server
            icswSimpleAjaxCall(
                url: ICSW_URLS.DEVICE_SCAN_DEVICE_NETWORK
                data:
                    settings: angular.toJson(scan_settings)
            ).then(
                (xml) =>
                    # scan startet (or already done for base-scan because base-scan is synchronous)
                    defer.resolve("scan started")
                (error) =>
                    defer.reject("scan not ok")
            )

            return defer.promise

        add_scanlock_to_device: (lock_data) =>
            pk = lock_data.device
            if pk of @all_lut
                # console.log "L", lock_data
                _dev = @all_lut[pk]
                _.remove(_dev.devicescanlock_set, (entry) -> return entry.idx == lock_data.idx)
                _dev.devicescanlock_set.push(lock_data)
                @_update_scan_lock_info(_dev)
                if not _dev.$$any_scan_locks
                    # refresh network and com_info
                    @enrich_devices(new icswDeviceTreeHelper(@, [_dev]), ["com_info", "network_info"], true).then(
                        (result) =>
                            console.log "enriched"
                            $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_SCAN_CHANGED"), _dev.idx)
                    )
                $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_SCAN_CHANGED"), _dev.idx)
            else
                console.error "got devicescanlock data for unknown device", lock_data

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

            # add the cluster device group if not already in list
            if @cluster_device_group_device.idx not in _res
                _res.push(@cluster_device_group_device.idx)
            # console.log "trace: in #{devs.length}, out #{_res.length}"
            return (@all_lut[idx] for idx in _res)

        # category functions
        add_category_to_device_by_pk: (dev_pk, cat_pk) =>
            @add_category_to_device(@all_lut[dev_pk], cat_pk)

        add_category_to_device: (dev, cat_pk) =>
            dev.categories.push(cat_pk)

        remove_category_from_device_by_pk: (dev_pk, cat_pk) =>
            @remove_category_from_device(@all_lut[dev_pk], cat_pk)

        remove_category_from_device: (dev, cat_pk) =>
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
            Restangular.one(ICSW_URLS.REST_CD_CONNECTION_LIST.slice(1)).get({idx: pk}).then(
                (new_cd) =>
                    new_cd = new_cd[0]
                    p_dev = @all_lut[new_cd.parent]
                    s_dev = @all_lut[new_cd.child]
                    p_dev.device_connection_set.push(new_cd)
                    s_dev.device_connection_set.push(new_cd)
                    hs.post_g_device_connection_info()
                    defer.resolve(msg)
            )

        # network graph functions
        seed_network_graph: (nodes, links, xy_dict) =>
            return new icswDeviceTreeGraph(nodes, links, @, xy_dict)

        # dispatcher functions
        salt_dispatcher_infos: (device_list, disp_tree) =>
            for dev in device_list
                # console.log dev.past_assetrun_set
                dev.$$sched_item_list = []
                dev.$$dispatcher_list = []
                if dev.dispatcher_set.length
                    dev.$$dispatcher_list = (disp_tree.lut[entry.dispatcher_setting] for entry in dev.dispatcher_set)
                    dev.$$dispatcher_sched_lut = {}
                    for disp in dev.$$dispatcher_list
                        dev.$$dispatcher_sched_lut[disp.idx] = []
                        # disp is now a dispatcherSetting
                        for entry in disp.$$sched_item_list
                            if entry.device == dev.idx
                                dev.$$dispatcher_sched_lut[disp.idx].push(entry)
                                dev.$$sched_item_list.push(entry)
                    
                else
                    dev.$$dispatcher_list = []
            
        sync_dispatcher_links: (device, dispatcher_tree, disp_idxs, user) =>
            # global deferer
            defer = $q.defer()
            # syncs the dispatcher-device links of device with the dispatchers specified in disp_idxs
            _cur_idx = (disp.dispatcher_setting for disp in device.dispatcher_set)
            _to_add = (idx for idx in disp_idxs when idx not in _cur_idx)
            _to_del = (idx for idx in _cur_idx when idx not in disp_idxs)
            # create and delete defer
            [_c_defer, _d_defer] = [$q.defer(), $q.defer()]
            if _to_add.length
                _w_list = (
                    Restangular.all(ICSW_URLS.REST_DISPATCHER_LINK_LIST.slice(1)).post(
                        {
                            model_name: "device"
                            object_id: device.idx
                            dispatcher_setting: _add_idx
                            user: user.idx
                            schedule_handler: "asset_schedule_handler"
                        }
                    ) for _add_idx in _to_add
                )
                $q.all(_w_list).then(
                    (results) ->
                        for entry in results
                            device.dispatcher_set.push(entry)
                        # console.log results
                        _c_defer.resolve("created")
                )
            else
                _c_defer.resolve("nothing to do")
            if _to_del.length
                _d_list = []
                for _del_disp in (entry for entry in device.dispatcher_set when entry.dispatcher_setting in _to_del)
                    Restangular.restangularizeElement(null, _del_disp, ICSW_URLS.REST_DISPATCHER_LINK_DETAIL.slice(1).slice(0, -2))
                    _d_list.push(_del_disp.remove())
                $q.all(_d_list).then(
                    (result) ->
                        _.remove(device.dispatcher_set, (entry) -> return entry.dispatcher_setting in _to_del)
                        _d_defer.resolve("removed")
                )
            else
                _d_defer.resolve("nothing to do")
            $q.all([_c_defer.promise, _d_defer.promise]).then(
                () ->
                    defer.resolve("done")
                () ->
                    defer.reject("not done")
            )
            return defer.promise

]).service("icswDeviceTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswDeviceClassTreeService",
    "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS", "icswNetworkTreeService";
    "icswDomainTreeService", "icswCategoryTreeService", "icswDeviceVariableScopeTreeService",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswDeviceClassTreeService,
    icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS, icswNetworkTreeService,
    icswDomainTreeService, icswCategoryTreeService, icswDeviceVariableScopeTreeService,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_DEVICE_TREE_LIST
            {
                # ignore_cdg: false
                # tree_mode: true
                # all_devices: true
                # with_categories: true
                # ignore_disabled: true
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
        _wait_list.push(icswNetworkTreeService.load(client))
        _wait_list.push(icswCategoryTreeService.load(client))
        _wait_list.push(icswDeviceVariableScopeTreeService.load(client))
        _wait_list.push(icswDeviceClassTreeService.load(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** device tree loaded ***"
                _result = new icswDeviceTree(data[0], data[1], data[2], data[3], data[4], data[5], data[6])
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
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        current: () ->
            return _result
    }
]).service("icswDeviceTreeGraph",
[
    "$q",
(
    $q,
) ->
    class icswDeviceTreeGraph
        constructor: (@nodes, @links, tree, xy_dict) ->
            @device_list = []
            _set_coords = false
            for node in @nodes
                node.$$device = tree.all_lut[node.id]
                @device_list.push(node.$$device)
                if node.id of xy_dict
                    node.x = xy_dict[node.id].x
                    node.y = xy_dict[node.id].y
                if not node.x?
                    _set_coords = true

            if _set_coords
                _id = 0
                for node in @nodes
                    _id++
                    # init coordinates if needed
                    _angle = 2 * Math.PI * @nodes.length / _id
                    if not node.x?
                        node.x = Math.cos(_angle) * 50
                        node.y = Math.sin(_angle) * 50
                    node.radius = 10
            # enumerate links
            _id = 0
            for link in @links
                link.id = _id
                _id++
            # create luts
            @nodes_lut = _.keyBy(@nodes, "id")
            @links_lut = _.keyBy(@links, "id")

        # helper functions
        node_to_dom_id: (node) ->
            return "n#{node.id}"

        dom_id_to_node: (id) =>
            return @nodes_lut[parseInt(id.slice(1))]

        link_to_dom_id: (link) ->
            return "l#{link.id}"

        dom_id_to_link: (id) =>
            return @links_lut[parseInt(id.slice(1))]

])
