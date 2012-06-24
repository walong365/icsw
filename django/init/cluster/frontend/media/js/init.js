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
