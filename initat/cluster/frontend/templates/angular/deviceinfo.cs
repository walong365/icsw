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
                <deviceinfo devicepk='{{ devicepk }}'>
                </deviceinfo>
                <div ng-show="show_uuid">
                    <h4>Copy the following snippet to /etc/sysconfig/cluster/.cluster_device_uuid :</h4>
                    <pre>
    urn:uuid:{{ _edit_obj.uuid }}
                    </pre>
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
        $scope.dev_json = undefined
        $scope.permissions = undefined
        #@replace_div = {% if index_view %}true{% else %}false{% endif %}
        msgbus.receive("devicelist", $scope, (name, args) ->
            dev_list = args[0]
            $scope.dev_pk_list = dev_list
            $scope.dev_pk_nmd_list = args[1]
            $scope.devg_pk_list = args[2]
            $scope.dev_pk_md_list = args[3]
            $scope.addon_text = " (4)"
            $scope.addon_text_nmd = " (1)"
            $scope.addon_devices = []
            if dev_list
                $scope.show = true
                $scope.fetch_info()
            else
                $scope.show = false
        )
        $scope.fetch_info = () ->
            call_ajax
                url     : "{% url 'rest:device_detail' 1 %}".slice(0, -2) + "?pk=#{$scope.dev_pk_list[0]}"
                method  : "GET"
                dataType  : "json"
                success : (json) =>
                    if $scope.addon_devices
                        # multi-device view, get minimum access levels
                        all_devs = (entry for entry in $scope.addon_devices)
                        all_devs.push($scope.dev_pk_list[0])
                        call_ajax
                            url     : "{% url 'rest:min_access_levels' %}"
                            method  : "GET"
                            data:
                                obj_type: "device"
                                obj_list: angular.toJson(all_devs)
                            dataType  : "json"
                            success: (access_json) =>
                                $scope.$apply(
                                    $scope.show_div(json, access_json)
                                )
                    else
                        $scope.$apply(
                            $scope.show_div(json, access_json)
                        )
        $scope.show_div = (json, access_json) ->
            $scope.dev_json = json
            $scope.permissions = access_json
            $scope.show = true
            #new_scope = $compile(info_template)($scope)
            #console.log new_scope
]).directive("deviceoverview", ($compile) ->
    return {
        restrict: "EA"
        replace: true
        compile: (element, attrs) ->
            return (scope, iElement, iAttrs) ->
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
                scope.$watch("dev_json", (new_val) ->
                    if new_val
                        scope.devicepk = new_val[0].idx
                        new_el = $compile(dev_info_template)
                        iElement.children().remove()
                        iElement.append(new_el(scope))
                )
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
        if @addon_devices.length
            addon_text = " (#{@addon_devices.length + 1})"
        else
            addon_text = ""
        if pk_list_nmd.length > 1
            addon_text_nmd = " (#{pk_list_nmd.length})"
        else
            addon_text_nmd = ""
        dev_div = $(dev_div_txt)
        @dev_div = dev_div
        @tabs_init = {}
        dev_div.find("a").click(
            (event) =>
                event.preventDefault()
                el = $(event.target)
                t_href = el.attr("href").slice(1)
                if not @tabs_init[t_href]?
                    # set init flag
                    @tabs_init[t_href] = true
                    # get target div
                    target_div = @dev_div.find("div[class='tab-pane'][id='#{t_href}'] > div[id^='icsw']")
                    # bootstrap angular (app == id of device)
                    #angular.bootstrap(target_div, [target_div.attr("id")])
                    @active_divs.push(target_div[0])
                # store active div
                @active_div = t_href
                el.tab("show")
        )
    
root.device_info = device_info

{% endinlinecoffeescript %}

</script>
