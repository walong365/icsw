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
    constructor: (@tree_div, @top_xml, @xml, @cat_tree, @top_node, @multi_sel=true) ->
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
                        (cur_node) ->
                            if cur_node.isSelected() and cur_node.data.key != dtnode.data.key
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
        cur_date = new Date()
        start_date = new Date()
        start_date.setHours(cur_date.getHours() - 40)
        min_date = new Date()
        min_date.setFullYear(cur_date.getYear() - 10)
        size_select =$("<select>").attr(
            "id"  : "rrd_size"
        ).on("change", @draw_rrd_el)
        for cur_size in ["400x200", "640x300", "800x400"]
            size_select.append(
                $("<option>").attr("value", cur_size).text(cur_size)
            )
        # default size
        size_select.val("640x300")
        @CUR_FILTER = ""
        @top_div.append(@filter_el, clear_el, draw_el, size_select, @rrd_from_field, @rrd_to_field)
        @rrd_from_field.datetimepicker(
            minDate     : min_date
            maxDate     : cur_date
            defaultDate : start_date
            hour        : start_date.getHours()
            minute      : start_date.getMinutes()
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
            maxDate     : cur_date
            defaultDate : cur_date
            hour        : cur_date.getHours()
            minute      : cur_date.getMinutes()
            changeMonth : true
            changeYear  : true
            dateFormat  : "yy-mm-dd"
            onClose     : (sel_date) =>
                @rrd_from_field.datepicker("option", "maxDate", sel_date)
                @update_rrd_timeframe()
        )
        @rrd_from_field.datetimepicker("setDate", start_date)
        @rrd_to_field.datetimepicker("setDate", cur_date)
        @load_rrd_tree()
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
                        root_node = @key_tree_div.dynatree("getRoot")
                        @build_rrd_node(root_node, @vector)
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
        @rrd_from_field.datetimepicker("setDate", new_gtd_start)
        @rrd_to_field.datetimepicker("setDate", new_gtd_end)
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
                    @build_div()
                    if replace_div
                        $("div#center_content").children().remove().end().append(@dev_div)
                    else
                        @dev_div.modal
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
                                $.modal.close()
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
    build_div: () =>
        dev_xml = @resp_xml.find("device")
        @my_submitter = new submitter({
            master_xml       : dev_xml
            modify_data_dict : @fqdn_compound
        })
        dev_div = $("<div>")
        dev_div.append(
            $("<h3>").text("#{dev_xml.attr('name')}, UUID: #{dev_xml.attr('uuid')}")
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
                $("<li>").append($("<a>").attr("href", "#network").text("Network")),
                $("<li>").append($("<a>").attr("href", "#config").text("Config")),
                $("<li>").append($("<a>").attr("href", "#disk").text("Disk")),
                $("<li>").append($("<a>").attr("href", "#mdcds").text("MD data store")),
                $("<li>").append($("<a>").attr("href", "#livestatus").text("Livestatus#{addon_text}")),
                $("<li>").append($("<a>").attr("href", "#monconfig").text("MonConfig#{addon_text}")),
                $("<li>").append($("<a>").attr("href", "#rrd").text("Graphs#{addon_text}")),
            )
        )
        @dev_div = dev_div
        tabs_div.append(@general_div(dev_xml))
        tabs_div.append(@category_div(dev_xml))
        tabs_div.append(@location_div(dev_xml))
        tabs_div.append(@network_div(dev_xml))
        tabs_div.append(@config_div(dev_xml))
        tabs_div.append(@disk_div(dev_xml))
        tabs_div.append(@mdcds_div(dev_xml))
        tabs_div.append(@livestatus_div(dev_xml))
        tabs_div.append(@monconfig_div(dev_xml))
        tabs_div.append(@rrd_div(dev_xml))
        tabs_div.tabs(
            activate : @activate_tab
        )
    activate_tab: (event, ui) =>
        t_href = ui.newTab.find("a").attr("href")
        if t_href == "#config"
            if not ui.newPanel.html()
                # lazy load config
                new config_table(ui.newPanel, undefined, @resp_xml.find("device"))
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
        general_div.find("input, select").bind("change", @my_submitter.submit)
        return general_div
    category_div: (dev_xml) =>
        cat_div = $("<div>").attr("id", "category")
        tree_div = $("<div>").attr("id", "cat_tree")
        cat_div.append(tree_div)
        new category_tree(tree_div, @configs_xml, dev_xml, @resp_xml, "/device")
        return cat_div
    location_div: (dev_xml) =>
        loc_div = $("<div>").attr("id", "location")
        tree_div = $("<div>").attr("id", "loc_tree")
        loc_div.append(tree_div)
        new category_tree(tree_div, @configs_xml, dev_xml, @resp_xml, "/location", false)
        return loc_div
    network_div: (dev_xml) =>
        # network div
        nw_div = $("<div>").attr("id", "network")
        if dev_xml.find("netdevice").length
            nd_ul = $("<ul>")
            dev_xml.find("netdevice").each (nd_idx, nd_xml) =>
                nd_xml = $(nd_xml)
                nd_li = $("<li>").text(nd_xml.attr("devname"))
                nd_ul.append(nd_li)
                ip_ul = $("<ul>")
                nd_xml.find("net_ip").each (ip_idx, ip_xml) =>
                    ip_xml = $(ip_xml)
                    ip_li = $("<li>").text(ip_xml.attr("ip"))
                    ip_ul.append(ip_li)
                nd_li.append(ip_ul)
        else
            nd_ul = $("<span>").text("no netdevices found")
        nw_div.append(nd_ul)
        return nw_div
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
root.device_info = device_info

{% endinlinecoffeescript %}

</script>
