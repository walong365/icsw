{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

dev_info_template = """
<tabset>
    <tab select="activate('general')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_category') && dev_pk_nmd_list.length" select="activate('category')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_location') && dev_pk_nmd_list.length" select="activate('location')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_network') && dev_pk_nmd_list.length" select="activate('network')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_config')" select="activate('config')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_disk') && dev_pk_nmd_list.length" select="activate('partinfo')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_variables')" select="activate('variables')">
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
    <tab select="activate('status_history')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_monitoring') && dev_pk_nmd_list.length" select="activate('livestatus')">
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
    <tab ng-if="acl_read(null, 'backbone.device.change_monitoring') && dev_pk_nmd_list.length" select="activate('monconfig')">
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
    <tab ng-if="acl_read(null, 'backbone.device.show_graphs')" select="activate('graphing')">
        <tab-heading>
            Graph{{ addon_text }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="rrd_ctrl">
                <rrdgraph devicepk="pk_list['graphing']" disablemodal="true">
                </rrdgraph>
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
        console.log "c", $window.ICSW_DEV_INFO
        access_level_service.install($scope)
        $scope.active_div = "general"
        $scope.show = false
        $scope.permissions = undefined
        $scope.devicepk = undefined
        #@replace_div = {% if index_view %}true{% else %}false{% endif %}
        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            console.log "new_devl"
            $scope.dev_pk_list = args[0]
            $scope.dev_pk_nmd_list = args[1]
            console.log "->", $scope.dev_pk_list, $scope.dev_pk_nmd_list
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
            console.log dev
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
).directive("deviceoverview", ($compile) ->
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
                            console.log "nv", new_val
                            scope.devicepk = new_val
                            scope.new_device_sel()
                    )
                console.log scope.multi_device
                scope.new_device_sel = () ->
                    console.log "*********SEL"
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
                        console.log "destroy"
                        scope.current_subscope.$destroy()
                    console.log " new overview"
                    new_scope = scope.$new()
                    new_el = $compile(dev_info_template)(new_scope)
                    iElement.children().remove()
                    iElement.append(new_el)
                    scope.current_subscope = new_scope
                scope.activate = (name) ->
                    if name in ["category", "location", "network", "partinfo", "status_history", "livestatus", "monconfig"]
                        scope.pk_list[name] = scope.dev_pk_nmd_list
                    else if name in ["config", "variables", "graphing"]
                        scope.pk_list[name] = scope.dev_pk_list
    }
)

class device_info
    constructor: (@event, @dev_key, @addon_devices=[], @md_list=[], default_mode="") ->
        if window.ICSW_DEV_INFO
            window.ICSW_DEV_INFO.close()
            @active_div = window.ICSW_DEV_INFO.active_div
        else
            if default_mode
                @active_div = default_mode
            else
                @active_div = "general"
        window.ICSW_DEV_INFO = @
        @active_divs = []
    show: () =>
        return
        @replace_div = {% if index_view %}true{% else %}false{% endif %}
        call_ajax
            url     : "{% url 'rest:device_detail' 1 %}".slice(0, -2) + "?pk=#{@dev_key}"
            method  : "GET"
            dataType  : "json"
            success : (json) =>
                if @addon_devices
                    # multi-device view, get minimum access levels
                    all_devs = (entry for entry in @addon_devices)
                    all_devs.push(@dev_key)
                    call_ajax
                        url     : "{% url 'rest:min_access_levels' %}"
                        method  : "GET"
                        data:
                            obj_type: "device"
                            obj_list: angular.toJson(all_devs)
                        dataType  : "json"
                        success: (access_json) =>
                            @show_div(json, access_json)
                else
                    @show_div(json, json[0].access_levels)
    show_div: (json, access_json) =>
        @dev_json = json[0]
        # set permissions
        @permissions = access_json
        if @dev_json.device_type_identifier == "MD" and @dev_key not in @md_list
            @md_list.push(@dev_key)
        @build_div()
        if @replace_div
            #$("div#center_deviceinfo"). children().remove().end().append(@dev_div)
            _index_scope = angular.element($("div[id='icsw.index_app']")[0]).scope()
            $("div#center_deviceinfo"). children().remove().end().append(@dev_div)
        else
            @dev_div.simplemodal
                opacity      : 50
                position     : [@event.clientY - 50, @event.clientX - 50]
                autoResize   : true
                autoPosition : true
                minWidth     : "800px"
                onShow: (dialog) -> 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                    $("#simplemodal-container").css("width", "auto")
                onClose: =>
                    # destroy scopes
                    @close()
                    $.simplemodal.close()
        _active_div = @dev_div.find("a[href='##{@active_div}']")
        if not _active_div.length
            @active_div = "general"
            _active_div = @dev_div.find("a[href='##{@active_div}']")
        _active_div.trigger("click")
    close: () =>
        # find all scopes and close them
        for active_div in @active_divs
            $(active_div).find(".ng-scope").scope().$destroy()
        @active_divs = []
    has_perm: (perm_name, min_perm) =>
        if @permissions[perm_name]?
            return if @permissions[perm_name] >= min_perm then 1 else 0
        else
            return 0
    build_div: () =>
        main_pk = @dev_json.idx
        # pks for all devices
        pk_list = [@dev_json.idx].concat(@addon_devices)
        # pks for devices which are no meta devices
        pk_list_nmd = (entry for entry in pk_list when entry not in @md_list)
        dis_modal = if @replace_div then 0 else 1
        dev_div = $(dev_div_txt)
        @dev_div = dev_div
    
{% endinlinecoffeescript %}

</script>
