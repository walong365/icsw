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
).controller("icswDeviceNetworkCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource",
     "$q", "$modal", "access_level_service", "$rootScope", "$timeout", "blockUI", "icswTools", "icswToolsButtonConfigService", "ICSW_URLS",
    "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource,
     $q, $modal, access_level_service, $rootScope, $timeout, blockUI, icswTools, icswToolsButtonConfigService, ICSW_URLS,
     icswCallAjaxService, icswParseXMLResponseService
    ) ->
        $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
        access_level_service.install($scope)
        # copy flags
        $scope.show_copy_button = false
        # accordion flags
        $scope.device_open = true
        $scope.netdevice_open = true
        $scope.netip_open = false
        $scope.peer_open = false
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

        $scope.devsel_list = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload= () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_network" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_network"}]),
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
        $scope.has_bridge_slaves = (nd) ->
            dev = $scope.dev_lut[nd.device]
            if nd.is_bridge
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx).length then true else false
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
                ip_dict[key] = _.sortBy(value)
            network_type_names = _.sortBy(network_type_names)
            dev.ip_dict = ip_dict
            dev.network_type_names = network_type_names
            dev.manual_address = ""
            dev.snmp_community = "public"
            if not dev.com_caps?
                # init com_caps array if not already set
                dev.com_caps = []
            dev.snmp_version = 1
            dev.remove_not_found = false
            dev.strict_mode = true
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
            icswCallAjaxService
                url     : ICSW_URLS.DEVICE_SCAN_DEVICE_NETWORK
                data    :
                    "dev" : angular.toJson($scope.scan_device)
                success : (xml) ->
                    icswParseXMLResponseService(xml)
                    blockUI.stop()
                    $scope.scan_mixin.close_modal()
                    $scope.update_scans()
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
            $scope.netdevice_edit.new_object = (scope) ->
                _dev = {
                    "device" : obj.idx
                    "devname" : "eth0"
                    "enabled" : true
                    "netdevice_speed" : (entry.idx for entry in $scope.netdevice_speeds when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
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
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and not entry.is_bridge)
        $scope.get_bridge_masters = (cur_nd) ->
            _cd = $scope.dev_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bridge)
        $scope.create_netip_dev = (obj, event) ->
            $scope._current_dev = obj
            $scope.netip_edit.create_list = undefined
            $scope.netip_edit.new_object = (scope) ->
                return {
                    "netdevice" : (entry.idx for entry in obj.netdevice_set)[0]
                    "ip" : "0.0.0.0"
                    "network" : $scope.networks[0].idx
                    "domain_tree_node" : obj.domain_tree_node #$scope.domain_tree_node[0].idx
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
            $scope.netip_edit.new_object = (scope) ->
                return {
                    "netdevice" : obj.idx
                    "ip" : "0.0.0.0"
                    "network" : $scope.networks[0].idx
                    "domain_tree_node" : $scope.domain_tree_node[0].idx
                } 
            $scope.netip_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.nd_lut[new_obj.netdevice].net_ip_set.push(new_obj)
                        $scope.ip_lut[new_obj.idx] = new_obj
            )
        $scope.edit_netip = (ip, event) ->
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
        $scope.copy_network = (src_obj, event) ->
            if confirm("Overwrite all networks with the one from #{src_obj.full_name} ?")
                blockUI.start()
                icswCallAjaxService
                    url     : ICSW_URLS.NETWORK_COPY_NETWORK
                    data    : {
                        "source_dev" : src_obj.idx
                        "all_devs"   : angular.toJson(@devsel_list)
                    },
                    success : (xml) =>
                        blockUI.stop()
                        icswParseXMLResponseService(xml)
                        $scope.reload()
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
    }
]).directive("icswDeviceComCapabilities", ["$templateCache", "$compile", "icswCachingCall", "ICSW_URLS", ($templateCache, $compile, icswCachingCall, ICSW_URLS) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.com.capabilities")
        scope:
            device: "=device"
            detail: "=detail"
        link: (scope, el, attrs) ->
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
                icswCachingCall.fetch(scope.$id, ICSW_URLS.REST_DEVICE_COM_CAPABILITIES, {"devices": "<PKS>"}, [scope.device.idx]).then((data) ->
                    scope.com_caps = data[0]
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
]).controller("icswDeviceNetworkClusterCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "access_level_service", "msgbus", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service, msgbus, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
        access_level_service.install($scope)
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.devices = args[1] 
        )
        $scope.clusters = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devices = _dev_sel
        $scope.reload = () ->
            icswCallAjaxService
                url      : ICSW_URLS.NETWORK_GET_CLUSTERS
                dataType : "json"
                success  : (json) =>
                    $scope.$apply(
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
]).controller("icswDeviceNetworkGraphCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "access_level_service", "icswLivestatusFilterFactory",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service, icswLivestatusFilterFactory) ->
        access_level_service.install($scope)
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
]).directive("icswDeviceNetworkGraph2", ["d3_service", "dragging", "svg_tools", "blockUI", "ICSW_URLS", "$templateCache", "icswCallAjaxService", "icswParseXMLResponseService", (d3_service, dragging, svg_tools, blockUI, ICSW_URLS, $templateCache, icswCallAjaxService, icswParseXMLResponseService) ->
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
                icswCallAjaxService
                    url      : ICSW_URLS.NETWORK_JSON_NETWORK
                    data     : 
                        "graph_sel" : scope.graph_sel
                    dataType : "json"
                    success  : (json) =>
                        blockUI.stop()
                        scope.json_data = json
                        scope.draw_graph()
            )
            scope.draw_graph = () ->
                scope.iter = 0
                scope.force.nodes(scope.json_data.nodes).links(scope.json_data.links)
                scope.$apply(() ->
                    scope.node_lut = {}
                    scope.nodes = scope.json_data.nodes
                    scope.links = scope.json_data.links
                    for node in scope.nodes
                        node.fixed = false
                        node.dragging = false
                        node.ignore_click = false
                        scope.node_lut[node.id] = node
                    scope.redraw_nodes++
                )
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
])
