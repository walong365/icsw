{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

dev_info_template = """
<tabset>
    <tab>
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
    <tab>
        <tab-heading>
            Category{{ addon_text_nmd }}
        </tab-heading>
        <div class="panel panel-default"><div class="panel-body">
            <div ng-controller="category_ctrl">
                <devicecategory devicepk="{{ pk_list_nmd }}">
                    <tree treeconfig="cat_tree"></tree>
                </devicecategory>
            </div>
        </div></div>
    </tab>
</tabset>
"""

{% endverbatim %}

device_info_module = angular.module(
    "icsw.device.info",
    ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools"]
).controller("device_info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$window", "msgbus"
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $window, msgbus) ->
        console.log "c", $window.ICSW_DEV_INFO
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
            $scope.dev_pk_nmd_list = args[3]
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
            console.log "show=", $scope.show
            #new_scope = $compile(info_template)($scope)
            #console.log new_scope
]).directive("deviceoverview", ($compile) ->
    return {
        restrict: "EA"
        replace: true
        compile: (element, attrs) ->
            console.log "comp", element, attrs
            return (scope, iElement, iAttrs) ->
                scope.$watch("dev_json", (new_val) ->
                    console.log "nv", new_val
                    if new_val
                        scope.devicepk = new_val[0].idx
                        console.log scope.devicepk
                        new_el = $compile(dev_info_template)
                        iElement.children().remove()
                        iElement.append(new_el(scope))
                )
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
        main_part = "<div class='panel-body'><div class='tab-content'>"
        dev_div_txt = """
<div class="panel panel-default">
    <div class="panel-heading">
        <ul class='nav nav-tabs' id="info_tab">
            <li><a href='#general'>General</a></li>
"""
        main_part += """
<div class="tab-pane" id="general">
    <div id="icsw.device.config">
        <div ng-controller="deviceinfo_ctrl">
            <deviceinfo devicepk='#{main_pk}'>
            </deviceinfo>
            {% verbatim %}
            <div ng-show="show_uuid">
                <h4>Copy the following snippet to /etc/sysconfig/cluster/.cluster_device_uuid :</h4>
                <pre>
urn:uuid:{{ _edit_obj.uuid }}
                </pre>
                <h4>and restart host-monitoring .</h4>
            </div>
            {% endverbatim %}
        </div>
    </div>
</div>"""
        if pk_list_nmd.length
            if @has_perm("backbone.device.change_category", 0)
                dev_div_txt += "<li><a href='#category'>Category#{addon_text_nmd}</a></li>"
                main_part += """
<div class="tab-pane" id="category">
    <div id="icsw.device.config">
        <div ng-controller="category_ctrl">
            <devicecategory devicepk='#{pk_list_nmd}'>
                <tree treeconfig="cat_tree"></tree>
            </devicecategory>
        </div>
    </div>
</div>
"""
            if @has_perm("backbone.device.change_location", 0)
                dev_div_txt += "<li><a href='#location'>Location#{addon_text_nmd}</a></li>"
                main_part += """
<div class="tab-pane" id="location">
    <div id="icsw.device.config">
        <div ng-controller="location_ctrl">
            <devicelocation devicepk='#{pk_list_nmd}'>
            </devicelocation>
        </div>
    </div>
</div>
"""
            if @has_perm("backbone.device.change_network", 0)
                dev_div_txt += "<li><a href='#di_network'>Network#{addon_text_nmd}</a></li>"
                main_part += """
<div class="tab-pane" id="di_network">
    <div id='icsw.network.device'>
        <div ng-controller='network_ctrl'>
            <devicenetworks devicepk='#{pk_list_nmd}' disablemodal='#{dis_modal}'>
            </devicenetworks>
        </div>
    </div>
</div>
"""
        if @has_perm("backbone.device.change_config", 0)
            dev_div_txt += "<li><a href='#config'>Config#{addon_text}</a></li>"
            main_part += """
<div class="tab-pane" id="config">
    <div id='icsw.device.config'>
        <div ng-controller='config_ctrl'>
            <deviceconfig devicepk='#{pk_list}'>
            </deviceconfig>
        </div>
"""
            if window.INIT_PRODUCT_NAME.toLowerCase() == "corvus"
                main_part += """
<div ng-controller='config_vars_ctrl'>
    <deviceconfigvars devicepk='#{pk_list}'>
    </deviceconfigvars>
</div>
"""
            main_part += "</div></div>"
        if pk_list_nmd.length and @has_perm("backbone.device.change_disk", 0)
            dev_div_txt += "<li><a href='#disk'>Disk#{addon_text_nmd}</a></li>"
            main_part += """
<div class="tab-pane" id="disk">
    <div id='icsw.device.config'>
        <div ng-controller='partinfo_ctrl'>
            <partinfo devicepk='#{pk_list_nmd}'>
            </partinfo>
        </div>
    </div>
</div>
"""
        if @has_perm("backbone.device.change_variables", 0)
            dev_div_txt += "<li><a href='#vars'>Vars#{addon_text}</a></li>"
            main_part += """
<div class="tab-pane" id="vars">
    <div id='icsw.device.variables'>
        <div ng-controller='dv_base'>
            <devicevars devicepk='#{pk_list}' disablemodal='#{dis_modal}'></devicevars>
        </div>
    </div>
</div>
"""

        dev_div_txt += "<li><a href='#status_history'>Status History#{addon_text}</a></li>"
        main_part += """
<div class="tab-pane" id="status_history">
    <div id='icsw.device.status_history'>
        <div ng-controller='status_history_ctrl'>
            <statushistory devicepks='#{pk_list}'>
            </statushistory>
        </div>
    </div>
</div>
"""

        if pk_list_nmd.length
            if window.SERVICE_TYPES["md-config"]? and @has_perm("backbone.device.change_monitoring", 0)
                dev_div_txt += "<li><a href='#livestatus'>Livestatus#{addon_text_nmd}</a></li><li><a href='#monconfig'>MonConfig/hint#{addon_text_nmd}</a></li>"
                main_part += """
<div class="tab-pane" id="livestatus">
    <div id='icsw.device.livestatus'>
        <div ng-controller='livestatus_ctrl'>
            <livestatus devicepk='#{pk_list_nmd}'>
            </livestatus>
        </div>
    </div>
</div>
<div class="tab-pane" id="monconfig">
    <div id='icsw.device.livestatus'>
        <div ng-controller='monconfig_ctrl'>
            <monconfig devicepk='#{pk_list_nmd}'>
            </monconfig>
        </div>
    </div>
</div>
"""
        if window.SERVICE_TYPES["grapher"]? and @has_perm("backbone.device.show_graphs", 0)
            dev_div_txt += "<li><a href='#rrd'>Graphs#{addon_text}</a></li>"
            main_part += """
<div class="tab-pane" id="rrd">
    <div id='icsw.device.rrd'>
        <div ng-controller='rrd_ctrl'>
            <rrdgraph devicepk='#{pk_list}'>
            </rrdgraph>
        </div>
    </div>
</div>
"""

        dev_div_txt += "</ul></div>"
        main_part += "</div></div>"
        dev_div_txt += main_part + "</div>"
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
