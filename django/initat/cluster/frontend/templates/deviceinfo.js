{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

beautify_seconds = (in_sec) ->
    if in_sec > 60
        mins = parseInt(in_sec / 60)
        return  "#{mins}:#{in_sec - 60 * mins}" 
    else
        return "#{in_sec} s"
        
class category_tree
    constructor: (@tree_div, @top_xml, @xml, @cat_tree, @top_node, @multi_sel) ->
        @tree_div.dynatree
            autoFocus : false
            checkbox  : true
            clickFolderMode : 2
            #onExpand : (flag, dtnode) =>
            #    dtnode.toggleSelect()
            onClick : (dtnode, event) =>
                #console.log dtnode.data.key, event.type
                #dtnode.toggleSelect()
            onSelect : (flag, dtnode) =>
                if flag
                    # deactivate other locations
                    @tree_div.dynatree("getTree").visit(
                        (cur_node) =>
                            if cur_node.isSelected() and cur_node.data.key != dtnode.data.key and not @multi_sel
                                cur_node.toggleSelect()
                    )
                $.ajax
                    url     : "{% url 'base:change_category' %}"
                    data    :
                        "obj_key" : @xml.attr("key")
                        "cat_pk"  : dtnode.data.key
                        "flag"    : if flag then 1 else 0
                    success : (xml) =>
                        if parse_xml_response(xml)
                            if @top_xml
                              replace_xml_element(@top_xml, $(xml))
                #dtnode.toggleSelect()
        root_node = @tree_div.dynatree("getRoot")
        @select_cats = @xml.attr("categories").split("::")
        @build_node(root_node, @cat_tree.find("category[full_name='#{@top_node}']"))
    build_node: (dt_node, db_node) =>
        if parseInt(db_node.attr("parent")) == 0
            title_str = "TOP"
            expand_flag = true
        else
            title_str = db_node.attr("name") + " (" + db_node.attr("full_name") + ")"
            expand_flag = false
        selected = if db_node.attr("pk") in @select_cats then true else false
        new_node = dt_node.addChild(
            title        : title_str
            expand       : expand_flag
            key          : db_node.attr("pk")
            hideCheckbox : if (db_node.attr("full_name") == "#{@top_node}") then true else false
            select       : selected
        )
        if selected
            new_node.makeVisible()
        @cat_tree.find("category[parent='" + db_node.attr("pk") + "']").each (idx, sub_db_node) =>
            @build_node(new_node, $(sub_db_node))

class rrd_config
    constructor: (@top_div, @key_tree_div, @graph_div, @pk_list) ->
        @top_div.css("vertical-align", "middle")
        @init()
    init: () =>
        @filter_el = $("<input>").attr(
            "id"    : "rrd_filter"
            "title" : "filter"
        ).focus().on("keyup", @change_rrd_sel)
        clear_el = $("<input>").attr(
            "title"  : "clear filter"
            "type"   : "image"
            "src"    : "{{ MEDIA_URL }}frontend/images/delete.png"
            "width"  : "22px"
            "height" : "22px"
        ).on("click", @clear_rrd_sel)
        draw_el =  $("<input>").attr(
            "title"  : "draw graph(s)"
            "type"   : "image"
            "src"    : "{{ MEDIA_URL }}frontend/images/ok.png"
            "width"  : "22px"
            "height" : "22px"
        ).on("click", @draw_rrd_el)
        @rrd_from_field = $("<input>").attr(
            type : "text"
            id   : "rrd_from"
        )
        @rrd_to_field = $("<input>").attr(
            type : "text"
            id   : "rrd_to"
        )
        cur_date = @get_date()
        start_date = @get_date()
        start_date.setHours(cur_date.getHours() - 40)
        size_select =$("<select>").attr(
            "id"  : "rrd_size"
        ).on("change", @draw_rrd_el)
        for cur_size in ["400x200", "640x300", "800x350", "1024x400", "1280x450"]
            size_select.append(
                $("<option>").attr("value", cur_size).text(cur_size)
            )
        # default size
        size_select.val("640x300")
        # now field
        @now_field = $("<input>").attr(
            "type"  : "button"
            "value" : "now"
        ).on("click", @set_to_field)
        @CUR_FILTER = ""
        # back / forth arrows
        @tf_prev_arrow = $("<input>").attr(
            "title"  : "previous timeframe"
            "type"   : "image"
            "src"    : "{{ MEDIA_URL }}frontend/images/left-arrow.png"
            "width"  : "22px"
            "height" : "22px"
            "disabled" : "disabled"
        ).on("click", @prev_timeframe)
        @tf_next_arrow = $("<input>").attr(
            "title"  : "next timeframe"
            "type"   : "image"
            "src"    : "{{ MEDIA_URL }}frontend/images/right-arrow.png"
            "width"  : "22px"
            "height" : "22px"
            "disabled" : "disabled"
        ).on("click", @next_timeframe)
        @rrd_tf_info = $("<span>").attr("id", "num_rrd_timeframes") 
        @top_div.append(@filter_el, clear_el, draw_el, size_select, @rrd_from_field, @rrd_to_field, @now_field,
            @tf_prev_arrow, @rrd_tf_info, @tf_next_arrow
        )
        @rrd_timeframes = []
        @append_rrd_timeframe(undefined, cur_date, start_date, cur_date)
        @load_rrd_tree()
    get_date: () =>
        cur_date = new Date()
        cur_date.setSeconds(0)
        cur_date.setMilliseconds(0)
        return cur_date
    prev_timeframe: (event) =>
        if @rrd_tf_idx > 0
            @rrd_tf_idx--
            @init_rrd_from_to()
            @draw_rrd_el()
    next_timeframe: (event) =>
        if @rrd_tf_idx < @rrd_timeframes.length - 1
            @rrd_tf_idx++
            @init_rrd_from_to()
            @draw_rrd_el()
    append_rrd_timeframe: (min_dt, max_dt, start_dt, end_dt) =>
        if not min_dt
            min_dt = @get_date()
            min_dt.setFullYear(min_dt.getYear() - 10)
        new_tf = {"min" : min_dt, "max" : max_dt, "start" : start_dt, "end" : end_dt}
        console.log new_tf["start"]
        # check for change
        add_new = true
        if @rrd_timeframes.length
            last_tf = @rrd_timeframes[@rrd_timeframes.length - 1]
            if Math.abs(new_tf.min - last_tf.min) + Math.abs(new_tf.max - last_tf.max) + Math.abs(new_tf.start - last_tf.start) + Math.abs(new_tf.end - last_tf.end) == 0
                add_new = false
        else
            @rrd_tf_idx = 0
        if add_new
            @rrd_timeframes.push(new_tf)
            if @rrd_timeframes.length > 1
                @tf_prev_arrow.removeAttr("disabled")
                @tf_next_arrow.removeAttr("disabled")
            @rrd_tf_idx = @rrd_timeframes.length - 1
            @init_rrd_from_to()
    update_rrd_tf_info: () =>
        @rrd_tf_info.text((@rrd_tf_idx + 1) + " / " + (@rrd_timeframes.length))
    init_rrd_from_to: () =>
        @update_rrd_tf_info()
        idx = @rrd_tf_idx
        cur_tf = @rrd_timeframes[idx]
        min_date = cur_tf.min
        max_date = cur_tf.max
        from_date = cur_tf.start
        to_date = cur_tf.end
        @rrd_from_field.datetimepicker("destroy")
        @rrd_to_field.datetimepicker("destroy")
        @rrd_from_field.datetimepicker(
            minDate     : min_date
            maxDate     : to_date
            defaultDate : from_date
            hour        : from_date.getHours()
            minute      : from_date.getMinutes()
            changeMonth : true
            changeYear  : true
            gotoCurrent : true
            dateFormat  : "yy-mm-dd"
            onClose     : (sel_date) =>
                @rrd_to_field.datepicker("option", "minDate", sel_date)
                @update_rrd_timeframe()
        )
        @rrd_to_field.datetimepicker(
            minDate     : min_date
            maxDate     : to_date
            defaultDate : to_date
            hour        : to_date.getHours()
            minute      : to_date.getMinutes()
            changeMonth : true
            changeYear  : true
            dateFormat  : "yy-mm-dd"
            onClose     : (sel_date) =>
                @rrd_from_field.datepicker("option", "maxDate", sel_date)
                @update_rrd_timeframe()
        )
        @rrd_from_field.datetimepicker("setDate", from_date)
        @rrd_to_field.datetimepicker("setDate", to_date)
    set_to_field: (event) =>
        # fix for IE
        to_date = new Date(@rrd_from_field.val().replace(/-/g, "/"))
        cur_date = @get_date()
        @append_rrd_timeframe(undefined, cur_date, to_date, cur_date) 
    load_rrd_tree: () =>
        $.ajax
            url  : "{% url 'rrd:device_rrds' %}"
            data : {
                "pks" : @pk_list
            }
            success : (xml) =>
                if parse_xml_response(xml)
                    @vector = $(xml).find("machine_vector")
                    if @vector.length
                        @key_tree_div.dynatree
                            autoFocus : false
                            checkbox  : true
                            clickFolderMode : 2
                            #onExpand : (flag, dtnode) =>
                            #    dtnode.toggleSelect()
                            onClick : (dtnode, event) =>
                                if dtnode.data.key[0] != "_"
                                    sel_list = (entry.data.key for entry in @key_tree_div.dynatree("getSelectedNodes"))
                                    sel_list.push(dtnode.data.key)
                                    @draw_rrd(sel_list)
                        @build_rrd_node(@key_tree_div.dynatree("getRoot"), @vector)
                    else
                        @key_tree_div.append($("<h2>").text("No graphs found"))
    build_rrd_node: (dt_node, db_node) =>
        if db_node.prop("tagName") == "machine_vector"
            title_str = "vector"
            key         = ""
            expand_flag = true
            hide_cb     = true
            tooltip     = "Device vector"
        else if db_node.prop("tagName") == "entry"
            title_str   = db_node.attr("part")
            expand_flag = false
            key         = ""
            hide_cb     = true
            tooltip     = ""
        else
            title_str   = db_node.attr("info")
            expand_flag = false
            key         = db_node.attr("name")
            hide_cb     = false
            tooltip     = "key: " + db_node.attr("name")
        if db_node.attr("devices") and parseInt(db_node.attr("devices")) > 1
            title_str = "#{title_str} (" + db_node.attr("devices") + ")"
        new_node = dt_node.addChild(
            title        : title_str
            expand       : expand_flag
            key          : key
            hideCheckbox : hide_cb
            isFolder     : hide_cb
            tooltip      : tooltip
            #select       : selected
        )
        db_node.find("> *").each (idx, sub_node) =>
            @build_rrd_node(new_node, $(sub_node))
    update_rrd_timeframe: () =>
        @draw_rrd_el() 
    change_rrd_sel: (event) =>
        new_filter = $(event.target).val()
        if new_filter != @CUR_FILTER
            @CUR_FILTER = new_filter
            cur_re = new RegExp(@CUR_FILTER)
            @key_tree_div.dynatree("getRoot").visit(
                (node) ->
                    if node.data.title.match(cur_re) or node.data.key.match(cur_re)
                        node.makeVisible(true)
                        node.select(true)
                    else
                        node.select(false)
                        node.expand(false)
            )
    clear_rrd_sel: (event) =>
        @filter_el.val("")
        @CUR_FILTER = ""
        @key_tree_div.dynatree("getRoot").visit(
            (node) ->
                node.select(false)
                if node.getLevel() < 2
                    node.expand(true)
                else                        
                    node.expand(false)
        )
    draw_rrd_el: (event) =>
        sel_list = (entry.data.key for entry in @key_tree_div.dynatree("getSelectedNodes"))
        @draw_rrd(sel_list)
    crop_select: (selection) =>
        # calculate new time
        # offsets
        gt_left  = parseInt(@cur_graph.attr("graph_left"))
        gt_right = parseInt(@cur_graph.attr("graph_right"))
        # width / height
        img_width  = parseInt(@cur_graph.attr("graph_width"))
        img_height = parseInt(@cur_graph.attr("graph_height"))
        # times
        gt_start = parseInt(@cur_graph.attr("graph_start"))
        gt_end   = parseInt(@cur_graph.attr("graph_end"))
        new_gt_start = parseInt(gt_start + (gt_end - gt_start) * (selection.x - gt_left) / (img_width))
        new_gt_end   = parseInt(gt_start + (gt_end - gt_start) * (selection.x2 - gt_left) / (img_width))
        new_gtd_start = new Date(new_gt_start * 1000)
        new_gtd_end   = new Date(new_gt_end   * 1000)
        new_gtd_start.setSeconds(0)
        new_gtd_start.setMilliseconds(0)
        new_gtd_end.setSeconds(0)
        new_gtd_end.setMilliseconds(0)
        @append_rrd_timeframe(undefined, @get_date(), new_gtd_start, new_gtd_end)
        #@rrd_from_field.datetimepicker("setDate", new_gtd_start)
        #@rrd_to_field.datetimepicker("setDate", new_gtd_end)
    draw_rrd: (rrd_key_list) =>
        $.ajax
            url  : "{% url 'rrd:graph_rrds' %}"
            data : {
                "keys"       : rrd_key_list
                "pks"        : @pk_list
                "start_time" : @rrd_from_field.val()
                "end_time"   : @rrd_to_field.val()
                "size"       : @top_div.find("select#rrd_size").val()
            }
            success : (xml) =>
                if parse_xml_response(xml)
                    @graph_div.children().remove()
                    @cur_graph = undefined
                    graph_list = $(xml).find("graph_list")
                    graph_list.find("graph").each (idx, cur_g) =>
                        cur_g = $(cur_g)
                        new_image = $("<img>").attr("src", cur_g.attr("href"))
                        @graph_div.append(new_image)
                        if idx == 0
                            @cur_graph = cur_g
                        # add crop
                        new_image.Jcrop(
                            bgOpacity : 0.8
                            onSelect  : @crop_select
                        )
        
show_domain_name_tree = (event) ->
    new domain_name_tree(event).show()

class domain_name_tree
    constructor: (@event) ->
    show: () =>
        $.ajax
            url     : "{% url 'network:domain_name_tree' %}"
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml = $(xml).find("domain_tree_nodes")
                    @build_div()
                    #console.log @resp_xml[0]
                    #console.log @event
                    @div.simplemodal
                        opacity      : 50 
                        position     : [@event.pageY, @event.pageX]
                        autoResize   : true
                        autoPosition : true
                        onShow: (dialog) -> 
                            dialog.container.draggable()
                        onClose: =>
                            $.simplemodal.close()
    build_div: () =>
        dnt_div = $("<div>")
        dnt_div.append(
            $("<h3>").text("Domain name tree")
        )
        @div = dnt_div
    
show_device_info = (event, dev_key, callback) ->
    new device_info(event, dev_key, callback).show()

class device_info
    constructor: (@event, @dev_key, @callback=undefined) ->
        @addon_devices = []
    show: () =>
        replace_div = {% if index_view %}true{% else %}false{% endif %}
        $.ajax
            url     : "{% url 'device:device_info' %}"
            data    :
                "key"    : @dev_key
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml = $(xml).find("response")
                    @network_list = @resp_xml.find("network_list network")
                    @permissions = @resp_xml.find("permissions")
                    @build_div()
                    if replace_div
                        $("div#center_content").children().remove().end().append(@dev_div)
                    else
                        @dev_div.simplemodal
                            opacity      : 50
                            position     : [@event.pageY, @event.pageX]
                            autoResize   : true
                            autoPosition : true
                            minWidth     : "640px"
                            onShow: (dialog) -> 
                                dialog.container.draggable()
                                $("#simplemodal-container").css("height", "auto")
                                $("#simplemodal-container").css("width", "auto")
                            onClose: =>
                                $.simplemodal.close()
                                if @callback
                                    @callback(@dev_key)
    get_pk_list: () =>
        # get all pks
        pk_list = [@resp_xml.find("device").attr("pk")]
        for addon_key in @addon_devices
            pk_list.push(addon_key.split("__")[1]) 
        return pk_list
    fqdn_compound: (in_dict) =>
        dev_key = in_dict["id"].split("__")[0..1].join("__")
        el_name = in_dict["id"].split("__")[2]
        dev_xml = @resp_xml.find("device[key='#{dev_key}']")
        other_list = []
        if el_name == "name"
            other_name = "domain_tree_node"
        else
            other_name = "name"
        other_id = "#{dev_key}__#{other_name}"
        in_dict[other_id] = dev_xml.attr(other_name)
        other_list.push(other_id)
        in_dict.other_list = other_list.join("::")
    has_perm: (perm_name) =>
        return if @permissions.find("permissions[permission='#{perm_name}']").length then true else false 
    build_div: () =>
        dev_xml = @resp_xml.find("device")
        @my_submitter = new submitter({
            master_xml       : dev_xml
            modify_data_dict : @fqdn_compound
        })
        @my_nd_submitter = new submitter({
            master_xml       : dev_xml
            callback         : @set_network_after_change
        })
        dev_div = $("<div>")
        dev_div.append(
            $("<h3>").text("Device #{dev_xml.attr('full_name')}")
        )
        tabs_div = $("<div>").attr("id", "tabs")
        dev_div.append(tabs_div)
        if @addon_devices.length
            num_devs = @addon_devices.length + 1
            addon_text = " (#{num_devs})"
        else
            addon_text = ""
        tabs_div.append(
            $("<ul>").append(
                $("<li>").append($("<a>").attr("href", "#general").text("General")),
                $("<li>").append($("<a>").attr("href", "#category").text("Category")),
                $("<li>").append($("<a>").attr("href", "#location").text("Location")),
                if @has_perm("change_network") then $("<li>").append($("<a>").attr("href", "#network").text("Network")) else null,
                $("<li>").append($("<a>").attr("href", "#config").text("Config")),
                $("<li>").append($("<a>").attr("href", "#disk").text("Disk")),
                $("<li>").append($("<a>").attr("href", "#mdcds").text("MD data store")),
                $("<li>").append($("<a>").attr("href", "#livestatus").text("Livestatus#{addon_text}")),
                $("<li>").append($("<a>").attr("href", "#monconfig").text("MonConfig#{addon_text}")),
                if @has_perm("show_graphs") then $("<li>").append($("<a>").attr("href", "#rrd").text("Graphs#{addon_text}")) else null,
            )
        )
        @dev_div = dev_div
        tabs_div.append(@general_div(dev_xml))
        tabs_div.append(@category_div(dev_xml))
        tabs_div.append(@location_div(dev_xml))
        if @has_perm("change_network")
            tabs_div.append(@network_div(dev_xml))
        tabs_div.append(@config_div(dev_xml))
        tabs_div.append(@disk_div(dev_xml))
        tabs_div.append(@mdcds_div(dev_xml))
        tabs_div.append(@livestatus_div(dev_xml))
        tabs_div.append(@monconfig_div(dev_xml))
        if @has_perm("show_graphs")
            tabs_div.append(@rrd_div(dev_xml))
        tabs_div.tabs(
            activate : @activate_tab
        )
    show_config_vars: () =>
        $.ajax
            url     : "{% url 'config:get_device_cvars' %}"
            data    :
                "key"    : @resp_xml.find("device").attr("pk")
            success : (xml) =>
                if parse_xml_response(xml)
                    vtl = $(xml).find("var_tuple_list")
                    if vtl.length
                        dt_div = $("<div>").attr("id", "var_tree")
                        dt_div.dynatree
                            autoFocus : false
                            checkbox  : false
                            clickFolderMode : 2
                        @build_vtl_node(dt_div.dynatree("getRoot"), vtl)
                        @dev_div.find("div#config").append(dt_div)
    build_vtl_node: (root_node, vtl_node) =>
        if vtl_node.prop("tagName") == "var"
            title_str = vtl_node.attr("key")
            if vtl_node.attr("value")?
                title_str = title_str + " = " + vtl_node.attr("value")
        else
            title_str = vtl_node.prop("tagName")
        if vtl_node.find("*").length
            is_folder = true
        else
            is_folder = false
        new_node = root_node.addChild(
            title    : title_str
            isFolder : is_folder
        )
        vtl_node.find("> *").each (idx, sub_node) =>
            @build_vtl_node(new_node, $(sub_node))
    build_rrd_noxde: (dt_node, db_node) =>
        if db_node.prop("tagName") == "machine_vector"
            title_str = "vector"
            key         = ""
            expand_flag = true
            hide_cb     = true
            tooltip     = "Device vector"
        else if db_node.prop("tagName") == "entry"
            title_str   = db_node.attr("part")
            expand_flag = false
            key         = ""
            hide_cb     = true
            tooltip     = ""
        else
            title_str   = db_node.attr("info")
            expand_flag = false
            key         = db_node.attr("name")
            hide_cb     = false
            tooltip     = "key: " + db_node.attr("name")
        if db_node.attr("devices") and parseInt(db_node.attr("devices")) > 1
            title_str = "#{title_str} (" + db_node.attr("devices") + ")"
        new_node = dt_node.addChild(
            title        : title_str
            expand       : expand_flag
            key          : key
            hideCheckbox : hide_cb
            isFolder     : hide_cb
            tooltip      : tooltip
            #select       : selected
        )
        db_node.find("> *").each (idx, sub_node) =>
            @build_rrd_node(new_node, $(sub_node))
    activate_tab: (event, ui) =>
        t_href = ui.newTab.find("a").attr("href")
        if t_href == "#config"
            if not ui.newPanel.html()
                # lazy load config
                new config_table(ui.newPanel, undefined, @resp_xml.find("device"), @show_config_vars)
        else if t_href == "#livestatus"
            if not ui.newPanel.html()
                # lazy load status
                @init_livestatus(ui.newPanel)
        else if t_href == "#monconfig"
            if not ui.newPanel.html()
                # lazy load monconfig
                @init_monconfig(ui.newPanel)
        else if t_href == "#rrd"
            if not ui.newPanel.html()
                # lazy load rrd
                @init_rrd(ui.newPanel)
        else if t_href == "#network"
            if not ui.newPanel.html()
                # lazy load network
                @init_network_div()
    init_livestatus: (top_div) =>
        table_div = $("<div>").attr("id", "livestatus")
        @livestatus_div = table_div
        top_div.append(@livestatus_div)
        top_div.append(
            $("<input>").attr(
                "type" : "button",
                "value" : "reload",
            ).on("click", @update_livestatus)
        )
        @update_livestatus()
    update_livestatus: () =>
        $.ajax
            url  : "{% url 'mon:get_node_status' %}"
            data : {
                "pks" : @get_pk_list()
            }
            success : (xml) =>
                if parse_xml_response(xml)
                    node_results = $(xml).find("node_results")
                    new_tab = $("<table>").addClass("style2")
                    new_tab.append(
                        $("<thead>").append(
                            $("<tr>").addClass("ui-widget ui-widget-header").append(
                                $("<th>").text("Host"),
                                $("<th>").text("Check"),
                                $("<th>").text("when"),
                                $("<th>").text("Result"),
                            )
                        )
                    )
                    cur_date = new Date()
                    tab_body = $("<tbody>")
                    node_results.find("node_result").each (node_idx, cur_node) =>
                        cur_node = $(cur_node)
                        cur_node.find("result").each (idx, cur_res) =>
                            cur_res = $(cur_res)
                            diff_date = parseInt(cur_date.getTime() / 1000 - parseInt(cur_res.attr("last_check")))
                            tab_body.append(
                                $("<tr>").addClass({"0" : "ok", "1" : "warn", "2" : "error", "3" : "unknown"}[cur_res.attr("state")]).append(
                                    $("<td>").text(cur_node.attr("name")),
                                    $("<td>").text(cur_res.attr("description")),
                                    $("<td>").addClass("right").text(beautify_seconds(diff_date)),
                                    $("<td>").text(cur_res.text()),
                                )
                            )
                    new_tab.append(tab_body)
                    @livestatus_div.empty().html(new_tab)
                    if tab_body.children().length
                        new_tab.dataTable(
                            "sPaginationType" : "full_numbers"
                            "iDisplayLength"  : 50
                            "bScrollCollapse" : true
                            "bScrollAutoCss"  : true
                            "bAutoWidth"      : false
                            "bJQueryUI"       : true
                            "bPaginate"       : true
                        )
    init_monconfig: (top_div) =>
        table_div = $("<div>").attr("id", "monconfig")
        @monconfig_div = table_div
        top_div.append(@monconfig_div)
        top_div.append(
            $("<input>").attr(
                "type"  : "button",
                "value" : "reload",
            ).on("click", @update_monconfig)
        )
        @update_monconfig()
    shorten_attribute: (in_name) =>
        return (sub_str.charAt(0).toUpperCase() for sub_str in in_name.split("_")).join("")
    update_monconfig: () =>
        $.ajax
            url  : "{% url 'mon:get_node_config' %}"
            data : {
                "pks" : @get_pk_list()
            }
            success : (xml) =>
                @monconfig_div.empty()
                if parse_xml_response(xml)
                    conf_top = $(xml).find("config")
                    tab_ul = $("<ul>")
                    if @monconfig_div.hasClass("ui-tabs")
                        @monconfig_div.tabs("destroy")
                    @monconfig_div.append(tab_ul)
                    conf_top.children().each (idx, child_xml) =>
                        child_xml = $(child_xml)
                        tag_name = child_xml.prop("tagName")
                        # tab selector
                        tab_ul.append($("<li>").append($("<a>").attr("href", "##{tag_name}").text(tag_name.split("_")[0])))
                        # tab content
                        sub_div = $("<div>").attr("id", tag_name)
                        # table
                        sub_table = $("<table>").addClass("style2")
                        # get all attribute
                        attr_list = []
                        child_xml.children().each (idx, sub_el) =>
                            for cur_attr in sub_el.attributes
                                if cur_attr.name not in attr_list
                                    attr_list.push(cur_attr.name)
                        header_row = $("<tr>").addClass("ui-widget ui-widget-header")
                        for attr_name in attr_list
                            header_row.append($("<th>").attr("title", attr_name).text(@shorten_attribute(attr_name)))
                        sub_table.append($("<thead>").append(header_row))
                        table_body = $("<tbody>")
                        sub_table.append(table_body)
                        child_xml.children().each (idx, sub_el) =>
                            sub_el = $(sub_el)
                            cur_line = $("<tr>")
                            for attr_name in attr_list
                                cur_line.append($("<td>").attr("title", attr_name).text(sub_el.attr(attr_name)))
                            table_body.append(cur_line)
                        sub_div.append(sub_table)
                        if table_body.children().length
                            sub_table.dataTable(
                                "sPaginationType" : "full_numbers"
                                "iDisplayLength"  : 50
                                "bScrollCollapse" : true
                                "bScrollAutoCss"  : true
                                "bAutoWidth"      : false
                                "bJQueryUI"       : true
                                "bPaginate"       : true
                            )
                        @monconfig_div.append(sub_div)
                    @monconfig_div.tabs()
    init_rrd: (top_div) =>
        rrd_div = $("<div>").attr("id", "rrd").addClass("leftfloat")
        graph_div = $("<div>").attr("id", "graph").addClass("leftfloat")
        config_div = $("<div>").attr("id", "rrd_config")
        @rrd_div = rrd_div
        @graph_div = graph_div
        @config_div = config_div
        @rrd_config = new rrd_config(@config_div, @rrd_div, @graph_div, @get_pk_list())
        top_div.append(@config_div)
        top_div.append(@rrd_div)
        top_div.append(@graph_div)
        #@load_rrd_tree()
    general_div: (dev_xml) =>
        # general div
        general_div = $("<div>").attr("id", "general")
        # working :-)
        general_div.html(@resp_xml.find("forms general_form").text())
        #console.log(@resp_xml.find("forms general_form")[0])
        general_div.find("input, select").bind("change", @my_submitter.submit)
        @uuid_div = null
        general_div.find("input[name='uuid']").on("click", @show_uuid_info)
        #general_div.find("select.select_chosen").chosen(
        #    width : "50%"
        #)
        #general_div.find("div#dnt").jstree(
        #    "plugins" : ["html_data", "themes",]            
        #)
        #general_div.find("div#dnt").dynatree(
        #    autoFocus  : false
        #    checkbox   : true
        #)
        #general_div.find("input[id$='_domain_tree_node']").on("click", show_domain_name_tree)
        return general_div
    show_uuid_info: (event) => 
        cur_el = $(event.target)
        if @uuid_div
            cur_el.val("show UUID info")
            @uuid_div.remove()
            @uuid_div = null
        else
            cur_el.val("hide UUID info")
            @uuid_div = $("<div>").
                append(
                    $("<h4>").text("Copy the following snippet to /etc/sysconfig/cluster/.cluster_device_uuid :"),
                    $("<pre>").
                        css("font-family", "courier").
                        css("font-size", "12pt").
                        css("display", "block").
                        text("urn:uuid:" + @resp_xml.find("device").attr("uuid")),
                    $("<h4>").text("and restart host-monitoring .")
                )
            cur_el.after(@uuid_div)
    category_div: (dev_xml) =>
        cat_div = $("<div>").attr("id", "category")
        tree_div = $("<div>").attr("id", "cat_tree")
        cat_div.append(tree_div)
        new category_tree(tree_div, undefined, dev_xml, @resp_xml, "/device", true)
        return cat_div
    location_div: (dev_xml) =>
        loc_div = $("<div>").attr("id", "location")
        tree_div = $("<div>").attr("id", "loc_tree")
        loc_div.append(tree_div)
        new category_tree(tree_div, undefined, dev_xml, @resp_xml, "/location", false)
        return loc_div
    init_network_div: =>
        # load structures needed for network
        $.ajax
            url     : "{% url 'network:get_valid_peers' %}"
            success : (xml) =>
                @valid_peers = $(xml).find("valid_peers")
                nd_list = @resp_xml.find("netdevice")
                nw_div = @network_div
                if nd_list.length
                    nd_ul = $("<ul>")
                    nw_div.append(nd_ul)
                    nd_list.each (nd_idx, nd_xml) =>
                        nd_xml = $(nd_xml)
                        nd_li = $("<li>").append($("<a>").attr("href", "#nd__" + nd_xml.attr("devname")).text(nd_xml.attr("devname")))
                        nd_ul.append(nd_li)
                        new_div = $("<div>").attr("id", "nd__" + nd_xml.attr("devname"))
                        nw_div.append(new_div)
                        new_div.append($("<h4>").text("IP addresses"))
                        new_div.append(@build_net_ip_table(nd_xml))
                        new_div.append($("<h4>").text("Peer information"))
                        new_div.append(@build_peer_info_table(nd_xml))
                        new_div.append($("<h4>").text("Device flags"))
                        new_div.append(
                            create_input_el(nd_xml, "routing", nd_xml.attr("key"), {master_xml : nd_xml, boolean : true, label : "routing capable:"}),
                            "<span>,</span>",
                            create_input_el(nd_xml, "penalty", nd_xml.attr("key"), {master_xml : nd_xml, number : true, min : 1, max : 128, label : "device penalty:"}),
                        )
                    nw_div.find("input[id^='ip__'], select[id^='ip__']").off("change").bind("change", @my_nd_submitter.submit)
                    @network_div = nw_div
                    nw_div.tabs()
                else
                    nw_div.append($("<span>").text("no netdevices found"))
    network_div: (dev_xml) =>
        # network div
        @network_div = $("<div>").attr("id", "network")
        return @network_div
    build_net_ip_table : (nd_xml) =>
        ip_table = $("<table>").attr("id", "ip__" + nd_xml.attr("key"))
        nd_xml.find("net_ip").each (ip_idx, ip_xml) =>
            ip_xml = $(ip_xml)
            ip_line = $("<tr>").append(
                $("<td>").append(
                    $("<input>").attr(
                        "id"     : ip_xml.attr("key"),
                        "type"   : "image"
                        "src"    : "{{ MEDIA_URL }}frontend/images/list-remove.png"
                        "width"  : "22px"
                        "height" : "22px"
                    ).on("click", @remove_net_ip),
                ),
                create_input_el(ip_xml, "ip", ip_xml.attr("key"), {master_xml : ip_xml, enclose_td : true, size : 16})
                create_input_el(ip_xml, "network", ip_xml.attr("key"), {select_source : @network_list, master_xml : ip_xml, enclose_td : true})
                create_input_el(ip_xml, "domain_tree_node", ip_xml.attr("key"), {select_source : @resp_xml.find("domain_tree_nodes domain_tree_node"), master_xml : ip_xml, enclose_td : true})
            )
            ip_table.append(ip_line)
        new_ip_key = nd_xml.attr("key") + "__ip__new"
        ip_table.append(
            $("<tr>").append(
                $("<td>").append(
                    $("<input>").attr(
                        "id"     : new_ip_key,
                        "type"   : "image"
                        "src"    : "{{ MEDIA_URL }}frontend/images/list-add.png"
                        "width"  : "22px"
                        "height" : "22px"
                    ).on("click", @create_net_ip),
                ),
                create_input_el(undefined, "ip", new_ip_key, {enclose_td : true, default : "0.0.0.0", size : 16})
                create_input_el(undefined, "network", new_ip_key, {select_source : @network_list, enclose_td : true})
                create_input_el(undefined, "domain_tree_node", new_ip_key, {select_source : @resp_xml.find("domain_tree_nodes domain_tree_node"), enclose_td : true})
            )
        )
        return ip_table
    build_peer_info_table: (nd_xml) =>
        peer_table = $("<table>").attr("id", "peer__" + nd_xml.attr("key"))
        nd_xml.find("peers > peer_information").each (p_idx, p_xml) =>
            p_xml = $(p_xml)
            if p_xml.attr("s_netdevice") == nd_xml.attr("pk")
                other_side = "to"
            else
                other_side = "from"
            peer_line = $("<tr>").append(
                $("<td>").append(
                    $("<input>").attr(
                        "id"     : p_xml.attr("key"),
                        "type"   : "image"
                        "src"    : "{{ MEDIA_URL }}frontend/images/list-remove.png"
                        "width"  : "22px"
                        "height" : "22px"
                    ).on("click", @remove_peer),
                ),
                create_input_el(p_xml, "penalty", p_xml.attr("key"), {enclose_td : true, default : 1, "0.0.0.0", number : true, min : 1, max : 256}),
                $("<td>").text("to " + p_xml.attr("#{other_side}_devname") + " on " + p_xml.attr("#{other_side}_device_full"))
            )
            peer_table.append(peer_line)
        new_peer_key = nd_xml.attr("key") + "__peer__new"
        peer_table.append(
            $("<tr>").append(
                $("<td>").append(
                    $("<input>").attr(
                        "id"     : new_peer_key,
                        "type"   : "image"
                        "src"    : "{{ MEDIA_URL }}frontend/images/list-add.png"
                        "width"  : "22px"
                        "height" : "22px"
                    ).on("click", @create_new_peer),
                ),
                create_input_el(undefined, "penalty", new_peer_key, {enclose_td : true, new_default : 1, number : true, min : 1, max : 256})
                create_input_el(undefined, "d_netdevice", new_peer_key, {enclose_td : true, select_source : @valid_peers.find("valid_peer")})
            )
        )
        return peer_table
    remove_peer: (event) =>
        cur_el = $(event.target)
        send_data = {}
        send_data[cur_el.attr("id")] = 1
        $.ajax
            url     : "{% url 'base:delete_object' 'peer_information' %}"
            data    : send_data
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml.find("peer_information[key='" + cur_el.attr("id") + "']").remove()
                    cur_el.parents("tr:first").remove()
    create_new_peer: (event) =>
        cur_el = $(event.target)
        cur_tr = cur_el.parents("tr:first")
        nd_pk = cur_el.attr("id").split("__")[1]
        c_dict = {
            "penalty"  : cur_tr.find("input[id$='__penalty']").val(),
            "id"       : "peer__nd__#{nd_pk}",
            "new_peer" : cur_tr.find("select[id$='__d_netdevice']").val(),
        }
        $.ajax
            url   : "{% url 'network:create_new_peer' %}"
            data  : c_dict
            success : (xml) =>
                if parse_xml_response(xml)
                    new_peer = $(xml).find("value[name='new_peer_information'] > peer_information")
                    add_nd = @resp_xml.find("netdevice[pk='#{nd_pk}']")
                    add_nd.find("peers").append(new_peer)
                    peer_table = @network_div.find("table[id='peer__nd__#{nd_pk}']")
                    peer_table.replaceWith(@build_peer_info_table(add_nd))
    remove_net_ip: (event) =>
        cur_el = $(event.target)
        send_data = {}
        send_data[cur_el.attr("id")] = 1
        $.ajax
            url     : "{% url 'base:delete_object' 'net_ip' %}"
            data    : send_data
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml.find("net_ip[key='" + cur_el.attr("id") + "']").remove()
                    cur_el.parents("tr:first").remove()
    create_net_ip: (event) =>
        cur_el = $(event.target)
        c_dict = create_dict_unserialized(cur_el.parents("tr:first"), cur_el.attr("id"))
        $.ajax
            url   : "{% url 'network:create_net_ip' %}"
            data  : c_dict
            success : (xml) =>
                if parse_xml_response(xml)
                    new_net_ip = $(xml).find("value[name='new_net_ip'] > net_ip")
                    add_nd = @resp_xml.find("netdevice[pk='" + new_net_ip.attr("netdevice") + "']") 
                    add_nd.find("net_ips").append(new_net_ip)
                    ip_table = @network_div.find("table[id='ip__" + add_nd.attr("key") + "']")
                    ip_table.replaceWith(@build_net_ip_table(add_nd))
    set_network_after_change: (cur_el) =>
        console.log cur_el
        # get xml_el
        net_ip_xml = @resp_xml.find("net_ip[pk='" + cur_el.attr("id").split("__")[1] + "']")
        @network_div.find("select[id='ip__" + net_ip_xml.attr("pk") + "__network']").attr("value", net_ip_xml.attr("network"))
    config_div: (dev_xml) =>
        # configuration div
        conf_div = $("<div>").attr("id", "config")
        return conf_div
    livestatus_div: (dev_xml) =>
        # configuration div
        return $("<div>").attr("id", "livestatus")
    monconfig_div: (dev_xml) =>
        # monitoring config div
        return $("<div>").attr("id", "monconfig")
    rrd_div: (dev_xml) =>
        # rrd div
        return $("<div>").attr("id", "rrd")
    disk_div: (dev_xml) =>
        # disk div
        disk_div = $("<div>").attr("id", "disk")
        if dev_xml.find("partition_table").length
            disk_div.append($("<h3>").text("partition table"))
            pt_ul = $("<ul>")
            dev_xml.find("partition_table partition_discs partition_disc").each (idx, cur_disc) =>
                cur_disc = $(cur_disc)
                disk_li = $("<li>").text(cur_disc.attr("disc"))
                disk_lu = $("<ul>")
                disk_li.append(disk_lu)
                cur_disc.find("partitions partition").each (p_idx, cur_part) =>
                    cur_part = $(cur_part)
                    part_li = $("<li>").text("part #{cur_part.attr('pnum')} at #{cur_part.attr('mountpoint')}")
                    part_li.append(
                        create_input_el(cur_part, "warn_threshold", cur_part.attr("key"), {master_xml : cur_part, number: true, min:0, max: 100, label: ", warning at"})
                        create_input_el(cur_part, "crit_threshold", cur_part.attr("key"), {master_xml : cur_part, number: true, min:0, max: 100, label: ", critical at"})
                    )
                    disk_lu.append(part_li)
                pt_ul.append(disk_li)
            dev_xml.find("partition_table lvm_info lvm_vg").each (idx, cur_vg) =>
                cur_vg = $(cur_vg)
                vg_li = $("<li>").text("VG " + cur_vg.attr("name"))
                vg_lu = $("<ul>")
                vg_li.append(vg_lu)
                cur_vg.find("lvm_lvs lvm_lv").each (lvm_idx, cur_lvm) =>
                    cur_lvm = $(cur_lvm)
                    lvm_li = $("<li>").text("#{cur_lvm.attr('name')} at #{cur_lvm.attr('mountpoint')}")
                    lvm_li.append(
                        create_input_el(cur_lvm, "warn_threshold", cur_lvm.attr("key"), {master_xml : cur_lvm, number: true, min:0, max: 100, label: ", warning at"})
                        create_input_el(cur_lvm, "crit_threshold", cur_lvm.attr("key"), {master_xml : cur_lvm, number: true, min:0, max: 100, label: ", critical at"})
                    )
                    vg_lu.append(lvm_li)
                pt_ul.append(vg_li)
            disk_div.append(pt_ul)
        else
            disk_div.append($("<h3>").text("No partition table defined"))
        return disk_div
    mdcds_div: (dev_xml) =>
        # md check data store div
        mdcds_div = $("<div>").attr("id", "mdcds")
        num_mdcds = dev_xml.find("md_check_data_store").length
        if num_mdcds
            mdcds_div.append($("<h3>").text("#{num_mdcds} entries found"))
            dev_xml.find("md_check_data_stores md_check_data_store").each (idx, cur_ds) =>
                cur_ds = $(cur_ds)
                mdcds_div.append(
                    $("<div>").text(cur_ds.attr("name")).append(
                        $("<textarea>").attr("id", "cm01").text(cur_ds.attr("data"))
                    )
                )
                cur_ed = CodeMirror.fromTextArea(mdcds_div.find("textarea")[0], {
                    "mode"         : {
                        "name"    : "xml",
                        "version" : "2"
                    },
                    "styleActiveLine" : true,
                    "lineNumbers"     : true,
                    "lineWrapping"    : true,
                    "indentUnit"      : 4,
                })
        else
            mdcds_div.append($("<h3>").text("No entries found"))
        return mdcds_div
    
root.show_device_info = show_device_info
root.show_domain_name_tree = show_domain_name_tree
root.device_info = device_info
root.category_tree = category_tree

{% endinlinecoffeescript %}

</script>
