{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

class device_info
    constructor: (@event, @dev_key, @addon_devices=[], @md_list=[]) ->
        if window.ICSW_DEV_INFO
            window.ICSW_DEV_INFO.close()
            @active_div = window.ICSW_DEV_INFO.active_div
        else
            @active_div = "general"
        window.ICSW_DEV_INFO = @
        @active_divs = []
    show: () =>
        @replace_div = {% if index_view %}true{% else %}false{% endif %}
        call_ajax
            url     : "{% url 'rest:device_detail' 1 %}".slice(0, -2) + "?pk=#{@dev_key}"
            method  : "GET"
            dataType  : "json"
            success : (json) =>
                @dev_json = json[0]
                if @dev_json.device_type_identifier == "MD" and @dev_key not in @md_list
                    @md_list.push(@dev_key)
                @permissions = []
                @build_div()
                if @replace_div
                    $("div#center_deviceinfo").children().remove().end().append(@dev_div)
                else
                    @dev_div.simplemodal
                        opacity      : 50
                        position     : [@event.pageY, @event.pageX]
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
                @dev_div.find("a[href='##{@active_div}']").trigger("click")
    close: () =>
        # find all scopes and close them
        for active_div in @active_divs
            $(active_div).find(".ng-scope").scope().$destroy()
        @active_divs = []
    has_perm: (perm_name) =>
        return if @permissions.find("permissions[permission='#{perm_name}']").length then true else false
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
        dev_div_txt = """
<div class="panel panel-default">
    <div class="panel-heading">
        <ul class='nav nav-tabs' id="info_tab">
            <li><a href='#general'>General</a></li>
"""
        if pk_list_nmd.length
            dev_div_txt += """
<li><a href='#category'>Category#{addon_text_nmd}</a></li>
<li><a href='#location'>Location#{addon_text_nmd}</a></li>
<li><a href='#di_network'>Network#{addon_text_nmd}</a></li>
"""
        dev_div_txt += """
<li><a href='#config'>Config#{addon_text}</a></li>
"""
        if pk_list_nmd.length
            dev_div_txt += """
<li><a href='#disk'>Disk#{addon_text_nmd}</a></li>
"""
        dev_div_txt += """ 
<li><a href='#vars'>Vars#{addon_text}</a></li>
"""
        if pk_list_nmd.length
            if window.SERVICE_TYPES["md-config"]?
                dev_div_txt += """            
<li><a href='#livestatus'>Livestatus#{addon_text_nmd}</a></li>
<li><a href='#monconfig'>MonConfig#{addon_text_nmd}</a></li>
<li><a href='#monhint'>MonHint#{addon_text_nmd}</a></li>
"""
            if window.SERVICE_TYPES["grapher"]?
                dev_div_txt += """            
<li><a href='#rrd'>Graphs#{addon_text_nmd}</a></li>
"""
        dev_div_txt += """
        </ul>
    </div>
<div class="panel-body">
    <div class="tab-content">
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
</div>
<div class="tab-pane" id="category">
    <div id="icsw.device.config">
        <div ng-controller="category_ctrl">
            <devicecategory devicepk='#{pk_list_nmd}'>
                <tree treeconfig="cat_tree"></tree>
            </devicecategory>
        </div>
    </div>
</div>
<div class="tab-pane" id="location">
    <div id="icsw.device.config">
        <div ng-controller="location_ctrl">
            <devicelocation devicepk='#{pk_list_nmd}'>
                <tree treeconfig="loc_tree"></tree>
            </devicelocation>
        </div>
    </div>
</div>
<div class="tab-pane" id="di_network">
    <div id='icsw.network.device'>
        <div ng-controller='network_ctrl'>
            <devicenetworks devicepk='#{pk_list_nmd}' disablemodal='#{dis_modal}'>
            </devicenetworks>
        </div>
    </div>
</div>
<div class="tab-pane" id="config">
    <div id='icsw.device.config'>
        <div ng-controller='config_ctrl'>
            <deviceconfig devicepk='#{pk_list}'>
            </deviceconfig>
        </div>
"""
        if window.INIT_PRODUCT_NAME.toLowerCase() == "corvus"
            dev_div_txt += """
<div ng-controller='config_vars_ctrl'>
    <deviceconfigvars devicepk='#{pk_list}'>
    </deviceconfigvars>
</div>
"""
        dev_div_txt += """
    </div>
</div>
<div class="tab-pane" id="vars">
    <div id='icsw.device.variables'>
        <div ng-controller='dv_base'>
            <devicevars devicepk='#{pk_list}' disablemodal='#{dis_modal}'></devicevars>
        </div>
    </div>
</div>
<div class="tab-pane" id="disk">
    <div id='icsw.device.config'>
        <div ng-controller='partinfo_ctrl'>
            <partinfo devicepk='#{pk_list_nmd}'>
            </partinfo>
        </div>
    </div>
</div>
"""
        if window.SERVICE_TYPES["md-config"]?
            dev_div_txt += """
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
<div class="tab-pane" id="monhint">
    <div id='icsw.device.config'>
        <div ng-controller='monitoring_hint_ctrl'>
            <monitoringhint devicepk='#{pk_list_nmd}'>
            </monitoringhint>
        </div>
    </div>
</div>
"""
        if window.SERVICE_TYPES["grapher"]?
            dev_div_txt += """
<div class="tab-pane" id="rrd">
    <div id='icsw.device.rrd'>
        <div ng-controller='rrd_ctrl'>
            <rrdgraph devicepk='#{pk_list_nmd}'>
            </rrdgraph>
        </div>
    </div>
</div>
"""
        dev_div_txt += """
        </div>
    </div>
</div>
            """
        dev_div = $(dev_div_txt)
        # if @has_perm("change_network")
        # if @has_perm("show_graphs")
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
                    angular.bootstrap(target_div, [target_div.attr("id")])
                    @active_divs.push(target_div[0])
                # store active div
                @active_div = t_href
                el.tab("show")
        )
    
root.device_info = device_info

{% endinlinecoffeescript %}

</script>

