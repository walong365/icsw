<script type="text/javascript">

$.ajaxSetup({
    type     : "POST",
    timeout  : 50000,
    dataType : "xml"
});

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

// create a dictionary from a list of elements
function create_dict(top_el, id_prefix) {
    var in_list = top_el.find("input[id^='" + id_prefix + "'], select[id^='" + id_prefix + "']");
    var out_dict = {};
    in_list.each(function(idx, value) {
        out_dict[$(this).attr("id")] = $(this).attr("value");
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

function submit_change(cur_el, callback) {
    if (cur_el.is(":checkbox")) {
        var el_value = cur_el.is(":checked") ? "1" : "0";
    } else {
        var el_value = cur_el.attr("value");
    };
    $.ajax({
        url  : "{% url config:change_xml_entry %}",
        data : {
            "id"       : cur_el.attr("id"),
            "checkbox" : cur_el.is(":checkbox"),
            "value"    : el_value
        },
        success : function(xml) {
            if (parse_xml_response(xml)) {
                replace_xml_element($(xml));
                if (callback != undefined && typeof callback == "function") callback(cur_el);
            } else {
                <!-- set back to previous value -->
                $(cur_el).attr("value", get_xml_value(xml, "original_value"));
            };
        }
    })
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
        } else {
            // text input style
            var new_el = $("<input>").attr({
                "type"  : kwargs.number ? "number" : "text",
                "id"    : id_prefix + "__" + attr_name,
                "value" : xml_el === undefined ? (kwargs.new_default || (kwargs.number ? "0" : "")) : xml_el.attr(attr_name)
            });
        }
    } else {
        // select input
        var sel_val = xml_el === undefined ? "0" : xml_el.attr(attr_name);
        if (kwargs.select_source.length) {
            var new_el = $("<select>").attr({
                "id"    : id_prefix + "__" + attr_name,
                "value" : sel_val
            });
            kwargs.select_source.each(function() {
                var cur_ns = $(this);
                var new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")}).text(cur_ns.text());
                if (cur_ns.attr("pk") == sel_val) new_opt.attr("selected", "selected");
                new_el.append(new_opt);
            });
        } else {
            var new_el = $("<span>").addClass("error").text("no " + attr_name + " defined");
        };
    };
    if (xml_el !== undefined) {
        new_el.bind("change", function(event) {
            submit_change($(event.target), kwargs.callback);
        })
    };
    return (dummy_div.append(new_el)).children();
};

</script>
