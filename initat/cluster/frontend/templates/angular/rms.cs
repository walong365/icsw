{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

running_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="run_list" pag_settings="pagRun" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="running_struct"></tr>
    </thead>
    <tbody>
        <tr rmsrunline ng-repeat-start="data in run_list | paginator2:this.pagRun" struct="running_struct">
        </tr>
        <tr ng-repeat-end>
            <td colspan="10">{{ datax }}</td>
        </tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="running_struct"></tr>
    </tfoot>
</table>
"""

waiting_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="wait_list" pag_settings="pagWait" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="waiting_struct"></tr>
    </thead>
    <tbody>
        <tr rmsline ng-repeat="data in wait_list | paginator2:this.pagWait" struct="waiting_struct"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="waiting_struct"></tr>
    </tfoot>
</table>
"""

node_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="node_list" pag_settings="pagNode" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="node_struct"></tr>
    </thead>
    <tbody>
        <tr rmsline ng-repeat="data in node_list | paginator2:this.pagNode" struct="node_struct"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="node_struct"></tr>
    </tfoot>
</table>
"""

iostruct = """
    <h4>File {{ io_struct.file_name() }} ({{ io_struct.file_size() }} in {{ io_struct.file_lines() }} lines), 
        <input type="button" class="btn btn-sm btn-warning" value="close" ng-click="close_io(io_struct)"></input>
    </h4>
    <!-- <textarea ui-codemirror="editorOptions" ng-model="io_struct.text" ui-refresh="io_struct.refresh_cm"> -->
    <textarea ng-model="io_struct.text" ng-show="io_struct.valid">{{ io_struct.text }}
    </textarea>
    <div ng-if="!io_struct.valid">
        <h5>nothing found</h5>
    </div>
"""

headers = """
<th ng-repeat="entry in struct.display_headers()">{{ entry }}</th>
"""

header_toggle = """
<th colspan="{{ struct.headers.length }}">
    <form class="inline">
        <input ng-repeat="entry in struct.headers" type="button" ng-class="struct.get_btn_class(entry)" value="{{ entry }}" ng-click="struct.change_entry(entry)">
        </input>
    </form>
</th>
"""

rmsline = """
<td ng-repeat="entry in get_display_data(data) track by $index">
<span ng-if="entry[0]" ng-bind-html="entry[1]"></span>
<span ng-if="!entry[0]" ng-bind-html="entry[1]"></span>
</td>
"""

rmsrunline = """
<td ng-show="running_struct.toggle['job_id']">
    {{ data[0] }}
</td>
<td ng-show="running_struct.toggle['task_id']">
    {{ data[1] }}
</td>
<td ng-show="running_struct.toggle['name']">
    {{ data[2] }}
</td>
<td ng-show="running_struct.toggle['real_user']">
    {{ data[3] }}
</td>
<td ng-show="running_struct.toggle['granted_pe']">
    {{ data[4] }}
</td>
<td ng-show="running_struct.toggle['owner']">
    {{ data[5] }}
</td>
<td ng-show="running_struct.toggle['state']">
    <b>{{ data[6] }}</b>
</td>
<td ng-show="running_struct.toggle['complex']">
    {{ data[7] }}
</td>
<td ng-show="running_struct.toggle['queue_name']">
    {{ data[8] }}
</td>
<td ng-show="running_struct.toggle['start_time']">
    {{ data[9] }}
</td>
<td ng-show="running_struct.toggle['run_time']">
    {{ data[10] }}
</td>
<td ng-show="running_struct.toggle['left_time']">
    {{ data[11] }}
</td>
<td ng-show="running_struct.toggle['load']">
    {{ data[12] }}
</td>
<td ng-show="running_struct.toggle['stdout']">
    <span ng-switch on="valid_file(data[13])">
        <span ng-switch-when="1">
            <input type="button" ng-class="get_io_link_class(data, 'stdout')" ng-value="data[13]" ng-click="activate_io(data, 'stdout')"></input>
        </span>
        <span ng-switch-when="0">
            {{ data[13] }}
        </span>
    </span>
</td>
<td ng-show="running_struct.toggle['stderr']">
    <span ng-switch on="valid_file(data[14])">
        <span ng-switch-when="1">
            <input type="button" ng-class="get_io_link_class(data, 'stderr')" ng-value="data[14]" ng-click="activate_io(data, 'stderr')"></input>
        </span>
        <span ng-switch-when="0">
            {{ data[14] }}
        </span>
    </span>
</td>
<td ng-show="running_struct.toggle['files']">
    {{ data[15] }}
</td>
"""
{% endverbatim %}

rms_module = angular.module("icsw.rms", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.codemirror"])

angular_module_setup([rms_module])

class header_struct
    constructor: (@table, @headers) ->
        _dict = {}
        for entry in @headers
            _dict[entry] = true
        @toggle = _dict
        @build_cache()
    set_disabled : (in_list) =>
        for entry in in_list
            @toggle[entry] = false
        @build_cache()
    build_cache : () =>
        _c = []
        for entry in @headers
            if @toggle[entry]
                _c.push([true, entry])
            else
                _c.push([false, entry])
        @togglec = _c
    change_entry : (entry) =>
        @toggle[entry] = ! @toggle[entry]
        $.ajax
            url      : "{% url 'rms:set_user_setting' %}"
            dataType : "json"
            data:
                "data" : angular.toJson({"table" : @table, "row" : entry, "enabled" : @toggle[entry]})
            success  : (json) =>
        @build_cache()
    display_headers : () =>
        return (v[0] for v in _.zip.apply(null, [@headers, @togglec]) when v[1][0])
    add_headers : (data) =>
        # get display list
        return ([v[1][1], v[0]] for v in _.zip.apply(null, [data, @togglec]))
    display_data : (data) =>
        # get display list
        return (v[0] for v in _.zip.apply(null, [data, @togglec]) when v[1][0])
    get_btn_class : (entry) ->
        if @toggle[entry]
            return "btn btn-sm btn-success"
        else
            return "btn btn-sm"
        
class io_struct
    constructor : (@job_id, @task_id, @type) ->
        @resp_xml = undefined
        @text = ""
        @valid = false
    get_name : () =>
        if @task_id
            return "#{@job_id}.#{@task_id} (#{@type})"
        else
            return "#{@job_id} (#{@type})"
    get_id : () ->
        return "#{@job_id}.#{@task_id}.#{@type}"
    file_name : () ->
        if @resp_xml
            return @resp_xml.attr("name")
        else
            return "---"
    file_lines : () ->
        if @resp_xml
            return @resp_xml.attr("lines")
        else
            return "---"
    file_size : () ->
        if @resp_xml
            return @resp_xml.attr("size_str")
        else
            return "---"
    feed : (xml) =>
        found_xml = $(xml).find("response file_info[id='" + @get_id() + "']")
        if found_xml.length
            @valid = true
            @resp_xml = found_xml
            @text = @resp_xml.text()
        else
            @valid = false
            @resp_xml = undefined
            @text = ""
          
rms_module.controller("rms_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", "$sce", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout, $sce) ->
        access_level_service.install($scope)
        $scope.rms_headers = {{ RMS_HEADERS | safe }}
        $scope.pagRun = paginatorSettings.get_paginator("run", $scope)
        $scope.pagWait = paginatorSettings.get_paginator("wait", $scope)
        $scope.pagNode = paginatorSettings.get_paginator("node", $scope)
        $scope.header_filter_set = false
        $scope.editorOptions = {
            lineWrapping : false
            lineNumbers: true
            mode: 
                name : "python"
                version : 2
            matchBrackets: true
            minHeight : 200
            width: "800px"
            height: "600px"
            styleActiveLine: true
            indentUnit : 4
        }
        $scope.io_dict = {}
        $scope.io_list = []
        $scope.run_list = []
        $scope.wait_list = []
        $scope.node_list = []
        $scope.running_struct = new header_struct("running", $scope.rms_headers.running_headers)
        $scope.waiting_struct = new header_struct("waiting", $scope.rms_headers.waiting_headers)
        $scope.node_struct = new header_struct("node", $scope.rms_headers.node_headers)
        $scope.structs = {
            "running" : $scope.running_struct
            "waiting" : $scope.waiting_struct
            "node" : $scope.node_struct
        }
        $scope.reload= () ->
            $scope.update_info_timeout = $timeout($scope.reload, 5000)
            $.ajax
                url      : "{% url 'rms:get_rms_json' %}"
                dataType : "json"
                data:
                    "angular" : true
                success  : (json) =>
                    $scope.$apply(() ->
                        $scope.run_list = json.run_table
                        $scope.wait_list = json.wait_table
                        $scope.node_list = json.node_table
                    )
                    # fetch file ids
                    fetch_list = []
                    for _id in $scope.io_list
                        fetch_list.push($scope.io_dict[_id].get_id())
                    if fetch_list.length
                        $.ajax
                            url     : "{% url 'rms:get_file_content' %}"
                            data    :
                                "file_ids" : angular.toJson(fetch_list)
                            success : (xml) =>
                                parse_xml_response(xml)
                                xml = $(xml)
                                for _id in $scope.io_list
                                    $scope.io_dict[_id].feed(xml)
                                $scope.$digest()
        $scope.valid_file = (std_val) ->
             # to be improved, transfer raw data (error = -1, 0 = no file, > 0 = file with content)
             if std_val == "---" or std_val == "err" or std_val == "0 B"
                 return 0
             else
                 return 1
        $scope.render_helper = {
            "host" : (name) ->
                return ["", "<b>#{name}</b>"]
            "load" : (load) ->
                if $scope.cur_table == "node"
                    cur_m = load.match(/(\d+\.\d+).*/)
                    if cur_m
                        max_load = 16.0
                        load = Math.min(cur_m[0], max_load)
                        load_val = $.sprintf("%3.2f", load)
                        width = parseInt(98 * load / max_load)
                        ret_el = "<div>
                            <div class='leftfloat load_value'><b>#{load_val}</b></div>
                            <div class='load_outer'><div class='load_inner' style='width: #{width}px;'></div></div>
                        </div>"
                        return ["", ret_el]
                    else
                        return ["", "<b>#{load}</b>"]
                else
                    return ["", load]
            "stdout" : (val) ->
                if val == "---" or val == "err"
                    return ["", "<b>#{val}</b>"]
                else
                    return ["s", "<input type='button' class='btn btn-xs btn-success' value='#{val}' ng-click='click()'></input>"]
        }
        $scope.get_io_link_class = (job, io_type) ->
            io_id = "#{job[0]}.#{job[1]}.#{io_type}"
            if io_id in $scope.io_list
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.activate_io = (job, io_type) ->
            io_id = "#{job[0]}.#{job[1]}.#{io_type}"
            if io_id not in $scope.io_list
                # create new tab
                $scope.io_list.push(io_id)
                $scope.io_dict[io_id] = new io_struct(job[0], job[1], io_type)
            # activate tab
            $scope.io_dict[io_id].active = true
        $scope.close_io = (io_struct) ->
            $scope.io_list = (entry for entry in $scope.io_list when entry != io_struct.get_id())
            delete $scope.io_dict[io_struct.get_id()]
        $.ajax
            url      : "{% url 'rms:get_user_setting' %}"
            dataType : "json"
            success  : (json) =>
                for key, value of json
                    $scope.structs[key].set_disabled(value)
                $scope.$apply(() ->
                    $scope.header_filter_set = true
                )
                $scope.reload()
]).directive("running", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("running_table.html")
        link : (scope, el, attrs) ->
    }
).directive("waiting", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("waiting_table.html")
        link : (scope, el, attrs) ->
    }
).directive("node", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("node_table.html")
        link : (scope, el, attrs) ->
    }
).directive("iostruct", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("iostruct.html")
        link : (scope, el, attrs) ->
    }
).directive("headers", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("headers.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).directive("rmsline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsline.html")
        link : (scope, el, attrs) ->
            scope.struct_name = attrs["struct"]
            scope.get_display_data = (data) ->
                return scope[scope.struct_name].display_data(data)
    }
).directive("rmsrunline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsrunline.html")
        link : (scope, el, attrs) ->
    }
).directive("headertoggle", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("header_toggle.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).run(($templateCache) ->
    $templateCache.put("running_table.html", running_table)
    $templateCache.put("waiting_table.html", waiting_table)
    $templateCache.put("node_table.html", node_table)
    $templateCache.put("headers.html", headers)
    $templateCache.put("rmsline.html", rmsline)
    $templateCache.put("rmsrunline.html", rmsrunline)
    $templateCache.put("header_toggle.html", header_toggle)
    $templateCache.put("iostruct.html", iostruct)
)

{% endinlinecoffeescript %}

</script>

