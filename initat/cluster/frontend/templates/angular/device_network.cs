{% load coffeescript %}

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
            <th>MAC / Network</th>
            <th>Devtype / DTN</th>
            <th>routing / alias</th>
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
<th>{{ obj.device_group_name }}</th>
<th>{{ obj.comment }}</th>
<th colspan="3">
    <div class="input-group-btn" ng-show="enable_modal">
        <button type="button" class="btn btn-success btn-sm dropdown-toggle" data-toggle="dropdown">
            Create new <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-click="create_netdevice(obj, $event)"><a href="#">Netdevice</a></li>
            <li ng-show="obj.netdevice_set.length" ng-click="create_netip(obj, $event)"><a href="#">IP Address</a></li>
            <li ng-show="obj.netdevice_set.length" ng-click="create_peer_information(obj, $event)"><a href="#">Peer</a></li>
        </ul>
    </div>
</th>
"""

nd_row_template = """
<td>
    <button class="btn btn-info btn-xs" ng-disabled="ndip_obj.net_ip_set.length + ndip_obj.peers.length == 0" ng-click="toggle_expand(ndip_obj)">
        <span ng-class="get_expand_class(ndip_obj)">
        {{ ndip_obj.net_ip_set.length }} / {{ ndip_obj.peers.length }}
        </span>  
    </button>
    {{ get_netdevice_name(ndip_obj) }}
</td>
<td>{{ ndip_obj.macaddr }}</td>
<td>{{ ndip_obj.network_device_type | array_lookup:network_device_types:'info_string':'-' }}</td>
<td>{{ ndip_obj.routing | yesno2 }} ({{ ndip_obj.penalty }})</td>
<td>
    <input type="button" class="btn btn-xs btn-info" value="info" tooltip-placement="right"
     tooltip-html-unsafe="<div class='text-left'>
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
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_netdevice(obj, ndip_obj, $event)" ng-show="enable_modal"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_netdevice(ndip_obj, $event)" ng-show="enable_modal"></input>
</td>
"""

ip_row_template = """
<td>{{ ndip_obj.ip }}</td>
<td>{{ ndip_obj.network | array_lookup:networks:'info_string':'-' }}</td>
<td>{{ ndip_obj.domain_tree_node | array_lookup:domain_tree_node:'tree_info':'-' }}</td>
<td><span ng-show="ndip_obj.alias">{{ ndip_obj.alias }} ({{ ndip_obj.alias_excl | yesno1 }})</span></td>
<td></td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_netip(ndip_obj, $event)" ng-show="enable_modal"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_netip(ndip_obj, $event)" ng-show="enable_modal"></input>
<td>
"""

peer_row_template = """
<td></td>
<td colspan="3">
    with penalty {{ ndip_obj.peer.penalty }}
    &nbsp;<span class="label label-primary">{{ get_peer_penalty(ndip_obj) }}</span>&nbsp;
    to {{ get_peer_target(ndip_obj) }}
</td>
<td></td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="modify" ng-click="edit_peer_information(ndip_obj, $event)" ng-show="enable_modal"></input>
</td>
<td>
    <input type="button" class="btn btn-danger btn-xs" value="delete" ng-click="delete_peer_information(ndip_obj, $event)" ng-show="enable_modal"></input>
</td>
"""

{% endverbatim %}

device_network_module = angular.module("icsw.network.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_network_module])

device_network_module.controller("network_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
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
        
        $scope.devsel_list = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload= () ->
            wait_list = [
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_network" : true, "pks" : angular.toJson($scope.devsel_list), "dolp" : "backbone.change_network"}]),
                restDataSource.reload(["{% url 'rest:peer_information_list' %}", {}]),
                # 2
                restDataSource.reload(["{% url 'rest:netdevice_speed_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:network_device_type_list' %}", {}])
                # 4
                restDataSource.reload(["{% url 'rest:network_list' %}", {}])
                restDataSource.reload(["{% url 'rest:domain_tree_node_list' %}", {}])
                # 6
                restDataSource.reload(["{% url 'rest:netdevice_peer_list' %}", {}])
                restDataSource.reload(["{% url 'rest:fetch_forms' %}", {"forms" : angular.toJson(["netdevice_form", "net_ip_form", "peer_information_s_form", "peer_information_d_form"])}]),
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
                $scope.domain_tree_node = data[5]
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
        $scope.get_netdevice_name = (nd) ->
            nd_name = nd.devname
            if nd.description
                nd_name = "#{nd_name} (#{nd.description})"
            if nd.vlan_id
                nd_name = "#{nd_name}, VLAN #{nd.vlan_id} on " + String($scope.nd_lut[nd.master_device].devname)
            return nd_name
        $scope.get_expand_class = (dev) ->
            if dev.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.toggle_expand = (dev) ->
            dev.expanded = !dev.expanded
        $scope.get_num_netdevices = (dev) ->
            return dev.netdevice_set.length
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
            console.log $scope.peers[0]
            return (entry for entry in $scope.nd_peers when entry.routing)
        $scope.get_ndip_objects = (dev) ->
            r_list = []
            for ndev in dev.netdevice_set
                r_list.push(ndev)
                r_list = r_list.concat(ndev.net_ip_set)
                r_list = r_list.concat(ndev.peers)
            return r_list
        $scope.create_netdevice = (dev, event) ->
            $scope._current_dev = dev
            $scope.netdevice_edit.create_list = dev.netdevice_set
            $scope.netdevice_edit.new_object = (scope) ->
                return {
                    "device" : dev.idx
                    "devname" : "eth0"
                    "netdevice_speed" : (entry.idx for entry in $scope.netdevice_speeds when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
                    "net_ip_set" : []
                    "ethtool_options" : 0
                    "ethtool_autoneg" : 0
                    "ethtool_speed" : 0
                    "ethtool_duplex" : 0
                    # dummy value
                    "network_device_type" : $scope.network_device_types[0].idx
                } 
            $scope.netdevice_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        new_obj.net_ip_set = []
                        new_obj.expanded = false
                        new_obj.peers = []
                        $scope.nd_lut[new_obj.idx] = new_obj
            )
        $scope.edit_netdevice = (dev, ndev, event) ->
            $scope._current_dev = dev
            $scope.netdevice_edit.edit(ndev, event).then(
                (mod_ndev) ->
                    if mod_ndev != false
                        true
                        #console.log "mod"
            )
        $scope.get_vlan_masters = () ->
            return $scope._current_dev.netdevice_set
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
            return src_nd.devname + " on " + $scope.dev_lut[src_nd.device].name
        $scope.edit_peer_information = (peer, event) ->
            if peer.peer.s_netdevice == peer.netdevice
                $scope.peer_edit.edit_template = "peer_information_d_form.html"
            else
                $scope.peer_edit.edit_template = "peer_information_s_form.html"
            #$scope._src_nd = $scope.nd_lut[peer.netdevice]
            $scope.peer_edit.edit(peer.peer, event).then(
                (mod_peer) ->
                    if mod_peer != false
                        true
                        # console.log "modpeer"
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
                        # console.log "delnd"
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
        $scope.get_peer_penalty = (ndip_obj) ->
            if ndip_obj.target of $scope.nd_lut
                t_penalty = $scope.nd_lut[ndip_obj.target].penalty
            else
                t_penalty = $scope.nd_peer_lut[ndip_obj.target].penalty
            return t_penalty + ndip_obj.peer.penalty + $scope.nd_lut[ndip_obj.netdevice].penalty
        $scope.get_peer_target = (ndip_obj) ->
            if ndip_obj.target of $scope.nd_lut
                peer = $scope.nd_lut[ndip_obj.target]
                return "#{peer.devname} (#{peer.penalty}) on " + String($scope.dev_lut[peer.device].name)
            else
                peer = $scope.nd_peer_lut[ndip_obj.target]
                return "#{peer.devname} (#{peer.penalty}) on #{peer.device__name}"
        $scope.copy_network = (src_obj, event) ->
            if confirm("Overwrite all networks with the one from #{src_obj.full_name} ?")
                $.blockUI()
                $.ajax
                    url     : "{% url 'network:copy_network' %}"
                    data    : {
                        "source_dev" : src_obj.idx
                        "all_devs"   : angular.toJson(@devsel_list)
                    },
                    success : (xml) =>
                        $.unblockUI()
                        parse_xml_response(xml)
                        $scope.reload()
        install_devsel_link($scope.new_devsel, true, true, false)
]).directive("devicenetworks", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devicenetworks.html")
        link : (scope, el, attrs) ->
            if attrs["devicepk"]?
                scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
            if attrs["disablemodal"]?
                scope.enable_modal = if parseInt(attrs["disablemodal"]) then false else true
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

{% endinlinecoffeescript %}

</script>

