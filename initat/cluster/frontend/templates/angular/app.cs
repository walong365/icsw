{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

ics_app = angular.module(
    "icsw.app",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "icsw.menu_app", "icsw.user", "icsw.monitoring.create", "icsw.device.config", "icsw.device",
        "icsw.login",
        "icsw.monitoring_basic", "icsw.monitoring_extended",
        "icsw.partition_table",
        "icsw.background_job_info",
    ]
)

ics_app.config(() ->
    console.log "go"
)

root.ics_app = ics_app

angular_module_setup([ics_app])

create_module = angular.module("icsw.monitoring.create", ["ngSanitize", "ui.bootstrap", "restangular"])

create_controller = create_module.controller("create_base", ["$scope", "$timeout", "$window", "$templateCache", "restDataSource", "$q",
    ($scope, $timeout, $window, $templateCache, restDataSource, $q) ->
        $scope.base_open = true
        $scope.resolve_pending = false
        $scope.device_data = {
            full_name        : ""
            comment          : "new device"
            device_group     : "newgroup"
            ip               : ""
            resolve_via_ip   : true
            routing_capable  : false
            peer             : 0
            icon_name        : "linux40"
        }
        $scope.peers = []
        $scope.rest_map = [
            {"short" : "device_group", "url" : "{% url 'rest:device_group_list' %}"}
            {"short" : "device_type", "url" : "{% url 'rest:device_type_list' %}"}
            {"short" : "mother_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_mother_servers" : true}}
            {"short" : "monitor_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"monitor_server_type" : true}}
            {"short" : "domain_tree_node", "url" : "{% url 'rest:domain_tree_node_list' %}"}
            {"short" : "peers", "url" : "{% url 'rest:netdevice_peer_list' %}" },
            {"short" : "mon_ext_host", "url" : "{% url 'rest:mon_ext_host_list' %}"}
        ]
        $scope.rest_data = {}
        $scope.all_peers = [{"idx" : 0, "info" : "no peering", "device group name" : "---"}]
        $scope.reload = () ->
            $.blockUI()
            wait_list = []
            for value, idx in $scope.rest_map
                $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
                wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                for value, idx in data
                    $scope.rest_data[$scope.rest_map[idx].short] = value
                # build image lut
                $scope.img_lut = {}
                for value in $scope.rest_data.mon_ext_host
                    $scope.img_lut[value.name] = value.data_image
                # create info strings
                for entry in $scope.rest_data.peers
                    entry.info = "#{entry.devname} on #{entry.device_name}"
                $scope.peers = (entry for entry in $scope.rest_data.peers when entry.routing)
                r_list = [{"idx" : 0, "info" : "no peering", "device group name" : "---"}]
                for entry in $scope.peers 
                    r_list.push(entry)
                $scope.all_peers = r_list
                $.unblockUI()
            )
        $scope.get_image_src = () ->
            img_url = ""
            if $scope.img_lut?
                if $scope.device_data.icon_name of $scope.img_lut
                    img_url = $scope.img_lut[$scope.device_data.icon_name]
            return img_url
        $scope.device_name_changed = () ->
            if not $scope.resolve_pending and $scope.device_data.full_name and not $scope.device_data.ip
                $scope.resolve_name()
        $scope.resolve_name = () ->
            # clear ip
            $scope.device_data.ip = ""
            $scope.resolve_pending = true
            call_ajax
                url  : "{% url 'mon:resolve_name' %}"
                data : {
                    "fqdn" : $scope.device_data.full_name
                }
                success : (xml) =>
                    $scope.$apply(
                        $scope.resolve_pending = false
                    )
                    if parse_xml_response(xml)
                        if $(xml).find("value[name='ip']").length and not $scope.device_data.ip
                            $scope.$apply(
                                $scope.device_data.ip = $(xml).find("value[name='ip']").text()
                            )
        $scope.device_groups = () ->
            return (entry.name for entry in $scope.rest_data.device_group when entry.cluster_device_group == false and entry.enabled)
        $scope.any_peers = () ->
            return if $scope.peers.length > 0 then true else false
        $scope.build_device_dict = () ->
            return {
                "full_name" : $scope.full_name
                "comment"   : $scope.comment
                "device_group" : $scope.device_group
                "ip"           : $scope.ip
            }
        $scope.create_device = () ->
            d_dict = $scope.device_data
            $.blockUI()
            call_ajax
                url  : "{% url 'mon:create_device' %}"
                data : {
                    "device_data" : angular.toJson(d_dict)
                }
                success : (xml) =>
                    parse_xml_response(xml)
                    reload_sidebar_tree()
                    $.unblockUI()
                    $scope.reload()
        $scope.reload()

]).controller("form_ctrl", ["$scope",
    ($scope) ->
])

{% endinlinecoffeescript %}

</script>
