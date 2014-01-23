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
            <th>Info</th>
            <th>Device</th>
            <th>Group</th>
            <th>Comment</th>
            <th>action</th>
        </tr>
    </thead>
    <tbody>
        <tr dnrow ng-repeat-start="obj in devices"></tr>
        <tr ndiprow ng-repeat-end ng-repeat="ndip_obj in get_ndip_objects(obj)" ng-show="obj.expanded"></tr>
    </tbody>
</table>
"""

dn_row_template = """
<td>
    <button class="btn btn-primary btn-xs" ng-click="toggle_expand(obj)">
        <span ng_class="get_expand_class(obj)">
        {{ get_num_netdevices(obj) }} / {{ get_num_netips(obj) }}  
        </span>
    </button>
</td>
<td>{{ obj.full_name }}</td>
<td>{{ obj.device_group_name }}</td>
<td>{{ obj.comment }}</td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="create nd" ng-click="create_netdevice(obj, $event)"></input>
</td>
"""

nd_row_template = """
<td>{{ ndip_obj.devname }}</td>
<td>
    <input type="button" class="btn btn-primary btn-xs" value="create IP" ng-click="create_netip(ndip_obj, $event)">
    </input>
    <input type="button" class="btn btn-success btn-xs" value="modify" ng-click="edit_netdevice(obj, ndip_obj, $event)">
    </input>
<td>
"""

ip_row_template = """
<td>{{ ndip_obj.ip }}****</td>
<td>
    <input type="button" class="btn btn-success btn-xs" value="modify" ng-click="edit_netip(ndip_obj, $event)">
    </input>
<td>
"""

{% endverbatim %}

device_network_module = angular.module("icsw.network.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_network_module])

device_network_module.controller("network_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        # mixins
        $scope.netdevice_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.netdevice_edit.create_template = "netdevice_template.html"
        $scope.netdevice_edit.edit_template = "netdevice_template.html"
        $scope.netdevice_edit.create_rest_url = Restangular.all("{% url 'rest:netdevice_list'%}".slice(1))
        $scope.netdevice_edit.modify_rest_url = "{% url 'rest:netdevice_detail' 1 %}".slice(1).slice(0, -2)
        $scope.netdevice_edit.new_object_at_tail = false
        $scope.netdevice_edit.use_promise = true

        $scope.netip_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.netip_edit.create_template = "netip_template.html"
        $scope.netip_edit.edit_template = "netip_template.html"
        $scope.netip_edit.create_rest_url = Restangular.all("{% url 'rest:net_ip_list'%}".slice(1))
        $scope.netip_edit.modify_rest_url = "{% url 'rest:net_ip_detail' 1 %}".slice(1).slice(0, -2)
        $scope.netip_edit.new_object_at_tail = false
        $scope.netip_edit.use_promise = true
        $scope.devsel_list = []
        $scope.devices = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            wait_list = [
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_network" : true, "pks" : angular.toJson($scope.devsel_list)}]),
                restDataSource.reload(["{% url 'rest:peer_information_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:netdevice_speed_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:network_device_type_list' %}", {}])
                restDataSource.reload(["{% url 'rest:network_list' %}", {}])
                restDataSource.reload(["{% url 'rest:domain_tree_node_list' %}", {}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = (dev for dev in data[0])
                for dev in $scope.devices
                    dev.expanded = true
                $scope.peers = data[1]
                $scope.netdevice_speeds = data[2]
                $scope.network_device_types = data[3]
                $scope.networks = data[4]
                $scope.domain_tree_node = data[5]
            )
        $scope.get_expand_class = (dev) ->
            if dev.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.toggle_expand = (dev) ->
            dev.expanded = !dev.expanded
        $scope.get_num_netdevices = (dev) ->
            return dev.netdevice_set.length
        $scope.get_ndip_objects = (dev) ->
            r_list = []
            for ndev in dev.netdevice_set
                r_list.push(ndev)
                r_list = r_list.concat(ndev.net_ip_set)
            return r_list
        $scope.get_num_netips = (dev) ->
            num_ip = 0
            for nd in dev.netdevice_set
                num_ip += nd.net_ip_set.length
            return num_ip
        $scope.create_netdevice = (dev, event) ->
            $scope.netdevice_edit.create_list = dev.netdevice_set
            $scope.netdevice_edit.new_object = (scope) ->
                return {
                    "device" : dev.idx
                    "devname" : "eth0"
                    "netdevice_speed" : (entry.idx for entry in $scope.netdevice_speeds when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
                    "net_ip_set" : []
                    # dummy value
                    "network_device_type" : $scope.network_device_types[0].idx
                } 
            $scope.netdevice_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        console.log "done"
            )
        $scope.edit_netdevice = (dev, ndev, event) ->
            $scope.netdevice_edit.edit(ndev, event).then(
                (mod_ndev) ->
                    if mod_ndev != false
                        console.log "mod"
            )
        $scope.create_netip = (ndev, event) ->
            $scope.netip_edit.create_list = ndev.net_ip_set
            $scope.netip_edit.new_object = (scope) ->
                return {
                    "netdevice" : ndev.idx
                    "ip" : "0.0.0.0"
                    "network" : $scope.networks[0].idx
                    "domain_tree_node" : $scope.domain_tree_node[0].idx
                } 
            $scope.netip_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        console.log "done ip"
            )
        $scope.edit_netip = (ip, event) ->
            $scope.netip_edit.edit(ip, event).then(
                (mod_ip) ->
                    if mod_ip != false
                        console.log "modip"
            )
        install_devsel_link($scope.new_devsel, true, true, false)
]).directive("devicenetworks", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devicenetworks.html")
        link : (scope, el, attrs) ->
            if attrs["devicepk"]
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
    $templateCache.put("devicenetworks.html", device_networks_template)
    $templateCache.put("devicenetrow.html", dn_row_template)
    $templateCache.put("netdevicerow.html", nd_row_template)
    $templateCache.put("netiprow.html", ip_row_template)
)

{% endinlinecoffeescript %}

</script>
