/** set colModel to the users jqgrid_params in grid_id show*/
function set_colModel_params(jqgrid_params, colModel, show) {
    if (show === undefined) { show = 0; }
    var names = new Array();
    for (var i = 0; i < colModel.length; i++) {
        names.push(colModel[i]["name"]);
    }
    var result = new Array();
    if ((jqgrid_params[show][1].length == 1) && (jqgrid_params[show][1][0] == "")) {
        result = colModel;
    } else {
        for (var i = 0; i < jqgrid_params[show][1].length; i++) {
            if (jqgrid_params[show][1][i] != "") {
                if (jQuery.inArray(jqgrid_params[show][1][i], names) >= 0) {
                    colModel[jQuery.inArray(jqgrid_params[show][1][i], names)].hidden = false;                
                    result.push(colModel[jQuery.inArray(jqgrid_params[show][1][i], names)]);
                }
            }
        }
    }
    for (var i = 0; i < colModel.length; i++) {
        if (jQuery.inArray(colModel[i], result) < 0) {
            colModel[i].hidden = true;
            result.push(colModel[i]);
        }
    }
    return result;
}

/** set colNames to the users jqgrid_params live_colModel column order in grid_id show */
function set_colNames_params(jqgrid_params, live_colModel, colNames, show) {
    if (show === undefined) { show = 0; }
    var names = new Array();
    for (var i = 0; i < live_colModel.length; i++) {
        names.push(live_colModel[i]["name"]);
    }
    var result = new Array();
    for (var i = 0; i < jqgrid_params[show][1].length; i++) {
        if (jqgrid_params[show][1][i] != "" && jQuery.inArray(jqgrid_params[show][1][i], names) >= 0) {
            result.push(colNames[jQuery.inArray(jqgrid_params[show][1][i], names)]);
        }
    }
    for (var i = 0; i < colNames.length; i++) {
        if (jQuery.inArray(colNames[i], result) < 0) {
            result.push(colNames[i]);
        }
    }
    return result;
}

/** return the visible colNames in order of jqgrid_params */
function get_colNames_params(jqgrid_params, colModel, colNames, show, all_cols) {
    if (show === undefined) { show = 0; }
    if (all_cols === undefined) { all_cols = false; }
    var names = new Array();
    for (var i = 0; i < colModel.length; i++) {
        names.push(colModel[i]["name"]);
    }
    var result = "";
    if (jqgrid_params === undefined) {
        if (colModel.length == colNames.length) {
            for (var i = 0; i < colNames.length; i++) {
                if (i > 0) { result = result + ";"; }
                result = result + colNames[i];
            }
        }
    } else if (!all_cols && (jqgrid_params[show][1].length > 0) && (jqgrid_params[show][1][0] != "")) { 
        for (var i = 0; i < jqgrid_params[show][1].length; i++) {
            if (jqgrid_params[show][1][i] != "") {
                if (i > 0) { result = result + ";"; }
                result = result + colNames[jQuery.inArray(jqgrid_params[show][1][i], names)];
            }
        }
    } else {
        for (var i = 0; i < colNames.length; i++) {
            if ((jQuery.inArray(colNames[i], result) < 0) && (all_cols | !colModel[i].hidden)) {
                if (i > 0) { result = result + ";"; }
                result = result + colNames[i];
            }
        }
    }
    return result;
}

/** parse params string from .py return render_me dict in a array */
function get_jqgrid_params(params) {
    params = params.split(" ");
    for (var i = 0; i < params.length; i++) {
        params[i] = params[i].split(":");
        for (var j = 0; j < params[i].length; j++) {
            params[i][j] = params[i][j].split(",");
        }
    }
    return params;
}

/** save changed jqgrid params in the db and set the changes "on_the_fly" in jqgrid_params */
function save_jqgrid_params(url, element, jqgrid_params, name, show) {
    if (show === undefined) { show = 0; }
    if (element) {
        var jqG_params = element.getGridParam();
        var params = "";
        for (var i = 0; i < jqG_params.colModel.length; i++) {
            if (!jqG_params.colModel[i].hidden) {
                if (i > 0) { params = params + " "; }
                params = params + jqG_params.colModel[i].name;
            }
        }
        jQuery.ajax({
            url      : url,
            type     : "POST",
            dataType : "html",
            data     : {"name"      : name,
                        "grid_num"  : show,
                        "rowNum"    : jqG_params.rowNum,
                        "params"    : params},
            success : function() {},
            error : function() {}
        });
        params_list = new Array();
        for (var i = 0; i < jqG_params.colModel.length; i++) {
            if (!jqG_params.colModel[i].hidden) {
                params_list.push(jqG_params.colModel[i].name);
            }
        }
        jqgrid_params[show][1] = params_list;
        jqgrid_params[show][0][0] = jqG_params.rowNum;
    }
    return jqgrid_params;
}

/** return the index id from colum with name in colModel */
function get_col_id_by_name(name, colModel) {
    for (var i = 0; i < colModel.length; i++) {
        if (colModel[i].name===name) {
            return i;
        }
    }
    return -1
}
