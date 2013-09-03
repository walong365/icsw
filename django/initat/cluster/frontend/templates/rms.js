{% load coffeescript %}

 <script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

class file_info
    constructor: (@event, @file_id) ->
    show: () =>
        $.ajax
            url     : "{% url 'rms:get_file_content' %}"
            data    :
                "file_id" : @file_id
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml = $(xml).find("response file_info")
                    @build_div()
                    @file_div.modal
                        opacity      : 50
                        position     : [@event.pageY, @event.pageX]
                        autoResize   : true
                        autoPosition : true
                        minWidth     : "640px"
                        minHeight    : "800px"
                        onShow: (dialog) => 
                            @activate_cm()
                            dialog.container.draggable()
                            $("#simplemodal-container").css("height", "auto")
                            $("#simplemodal-container").css("width", "auto")
                        onClose: =>
                            $.modal.close()
    build_div: () =>
        file_div = $("<div>")
        file_div.append(
            $("<h3>").text("File '" + @resp_xml.attr("name") + "', " + @resp_xml.attr("lines") + " lines in " + @resp_xml.attr("size_str"))
        )
        file_ta = $("<textarea>").text(@resp_xml.text())
        file_div.append(file_ta)
        @file_div = file_div
        @file_ta = file_ta
    activate_cm: () =>
        cur_ed = CodeMirror.fromTextArea(@file_ta[0], {
            #"mode"            : "shell",
            "styleActiveLine" : true,
            "lineNumbers"     : true,
            "lineWrapping"    : true,
            "indentUnit"      : 4,
        })
        cur_ed.setSize(1024, 600)
        cur_ed.refresh()
        cur_ed.focus()

class rms_view
    constructor: (@top_div, @reload_button, @search={}) ->
        @divs = {}
        @tables = {}
        @expand_dict = {}
    setup: () =>
        $.ajax
            url : "{% url 'rms:get_header_xml' %}"
            success : (xml) =>
                if parse_xml_response(xml)
                    @run_headers = $(xml).find("headers running_headers")[0]
                    @wait_headers = $(xml).find("headers waiting_headers")[0]
                    @node_headers = $(xml).find("headers node_headers")[0]
                    @top_div.append($("<ul>"))
                    @divs["run_table"] = @build_table_div("run_table", @run_headers)
                    @divs["wait_table"] = @build_table_div("wait_table", @wait_headers)
                    @divs["node_table"] = @build_table_div("node_table", @node_headers)
                    @top_div.append(@divs["run_table"])
                    @top_div.append(@divs["wait_table"])
                    @top_div.append(@divs["node_table"])
                    @top_div.tabs()
                    @init_tables()
                    @init_timer()
    build_table_div: (id_str, headers) =>
        new_div = $("<div>").attr("id", id_str)
        new_table = $("<table>").attr("id", id_str).css("width", "100%")
        @tables[id_str] = new_table
        top_tr = $("<tr>")
        $(headers).find("*").find("*").each (idx, cur_el) =>
            top_tr.append($("<th>").text($(cur_el).prop("tagName")))
        new_div.append(new_table)
        new_table.append($("<thead>").append(top_tr))
        new_table.append($("<tbody>"))
        @top_div.find("ul").append($("<li>").append($("<a>").attr("href", "##{id_str}").text(id_str)))
        return new_div
    init_timer: () =>
        $(document).everyTime(10000, "reload_page", =>
            @reload_tables()
        )
        if @reload_button
            @reload_button.on("click", @reload_tables)
        @reload_tables()
    reload_tables: () =>
        $.ajax
            url: "{% url 'rms:get_rms_json' %}"
            dataType : "json"
            success : (json) =>
                @file_dict = json["files"]
                for key, cur_table of @tables
                    while cur_table.fnSettings().fnRecordsTotal()
                        cur_table.fnDeleteRow(0, undefined, false)
                    cur_table.dataTable().fnAddData(json[key]["aaData"], false)
                    cur_table.dataTable().fnDraw()
                for key, table_name of @expand_dict
                    cur_table = @tables[table_name]
                    cur_div = cur_table.find("tr div[id^='expand_#{key}_']")
                    if cur_div.length
                        cur_div.removeClass("ui-icon-triangle-1-e").addClass("ui-icon-triangle-1-s")
                        @build_fileinfo_line(key, cur_table.dataTable(), cur_div.parents("tr:first")[0])
    init_tables: () =>
        @init_run_table()
        @init_wait_table()
        @init_node_table()
    init_run_table: () =>
        cur_table = @tables["run_table"]
        cur_table.dataTable
            "bProcessing"     : true,
            "aaData"          : [],
            "bJQueryUI"       : true,
            "sPaginationType" : "full_numbers",
            "bStateSave"      : true,
            "bAutoWidth"      : false
            "oSearch"         : {"sSearch" : if "run_table" of @search then @search["run_table"] else ""}
            "aoColumnDefs"    : [
                {
                    "fnRender" : (o, val) ->
                        return "<b>#{val}</b>"
                    "aTargets" : [5],
                    "sClass" : "center"
                }, {
                    "aTargets" : [7, 8, 10, 11],
                    "sClass"   : "nowrap"
                }, {
                    "fnRender" : (o, val) ->
                        if val == "---" or val == "err"
                            return "<b>#{val}</b>"
                        else
                            a_el = $("<a>").attr("href", "file:#{o.mDataProp}:#{o.aData[0]}:#{o.aData[1]}").text(val)
                            return $("<div>").append(a_el).html()
                    "aTargets" : [12, 13],
                    "sClass"   : "nowrap"
                }, {
                    "fnRender" : (o, val) =>
                        return @render_action(o, val)
                    "aTargets" : [16],
                    "sClass"   : "nowrap"
                }, {
                    "aTargets" : [14],
                    "fnRender" : (o, val) ->
                        return "#{val} <div class='ui-icon ui-icon-triangle-1-e' id='expand_#{o.aData[0]}_#{o.aData[1]}'>"
                    "sClass"   : "center nowrap"
                }
            ],
            "fnDrawCallback"   : (o_settings) =>
                @tables["run_table"].find("a[href^='file']").bind("click", @new_file_info)
                @tables["run_table"].find("input[type='button'][id^='jctrl:']").on("click", @control_job)
                @tables["run_table"].find("div[id^='expand_']").on("click", @toggle_file_expand)
        @init_redraw(cur_table)
    init_wait_table: () =>
        cur_table = @tables["wait_table"] 
        cur_table.dataTable
            "bProcessing"     : true,
            "aaData"          : []
            "bJQueryUI"       : true,
            "sPaginationType" : "full_numbers",
            "bStateSave"      : true,
            "bAutoWidth"      : false,
            "oSearch"         : {"sSearch" : if "wait_table" of @search then @search["wait_table"] else ""}
            "aoColumnDefs"    : [
                {
                    "fnRender" : (o, val) ->
                        return "<b>#{val}</b>"
                    "aTargets" : [5],
                    "sClass" : "center"
                }, {
                    "fnRender" : (o, val) =>
                        return @render_action(o, val)
                    "aTargets" : [13],
                    "sClass"   : "nowrap"
                }, {
                    "aTargets" : [8, 9],
                    "sClass"   : "nowrap"
                }
            ]
            "fnDrawCallback"   : (o_settings) =>
                @tables["wait_table"].find("input[type='button'][id^='jctrl:']").bind("click", @control_job)
        @init_redraw(cur_table)
    init_node_table: () =>
        cur_table = @tables["node_table"] 
        cur_table.dataTable
            "bProcessing"     : true,
            "aaData"          : []
            "bJQueryUI"       : true,
            "sPaginationType" : "full_numbers",
            "bStateSave"      : true,
            "bAutoWidth"      : true,
            "aoColumnDefs"    : [
                {
                    "fnRender" : (o, val) ->
                        return "<b>#{val}</b>"
                    "aTargets" : [6, 7, 8],
                    "sClass" : "center slots_info"
                }, {
                    "fnRender" : (o, val) ->
                        cur_m = val.match(/(\d+\.\d+).*/)
                        if cur_m
                            max_load = 16.0
                            load = Math.min(cur_m[0], max_load)
                            ret_el = $("<div>").addClass("leftfloat load_value").append(
                                $("<b>").text($.sprintf("%3.2f", load))
                            ).append(
                                $("<div>").addClass("load_outer").append(
                                    $("<div>").addClass("load_inner").css("width", parseInt(98 * load / max_load) + "px")
                                )
                            )
                            return $("<div>").append(ret_el).html()
                        else
                            return "<b>#{val}</b>"
                    "aTargets" : [5],
                    "sClass"   : "load"
                }, {
                    "aTargets" : [9, 4],
                    "sClass"   : "nowrap"
                }
             ]
        @init_redraw(cur_table)
    init_redraw: (cur_table) =>
        cur_table.bind("draw", (event) =>
            table = $(event.target)
            #@divs[table.attr("id")].width(table.width())
        )
    toggle_file_expand: (event) =>
        cur_el = $(event.target)
        cur_tr = cur_el.parents("tr:first")
        cur_table = cur_tr.parents("table:first")
        table_id = cur_table.attr("id")
        #console.log table_id, cur_el.attr("id")
        job_id = cur_el.attr("id").split("_")[1]
        if job_id of @file_dict
            cur_dt = @tables[table_id].dataTable()
            cur_tr = cur_tr[0]
            if job_id of @expand_dict
                cur_dt.fnClose(cur_tr)
                delete @expand_dict[job_id]
                cur_el.removeClass("ui-icon-triangle-1-s").addClass("ui-icon-triangle-1-e")
            else
                cur_el.removeClass("ui-icon-triangle-1-e").addClass("ui-icon-triangle-1-s")
                @expand_dict[job_id] = table_id
                @build_fileinfo_line(job_id, cur_dt, cur_tr)
    build_fileinfo_line: (job_id, cur_dt, cur_tr) =>
        new_table = $("<table>")
        for struct in @file_dict[job_id]
            file_name = struct[0]
            file_content = struct[1]
            file_size = struct[2]
            max_rows = struct[3]
            new_table.append($("<tr>").append($("<td>").text("filename = #{file_name}, size = #{file_size} Bytes")))
            new_table.append($("<tr>").append($("<td>").append($("<textarea>").attr(
                "cols" : "100",
                "rows" : max_rows).val(file_content))))
        cur_tr = cur_dt.fnOpen(cur_tr, $("<tr>").append($("<td>").append(new_table)))
    render_action: (o, val) =>
        cap_list = val.split(":")
        res_list = $("<div>")
        if "delete" in cap_list
            res_list.append(
                $("<input>").attr(
                    "type"  : "button"
                    "value" : "delete"
                    "id"    : "jctrl:delete:#{o.aData[0]}:#{o.aData[1]}" 
                )
            )
        if "force_delete" in cap_list
            res_list.append(
                $("<input>").attr(
                    "type"  : "button"
                    "value" : "force delete"
                    "id"    : "jctrl:force_delete:#{o.aData[0]}:#{o.aData[1]}" 
                )
            )
        return $("<div>").append(res_list).html()
    new_file_info: (event) =>
        cur_el = $(event.target)
        cur_fi = new file_info(event, cur_el.attr("href"))
        cur_fi.show()
        return false
    control_job: (event) =>
        cur_el = $(event.target)
        el_id = cur_el.attr("id")
        job_id = el_id.split(":")[2..3]
        action_name = el_id.split(":")[1]
        full_job_id = job_id.join(".")
        if full_job_id.match(/^.*\.$/)
            full_job_id = full_job_id[..-2]
        if confirm("really #{action_name} job #{full_job_id} ?")
            $.ajax
                url     : "{% url 'rms:control_job' %}"
                data    : {
                    "control_id" : el_id
                }
                success : (xml) ->
                    parse_xml_response(xml)
        return false

root.rms_view = rms_view

{% endinlinecoffeescript %}

</script>

