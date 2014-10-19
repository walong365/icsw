{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

device_networks_template = """
<h3>
    Network config for {{ devices.length }} devices ({{ get_nd_objects().length }} netdevices, {{ get_ip_objects().length }} IPs, {{ get_peer_objects().length }} peers)
</h3>
<table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <th>Device</th>
            <th>bootinfo</th>
            <th>#Ports</th>
            <th>#IPs</th>
            <th>#peers</th>
        </tr>
    </thead>
    <tbody>
        <tr devrow ng-repeat="ndip_obj in devices"></tr>
    </tbody>
</table>

<table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <th>Device</th>
            <th>Port</th>
            <th>#IPs</th>
            <th>#peers</th>
            <th>Bridge</th>
            <th>MAC</th>
            <th>Devtype</th>
            <th>MTU</th>
            <th>speed</th>
            <th>penalty</th>
            <th>flags</th>
            <th colspan="4">action</th>
        </tr>
    </thead>
    <tbody>
        <tr netdevicerow ng-repeat="ndip_obj in get_nd_objects()"></tr>
    </tbody>
</table>

<table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <th>Device</th>
            <th>Port</th>
            <th>IP</th>
            <th>Network</th>
            <th>DTN</th>
            <th>alias</th>
            <th colspan="2">action</th>
        </tr>
    </thead>
    <tbody>
        <tr netiprow ng-repeat="ndip_obj in get_ip_objects()"></tr>
    </tbody>
</table>

<table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <th>Device</th>
            <th>Port</th>
            <th>cost</th>
            <th>Dest</th>
            <th>type</th>
            <th colspan="2">action</th>
        </tr>
    </thead>
    <tbody>
        <tr netpeerrow ng-repeat="ndip_obj in get_peer_objects()"></tr>
    </tbody>
</table>
"""

dev_row_template = """
<td>
    {{ ndip_obj.full_name }}
    <button type="button" class="btn btn-xs btn-success pull-right"
        tooltip-placement="bottom"
        tooltip-html-unsafe="<div class='text-left'>
        devicegroup: {{ ndip_obj.device_group_name }}<br>
        comment: {{ ndip_obj.comment }}<br>
        </div>
        ">
        <span class="glyphicon glyphicon-info-sign"></span>
    </button>
</td>
<td>
    <input type="button" class="btn btn-xs btn-warning" ng-class="get_bootdevice_info_class(ndip_obj)" ng-show="get_num_bootips(ndip_obj)" ng-value="get_boot_value(ndip_obj)" ng-click="edit_boot_settings(ndip_obj, $event)"></input>
</td>
<td>
    {{ get_num_netdevices(ndip_obj) }}
</td>
<td>
    {{ get_num_netips_dev(ndip_obj) }}
</td>
<td>
    {{ get_num_peers_dev(ndip_obj) }}
</td>
<th colspan="3">
    <div class="input-group-btn" ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network')">
        <div class="btn-group btn-xs">
            <button type="button" class="btn btn-success btn-xs dropdown-toggle" data-toggle="dropdown">
                Create new <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="create_netdevice(ndip_obj, $event)"><a href="#">Netdevice</a></li>
                <li ng-show="ndip_obj.netdevice_set.length && networks.length" ng-click="create_netip_dev(ndip_obj, $event)"><a href="#">IP Address</a></li>
                <li ng-show="ndip_obj.netdevice_set.length && nd_peers.length" ng-click="create_peer_information_dev(ndip_obj, $event)"><a href="#">Peer</a></li>
            </ul>
        </div>
        <div class="btn-group">
            <button type="button" class="btn btn-warning btn-xs dropdown-toggle" data-toggle="dropdown" ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network') && no_objects_defined(ndip_obj)">
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
    {{ dev_lut[ndip_obj.device].full_name }}
</td>
<td>
    <span ng-show="ndip_obj.enabled">
        {{ get_netdevice_name(ndip_obj) }}
    </span>
    <span ng-show="!ndip_obj.enabled">
        <em><strike>{{ get_netdevice_name(ndip_obj) }}</strike></em>
    </span>
</td>
<td>
    {{ get_num_netips_nd(ndip_obj) }}
</td>
<td>
    {{ get_num_peers_nd(ndip_obj) }}
</td>
<td>{{ get_bridge_info(ndip_obj) }}</td>
<td>{{ ndip_obj.macaddr }}</td>
<td>{{ ndip_obj.network_device_type | array_lookup:network_device_types:'info_string':'-' }}</td>
<td class="text-right">{{ ndip_obj.mtu }}</td>
<td>{{ ndip_obj.netdevice_speed | array_lookup:netdevice_speeds:'info_string':'-' }}</td>
<td class="text-right">{{ ndip_obj.penalty }}</td>
<td>{{ get_flags(ndip_obj) }}</td>
<td>
    <button type="button" class="btn btn-xs btn-success"
     tooltip-placement="right"
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
     </div>">
     <span class="glyphicon glyphicon-info-sign"></span>
     </button>
</td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_netdevice(ndip_obj, $event)" ng-show="enable_modal && acl_modify(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_netdevice(ndip_obj, $event)" ng-show="enable_modal && acl_delete(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <div class="btn-group btn-xs" ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network')">
        <button type="button" class="btn btn-success btn-xs dropdown-toggle" data-toggle="dropdown">
            Create new <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-click="create_netip_nd(ndip_obj, $event)"><a href="#">IP Address</a></li>
            <li ng-click="create_peer_information_nd(ndip_obj, $event)"><a href="#">Peer</a></li>
        </ul>
    </div>
</td>
"""

ip_row_template = """
<td>{{ dev_lut[nd_lut[ndip_obj.netdevice].device].full_name }}</td>
<td>{{ nd_lut[ndip_obj.netdevice].devname }}</td>
<td>{{ ndip_obj.ip }}</td>
<td>{{ ndip_obj.network | array_lookup:networks:'info_string':'-' }}</td>
<td>{{ ndip_obj.domain_tree_node | array_lookup:domain_tree_node:'tree_info':'-' }}</td>
<td><span ng-show="ndip_obj.alias">{{ ndip_obj.alias }} <span ng-show="ndip_obj.alias_excl">( exclusive )</span></span></td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_netip(ndip_obj, $event)" ng-show="enable_modal && acl_modify(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_netip(ndip_obj, $event)" ng-show="enable_modal && acl_delete(obj, 'backbone.device.change_network')"></input>
<td>
"""

peer_row_template = """
<td>{{ dev_lut[nd_lut[ndip_obj.netdevice].device].full_name }}</td>
<td>{{ nd_lut[ndip_obj.netdevice].devname }} ({{ nd_lut[ndip_obj.netdevice].penalty }})</td>
<td>
    with cost {{ ndip_obj.peer.penalty }}
    &nbsp;<span class="label label-primary">{{ get_peer_cost(ndip_obj) }}</span>&nbsp;
</td>
<td>
    to {{ get_peer_target(ndip_obj) }}
</td>
<td>
    {{ get_peer_type(ndip_obj) }}
</td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_peer_information(ndip_obj, $event)" ng-show="enable_modal && acl_modify(obj, 'backbone.device.change_network')"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_peer_information(ndip_obj, $event)" ng-show="enable_modal && acl_delete(obj, 'backbone.device.change_network')"></input>
</td>
"""

net_cluster_info_template = """
<div class="modal-header">
    <h3 class="modal-title">Devices in cluster ({{ cluster.device_pks.length }})</h3>
</div>
<div class="modal-body">
    <ul>
        <li ng-repeat="device in devices">
            {{ device.full_name }} ({{ device.device_group_name }})
        </li>
    </ul>
    Selected: <b>{{ selected.item }}</b>
</div>
<div class="modal-footer">
    <button class="btn btn-primary" ng-click="ok()">close</button>
</div>
"""

{% endverbatim %}

device_network_module = angular.module("icsw.network.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select"])

angular_module_setup([device_network_module])

device_network_module.controller("network_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$rootScope",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $rootScope) ->
        access_level_service.install($scope)
        $scope.enable_modal = true
        # mixins
        $scope.netdevice_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "nd")
        $scope.netdevice_edit.create_template = "netdevice_form.html"
        $scope.netdevice_edit.edit_template = "netdevice_form.html"
        $scope.netdevice_edit.create_rest_url = Restangular.all("{% url 'rest:netdevice_list'%}".slice(1))
        $scope.netdevice_edit.modify_rest_url = "{% url 'rest:netdevice_detail' 1 %}".slice(1).slice(0, -2)
        $scope.netdevice_edit.new_object_at_tail = false
        $scope.netdevice_edit.use_promise = true

        $scope.netip_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "ni")
        $scope.netip_edit.create_template = "net_ip_form.html"
        $scope.netip_edit.edit_template = "net_ip_form.html"
        $scope.netip_edit.create_rest_url = Restangular.all("{% url 'rest:net_ip_list'%}".slice(1))
        $scope.netip_edit.modify_rest_url = "{% url 'rest:net_ip_detail' 1 %}".slice(1).slice(0, -2)
        $scope.netip_edit.new_object_at_tail = false
        $scope.netip_edit.use_promise = true

        $scope.peer_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "np")
        $scope.peer_edit.create_template = "peer_information_form.html"
        $scope.peer_edit.edit_template = "peer_information_form.html"
        #$scope.peer_edit.edit_template = "netip_template.html"
        $scope.peer_edit.create_rest_url = Restangular.all("{% url 'rest:peer_information_list'%}".slice(1))
        $scope.peer_edit.modify_rest_url = "{% url 'rest:peer_information_detail' 1 %}".slice(1).slice(0, -2)
        $scope.peer_edit.new_object_at_tail = false
        $scope.peer_edit.use_promise = true

        $scope.boot_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "nb")
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
                        "peer_information_form"
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
        $scope.get_ip_objects = () ->
            r_list = []
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
        $scope.scan_device_network = (dev, event) ->
            dev.scan_address = dev.full_name
            dev.strict_mode = true
            $scope.scan_device = dev
            $scope.scan_mixin.edit(dev, event).then(
                (mod_obj) ->
                    true
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
                        new_obj.expanded = false
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
                    "domain_tree_node" : $scope.domain_tree_node[0].idx
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
        $scope.get_peer_type = (peer) ->
            if peer.target of $scope.nd_lut
                other = $scope.nd_lut[peer.target]
                return if other.device == peer.device then "local" else "remote"
            else
                if peer.target of $scope.nd_peer_lut
                    other= $scope.nd_peer_lut[peer.target]
                    return if other.device == peer.device then "local" else "remote"
                else
                    return "---"    
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
        $scope.get_bootdevice_info_class = (obj) ->
            num_bootips = $scope.get_num_bootips(obj)
            if num_bootips == 0
                return ""
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
            return "#{num_bootips} IPs (" + (if obj.dhcp_write then "write" else "no write") + " / " + (if obj.dhcp_mac then "greedy" else "not greedy") + ")"
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
).directive("netdevicerow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("netdevicerow.html")
        link : (scope, element, attrs) ->
    }
).directive("netiprow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("netiprow.html")
        link : (scope, element, attrs) ->
    }
).directive("devrow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("devrow.html")
        link : (scope, element, attrs) ->
    }
).directive("netpeerrow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("peerrow.html")
        link : (scope, element, attrs) ->
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("devicenetworks.html", device_networks_template)
    $templateCache.put("netdevicerow.html", nd_row_template)
    $templateCache.put("netiprow.html", ip_row_template)
    $templateCache.put("peerrow.html", peer_row_template)
    $templateCache.put("devrow.html", dev_row_template)
    $templateCache.put("net_cluster_info.html", net_cluster_info_template)
)

device_network_module.controller("cluster_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.clusters = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devices = _dev_sel
        $scope.reload = () ->
            call_ajax
                url      : "{% url 'network:get_clusters' %}"
                dataType : "json"
                success  : (json) =>
                    $scope.$apply(
                        $scope.clusters = json
                    )
        $scope.is_selected = (cluster) ->
            _sel = _.intersection(cluster.device_pks, $scope.devices)
            return if _sel.length then "yes (#{_sel.length})" else "no"
        $scope.show_cluster = (cluster) ->
            _modal = $modal.open(
                {
                    templateUrl : "net_cluster_info.html"
                    controller  : cluster_info_ctrl
                    size : "lg"
                    resolve : {
                        "cluster" : () -> return cluster
                    }
                }
            )          
        install_devsel_link($scope.new_devsel, false)
        $scope.reload()
])

cluster_info_ctrl = ($scope, $modalInstance, Restangular, cluster) ->
    $scope.cluster = cluster
    $scope.devices = []
    Restangular.all("{% url 'rest:device_tree_list' %}".slice(1)).getList({"pks" : angular.toJson(cluster.device_pks), "ignore_meta_devices" : true}).then(
        (data) ->
            $scope.devices = data
    )
    $scope.ok = () -> 
        $modalInstance.close()

device_network_module.controller("graph_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.graph_mode = "m"
        $scope.graph_sel = "none"
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devices = _dev_sel
            $scope.$apply()
        install_devsel_link($scope.new_devsel, false)
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
                    "translate(#{scope.cur_trans}) scale(#{scope.cur_scale})"
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
                        d3.select(this).select("circle").attr("stroke-width", if d.num_nds then d.num_nds else 1).attr("stroke", if d.num_nds then "grey" else "red")
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
                        "stroke-width" : (n) -> return if n.num_nds then n.num_nds else 1
                        "stroke"  : (n) -> return if n.num_nds then "grey" else "red"
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
            )
    }
])

{% endinlinecoffeescript %}

</script>

