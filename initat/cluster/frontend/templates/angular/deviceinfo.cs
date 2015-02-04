{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

dev_info_template = """
<tabset>
    <tab select="activate('general')" active="general_active">
        <tab-heading>
            General
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="deviceinfo_ctrl">
                <deviceinfo devicepk='devicepk'>
                </deviceinfo>
                <div ng-show="show_uuid">
                    <h4>Copy the following snippet to /etc/sysconfig/cluster/.cluster_device_uuid :</h4>
                    <pre>urn:uuid:{{ _edit_obj.uuid }}</pre>
                    <h4>and restart host-monitoring .</h4>
                </div>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_category') && dev_pk_nmd_list.length" select="activate('category')" active="category_active">
        <tab-heading>
            Category{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="category_ctrl">
                <devicecategory devicepk="pk_list['category']">
                    <tree treeconfig="cat_tree"></tree>
                </devicecategory>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_location') && dev_pk_nmd_list.length" select="activate('location')" active="location_active">
        <tab-heading>
            Location{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="location_ctrl">
                <devicelocation devicepk="pk_list['location']">
                </devicelocation>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_network') && dev_pk_nmd_list.length" select="activate('network')" active="network_active">
        <tab-heading>
            Network{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="network_ctrl">
                <devicenetworks devicepk="pk_list['network']" disablemodal="true">
                </devicenetworks>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_config')" select="activate('config')" active="config_active">
        <tab-heading>
            Config{{ addon_text }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="config_ctrl">
                <deviceconfig devicepk="pk_list['config']">
                </deviceconfig>
            </div>
            <!-- only valid for corvus -->
            <div ng-controller='config_vars_ctrl'>
                <deviceconfigvars devicepk='pk_list_config'>
                </deviceconfigvars>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_disk') && dev_pk_nmd_list.length" select="activate('partinfo')" active="partinfo_active">
        <tab-heading>
            Disk{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="partinfo_ctrl">
                <partinfo devicepk="pk_list['partinfo']">
                </partinfo>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_variables')" select="activate('variables')" active="variables_active">
        <tab-heading>
            Vars{{ addon_text }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="dv_base">
                <devicevars devicepk="pk_list['variables']" disablemodal="true">
                </devicevars>
            </div>
        </div></div>
    </tab>
    <tab select="activate('status_history')" active="status_history_active">
        <tab-heading>
            Status History
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="status_history_ctrl">
                <statushistory devicepks="pk_list['status_history']">
                </statushistory>
            </div>
        </div></div>
    </tab>
    <!-- also check for md-config-server in service list -->
    <tab ng-if="acl_read(null, 'backbone.device.change_monitoring') && dev_pk_nmd_list.length" select="activate('livestatus')" active="livestatus_active">
        <tab-heading>
            Livestatus{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="livestatus_ctrl">
                <livestatus devicepk="pk_list['livestatus']">
                </livestatus>
            </div>
        </div></div>
    </tab>
    <tab ng-if="acl_read(null, 'backbone.device.change_monitoring') && dev_pk_nmd_list.length" select="activate('monconfig')" active="monconfig_active">
        <tab-heading>
            MonConfig/hint{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="monconfig_ctrl">
                <monconfig devicepk="pk_list['monconfig']">
                </monconfig>
            </div>
        </div></div>
    </tab>
    <!-- also check for grapher in service list -->
    <tab ng-if="acl_read(null, 'backbone.device.show_graphs')" select="activate('graphing')" active="graphing_active">
        <tab-heading>
            Graph{{ addon_text }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="icswGraphOverviewCtrl">
                <icsw-rrd-graph devicepk="pk_list['graphing']" disablemodal="true">
                </icsw-rrd-graph>
            </div>
        </div></div>
    </tab>
</tabset>
"""

{% endverbatim %}

device_info_module = angular.module(
    "icsw.device.info",
    ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools"]
).controller("device_info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$window", "msgbus", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $window, msgbus, access_level_service) ->
        access_level_service.install($scope)
        $scope.active_div = "general"
        $scope.show = false
        $scope.permissions = undefined
        $scope.devicepk = undefined
        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.dev_pk_list = args[0]
            $scope.dev_pk_nmd_list = args[1]
            $scope.devg_pk_list = args[2]
            $scope.dev_pk_md_list = args[3]
            $scope.addon_devices = []
            if $scope.dev_pk_list.length
                $scope.show = true
                $scope.fetch_info()
            else
                $scope.show = false
        )
        $scope.fetch_info = () ->
            wait_list = [
                Restangular.one("{% url 'rest:device_detail' 1 %}".slice(1).slice(0, -2), $scope.dev_pk_list[0]).get()
                Restangular.one("{% url 'rest:min_access_levels' %}".slice(1)).get( {"obj_type": "device", "obj_list": angular.toJson($scope.dev_pk_list)})
            ]
            # access levels needed ?
            $q.all(wait_list).then((data) ->
                $scope.show_div(data[0], data[1])
            )
        $scope.show_div = (json, access_json) ->
            $scope.devicepk = json.idx
            $scope.permissions = access_json
            $scope.show = true
]).service("DeviceOverviewService", (Restangular, $rootScope, $templateCache, $compile, $modal, $q, access_level_service, msgbus) ->
    return {
        "NewSingleSelection" : (dev) ->
            if dev.device_type_identifier == "MD"
                msgbus.emit("devicelist", [[dev.idx], [], [], [dev.idx]])
            else
                msgbus.emit("devicelist", [[dev.idx], [dev.idx], [], []])
        "NewOverview" : (event, dev) ->
            # create new modal for device
            # device object with access_levels
            sub_scope = $rootScope.$new()
            access_level_service.install(sub_scope)
            dev_idx = dev.idx
            sub_scope.devicepk = dev_idx
            sub_scope.disable_modal = true
            if dev.device_type_identifier == "MD"
                sub_scope.dev_pk_list = [dev_idx]
                sub_scope.dev_pk_nmd_list = []
            else
                sub_scope.dev_pk_list = [dev_idx]
                sub_scope.dev_pk_nmd_list = [dev_idx]
            my_mixin = new angular_modal_mixin(
                sub_scope,
                $templateCache,
                $compile
                $modal
                Restangular
                $q
            )
            my_mixin.min_width = "800px"
            my_mixin.template = "DeviceOverviewTemplate"
            my_mixin.edit(null, dev_idx)
            # todo: destroy sub_scope
    }
).run(($templateCache) ->
    $templateCache.put(
        "DeviceOverviewTemplate",
        "<deviceoverview devicepk='devicepk'></deviceoverview>"
    )
).service("DeviceOverviewSettings", [() ->
    def_mode = ""
    return {
        "get_mode" : () ->
            return def_mode
        "set_mode": (mode) ->
            def_mode = mode
    }
]).directive("deviceoverview", ($compile, DeviceOverviewSettings) ->
    return {
        restrict: "EA"
        replace: true
        compile: (element, attrs) ->
            return (scope, iElement, iAttrs) ->
                scope.current_subscope = undefined
                scope.pk_list = {
                    "category": []
                    "location": []
                    "network": []
                    "config": []
                    "partinfo": []
                    "variables": []
                    "status_history": []
                    "livestatus": []
                    "monconfig": []
                    "graphing": []
                }
                scope["general_active"] = true
                for key of scope.pk_list
                    scope["#{key}_active"] = false
                scope.active_div = DeviceOverviewSettings.get_mode()
                if scope.active_div
                    scope["#{scope.active_div}_active"] = true
                if attrs["multi"]?
                    # possibly multi-device view
                    scope.multi_device = true
                    scope.$watch("dev_pk_list", (new_val) ->
                        if new_val and new_val.length
                            scope.devicepk = new_val[0]
                            scope.new_device_sel()
                    )
                else
                    scope.multi_device = false
                    scope.$watch(attrs["devicepk"], (new_val) ->
                        if new_val
                            scope.devicepk = new_val
                            scope.new_device_sel()
                    )
                scope.new_device_sel = () ->
                    if scope.dev_pk_list.length > 1
                        scope.addon_text = " (#{scope.dev_pk_list.length})"
                    else
                        scope.addon_text = ""
                    if scope.dev_pk_nmd_list.length > 1
                        scope.addon_text_nmd = " (#{scope.dev_pk_nmd_list.length})"
                    else
                        scope.addon_text_nmd = ""
                    # destroy old subscope, important
                    if scope.current_subscope
                        scope.current_subscope.$destroy()
                    new_scope = scope.$new()
                    new_el = $compile(dev_info_template)(new_scope)
                    iElement.children().remove()
                    iElement.append(new_el)
                    scope.current_subscope = new_scope
                scope.activate = (name) ->
                    DeviceOverviewSettings.set_mode(name)
                    if name in ["category", "location", "network", "partinfo", "status_history", "livestatus", "monconfig"]
                        scope.pk_list[name] = scope.dev_pk_nmd_list
                    else if name in ["config", "variables", "graphing"]
                        scope.pk_list[name] = scope.dev_pk_list
    }
)

{% endinlinecoffeescript %}

</script>
