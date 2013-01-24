{% load coffeescript %}

<script type="text/javascript">

String.prototype.toTitle = function () {
    return this.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
};

AJAX_UUID = 0;
AJAX_DICT = new Object();

$.ajaxSetup({
    type       : "POST",
    timeout    : 50000,
    dataType   : "xml",
    beforeSend : function(xhr, settings) {
        xhr.inituuid = AJAX_UUID;
        AJAX_UUID++;
        AJAX_DICT[xhr.inituuid] = {
            "state" : "pending",
            "start" : new Date()
        };
        var ai_div = $("div#ajax_info");
        if (! ai_div.find("ul").length) {
            ai_div.append($("<ul>"));
        };
        ai_ul = ai_div.find("ul");
        ai_ul.append($("<li>").attr({
            "id" : xhr.inituuid
        }).text("pending..."));
    },
    complete   : function(xhr, textstatus) {
        AJAX_DICT[xhr.inituuid]["state"] = "done";
        AJAX_DICT[xhr.inituuid]["runtime"] = new Date() - AJAX_DICT[xhr.inituuid]["start"];
        var ai_div = $("div#ajax_info");
        ai_div.find("li#" + xhr.inituuid).remove();
    }
});

{% inlinecoffeescript %}

root = exports ? this

root.draw_ds_tables = (t_div, master_array, master_xml=undefined) ->
    t_div.children().remove()
    t_div.append (value.draw_table(master_xml, master_array) for key, value of master_array)
    t_div.accordion
        heightStyle : "content"
        collapsible : true

class draw_setup
    constructor: (@name, @postfix, @xml_name, @create_url, @delete_url, @draw_array, @kwargs={}) ->
        @xml_name_plural = if this.xml_name.match(///s$///) then this.xml_name + "es" else this.xml_name + "s"
        @required_xml = @kwargs.required_xml or []
        @lock_div = @kwargs.lock_div or ""
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
    clean: ->
        @drawn      = false
        @table_div  = undefined
        @info_h3    = undefined
        @master_xml = undefined
    redraw_tables: =>
        (value.draw_table() for key, value of @master_array)
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
            @info_h3 = $("<h3>").attr
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
                    search_str = ref_obj.xml_name_plural + " " + ref_obj.xml_name
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
            @info_h3.text("parent objects missing for " + @name + ": " + missing_objects.join(", "))
        @drawn = draw
        if not @table_div
            @table_div = table_div
            @update_table_info()
            dummy_div = $("<div>").append(@info_h3).append(table_div)
            return dummy_div.children()
        else
            @update_table_info()
    first_draw: (p_table) ->
        if @timer_callback
            $(document).everyTime(@timer_timeout * 1000, "table_draw_timer", (idx) =>
                @timer_callback(@)
            )
        p_table.append(@draw_head_line())
        if @create_url
            p_table.append(@draw_line())
        @master_xml.find(@xml_name_plural + " " + @xml_name).each (index, element) =>
            p_table.append(@draw_line($(element)))
        @info_h3.text(@name + " (").append(
            $("<span>").attr(id : "info__" + @postfix).text("---")
        ).append($("<span>").text(")"))
    redraw: () ->
        @table_div.find("table").find("tr[id]").each (index, cur_tr) =>
            $(cur_tr).find("select").each (index, cur_sel) =>
                for cur_di in @draw_array
                    cur_re = new RegExp("__" + cur_di.name + "$")
                    if $(cur_sel).attr("id").match(cur_re)
                        cur_di.sync_select_from_xml($(cur_sel))
    redraw_line: (line_id, new_xml) ->
        # todo: replace master_xml with new element
        cur_line = @table_div.find("table").find("tr[id='#{line_id}']")
        cur_line.replaceWith(@draw_line(new_xml))
        @recolor_table()
    append_new_line: (cur_el, new_xml) ->
        @table_div.find("table:first").append(@draw_line(new_xml))
        @update_table_info()
    delete_line: (cur_el) ->
        del_tr = cur_el.parents("tr:first")
        if del_tr.attr("id")
            @table_div.find("table:first tr#" + del_tr.attr("id")).remove()
        else
            del_tr.remove()
        @update_table_info()
    update_table_info: () ->
        @info_h3.find("span#info__" + @postfix).text(@master_xml.find(@xml_name_plural + " " + @xml_name).length)
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
        line_prefix = @postfix + "__" + xml_pk
        cur_dl = new draw_line(@)
        return cur_dl.draw(line_prefix, xml_el, xml_pk)
    create_delete_element: (event) =>
        cur_el = $(event.target)
        el_id  = cur_el.attr("id")
        lock_list = if @lock_div then lock_elements($("div#" + @lock_div)) else undefined
        if el_id.match(///new$///)
            $.ajax
                url     : @create_url
                data    : create_dict(@table_div, el_id)
                success : (xml) =>
                    if parse_xml_response(xml)
                        new_element = $(xml).find(@xml_name)
                        @master_xml.find(@xml_name_plural).append(new_element)
                        @append_new_line(cur_el, new_element)
                        for clear_el in (@draw_array.filter (cur_di) -> cur_di.clear_after_create)
                            @table_div.find("#" + el_id + "__" + clear_el.name).val("")
                        @redraw_tables()
                    @unlock_elements(lock_list)
        else
            if confirm("really delete " + @name + " ?")
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
    draw: (line_prefix, xml_el, xml_pk) =>
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
            n_line.append(
                $("<td>").append(
                    $("<input>").attr(
                        "type"  : "button"
                        "value" : if xml_pk == "new" then "create" else "delete"
                        "id"    : line_prefix)
                ).bind("click", (event) =>
                    @cur_ds.create_delete_element(event)
                )
            )
        # collapse if requested
        if not @expand
            dummy_div.children()[1..].hide()
        return dummy_div.children()

class draw_info
    constructor: (@name, @kwargs={}) ->
        @label = @kwargs.label or @name.toTitle()
        @span = @kwargs.span or 1
        for attr_name in ["size", "default", "select_source", "boolean", "min", "max", "ro",
        "button", "change_cb", "trigger", "draw_result_cb", "draw_conditional",
        "number", "manytomany", "add_null_entry", "newline", "cspan", "show_label", "group",
        "css", "select_source_attribute", "password", "keep_td", "clear_after_create"]
            @[attr_name] = @kwargs[attr_name] ? undefined
        @size = @kwargs.size or undefined
    get_kwargs: () ->
        kwargs = {new_default : @default}
        for attr_name in ["size", "select_source", "boolean", "min", "max", "ro", "button", "change_cb",
            "draw_result_cb", "trigger",
            "number", "manytomany", "add_null_entry", "css", "select_source_attribute", "password"]
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
    draw: (cur_line, xml_el, line_prefix) =>
        kwargs = @get_kwargs()
        if not cur_line.cur_ds.create_url
            kwargs.ro = true
        if (@trigger and xml_el) or not @trigger
            if @draw_conditional
                draw_el = @draw_conditional(xml_el)
            else
                draw_el = true
        else
            draw_el = false
        if draw_el
            new_els = create_input_el(xml_el, @name, line_prefix, kwargs)
        else
            new_els = []
        return new_els
    create_draw_result: (new_el) ->
        return new draw_result(@name, @group, new_el)

class draw_collapse extends draw_info
    constructor: (name="collapse", kwargs={}) ->
        super(name, kwargs)
    draw: (cur_line, xml_el, line_prefix) =>
        cur_line.expand = @default ? true
        return get_expand_td(line_prefix, "exp", undefined, @expand_cb, @default ? true)
    expand_cb: (line_prefix, state, name) =>
        if state
            @draw_setup.table_div.find("tr[id^='#{line_prefix}']")[1..].show()
        else
            @draw_setup.table_div.find("tr[id^='#{line_prefix}']")[1..].hide()
        
class draw_link extends draw_info
    constructor: (name="link", kwargs={}) ->
        super(name, kwargs)
    draw: (cur_line, xml_el, line_prefix) =>
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
        el_value = cur_el.text()
    else if cur_el.prop("tagName") == "SELECT" and cur_el.attr("multiple")
        el_value = ($(element).attr("value") for element in cur_el.find("option:selected")).join("::")
    else
        el_value = cur_el.attr("value")
    return el_value;

set_value = (el_id, el_value) ->
    $("#" + el_id).val(el_value)

root.get_value = get_value
root.set_value = set_value
root.draw_setup = draw_setup
root.draw_info  = draw_info
root.draw_link  = draw_link
root.draw_collapse  = draw_collapse

{% endinlinecoffeescript %}

parse_xml_response = function(xml, min_level) {
    var success = false;
    // parse xml response from server
    if ($(xml).find("response header").length) {
        var ret_state = $(xml).find("response header").attr("code");
        if (parseInt(ret_state) < (min_level ? min_level : 40)) {
            // return true if we can parse the header and ret_code <= 40 (less than error)
            success = true;
        };
        $(xml).find("response header messages message").each(function() {
            var cur_mes = $(this);
            var cur_level = parseInt($(cur_mes).attr("log_level"));
            if (cur_level < 30) {
                $.jnotify($(cur_mes).text());
            } else if (cur_level == 30) {
                $.jnotify($(cur_mes).text(), "warning");
            } else {
                $.jnotify($(cur_mes).text(), "error", true);
            };
        });
    } else {
        $.jnotify("error parsing response", "error", true);
    };
    return success;
};

handle_ajax_ok = function(xml, ok_func) {
    if ($(xml).find("err_str").length) {
        var ret_value = false;
        alert($(xml).find("err_str").attr("value"));
    } else {
        var ret_value = true;
        if (ok_func == undefined) {
            if ($(xml).find("ok_str").length) {
                alert($(xml).find("ok_str").attr("value"));
            } else {
                alert("OK");
            }
        } else {
            ok_func(xml);
        }
    }
    return ret_value;
};

handle_ajax_error = function(xhr, status, except) {
    //alert(xhr.status + "," + status + ", " + except);
    if (status == "timeout") {
        alert("timeout");
    } else {
        if (xhr.status ) {
            // if status is != 0 an error has occured
            alert("*** " + status + " ***\nxhr.status : " + xhr.status + "\nxhr.statusText : " + xhr.statusText);
        }
    }
    return false;
}

function get_xml_value(xml, key) {
    var ret_value = undefined;
    $(xml).find("response values value[name='" + key + "']").each(function() {
        var value_xml =$(this);
        if ($(value_xml).attr("type") == "integer") {
            ret_value = parseInt($(value_xml).text());
        } else {
            ret_value = $(value_xml).text();
        };
    });
    return ret_value;
};

// lock all active input elements
function lock_elements(top_el) {
    var el_list = top_el.find("input:enabled", "select:enabled");
    el_list.attr("disabled", "disabled");
    return el_list;
};

// unlock list of elements
function unlock_elements(el_list) {
    el_list.removeAttr("disabled");
};

// create a dictionary from a list of elements
function create_dict(top_el, id_prefix) {
    var in_list = top_el.find("input[id^='" + id_prefix + "'], select[id^='" + id_prefix + "'], textarea[id^='" + id_prefix + "']");
    var out_dict = {};
    in_list.each(function(idx, value) {
        var cur_el = $(this);
        if (cur_el.prop("tagName") == "TEXTAREA") {
            out_dict[cur_el.attr("id")] = cur_el.text();
        } else if (cur_el.is(":checkbox")) {
            out_dict[cur_el.attr("id")] = cur_el.is(":checked") ? "1" : "0";
        } else if (cur_el.prop("tagName") == "SELECT" && cur_el.attr("multiple")) {
            var sel_field = [];
            cur_el.find("option:selected").each(function(idx) {
                sel_field.push($(this).attr("value"));
            });
            out_dict[cur_el.attr("id")] = sel_field.join("::");
        } else {
            out_dict[cur_el.attr("id")] = cur_el.attr("value");
        };
    });
    return out_dict;
};

function replace_xml_element(master_xml, xml) {
    // replace element in master_xml
    xml.find("value[name='object'] > *").each(function() {
        var new_el = $(this);
        master_xml.find("[key='" + new_el.attr("key") + "']").replaceWith(new_el);
    });
};

function submit_change(cur_el, callback, modify_data_dict, modify_data_dict_opts, master_xml) {
    var is_textarea = false;
    var el_value = get_value(cur_el);
    reset_value = false;
    if (cur_el.attr("type") == "password") {
        var check_pw = prompt("Please reenter password", "");
        if (check_pw != el_value) {
            alert("Password mismatch");
            return;
        } else {
            reset_value = true;
        };
    };
    var data_field = {
        "id"       : cur_el.attr("id"),
        "checkbox" : cur_el.is(":checkbox"),
        "value"    : el_value
    };
    if (modify_data_dict !== undefined) {
        modify_data_dict(data_field);
    };
    if (data_field.lock_list) {
        lock_list = $(data_field.lock_list.join(", ")).attr("disabled", "disabled");
    } else {
        lock_list = undefined;
    };
    $.ajax({
        url  : "{% url base:change_xml_entry %}",
        data : data_field,
        success : function(xml) {
            if (parse_xml_response(xml)) {
                replace_xml_element(master_xml, $(xml));
                if (callback != undefined && typeof callback == "function") {
                    callback(cur_el);
                } else {
                    // set values
                    $(xml).find("changes change").each(function() {
                        var cur_os = $(this);
                        set_value(cur_os.attr("id"), cur_os.text());
                    });
                    if (reset_value) cur_el.val("");
                };
            } else {
                <!-- set back to previous value -->
                if (is_textarea) {
                    $(cur_el).text(get_xml_value(xml, "original_value"));
                } else {
                    $(cur_el).attr("value", get_xml_value(xml, "original_value"));
                };
                if (reset_value) cur_el.val("");
            };
            if (lock_list) unlock_elements(lock_list);
        }
    })
};

function in_array(in_array, s_str) {
    var res = false;
    for (var idx=0 ; idx < in_array.length; idx++) {
        if (in_array[idx] == s_str) {
            res = true;
            break;
        };
    };
    return res;
};

// get expansion list
function get_expand_td(line_prefix, name, title, cb_func, initial_state) {
    if (initial_state === undefined) initial_state = false;
    return exp_td = $("<td>").append(
        $("<div>").attr({
            "class"   : initial_state ? "ui-icon ui-icon-triangle-1-s leftfloat" : "ui-icon ui-icon-triangle-1-e leftfloat",
            "id"      : line_prefix + "__expand__" + name,
            "title"   : title === undefined ? "show " + name : title
        })
    ).append(
        $("<span>").attr({
            "id"    : line_prefix + "__expand__" + name + "__info",
            "title" : title === undefined ? "show " + name : title
        }).text(name)
    ).bind("click", function(event) { toggle_config_line_ev(event, cb_func) ; }).mouseover(function () { $(this).addClass("highlight"); }).mouseout(function() { $(this).removeClass("highlight"); });
};

function force_expansion_state(cur_tr, state) {
    var cur_el = cur_tr.find("div[id*='__expand__']");
    cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s");
    if (state) {
        cur_el.addClass("ui-icon-triangle-1-s");
    } else {
        cur_el.addClass("ui-icon-triangle-1-e");
    }
}

function toggle_config_line_ev(event, cb_func) {
    // get div-element
    var cur_el = $(event.target);
    if (cur_el.prop("tagName") != "TD") cur_el = cur_el.parent("td");
    cur_el = cur_el.children("div");
    var cur_class = cur_el.attr("class");
    var name = cur_el.attr("id").split("__").pop();
    var line_prefix = /^(.*)__expand__.*$/.exec(cur_el.attr("id"))[1];
    if (cur_class.match(/-1-e/)) {
        cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s");
        cur_el.addClass("ui-icon-triangle-1-s");
        cb_func(line_prefix, true, name);
    } else {
        cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s");
        cur_el.addClass("ui-icon-triangle-1-e");
        cb_func(line_prefix, false, name);
    }
};

function create_input_el(xml_el, attr_name, id_prefix, kwargs) {
    var dummy_div = $("<div>");
    kwargs = kwargs || {};
    if (kwargs["label"]) {
        dummy_div.append($("<label>").attr({"for" : attr_name}).text(kwargs["label"]));
    };
    if (kwargs["select_source"] === undefined) {
        if (kwargs.button) {
            // manual callback
            var new_el = $("<input>").attr({
                "type"  : "button",
                "id"    : id_prefix + "__" + attr_name
            });
            new_el.val(attr_name);
        } else if (kwargs.boolean) {
            // checkbox input style
            var new_el = $("<input>").attr({
                "type"  : "checkbox",
                "id"    : id_prefix + "__" + attr_name
            });
            if ((xml_el && xml_el.attr(attr_name) == "1") || (! xml_el && kwargs.new_default)) new_el.prop("checked", true);
        } else if (kwargs.textarea) {
            // textarea input style
            var new_el = $("<textarea>").attr({
                "id"    : id_prefix + "__" + attr_name
            }).text(xml_el === undefined ? (kwargs.new_default || "") : xml_el.attr(attr_name));
        } else {
            // text input style
            if (kwargs.ro) {
                // experimental, FIXME, too many if-levels
                var new_el = $("<span>").attr({
                    "id"    : id_prefix + "__" + attr_name
                }).text(xml_el === undefined ? (kwargs.new_default || (kwargs.number ? "0" : "")) : xml_el.attr(attr_name));
            } else {
                var new_el = $("<input>").attr({
                    "type"  : kwargs.password ? "password" : (kwargs.number ? "number" : "text"),
                    "id"    : id_prefix + "__" + attr_name,
                    "value" : xml_el === undefined ? (kwargs.new_default || (kwargs.number ? "0" : "")) : xml_el.attr(attr_name)
                });
            };
        };
        // copy attributes
        var attr_list = ["size", "min", "max"];
        for (idx=0 ; idx < attr_list.length; idx ++) {
            var attr_name = attr_list[idx];
            if (kwargs.hasOwnProperty(attr_name)) {
                new_el.attr(attr_name, kwargs[attr_name]);
            };
        }
    } else {
        // select input
        if (typeof(kwargs.select_source) == "string") {
            var sel_source = kwargs.master_xml.find(kwargs.select_source);
        } else if (typeof(kwargs.select_source) == "function") {
            var sel_source = kwargs.select_source(xml_el, kwargs);
        } else {
            var sel_source = kwargs.select_source;
        };
        if (sel_source.length || kwargs.add_null_entry || kwargs.add_extra_entry) {
            var new_el = $("<select>").attr({
                "id"    : id_prefix + "__" + attr_name
            });
            if (kwargs["css"]) {
                $.each(kwargs["css"], function(key, value) {
                    new_el.css(key, value);
                });
            };
            if (kwargs.manytomany) {
                var sel_val = xml_el === undefined ? [] : xml_el.attr(attr_name).split("::");
                new_el.attr({
                    "multiple" : "multiple",
                    "size"     : 5
                });
            } else {
                var sel_val = xml_el === undefined ? "0" : xml_el.attr(attr_name);
                new_el.val(sel_val);//attr("value", sel_val);
            };
            if (kwargs.add_null_entry) {
                new_el.append($("<option>").attr({"value" : "0"}).text(kwargs.add_null_entry));
            };
            if (kwargs.add_extra_entry) {
                new_el.append($("<option>").attr({"value" : kwargs.extra_entry_id || "-1"}).text(kwargs.add_extra_entry));
            };
            sel_source.each(function() {
                var cur_ns = $(this);
                var new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")});
                if (kwargs.select_source_attribute === undefined) {
                    new_opt.text(cur_ns.text());
                } else {
                    new_opt.text(cur_ns.attr(kwargs.select_source_attribute));
                };
                if (kwargs.manytomany) {
                    if (in_array(sel_val, cur_ns.attr("pk"))) new_opt.attr("selected", "selected");
                } else {
                    if (cur_ns.attr("pk") == sel_val) new_opt.attr("selected", "selected");
                };
                if (cur_ns.attr("data-image")) {
                    new_opt.attr("data-image", cur_ns.attr("data-image"));
                };
                new_el.append(new_opt);
            });
            //new_el.msDropdown();
        } else {
            if (kwargs.ignore_missing_source) {
                var new_el = $("<span>");
            } else {
                var new_el = $("<span>").addClass("error").text("no " + attr_name + " defined");
            };
        };
    };
    if (xml_el !== undefined && (kwargs.bind === undefined || kwargs.bind)) {
        if (kwargs.change_cb) {
            if (kwargs.button) {
                new_el.bind("click", kwargs.change_cb);
            } else {
                new_el.bind("change", kwargs.change_cb);
            };
            new_el.bind("change", kwargs.change_cb);
        } else {
            new_el.bind("change", function(event) {
                submit_change($(event.target), kwargs.callback, kwargs.modify_data_dict, kwargs.modify_data_dict_opts, kwargs.master_xml);
            })
        };
    } else if (kwargs.change_cb) {
        new_el.bind("change", kwargs.change_cb);
    };
    if (kwargs && kwargs.ro && new_el.get(0).tagName != "SPAN" && ! kwargs.trigger) {
        new_el.attr("disabled", "disabled");
    };
    dummy_div.append(new_el);
    if (kwargs && kwargs.draw_result_cb) dummy_div = kwargs.draw_result_cb(xml_el, dummy_div);
    return dummy_div.children();
};

</script>
