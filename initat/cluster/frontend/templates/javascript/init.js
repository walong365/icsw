{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

remove_by_idx = (in_array, idx) ->
    for c_idx, val of in_array
        if val.idx == idx
            remove_from_array(in_array, c_idx)
            break

remove_from_array = (in_array, from, to) ->
    rest = in_array.slice((to | from) + 1 || in_array.length)
    in_array.length = if from < 0 then in_array.length + from else from
    return in_array.push.apply(in_array, rest)

root.remove_by_idx = remove_by_idx

jQuery.fn.justtext = () ->
    return $(this).clone().children().remove().end().text()
    
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
        title_str = settings.title or "pending..."
        {% if debug %}
        title_str = "(#{cur_id}) #{title_str}"
        {% endif %}
        ai_ul.append(
            $("<li>").attr({
                "id" : cur_id
            }).text(title_str)
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
    headers    : { "X-CSRFToken" : $.cookie("csrftoken") }
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

class display_config
    constructor: (cur_conf) ->
        @pk = cur_conf.attr("pk")
        @name = cur_conf.attr("name")
        @num_vars    = cur_conf.find("config_vars *").length
        @num_scripts = cur_conf.find("config_scripts *").length
        @num_checks  = cur_conf.find("mon_check_commands *").length
        @title = "#{@num_vars} variables, #{@num_scripts} scripts, #{@num_checks} check commands"
        
class config_table
    constructor: (@top_div, @filter_div=undefined, @device=undefined, @callback=undefined) ->
        @cur_filter = ""
        @show_list = ""
        @only_associated = false
        if @filter_div
            @filter_div.find("input#filter").on("keyup", @apply_filter)
            @filter_div.find("input#filter_clear").on("click", @clear_filter)
            @filter_div.find("input#filter_assoc").on("click", @change_assoc_filter)
        if @device
            @load_device_configs([@device.attr("key")])
    use_devs: (sel_list, sel_g_list) =>
        notify_generate_link(sel_list)
        for cur_devg in sel_g_list
            sel_list.push(cur_devg)
        $.ajax
            url     : "{% url 'device:get_group_tree' %}"
            data    : {
                "sel_list"  : sel_list
                "full_name" : 1
            }
            success : (xml) =>
                if parse_xml_response(xml)
                    @devices = $(xml).find("value[name='response']")
                    @load_device_configs(sel_list)
    load_device_configs : (sel_list) =>
        $.ajax
            url     : "{% url 'config:get_device_configs' %}"
            data    : {
                "sel_list" : sel_list
            }
            success : (xml) =>
                if parse_xml_response(xml)
                    @device_configs = $(xml).find("value[name='response']")
                    @load_configs()
    load_configs : () =>
        $.ajax
            url     : "{% url 'config:show_configs' %}"
            data    : {
                "mode" : "full"
            }
            success : (xml) =>
                if parse_xml_response(xml)
                    @configs = $(xml).find("value[name='response']")
                    @apply_filter(true)
                    if @callback
                        @callback()
    change_assoc_filter: (event) =>
        cur_el = $(event.target)
        @only_associated = cur_el.is(":checked")
        @apply_filter(true)
    apply_filter : (force_reload) =>
        if @filter_div
            cur_text = @filter_div.find("input#filter").attr("value")
        else
            cur_text = ""
        if (cur_text != @cur_filter) or force_reload
            @cur_filter = cur_text
            cur_re = new RegExp("^.*#{@cur_filter}.*$")
            disp_list = new Array()
            # get keys/pks for current filter
            @configs.find("config").each (idx, c_config) =>
                c_config = $(c_config)
                if c_config.attr("name").match(cur_re)
                    if @only_associated
                        conf_pk = c_config.attr("pk")
                        if @device_configs.find("device_config[config='#{conf_pk}']").length
                            disp_list.push(c_config.attr("key"))
                    else
                        disp_list.push(c_config.attr("key"))
            # not working, FIXME
            if (@show_list != disp_list) or force_reload
                # build fast display list
                @display_list = (new display_config(@configs.find("config[key='#{name}']")) for name in disp_list)
                @update_config_info(disp_list.length)
                cur_exp_list = @get_expand_list()
                @draw_tables()
                @restore_expansion(cur_exp_list)
            @show_list = disp_list
    get_expand_list : =>
        if @c_table
            ret_list = ($(cur_el).attr("id") for cur_el in @c_table.find("tr div[id*='__expand__'][class*='-1-s']"))
        else
            ret_list = []
        return ret_list
    update_config_info : (num_shown) =>
        num_defs = @configs.find("config").length
        if num_shown == num_defs
            info_str = "configs defined: #{num_defs}, all shown"
        else
            info_str = "configs defined: #{num_defs}, #{num_shown} shown"
        $("span#config_info").text(info_str)
    clear_filter : =>
        $("input#filter").val("")
        $("input#filter_assoc").removeAttr("checked")
        @only_associated = false
        @apply_filter(false)
    draw_tables : =>
        @selected = {}
        @meta_selected = {}
        # fill selected / meta selected
        if @device
            # single device path
            dev_pk = @device.attr("pk")
            @selected[dev_pk] = []
            @meta_selected[dev_pk] = []
        else
            # multi device path
            @devices.find("device[tree_selected='selected']").each (dev_idx, cur_dev) =>
                dev_pk = $(cur_dev).attr("pk")
                @selected[dev_pk] = []
                @meta_selected[dev_pk] = []
        @device_configs.find("device_config").each (idx, cur_dc) =>
            cur_dc = $(cur_dc)
            if cur_dc.attr("meta") == "1"
                @meta_selected[cur_dc.attr("device")].push(cur_dc.attr("config"))
            else
                @selected[cur_dc.attr("device")].push(cur_dc.attr("config"))
        @top_div.children().remove()
        c_table = $("<table>").attr({"id" : "config"}).addClass("devicelist")
        if @device
            # single device path
            c_table.append(@draw_device(@device))
        else
            # multi device path
            @devices.find("device_group").each (idx, cur_dg) =>
                cur_dg = $(cur_dg)
                new_tr = $("<tr>").attr({
                    "class"   : "ui-widget ui-widget-header devicegroup"
                })
                new_tr.append($("<th>").css({
                    "padding" : "5px",
                    "border"  : "1px solid black"
                }).attr({
                    "colspan" : "5"
                }).text("device group " + cur_dg.attr("name")))
                c_table.append(new_tr)
                cur_dg.find("devices device[tree_selected='selected'][meta_device='1']").each (meta_idx, meta_dev) =>
                    #console.log "meta", $(meta_dev)[0]
                    c_table.append(@draw_device($(meta_dev)))
                cur_dg.find("devices device[tree_selected='selected'][meta_device='0']").each (dev_idx, cur_dev) =>
                    #console.log "normal"
                    c_table.append(@draw_device($(cur_dev)))
        @top_div.append(c_table)
        @c_table = c_table
    draw_device : (d_el) =>
        dev_pk = d_el.attr("pk")
        dummy_div = $("<div>")
        line_prefix = d_el.attr("key")
        new_tr = $("<tr>").attr({
            "class" : "ui-widget ui-widget-header",
            "id"    : line_prefix
        })
        new_tr.append(get_expand_td(line_prefix, "config", "config", @toggle_config_line, if @device then true else false))
        new_tr.append($("<th>").attr({
            "class"   : "left",
            "colspan" : "4",
            "id"      : dev_pk,
        }))
        dummy_div.append(new_tr)
        cur_entries = 0
        run_idx = 1
        NUM_ROWS = 4
        NUM_LINES = parseInt((@display_list.length + NUM_ROWS - 1) / NUM_ROWS)
        MATR_SIZE = NUM_ROWS * NUM_LINES
        cur_ref_idx = 0
        for cur_idx in [0..MATR_SIZE - 1]
            cur_conf = @display_list[cur_ref_idx]
            if !cur_entries
                cur_tr = $("<tr>").attr({
                    "id" : "#{line_prefix}__config__#{run_idx}"
                })
                cur_tr.append(
                    $("<td>")
                )
            if cur_conf
                conf_pk = cur_conf.pk
                num_vars    = cur_conf.num_vars
                num_scripts = cur_conf.num_scripts
                num_checks  = cur_conf.num_checks
                text_td = $("<td>").attr(
                    "id" : "#{line_prefix}__config__#{conf_pk}"
                ).on(
                    "hover", @hover
                ).on(
                    "click", @change_config
                ).attr(
                    "title", cur_conf.title
                ).text(
                    #cur_conf.name + (if @device then "" else " (#{num_vars}, #{num_scripts}, #{num_checks})")
                    cur_conf.name + (" (#{num_vars}, #{num_scripts}, #{num_checks})")
                )
                if conf_pk in @meta_selected[dev_pk]
                    text_td.addClass("meta_selected")
                else if conf_pk in @selected[dev_pk]
                    text_td.addClass("selected")
            else
                text_td = $("<td>").text(".")
            cur_tr.append(text_td)
            # increase cur_ref_idx
            cur_ref_idx += NUM_LINES
            cur_entries++
            if cur_entries == 4
                cur_ref_idx += 1 - MATR_SIZE 
                dummy_div.append(cur_tr)
                cur_entries = 0
                run_idx += 1
            
        @update_device_info(dev_pk, new_tr.find("th"))
        # hide if in multi-device mode
        if not @device
            dummy_div.find("tr[id*='__config__']").hide()
        # beautify it
        dummy_div.find("tr[id*='__config__'] td").addClass("selectable")
        dummy_div.find("tr:even").addClass("even")
        dummy_div.find("tr:odd").addClass("odd")
        return dummy_div.children()
    hover: (event) ->
        target = $(event.target)
        if event.type == "mouseenter"
            target.addClass("highlight")
        else
            target.removeClass("highlight")
    restore_expansion : (exp_list) =>
        for cur_val in exp_list
            @toggle_config_line(cur_val.split("__")[0] + "__" + cur_val.split("__")[1], true, "config")
    toggle_config_line : (line_prefix, state, line_spec) =>
        conf_line = @c_table.find("tr[id='#{line_prefix}']")
        exp_line  = @c_table.find("tr[id^='#{line_prefix}__#{line_spec}']")
        if state
            exp_line.show()
            force_expansion_state(conf_line, true)
        else
            exp_line.hide()
            force_expansion_state(conf_line, false)
    update_device_info: (dev_pk, dev_th) =>
        selected = @selected[dev_pk].length
        meta_selected = @meta_selected[dev_pk].length
        if @device
            # single device path
            cur_dev = @device
        else
            # multi device path
            cur_dev = @devices.find("device[pk='#{dev_pk}']")
        is_meta = cur_dev.attr("meta_device") == "1"
        #if is_meta
        #    dev_th.addClass("meta_device")
        dev_str = (if is_meta then "[Meta] " else " ") + cur_dev.justtext()
        if selected
            dev_str = "#{dev_str}, #{selected} selected"
        if meta_selected
            dev_str = "#{dev_str}, #{meta_selected} via meta"
        if dev_th
            dev_th.text(dev_str)
        else
            @c_table.find("tr th[id='#{dev_pk}']").text(dev_str)
    change_config : (event) =>
        cur_td = $(event.target)
        lock_list = lock_elements(@c_table)
        $.ajax
            url  : "{% url 'config:alter_config_cb' %}"
            data : {
                "id"    : cur_td.attr("id")
                "value" : if (cur_td.hasClass("meta_selected") or cur_td.hasClass("selected")) then "0" else "1"
            },
            success : (xml) =>
                parse_xml_response(xml)
                res_xml = $(xml)
                conf_pk = res_xml.find("device_configs config").attr("pk")
                # remove selection
                for dev_pk of @selected
                    @selected[dev_pk]      = @selected[dev_pk].filter (val) -> val != conf_pk
                    @meta_selected[dev_pk] = @meta_selected[dev_pk].filter (val) -> val != conf_pk
                res_xml.find("devices device").each (xml_idx, cur_dev) =>
                    # deselect all checkboxes
                    cur_dev = $(cur_dev)
                    dev_pk = cur_dev.attr("pk")
                    cur_td = @c_table.find("td[id='dev__#{dev_pk}__config__#{conf_pk}']")
                    cur_td.removeClass("meta_selected").removeClass("selected")
                res_xml.find("device_configs device_config").each (xml_idx, cur_dc) =>
                    cur_dc = $(cur_dc)
                    dev_pk = cur_dc.attr("device")
                    if dev_pk of @selected
                        cur_td = @c_table.find("td[id='dev__#{dev_pk}__config__#{conf_pk}']")
                        if cur_dc.attr("meta") == "1"
                            cur_td.addClass("meta_selected")
                            @meta_selected[dev_pk].push(conf_pk)
                        else
                            cur_td.addClass("selected")
                            @selected[dev_pk].push(conf_pk)
                for dev_pk, sel_list of @selected
                    @update_device_info(dev_pk)
                unlock_elements(lock_list)

root.show_moncc_detail = (event, config_xml, moncc_key) ->
    new moncc_detail(event, config_xml, moncc_key).show()
    
class moncc_detail
    constructor: (@event, @configs_xml, @key) ->
        @cat_xml = @configs_xml.find("categories")
    show: () =>
        $.ajax
            url     : "{% url 'mon:moncc_info' %}"
            data    :
                "key"    : @key
            success : (xml) =>
                if parse_xml_response(xml)
                    @ajax_xml = $(xml).find("response")
                    @build_div()
                    @moncc_div.simplemodal
                        opacity      : 50
                        position     : [@event.pageY, @event.pageX]
                        autoResize   : true
                        autoPosition : true
                        onShow: (dialog) -> 
                            dialog.container.draggable()
                            $("#simplemodal-container").css("height", "auto")
    build_div: () =>
        moncc_xml = @configs_xml.find("mon_check_command[key='#{@key}']")
        @my_submitter = new submitter({
            master_xml : moncc_xml
        })
        moncc_div = $("<div>")
        moncc_div.append(
            $("<h3>").text("config #{moncc_xml.attr('name')}")
        )
        tabs_div = $("<div>").attr("id", "tabs")
        moncc_div.append(tabs_div)
        tabs_div.append(
            $("<ul>").append(
                $("<li>").append(
                    $("<a>").attr("href", "#template").text("Template / flags")
                )
            ).append(
                $("<li>").append(
                    $("<a>").attr("href", "#category").text("Category")
                )
            )
        )
        @moncc_div = moncc_div
        tabs_div.append(@template_div(moncc_xml))
        tabs_div.append(@category_div(moncc_xml))
        tabs_div.tabs()
    template_div: (moncc_xml) =>
        # parent div
        template_div = $("<div>").attr("id", "template")
        template_div.html(@ajax_xml.find("forms template_form").text())
        #template_div.uniform()
        template_div.find("select").addClass("chosen-select").chosen(
            width : "100%"
        )
        template_div.find("input, select").bind("change", @my_submitter.submit)
        return template_div
    category_div: (moncc_xml) =>
        cat_div = $("<div>").attr("id", "category")
        tree_div = $("<div>").attr("id", "cat_tree")
        cat_div.append(tree_div)
        new category_tree(tree_div, @configs_xml, moncc_xml, @cat_xml, "/mon")
        return cat_div

root.show_config_detail = (event, config_xml, config_key) ->
    new config_detail(event, config_xml, config_key).show()
    
class config_detail
    constructor: (@event, @configs_xml, @key) ->
        @cat_xml = @configs_xml.find("categories")
    show: () =>
        @build_div()
        @config_div.simplemodal
            #opacity      : 50
            #position     : [@event.pageY, @event.pageX]
            #autoResize   : true
            #autoPosition : true
            onShow: (dialog) -> 
                dialog.container.draggable()
                $("#simplemodal-container").css("height", "auto")
    build_div: () =>
        conf_xml = @configs_xml.find("config[key='#{@key}']")
        @my_submitter = new submitter({
            master_xml : conf_xml
        })
        conf_div = $("<div>")
        conf_div.append(
            $("<h3>").text("config #{conf_xml.attr('name')}")
        )
        tabs_div = $("<div>").attr("id", "tabs")
        conf_div.append(tabs_div)
        tabs_div.append(
            $("<ul>").append(
                $("<li>").append(
                    $("<a>").attr("href", "#parent").text("Parent")
                ),
                $("<li>").append(
                    $("<a>").attr("href", "#category").text("Category")
                )
            )
        )
        @config_div = conf_div
        tabs_div.append(@parent_div(conf_xml))
        tabs_div.append(@category_div(conf_xml))
        tabs_div.tabs()
    parent_div: (conf_xml) =>
        # parent div
        parent_div = $("<div>").attr("id", "parent")
        parent_div.append(
            create_input_el(conf_xml, "parent_config", conf_xml.attr("key"), {label : "Parent" , select_source : @configs_xml.find("config"), add_null_entry : "none", select_source_attribute : "name", master_xml : @configs_xml})
        )
        return parent_div
    category_div: (conf_xml) =>
        cat_div = $("<div>").attr("id", "category")
        tree_div = $("<div>").attr("id", "cat_tree")
        cat_div.append(tree_div)
        new category_tree(tree_div, @configs_xml, conf_xml, @cat_xml, "/config")
        return cat_div
    
String.prototype.toTitle = () ->
    return @.replace(/\w\S*/g, (txt) ->
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
    )
        
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
                noty({"text" : cur_mes.text()})
            else if cur_level == 30
                noty({"text" : cur_mes.text(), "type" : "warning"})
            else
                noty({"text" : cur_mes.text(), "type" : "error", "timeout" : false})
    else
        if xml != null
            noty({"text" : "error parsing response", "type" : "error", "timeout" : false})
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
create_dict_unserialized = (top_el, id_prefix, use_name=false, django_save=false) ->
    in_list = top_el.find("input[id^='#{id_prefix}'], select[id^='#{id_prefix}'], textarea[id^='#{id_prefix}']")
    out_dict = {}
    in_list.each (idx, cur_el) ->
        cur_el = $(cur_el)
        if use_name
            key = cur_el.attr("name")
        else
            key = cur_el.attr("id")
        if cur_el.prop("tagName") == "TEXTAREA"
            if cur_el.is(":visible")
                out_dict[key] = cur_el.val()
            else
                out_dict[key] = cur_el.text()
        else if cur_el.is(":checkbox")
            if django_save
                if cur_el.is(":checked")
                    out_dict[key] = "1"
            else
                out_dict[key] = if cur_el.is(":checked") then "1" else "0"
        else if cur_el.prop("tagName") == "SELECT" and cur_el.attr("multiple")
            sel_field = []
            cur_el.find("option:selected").each (idx, opt_field) ->
                sel_field.push($(opt_field).attr("value"))
            if django_save
                out_dict[key] = sel_field
            else
                out_dict[key] = sel_field.join("::")
        else
            out_dict[key] = cur_el.attr("value")
    return out_dict
    
create_dict = (top_el, id_prefix, use_name=false, django_save=false) ->
    out_dict = create_dict_unserialized(top_el, id_prefix, use_name, django_save)
    return $.param(out_dict, traditional=true)

replace_xml_element = (master_xml, xml) ->
    # replace element in master_xml
    xml.find("value[name='object'] > *").each (idx, new_el) ->
        new_el = $(new_el)
        if master_xml
            master_xml.find("[key='" + new_el.attr("key") + "']").replaceWith(new_el)

class submitter
    constructor: (kwargs) ->
        kwargs = kwargs ? {}
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
                        @callback(cur_el)
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
                    cur_el.text(get_xml_value(xml, "original_value"))
                else if $(cur_el).is(":checkbox")
                    if get_xml_value(xml, "original_value") == "False"
                        cur_el.removeAttr("checked")
                    else
                        cur_el.attr("checked", "checked")
                else
                    orig_val = get_xml_value(xml, "original_value")
                    if cur_el.is("select")
                        if orig_val = "None"
                            orig_val = "0"
                        # check for chosen
                        if cur_el.next().attr("id") == cur_el.attr("id") + "_chosen"
                            cur_el.val(orig_val).trigger("chosen:updated")
                        else
                            cur_el.val(orig_val)
                    else
                        cur_el.val(orig_val)
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

class password_struct
    constructor: (@event) ->
        @handle_pwd()
    handle_pwd: =>
        @target = $(event.target)
        top_div = $("<div>")
        $.ajax
            url     : "{% url 'user:get_password_form' %}"
            success : (xml) =>
                if parse_xml_response(xml)
                    in_form = $(xml).find("value[name='form']").text()
                    top_div.append(in_form)
                    #top_div.uniform()
                    top_div.append(
                        $("<h4>").append(
                            $("<span>").attr
                                id : "error"
                        )
                    )
                    $.simplemodal(
                        top_div,
                        {
                            onShow : (dialog) =>
                                dialog.data.find("input[type='password']").bind("change", (event) =>
                                    @check_passwd(dialog)
                                )
                                dialog.data.find("input[type='button']").bind("click", (event) =>
                                    cur_id = $(event.target).attr("id")
                                    @check_passwd(dialog, cur_id == "button-id-leave")
                                )
                            onClose : (dialog) =>
                                pwd0 = dialog.data.find("input#id_password1").val()
                                pwd1 = dialog.data.find("input#id_password1").val()
                                $.simplemodal.close()
                                if pwd0 == pwd1
                                    if pwd0.length < 4
                                        @target.val("")
                                    else
                                        @target.val(pwd0).trigger("change")
                                else
                                    @target.val("")
                        }
                    )
    check_passwd: (dialog, leave_on_ok=false) =>
        stat_h4 = dialog.data.find("span#error")
        stat_h4.text("password empty")
        pwd0 = dialog.data.find("input#id_password1").val()
        pwd1 = dialog.data.find("input#id_password2").val()
        if pwd0 == pwd1
            if not pwd0 or not pwd1
                stat_h4.attr("class", "warn").text("password empty")
            else
                if pwd0.length < 4
                    stat_h4.attr("class", "error").text("password too short")
                else
                    stat_h4.attr("class", "ok").text("password OK")
                    if leave_on_ok
                        $.simplemodal.close()
        else
            stat_h4.attr("class", "error").text("password mismatch")

enter_password = (event) ->
    new password_struct(event)
    
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
        else
            if kwargs.submitter
                new_el.bind("change", kwargs.submitter.submit)
            else
                new_el.bind("change", (event) ->
                    submit_change($(event.target), kwargs.callback, kwargs.modify_data_dict, kwargs.modify_data_dict_opts, kwargs.master_xml)
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
    if kwargs.chosen
        new_el.chosen(
            kwargs.chosen
        )
        #new_el.show()
    return dummy_div.children()

store_user_var = (var_name, var_value, var_type="str") -> 
    $.ajax
        url  : "{% url 'user:set_user_var' %}"
        data : 
            key   : var_name
            value : var_value
            type  : var_type
            
load_user_var = (var_name) ->
    ret_dict = {}
    $.ajax
        url     : "{% url 'user:get_user_var' %}"
        data    :
            var_name : var_name
        async   : false
        success : (xml) ->
            if parse_xml_response(xml)
                #console.log xml
                $(xml).find("user_variable").each (idx, cur_var) =>
                    cur_var = $(cur_var)
                    var_name = cur_var.attr("name")
                    var_type = cur_var.attr("type")
                    switch var_type
                        when "s"
                            ret_dict[var_name] = cur_var.text()
                        when "i"
                            ret_dict[var_name] = parseInt(cur_var.text())
                        when "b"
                            ret_dict[var_name] = if cur_var.text() == "True" then true else false
                    # very important for CS
                    true
    return ret_dict

root.get_value                = get_value
root.set_value                = set_value
root.parse_xml_response       = parse_xml_response
root.lock_elements            = lock_elements
root.unlock_elements          = unlock_elements
root.get_expand_td            = get_expand_td
root.toggle_config_line_ev    = toggle_config_line_ev
root.get_xml_value            = get_xml_value
root.replace_xml_element      = replace_xml_element
root.submit_change            = submit_change
root.force_expansion_state    = force_expansion_state
root.create_input_el          = create_input_el
root.submitter                = submitter
root.config_table             = config_table
root.enter_password           = enter_password
root.store_user_var           = store_user_var
root.load_user_var            = load_user_var
root.create_dict              = create_dict
root.create_dict_unserialized = create_dict_unserialized
root.my_ajax_struct           = my_ajax_struct

{% endinlinecoffeescript %}

</script>
