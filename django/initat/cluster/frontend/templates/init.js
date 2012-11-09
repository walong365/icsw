<script type="text/javascript">

String.prototype.toTitle = function () {
    return this.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
};

$.ajaxSetup({
    type     : "POST",
    timeout  : 50000,
    dataType : "xml"
});


function draw_setup(name, postfix, xml_name, create_url, delete_url, draw_array, kwargs) {
    this.name = name;
    this.postfix = postfix;
    this.xml_name = xml_name;
    // plural, plural(s) = ses and not ss (!)
    this.xml_name_plural = this.xml_name.match(/s$/) ? this.xml_name + "es" : this.xml_name + "s";
    this.create_url = create_url;
    this.delete_url = delete_url;
    this.required_xml = kwargs && (kwargs.required_xml || []) || [];
    this.lock_div = kwargs && (kwargs.lock_div || "") || "";
    this.drawn = false;
    this.draw_array = draw_array;
    for (var idx=0; idx < draw_array.length ; idx++) {
        draw_array[idx].draw_setup = this;
    };
    this.table_div = undefined;
    function draw_table() {
        if (this.table_div) {
            var table_div = this.table_div;
        } else {
            var table_div = $("<div>").attr({"id" : this.postfix});
            table_div.append($("<h3>").attr({"id" : this.postfix}));
            table_div.append($("<table>").attr({"id" : this.postfix}));
        };
        var draw = true;
        var cur_ds = this;
        var missing_objects = []
        if (cur_ds.required_xml) {
            for (var idx=0; idx < cur_ds.required_xml.length; idx++) {
                var cur_req = cur_ds.required_xml[idx];
                var ref_obj = master_array[cur_req];
                if (ref_obj) {
                    var search_str = ref_obj.xml_name_plural + " " + ref_obj.xml_name;
                } else {
                    var search_str = cur_req + "s " + cur_req;
                };
                if (! MASTER_XML.find(search_str).length) {
                    missing_objects.push(ref_obj ? ref_obj.name : cur_req);
                    draw = false;
                };
            };
        };
        var p_table = table_div.find("table");
        var info_h3 = table_div.find("h3#" + this.postfix);
        if (draw) {
            if (cur_ds.drawn) {
                p_table.find("tr[id]").each(function() {
                    var cur_tr = $(this);
                    cur_tr.find("select").each(function() {
                        var cur_sel = $(this);
                        for (idx=0 ; idx < cur_ds.draw_array.length; idx++) {
                            var cur_di = cur_ds.draw_array[idx];
                            var cur_re = new RegExp(cur_di.name + "$");
                            if (cur_sel.attr("id").match(cur_re)) {
                                if (cur_di.select_source) {
                                    sync_select_from_xml(cur_sel, cur_di);
                                };
                            };
                        };
                    });
                });
            } else {
                p_table.append(draw_line(cur_ds));
                MASTER_XML.find(this.xml_name_plural + " " + this.xml_name).each(function() {
                    p_table.append(draw_line(cur_ds, $(this)));
                });
                info_h3.text(cur_ds.name + " (").append(
                    $("<span>").attr({"id" : "info__" + this.postfix}).text("---")
                ).append($("<span>").text(")"));
                update_table_info(this, info_h3);
            };
        } else {
            if (this.drawn) {
                p_table.children().remove();
            };
            info_h3.text("parent objects missing for " + cur_ds.name + ": " + missing_objects.join(", "));
        };
        table_div.append(p_table);
        this.drawn = draw;
        this.table_div = table_div;
        return table_div;
    };
    this.draw_table = draw_table;
};

function draw_info(name, kwargs) {
    this.name = name;
    this.label = kwargs && (kwargs.label || name.toTitle()) || name.toTitle();
    this.span = kwargs && (kwargs.span || 1) || 1;
    var attr_list = ["size", "default", "select_source", "boolean", "min", "max",
        "number", "manytomany", "add_null_entry", "newline", "cspan", "show_label", "group"];
    for (idx=0 ; idx < attr_list.length; idx ++) {
        var attr_name = attr_list[idx];
        if (kwargs && kwargs.hasOwnProperty(attr_name)) {
            this[attr_name] = kwargs[attr_name];
        } else {
            this[attr_name] = undefined;
        };
    };
    this.size = kwargs && kwargs.size || undefined;
    function get_kwargs() {
        var attr_list = ["size", "select_source", "boolean", "min", "max",
            "number", "manytomany", "add_null_entry"];
        var kwargs = {new_default : this.default};
        for (idx=0 ; idx < attr_list.length; idx ++) {
            var attr_name = attr_list[idx];
            kwargs[attr_name] = this[attr_name];
        };
        if (this.show_label) {
            kwargs["label"] = this["label"];
        };
        if (this.group) {
            kwargs.modify_data_dict = this["modify_data_dict"];
            kwargs.modify_data_dict_opts = this;
        };
        
        return kwargs;
    };
    function modify_data_dict(in_dict, cur_di) {
        var other_list = [];
        for (idx = 0; idx < cur_di.draw_setup.draw_array.length; idx++) {
            var other_di = cur_di.draw_setup.draw_array[idx];
            if (other_di.group == cur_di.group && other_di.name != cur_di.name) {
                other_list.push(other_di.element.attr("id"));
                in_dict[other_di.element.attr("id")] = get_value(other_di.element);
            };
        };
        in_dict["other_list"] = other_list.join("::");
    };
    this.modify_data_dict = modify_data_dict;
    this.get_kwargs = get_kwargs;
};

function draw_line(cur_ds, xml_el) {
    // cur_ds .... draw_setup
    // xml_el .... xml or undefined
    var dummy_div = $("<div>");
    if (xml_el === undefined) {
        var xml_pk = "new";
        var head_line = $("<tr>").attr({
            "class" : "ui-widget-header ui-widget"
        });
        var cur_array = cur_ds.draw_array;
        var cur_span = 1;
        for (var idx=0; idx < cur_array.length ; idx++) {
            var cur_di = cur_array[idx];
            if (cur_di.newline) break;
            cur_span--;
            if (! cur_span) {
                var new_td = $("<th>").attr({"colspan" : cur_di.span}).text(cur_di.label);
                cur_span += cur_di.span;
            };
            head_line.append(new_td);
        };
        head_line.append($("<th>").text("action"));
        dummy_div.append(head_line);
    } else {
        var xml_pk = xml_el.attr("pk");
    };
    var line_prefix = cur_ds.postfix + "__" + xml_pk;
    var n_line = $("<tr>").attr({
        "id"    : line_prefix,
        "class" : "ui-widget"
    });
    dummy_div.append(n_line);
    var cur_array = cur_ds.draw_array;
    var cur_line = n_line;
    for (var idx=0; idx < cur_array.length ; idx++) {
        var cur_di = cur_array[idx];
        if (cur_di.newline) {
            var cur_line = $("<tr>").attr({
                "id"    : line_prefix,
                "class" : "ui-widget"
            });
            dummy_div.append(cur_line);
        };
        var new_td = $("<td>");
        if (cur_di.cspan) {
            new_td.attr({"colspan" : cur_di.cspan});
        };
        cur_line.append(new_td);
        var new_els = create_input_el(xml_el, cur_di.name, line_prefix, cur_di.get_kwargs());
        cur_di.element = new_els.last();
        new_td.append(new_els);
    };
    n_line.append(
        $("<td>").append($("<input>").attr({
            "type"  : "button",
            "value" : xml_pk == "new" ? "create" : "delete",
            "id"    : line_prefix
        }).bind("click", function(event) { create_delete_element(event, cur_ds); })
    ));
    return dummy_div.children();
};

function redraw_tables() {
    for (var key in master_array) {
        master_array[key].draw_table();
    };
};

function update_table_info(cur_ds, info_h3) {
    if (info_h3) {
        var info_span = info_h3.find("span#info__" + cur_ds.postfix);
    } else {
        var info_span = $("span#info__" + cur_ds.postfix);
    };
    info_span.text(MASTER_XML.find(cur_ds.xml_name_plural + " " + cur_ds.xml_name).length);
};

function append_new_line(cur_el, new_xml, cur_ds) {
    var t_table = cur_el.parents("table:first");
    t_table.append(draw_line(cur_ds, new_xml));
};

function delete_line(cur_el) {
    var del_tr = cur_el.parents("tr:first");
    del_tr.remove();
};

function create_delete_element(event, cur_ds) {
    var cur_el = $(event.target);
    var el_id = cur_el.attr("id");
    if (cur_ds.lock_div) {
        var lock_list = lock_elements($("div#" + cur_ds.lock_div));
    } else {
        var lock_list = [];
    };
    if (el_id.match(/new$/)) {
        $.ajax({
            url  : cur_ds.create_url,
            data : create_dict($("table#" + cur_ds.postfix), el_id),
            success : function(xml) {
                if (parse_xml_response(xml)) {
                    var new_period = $(xml).find(cur_ds.xml_name);
                    MASTER_XML.find(cur_ds.xml_name_plural).append(new_period);
                    append_new_line(cur_el, new_period, cur_ds);
                    cur_el.parents("tr:first").find("td input[id$='__name']").attr("value", "");
                    update_table_info(cur_ds);
                    redraw_tables();
                };
                unlock_elements(lock_list);
            }
        });
    } else {
        if (confirm("really delete " + cur_ds.name + " ?")) {
            $.ajax({
                url  : cur_ds.delete_url,
                data : create_dict($("table#" + cur_ds.postfix), el_id),
                success : function(xml) {
                    if (parse_xml_response(xml)) {
                        MASTER_XML.find(cur_ds.xml_name + "[pk='" + el_id.split("__")[1] + "']").remove();
                        delete_line(cur_el);
                        update_table_info(cur_ds);
                        redraw_tables();
                    };
                    unlock_elements(lock_list);
                }
            });
        } else {
            unlock_elements(lock_list);
        };
    };
};

parse_xml_response = function(xml) {
    var success = false;
    // parse xml response from server
    if ($(xml).find("response header").length) {
        var ret_state = $(xml).find("response header").attr("code");
        if (parseInt(ret_state) < 40) {
            // return true if we can parse the header and ret_code <= 40 (less than error)
            success = true;
        }
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

// get all attributes of a given select
function get_attribute_list(jq_sel, attr_name) {
    var new_list = [];
    jq_sel.each(function() { new_list.push($(this).attr(attr_name)); });
    return new_list;
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

MASTER_XML = undefined;

function init_xml_change(master_el) {
    // set reference XML element
    MASTER_XML = master_el;
};

function replace_xml_element(xml) {
    // replace element in MASTER_XML
    xml.find("value[name='object'] > *").each(function() {
        var new_el = $(this);
        MASTER_XML.find("[key='" + new_el.attr("key") + "']").replaceWith(new_el);
    });
};

function get_value(cur_el) {
    if (cur_el.is(":checkbox")) {
        var el_value = cur_el.is(":checked") ? "1" : "0";
    } else if (cur_el.prop("tagName") == "TEXTAREA") {
        var is_textarea = true;
        var el_value = cur_el.text();
    } else if (cur_el.prop("tagName") == "SELECT" && cur_el.attr("multiple")) {
        var sel_field = [];
        cur_el.find("option:selected").each(function(idx) {
            sel_field.push($(this).attr("value"));
        });
        var el_value = sel_field.join("::");
    } else {
        var el_value = cur_el.attr("value");
    };
    return el_value;
};

function submit_change(cur_el, callback, modify_data_dict, modify_data_dict_opts) {
    var is_textarea = false;
    var el_value = get_value(cur_el);
    var data_field = {
        "id"       : cur_el.attr("id"),
        "checkbox" : cur_el.is(":checkbox"),
        "value"    : el_value
    };
    if (modify_data_dict !== undefined) {
        modify_data_dict(data_field, modify_data_dict_opts);
    };
    $.ajax({
        url  : "{% url base:change_xml_entry %}",
        data : data_field,
        success : function(xml) {
            if (parse_xml_response(xml)) {
                replace_xml_element($(xml));
                if (callback != undefined && typeof callback == "function") {
                    callback(cur_el);
                } else {
                    // set values
                    console.log(data_field["id"]);
                };
            } else {
                <!-- set back to previous value -->
                if (is_textarea) {
                    $(cur_el).text(get_xml_value(xml, "original_value"));
                } else {
                    $(cur_el).attr("value", get_xml_value(xml, "original_value"));
                };
            };
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

// resync select list
function sync_select_from_xml(cur_el, cur_di) {
    var old_pks = get_attribute_list(cur_el.find("option:selected"), "value");
    var ref_list = MASTER_XML.find(cur_di.select_source);
    cur_el.children().remove();
    ref_list.each(function() {
        var cur_ns = $(this);
        var new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")}).text(cur_ns.text());
        if (in_array(cur_ns.attr("pk"), old_pks)) new_opt.attr("selected", "seleted");
        cur_el.append(new_opt);
    });
};

function create_input_el(xml_el, attr_name, id_prefix, kwargs) {
    var dummy_div = $("<div>");
    kwargs = kwargs || {};
    if (kwargs["label"]) {
        dummy_div.append($("<label>").attr({"for" : attr_name}).text(kwargs["label"]));
    };
    if (kwargs["select_source"] === undefined) {
        if (kwargs.boolean) {
            // checkbox input style
            var new_el = $("<input>").attr({
                "type"  : "checkbox",
                "id"    : id_prefix + "__" + attr_name
            });
            if (xml_el && xml_el.attr(attr_name) == "1") new_el.attr("checked", "checked");
        } else if (kwargs.textarea) {
            // textarea input style
            var new_el = $("<textarea>").attr({
                "id"    : id_prefix + "__" + attr_name
            }).text(xml_el === undefined ? (kwargs.new_default || "") : xml_el.attr(attr_name));
        } else {
            // text input style
            var new_el = $("<input>").attr({
                "type"  : kwargs.number ? "number" : "text",
                "id"    : id_prefix + "__" + attr_name,
                "value" : xml_el === undefined ? (kwargs.new_default || (kwargs.number ? "0" : "")) : xml_el.attr(attr_name)
            });
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
            var sel_source = MASTER_XML.find(kwargs.select_source);
        } else {
            var sel_source = kwargs.select_source;
        };
        if (sel_source.length) {
            var new_el = $("<select>").attr({
                "id"    : id_prefix + "__" + attr_name
            });
            if (kwargs.manytomany) {
                var sel_val = xml_el === undefined ? [] : xml_el.attr(attr_name).split("::");
                new_el.attr({
                    "multiple" : "multiple",
                    "size"     : 5
                });
            } else {
                var sel_val = xml_el === undefined ? "0" : xml_el.attr(attr_name);
                new_el.attr("value", sel_val);
            };
            if (kwargs.add_null_entry) {
                new_el.append($("<option>").attr({"value" : "0"}).text(kwargs.add_null_entry));
            };
            sel_source.each(function() {
                var cur_ns = $(this);
                var new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")}).text(cur_ns.text());
                if (kwargs.manytomany) {
                    if (in_array(sel_val, cur_ns.attr("pk"))) new_opt.attr("selected", "selected");
                } else {
                    if (cur_ns.attr("pk") == sel_val) new_opt.attr("selected", "selected");
                };
                new_el.append(new_opt);
            });
        } else {
            var new_el = $("<span>").addClass("error").text("no " + attr_name + " defined");
        };
    };
    if (xml_el !== undefined) {
        new_el.bind("change", function(event) {
            submit_change($(event.target), kwargs.callback, kwargs.modify_data_dict, kwargs.modify_data_dict_opts);
        })
    };
    return (dummy_div.append(new_el)).children();
};

</script>
