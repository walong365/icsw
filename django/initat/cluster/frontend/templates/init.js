{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

class ajax_struct
    constructor: (@top_div_name) ->
        @ajax_uuid = 0
        @ajax_dict = {}
        @top_div = undefined
    new_connection: (settings) =>
        cur_id = @ajax_uuid
        if not @top_div
            @top_div = $(@top_div_name)
        if not @top_div.find("ul").length
            @top_div.append($("<ul>"))
        ai_ul = @top_div.find("ul")
        ai_ul.append(
            $("<li>").attr({
                "id" : cur_id
            }).text(settings.title or "pending...")
        )
        @ajax_dict[cur_id] = {
            "state" : "pending"
            "start" : new Date()
        }
        @ajax_uuid++
        return cur_id
    close_connection: (xhr_id) =>
        if xhr_id?
            @ajax_dict[xhr_id]["state"]   = "done"
            @ajax_dict[xhr_id]["runtime"] = new Date() - @ajax_dict[xhr_id]["start"]
            @top_div.find("li##{xhr_id}").remove()
        
my_ajax_struct = new ajax_struct("div#ajax_info")

$.ajaxSetup
    type       : "POST"
    timeout    : 50000
    dataType   : "xml"
    beforeSend : (xhr, settings) ->
        if not settings.hidden
            xhr.inituuid = my_ajax_struct.new_connection(settings)
    complete   : (xhr, textstatus) ->
        my_ajax_struct.close_connection(xhr.inituuid)
    dataFilter : (data, data_type) ->
        return data
    error      : (xhr, status, except) ->
        if status == "timeout"
            alert("timeout")
        else
            if xhr.status 
                # if status is != 0 an error has occured
                alert("*** #{status} ***\nxhr.status : #{xhr.status}\nxhr.statusText : #{xhr.statusText}")
        return false

root.show_device_info = (event, dev_key) ->
    new device_info(event, dev_key).show()

class device_info
    constructor: (@event, @dev_key) ->
    show: () =>
        $.ajax
            url     : "{% url 'device:device_info' %}"
            data    :
                "key"    : @dev_key
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml = $(xml).find("response")
                    @build_div()
                    @dev_div.modal
                        opacity      : 50
                        position     : [@event.pageY, @event.pageX]
                        autoResize   : true
                        autoPosition : true
                        onShow: (dialog) -> 
                            dialog.container.draggable()
                            $("#simplemodal-container").css("height", "auto")
    build_div: () =>
        dev_xml = @resp_xml.find("device")
        dev_div = $("<div>")
        dev_div.append(
            $("<h3>").text("#{dev_xml.attr('name')}, UUID: #{dev_xml.attr('uuid')}")
        )
        tabs_div = $("<div>").attr("id", "tabs")
        dev_div.append(tabs_div)
        tabs_div.append(
            $("<ul>").append(
                $("<li>").append(
                    $("<a>").attr("href", "#general").text("General")
                )
            ).append(
                $("<li>").append(
                    $("<a>").attr("href", "#network").text("Network")
                )
            ).append(
                $("<li>").append(
                    $("<a>").attr("href", "#disk").text("Disk")
                )
            ).append(
                $("<li>").append(
                    $("<a>").attr("href", "#mdcds").text("MD data store")
                )
            )
        )
        @dev_div = dev_div
        tabs_div.append(@general_div())
        tabs_div.append(@network_div())
        tabs_div.append(@disk_div())
        tabs_div.append(@mdcds_div())
        tabs_div.tabs()
    general_div: () =>
        dev_xml = @resp_xml.find("device")
        # general div
        general_div = $("<div>").attr("id", "general")
        # working :-)
        general_div.append(
            $("<div>").attr("style", "clear: both").append(
                create_input_el(
                    dev_xml,
                    "name",
                    dev_xml.attr("key"), {
                        master_xml : @resp_xml,
                        title      : "device name",
                        label      : "Device name"
                        callback   : @domain_callback
                    }
                )
            ).append(".").append(
                create_input_el(
                    dev_xml,
                    "domain_tree_node",
                    dev_xml.attr("key"), {
                        master_xml : @resp_xml,
                        select_source : @resp_xml.find("domain_tree_node"),
                        title      : "domain name",
                    }
                )
            )
        )
        general_div.append($("<div>").attr("style", "clear: both").append(create_input_el(dev_xml, "comment", dev_xml.attr("key"), {master_xml : @resp_xml, title : "comment", label : "Comment", textarea : true})))
        general_div.append($("<div>").attr("style", "clear: both").append(create_input_el(dev_xml, "monitor_checks", dev_xml.attr("key"), {master_xml : @resp_xml, title : "Enable checks", label : "Monitoring", boolean : true})))
        return general_div
    network_div: () =>
        dev_xml = @resp_xml.find("device")
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
    disk_div: () =>
        dev_xml = @resp_xml.find("device")
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
    mdcds_div: () =>
        dev_xml = @resp_xml.find("device")
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
    domain_callback: (cur_el) =>
        dev_xml = @resp_xml.find("device")
        @dev_div.find("input##{dev_xml.attr('key')}__name").val(dev_xml.attr("name"))
        @dev_div.find("select##{dev_xml.attr('key')}__domain_tree_node").val(dev_xml.attr("domain_tree_node"))
    
root.draw_ds_tables = (t_div, master_array, master_xml=undefined) ->
    # remove accordion if already exists
    if t_div.hasClass("ui-accordion")
        t_div.accordion("destroy")
    t_div.children().remove()
    master_tables = []
    for key, value of master_array
        if value.parent_class
            master_array[value.parent_class].add_child(key)
        else
            master_tables.push(key)
    t_div.append (master_array[key].draw_table(master_xml, master_array) for key in master_tables)
    t_div.accordion
        heightStyle : "content"
        collapsible : true

class draw_setup
    constructor: (@name, @postfix, @xml_name, @create_url, @delete_url, @draw_array, @kwargs={}) ->
        @xml_name_plural = if @xml_name.match(///s$///) then @xml_name + "es" else @xml_name + "s"
        @required_xml = @kwargs.required_xml or []
        @lock_div = @kwargs.lock_div or ""
        @parent_class = @kwargs.parent_class or ""
        @add_create_line = if @kwargs.add_create_line? then @kwargs.add_create_line else true
        @childs = []
        for draw_entry in @draw_array
            draw_entry.draw_setup = @
        # timer events
        @timer_callback = @kwargs.timer_callback or ""
        @timer_timeout = @kwargs.timer_timeout or 0
        # flags
        @drawn = false
        @table_div = undefined
        @element_info = {}
        @master_xml = undefined
    duplicate: () =>
        new_ds = new draw_setup(@name, @postfix, @xml_name, @create_url, @delete_url, @draw_array)
        new_ds.parent_class = @parent_class
        #new_ds.master_array = @master_array
        return new_ds
    add_child: (child) =>
        @childs.push(child)
    clean: ->
        @drawn      = false
        @table_div  = undefined
        @info_div    = undefined
        @master_xml = undefined
    redraw_tables: =>
        master_tables = []
        for key, value of @master_array
            if not value.parent_class
                master_tables.push(key)
        (@master_array[key].draw_table() for key in master_tables)
    draw_head_line: =>
        dummy_div = $("<div>")
        head_line = $("<tr>").attr
            class : "ui-widget-header ui-widget"
        cur_span = 1
        for cur_di in @draw_array
            # exit after first newline
            if cur_di.newline
                break
            cur_span--
            if not cur_span
                new_td = $("<th>").attr("colspan" : cur_di.span).text(cur_di.label)
                cur_span += cur_di.span
            head_line.append(new_td)
        if @create_url
            head_line.append($("<th>").text("action"))
        dummy_div.append(head_line)
        return dummy_div.children()
    draw_table: (master_xml, master_array) ->
        if not @master_xml
            @master_xml = master_xml
            @master_array = master_array
        if @table_div
            table_div = @table_div
        else
            table_div = $("<div>").attr
                id : @postfix
            if @parent_class
                @info_div = $("<span>").attr
                    id : @postfx
            else
                @info_div = $("<h3>").attr
                    id : @postfx
            table_div.append ($("<table>")
                .attr(id: @postfix)
                .addClass("style2"))
        draw = true
        missing_objects = []
        if @required_xml
            for cur_req in @required_xml
                ref_obj = @master_array[cur_req]
                if ref_obj
                    search_str = "#{ref_obj.xml_name_plural} #{ref_obj.xml_name}"
                else
                    search_str = "#{cur_req}s #{cur_req}"
                if not @master_xml.find(search_str).length
                    missing_objects.push(if ref_obj then ref_obj.name else cur_req)
                    draw = false
        p_table = table_div.find("table")
        if draw
            if @drawn
                @redraw()
            else
                @first_draw(p_table)
        else
            if @drawn
                p_table.children().remove()
            @info_div.text("parent objects missing for " + @name + ": " + missing_objects.join(", "))
        @drawn = draw
        if not @table_div
            @table_div = table_div
            @update_table_info()
            dummy_div = $("<div>").append(@info_div).append(table_div)
            return dummy_div.children()
        else
            @update_table_info()
    search_str: =>
        search_str = "#{@xml_name_plural} #{@xml_name}"
        if @parent_class
            search_str = "#{search_str}[#{@parent_class}='" + @parent_el.attr("pk") + "']"
        return search_str
    first_draw: (p_table) ->
        if @timer_callback
            $(document).everyTime(@timer_timeout * 1000, "table_draw_timer", (idx) =>
                @timer_callback(@)
            )
        p_table.append(@draw_head_line())
        if @create_url and @add_create_line
            p_table.append(@draw_line())
        @master_xml.find(@search_str()).each (index, element) =>
            p_table.append(@draw_line($(element)))
        @info_div.text("#{@name}(").append(
            $("<span>").attr(id : "info__#{@postfix}").text("---")
        ).append($("<span>").text(")"))
    redraw: () ->
        @table_div.find("table").find("tr[id]").each (index, cur_tr) =>
            $(cur_tr).find("select").each (index, cur_sel) =>
                for cur_di in @draw_array
                    cur_re = new RegExp("__#{cur_di.name}$")
                    if $(cur_sel).attr("id").match(cur_re)
                        cur_di.sync_select_from_xml($(cur_sel))
    redraw_line: (new_xml) ->
        line_id = new_xml.attr("key")
        @master_xml.find("*[key='" + new_xml.attr("key") + "']").replaceWith(new_xml)
        cur_line = @table_div.find("table").find("tr[id='#{line_id}']")
        cur_line.replaceWith(@draw_line(@master_xml.find("*[key='" + new_xml.attr("key") + "']")))
        @recolor_table()
    append_new_line: (cur_el, new_xml) ->
        @table_div.find("table:first").append(@draw_line(new_xml))
        @update_table_info()
    delete_line: (cur_el) ->
        del_tr = cur_el.parents("tr:first")
        del_id = del_tr.attr("id")
        if del_tr.attr("id")
            @table_div.find("table:first tr#" + del_id).remove()
        else
            del_tr.remove()
        if @childs and del_id
            @table_div.find("tr[id^='child__#{del_id}__']").remove()
        @update_table_info()
    update_table_info: () ->
        @info_div.find("span#info__" + @postfix).text(@master_xml.find(@search_str()).length)
        @recolor_table()
    recolor_table: () =>
        act_class = "even"
        last_id = "x"
        for cur_tr in @table_div.find("tr[id]")
            $(cur_tr).removeClass("even odd")
            if $(cur_tr).attr("id") != last_id
                last_id = $(cur_tr).attr("id")
                act_class = if act_class is "even" then "odd" else "even"
            $(cur_tr).addClass(act_class)
    draw_line: (xml_el) ->
        xml_pk = if xml_el then xml_el.attr("pk") else "new"
        line_prefix = "#{@postfix}__#{xml_pk}"
        cur_dl = new draw_line(@)
        dummy_div = $("<div>")
        dummy_div.append(cur_dl.draw(line_prefix, xml_el, xml_pk))
        if xml_el
            cur_colspan = dummy_div.find("tr td").length
            for child in @childs
                new_ds = @master_array[child].duplicate()
                new_ds.parent_el = xml_el
                dummy_div.append($("<tr>").attr("id", "child__#{line_prefix}__#{child}").append($("<td>").attr("colspan", cur_colspan).append(new_ds.draw_table(@master_xml, @master_array))))
        return dummy_div.children()
    create_delete_element: (event) =>
        cur_el = $(event.target)
        el_id  = cur_el.attr("id")
        lock_list = if @lock_div then lock_elements($("div#" + @lock_div)) else undefined
        if el_id.match(///new$///)
            send_data = create_dict(@table_div, el_id)
            if @parent_class
                send_data["#{el_id}__#{@parent_class}"] = @parent_el.attr("pk")
            $.ajax
                url     : @create_url
                data    : send_data
                success : (xml) =>
                    if parse_xml_response(xml)
                        new_element = $(xml).find(@xml_name)
                        @master_xml.find(@xml_name_plural).append(new_element)
                        @append_new_line(cur_el, new_element)
                        for clear_el in (@draw_array.filter (cur_di) -> cur_di.clear_after_create)
                            @table_div.find("##{el_id}__#{clear_el.name}").val("")
                        @redraw_tables()
                    @unlock_elements(lock_list)
        else
            if confirm("really delete #{@name} ?")
                $.ajax
                    url     : @delete_url
                    data    : create_dict(@table_div, el_id)
                    success : (xml) =>
                        if parse_xml_response(xml)
                            @master_xml.find(@xml_name + "[pk='" + el_id.split("__")[1] + "']").remove()
                            @delete_line(cur_el)
                            @redraw_tables()
                        @unlock_elements(lock_list)
            else
                @unlock_elements(lock_list)
    unlock_elements: (el_list) =>
        if el_list
            el_list.removeAttr("disabled")

class draw_line
    constructor: (@cur_ds) ->
    draw: (line_prefix, xml_el, xml_pk) ->
        @expand = true
        dummy_div = $("<div>")
        n_line = $("<tr>").attr
            "id"    : line_prefix
            "class" : "ui-widget"
        el_list = []
        dummy_div.append(n_line)
        cur_line = n_line
        for cur_di in @cur_ds.draw_array
            if cur_di.newline
                cur_line = $("<tr>").attr
                    "id"    : line_prefix
                    "class" : "ui-widget"
                dummy_div.append(cur_line)
            if not cur_di.keep_td
                new_td = $("<td>")
                if cur_di.cspan
                    new_td.attr("colspan" : cur_di.cspan)
                cur_line.append(new_td)
            new_els = cur_di.draw(@, xml_el, line_prefix)
            if new_els.length
                el_list.push(cur_di.create_draw_result(new_els.last()))
            new_td.append(new_els)
        @cur_ds.element_info[xml_pk] = el_list
        if @cur_ds.create_url
            cd_td = $("<td>").append(
                $("<input>").addClass(if xml_pk == "new" then "" else "delete").attr(
                    "type"  : "button"
                    "value" : if xml_pk == "new" then "create" else "delete"
                    "id"    : line_prefix,
                )
            )
            n_line.append(
                cd_td.bind("click", (event) =>
                    @cur_ds.create_delete_element(event)
                )
            )
        # collapse if requested
        if not @expand
            dummy_div.children()[1..].hide()
        return dummy_div.children()

String.prototype.toTitle = () ->
    return @.replace(/\w\S*/g, (txt) ->
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
    )
        
class draw_info
    constructor: (@name, @kwargs={}) ->
        @label = @kwargs.label or @name.toTitle()
        @span = @kwargs.span or 1
        for attr_name in ["size", "default", "select_source", "boolean", "min", "max", "ro",
        "button", "change_cb", "trigger", "draw_result_cb", "draw_conditional", "text_source",
        "number", "manytomany", "add_null_entry", "newline", "cspan", "show_label", "group",
        "css", "select_source_attribute", "password", "keep_td", "clear_after_create", "callback"]
            @[attr_name] = @kwargs[attr_name] ? undefined
        @size = @kwargs.size or undefined
    get_kwargs: () ->
        kwargs = {new_default : @default}
        for attr_name in ["size", "select_source", "boolean", "min", "max", "ro", "button",
            "change_cb", "draw_result_cb", "trigger", "callback", "text_source",
            "number", "manytomany", "add_null_entry", "css", "select_source_attribute", "password",]
            kwargs[attr_name] = @[attr_name]
        kwargs.master_xml = @draw_setup.master_xml
        if @show_label
            kwargs.label = @label
        if @group
            kwargs.modify_data_dict = @modify_data_dict
        return kwargs
    modify_data_dict: (in_dict) =>
        other_list = []
        lock_list  = []
        xml_pk = in_dict["id"].split("__")
        xml_pk = xml_pk[xml_pk.length - 2]
        element_info = @draw_setup.element_info[xml_pk]
        for other_dr in element_info
            if other_dr.group == @group and other_dr.name != @name
                other_id = other_dr.element.attr("id")
                other_list.push(other_id)
                lock_list.push("#" + other_id)
                in_dict[other_id] = get_value(other_dr.element)
        in_dict.other_list = other_list.join("::")
        in_dict.lock_list = lock_list
    sync_select_from_xml: (cur_el) =>
        old_pks = ($(cur_sub).attr("value") for cur_sub in cur_el.find("option:selected"))
        if typeof(@select_source) == "string"
            sel_source = @draw_setup.master_xml.find(@select_source)
        else if typeof(@select_source) == "function"
            sel_source = @select_source(cur_el, @get_kwargs())
        else
            sel_source = @select_source
        cur_el.children().remove()
        if @add_null_entry
            cur_el.append($("<option>").attr("value" : 0).text(@add_null_entry))
        for cur_ns in sel_source
            cur_ns = $(cur_ns)
            new_opt = $("<option>").attr("value" : cur_ns.attr("pk")).text(cur_ns.text())
            if cur_ns.attr("pk") in old_pks
                new_opt.attr("selected", "selected")
            cur_el.append(new_opt)
    draw: (cur_line, xml_el, line_prefix) ->
        kwargs = @get_kwargs()
        if not cur_line.cur_ds.create_url and not cur_line.cur_ds.kwargs.change
            kwargs.ro = true
        if (@trigger and xml_el) or not @trigger
            if @draw_conditional
                draw_el = @draw_conditional(xml_el)
            else
                draw_el = true
        else
            draw_el = false
        if draw_el
            # faster without get_kwargs, check, FIXME, AL 20130331
            if false
                @master_xml = @draw_setup.master_xml
                new_els = create_input_el(xml_el, @name, line_prefix, @)
            else
                new_els = create_input_el(xml_el, @name, line_prefix, kwargs)
        else
            new_els = []
        return new_els
    create_draw_result: (new_el) ->
        return new draw_result(@name, @group, new_el)

class draw_collapse extends draw_info
    constructor: (name="collapse", kwargs={}) ->
        super(name, kwargs)
    draw: (cur_line, xml_el, line_prefix) ->
        cur_line.expand = @default ? true
        return get_expand_td(line_prefix, "exp", undefined, @expand_cb, @default ? true)
    expand_cb: (line_prefix, state, name) =>
        if state
            @draw_setup.table_div.find("tr[id='#{line_prefix}']")[1..].show()
        else
            @draw_setup.table_div.find("tr[id='#{line_prefix}']")[1..].hide()
        
class draw_link extends draw_info
    constructor: (name="link", kwargs={}) ->
        super(name, kwargs)
    draw: (cur_line, xml_el, line_prefix) ->
        if xml_el
            return $("<a>").attr({
                "href" : "#",
                "id"   : "#{line_prefix}__detail"
            }).bind("click", (event) => @change_cb(event)).text(@name)
        else
            return ""
    
# storage node for rendered element
class draw_result
    constructor: (@name, @group, @element) ->
    
get_value = (cur_el) ->
    if cur_el.is(":checkbox")
        el_value = if cur_el.is(":checked") then "1" else "0"
    else if cur_el.prop("tagName") == "TEXTAREA"
        is_textarea = true
        if cur_el.is(":visible")
            # normal elements (not wrapped in codemirror)
            el_value = cur_el.val()
        else
            # wrapped in codemirror
            el_value = cur_el.text()
    else if cur_el.prop("tagName") == "SELECT" and cur_el.attr("multiple")
        el_value = ($(element).attr("value") for element in cur_el.find("option:selected")).join("::")
    else
        el_value = cur_el.attr("value")
    return el_value

set_value = (el_id, el_value) ->
    $("#" + el_id).val(el_value)

parse_xml_response = (xml, min_level) ->
    success = false
    if $(xml).find("response header").length
        ret_state = $(xml).find("response header").attr("code")
        if parseInt(ret_state) < (if min_level then min_level else 40)
            success = true
        $(xml).find("response header messages message").each (idx, cur_mes) ->
            cur_mes = $(cur_mes)
            cur_level = parseInt(cur_mes.attr("log_level"))
            if cur_level < 30
                $.jnotify(cur_mes.text())
            else if cur_level == 30
                $.jnotify(cur_mes.text(), "warning")
            else
                $.jnotify(cur_mes.text(), "error", true)
    else
        $.jnotify("error parsing responsee", "error", true)
    return success

# lock all active input elements
lock_elements = (top_el) ->
    el_list = top_el.find("input:enabled", "select:enabled")
    el_list.attr("disabled", "disabled")
    return el_list

# unlock list of elements
unlock_elements = (el_list) ->
    el_list.removeAttr("disabled")

# get expansion list
get_expand_td = (line_prefix, name, title, cb_func, initial_state) ->
    if not initial_state
        initial_state = false
    exp_td = $("<td>").append(
        $("<div>").attr({
            "class"   : if initial_state then "ui-icon ui-icon-triangle-1-s leftfloat" else "ui-icon ui-icon-triangle-1-e leftfloat"
            "id"      : "#{line_prefix}__expand__#{name}"
            "title"   : if title then title else "show #{name}"
        })
    ).append(
        $("<span>").attr({
            "id"    : "#{line_prefix}__expand__#{name}__info",
            "title" : if title then title else "show #{name}"
        }).text(name)
    ).bind("click", (event) ->
        toggle_config_line_ev(event, cb_func)
    )
    exp_td.find("div, span").on("hover", highlight_td)
    return exp_td
    
highlight_td = (event) ->
    target = $(event.target).parents("td:first")
    if event.type == "mouseenter"
        target.addClass("highlight")
    else
        target.removeClass("highlight")

toggle_config_line_ev = (event, cb_func) ->
    # get div-element
    cur_el = $(event.target)
    if cur_el.prop("tagName") != "TD"
        cur_el = cur_el.parent("td")
    cur_el = cur_el.children("div")
    cur_class = cur_el.attr("class")
    name = cur_el.attr("id").split("__").pop()
    line_prefix = /^(.*)__expand__.*$/.exec(cur_el.attr("id"))[1]
    if cur_class.match(/-1-e/)
        cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s")
        cur_el.addClass("ui-icon-triangle-1-s")
        cb_func(line_prefix, true, name)
    else
        cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s")
        cur_el.addClass("ui-icon-triangle-1-e")
        cb_func(line_prefix, false, name)

get_xml_value = (xml, key) ->
    ret_value = undefined
    $(xml).find("response values value[name='#{key}']").each (idx, val) ->
        value_xml = $(val)
        if value_xml.attr("type") == "integer"
            ret_value = parseInt(value_xml.text())
        else
            ret_value = value_xml.text()
    return ret_value

# create a dictionary from a list of elements
create_dict = (top_el, id_prefix) ->
    in_list = top_el.find("input[id^='#{id_prefix}'], select[id^='#{id_prefix}'], textarea[id^='#{id_prefix}']")
    out_dict = {}
    in_list.each (idx, cur_el) ->
        cur_el = $(cur_el)
        if cur_el.prop("tagName") == "TEXTAREA"
            out_dict[cur_el.attr("id")] = cur_el.text()
        else if cur_el.is(":checkbox")
            out_dict[cur_el.attr("id")] = if cur_el.is(":checked") then "1" else "0"
        else if cur_el.prop("tagName") == "SELECT" and cur_el.attr("multiple")
            sel_field = []
            cur_el.find("option:selected").each (idx, opt_field) ->
                sel_field.push($(opt_field).attr("value"))
            out_dict[cur_el.attr("id")] = sel_field.join("::")
        else
            out_dict[cur_el.attr("id")] = cur_el.attr("value")
    return out_dict

replace_xml_element = (master_xml, xml) ->
    # replace element in master_xml
    xml.find("value[name='object'] > *").each (idx, new_el) ->
        new_el = $(new_el)
        if master_xml
            master_xml.find("[key='" + new_el.attr("key") + "']").replaceWith(new_el)

class submitter
    constructor: (kwargs) ->
        @modify_data_dict = kwargs.modify_data_dict ? undefined
        @master_xml = kwargs.master_xml ? undefined
        @success_callback = kwargs.success_callback ? undefined
        @error_callback = kwargs.error_callback ? undefined
        @callback = kwargs.callback ? undefined
    submit: (event) =>
        cur_el = $(event.target)
        is_textarea = false
        el_value = get_value(cur_el)
        data_field = {
            "id"         : cur_el.attr("id")
            "checkbox"   : cur_el.is(":checkbox")
            "value"      : el_value,
            "ignore_nop" : 1
        }
        if @modify_data_dict
            @modify_data_dict(data_field)
        if data_field.lock_list
            lock_list = $(data_field.lock_list.join(", ")).attr("disabled", "disabled")
        else
            lock_list = undefined
        $.ajax
            url     : "{% url 'base:change_xml_entry' %}"
            data    : data_field
            success : (xml) =>
                if parse_xml_response(xml)
                    replace_xml_element(@master_xml, $(xml))
                    if @callback
                        callback(cur_el)
                    else
                        # set values
                        $(xml).find("changes change").each (idx, cur_os) ->
                            cur_os = $(cur_os)
                            set_value(cur_os.attr("id"), cur_os.text())
                        if @success_callback
                            @success_callback(cur_el)
                else
                    # set back to previous value 
                    if is_textarea
                        $(cur_el).text(get_xml_value(xml, "original_value"))
                    else if $(cur_el).is(":checkbox")
                        if get_xml_value(xml, "original_value") == "False"
                            $(cur_el).removeAttr("checked")
                        else
                            $(cur_el).attr("checked", "checked")
                    else
                        $(cur_el).attr("value", get_xml_value(xml, "original_value"))
                if lock_list
                    unlock_elements(lock_list)
        

submit_change = (cur_el, callback, modify_data_dict, modify_data_dict_opts, master_xml) ->
    is_textarea = false
    el_value = get_value(cur_el)
    reset_value = false
    data_field = {
        "id"         : cur_el.attr("id")
        "checkbox"   : cur_el.is(":checkbox")
        "value"      : el_value,
        "ignore_nop" : 1
    }
    if modify_data_dict != undefined
        modify_data_dict(data_field)
    if data_field.lock_list
        lock_list = $(data_field.lock_list.join(", ")).attr("disabled", "disabled")
    else
        lock_list = undefined
    $.ajax
        url     : "{% url 'base:change_xml_entry' %}"
        data    : data_field
        success : (xml) ->
            if parse_xml_response(xml)
                replace_xml_element(master_xml, $(xml))
                if callback != undefined and typeof callback == "function"
                    callback(cur_el)
                else
                    # set values
                    $(xml).find("changes change").each (idx, cur_os) ->
                        cur_os = $(cur_os)
                        set_value(cur_os.attr("id"), cur_os.text())
                    if reset_value
                        cur_el.val("")
            else
                # set back to previous value 
                if is_textarea
                    $(cur_el).text(get_xml_value(xml, "original_value"))
                else if $(cur_el).is(":checkbox")
                    if get_xml_value(xml, "original_value") == "False"
                        $(cur_el).removeAttr("checked")
                    else
                        $(cur_el).attr("checked", "checked")
                else
                    $(cur_el).attr("value", get_xml_value(xml, "original_value"))
                if reset_value
                    cur_el.val("")
            if lock_list
                unlock_elements(lock_list)

force_expansion_state = (cur_tr, state) ->
    cur_el = cur_tr.find("div[id*='__expand__']")
    cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s")
    if state
        cur_el.addClass("ui-icon-triangle-1-s")
    else
        cur_el.addClass("ui-icon-triangle-1-e")

enter_password = (event) ->
    top_div = $("<div>")
    top_div.append(
        $("<h3>").text("Please enter password")
    )
    tabs_div = $("<div>").attr("id", "tabs")
    top_div.append(tabs_div)
    tabs_div.append(
        $("<ul>").append(
            $("<li>").append(
                $("<a>").attr("href", "#password").text("password")
            )
        )
    )
    # password div
    pw_div = $("<div>").attr("id", "password")
    pw_div.append(
        $("<ul>").append(
            $("<li>").text("Password:").append(
                $("<input>").attr
                    id   : "pwd0"
                    type : "password"
            )
        ).append(
            $("<li>").text("again:").append(
                $("<input>").attr
                    id   : "pwd1"
                    type : "password"
            )
        )
    ).append(
        $("<h4>").append(
            $("<span>").attr
                id : "error"
        )
    )
    tabs_div.append(pw_div)
    top_div.tabs()
    $.modal(
        top_div,
        {
            onShow : (dialog) ->
                stat_h4 = dialog.data.find("span#error")
                stat_h4.text("password empty")
                dialog.data.find("input").bind("change", () ->
                    pwd0 = dialog.data.find("input#pwd0").val()
                    pwd1 = dialog.data.find("input#pwd1").val()
                    if pwd0 == pwd1
                        if not pwd0 or not pwd1
                            stat_h4.text("password empty")
                            stat_h4.attr("class", "warn")
                        else
                            stat_h4.text("password OK")
                            stat_h4.attr("class", "ok")
                    else
                        stat_h4.text("password mismatch")
                        stat_h4.attr("class", "error")
                )
            onClose : (dialog) ->
                pwd0 = dialog.data.find("input#pwd0").val()
                pwd1 = dialog.data.find("input#pwd1").val()
                $.modal.close()
                if pwd0 == pwd1
                    $(event.target).val(pwd0).trigger("change")
                else
                    $(event.target).val("")
        }
    )
    
create_input_el = (xml_el, attr_name, id_prefix, kwargs) ->
    dummy_div = $("<div>")
    kwargs = kwargs or {}
    if kwargs["select_source"] == undefined
        if kwargs.button
            # manual callback
            new_el = $("<input>").attr
                "type"  : "button"
                "id"    : "#{id_prefix}__#{attr_name}"
            new_el.val(attr_name)
        else if kwargs.boolean
            # checkbox input style
            new_el = $("<input>").attr
                "type"  : "checkbox"
                "id"    : "#{id_prefix}__#{attr_name}"
            if (xml_el and xml_el.attr(attr_name) == "1") or (not xml_el and kwargs.new_default)
                new_el.prop("checked", true)
        else if kwargs.textarea
            # textarea input style
            new_el = $("<textarea>").attr({
                "id"    : "#{id_prefix}__#{attr_name}"
            }).text(if xml_el then xml_el.attr(attr_name) else (kwargs.new_default or ""))
        else
            if xml_el
                text_default = xml_el.attr(attr_name)
            else
                text_default = kwargs.new_default or (if kwargs.number then "0" else "")
            if kwargs.text_source
                # foreign key lookup
                text_default = kwargs.master_xml.find("#{kwargs.text_source}[pk='#{text_default}']").text()
            # text input style
            if kwargs.ro
                # experimental, FIXME, too many if-levels
                new_el = $("<span>").attr({
                    "id"    : "#{id_prefix}__#{attr_name}"
                }).text(text_default)
            else
                new_el = $("<input>").attr({
                    "type"  : if kwargs.password then "password" else (if kwargs.number then "number" else "text")
                    "id"    : "#{id_prefix}__#{attr_name}"
                    "value" : text_default
                })
                if kwargs.password
                    new_el.bind("focus", enter_password)
        # copy attributes
        for attr_name in ["size", "min", "max"]
            if kwargs.hasOwnProperty(attr_name)
                new_el.attr(attr_name, kwargs[attr_name])
        if kwargs["css"]
            console.log kwargs["css"]
            $.each(kwargs["css"], (key, value) ->
                new_el.css(key, value)
            )
    else
        # select input
        if typeof(kwargs.select_source) == "string"
            sel_source = kwargs.master_xml.find(kwargs.select_source)
        else if typeof(kwargs.select_source) == "function"
            sel_source = kwargs.select_source(xml_el, kwargs)
        else
            sel_source = kwargs.select_source
        if sel_source.length or kwargs.add_null_entry or kwargs.add_extra_entry
            new_el = $("<select>").attr
                "id"    : "#{id_prefix}__#{attr_name}"
            if kwargs["css"]
                $.each(kwargs["css"], (key, value) ->
                    new_el.css(key, value)
                )
            if kwargs.manytomany
                sel_val = if xml_el == undefined then (if kwargs.new_default == undefined then [] else kwargs.new_default) else xml_el.attr(attr_name).split("::")
                new_el.attr
                    "multiple" : "multiple"
                    "size"     : 5
            else
                sel_val = if xml_el == undefined then (if kwargs.new_default == undefined then "0" else kwargs.new_default) else xml_el.attr(attr_name)
                new_el.val(sel_val)
            if kwargs.add_null_entry
                new_el.append(
                    $("<option>").attr({"value" : "0"}).text(kwargs.add_null_entry)
                )
            if kwargs.add_extra_entry
                new_el.append(
                    $("<option>").attr({"value" : kwargs.extra_entry_id or "-1"}).text(kwargs.add_extra_entry)
                )
            sel_source.each (idx, cur_ns) ->
                cur_ns = $(cur_ns)
                new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")})
                if kwargs.select_source_attribute == undefined
                    new_opt.text(cur_ns.text())
                else
                    new_opt.text(cur_ns.attr(kwargs.select_source_attribute))
                if kwargs.manytomany
                    if cur_ns.attr("pk") in sel_val
                        new_opt.attr("selected", "selected")
                else
                    if (cur_ns.attr("pk") == sel_val)
                        new_opt.attr("selected", "selected")
                if cur_ns.attr("data-image")
                    new_opt.attr("data-image", cur_ns.attr("data-image"))
                new_el.append(new_opt)
        else
            if kwargs.ignore_missing_source
                new_el = $("<span>")
            else
                new_el = $("<span>").addClass("error").text("no #{attr_name} defined")
    if kwargs["title"]
        new_el.attr("title", kwargs["title"])
    if xml_el != undefined and (kwargs.bind == undefined or kwargs.bind)
        if kwargs.change_cb
            if kwargs.button
                new_el.bind("click", kwargs.change_cb)
            else
                new_el.bind("change", kwargs.change_cb)
            new_el.bind("change", kwargs.change_cb)
        else
            if kwargs.submitter
                new_el.bind("change", kwargs.submitter.submit)
            else
                new_el.bind("change", (event) ->
                    submit_change($(event.target), kwargs.callback, kwargs.modify_data_dict, kwargs.    modify_data_dict_opts, kwargs.master_xml)
                )
    else if kwargs.change_cb
        new_el.bind("change", kwargs.change_cb)
    if kwargs and kwargs.ro and new_el.get(0).tagName != "SPAN" and not kwargs.trigger
        new_el.attr("disabled", "disabled")
    if kwargs["label"]
        dummy_div.append($("<label>").attr({"for" : attr_name}).text(kwargs["label"]))
    dummy_div.append(new_el)
    if kwargs and kwargs.draw_result_cb
        dummy_div = kwargs.draw_result_cb(xml_el, dummy_div)
    if kwargs.enclose_td
        kwargs.enclose_tag = "<td>"
    if kwargs.enclose_tag
        # will not work when draw_result_cb is specified
        enc_td = $(kwargs.enclose_tag).append(dummy_div.children())
        dummy_div.append(enc_td)
    return dummy_div.children()

root.get_value             = get_value
root.set_value             = set_value
root.draw_setup            = draw_setup
root.draw_info             = draw_info
root.draw_link             = draw_link
root.draw_collapse         = draw_collapse
root.parse_xml_response    = parse_xml_response
root.lock_elements         = lock_elements
root.unlock_elements       = unlock_elements
root.get_expand_td         = get_expand_td
root.toggle_config_line_ev = toggle_config_line_ev
root.get_xml_value         = get_xml_value
root.create_dict           = create_dict
root.replace_xml_element   = replace_xml_element
root.submit_change         = submit_change
root.force_expansion_state = force_expansion_state
root.create_input_el       = create_input_el
root.submitter             = submitter

{% endinlinecoffeescript %}

</script>
