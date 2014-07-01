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
        <tr rmsrunline ng-repeat-start="data in run_list | paginator2:this.pagRun" >
        </tr>
        <tr ng-repeat-end ng-show="data.files != '0' && running_struct.toggle['files']">
            <td colspan="99"><fileinfo job="data" files="files" fis="fis"></fileinfo></td>
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
        <tr rmsline ng-repeat="data in wait_list | paginator2:this.pagWait"></tr>
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
        <tr rmsnodeline ng-repeat="data in node_list | paginator2:this.pagNode" ng-class="get_class(data)"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="node_struct"></tr>
    </tfoot>
</table>
"""

iostruct = """
    <h4>
        {{ io_struct.get_file_info() }}, 
        <input type="button" class="btn btn-sm btn-warning" value="close" ng-click="close_io(io_struct)"></input>
        <input type="button" ng-class="io_struct.update && 'btn btn-sm btn-success' || 'btn btn-sm'" value="update" ng_click="io_struct.update = !io_struct.update"></input>
    </h4>
    <div ng-show="io_struct.valid"> 
        <tt>
            <textarea ui-codemirror="editorOptions" ng-model="io_struct.text">
            </textarea>
        </tt>
    </div>
"""

headers = """
<th ng-repeat="entry in struct.display_headers()">{{ entry }}</th>
"""

header_toggle = """
<th colspan="{{ struct.headers.length }}">
    <form class="inline">
        <input
            ng-repeat="entry in struct.headers"
            type="button"
            ng-class="struct.get_btn_class(entry)"
            value="{{ entry }}"
            ng-click="struct.change_entry(entry)"
            ng-show="struct.header_not_hidden(entry)"
        ></input>
    </form>
</th>
"""

filesinfo = """
<div ng-repeat="file in jfiles">
    <div>
        <input
            type="button"
            ng-class="fis[file[0]].show && 'btn btn-xs btn-success' || 'btn btn-xs'"
            ng-click="fis[file[0]].show = !fis[file[0]].show"
            ng-value="fis[file[0]].show && 'hide' || 'show'"></input>
        {{ file[0] }}, {{ file[2] }} Bytes
    </div>
    <div ng-show="fis[file[0]].show">
        <textarea rows="{{ file[4] }}" cols="120" readonly="readonly">{{ file[1] }}</textarea>
    </div>
</div>
"""

rmsnodeline = """
<td ng-show="node_struct.toggle['host']">
    {{ data.host }}
    <button type="button" class="pull-right btn btn-xs btn-primary" ng-show="has_rrd(data.host)" ng-click="show_node_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="node_struct.toggle['queues']">
    <queuestate operator="rms_operator" host="data"></queuestate>
</td>
<td ng-show="node_struct.toggle['complex']">
    {{ data.complex }}
</td>
<td ng-show="node_struct.toggle['pe_list']">
    {{ data.pe_list }}
</td>
<td ng-show="node_struct.toggle['load']">
    <span ng-switch on="valid_load(data.load)">
        <span ng-switch-when="1">
            <div class="pull-left"><b>{{ data.load }}</b>&nbsp;</div>
            <div class="pull-right" style="width:140px; height:10px;">
                <progressbar value="get_load(data.load)" animate="false"></progressbar>
            </div>
        </span>
        <span ng-switch-when="0">
            <b>{{ data.load }}</b>
        </span>    
    </span>
</td>
<td ng-show="node_struct.toggle['slots_used']">
    {{ data.slots_used }}
</td>
<td ng-show="node_struct.toggle['slots_reserved']">
    {{ data.slots_reserved }}
</td>
<td ng-show="node_struct.toggle['slots_total']">
    {{ data.slots_total }}
</td>
<td ng-show="node_struct.toggle['jobs']">
    {{ data.jobs }}
</td>
"""

queuestateoper = """
<div>
    <div class="btn-group" ng-repeat="(queue, state) in get_states()" ng-show="queues_defined()">
        <button type="button" class="btn btn-xs dropdown-toggle" ng-class="get_queue_class(state, 'btn')" data-toggle="dropdown">
            {{ queue }} : {{ state }} <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-show="enable_ok(state)" ng-click="queue_control('enable', queue)">
                <a href="#">Enable {{ queue }}@{{ host.host }}</a>
            </li>
            <li ng-show="disable_ok(state)" ng-click="queue_control('disable', queue)">
                <a href="#">Disable {{ queue }}@{{ host.host }}</a>
            </li>
            <li ng-show="clear_error_ok(state)" ng-click="queue_control('clear_error', queue)">
                <a href="#">Clear error on {{ queue }}@{{ host.host }}</a>
            </li>
        </ul>
    </div>
    <span ng-show="!queues_defined()">
        N/A
    </span>
</div>    
"""

queuestate = """
<div>
    <span class="label" ng-class="get_queue_class(state, 'label')" ng-repeat="(queue, state) in get_states()">
        {{ queue }} : {{ state }}
    </span>
</div>    
"""

jobactionoper = """
<div>
    <div class="btn-group">
        <button type="button" class="btn btn-xs dropdown-toggle btn-primary" data-toggle="dropdown">
            Action <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-click="job_control('delete', false)">
                <a href="#">Delete</a>
            </li>
            <li ng-click="job_control('delete', true)">
                <a href="#">force Delete</a>
            </li>
        </ul>
    </div>
</div>
"""

jobaction = """
<div>
---
</div>
"""

rmsline = """
<td ng-show="waiting_struct.toggle['job_id']">
    {{ data.job_id }}
</td>
<td ng-show="waiting_struct.toggle['task_id']">
    {{ data.task_id }}
</td>
<td ng-show="waiting_struct.toggle['name']">
    {{ data.name }}
</td>
<td ng-show="waiting_struct.toggle['requested_pe']">
    {{ data.requested_pe }}
</td>
<td ng-show="waiting_struct.toggle['owner']">
    {{ data.owner }}
</td>
<td ng-show="waiting_struct.toggle['state']">
    <b>{{ data.state }}</b>
</td>
<td ng-show="waiting_struct.toggle['complex']">
    {{ data.complex }}
</td>
<td ng-show="waiting_struct.toggle['queue']">
    {{ data.queue }}
</td>
<td ng-show="waiting_struct.toggle['queue_time']">
    {{ data.queue_time }}
</td>
<td ng-show="waiting_struct.toggle['wait_time']">
    {{ data.wait_time }}
</td>
<td ng-show="waiting_struct.toggle['left_time']">
    {{ data.left_time }}
</td>
<td ng-show="waiting_struct.toggle['priority']">
    {{ data.priority }}
</td>
<td ng-show="waiting_struct.toggle['depends']">
    {{ data.depends || '---' }}
</td>
<td ng-show="waiting_struct.toggle['action']">
    <jobaction job="data" operator="rms_operator"></jobaction>
</td>
"""

rmsrunline = """
<td ng-show="running_struct.toggle['job_id']">
    {{ data.job_id }}
    <button type="button" class="btn btn-xs btn-primary" ng-show="has_rrd(data.nodelist)" ng-click="show_job_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="running_struct.toggle['task_id']">
    {{ data.task_id }}
</td>
<td ng-show="running_struct.toggle['name']">
    {{ data.name }}
</td>
<td ng-show="running_struct.toggle['real_user']">
    {{ data.real_user }}
</td>
<td ng-show="running_struct.toggle['granted_pe']">
    {{ data.granted_pe }}
</td>
<td ng-show="running_struct.toggle['owner']">
    {{ data.owner }}
</td>
<td ng-show="running_struct.toggle['state']">
    <b>{{ data.state }}</b>
</td>
<td ng-show="running_struct.toggle['complex']">
    {{ data.complex }}
</td>
<td ng-show="running_struct.toggle['queue_name']">
    {{ data.queue_name }}
</td>
<td ng-show="running_struct.toggle['start_time']">
    {{ data.start_time }}
</td>
<td ng-show="running_struct.toggle['run_time']">
    {{ data.run_time }}
</td>
<td ng-show="running_struct.toggle['left_time']">
    {{ data.left_time }}
</td>
<td ng-show="running_struct.toggle['load']">
    {{ data.load }}
</td>
<td ng-show="running_struct.toggle['stdout']">
    <span ng-switch on="valid_file(data.stdout)">
        <span ng-switch-when="1">
            <input type="button" ng-class="get_io_link_class(data, 'stdout')" ng-value="data.stdout" ng-click="activate_io(data, 'stdout')"></input>
        </span>
        <span ng-switch-when="0">
            {{ data.stdout }}
        </span>
    </span>
</td>
<td ng-show="running_struct.toggle['stderr']">
    <span ng-switch on="valid_file(data.stderr)">
        <span ng-switch-when="1">
            <input type="button" ng-class="get_io_link_class(data, 'stderr')" ng-value="data.stderr" ng-click="activate_io(data, 'stderr')"></input>
        </span>
        <span ng-switch-when="0">
            {{ data.stderr }}
        </span>
    </span>
</td>
<td ng-show="running_struct.toggle['files']">
    {{ data.files }}
</td>
<td ng-show="running_struct.toggle['nodelist']">
    {{ get_nodelist(data) }}
</td>
<td ng-show="running_struct.toggle['action']">
    <jobaction job="data" operator="rms_operator"></jobaction>
</td>
"""

{% endverbatim %}

rms_module = angular.module("icsw.rms", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.codemirror"])

angular_module_setup([rms_module])

LOAD_RE = /(\d+.\d+).*/

class header_struct
    constructor: (@table, @headers, @hidden_headers) ->
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
        call_ajax
            url      : "{% url 'rms:set_user_setting' %}"
            dataType : "json"
            data:
                "data" : angular.toJson({"table" : @table, "row" : entry, "enabled" : @toggle[entry]})
            success  : (json) =>
        @build_cache()
    display_headers : () =>
        return (v[0] for v in _.zip.apply(null, [@headers, @togglec]) when v[1][0] and v[0] not in @hidden_headers)
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
    map_headers : (simple_list) =>
        return (_.zipObject(@headers, _line) for _line in simple_list)
    header_not_hidden : (entry) ->
        return entry not in @hidden_headers
        
class io_struct
    constructor : (@job_id, @task_id, @type) ->
        @resp_xml = undefined
        @text = ""
        # is set to true as soon as we got any data
        @valid = false
        @waiting = true
        @refresh = 0
        @update = true
    get_name : () =>
        if @task_id
            return "#{@job_id}.#{@task_id} (#{@type})"
        else
            return "#{@job_id} (#{@type})"
    get_id : () ->
        return "#{@job_id}.#{@task_id}.#{@type}"
    file_name : () ->
        return @resp_xml.attr("name")
    file_lines : () ->
        return @resp_xml.attr("lines")
    file_size : () ->
        return @resp_xml.attr("size_str")
    get_file_info : () ->
        if @valid
            return "File " + @file_name() + " (" + @file_size() + " in " + @file_lines() + " lines)"
        else if @waiting
            return "waiting for data"
        else
            return "nothing found"
    feed : (xml) => 
        @waiting = false
        found_xml = $(xml).find("response file_info[id='" + @get_id() + "']")
        if found_xml.length
            @valid = true
            @resp_xml = found_xml
            if @text != @resp_xml.text()
                @text = @resp_xml.text()
                @refresh++
        else
            @update = false
            #@valid = false
            #@resp_xml = undefined
            #@text = ""
            @refresh++
          
rms_module.value('ui.config', {
    codemirror : {
        mode : 'text/x-php'
        lineNumbers: true
        matchBrackets: true
    }
})

class device_info
    constructor: (@name, in_list) ->
        @pk = in_list[0]
        @rrd = in_list[1]

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
            lineNumbers : true
            readOnly : true
            styleActiveLine: true
            indentUnit : 4
        }
        $scope.io_dict = {}
        $scope.io_list = []
        $scope.run_list = []
        $scope.wait_list = []
        $scope.node_list = []
        $scope.device_dict = {}
        $scope.device_dict_set = false
        # set to false to avoid destroying of subscopes (graphs)
        $scope.refresh = true
        # fileinfostruct
        $scope.fis = {}
        $scope.running_struct = new header_struct("running", $scope.rms_headers.running_headers, [])
        $scope.waiting_struct = new header_struct("waiting", $scope.rms_headers.waiting_headers, [])
        $scope.node_struct = new header_struct("node", $scope.rms_headers.node_headers, ["state"])
        $scope.rms_operator = false
        $scope.structs = {
            "running" : $scope.running_struct
            "waiting" : $scope.waiting_struct
            "node" : $scope.node_struct
        }
        $scope.$on("icsw.disable_refresh", () ->
            $scope.refresh = false
        )
        $scope.$on("icsw.enable_refresh", () ->
            $scope.refresh = true
        )
        $scope.reload= () ->
            $scope.rms_operator = $scope.acl_modify(null, "backbone.user.rms_operator")
            if $scope.update_info_timeout
                $timeout.cancel($scope.update_info_timeout)
            # refresh every 10 seconds
            $scope.update_info_timeout = $timeout($scope.reload, 10000)
            if $scope.refresh
                call_ajax
                    url      : "{% url 'rms:get_rms_json' %}"
                    dataType : "json"
                    success  : (json) =>
                        $scope.$apply(() ->
                            $scope.files = json.files
                            $scope.run_list = $scope.running_struct.map_headers(json.run_table)
                            $scope.wait_list = $scope.waiting_struct.map_headers(json.wait_table)
                            $scope.node_list = $scope.node_struct.map_headers(json.node_table)
                            # calculate max load
                            valid_loads = (parseFloat(entry.load) for entry in $scope.node_list when entry.load.match(LOAD_RE))
                            if valid_loads.length
                                $scope.max_load = _.max(valid_loads)
                                # round to next multiple of 4
                                $scope.max_load = 4 * parseInt(($scope.max_load + 3.9999) / 4)
                            else
                                $scope.max_load = 4
                        )
                        if not $scope.device_dict_set
                            node_names = (entry[0] for entry in json.node_table)
                            $scope.device_dict_set = true
                            call_ajax
                                url      : "{% url 'rms:get_node_info' %}"
                                data     :
                                    devnames : angular.toJson(node_names)
                                dataType : "json"
                                success  : (json) =>
                                    $scope.$apply(() ->
                                        for name of json
                                            $scope.device_dict[name] = new device_info(name, json[name])
                                    )
                        # fetch file ids
                        fetch_list = []
                        for _id in $scope.io_list
                            if $scope.io_dict[_id].update
                                fetch_list.push($scope.io_dict[_id].get_id())
                        if fetch_list.length
                            call_ajax
                                url     : "{% url 'rms:get_file_content' %}"
                                data    :
                                    "file_ids" : angular.toJson(fetch_list)
                                success : (xml) =>
                                    parse_xml_response(xml)
                                    xml = $(xml)
                                    for _id in $scope.io_list
                                        $scope.io_dict[_id].feed(xml)
                                    $scope.$digest()
        $scope.get_io_link_class = (job, io_type) ->
            io_id = "#{job.job_id}.#{job.task_id}.#{io_type}"
            if io_id in $scope.io_list
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.activate_io = (job, io_type) ->
            io_id = "#{job.job_id}.#{job.task_id}.#{io_type}"
            if io_id not in $scope.io_list
                # create new tab
                $scope.io_list.push(io_id)
                $scope.io_dict[io_id] = new io_struct(job.job_id, job.task_id, io_type)
            # activate tab
            $scope.io_dict[io_id].active = true
            # reload
            $scope.reload()
        $scope.close_io = (io_struct) ->
            $scope.io_list = (entry for entry in $scope.io_list when entry != io_struct.get_id())
            delete $scope.io_dict[io_struct.get_id()]
        $scope.$on("queue_control", (event, host, command, queue) ->
            call_ajax
                url      : "{% url 'rms:control_queue' %}"
                data     : {
                    "queue"   : queue
                    "host"    : host.host
                    "command" : command 
                }
                success  : (xml) =>
                    parse_xml_response(xml)
        )
        $scope.$on("job_control", (event, job, command, force) ->
            call_ajax
                url      : "{% url 'rms:control_job' %}"
                data     : {
                    "job_id"  : job.job_id
                    "task_id" : job.task_id
                    "command" : command 
                }
                success  : (xml) =>
                    parse_xml_response(xml)
        )
        $scope.show_rrd = (event, name_list) ->
            dev_pks = ($scope.device_dict[name].pk for name in name_list).join(",")
            rrd_txt = """
<div class="panel panel-default">
    <div class="panel-body">
        <h2>Device #{name}</h2>
        <div ng-controller='rrd_ctrl'>
            <rrdgraph devicepk='#{dev_pks}' selectkeys="load.*,net.all.*,mem.used.phys$" draw="1" mergedevices="0" graphsize="240x100">
            </rrdgraph>
        </div>
    </div>
</div>
"""
            # disable refreshing
            $scope.refresh = false
            $scope.rrd_div = angular.element(rrd_txt)
            $compile($scope.rrd_div)($scope)
            $scope.rrd_div.simplemodal
                opacity      : 50
                position     : [event.pageY, event.pageX]
                autoResize   : true
                autoPosition : true
                minWidth     : "1280px"
                minHeight   : "800px"
                onShow: (dialog) -> 
                    dialog.container.draggable()
                    #$("#simplemodal-container").css("height", "auto")
                    #$("#simplemodal-container").css("width", "auto")
                onClose: =>
                    # destroy scopes
                    $scope.refresh = true
                    $.simplemodal.close()
        call_ajax
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
            scope.get_class = (data) ->
                parts = data.state.split("")
                if _.indexOf(parts, "a") >= 0 or _.indexOf(parts, "u") >= 0
                    return "danger"
                else if _.indexOf(parts, "d") >= 0
                    return "warning"
                else
                    return ""
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
            scope.valid_file = (std_val) ->
                # to be improved, transfer raw data (error = -1, 0 = no file, > 0 = file with content)
                if std_val == "---" or std_val == "err" or std_val == "error" or std_val == "0 B"
                    return 0
                else
                    return 1
            scope.get_nodelist = (job) ->
                nodes = job.nodelist.split(",")
                r_list = []
                _.forEach(_.countBy(nodes), (key, value) ->
                    if key == 1
                        r_list.push(value)
                    else
                        r_list.push("#{value}(#{key})")
                )
                return r_list.join(",")
            scope.get_rrd_nodes = (nodelist) ->
                nodes = _.uniq((entry.split("(")[0] for entry in nodelist.split(",")))
                rrd_nodes = (entry for entry in nodes when entry of scope.device_dict and scope.device_dict[entry].rrd)
                return rrd_nodes
            scope.has_rrd = (nodelist) ->
                rrd_nodes = scope.get_rrd_nodes(nodelist)
                return if rrd_nodes.length then true else false
            scope.show_job_rrd = (event, job) ->
                rrd_nodes = scope.get_rrd_nodes(job.nodelist)
                scope.show_rrd(event, rrd_nodes)
    }
).directive("rmsnodeline", ($templateCache, $sce, $compile) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsnodeline.html")
        link : (scope, el, attrs) ->
            scope.valid_load = (load) ->
                return if load.match(LOAD_RE) then 1 else 0
            scope.get_load = (load) ->
                cur_m = load.match(LOAD_RE)
                if cur_m
                    return parseInt(100 * load / scope.max_load)
                else
                    return 0
            scope.has_rrd = (name) ->
                if name of scope.device_dict
                    return scope.device_dict[name].rrd
                else
                    return false
            scope.show_node_rrd = (event, node) ->
                scope.show_rrd(event, [node.host])
    }
).directive("headertoggle", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("header_toggle.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).directive("jobaction", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        #template : $templateCache.get("queue_state.html")
        scope:
            job : "="
            operator : "="
        replace : true
        compile : (tElement, tAttr) ->
            return (scope, el, attrs) ->
                scope.job_control = (command, force) ->
                    scope.$emit("job_control", scope.job, command, force)
                if scope.operator
                    is_oper = true
                else if scope.job.real_user == '{{ user.login }}'
                    is_oper = true
                else
                    is_oper = false
                el.append($compile($templateCache.get(if is_oper then "job_action_oper.html" else "job_action.html"))(scope))
      
    }
).directive("queuestate", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        #template : $templateCache.get("queue_state.html")
        scope:
            host : "="
            operator : "="
        replace : true
        compile : (tElement, tAttr) ->
            return (scope, el, attrs) ->
                scope.get_states = () ->
                    states = scope.host.state.split("/")
                    queues = scope.host.queues.split("/")
                    if queues.length != states.length
                        states = (states[0] for queue in queues)
                    return _.zipObject(queues, states)
                scope.queues_defined = () ->
                    return if scope.host.state.length then true else false
                scope.enable_ok = (state) ->
                    return if state.match(/d/g) then true else false
                scope.disable_ok = (state) ->
                    return if not state.match(/d/g) then true else false
                scope.clear_error_ok = (state) ->
                    return if state.match(/e/gi) then true else false
                scope.get_queue_class = (state, prefix) ->
                    if state.match(/a|u/gi)
                        return "#{prefix}-danger"
                    else if state.match(/d/gi)
                        return "#{prefix}-warning"
                    else
                        return "#{prefix}-success"
                scope.queue_control = (command, queue) ->
                    scope.$emit("queue_control", scope.host, command, queue)
                el.append($compile($templateCache.get(if scope.operator then "queue_state_oper.html" else "queue_state.html"))(scope))
      
    }
).directive("fileinfo", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        scope:
            job   : "="
            files : "="
            fis   : "="
        template : $templateCache.get("files_info.html")
        link : (scope, el, attrs) ->
            full_id = if scope.job.task_id then "#{scope.job.job_id}.#{scope.job.task_id}" else scope.job.job_id
            scope.full_id = full_id
            if full_id of scope.files
                scope.jfiles = scope.files[full_id]
                for file in scope.jfiles
                    if not scope.fis[file[0]]?
                        scope.fis[file[0]] = {
                            "show" : true
                        }
            else
                scope.jfiles = []
    }
).run(($templateCache) ->
    $templateCache.put("running_table.html", running_table)
    $templateCache.put("waiting_table.html", waiting_table)
    $templateCache.put("node_table.html", node_table)
    $templateCache.put("headers.html", headers)
    $templateCache.put("rmsline.html", rmsline)
    $templateCache.put("rmsrunline.html", rmsrunline)
    $templateCache.put("rmsnodeline.html", rmsnodeline)
    $templateCache.put("header_toggle.html", header_toggle)
    $templateCache.put("iostruct.html", iostruct)
    $templateCache.put("queue_state_oper.html", queuestateoper)
    $templateCache.put("queue_state.html", queuestate)
    $templateCache.put("job_action_oper.html", jobactionoper)
    $templateCache.put("job_action.html", jobaction)
    $templateCache.put("files_info.html", filesinfo)
)

add_rrd_directive(rms_module)

{% endinlinecoffeescript %}

</script>

