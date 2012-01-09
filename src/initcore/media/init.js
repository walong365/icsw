// popupwindow profiles
puw_profiles = {
    standard : { height : 800, width : 800, resizeable : 1, center : 1, scrollbars : 1 }
};

// check if is number
function isNumber(n) {
    return !isNaN(parseFloat(n)) && isFinite(n);
}

// general list
function general_list() {
    this.length = 0;
    this.item_list = new Object();
    this.add_item = function(item) {
        this.item_list[item.pk] = item;
        this.length++;
    }
    this.get_item = function(pk) {
        return this.item_list[pk];
    }
}

// simple table search
function show_matching_table_rows(table_obj, s_string) {
    var info_dict = {"total"    : table_obj.find("tbody tr").length};
    info_dict.selected = info_dict.total;
    if (s_string.length) {
        var loc_re=new RegExp(s_string, "i");
        table_obj.find("tbody tr").each(function() {
            var show_it = false;
            $(this).find("td").each(function() {
                if (loc_re.test($(this).text())) {
                    $(this).addClass("found");
                    show_it=true;
                } else {
                    $(this).removeClass("found");
                }
            });
            if (! show_it) {
                $(this).hide();
                info_dict.selected --;
            } else {
                $(this).show();
            }
        });
    } else {
        table_obj.find("tbody td").removeClass("found");
        table_obj.find("tbody tr").show();
    }
    table_obj.trigger("applyWidgets");
    return info_dict;
}

// test for element in array
function in_array(act_list, value) {
    in_list = false;
    for (idx=0 ; idx < act_list.length; idx++) {
        if (act_list[idx] == value) in_list=true;
    }
    return in_list;
}

// test for element in array and return idx (or -1)
function in_array_idx(act_list, value) {
    for (idx=0 ; idx < act_list.length; idx++) {
        if (act_list[idx] == value) return idx;
    }
    return -1;
}

// construct new list from act_list without element at position del_idx
function remove_element(act_list, del_idx) {
    var new_list = new Array();
    for (idx=0; idx < act_list.length; idx++) {
        if (idx != del_idx) new_list.push(act_list[idx]);
    }
    return new_list;
}

// element object, some kind of dictionary
function gen_element(xml_code) {
    var act_obj = this;
    this.val_dict = [];
    this.pk = parseInt($(xml_code).attr("pk"));
    $(xml_code).find("field").each(function() {
        var act_value = $(this).text();
        var act_name = $(this).attr("name");
        var act_type = $(this).attr("type");
        act_type = act_type == undefined ? "string" : act_type.toLowerCase();
        if (act_type == "datetimefield") {
            if (act_value.toLowerCase() != "") {
                act_value = transform_to_date(act_value);
            }
        } else if (act_type == "datefield") {
            if (act_value.toLowerCase() != "") {
                act_value = transform_to_date(act_value);
            }
        } else if (act_type.search("booleanfield") != -1) {
            act_value = act_value.toLowerCase() == "true" ? true : false;
        } else {
            act_value = isNumber(act_value) ? parseInt(act_value) : act_value;
        }
        act_obj.val_dict[act_name] = act_value;
    });
    this.get = function(key, def_value) {
        ret_value = this.val_dict[key];
        if (typeof(ret_value) == "undefined") { ret_value = def_value; };
        return ret_value;
    };
}

// input to spinner
function add_spinner_to_input(inp_el) {
    inp_el.after($("<div>").addClass("spinner"));
    inp_el.hide();
}

$.ajaxSetup({type     : "POST",
    timeout  : 50000,
    dataType : "xml"
    });

handle_ajax_ok = function(xml, ok_func) {
    if ($(xml).find("err_str").length) {
        alert($(xml).find("err_str").attr("value"));
    } else {
        ok_func(xml);
    }
}

/* maybe the new handle_ajax_ok */
function handle_ajax_dispatcher(data, success_func, error_func) {
    result = false;
    if ($(data).find("err_str").length) {
        error_func(data);
    } else {
        success_func(data);
        result = true;
    }
    return result;
}

handle_ajax_error = function(xhr, status, except) {
    if (status == "timeout") {
        alert("timeout");
    } else {
        if (xhr.status ) {
            // if status is != 0 an error has occured
            alert("*** " + status + " ***\nxhr.status : " + xhr.status + "\nxhr.statusText : " + xhr.statusText);
        }
    }
}


function enable_edit_mode(show_table, form_table) {
    show_table.hide();
    form_table.show();
}

function submit_form(show_table, form_table, in_dict) {
    in_dict.source_object = form_table;
    in_dict.success = function(xml) {
        // copy values
        if (in_dict.success_callback != undefined) in_dict.success_callback(xml);
        if (show_table.length > 0) {
            copy_form_oeko(show_table, form_table);
            close_form(show_table, form_table);
        };
    };
    validate_form_oeko(in_dict);
}

function close_form(show_table, form_table) {
    if (show_table.length > 0) {
        form_table.hide();
        show_table.show();
    }
}

function add_edit_cap_to_tables(table_list, in_dict) {
    table_list.each(function() {
        var form_table = $(this);
        var show_table = $("table#" + form_table.attr("id").replace("form_", "show_"));
        var act_tbody = form_table.find("tbody");
        // add error divs to form_tables
        act_tbody.find("tr").each(function() {
            var act_row = $(this);
            act_row.append($("<td>").append($("<div>").attr("class", "red_color").attr("id", act_row.children().last().children().first().attr("id") + "_error")));
        });
        // add edit/submit buttons to bottom of form
        var new_td = $("<td>").addClass("center").attr("colspan", "3");
        var new_div = $("<div>").addClass("left");
        new_div.append($("<input>").bind("click", function() {
            submit_form(show_table, form_table, in_dict);
            return false;
        }).attr("type", "submit").attr("value", in_dict.submit_str));
        if (show_table.length > 0) {
            new_div.append($("<input>").bind("click", function() {
                close_form(show_table, form_table);
            }).attr("type", "button").attr("value", in_dict.close_str));
        }
        new_td.append($("<div>").attr("id", "wait").addClass("left"));
        new_td.append($("<div>").attr("id", "error").addClass("left red_color"));
        act_tbody.append($("<tr>").append(new_td.append(new_div)));
        // add edit link to show tables
        if (show_table.length > 0) {
            var new_row = $("<tr>");
            new_row.append($("<td>").addClass("center").attr("colspan", "2").append($("<input>").attr("type", "button").attr("value", in_dict.edit_str).bind("click", function() {
                enable_edit_mode(show_table, form_table) ;
            })));
            show_table.find("tbody").append(new_row);
            close_form(show_table, form_table);
        };
    });

}

// validate form and send via xml
function validate_form_oeko(in_dict) {
    in_dict.source_object.find(":submit").attr("disabled", "disabled");
    send_data = new Object();
    send_data.table_id = in_dict.source_object.attr("id");
    send_data.add_data = in_dict.add_data;
    in_dict.source_object.find("input, select, textarea").each(function() {
        if ($(this).attr("type") == "checkbox") {
            send_data[$(this).attr("id")] = $(this).attr("checked") == true ? 1 : 0;
        } else {
            send_data[$(this).attr("id")] = $(this).val();
        };
    });
    error_div = in_dict.source_object.find("div#error");
    wait_div = in_dict.source_object.find("div#wait");
    error_div.text("");
    wait_div.addClass("spinner");
    // clear all error strings
    in_dict.source_object.find("[id$=_error]").text("");
    $.ajax({
        url     : in_dict.url,
        data    : send_data,
        error   : handle_ajax_error,
        success : function(xml) {
            in_dict.source_object.find(":submit").removeAttr("disabled");
            wait_div.removeClass("spinner");
            if ($(xml).find("err_str").length) {
                var err_str = $(xml).find("err_str").attr("value");
                $(xml).find("[nodeName^=id_]").each(function() {
                    in_dict.source_object.find("div#" + this.nodeName + "_error").text($(this).attr("value"));
                });
                if (error_div == undefined) {
                    alert(err_str);
                } else {
                    error_div.text(err_str);
                }
            }
            if ($(xml).find("res_str").length) {
                in_dict.success(xml);
            }
        }
    });
}

// copy from edit_form to show_form
function copy_form_oeko(show_tab, form_tab) {
    form_tab.find("input[id^=id_]").each(function() {
        // modify by selecting the correct index
        var target_el = show_tab.find("tr").slice($(this).parent().parent().index()).children().first().next();
        if ($(this).attr("type") == "checkbox") {
            var img_src = target_el.children().first().attr("src");
            if (img_src == undefined) {
                target_el.text($(this).attr("checked") == true ? "yes" : "no");
            } else {
                var img_array = img_src.split("/");
                img_array.pop();
                var new_img = img_array.join("/") + "/" + ($(this).attr("checked") == true ? "add_certificate.png" : "delete_bill.png");
                target_el.children().first().attr("src", new_img);
            }
        } else {
            target_el.text($(this).val());
        }
    });
    form_tab.find("select[id^=id_]").each(function() {
        show_tab.find("tr").slice($(this).parent().parent().index()).children().first().next().text($(this).find("option:selected").text());
    });
}

// object for holding the time (hh:mm:ss)
function simple_hhmm_time(in_str) {
    var split_array = in_str.split(":");
    this.hours   = parseInt(split_array[0], 10);
    this.minutes = parseInt(split_array[1], 10);
    this.sconds = parseInt(split_array[2], 10);
    this.get_str_hhmm = function() {
        return $.sprintf("%02d:%02d", this.hours, this.minutes);
    }
    this.get_str = function() {
        return $.sprintf("%02d:%02d:%02d", this.hours, this.minutes, this.seconds);
    }
    this.set_from_string_hhmm = function(in_str) {
        var hhmm_reg = new RegExp("^\\d{1,2}:\\d{1,2}$");
        if (hhmm_reg.test(in_str)) {
            var hhmm_part = in_str.split(":");
            if (parseInt(hhmm_part[0], 10) > 23 | parseInt(hhmm_part[1], 10) > 59) {
                throw ("time out of bounds");
            } else {
                this.hours   = parseInt(hhmm_part[0], 10);
                this.minutes = parseInt(hhmm_part[1], 10);
                this.seconds = 0;
            }
        } else {
            throw ("time parse error");
        }
    }
    this.get_minutes = function() {
        return 60 * this.hours + this.minutes;
    }
    this.clone = function() {
        return new simple_hhmm_time(this.get_str());
    }
}

Date.prototype.get_date_ddmmyyyy = function(in_str) {
    var new_date = new Date();
    var parts = in_str.split()[0].split(".");
    this.setFullYear(parseInt(parts[2], 10));
    this.setMonth(parseInt(parts[1] - 1, 10), parseInt(parts[0], 10));
}

Date.prototype.parse_date_ddmmyyyy = function(in_str) {
    var ddmmyyyy_reg = new RegExp("^\\d{1,2}.\\d{1,2}.\\d{4}$");
    if (ddmmyyyy_reg.test(in_str)) {
        var parts = in_str.split(".");
        if (parts[0] > 31 || parts[1] > 12 || parts[2] < 1970 || parts[2] > 2200) {
            throw("date out of range");
        }
    } else {
        throw("date parse error");
    }
}

Date.prototype.short_date_form = function() {
    // returns day.month.year
    return $.sprintf("%02d.%02d.%04d", this.getDate(), this.getMonth() + 1, this.getFullYear());
}

Date.prototype.strftime = function(format_str) {
    // returns day.month.year
    return $.strftime(format_str, this);
}

function transform_to_date(in_str) {
    var new_date = new Date();
    var in_str_split = in_str.split(/\s+/);
    var yysplit_str = in_str_split[0].split("-");
    new_date.setFullYear(parseInt(yysplit_str[0], 10));
    new_date.setMonth(parseInt(yysplit_str[1], 10) - 1, parseInt(yysplit_str[2], 10));
    if (in_str_split.length == 2) {
        var hhmmss_str = in_str_split[1].split(":");
        new_date.setHours(parseInt(hhmmss_str[0], 10));
        new_date.setMinutes(parseInt(hhmmss_str[1], 10));
        new_date.setSeconds(parseInt(hhmmss_str[2], 10));
    }
    return new_date;
}

function get_diff_time_str(minutes) {
    var ret_array = new Array();
    var hours = parseInt(minutes / 60, 10);
    minutes -= 60 * hours;
    if (hours) {
        return $.sprintf("%d:%02d", hours, minutes);
    } else {
        return $.sprintf("%d", minutes);
    }
}

// show object properties
function show_obj_props(act_obj) {
    var prop_list = "";
    for (var prop in act_obj) {
        prop_list += prop + "\n";
    }
    alert(prop_list);
}

// popupwindow
jQuery.fn.popupwindow = function(p) {
    var profiles = p || {};
    return this.each(function(index){
        var settings, parameters, mysettings, b, a;
        // for overrideing the default settings
        mysettings = (jQuery(this).attr("rel") || "").split(",");
        settings = {
            height     : 600, // sets the height in pixels of the window.
            width      : 600, // sets the width in pixels of the window.
            toolbar    : 0,   // determines whether a toolbar (includes the forward and back buttons) is displayed {1 (YES) or 0 (NO)}.
            scrollbars : 0,   // determines whether scrollbars appear on the window {1 (YES) or 0 (NO)}.
            status     : 0,   // whether a status line appears at the bottom of the window {1 (YES) or 0 (NO)}.
            resizable  : 1,   // whether the window can be resized {1 (YES) or 0 (NO)}. Can also be overloaded using resizable.
            left       : 0,   // left position when the window appears.
            top        : 0,   // top position when the window appears.
            center     : 0,   // should we center the window? {1 (YES) or 0 (NO)}. overrides top and left
            createnew  : 1,   // should we create a new window for each occurance {1 (YES) or 0 (NO)}.
            location   : 0,   // determines whether the address bar is displayed {1 (YES) or 0 (NO)}.
            menubar    : 0    // determines whether the menu bar is displayed {1 (YES) or 0 (NO)}.
        };
        // if mysettings length is 1 and not a value pair then assume it is a profile declaration
        // and see if the profile settings exists
        if(mysettings.length == 1 && mysettings[0].split(":").length == 1) {
            a = mysettings[0];
            // see if a profile has been defined
            if(typeof profiles[a] != "undefined") { settings = jQuery.extend(settings, profiles[a]); }
        } else {
            // overrides the settings with parameter passed in using the rel tag.
            for(var i=0; i < mysettings.length; i++) {
                b = mysettings[i].split(":");
                if(typeof settings[b[0]] != "undefined" && b.length == 2) {	settings[b[0]] = b[1]; }
            }
        }
        // center the window
        if (settings.center == 1) {
            settings.top  = (screen.height - (settings.height + 110))/2;
            settings.left = (screen.width  - settings.width)/2;
        }
        parameters = "location=" + settings.location + ",menubar=" + settings.menubar + ",height=" + settings.height + ",width=" + settings.width + ",toolbar=" + settings.toolbar + ",scrollbars=" + settings.scrollbars  + ",status=" + settings.status + ",resizable=" + settings.resizable + ",left=" + settings.left  + ",screenX=" + settings.left + ",top=" + settings.top  + ",screenY=" + settings.top;
        jQuery(this).bind("click", function() {
            var name = settings.createnew ? "PopUpWindow" + index : "PopUpWindow";
            window.open($(this).attr("href"), name, parameters).focus();
            return false;
        });
    });
};

/** xlsx_export_request(form, url, colModel, jqgrid_params);
    show is optional, default 0
    args is optional, default "", can be used for all you need */
//  needs $(input#xlsx_export) and $(div#div_spinner)
function xlsx_export_request(form, url, colModel, colNames, jqgrid_params, show, args, all_cols) {
    var formdata = "";
    if (form != "") { formdata = $("form#" + form).serialize(); }
    if (show === undefined) { show = 0; }
    if (args === undefined) { args = ""; }
    if (all_cols === undefined) { all_cols = false; }
    $("input#xlsx_export").attr("disabled", "disabled");
    div_spinner_on();
    var col_index = "";
    if (jqgrid_params === undefined) {
        if (colModel.length == colNames.length) {
            for (var i = 0; i < colModel.length; i++) {
                if (i > 0) { col_index = col_index + " "; }
                col_index = col_index + colModel[i].index;
            }
        }
    } else if (all_cols | jqgrid_params[show][1][0] == "") {
        for (var i = 0; i < colModel.length; i++) {
            if (all_cols | !colModel[i].hidden) {
                if (i > 0) { col_index = col_index + " "; }
                col_index = col_index + colModel[i].index;
            }
        }
    } else {
        for (var i = 0; i < jqgrid_params[show][1].length; i++) {
            for (var j = 0; j < colModel.length; j++) {
                if (jqgrid_params[show][1][i] == colModel[j].name) {
                    if (i > 0) { col_index = col_index + " "; }
                    col_index = col_index + colModel[j].index;
                }
            }
        }
    }
    var col_names = get_colNames_params(jqgrid_params, colModel, colNames, show, all_cols);
    $.ajax({
        timeout: 86400000,/** timeout for big imports, can bis run some hours" */
        url  : url,
        type : "POST",
        data : {
            "formdata"  : formdata,
            "col_index" : col_index,
            "col_names" : col_names,
            "args"      : args
        },
        success  : function(xml) {
            _xml = get_xml_value(xml, "url");
            if (_xml == "") {
                alert(TRANS_TO_MANY_RESULTS + "\n\r" + TRANS_ONLY_X_RECORDS_ALLOWED);
            } else if (_xml === undefined) {
                alert(TRANS_ERROR + TRANS_NOTHUNG_TO_EXPORT);
            } else {
                window.location = _xml;
            }
            div_spinner_off();
            $("input#xlsx_export").removeAttr("disabled");
        },
        error    : function(error) {
            div_spinner_off();
            $("input#xlsx_export").removeAttr("disabled");
            if (error.statusText == "timeout") {
                alert(TRANS_ERROR + error.statusText + "\r\n" + TRANS_TO_MANY_RESULTS);
            } else {
                alert(TRANS_ERROR + error.statusText);
            }
        }
    });
}

function div_spinner_on() {
    $("div#div_spinner").addClass("spinner").removeClass("hidden").text(TRANS_LOADING);
}
function div_spinner_off() {
    $("div#div_spinner").addClass("hidden").removeClass("spinner").text("");
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
