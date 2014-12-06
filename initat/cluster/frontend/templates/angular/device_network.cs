{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

device_networks_template = """
<h3>
    Network config for {{ devices.length }} devices ({{ get_nd_objects().length }} netdevices, {{ get_ip_objects().length }} IPs, {{ get_peer_objects().length }} peers)
</h3>
<accordion close-others="no">
    <accordion-group is-open="device_open">
        <accordion-heading>
            <i class="glyphicon" ng-class="{'glyphicon-chevron-down': device_open, 'glyphicon-chevron-right': !device_open}"></i>
            {{ devices.length }} devices
        </accordion-heading>
        <table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
            <thead>
                <tr>
                    <th>Device</th>
                    <th>bootinfo</th>
                    <th>#Ports</th>
                    <th>#IPs</th>
                    <th>#peers</th>
                    <th>SNMP schemes</th>
                    <th colspan="2">action</th>
                </tr>
            </thead>
            <tbody>
                <tr devrow ng-repeat="ndip_obj in devices"></tr>
            </tbody>
        </table>
    </accordion-group>
    <accordion-group is-open="netdevice_open">
        <accordion-heading>
            <i class="glyphicon" ng-class="{'glyphicon-chevron-down': netdevice_open, 'glyphicon-chevron-right': !netdevice_open}"></i>
            {{ get_nd_objects().length }} netdevices
        </accordion-heading>
        <table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
            <thead>
                <tr>
                    <th>Device</th>
                    <th>idx</th>
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
                    <th>status</th>
                    <th colspan="4">action</th>
                </tr>
            </thead>
            <tbody>
                <tr netdevicerow ng-repeat="ndip_obj in get_nd_objects()"></tr>
            </tbody>
        </table>
    </accordion-group>
    <accordion-group is-open="netip_open">
        <accordion-heading>
            <i class="glyphicon" ng-class="{'glyphicon-chevron-down': netip_open, 'glyphicon-chevron-right': !netip_open}"></i>
            {{ get_ip_objects().length }} IPs
        </accordion-heading>
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
    </accordion-group>
    <accordion-group is-open="peer_open">
        <accordion-heading>
            <i class="glyphicon" ng-class="{'glyphicon-chevron-down': peer_open, 'glyphicon-chevron-right': !peer_open}"></i>
            {{ get_peer_objects().length }} peer connections
        </accordion-heading>
        <table ng-show="devices.length" class="table table-condensed table-hover table-striped" style="width:auto;">
            <thead>
                <tr>
                    <th>Device</th>
                    <th>Port</th>
                    <th>IPs</th>
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
    </accordion-group>
</accordion>
"""

dev_row_template = """
<td>
    {{ ndip_obj.full_name }}
</td>
<td>
    <input
        type="button"
        class="btn btn-xs btn-warning"
        ng-class="get_bootdevice_info_class(ndip_obj)"
        ng-show="get_num_bootips(ndip_obj)"
        ng-value="get_boot_value(ndip_obj)"
        ng-click="edit_boot_settings(ndip_obj, $event)">
    </input>
    <span ng-show="!get_num_bootips(ndip_obj)">N/A</span>
    <!--<button class="btn btn-primary btn-xs" ladda="true" data-style="expand-left">xxx</button>-->
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
<td>
    <span class="label label-info" ng-repeat="obj in ndip_obj.snmp_schemes">
        {{ obj.full_name }}
        <span class="glyphicon glyphicon-remove"></span>
    </span>
</td>
<td>
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
    <div class="input-group-btn" ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network')">
        <div class="btn-group btn-xs">
            <button type="button" class="btn btn-success btn-xs dropdown-toggle" data-toggle="dropdown">
                Create new <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-click="create_netdevice(ndip_obj, $event)"><a href="#">Netdevice</a></li>
                <li ng-show="ndip_obj.netdevice_set.length && networks.length" ng-click="create_netip_dev(ndip_obj, $event)"><a href="#">IP Address</a></li>
                <li ng-show="ndip_obj.netdevice_set.length && nd_peers.length" ng-click="create_peer_information_dev(ndip_obj, $event)"><a href="#">Network topology connection</a></li>
            </ul>
        </div>
            <button type="button" class="btn btn-warning btn-xs"
                ng-show="enable_modal && acl_create(obj, 'backbone.device.change_network')"
                ng-click="scan_device_network(ndip_obj, $event)">
            update network
            </button>
    </div>
</td>
"""

nd_row_template = """
<td>
    {{ dev_lut[ndip_obj.device].full_name }}
</td>
<td>
    <span ng-show="ndip_obj.snmp_idx">{{ ndip_obj.snmp_idx }}</span>
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
<td>{{ get_network_type(ndip_obj) }}</td>
<td class="text-right">{{ ndip_obj.mtu }}</td>
<td>{{ ndip_obj.netdevice_speed | array_lookup:netdevice_speeds:'info_string':'-' }}</td>
<td class="text-right">{{ ndip_obj.penalty }}</td>
<td>{{ get_flags(ndip_obj) }}</td>
<td ng-class="get_snmp_ao_status_class(ndip_obj)">{{ get_snmp_ao_status(ndip_obj) }}</td>
<td>
    <button type="button" class="btn btn-xs btn-success"
     tooltip-placement="right"
     tooltip-html-unsafe="<div class='text-left'>
        device: {{ get_netdevice_name(ndip_obj) }}<br>
        SNMP: {{ ndip_obj.snmp_idx && 'yes' || 'no' }}<span ng-show='ndip_obj.snmp'> ( {{ ndip_obj.snmp_idx }} )</span><br>
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
            <li ng-show="networks.length" ng-click="create_netip_nd(ndip_obj, $event)"><a href="#">IP Address</a></li>
            <li ng-click="create_peer_information_nd(ndip_obj, $event)"><a href="#">Network topology connection</a></li>
        </ul>
    </div>
</td>
"""

ip_row_template = """
<td>{{ dev_lut[nd_lut[ndip_obj.netdevice].device].full_name }}</td>
<td>{{ get_netdevice_name(ndip_obj.netdevice) }}</td>
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
<td>{{ get_netdevice_name(ndip_obj.netdevice) }} ({{ nd_lut[ndip_obj.netdevice].penalty }})</td>
<td>
    <span ng-repeat="ip in get_ip_objects(nd_lut[ndip_obj.netdevice])">{{ ip.ip }}&nbsp;</span>
</td>
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

chart_template = """
<svg                                                                                                                                                                                                                                                                           
  class="draggable-container"                                                                                                                                                                                                                                                  
  xmlns="http://www.w3.org/2000/svg"                                                                                                                                                                                                                                           
  ng-mousedown="mouseDown($event)"                                                                                                                                                                                                                                             
  ng-mousemove="mouseMove($event)"                                                                                                                                                                                                                                             
  >                                                                                                                                                                                                                                                                            
  <defs>                                                                                                                                                                                                                                                                       
    <linearGradient                                                                                                                                                                                                                                                            
      spreadMethod="pad"                                                                                                                                                                                                                                                       
      y2="0"                                                                                                                                                                                                                                                                   
      x2="0"                                                                                                                                                                                                                                                                   
      y1="1"                                                                                                                                                                                                                                                                   
      x1="0"                                                                                                                                                                                                                                                                   
      id="nodeBackgroundGradient"                                                                                                                                                                                                                                              
      >                                                                                                                                                                                                                                                                        
      <stop                                                                                                                                                                                                                                                                    
        offset="0"                                                                                                                                                                                                                                                             
        stop-opacity="0.99609"                                                                                                                                                                                                                                                 
        stop-color="#56aaff"                                                                                                                                                                                                                                                   
        />                                                                                                                                                                                                                                                                     
        <stop 
        offset="0.63934" 
        stop-opacity="0.99219" 
        stop-color="#d0d0e5"
        />
    </linearGradient>
  </defs>
  <g
    ng-repeat="node in chart.nodes"
    ng-mousedown="nodeMouseDown($event, node)"
    ng-attr-transform="translate({{node.x()}}, {{node.y()}})"
    >
    <rect 
      ng-attr-class="{{node.selected() && 'selected-node-rect' || (node == mouseOverNode && 'mouseover-node-rect' || 'node-rect')}}"
      ry="10" 
      rx="10" 
      x="0" 
      y="0" 
      ng-attr-width="{{node.width()}}" 
      ng-attr-height="{{node.height()}}" 
      fill="url(#nodeBackgroundGradient)"
      >

    </rect>

    <text
      ng-attr-x="{{node.width()/2}}"
      y="25"
      text-anchor="middle"
      alignment-baseline="middle"
      >
      {{node.name()}}
    </text>

    <g
      ng-repeat="connector in node.inputConnectors"
      ng-mousedown="connectorMouseDown($event, node, connector, $index, true)"
      class="connector input-connector"
      >
      <text
        ng-attr-x="{{connector.x() + 20}}"
        ng-attr-y="{{connector.y()}}"
        text-anchor="left"
        alignment-baseline="middle"
        >
        {{connector.name()}}
      </text>
      
      <circle       
        ng-attr-class="{{connector == mouseOverConnector && 'mouseover-connector-circle' || 'connector-circle'}}"
        ng-attr-r="{{connectorSize}}" 
        ng-attr-cx="{{connector.x()}}"
        ng-attr-cy="{{connector.y()}}"
        />
    </g>

    <g
      ng-repeat="connector in node.outputConnectors"
      ng-mousedown="connectorMouseDown($event, node, connector, $index, false)"
      class="connector output-connector"
      >
      <text
        ng-attr-x="{{connector.x() - 20}}"
        ng-attr-y="{{connector.y()}}"
        text-anchor="end"
        alignment-baseline="middle"
        >
        {{connector.name()}}
      </text>

      <circle             
        ng-attr-class="{{connector == mouseOverConnector && 'mouseover-connector-circle' || 'connector-circle'}}"
        ng-attr-r="{{connectorSize}}" 
        ng-attr-cx="{{connector.x()}}"
        ng-attr-cy="{{connector.y()}}"
        />
    </g>
  </g>

  <g>
    <g
      ng-repeat="connection in chart.connections"
      class="connection"
      ng-mousedown="connectionMouseDown($event, connection)"
      >
        <path
          ng-attr-class="{{connection.selected() && 'selected-connection-line' || (connection == mouseOverConnection && 'mouseover-connection-line' || 'connection-line')}}"
          ng-attr-d="M {{connection.sourceCoordX()}}, {{connection.sourceCoordY()}}
                     C {{connection.sourceTangentX()}}, {{connection.sourceTangentY()}}
                       {{connection.destTangentX()}}, {{connection.destTangentY()}}
                       {{connection.destCoordX()}}, {{connection.destCoordY()}}"
          >
        </path>
        <circle
            ng-attr-class="{{connection.selected() && 'selected-connection-endpoint' || (connection == mouseOverConnection && 'mouseover-connection-endpoint' || 'connection-endpoint')}}"
            r="5" 
            ng-attr-cx="{{connection.sourceCoordX()}}" 
            ng-attr-cy="{{connection.sourceCoordY()}}" 
            >
        </circle>

        <circle
            ng-attr-class="{{connection.selected() && 'selected-connection-endpoint' || (connection == mouseOverConnection && 'mouseover-connection-endpoint' || 'connection-endpoint')}}"
            r="5" 
            ng-attr-cx="{{connection.destCoordX()}}" 
            ng-attr-cy="{{connection.destCoordY()}}" 
            >
        </circle>
    </g>
  </g>

  <g
    ng-if="draggingConnection"
    >
    <path
      class="dragging-connection dragging-connection-line"
      ng-attr-d="M {{dragPoint1.x}}, {{dragPoint1.y}}
                 C {{dragTangent1.x}}, {{dragTangent1.y}}
                   {{dragTangent2.x}}, {{dragTangent2.y}}
                   {{dragPoint2.x}}, {{dragPoint2.y}}"
      >
    </path>

    <circle
        class="dragging-connection dragging-connection-endpoint"
        r="4" 
        ng-attr-cx="{{dragPoint1.x}}" 
        ng-attr-cy="{{dragPoint1.y}}" 
        >
    </circle>

    <circle
        class="dragging-connection dragging-connection-endpoint"
        r="4" 
        ng-attr-cx="{{dragPoint2.x}}" 
        ng-attr-cy="{{dragPoint2.y}}" 
        >
    </circle>
  </g>

  <rect
      ng-if="dragSelecting"
      class="drag-selection-rect"
      ng-attr-x="{{dragSelectionRect.x}}"
      ng-attr-y="{{dragSelectionRect.y}}"
      ng-attr-width="{{dragSelectionRect.width}}"
      ng-attr-height="{{dragSelectionRect.height}}"
    >
  </rect>
  
</svg>
"""

{% endverbatim %}

removeClassSVG = (obj, remove) ->
    classes = obj.attr('class')
    if !classes
        return false
    index = classes.search(remove);
    if index == -1
        return false
    else
        classes = classes.substring(0, index) + classes.substring((index + remove.length), classes.length)
        obj.attr('class', classes)
        return true

has_class_svg = (obj, has) ->
    classes = obj.attr('class')
    if !classes
        return false
    return if classes.search(has) == -1 then false else true

testchart = {
     nodes : [
        {
            "name": "Example Node 1",
            "id": 0,
            "x": 26,
            "y": 33,
            "inputConnectors": [
                {
                    "name": "A"
                },
                {
                    "name": "B"
                },
                {
                    "name": "C"
                }
            ],
            "outputConnectors": [
                {
                    "name": "A"
                },
                {
                    "name": "B"
                },
                {
                    "name": "C"
                }
            ]
        },
    ]
}

angular.module("mouseCapture", []).factory('mouseCapture', ($rootScope) ->
    $element = document
    mouseCaptureConfig = null
    mouseMove = (event) ->
        if mouseCaptureConfig and mouseCaptureConfig.mouseMove
            mouseCaptureConfig.mouseMove(event)
            $rootScope.$digest()
    mouseUp = (event) ->
        if mouseCaptureConfig and mouseCaptureConfig.mouseUp
            mouseCaptureConfig.mouseUp(event)
            $rootScope.$digest()
    return {
        registerElement: (element) ->
            $element = element
        acquire: (event, config) ->
            this.release()
            mouseCaptureConfig = config
            $element.mousemove(mouseMove)
            $element.mouseup(mouseUp)
        release: () ->
            if mouseCaptureConfig
                if mouseCaptureConfig.released
                    mouseCaptureConfig.released()
                mouseCaptureConfig = null;
                $element.unbind("mousemove", mouseMove)
                $element.unbind("mouseup", mouseUp)
    }
).directive('mouseCapture', () ->
    return {
        restrict: "A"
        controller: ($scope, $element, $attrs, mouseCapture) ->
            mouseCapture.registerElement($element)
    }
)

angular.module("dragging", ["mouseCapture"]
).factory("dragging", ($rootScope, mouseCapture) ->
    return {
        startDrag: (event, threshold, config) ->
            dragging = false
            x = event.clientX
            y = event.clientY
            mouseMove = (event) ->
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
            mouseUp = (event) ->
                mouseCapture.release()
                event.stopPropagation()
                event.preventDefault()
            mouseCapture.acquire(event, {
                mouseMove: mouseMove
                mouseUp: mouseUp
                released: released
            })
            event.stopPropagation()
            event.preventDefault()
    }
)

angular.module("flowChart", ["dragging"]
).directive("flowChart", () ->
    return {
        restrict: "E"
        template: chart_template
        replace: true,
        scope: 
            chart: "=chart"
        controller: "FlowChartController"
    }
).directive("chartJsonEdit", () ->
    return {
        restrict: "A"
        scope: 
            viewModel: "="
        link: (scope, elem, attr) ->
            updateJson = () ->
                if scope.viewModel
                    json = angular.toJson(scope.viewModel.data, null, 4)
                    $(elem).val(json)
            updateJson()
            scope.$watch("viewModel.data", updateJson, true)
            $(elem).bind("input propertychange", () ->
                json = $(elem).val()
                dataModel = angular.fromJson(json)
                scope.viewModel = flowchart.ChartViewModel(dataModel)
                scope.$digest()
            )
    }
).controller("FlowChartController", ["$scope", "dragging", "$element",
    FlowChartController = ($scope, dragging, $element) ->
        controller = this
        this.document = document
        this.jQuery = (element) ->
            return $(element)
        $scope.draggingConnection = false
        $scope.connectorSize = 10
        $scope.dragSelecting = false
        $scope.mouseOverConnector = null
        $scope.mouseOverConnection = null
        $scope.mouseOverNode = null
        this.connectionClass = 'connection'
        this.connectorClass = 'connector'
        this.nodeClass = "node"
        this.searchUp = (element, parentClass) ->
            if element == null or element.length == 0
                return null
            if hasClassSVG(element, parentClass)
                return element
            return this.searchUp(element.parent(), parentClass)
        this.hitTest = (clientX, clientY) ->
            return this.document.elementFromPoint(clientX, clientY)
        this.checkForHit = (mouseOverElement, whichClass) ->
            hoverElement = this.searchUp(this.jQuery(mouseOverElement), whichClass)
            if !hoverElement
                return null
            return hoverElement.scope()
        this.translateCoordinates = (x, y) ->
            svg_elem =  $element.get(0)
            matrix = svg_elem.getScreenCTM()
            point = svg_elem.createSVGPoint()
            point.x = x
            point.y = y
            return point.matrixTransform(matrix.inverse())
        $scope.mouseDown = (event) ->
            $scope.chart.deselectAll()
            dragging.startDrag(event, {
                dragStarted: (x, y) ->
                    $scope.dragSelecting = true;
                    startPoint = controller.translateCoordinates(x, y)
                    $scope.dragSelectionStartPoint = startPoint
                    $scope.dragSelectionRect = {
                        x: startPoint.x
                        y: startPoint.y
                        width: 0
                        height: 0
                    }
                dragging: (x, y) ->
                    startPoint = $scope.dragSelectionStartPoint
                    curPoint = controller.translateCoordinates(x, y)
    
                    $scope.dragSelectionRect = {
                        x: if curPoint.x > startPoint.x then startPoint.x else curPoint.x
                        y: if curPoint.y > startPoint.y then startPoint.y else curPoint.y
                        width: if curPoint.x > startPoint.x then curPoint.x - startPoint.x else startPoint.x - curPoint.x
                        height: if curPoint.y > startPoint.y then curPoint.y - startPoint.y else startPoint.y - curPoint.y
                    }
                dragEnded: () ->
                    $scope.dragSelecting = false
                    $scope.chart.applySelectionRect($scope.dragSelectionRect)
                    delete $scope.dragSelectionStartPoint
                    delete $scope.dragSelectionRect
            })
        $scope.mouseMove = (event) ->
            $scope.mouseOverConnection = null
            $scope.mouseOverConnector = null
            $scope.mouseOverNode = null
            mouseOverElement = controller.hitTest(event.clientX, event.clientY)
            if mouseOverElement == null
                return
            if !$scope.draggingConnection
                scope = controller.checkForHit(mouseOverElement, controller.connectionClass)
                $scope.mouseOverConnection = if (scope && scope.connection) then scope.connection else null
                if $scope.mouseOverConnection
                    return;
            scope = controller.checkForHit(mouseOverElement, controller.connectorClass)
            $scope.mouseOverConnector = if (scope && scope.connector) then scope.connector else null
            if $scope.mouseOverConnector
                return
            scope = controller.checkForHit(mouseOverElement, controller.nodeClass)
            $scope.mouseOverNode = if (scope && scope.node) then scope.node else null
        $scope.nodeMouseDown = (event, node) ->
            chart = $scope.chart
            dragging.startDrag(event, {
                dragStarted: (x, y) ->
                    lastMouseCoords = controller.translateCoordinates(x, y)
                    if !node.selected()
                        chart.deselectAll()
                        node.select()
                dragging: (x, y) ->
                    curCoords = controller.translateCoordinates(x, y)
                    deltaX = curCoords.x - lastMouseCoords.x
                    deltaY = curCoords.y - lastMouseCoords.y
                    chart.updateSelectedNodesLocation(deltaX, deltaY)
                    lastMouseCoords = curCoords
                clicked: () ->
                    chart.handleNodeClicked(node, event.ctrlKey)
            })
        $scope.connectionMouseDown = (event, connection) ->
            chart = $scope.chart
            chart.handleConnectionMouseDown(connection, event.ctrlKey)
            event.stopPropagation()
            event.preventDefault()
        $scope.connectorMouseDown = (event, node, connector, connectorIndex, isInputConnector) ->
            dragging.startDrag(event, {
                dragStarted: (x, y) ->
                    curCoords = controller.translateCoordinates(x, y)
                    $scope.draggingConnection = true
                    $scope.dragPoint1 = flowchart.computeConnectorPos(node, connectorIndex, isInputConnector)
                    $scope.dragPoint2 = {
                        x: curCoords.x
                        y: curCoords.y
                    }
                    $scope.dragTangent1 = flowchart.computeConnectionSourceTangent($scope.dragPoint1, $scope.dragPoint2)
                    $scope.dragTangent2 = flowchart.computeConnectionDestTangent($scope.dragPoint1, $scope.dragPoint2)
                dragging: (x, y, event) ->
                    startCoords = controller.translateCoordinates(x, y)
                    $scope.dragPoint1 = flowchart.computeConnectorPos(node, connectorIndex, isInputConnector)
                    $scope.dragPoint2 = {
                        x: startCoords.x
                        y: startCoords.y
                    }
                    $scope.dragTangent1 = flowchart.computeConnectionSourceTangent($scope.dragPoint1, $scope.dragPoint2)
                    $scope.dragTangent2 = flowchart.computeConnectionDestTangent($scope.dragPoint1, $scope.dragPoint2)
                dragEnded: () ->
                    if $scope.mouseOverConnector and $scope.mouseOverConnector != connector
                        $scope.chart.createNewConnection(connector, $scope.mouseOverConnector)
                    $scope.draggingConnection = false
                    delete $scope.dragPoint1
                    delete $scope.dragTangent1
                    delete $scope.dragPoint2
                    delete $scope.dragTangent2
            })
])

device_network_module = angular.module("icsw.network.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select", "angular-ladda", "dragging"])

angular_module_setup([device_network_module])

device_network_module.controller("network_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$rootScope",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $rootScope) ->
        access_level_service.install($scope)
        $scope.enable_modal = true
        # accordion flags
        $scope.device_open = true
        $scope.netdevice_open = true
        $scope.netip_open = false
        $scope.peer_open = false
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
                restDataSource.reload(["{% url 'rest:snmp_network_type_list' %}", {}])
                # 8
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
                $scope.peers = data[1]
                $scope.netdevice_speeds = data[2]
                $scope.network_device_types = data[3]
                $scope.ndt_lut = build_lut($scope.network_device_types)
                $scope.networks = data[4]
                $scope.network_lut = build_lut($scope.networks)
                $scope.domain_tree_node = data[5]
                $scope.dtn_lut = build_lut($scope.domain_tree_node)
                $scope.nd_peers = data[6]
                $scope.build_luts()
                # snmp network types
                $scope.snt = data[7]
                $scope.snt_lut = build_lut($scope.snt)
                # forms
                for cur_form in data[8] 
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
        $scope.scan_device_network = (dev, event) ->
            $scope._current_dev = dev
            $scope.scan_device = dev
            dev.scan_address = dev.full_name
            dev.snmp_address = dev.full_name
            dev.snmp_community = "public"
            dev.snmp_version = 1
            dev.remove_not_found = false
            dev.strict_mode = true
            dev.scan_hm_active = false
            dev.scan_snmp_active = false
            if $scope.no_objects_defined(dev)
                $scope.set_scan_mode("snmp")
            else
                $scope.set_scan_mode("hm")
            $scope.scan_mixin.edit(dev, event).then(
                (mod_obj) ->
                    true
            )
        $scope.fetch_device_network = () ->
            $.blockUI()
            call_ajax
                url     : "{% url 'device:scan_device_network' %}"
                data    :
                    "dev" : angular.toJson($scope.scan_device)
                success : (xml) ->
                    parse_xml_response(xml)
                    Restangular.all("{% url 'rest:device_tree_list' %}".slice(1)).getList({"with_network" : true, "pks" : angular.toJson([$scope.scan_device.idx]), "olp" : "backbone.device.change_network"}).then(
                        (dev_data) ->
                            Restangular.all("{% url 'rest:network_list' %}".slice(1)).getList().then((data) ->
                                $scope.networks = data
                                $scope.network_lut = build_lut($scope.networks)
                                $scope.update_device(dev_data[0])
                                $.unblockUI()
                            )
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
            #scope.get_snmp_scheme_info = (obj) ->
            #    _sc = obj.snmp_schemes
            #    if _sc.length
            #        return ("#{_entry.snmp_scheme_vendor.name}.#{_entry.name}" for _entry in _sc).join(", ")
            #    else
            #        return "---"
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
]).directive("hostnode", ["dragging", (dragging) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope: 
            node: "=node"
            redraw: "=redraw"
        template: """
{% verbatim %}
<g class="node draggable" node_id="{{ node.id }}"
    ng-mouseenter="mouse_enter()"
    ng-mouseleave="mouse_leave()"
    ng-click="mouse_click()"
    ng-dblclick="double_click($event)"
>
    <circle r="18" fill="{{ fill_color }}" stroke-width="{{ stroke_width }}" stroke="{{ stroke_color }}" cursor="crosshair"></circle>
    <text text-anchor="middle" cursor="crosshair">{{ node.name }}</text>
</g>       
{% endverbatim %}
"""
        link : (scope, element, attrs) ->
            scope.stroke_width = 1
            scope.focus = true
            scope.mousedown = false
            scope.$watch("node", (new_val) ->
                scope.node = new_val
                scope.fill_color = "white"
                scope.stroke_width = if new_val.num_nds then new_val.num_nds else 1
                scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            scope.$watch("redraw", () ->
                scope.transform()
            )
            scope.transform= () ->
                if scope.node.x?
                    element.attr("transform", "translate(#{scope.node.x},#{scope.node.y})")
                scope.fill_color = if scope.node.fixed then "red" else "white"
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
            scope.double_click = (event) ->
                cur_di = new device_info(event, scope.node.id)
                cur_di.show()
    }
]).directive("hostlink", () ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope: 
            link: "=link"
            redraw: "=redraw"
        template: """
{% verbatim %}
<line stroke="#ff7788" stroke-width="2" opacity="1">
</line>
{% endverbatim %}
"""
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
).directive("networkgraph", ["d3_service", "dragging", (d3_service, dragging) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        template: """
{% verbatim %}
<svg
    class="draggable"
    ng-attr-width="{{ size.width }}"
    ng-attr-height="{{ size.height }}"
    ng-attr-viewBox="0 0 {{ size.width }} {{ size.height }}"
    preserveAspectRatio="xMidYMid"
    style="width:100%;"
    pointer-events: "all"
    ng-mousedown="mouse_down($event)"
>
    <g ng-attr-transform="translate({{ offset.x }}, {{ offset.y }})">
        <hostlink ng-repeat="link in links" link="link" redraw="redraw_nodes"></hostlink>
        <hostnode ng-repeat="node in nodes" node="node" redraw="redraw_nodes"></hostnode>
    </g>
</svg>
{% endverbatim %}
""" 
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            scope.cur_trans = [0, 0]
            scope.size = {
                width: 1000
                height: 800
            }
            scope.offset = {
                x: 0
                y: 0
            }
            scope.nodes = []
            scope.redraw_nodes = 0
            d3_service.d3().then((d3) ->
                width = 1000
                height = 800
                scope.svg_el = element[0]
                svg = d3.select(scope.svg_el)
                scope.svg = svg
                svg.attr("height", scope.size.height)
                scope.vis = d3.select(element.find("g")[0])
                scope.nodes = []
                scope.links = []
                scope.force = d3.layout.force().charge(-220).gravity(0.02).linkDistance(150).size([width, height])
                  .linkDistance((d) -> return 100).on("tick", scope.tick)
                scope.get_rel_coordinate = (x, y) ->
                    screen_ctm = scope.svg_el.getScreenCTM()
                    svg_point = scope.svg_el.createSVGPoint()
                    svg_point.x = x
                    svg_point.y = y
                    first = svg_point.matrixTransform(screen_ctm.inverse())
                    first.x -= scope.offset.x
                    first.y -= scope.offset.y
                    return first
                    glob_to_local = event.target.getTransformToElement(scope.svg_el)
                    second = first.matrixTransform(glob_to_local.inverse())
                    return second
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
            scope.draw_graph = () ->
                scope.iter = 0
                scope.force.nodes(scope.json_data.nodes).links(scope.json_data.links)
                console.log scope.json_data.links
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
                if has_class_svg(s_target, "draggable")
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
                        dragging.startDrag(event, 0, {
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
                        dragging.startDrag(event, 1, {
                            dragStarted: (x, y, event) ->
                                drag_node.dragging = true
                                drag_node.fixed = true
                                drag_node.ignore_click = true
                                scope.start_drag_point = scope.get_rel_coordinate(x, y)
                                scope.force.start()
                            dragging: (x, y) ->
                                cur_point = scope.get_rel_coordinate(x, y)
                                drag_node.x = cur_point.x
                                drag_node.y = cur_point.y
                                drag_node.px = cur_point.x
                                drag_node.py = cur_point.y
                                scope.tick()
                            dragEnded: () ->
                                drag_node.dragging = false
                        })
            scope.iter = 0
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
