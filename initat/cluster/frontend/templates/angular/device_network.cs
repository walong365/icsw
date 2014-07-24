{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

device_networks_template = """
<h2>
    Network config for {{ devices.length }} devices
</h2>
<table ng-show="devices.length" class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <th>Devname / IP</th>
            <th>Bridge</th>
            <th>MAC / Network</th>
            <th>Devtype / DTN</th>
            <th>routing / alias / enabled</th>
            <th colspan="3">action</th>
        </tr>
    </thead>
    <tbody>
        <tr dnrow ng-repeat-start="obj in devices" class="success"></tr>
        <tr ndiprow ng-repeat-end ng-repeat="ndip_obj in get_ndip_objects(obj)" ng-show="obj.expanded && get_ndip_expanded(ndip_obj)" ng-class="get_ndip_class(ndip_obj)"></tr>
    </tbody>
</table>
"""

dn_row_template = """
<td>
    <button class="btn btn-primary btn-xs" ng-click="toggle_expand(obj)">
        <span ng_class="get_expand_class(obj)">
        {{ get_num_netdevices(obj) }} / {{ get_num_netips(obj) }} / {{ get_num_peers(obj) }}  
        </span>
    </button>
</td>
<th>{{ obj.full_name }}</th>
<th ng_class="get_bootdevice_info_class(obj)">
    {{ get_bootdevice_info(obj) }}
    <input type="button" class="btn btn-xs btn-warning" ng-show="get_num_bootips(obj)" ng-value="get_boot_value(obj)" ng-click="edit_boot_settings(obj, $event)"></input>
</th>
<th>{{ obj.device_group_name }}</th>
<th>{{ obj.comment }}</th>
<th colspan="3">
    <div class="input-group-btn" ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network')">
        <div class="btn-group">
            <button type="button" class="btn btn-success btn-sm dropdown-toggle" data-toggle="dropdown">
                Create new <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="create_netdevice(obj, $event)"><a href="#">Netdevice</a></li>
                <li ng-show="obj.netdevice_set.length && networks.length" ng-click="create_netip(obj, $event)"><a href="#">IP Address</a></li>
                <li ng-show="obj.netdevice_set.length && nd_peers.length" ng-click="create_peer_information(obj, $event)"><a href="#">Peer</a></li>
            </ul>
        </div>
        <div class="btn-group">
            <button type="button" class="btn btn-warning btn-sm dropdown-toggle" data-toggle="dropdown" ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network') && no_objects_defined(obj)">
               scan via <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                 <li ng-click="scan_device_network(obj, $event)"><a href="#">HostMonitor</a></li>
            </ul>
        </div>
    </div>
</th>
"""

nd_row_template = """
<td>
    <button class="btn btn-info btn-xs" ng-disabled="ndip_obj.net_ip_set.length + ndip_obj.peers.length == 0" ng-click="toggle_expand(ndip_obj)">
        <span ng-class="get_expand_class(ndip_obj)">
        {{ ndip_obj.net_ip_set.length }} / {{ ndip_obj.peers.length }} {{ get_netdevice_boot_info(ndip_obj) }}
        </span>
    </button>
    <span ng-show="ndip_obj.enabled">
        {{ get_netdevice_name(ndip_obj) }}
    </span>
    <span ng-show="!ndip_obj.enabled">
        <em>{{ get_netdevice_name(ndip_obj) }}</em>
    </span>
</td>
<td>{{ get_bridge_info(ndip_obj) }}</td>
<td>{{ ndip_obj.macaddr }}</td>
<td>{{ ndip_obj.network_device_type | array_lookup:network_device_types:'info_string':'-' }}</td>
<td>{{ ndip_obj.routing | yesno2 }} ({{ ndip_obj.penalty }}) / {{ ndip_obj.inter_device_routing | yesno2 }} / {{ ndip_obj.enabled | yesno2 }}</td>
<td>
    <input type="button" class="btn btn-xs btn-info" value="info" tooltip-placement="right"
     tooltip-html-unsafe="<div class='text-left'>
        device: {{ ndip_obj.devname }}<br>
        enabled: {{ ndip_obj.enabled | yesno2 }}<br>
        <hr>  
        driver: {{ ndip_obj.driver }}<br>
        driver options: {{ ndip_obj.driver_options }}<br>
        fake MACAddress: {{ ndip_obj.fake_macaddr }}<br>
        force write DHCP: {{ ndip_obj.dhcp_device | yesno2 }}
        <hr>
        Autonegotiation: {{ ethtool_options(ndip_obj, 'a')}}<br>
        Duplex: {{ ethtool_options(ndip_obj, 'd')}}<br>
        Speed: {{ ethtool_options(ndip_obj, 's')}}
        <hr>
        Monitoring: {{ ndip_obj.netdevice_speed | array_lookup:netdevice_speeds:'info_string':'-' }} 
     </div>"></input>
</td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_netdevice(obj, ndip_obj, $event)" ng-show="enable_modal && acl_modify(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_netdevice(ndip_obj, $event)" ng-show="enable_modal && acl_delete(obj, 'backbone.device.change_network')"></input>
</td>
"""

ip_row_template = """
<td>{{ ndip_obj.ip }}</td>
<td></td>
<td>{{ ndip_obj.network | array_lookup:networks:'info_string':'-' }}</td>
<td>{{ ndip_obj.domain_tree_node | array_lookup:domain_tree_node:'tree_info':'-' }}</td>
<td><span ng-show="ndip_obj.alias">{{ ndip_obj.alias }} ({{ ndip_obj.alias_excl | yesno1 }})</span></td>
<td></td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_netip(ndip_obj, $event)" ng-show="enable_modal && acl_modify(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_netip(ndip_obj, $event)" ng-show="enable_modal && acl_delete(obj, 'backbone.device.change_network')"></input>
<td>
"""

peer_row_template = """
<td></td>
<td colspan="4">
    with cost {{ ndip_obj.peer.penalty }}
    &nbsp;<span class="label label-primary">{{ get_peer_cost(ndip_obj) }}</span>&nbsp;
    to {{ get_peer_target(ndip_obj) }}
</td>
<td></td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_peer_information(ndip_obj, $event)" ng-show="enable_modal && acl_modify(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_peer_information(ndip_obj, $event)" ng-show="enable_modal && acl_delete(obj, 'backbone.device.change_network')"></input>
</td>
"""

{% endverbatim %}

device_network_module = angular.module("icsw.network.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "icsw.d3"])

angular_module_setup([device_network_module])

device_network_module.controller("network_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.enable_modal = true
        # mixins
        $scope.netdevice_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.netdevice_edit.create_template = "netdevice_form.html"
        $scope.netdevice_edit.edit_template = "netdevice_form.html"
        $scope.netdevice_edit.create_rest_url = Restangular.all("{% url 'rest:netdevice_list'%}".slice(1))
        $scope.netdevice_edit.modify_rest_url = "{% url 'rest:netdevice_detail' 1 %}".slice(1).slice(0, -2)
        $scope.netdevice_edit.new_object_at_tail = false
        $scope.netdevice_edit.use_promise = true

        $scope.netip_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.netip_edit.create_template = "net_ip_form.html"
        $scope.netip_edit.edit_template = "net_ip_form.html"
        $scope.netip_edit.create_rest_url = Restangular.all("{% url 'rest:net_ip_list'%}".slice(1))
        $scope.netip_edit.modify_rest_url = "{% url 'rest:net_ip_detail' 1 %}".slice(1).slice(0, -2)
        $scope.netip_edit.new_object_at_tail = false
        $scope.netip_edit.use_promise = true

        $scope.peer_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.peer_edit.create_template = "peer_information_d_form.html"
        #$scope.peer_edit.edit_template = "netip_template.html"
        $scope.peer_edit.create_rest_url = Restangular.all("{% url 'rest:peer_information_list'%}".slice(1))
        $scope.peer_edit.modify_rest_url = "{% url 'rest:peer_information_detail' 1 %}".slice(1).slice(0, -2)
        $scope.peer_edit.new_object_at_tail = false
        $scope.peer_edit.use_promise = true

        $scope.boot_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.boot_edit.edit_template = "device_boot_form.html"
        $scope.boot_edit.put_parameters = {"only_boot" : true}
        $scope.boot_edit.modify_rest_url = "{% url 'rest:device_tree_detail' 1 %}".slice(1).slice(0, -2)
        $scope.boot_edit.new_object_at_tail = false
        $scope.boot_edit.use_promise = true

        $scope.scan_mixin = new angular_modal_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.scan_mixin.template = "device_network_scan_form.html"
        
        $scope.devsel_list = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload= () ->
            wait_list = [
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_network" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_network"}]),
                restDataSource.reload(["{% url 'rest:peer_information_list' %}", {}]),
                # 2
                restDataSource.reload(["{% url 'rest:netdevice_speed_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:network_device_type_list' %}", {}])
                # 4
                restDataSource.reload(["{% url 'rest:network_list' %}", {}])
                restDataSource.reload(["{% url 'rest:domain_tree_node_list' %}", {}])
                # 6
                restDataSource.reload(["{% url 'rest:netdevice_peer_list' %}", {}])
                restDataSource.reload(["{% url 'rest:fetch_forms' %}", {
                    "forms" : angular.toJson([
                        "netdevice_form"
                        "net_ip_form"
                        "peer_information_s_form"
                        "peer_information_d_form"
                        "device_network_scan_form"
                        "device_boot_form"
                     ])
                }]),
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = (dev for dev in data[0])
                for dev in $scope.devices
                    dev.expanded = true
                    for nd in dev.netdevice_set
                        nd.expanded = false
                $scope.peers = data[1]
                $scope.netdevice_speeds = data[2]
                $scope.network_device_types = data[3]
                $scope.networks = data[4]
                $scope.network_lut = build_lut($scope.networks)
                $scope.domain_tree_node = data[5]
                $scope.dtn_lut = build_lut($scope.domain_tree_node)
                $scope.nd_peers = data[6]
                $scope.build_luts()
                for cur_form in data[7] 
                    $templateCache.put(cur_form.name, cur_form.form)
            )
        $scope.build_luts = () ->
            $scope.dev_lut = {}
            $scope.nd_lut = {}
            $scope.ip_lut = {}
            for dev in $scope.devices
                $scope.dev_lut[dev.idx] = dev
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
        $scope.get_bridge_info = (nd) ->
            dev = $scope.dev_lut[nd.device]
            if nd.is_bridge
                slaves = (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx)
                if slaves.length
                    return "yes" + " (" + slaves.join(", ") + ")"
                else
                    return "yes"
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
        $scope.get_expand_class = (dev) ->
            if dev.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.toggle_expand = (dev) ->
            dev.expanded = !dev.expanded
        $scope.get_num_netdevices = (dev) ->
            return dev.netdevice_set.length
        $scope.no_objects_defined = (dev) ->
            return if (dev.netdevice_set.length == 0) then true else false
        $scope.get_num_netips = (dev) ->
            num_ip = 0
            for nd in dev.netdevice_set
                num_ip += nd.net_ip_set.length
            return num_ip
        $scope.get_num_peers = (dev) ->
            num_peers = 0
            for nd in dev.netdevice_set
                num_peers += nd.peers.length
            return num_peers
        $scope.get_route_peers =() ->
            return (entry for entry in $scope.nd_peers when entry.routing)
        $scope.get_ndip_objects = (dev) ->
            r_list = []
            for ndev in dev.netdevice_set
                r_list.push(ndev)
                r_list = r_list.concat(ndev.net_ip_set)
                r_list = r_list.concat(ndev.peers)
            return r_list
        $scope.scan_device_network = (dev, event) ->
            dev.scan_address = dev.full_name
            dev.strict_mode = true
            $scope.scan_device = dev
            $scope.scan_mixin.edit(dev, event).then(
                (mod_obj) ->
                    true #console.log "*", mod_obj
            )
        $scope.fetch_device_network = () ->
            $.blockUI()
            call_ajax
                url     : "{% url 'device:scan_device_network' %}"
                data    : {
                    "info" : angular.toJson({
                        "pk" : $scope.scan_device.idx
                        "scan_address" : $scope.scan_device.scan_address
                        "strict_mode" : $scope.scan_device.strict_mode
                    }) 
                }
                success : (xml) ->
                    parse_xml_response(xml)
                    
                    Restangular.all("{% url 'rest:device_tree_list' %}".slice(1)).getList({"with_network" : true, "pks" : angular.toJson([$scope.scan_device.idx]), "olp" : "backbone.device.change_network"}).then(
                        (data) ->
                            new_dev = data[0]
                            new_dev.expanded = true
                            cur_devs = []
                            for dev in $scope.devices
                                if dev.idx == new_dev.idx
                                    cur_devs.push(new_dev)
                                else
                                    cur_devs.push(dev)
                            $scope.devices = cur_devs
                            $scope.build_luts()
                            $.unblockUI()
                    )
        $scope.create_netdevice = (dev, event) ->
            $scope._current_dev = dev
            $scope.netdevice_edit.create_list = dev.netdevice_set
            $scope.netdevice_edit.new_object = (scope) ->
                _dev = {
                    "device" : dev.idx
                    "devname" : "eth0"
                    "enabled" : true
                    "netdevice_speed" : (entry.idx for entry in $scope.netdevice_speeds when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
                    "penalty" : 1
                    "net_ip_set" : []
                    "ethtool_options" : 0
                    "ethtool_autoneg" : 0
                    "ethtool_speed" : 0
                    "ethtool_duplex" : 0
                    # dummy value
                    "network_device_type" : $scope.network_device_types[0].idx
                } 
                $scope.set_edit_flags(_dev)
                return _dev
            $scope.netdevice_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        new_obj.net_ip_set = []
                        new_obj.expanded = false
                        new_obj.peers = []
                        $scope.nd_lut[new_obj.idx] = new_obj
                        $scope.check_for_peer_change(new_obj)
            )
        $scope.edit_netdevice = (dev, ndev, event) ->
            $scope._current_dev = dev
            $scope.set_edit_flags(ndev)
            $scope.netdevice_edit.edit(ndev, event).then(
                (mod_ndev) ->
                    if mod_ndev != false
                        $scope.check_for_peer_change(mod_ndev)
            )
        $scope.edit_boot_settings = (dev, event) ->
            $scope._current_dev = dev
            $scope.boot_edit.edit(dev, event).then(
                (mod_dev) ->
                    true
            )
        $scope.set_edit_flags = (dev) ->
            dev.show_mac = true
            dev.show_hardware = true
            dev.show_ethtool = true
            dev.show_vlan = true
        $scope.check_for_peer_change = (ndev) ->
            # at first remove from list
            $scope.nd_peers = (entry for entry in $scope.nd_peers when entry.idx != ndev.idx)
            if ndev.routing
                ndev.fqdn = $scope._current_dev.full_name
                ndev.device_name = $scope._current_dev.name
                ndev.device_group_name = $scope._current_dev.device_group_name
                $scope.nd_peers.push(ndev)
            $scope.build_luts()
        $scope.get_vlan_masters = (cur_nd) ->
            return (entry for entry in $scope._current_dev.netdevice_set when entry.idx != cur_nd.idx and not entry.is_bridge)
        $scope.get_bridge_masters = (cur_nd) ->
            return (entry for entry in $scope._current_dev.netdevice_set when entry.idx != cur_nd.idx and entry.is_bridge)
        $scope.create_netip = (dev, event) ->
            $scope._current_dev = dev
            $scope.netip_edit.create_list = undefined
            $scope.netip_edit.new_object = (scope) ->
                return {
                    "netdevice" : (entry.idx for entry in dev.netdevice_set)[0]
                    "ip" : "0.0.0.0"
                    "network" : $scope.networks[0].idx
                    "domain_tree_node" : $scope.domain_tree_node[0].idx
                } 
            $scope.netip_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        # console.log "***", new_obj
                        $scope.nd_lut[new_obj.netdevice].net_ip_set.push(new_obj)
                        $scope.ip_lut[new_obj.idx] = new_obj
            )
        $scope.edit_netip = (ip, event) ->
            $scope.netip_edit.edit(ip, event).then(
                (mod_ip) ->
                    if mod_ip != false
                        true
                        #console.log "modip"
            )
        $scope.get_peer_src_info = () ->
            #console.log $scope._edit_obj
            src_nd = $scope.nd_lut[$scope._edit_obj.s_netdevice]
            if src_nd
                return src_nd.devname + " on " + $scope.dev_lut[src_nd.device].name
            else
                return "???"
        $scope.edit_peer_information = (peer, event) ->
            if peer.peer.s_netdevice == peer.netdevice
                $scope.peer_edit.edit_template = "peer_information_d_form.html"
            else
                $scope.peer_edit.edit_template = "peer_information_s_form.html"
            #$scope._src_nd = $scope.nd_lut[peer.netdevice]
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
        $scope.create_peer_information = (dev, event) ->
            $scope._current_dev = dev
            $scope.peer_edit.create_list = undefined#dev.netdevice_set
            $scope.peer_edit.new_object = (scope) ->
                return {
                    "s_netdevice" : (entry.idx for entry in dev.netdevice_set)[0]
                    "penalty" : 1
                } 
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
                        # console.log "deldip"
            )
        $scope.delete_netdevice = (nd, event) ->
            # find device / netdevice
            $scope.netdevice_edit.delete_list = $scope.dev_lut[nd.device].netdevice_set
            $scope.netdevice_edit.delete_obj(nd).then(
                (res) ->
                    if res
                        true
                        #console.log "delnd"
            )
        $scope.get_ndip_class = (ndip_obj) ->
            if ndip_obj.device
                return "warning"
            else
                return ""
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
        $scope.get_ndip_expanded = (ndip_obj) ->
            if ndip_obj.device
                return true
            else if ndip_obj.netdevice
                return $scope.nd_lut[ndip_obj.netdevice].expanded
            else
                return $scope.nd_lut[ndip_obj.netdevice].expanded
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
        $scope.copy_network = (src_obj, event) ->
            if confirm("Overwrite all networks with the one from #{src_obj.full_name} ?")
                $.blockUI()
                call_ajax
                    url     : "{% url 'network:copy_network' %}"
                    data    : {
                        "source_dev" : src_obj.idx
                        "all_devs"   : angular.toJson(@devsel_list)
                    },
                    success : (xml) =>
                        $.unblockUI()
                        parse_xml_response(xml)
                        $scope.reload()
        $scope.get_bootdevice_info = (obj) ->
            num_bootips = $scope.get_num_bootips(obj)
            if num_bootips == 0
                return "---"
            else if num_bootips == 1
                return "1 boot-IP"
            else
                return "#{num_bootips} boot-IPs"
        $scope.get_bootdevice_info_class = (obj) ->
            num_bootips = $scope.get_num_bootips(obj)
            if num_bootips == 0
                return ""
            else if num_bootips == 1
                return "success"
            else
                return "danger"
        $scope.get_num_bootips = (obj) ->
            num_bootips = 0
            for net_dev in obj.netdevice_set
                for net_ip in net_dev.net_ip_set
                    #console.log net_ip.ip, $scope.network_lut[net_ip.network].network_type_identifier
                    if $scope.network_lut[net_ip.network].network_type_identifier == "b"
                        num_bootips++
            return num_bootips
        $scope.get_boot_value = (obj) ->
            return "boot (" + (if obj.dhcp_write then "write" else "no write") + " / " + (if obj.dhcp_mac then "greedy" else "not greedy") + ")"
        install_devsel_link($scope.new_devsel, false)
]).directive("devicenetworks", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devicenetworks.html")
        link : (scope, el, attrs) ->
            if attrs["disablemodal"]?
                scope.enable_modal = if parseInt(attrs["disablemodal"]) then false else true
            if attrs["devicepk"]?
                scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).directive("dnrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devicenetrow.html")
    }
).directive("ndiprow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            if scope.ndip_obj.device
                new_el = $compile($templateCache.get("netdevicerow.html"))
            else if scope.ndip_obj.peer
                new_el = $compile($templateCache.get("peerrow.html"))
            else
                new_el = $compile($templateCache.get("netiprow.html"))
            element.append(new_el(scope))        
    }
).directive("iprow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("netiprow.html")
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("devicenetworks.html", device_networks_template)
    $templateCache.put("devicenetrow.html", dn_row_template)
    $templateCache.put("netdevicerow.html", nd_row_template)
    $templateCache.put("netiprow.html", ip_row_template)
    $templateCache.put("peerrow.html", peer_row_template)
)

device_network_module.controller("graph_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.graph_mode = "m"
        $scope.graph_sel = "none"
]).directive("networkgraph", ["d3_service", (d3_service) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            scope.cur_trans = [0, 0]
            d3_service.d3().then((d3) ->
                width = d3.select(element[0]).node().offsetWidth
                width = 1000
                height = 800
                svg = d3.select(element[0])
                    .append("svg:svg")
                    .style('width', '100%')
                    .attr(
                        "width" : width
                        "height" : height
                        "viewBox" : "0 0 #{width} #{height}"
                        "pointer-events"      : "all"
                        "preserveAspectRatio" : "xMidYMid"
                    )
                scope.svg = svg
                scope.vis = d3.select(element[0])
                svg.attr("height", height)
                #console.log svg
                scope.vis = svg.append("svg:g")
                    .call(d3.behavior.zoom().on("zoom", scope.rescale))
                    .on("dblclick.zoom", null)
                .append("svg:g")
                    .on("mousemove", scope.mousemove)
                    .on("mousedown", scope.mousedown)
                    .on("mouseup", scope.mouseup)
                scope.vis.append("rect").attr(
                    "x"      : -width,
                    "y"      : -height,
                    "width"  : 3 * width,
                    "height" : 3 * height,
                    "fill"   : "white",
                )
                scope.nodes = []
                scope.links = []
                scope.force = d3.layout.force().charge(-220).gravity(0.02).linkDistance(150).size([width, height])
                  .linkDistance((d) -> return 100).on("tick", scope.tick)
                scope.drag_node = scope.force.drag()
                    .on("dragstart", (d) ->
                        scope.start_coords = [d.x, d.y]
                        d.fixed = true
                        if scope.selected == d
                            # deselect
                            scope.selected = undefined
                            #$("span#selected_node").text("")
                            d3.select(this).select("circle").classed("fixed", true)
                        else
                            # select
                            scope.selected = d
                            #$("span#selected_node").text(_this.selected.name)
                            fixed = true
                            d.fixed = fixed
                            d3.select(@).select("circle").classed("fixed", fixed)
                    )
                    .on("dragend", (d) ->
                        if d.x != scope.start_coords[0] or d.y != scope.start_coords[1]
                            # node was moved, set fixed
                            fixed = true
                        else
                            if scope.selected
                                # a node is selected, set fixed flag
                                fixed = true
                            else
                                # no node is selected, clear fixed flag
                                fixed = false
                        d.fixed = fixed
                        d3.select(this).select("circle").classed("fixed", d.fixed)
                    )
                scope.selected = undefined
                scope.connect_line = scope.vis.append("line").attr
                    "class" : "connect_line"
                    "x1"    : 0
                    "y1"    : 0
                    "x2"    : 0
                    "y2"    : 0
                scope.fetch_data()
            scope.fetch_data = () ->
                $.blockUI(
                    message : "loading, please wait..."
                )
                call_ajax
                    url      : "{% url 'network:json_network' %}"
                    data     : 
                        "graph_mode" : scope.graph_sel
                    dataType : "json"
                    success  : (json) =>
                        $.unblockUI()
                        scope.json_data = json
                        scope.vis.selectAll(".node").remove()
                        scope.vis.selectAll(".link").remove()
                        scope.draw_graph()
            )
            scope.rescale = () ->
                scope.cur_scale = d3.event.scale
                scope.cur_trans = d3.event.translate
                scope.vis.attr("transform",
                    "translate(" + scope.cur_trans + ")" + " scale(" + scope.cur_scale + ")"
                )
            scope.draw_graph = () ->
                scope.force.nodes(scope.json_data.nodes).links(scope.json_data.links)
                scope.svg_nodes = scope.vis.selectAll(".node").data(scope.json_data.nodes)
                scope.svg_links = scope.vis.selectAll(".link").data(scope.json_data.links)
                scope.svg_links.enter().append("line")
                    .attr
                        "class" : "link"
                    .style
                        "stroke" : (d) ->
                            if d.num_connections == 1
                                return "#7788ff"
                            else
                                return "#2222ff"
                        "stroke-opacity" : "1"
                        "stroke-width"   : (d) ->
                            if d.min_penalty == 1
                                return 3
                            else
                                return 1
                scope.svg_links.exit().remove()
                centers = scope.svg_nodes.enter()
                    .append("g").call(scope.drag_node)
                    .attr
                        "class"   : "node"
                        "node_id" : (n) -> return n.id
                    .on("mouseenter", (d) ->
                        scope.svg.call(d3.behavior.zoom().on("zoom", null))
                        d3.select(this).select("circle").attr("stroke-width", d.num_nds + 3)
                    )
                    .on("mouseleave", (d) ->
                        scope.svg.call(d3.behavior.zoom().scale(scope.cur_scale).translate(scope.cur_trans).on("zoom", scope.rescale))
                        d3.select(this).select("circle").attr("stroke-width", d.num_nds)
                    )
                    .on("mousedown", (d) ->
                        if scope.graph_mode == "c"
                            scope.mousedown_node = d
                            cur_c = d3.select(this).select("circle")
                            #cur_c.attr("stroke-width", 3)#parseInt(cur_c.attr("stroke-width")) + 3)
                            scope.connect_line.attr
                                "class" : "connect_line"
                                "x1" : d.x
                                "y1" : d.y
                                "x2" : d.x
                                "y2" : d.y
                    )
                    .on("mouseup", (d) ->
                        if scope.mousedown_node
                            scope.mouseup_node = d
                            if scope.mouseup_node == scope.mousedown_node
                                scope.reset_connection_parameters()
                            else
                                #console.log "nl"
                                link = {
                                    source : scope.mousedown_node
                                    target : scope.mouseup_node
                                    min_penalty : 1
                                    num_connections : 1
                                }
                                line_idx = scope.json_data.links.push(link)
                                scope.draw_graph()
                                scope.reset_connection_parameters()
                                cur_el = scope.vis.selectAll("line")[0][line_idx]
                                # insert before first g element
                                cur_el.parentNode.insertBefore(cur_el, cur_el.parentNode.firstChild.nextSibling.nextSibling)
                    )
                    .on("dblclick", (d) ->
                        cur_ev = d3.event
                        cur_di = new device_info(cur_ev, d.id)
                        cur_di.show()
                    )
                centers.append("circle")
                    .attr
                        "r"       : (n) -> return 18
                        "fill"    : "white"
                        "stroke-width" : (n) -> return n.num_nds
                        "stroke"  : "grey"
                        "cursor"  : "crosshair"
                centers.append("text")
                    .attr
                        "text-anchor" : "middle"
                        "cursor"      : "crosshair"
                    .text((d) -> return d.name)
                scope.force.start()
            scope.reset_connection_parameters = () =>
                scope.mousedown_node = undefined
                scope.mouseup_node   = undefined
                scope.connect_line.attr
                    "class" : "connect_line_hidden"
                    "x1"    : 0
                    "y1"    : 0
                    "x2"    : 0
                    "y2"    : 0
            scope.mousemove = (a) ->
                if scope.mousedown_node
                    scope.connect_line.attr
                        "x1" : scope.mousedown_node.x
                        "y1" : scope.mousedown_node.y
                        "x2" : d3.mouse(scope.vis[0][0])[0]
                        "y2" : d3.mouse(scope.vis[0][0])[1]
                #console.log "mm", d3.mouse(scope.svg[0][0])
            scope.tick = () ->
                scope.svg_links.attr
                    "x1" : (d) -> return d.source.x
                    "y1" : (d) -> return d.source.y
                    "x2" : (d) -> return d.target.x
                    "y2" : (d) -> return d.target.y
                scope.svg_nodes.attr
                    "transform" : (d) -> 
                        return "translate(#{d.x},#{d.y})"
            scope.$watch("graph_mode", (new_val) ->
                if scope.svg_nodes
                    if new_val == "c"
                        scope.svg_nodes.call(scope.drag_node).on("mousedown.drag", null)
                    else
                        scope.svg_nodes.call(scope.drag_node)
                #console.log "ngm", new_val
            )
    }
])

{% endinlinecoffeescript %}

</script>

