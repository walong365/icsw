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
    "icsw.svg_tools",
    []
).factory("svg_tools", () ->
    return {
        has_class_svg: (obj, has) ->
            classes = obj.attr("class")
            if !classes
                return false
            return if classes.search(has) == -1 then false else true
        get_abs_coordinate : (svg_el, x, y) ->
            screen_ctm = svg_el.getScreenCTM()
            svg_point = svg_el.createSVGPoint()
            svg_point.x = x
            svg_point.y = y
            first = svg_point.matrixTransform(screen_ctm.inverse())
            return first
            glob_to_local = event.target.getTransformToElement(scope.svg_el)
            second = first.matrixTransform(glob_to_local.inverse())
            return second
    }
)

angular.module(
    "icsw.mouseCapture",
    []
).factory('mouseCaptureFactory', ["$rootScope", ($rootScope) ->
    $element = document
    mouse_capture_config = null
    mouse_move = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_move
            mouse_capture_config.mouse_move(event)
            $rootScope.$digest()
    mouse_up = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_up
            mouse_capture_config.mouse_up(event)
            $rootScope.$digest()
    return {
        register_element: (element) ->
            $element = element
        acquire: (event, config) ->
            this.release()
            mouse_capture_config = config
            $element.mousemove(mouse_move)
            $element.mouseup(mouse_up)
        release: () ->
            if mouse_capture_config
                if mouse_capture_config.released
                    mouse_capture_config.released()
                mouse_capture_config = null;
                $element.unbind("mousemove", mouse_move)
                $element.unbind("mouseup", mouse_up)
    }
]).directive('icswMouseCapture', () ->
    return {
        restrict: "A"
        controller: ["$scope", "$element", "mouseCaptureFactory", ($scope, $element, mouseCaptureFactory) ->
            mouseCaptureFactory.register_element($element)
        ]
    }
)

angular.module(
    "icsw.dragging",
    [
        "icsw.mouseCapture"
    ]
).factory("dragging", ["$rootScope", "mouseCaptureFactory", ($rootScope, mouseCaptureFactory) ->
    return {
        start_drag: (event, threshold, config) ->
            dragging = false
            x = event.clientX
            y = event.clientY
            mouse_move = (event) ->
                if !dragging
                    if Math.abs(event.clientX - x) > threshold or Math.abs(event.clientY - y) > threshold
                        dragging = true;
                        if config.dragStarted
                            config.dragStarted(x, y, event)
                        if config.dragging
                            config.dragging(event.clientX, event.clientY, event)
                else 
                    if config.dragging
                        config.dragging(event.clientX, event.clientY, event);
                    x = event.clientX
                    y = event.clientY
            released = () ->
                if dragging
                    if config.dragEnded
                        config.dragEnded()
                else 
                    if config.clicked
                        config.clicked()
            mouse_up = (event) ->
                mouseCaptureFactory.release()
                event.stopPropagation()
                event.preventDefault()
            mouseCaptureFactory.acquire(event, {
                mouse_move: mouse_move
                mouse_up: mouse_up
                released: released
            })
            event.stopPropagation()
            event.preventDefault()
    }
])

angular.module(
    "icsw.device.network",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.devicenetwork", {
            url: "/network"
            template: '<icsw-device-network-total></icsw-device-network-total>'
            data:
                pageTitle: "Network"
                rights: ["device.change_network"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-sitemap"
                    ordering: 30
        }
    )
]).controller("icswDeviceNetworkCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource",
     "$q", "$uibModal", "icswAcessLevelService", "$rootScope", "$timeout", "blockUI", "icswTools", "icswToolsButtonConfigService", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswToolsSimpleModalService", "icswDeviceTreeService",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource,
     $q, $uibModal, icswAcessLevelService, $rootScope, $timeout, blockUI, icswTools, icswToolsButtonConfigService, ICSW_URLS,
     icswSimpleAjaxCall, icswToolsSimpleModalService, icswDeviceTreeService
    ) ->
        $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
        icswAcessLevelService.install($scope)
        # copy flags
        $scope.show_copy_button = false
        # accordion flags
        $scope.device_open = true
        $scope.netdevice_open = true
        $scope.netip_open = false
        $scope.peer_open = false
        $scope.copy_coms = false
        # mixins
        $scope.netdevice_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "nd")
        $scope.netdevice_edit.create_template = "netdevice.form"
        $scope.netdevice_edit.edit_template = "netdevice.form"
        $scope.netdevice_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_NETDEVICE_LIST.slice(1))
        $scope.netdevice_edit.modify_rest_url = ICSW_URLS.REST_NETDEVICE_DETAIL.slice(1).slice(0, -2)
        $scope.netdevice_edit.new_object_at_tail = false
        $scope.netdevice_edit.use_promise = true

        $scope.netip_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "ni")
        $scope.netip_edit.create_template = "net.ip.form"
        $scope.netip_edit.edit_template = "net.ip.form"
        $scope.netip_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_NET_IP_LIST.slice(1))
        $scope.netip_edit.modify_rest_url = ICSW_URLS.REST_NET_IP_DETAIL.slice(1).slice(0, -2)
        $scope.netip_edit.new_object_at_tail = false
        $scope.netip_edit.use_promise = true

        $scope.peer_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "np")
        $scope.peer_edit.create_template = "peer.information.form"
        $scope.peer_edit.edit_template = "peer.information.form"
        #$scope.peer_edit.edit_template = "netip_template.html"
        $scope.peer_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_PEER_INFORMATION_LIST.slice(1))
        $scope.peer_edit.modify_rest_url = ICSW_URLS.REST_PEER_INFORMATION_DETAIL.slice(1).slice(0, -2)
        $scope.peer_edit.new_object_at_tail = false
        $scope.peer_edit.use_promise = true

        $scope.boot_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "nb")
        $scope.boot_edit.edit_template = "device.boot.form"
        $scope.boot_edit.put_parameters = {"only_boot" : true}
        $scope.boot_edit.modify_rest_url = ICSW_URLS.REST_DEVICE_TREE_DETAIL.slice(1).slice(0, -2)
        $scope.boot_edit.new_object_at_tail = false
        $scope.boot_edit.use_promise = true

        $scope.scan_mixin = new angular_modal_mixin($scope, $templateCache, $compile, $q, "Scan network")
        $scope.scan_mixin.template = "device.network.scan.form"
        $scope.scan_mixin.cssClass = "modal-tall"

        $scope.ethtool_autoneg = [
            {"id": 0, "option": "default"},
            {"id": 1, "option": "on"},
            {"id": 2, "option": "off"},
        ]
        $scope.ethtool_duplex = [
            {"id": 0, "option": "default"},
            {"id": 1, "option": "on"},
            {"id": 2, "option": "off"},
        ]
        $scope.ethtool_speed = [
            {"id": 0, "option": "default"},
            {"id": 1, "option": "10 MBit"},
            {"id": 2, "option": "100 MBit"},
            {"id": 3, "option": "1 GBit"},
            {"id": 4, "option": "10 GBit"},
        ]
        $scope.devsel_list = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload= () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_network" : true, "with_com_info": true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_network"}]),
                restDataSource.reload([ICSW_URLS.REST_PEER_INFORMATION_LIST, {}]),
                # 2
                restDataSource.reload([ICSW_URLS.REST_NETDEVICE_SPEED_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST, {}])
                # 4
                restDataSource.reload([ICSW_URLS.REST_NETWORK_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, {}])
                # 6
                restDataSource.reload([ICSW_URLS.REST_NETDEVICE_PEER_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_SNMP_NETWORK_TYPE_LIST, {}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = (dev for dev in data[0])
                $scope.peers = data[1]
                $scope.netdevice_speeds = data[2]
                $scope.desired_stati = [
                    {"short": "i", "info_string": "ignore"}
                    {"short": "u", "info_string": "must be up"}
                    {"short": "d", "info_string": "must be down"}
                ]
                $scope.network_device_types = data[3]
                $scope.ndt_lut = icswTools.build_lut($scope.network_device_types)
                $scope.networks = data[4]
                $scope.network_lut = icswTools.build_lut($scope.networks)
                $scope.domain_tree_node = data[5]
                $scope.dtn_lut = icswTools.build_lut($scope.domain_tree_node)
                $scope.nd_peers = data[6]
                $scope.build_luts()
                # snmp network types
                $scope.snt = data[7]
                $scope.snt_lut = icswTools.build_lut($scope.snt)
            )
        # new selection
        if $scope.devicelist?
            $scope.dev_tree = icswDeviceTreeService.current()
            console.log "nwsel"
            $scope.new_devsel($scope.devicelist)
        else
            # install receiver from icsw-sel-man
            $scope.selection_changed = () ->
                # called when run in full-screen mode (not overview)
                $scope.dev_tree = icswDeviceTreeService.current()
                $scope.new_devsel((scope.dev_tree.all_lut[pk] for pk in icswActiveSelectionService.current().tot_dev_sel))
            $scope.register_receiver()

        $scope.build_luts = () ->
            $scope.dev_lut = {}
            $scope.nd_lut = {}
            $scope.ip_lut = {}
            for dev in $scope.devices
                $scope.dev_lut[dev.idx] = dev
                dev.previous_scan = dev.active_scan
                for nd in dev.netdevice_set
                    nd.peers = []
                    $scope.nd_lut[nd.idx] = nd
                    for ip in nd.net_ip_set
                        $scope.ip_lut[ip.idx] = ip
            $scope.nd_peer_lut = {}
            for ext_peer in $scope.nd_peers
                ext_peer.info_string = "#{ext_peer.devname} (#{ext_peer.penalty}) on #{ext_peer.fqdn} (#{ext_peer.device_group_name})"
                $scope.nd_peer_lut[ext_peer.idx] = ext_peer
            $scope.peer_lut = {}
            for peer in $scope.peers
                $scope.peer_lut[peer.idx] = peer
                if peer.s_netdevice of $scope.nd_lut
                    $scope.nd_lut[peer.s_netdevice].peers.push({"peer" : peer, "netdevice" : peer.s_netdevice, "target" : peer.d_netdevice})
                if peer.d_netdevice of $scope.nd_lut and peer.s_netdevice != peer.d_netdevice
                    $scope.nd_lut[peer.d_netdevice].peers.push({"peer" : peer, "netdevice" : peer.d_netdevice, "target" : peer.s_netdevice})
        $scope.get_flags = (nd) ->
            _f = []
            if nd.routing
                _f.push("extrouting")
            if nd.inter_device_routing
                _f.push("introuting")
            if !nd.enabled
                _f.push("disabled")
            return _f.join(", ")
        $scope.get_bridge_info = (nd) ->
            dev = $scope.dev_lut[nd.device]
            if nd.is_bridge
                slaves = (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx)
                if slaves.length
                    return "bridge" + " (" + slaves.join(", ") + ")"
                else
                    return "bridge"
            else if nd.bridge_device
                return "slave (" + $scope.nd_lut[nd.bridge_device].devname + ")"
            else
                return ""
        $scope.get_bond_info = (nd) ->
            dev = $scope.dev_lut[nd.device]
            if nd.is_bond
                slaves = (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bond_master == nd.idx)
                if slaves.length
                    return "master" + " (" + slaves.join(", ") + ")"
                else
                    return "master"
            else if nd.bond_master
                return "slave (" + $scope.nd_lut[nd.bond_master].devname + ")"
            else
                return ""
        $scope.has_bridge_slaves = (nd) ->
            dev = $scope.dev_lut[nd.device]
            if nd.is_bridge
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx).length then true else false
            else
                return false
        $scope.has_bond_slaves = (nd) ->
            dev = $scope.dev_lut[nd.device]
            if nd.is_bond
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bond_master == nd.idx).length then true else false
            else
                return false
        $scope.get_netdevice_name = (nd) ->
            if angular.isNumber(nd)
                nd = $scope.nd_lut[nd]
            nd_name = nd.devname
            if nd.description
                nd_name = "#{nd_name} (#{nd.description})"
            if nd.vlan_id
                if nd.master_device
                    nd_name = "#{nd_name}, VLAN #{nd.vlan_id} on " + String($scope.nd_lut[nd.master_device].devname)
                else
                    nd_name = "#{nd_name}, VLAN #{nd.vlan_id}"
            return nd_name
        $scope.get_netdevice_boot_info = (nd) ->
            num_boot = (true for net_ip in nd.net_ip_set when $scope.network_lut[net_ip.network].network_type_identifier == "b").length
            if num_boot == 0
                return ""
            else if num_boot == 1
                return "(b)"
            else
                return "(#{num_boot})"
        $scope.get_num_netdevices = (dev) ->
            return dev.netdevice_set.length
        $scope.no_objects_defined = (dev) ->
            return if (dev.netdevice_set.length == 0) then true else false
        $scope.get_num_netips_nd = (nd) ->
            return nd.net_ip_set.length
        $scope.get_num_netips_dev = (dev) ->
            _n = 0
            for nd in dev.netdevice_set
                _n += nd.net_ip_set.length
            return _n
        $scope.get_num_peers_nd = (nd) ->
            return nd.peers.length
        $scope.get_num_peers_dev = (dev) ->
            _n = 0
            for nd in dev.netdevice_set
                _n += nd.peers.length
            return _n
        $scope.get_route_peers =() ->
            return (entry for entry in $scope.nd_peers when entry.routing)
        $scope.get_ndip_objects = (dev) ->
            r_list = []
            for ndev in dev.netdevice_set
                r_list.push(ndev)
                r_list = r_list.concat(ndev.net_ip_set)
                r_list = r_list.concat(ndev.peers)
            return r_list
        $scope.get_ip_objects = (src_obj) ->
            r_list = []
            if src_obj and src_obj.devname?
                r_list = src_obj.net_ip_set
            else
                for dev in $scope.devices
                    for ndev in dev.netdevice_set
                        r_list = r_list.concat(ndev.net_ip_set)
            return r_list
        $scope.get_nd_objects = () ->
            r_list = []
            for dev in $scope.devices
                for ndev in dev.netdevice_set
                    r_list.push(ndev)
            return r_list
        $scope.get_peer_objects = () ->
            r_list = []
            for dev in $scope.devices
                for ndev in dev.netdevice_set
                    r_list = r_list.concat(ndev.peers)
            return r_list
        $scope.set_scan_mode = (sm) ->
            $scope.scan_device.scan_mode = sm
            $scope.scan_device["scan_#{sm}_active"] = true
        $scope.has_com_capability = (dev, cc) ->
            return cc in dev.com_caps
        $scope.scan_device_network = (dev, event) ->
            $scope._current_dev = dev
            $scope.scan_device = dev
            network_type_names = []
            ip_dict = {}
            for ndev in dev.netdevice_set
                for ip in ndev.net_ip_set
                    if ip.network of $scope.network_lut
                        network = $scope.network_lut[ip.network]
                        if network.network_type_identifier != "l" and not (network.netmask == "255.0.0.0" and network.network == "127.0.0.0")
                            if network.network_type_name not of ip_dict
                                ip_dict[network.network_type_name] = []
                                network_type_names.push(network.network_type_name)
                            ip_dict[network.network_type_name].push(ip.ip)
            for key, value of ip_dict
                ip_dict[key] = _.uniq(_.sortBy(value))
            network_type_names = _.sortBy(network_type_names)
            dev.ip_dict = ip_dict
            dev.network_type_names = network_type_names

            dev.manual_address = ""
            # set ip if there is only one
            if Object.keys(ip_dict).length == 1
                nw_ip_addresses = ip_dict[ Object.keys(ip_dict)[0] ]
                if nw_ip_addresses.length == 1
                    dev.manual_address = nw_ip_addresses[0]

            dev.snmp_community = "public"
            if not dev.com_caps?
                # init com_caps array if not already set
                dev.com_caps = []
            dev.snmp_version = "2c"
            dev.remove_not_found = false
            dev.strict_mode = true
            dev.modify_peering = false
            dev.wmi_username = "Administrator"
            dev.wmi_password = ""
            dev.wmi_discard_disabled_interfaces = true
            dev.scan_base_active = false
            dev.scan_hm_active = false
            dev.scan_snmp_active = false
            if not $scope.no_objects_defined(dev) and $scope.has_com_capability(dev, "snmp")
                $scope.set_scan_mode("snmp")
            else
                $scope.set_scan_mode("base")
            $scope.scan_mixin.edit(dev, event).then(
                (mod_obj) ->
                    true
            )
        $scope.fetch_device_network = () ->
            blockUI.start()
            _dev = $scope._current_dev
            _dev.scan_address = _dev.manual_address
            # intermediate state to trigger reload
            _dev.active_scan = "waiting"
            icswSimpleAjaxCall(
                url     : ICSW_URLS.DEVICE_SCAN_DEVICE_NETWORK
                data    :
                    "dev" : angular.toJson($scope.scan_device)
            ).then((xml) ->
                blockUI.stop()
                $scope.scan_mixin.close_modal()
                $scope.update_scans()
            )
        $scope.update_scans = () ->
            Restangular.all(ICSW_URLS.NETWORK_GET_ACTIVE_SCANS.slice(1)).getList({"pks" : angular.toJson($scope.devsel_list)}).then(
                (data) ->
                    any_scans_running = false
                    for obj in data
                        dev = $scope.dev_lut[obj["pk"]]
                        dev.previous_scan = dev.active_scan
                        dev.active_scan = obj.active_scan
                        if dev.active_scan != dev.previous_scan
                            if not dev.active_scan
                                # scan finished
                                $q.all(
                                    [
                                        Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList({"with_network" : true, "pks" : angular.toJson([dev.idx]), "olp" : "backbone.device.change_network"})
                                        Restangular.all(ICSW_URLS.REST_PEER_INFORMATION_LIST.slice(1)).getList(),
                                        Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).getList(),
                                    ]
                                ).then((data) ->
                                    $scope.networks = data[2]
                                    $scope.peers = data[1]
                                    $scope.network_lut = icswTools.build_lut($scope.networks)
                                    $scope.update_device(data[0][0])
                                )
                        if obj.active_scan
                            any_scans_running = true
                    if any_scans_running
                        $timeout($scope.update_scans, 5000)
            )
        $scope.update_device = (new_dev) ->
            cur_devs = []
            for dev in $scope.devices
                if dev.idx == new_dev.idx
                    cur_devs.push(new_dev)
                else
                    cur_devs.push(dev)
            $scope.devices = cur_devs
            $scope.build_luts()
        $scope.create_netdevice = (obj, event) ->
            $scope.netdevice_edit.create_list = obj.netdevice_set
            $scope.netdevice_edit.title = "New Netdevice"
            $scope.netdevice_edit.new_object = (scope) ->
                _dev = {
                    "device" : obj.idx
                    "devname" : "eth0"
                    "enabled" : true
                    "netdevice_speed" : (entry.idx for entry in $scope.netdevice_speeds when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
                    "ignore_netdevice_speed": false
                    "desired_status": "i"
                    "penalty" : 1
                    "net_ip_set" : []
                    "ethtool_options" : 0
                    "ethtool_autoneg" : 0
                    "ethtool_speed" : 0
                    "ethtool_duplex" : 0
                    "mtu": 1500
                    # dummy value
                    "network_device_type" : $scope.network_device_types[0].idx
                } 
                return _dev
            $scope.netdevice_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        new_obj.net_ip_set = []
                        new_obj.peers = []
                        $scope.nd_lut[new_obj.idx] = new_obj
                        $scope.check_for_peer_change(new_obj)
            )
        $scope.edit_netdevice = (ndev, event) ->
            $scope.netdevice_edit.title = "Netdevice '#{ndev.devname}'"
            $scope.netdevice_edit.edit(ndev, event).then(
                (mod_ndev) ->
                    if mod_ndev != false
                        $scope.check_for_peer_change(mod_ndev)
            )
        $scope.edit_boot_settings = (obj, event) ->
            $scope.boot_edit.edit(obj, event).then(
                (mod_dev) ->
                    true
            )
        $scope.check_for_peer_change = (ndev) ->
            # at first remove from list
            $scope.nd_peers = (entry for entry in $scope.nd_peers when entry.idx != ndev.idx)
            if ndev.routing
                _cd = $scope.dev_lut[ndev.device]
                ndev.fqdn = _cd.full_name
                ndev.device_name = _cd.name
                ndev.device_group_name = _cd.device_group_name
                $scope.nd_peers.push(ndev)
            $scope.build_luts()
        $scope.get_vlan_masters = (cur_nd) ->
            _cd = $scope.dev_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and not entry.is_bridge and not entry.is_bond)
        $scope.get_bridge_masters = (cur_nd) ->
            _cd = $scope.dev_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bridge)
        $scope.get_bond_masters = (cur_nd) ->
            _cd = $scope.dev_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bond)
        $scope.create_netip_dev = (obj, event) ->
            $scope._current_dev = obj
            $scope.netip_edit.create_list = undefined
            $scope.netip_edit.title = "New IP"
            $scope.netip_edit.new_object = (scope) ->
                return {
                    "netdevice" : (entry.idx for entry in obj.netdevice_set)[0]
                    "ip" : "0.0.0.0"
                    "_changed_by_user_": false
                    "network" : $scope.networks[0].idx
                    # copy domain tree node from device
                    "domain_tree_node" : obj.domain_tree_node
                } 
            $scope.netip_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.nd_lut[new_obj.netdevice].net_ip_set.push(new_obj)
                        $scope.ip_lut[new_obj.idx] = new_obj
            )
        $scope.create_netip_nd = (obj, event) ->
            $scope._current_dev = $scope.dev_lut[obj.device]
            $scope.netip_edit.create_list = undefined
            $scope.netip_edit.title = "New IP"
            $scope.netip_edit.new_object = (scope) ->
                return {
                    "netdevice" : obj.idx
                    "ip" : "0.0.0.0"
                    "_changed_by_user_": false
                    "network" : $scope.networks[0].idx
                    # take first domain tree node
                    "domain_tree_node" : $scope.domain_tree_node[0].idx
                } 
            $scope.netip_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.nd_lut[new_obj.netdevice].net_ip_set.push(new_obj)
                        $scope.ip_lut[new_obj.idx] = new_obj
            )
        $scope.edit_netip = (ip, event) ->
            $scope._current_dev = $scope.dev_lut[$scope.nd_lut[ip.netdevice].device]
            $scope.netip_edit.title = "Edit IP '#{ip.ip}'"
            $scope.netip_edit.edit(ip, event).then(
                (mod_ip) ->
                    if mod_ip != false
                        true
            )
        $scope.get_peer_src_info = (_edit_obj) ->
            if $scope.source_is_local
                _nd = $scope.nd_lut[$scope._edit_obj.s_netdevice]
            else
                _nd = $scope.nd_lut[$scope._edit_obj.d_netdevice]
            if _nd
                return _nd.devname + " on " + $scope.dev_lut[_nd.device].name
            else
                return "???"
        $scope.edit_peer_information = (peer, event) ->
            if peer.peer.s_netdevice == peer.netdevice
                $scope.source_is_local = true
            else
                $scope.source_is_local = false
            $scope.peer_edit.edit(peer.peer, event).then(
                (mod_peer) ->
                    if mod_peer != false
                        # rebuild luts
                        $scope.build_luts()
            )
        $scope.delete_peer_information = (ndip_obj, event) ->
            # find device / netdevice
            peer = ndip_obj.peer
            $scope.peer_edit.delete_list = undefined
            $scope.peer_edit.delete_obj(peer).then(
                (res) ->
                    if res
                        if peer.s_netdevice of $scope.nd_lut
                            $scope.nd_lut[peer.s_netdevice].peers = (entry for entry in $scope.nd_lut[peer.s_netdevice].peers when entry.peer.idx != peer.idx)
                        if peer.d_netdevice of $scope.nd_lut
                            $scope.nd_lut[peer.d_netdevice].peers = (entry for entry in $scope.nd_lut[peer.d_netdevice].peers when entry.peer.idx != peer.idx)
                        delete $scope.peer_lut[peer.idx]
            )
        $scope.create_peer_information_dev = (obj, event) ->
            $scope._current_dev = obj
            $scope.source_is_local = true
            $scope.peer_edit.create_list = undefined
            $scope.peer_edit.new_object = (scope) ->
                return {
                    "s_netdevice" : (entry.idx for entry in obj.netdevice_set)[0]
                    "penalty" : 1
                } 
            $scope.create_peer_information(event)
        $scope.create_peer_information_nd = (obj, event) ->
            $scope._current_dev = $scope.dev_lut[obj.device]
            $scope.source_is_local = true
            $scope.peer_edit.create_list = undefined
            $scope.peer_edit.new_object = (scope) ->
                return {
                    "s_netdevice" : obj.idx
                    "penalty" : 1
                } 
            $scope.create_peer_information(event)
        $scope.create_peer_information = (event) ->
            $scope.peer_edit.create(event).then(
                (peer) ->
                    if peer != false
                        $scope.peer_lut[peer.idx] = peer
                        if peer.s_netdevice of $scope.nd_lut
                            $scope.nd_lut[peer.s_netdevice].peers.push({"peer" : peer, "netdevice" : peer.s_netdevice, "target" : peer.d_netdevice})
                        if peer.d_netdevice of $scope.nd_lut and peer.s_netdevice != peer.d_netdevice
                            $scope.nd_lut[peer.d_netdevice].peers.push({"peer" : peer, "netdevice" : peer.d_netdevice, "target" : peer.s_netdevice})
            )
        $scope.delete_netip = (ip, event) ->
            # find device / netdevice
            $scope.netip_edit.delete_list = $scope.nd_lut[ip.netdevice].net_ip_set
            $scope.netip_edit.delete_obj(ip).then(
                (res) ->
                    if res
                        true
            )
        $scope.delete_netdevice = (nd, event) ->
            # find device / netdevice
            $scope.netdevice_edit.delete_list = $scope.dev_lut[nd.device].netdevice_set
            $scope.netdevice_edit.delete_obj(nd).then(
                (res) ->
                    if res
                        true
            )
        $scope.ethtool_options = (ndip_obj, type) ->
            if type == "a"
                eth_opt = ndip_obj.ethtool_options & 3
                return {0 : "default", 1 : "on", 2 : "off"}[eth_opt]
            else if type == "d"
                eth_opt = (ndip_obj.ethtool_options >> 2) & 3
                return {0 : "default", 1 : "on", 2 : "off"}[eth_opt]
            else if type == "s"
                eth_opt = (ndip_obj.ethtool_options >> 4) & 7
                return {0 : "default", 1 : "10 MBit", 2 : "100 MBit", 3 : "1 GBit", 4 : "10 GBit"}[eth_opt]
        $scope.update_ethtool = (ndip_obj) ->
            ndip_obj.ethtool_options = (parseInt(ndip_obj.ethtool_speed) << 4) | (parseInt(ndip_obj.ethtool_duplex) << 2) < (parseInt(ndip_obj.ethtool_autoneg))
        $scope.get_peer_cost = (ndip_obj) ->
            if ndip_obj.target of $scope.nd_lut
                t_cost = $scope.nd_lut[ndip_obj.target].penalty
            else
                if ndip_obj.target of $scope.nd_peer_lut
                    t_cost = $scope.nd_peer_lut[ndip_obj.target].penalty
                else
                    return "N/A"
            return t_cost + ndip_obj.peer.penalty + $scope.nd_lut[ndip_obj.netdevice].penalty
        $scope.get_peer_target = (ndip_obj) ->
            if ndip_obj.target of $scope.nd_lut
                peer = $scope.nd_lut[ndip_obj.target]
                _dev = $scope.dev_lut[peer.device]
                if _dev.domain_tree_node of $scope.dtn_lut
                    _domain = "." + $scope.dtn_lut[_dev.domain_tree_node].full_name
                else
                    _domain = ""
                return "#{peer.devname} (#{peer.penalty}) on " + String(_dev.name) + _domain
            else
                if ndip_obj.target of $scope.nd_peer_lut
                    peer = $scope.nd_peer_lut[ndip_obj.target]
                    return "#{peer.devname} (#{peer.penalty}) on #{peer.fqdn}"
                else
                    return "N/A (disabled device ?)"
        $scope.get_peer_type = (peer) ->
            source = peer.netdevice
            dest = peer.target
            if source of $scope.nd_lut
                source = $scope.nd_lut[source]
            else
                source = undefined
            if dest of $scope.nd_lut
                dest = $scope.nd_lut[dest]
            else
                dest = undefined
            if source and dest
                return if source.device == dest.device then "local" else "remote"
            else
                return "---"
        $scope.toggle_copy_com = () ->
            $scope.copy_coms = !$scope.copy_coms
        $scope.copy_com_class = () ->
            if $scope.copy_coms
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm btn-default"
        $scope.copy_com_value = () ->
            if $scope.copy_coms
                return "Copy Coms and Schemes"
            else
                return "start with empty Coms and Schemes"
        $scope.copy_network = (src_obj, event) ->
            icswToolsSimpleModalService("Overwrite all networks with the one from #{src_obj.full_name} ?").then(
                () ->
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url     : ICSW_URLS.NETWORK_COPY_NETWORK
                        data    : {
                            "source_dev" : src_obj.idx
                            "copy_coms"  : $scope.copy_coms
                            "all_devs"   : angular.toJson($scope.devsel_list)
                        }
                    ).then((xml) ->
                        blockUI.stop()
                        $scope.reload()
                    )
            )
        $scope.get_bootdevice_info_class = (obj) ->
            num_bootips = $scope.get_num_bootips(obj)
            if obj.dhcp_error
                return "btn-danger"
            else
                if num_bootips == 0
                    return "btn-warning"
                else if num_bootips == 1
                    return "btn-success"
                else
                    return "btn-danger"
        $scope.get_num_bootips = (obj) ->
            num_bootips = 0
            for net_dev in obj.netdevice_set
                for net_ip in net_dev.net_ip_set
                    if $scope.network_lut[net_ip.network].network_type_identifier == "b"
                        num_bootips++
            return num_bootips
        $scope.get_boot_value = (obj) ->
            num_bootips = $scope.get_num_bootips(obj)
            r_val = "#{num_bootips} IPs (" + (if obj.dhcp_write then "write" else "no write") + " / " + (if obj.dhcp_mac then "greedy" else "not greedy") + ")"
            if obj.dhcp_error
                r_val = "#{r_val}, #{obj.dhcp_error}"
            if obj.dhcp_write != obj.dhcp_written
                r_val = "#{r_val}, DHCP is " + (if obj.dhcp_written then "" else "not") + " written"
            return r_val
        $scope.network_changed = (obj) ->
            if obj.ip == "0.0.0.0" or not obj._changed_by_user_
                $scope.get_free_ip(obj)
            if not obj._changed_by_user_
                _nw = $scope.network_lut[obj.network]
                if _nw.preferred_domain_tree_node
                    obj.domain_tree_node = _nw.preferred_domain_tree_node

        $scope.get_free_ip = (obj) ->
            blockUI.start("requesting free IP...")
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_GET_FREE_IP
                data: {
                    "netip": angular.toJson(obj)
                }
                dataType: "json"
            ).then((json) ->
                blockUI.stop()
                if json["ip"]?
                    obj.ip = json["ip"]
            )
]).directive("icswDeviceNetworkNetdeviceRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.netdevice.row")
        link : (scope, element, attrs) ->
            scope.get_network_type = (ndip_obj) ->
                if ndip_obj.snmp_network_type
                    return scope.snt_lut[ndip_obj.snmp_network_type].if_label
                else
                    return scope.ndt_lut[ndip_obj.network_device_type].info_string
            scope.get_snmp_ao_status = (ndip_obj) ->
                as = ndip_obj.snmp_admin_status
                os = ndip_obj.snmp_oper_status
                if as == 0 and os == 0
                    return ""
                else if as == 1 and os == 1
                    return "up"
                else
                    _r_f = []
                    _r_f.push({1 : "up", 2: "down", 3: "testing"}[as])
                    _r_f.push({1 : "up", 2: "down", 3: "testing", 4: "unknown", 5:"dormant", 6:"notpresent", 7:"lowerLayerDown"}[os])
                    return _r_f.join(", ")
            scope.get_snmp_ao_status_class = (ndip_obj) ->
                as = ndip_obj.snmp_admin_status
                os = ndip_obj.snmp_oper_status
                if as == 0 and os == 0
                    return ""
                else if as == 1 and os == 1
                    return "success text-center"
                else
                    return "warning text-center"
            scope.get_desired_status = (ndip_obj) ->
                return {
                    "i": "ignore"
                    "u": "up"
                    "d" : "down"
                }[ndip_obj.desired_status]
    }
]).directive("icswDeviceComCapabilities", ["$templateCache", "$compile", "icswCachingCall", "ICSW_URLS", ($templateCache, $compile, icswCachingCall, ICSW_URLS) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.com.capabilities")
        scope:
            device: "=device"
            detail: "=detail"
        link: (scope, el, attrs) ->
            console.log scope.device
            scope.com_class = () ->
                if scope.pending
                    return "btn-warning"
                else if scope.com_caps.length
                    return "btn-success"
                else
                    return "btn-danger"
            scope.com_caps = []
            scope.$watch("device.active_scan", (new_val) ->
                if new_val == "base"
                    el.find("span.ladda-label").text("...")
                    scope.pending = true
                else
                    update_com_cap()
            )
            update_com_cap = () ->
                el.find("span.ladda-label").text("...")
                scope.pending = true
                icswCachingCall.fetch(scope.$id, ICSW_URLS.REST_DEVICE_COM_CAPABILITIES, {"devices": "<PKS>"}, [scope.device.idx]).then(
                    (data) ->
                        console.log "***", data
                        scope.com_caps = if data[0]? then data[0] else []
                        scope.pending = false
                        if scope.com_caps.length
                            scope.device.com_caps = (_entry.matchcode for _entry in scope.com_caps)
                            scope.device.com_cap_names = (_entry.name for _entry in scope.com_caps)
                            if scope.detail?
                                el.find("span.ladda-label").text(scope.device.com_cap_names.join(", "))
                            else
                                el.find("span.ladda-label").text(scope.device.com_caps.join(", "))
                        else
                            el.find("span.ladda-label").text("N/A")
                )
            update_com_cap()
    }

]).directive("icswDeviceNetworkIpRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.ip.row")
    }
]).directive("icswDeviceNetworkDeviceRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.device.row")
    }
]).directive("icswDeviceNetworkPeerRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.peer.row")
    }
]).directive("icswDeviceNetworkOverview", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        scope: true
        restrict : "EA"
        link: (scope, el, attrs) ->
            if attrs["showCopyButton"]?
                scope.show_copy_button = true
        template : $templateCache.get("icsw.device.network.overview")
        controller: "icswDeviceNetworkCtrl"
    }
]).directive("icswDeviceNetworkTotal", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.network.total")
    }
]).controller("icswDeviceNetworkClusterCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "icswAcessLevelService", "msgbus", "ICSW_URLS", "icswSimpleAjaxCall",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, icswAcessLevelService, msgbus, ICSW_URLS, icswSimpleAjaxCall) ->
        icswAcessLevelService.install($scope)
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.devices = args[1] 
        )
        $scope.clusters = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devices = _dev_sel
        $scope.reload = () ->
            icswSimpleAjaxCall(
                url      : ICSW_URLS.NETWORK_GET_CLUSTERS
                dataType : "json"
            ).then((json) ->
                $scope.clusters = json
            )
        $scope.is_selected = (cluster) ->
            _sel = _.intersection(cluster.device_pks, $scope.devices)
            return if _sel.length then "yes (#{_sel.length})" else "no"
        $scope.show_cluster = (cluster) ->
            child_scope = $scope.$new()
            child_scope.cluster = cluster
            child_scope.devices = []
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList({"pks" : angular.toJson(cluster.device_pks), "ignore_meta_devices" : true}).then(
                (data) ->
                    child_scope.devices = data
            )
            msg = $compile($templateCache.get("icsw.device.network.cluster.info"))(child_scope)
            child_scope.modal = BootstrapDialog.show
                title: "Devices in cluster (#{child_scope.cluster.device_pks.length})"
                message: msg
                draggable: true
                closable: true
                closeByBackdrop: false
                buttons: [
                    {
                         cssClass: "btn-primary"
                         label: "Close"
                         action: (dialog) ->
                             dialog.close()
                    },
                    ]
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)

        $scope.reload()
]).controller("icswDeviceNetworkGraphCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "icswAcessLevelService", "icswLivestatusFilterFactory",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, icswAcessLevelService, icswLivestatusFilterFactory) ->
        icswAcessLevelService.install($scope)
        $scope.graph_sel = "sel"
        $scope.show_livestatus = false
        $scope.devices = []
        $scope.new_devsel = (_dev_sel) ->
            $scope.devices = _dev_sel
        $scope.ls_filter = new icswLivestatusFilterFactory()
]).directive("icswDeviceNetworkNodeTransform", [() ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.$watch(attrs["icswDeviceNetworkNodeTransform"], (transform_node) ->
                scope.$watch(attrs["redraw"], (new_val) ->
                    if transform_node.x?
                        element.attr("transform", "translate(#{transform_node.x},#{transform_node.y})")
                )
            )
    }
]).directive("icswDeviceNetworkNodeDblClick", ["DeviceOverviewService", (DeviceOverviewService) ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.click_node = null
            scope.double_click = (event) ->
                # beef up node structure
                if scope.click_node?
                    scope.click_node.idx = scope.click_node.id
                    #scope.click_node.device_type_identifier = "D"
                    DeviceOverviewService.NewOverview(event, [scope.click_node])
            scope.$watch(attrs["icswDeviceNetworkNodeDblClick"], (click_node) ->
                scope.click_node = click_node
            )
    }
]).directive("icswDeviceNetworkHostLivestatus", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.network.host.livestatus")
        scope:
             devicepk: "=devicepk"
             ls_filter: "=lsFilter"
        replace: true
    }
]).directive("icswDeviceNetworkHostNode", ["dragging", "$templateCache", (dragging, $templateCache) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope:
            node: "=node"
            redraw: "=redraw"
        template: $templateCache.get("icsw.device.network.host.node")
        link : (scope, element, attrs) ->
            scope.stroke_width = 1
            scope.focus = true
            scope.mousedown = false
            scope.$watch("node", (new_val) ->
                scope.node = new_val
                scope.fill_color = "white"
                scope.stroke_width = Math.max(Math.min(new_val.num_nds, 3), 1)
                scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            scope.mouse_click = () ->
                if scope.node.ignore_click
                    scope.node.ignore_click = false
                else
                    scope.node.fixed = !scope.node.fixed
                    scope.fill_color = if scope.node.fixed then "red" else "white"
            scope.mouse_enter = () ->
                scope.focus = true
                scope.stroke_width++
            scope.mouse_leave = () ->
                scope.focus = false
                scope.mousedown = false
                scope.stroke_width--
    }
]).directive("icswDeviceNetworkHostLink", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope: 
            link: "=link"
            redraw: "=redraw"
        template: $templateCache.get("icsw.device.network.host.link")
        link : (scope, element, attrs) ->
            scope.$watch("link", (new_val) ->
                scope.link = new_val
                #scope.stroke_width = if new_val.num_nds then new_val.num_nds else 1
                #scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            scope.$watch("redraw", () ->
                element.attr("x1", scope.link.x1c)
                element.attr("y1", scope.link.y1c)
                element.attr("x2", scope.link.x2c)
                element.attr("y2", scope.link.y2c)
            )
    }
]).directive("icswDeviceNetworkGraph", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        replace: true
        template: $templateCache.get("icsw.device.network.graph")
        link: (scope, element, attrs) ->
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[1])
                )
            scope.prev_size = {width:100, height:100}
            scope.get_element_dimensions = () ->
                return {"h": element.height(), "w": element.width()}
            scope.size = {
                width: 1200
                height: 800
            }
            scope.zoom = {
                factor: 1.0
            }
            scope.offset = {
                x: 0
                y: 0
            }
            scope.$watch(
                scope.get_element_dimensions
                (new_val) ->
                    scope.prev_size = {width: scope.size.width, height:scope.size.height}
                    #scope.size.width = new_val["w"]
                    #scope.size.height = new_val["h"]
                    #console.log scope.prev_size, scope.size
                true
            )
            element.bind("resize", () ->
                scope.$apply()
            )
    }
]).directive("icswDeviceNetworkGraph2", ["d3_service", "dragging", "svg_tools", "blockUI", "ICSW_URLS", "$templateCache", "icswSimpleAjaxCall", (d3_service, dragging, svg_tools, blockUI, ICSW_URLS, $templateCache, icswSimpleAjaxCall) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        template: $templateCache.get("icsw.device.network.graph2")
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            scope.cur_trans = [0, 0]
            scope.nodes = []
            scope.links = []
            scope.redraw_nodes = 0
            d3_service.d3().then((d3) ->
                scope.svg_el = element[0]
                svg = d3.select(scope.svg_el)
                #svg.attr("height", scope.size.height)
                scope.force = d3.layout.force().charge(-220).gravity(0.02).linkDistance(150).size([scope.size.width, scope.size.height])
                  .linkDistance((d) -> return 100).on("tick", scope.tick)
                scope.fetch_data()
            scope.fetch_data = () ->
                blockUI.start(
                    "loading, please wait..."
                )
                icswSimpleAjaxCall(
                    url      : ICSW_URLS.NETWORK_JSON_NETWORK
                    data     : 
                        "graph_sel" : scope.graph_sel
                    dataType : "json"
                ).then((json) ->
                    blockUI.stop()
                    scope.json_data = json
                    scope.draw_graph()
                )
            )
            scope.draw_graph = () ->
                scope.iter = 0
                scope.force.nodes(scope.json_data.nodes).links(scope.json_data.links)
                scope.node_lut = {}
                scope.nodes = scope.json_data.nodes
                scope.links = scope.json_data.links
                for node in scope.nodes
                    node.fixed = false
                    node.dragging = false
                    node.ignore_click = false
                    scope.node_lut[node.id] = node
                scope.redraw_nodes++
                scope.force.start()
            scope.find_element = (s_target) ->
                if svg_tools.has_class_svg(s_target, "draggable")
                    return s_target
                s_target = s_target.parent()
                if s_target.length
                    return scope.find_element(s_target)
                else
                    return null
            scope.mouse_down = (event) ->
                drag_el = scope.find_element($(event.target))
                if drag_el.length
                    el_scope = angular.element(drag_el[0]).scope()
                else
                    el_scope = null
                if el_scope
                    drag_el_tag = drag_el.prop("tagName")
                    if drag_el_tag == "svg"
                        dragging.start_drag(event, 0, {
                            dragStarted: (x, y, event) ->
                                scope.sx = x - scope.offset.x
                                scope.sy = y - scope.offset.y
                            dragging: (x, y) ->
                                scope.offset = {
                                   x: x - scope.sx
                                   y: y - scope.sy
                                }
                            dragEnded: () ->
                        })
                    else
                        drag_node = el_scope.node
                        scope.redraw_nodes++
                        dragging.start_drag(event, 1, {
                            dragStarted: (x, y, event) ->
                                drag_node.dragging = true
                                drag_node.fixed = true
                                drag_node.ignore_click = true
                                scope.start_drag_point = scope.rescale(
                                    svg_tools.get_abs_coordinate(scope.svg_el, x, y)
                                )
                                scope.force.start()
                            dragging: (x, y) ->
                                cur_point = scope.rescale(
                                    svg_tools.get_abs_coordinate(scope.svg_el, x, y)
                                )
                                drag_node.x = cur_point.x
                                drag_node.y = cur_point.y
                                drag_node.px = cur_point.x
                                drag_node.py = cur_point.y
                                scope.tick()
                            dragEnded: () ->
                                drag_node.dragging = false
                        })
            scope.rescale = (point) ->
                point.x -= scope.offset.x
                point.y -= scope.offset.y
                point.x /= scope.zoom.factor
                point.y /= scope.zoom.factor
                return point
            scope.iter = 0
            scope.mouse_wheel = (event, delta, deltax, deltay) ->
                scale_point = scope.rescale(
                    svg_tools.get_abs_coordinate(scope.svg_el, event.originalEvent.clientX, event.originalEvent.clientY)
                )
                prev_factor = scope.zoom.factor
                if delta > 0
                    scope.zoom.factor *= 1.05
                else
                    scope.zoom.factor /= 1.05
                scope.offset.x += scale_point.x * (prev_factor - scope.zoom.factor)
                scope.offset.y += scale_point.y * (prev_factor - scope.zoom.factor)
                event.stopPropagation()
                event.preventDefault()
            scope.tick = () ->
                scope.iter++
                #console.log "t"
                for node in scope.force.nodes()
                    t_node = scope.node_lut[node.id]
                    #if t_node.fixed
                        #console.log "*", t_node
                    #    t_node.x = node.x
                    #    t_node.y = node.y
                for link in scope.links
                    s_node = scope.node_lut[link.source.id]
                    d_node = scope.node_lut[link.target.id]
                    link.x1c = s_node.x
                    link.y1c = s_node.y
                    link.x2c = d_node.x
                    link.y2c = d_node.y
                scope.$apply(() ->
                    scope.redraw_nodes++
                )
    }
]).service('icswNetworkDeviceTypeService', ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url           : ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST
        delete_confirm_str : (obj) ->
            return "Really delete Network type '#{obj.description}' ?"
        edit_template      : "network.device.type.form"
        new_object: {
                "identifier"  : "eth"
                "description" : "new network device type"
                "name_re"     : "^eth.*$"
                "mac_bytes"   : 6
                "allow_virtual_interfaces" : true
        }
    }
]).service('icswNetworkTypeService', ["ICSW_URLS", (ICSW_URLS) ->
    nw_types_dict = [
        {"value":"b", "name":"boot"}
        {"value":"p", "name":"prod"}
        {"value":"s", "name":"slave"}
        {"value":"o", "name":"other"}
        {"value":"l", "name":"local"}
    ]
    return {
        rest_url            : ICSW_URLS.REST_NETWORK_TYPE_LIST
        edit_template       : "network.type.form"
        modal_title         : "Network Type"
        delete_confirm_str  : (obj) -> return "Really delete Network type '#{obj.description}' ?"
        new_object          : {"identifier" : "p", description : ""}
        object_created      : (new_obj) -> new_obj.description = ""
        network_types       : nw_types_dict  # for create/edit dialog
    }
]).service('icswNetworkService', ["Restangular", "$q", "icswTools", "ICSW_URLS", "icswDomainTreeService", "icswSimpleAjaxCall", "blockUI", (Restangular, $q, icswTools, ICSW_URLS, icswDomainTreeService, icswSimpleAjaxCall, blockUI) ->

    networks_rest = Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    network_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    network_device_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    domain_tree_node_list = []
    domain_tree_node_dict = {}

    network_display = {}
    get_defer = (q_type) ->
        d = $q.defer()
        result = q_type.then(
           (response) ->
               d.resolve(response)
        )
        return d.promise

    hide_network =  () ->
        network_display.active_network = null
        network_display.iplist = []

    long2ip = (long) ->
        a = (long & (0xff << 24)) >>> 24
        b = (long & (0xff << 16)) >>> 16
        c = (long & (0xff << 8)) >>> 8
        d = long & 0xff
        return [a, b, c, d].join('.')

    ip2long = (ip) ->
        b = (ip + '').split('.')
        if b.length is 0 or b.length > 4 then throw new Error('Invalid IP')
        for byte, i in b
            if isNaN parseInt(byte, 10) then throw new Error("Invalid byte: #{byte}")
            if byte < 0 or byte > 255 then throw new Error("Invalid byte: #{byte}")
        return ((b[0] or 0) << 24 | (b[1] or 0) << 16 | (b[2] or 0) << 8 | (b[3] or 0)) >>> 0

    set_domain_tree_node = (data) ->
        domain_tree_node_dict = {}
        for entry in data
            _name = if entry.depth then entry.full_name else "[TLN]"
            entry.info = _name
            domain_tree_node_dict[entry.idx] = entry
        domain_tree_node_list = data

    scan_networks = (scope) ->
        return () ->
            # blockUI
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.NETWORK_RESCAN_NETWORKS
                title   : "scanning for networks"
            ).then(
                (xml) ->
                    blockUI.stop()
                    scope.reload()
                (xml) ->
                    blockUI.stop()
            )
    return {
        rest_handle         : networks_rest
        edit_template       : "network.form"
        modal_title         : "Network definition"
        domain_tree_node_list: () ->
            return domain_tree_node_list
        refresh_domain_tree_node: () ->
            icswDomainTreeService.load("ins").then((data) ->
                set_domain_tree_node(data)
            )
        init_fn             : (scope) ->
            # install salteed scan_networks function
            scope.scan_networks = scan_networks(scope)
        networks            : networks_rest
        network_types       : network_types_rest
        network_device_types: network_device_types_rest
        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"
        new_object          : () ->
            return {
                "identifier"   : "new network",
                "network_type" : (entry["idx"] for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["identifier"] == "o")[0]
                "enforce_unique_ips" : true
                "num_ip"       : 0
                "gw_pri"       : 1
            }
        network_display     : network_display
        show_network        : (obj) ->
            if network_display.active_network == obj
                hide_network()
            else
                network_display.active_network = obj
                q_list = [
                    get_defer(Restangular.all(ICSW_URLS.REST_NET_IP_LIST.slice(1)).getList({"network" : obj.idx, "_order_by" : "ip"}))
                    get_defer(Restangular.all(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).getList({"net_ip__network" : obj.idx}))
                    get_defer(Restangular.all(ICSW_URLS.REST_DEVICE_LIST.slice(1)).getList({"netdevice__net_ip__network" : obj.idx}))
                ]
                $q.all(q_list).then((data) ->
                    iplist = data[0]
                    netdevices = icswTools.build_lut(data[1])
                    devices = icswTools.build_lut(data[2])
                    for entry in iplist
                        nd = netdevices[entry.netdevice]
                        entry.netdevice_name = nd.devname
                        entry.device_full_name = devices[nd.device].full_name
                    network_display.iplist = iplist
                )
        hide_network : hide_network
        after_reload : () ->
            hide_network()
        get_production_networks : () ->
            prod_idx = (entry for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["identifier"] == "p")[0].idx
            return (entry for key, entry of networks_rest when typeof(entry) == "object" and entry and entry.network_type == prod_idx)
        is_slave_network : (nw_type) ->
            if nw_type
                return (entry for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["idx"] == nw_type)[0].identifier == "s"
            else
                return false
        preferred_dtn: (edit_obj) ->
            if edit_obj.preferred_domain_tree_node
                if domain_tree_node_list.length
                    return domain_tree_node_dict[edit_obj.preferred_domain_tree_node].full_name
                else
                    icswDomainTreeService.fetch("ins").then((data) ->
                        set_domain_tree_node(data)
                    )
            else
                return "---"
        autorange_set : (edit_obj) ->
            if edit_obj.start_range == "0.0.0.0" and edit_obj.end_range == "0.0.0.0"
                return false
            else
                return true
        has_master_network : (edit_obj) ->
            return if edit_obj.master_network then true else false

        clear_range : (edit_obj) ->
            edit_obj.start_range = "0.0.0.0"
            edit_obj.end_range = "0.0.0.0"

        enter_range : (edit_obj) ->
            # click on range field
            sr = edit_obj.start_range
            er = edit_obj.end_range
            if (not sr and not er) or (sr == "0.0.0.0" and er == "0.0.0.0")
                sr = ip2long(edit_obj.network) + 1
                er = ip2long(edit_obj.network) + (4294967295 - ip2long(edit_obj.netmask)) - 1
                # range valid, set
                if sr < er
                    edit_obj.start_range = long2ip(sr)
                    edit_obj.end_range = long2ip(er)

        range_check : (edit_obj) ->
            # check the range parameters
            sr = edit_obj.start_range
            er = edit_obj.end_range
            if sr and er
                sr = ip2long(sr)
                er = ip2long(er)
                min = ip2long(edit_obj.network) + 1
                max = ip2long(edit_obj.network) + (4294967295 - ip2long(edit_obj.netmask)) - 1
                # todo, improve checks

        network_or_netmask_blur : (edit_obj) ->
            # calculate broadcast and gateway automatically

            # validation ensures that if it is not undefined, then it is a valid entry
            if edit_obj.network? and edit_obj.netmask?

                ip_long = ip2long(edit_obj.network)
                mask_long = ip2long(edit_obj.netmask)

                base_long = ip_long & mask_long
                bcast_long = (ip_long & mask_long) | (4294967295 - mask_long)

                # only set if there is no previous value
                if ! edit_obj.broadcast?
                    edit_obj.broadcast = long2ip(bcast_long)
                if ! edit_obj.gateway?
                    edit_obj.gateway = long2ip(base_long)
    }
])
