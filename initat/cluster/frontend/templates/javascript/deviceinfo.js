{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

class device_info
    constructor: (@event, @dev_key, @addon_devices=[]) ->
    show: () =>
        @replace_div = {% if index_view %}true{% else %}false{% endif %}
        $.ajax
            url     : "{% url 'rest:device_detail' 1 %}".slice(0, -2) + "?pk=#{@dev_key}"
            method  : "GET"
            dataType  : "json"
            success : (json) =>
                @dev_json = json[0]
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
                            $.simplemodal.close()
                @dev_div.find("a[href='#general']").trigger("click")
    get_pk_list: (with_md=true) =>
        # get all pks
        return [@dev_json.idx].concat(@addon_devices)
    has_perm: (perm_name) =>
        return if @permissions.find("permissions[permission='#{perm_name}']").length then true else false 
    build_div: () =>
        if @addon_devices.length
            num_devs = @addon_devices.length + 1
            addon_text = " (#{num_devs})"
        else
            addon_text = ""
        main_pk = @dev_json.idx
        pk_list = @get_pk_list().join(",")
        dis_modal = if @replace_div then 0 else 1
        dev_div = $("""
<div class="panel panel-default">
    <div class="panel-heading">
        <ul class='nav nav-tabs' id="info_tab">
            <li><a href='#general'>General</a></li>
            <li><a href='#category'>Category</a></li>
            <li><a href='#location'>Location</a></li>
            <li><a href='#network'>Network#{addon_text}</a></li>
            <li><a href='#config'>Config#{addon_text}</a></li>
            <li><a href='#disk'>Disk#{addon_text}</a></li>
            <li><a href='#livestatus'>Livestatus#{addon_text}</a></li>
            <li><a href='#monconfig'>MonConfig#{addon_text}</a></li>
            <li><a href='#rrd'>Graphs#{addon_text}</a></li>
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
                        <devicecategory devicepk='#{main_pk}'>
                            <tree treeconfig="cat_tree"></tree>
                        </devicecategory>
                    </div>
                </div>
            </div>
            <div class="tab-pane" id="location">
                <div id="icsw.device.config">
                    <div ng-controller="location_ctrl">
                        <devicelocation devicepk='#{main_pk}'>
                            <tree treeconfig="loc_tree"></tree>
                        </devicelocation>
                    </div>
                </div>
            </div>
            <div class="tab-pane" id="network">
                <div id='icsw.network.device'>
                    <div ng-controller='network_ctrl'>
                        <devicenetworks devicepk='#{pk_list}' disablemodal='#{dis_modal}'>
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
                    {% if settings.INIT_PRODUCT_NAME = 'Corvus' %}
                    <div ng-controller='config_vars_ctrl'>
                        <deviceconfigvars devicepk='#{pk_list}'>
                        </deviceconfigvars>
                    </div>
                    {% endif %}
                </div>
            </div>
            <div class="tab-pane" id="livestatus">
                <div id='icsw.device.livestatus'>
                    <div ng-controller='livestatus_ctrl'>
                        <livestatus devicepk='#{pk_list}'>
                        </livestatus>
                    </div>
                </div>
            </div>
            <div class="tab-pane" id="monconfig">
                <div id='icsw.device.livestatus'>
                    <div ng-controller='monconfig_ctrl'>
                        <monconfig devicepk='#{pk_list}'>
                        </monconfig>
                    </div>
                </div>
            </div>
            <div class="tab-pane" id="rrd">
                <div id='icsw.device.rrd'>
                    <div ng-controller='rrd_ctrl'>
                        <rrdgraph devicepk='#{pk_list}'>
                        </rrdgraph>
                    </div>
                </div>
            </div>
            <div class="tab-pane" id="disk">
                <div id='icsw.device.config'>
                    <div ng-controller='partinfo_ctrl'>
                        <partinfo devicepk='#{pk_list}'>
                        </partinfo>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
            """)
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
                el.tab("show")
        )
    
root.device_info = device_info

{% endinlinecoffeescript %}

</script>

