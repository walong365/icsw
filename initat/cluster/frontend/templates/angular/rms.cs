-{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

running_table = """
<table class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="run_list" pag_settings="pagRun" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="running_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmsrunline ng-repeat-start="data in run_list | paginator2:pagRun" ></tr>
        <tr ng-repeat-end ng-show="data.files.value != '0' && running_struct.toggle['files']">
            <td colspan="99"><fileinfo job="data" files="files" fis="fis"></fileinfo></td>
        </tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="running_struct"></tr>
    </tfoot>
</table>
"""

waiting_table = """
<table class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="wait_list" pag_settings="pagWait" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="waiting_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmswaitline ng-repeat="data in wait_list | paginator2:pagWait"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="waiting_struct"></tr>
    </tfoot>
</table>
"""

done_table ="""
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="done_list" pag_settings="pagDone" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="done_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmsdoneline ng-repeat="data in done_list | paginator2:pagDone"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="done_struct"></tr>
    </tfoot>
</table>
"""

node_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="node_list" pag_settings="pagNode" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="node_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmsnodeline ng-repeat="data in node_list | paginator2:pagNode" ng-class="get_class(data)"></tr>
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
<th ng-repeat="entry in struct.display_headers()" colspan="{{ struct.get_span(entry) }}">{{ struct.get_header(entry) }}</th>
"""

header_toggle = """
<th colspan="{{ struct.headers.length }}">
    <form class="inline">
        <input
            ng-repeat="entry in struct.headers"
            type="button"
            ng-class="struct.get_btn_class(entry)"
            value="{{ struct.get_header(entry) }}"
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
    {{ data.host.value }}&nbsp;<button type="button" class="pull-right btn btn-xs btn-primary" ng-show="has_rrd(data.host)" ng-click="show_node_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="node_struct.toggle['queues']">
    <queuestate operator="rms_operator" host="data"></queuestate>
</td>
<td ng-show="node_struct.toggle['type']">
    {{ data.type.value }}
</td>
<td ng-show="node_struct.toggle['complex']">
    {{ data.complex.value }}
</td>
<td ng-show="node_struct.toggle['pe_list']">
    {{ data.pe_list.value }}
</td>
<td ng-show="node_struct.toggle['load']">
    <span ng-switch on="valid_load(data.load)">
        <span ng-switch-when="1">
            <div class="row">
                <div class="col-sm-3"><b>{{ data.load.value }}</b>&nbsp;</div>
                <div class="col-sm-9" style="width:140px; height:20px;">
                    <progressbar value="get_load(data.load)" animate="false"></progressbar>
                </div>
            </div>
        </span>
        <span ng-switch-when="0">
            <b>{{ data.load.value }}</b>
        </span>    
    </span>
</td>
<td ng-show="node_struct.toggle['slots_used']">
    <div ng-repeat="entry in data.load_vector" class="row">
         <div class="col-sm-12" style="width:140px; height:20px;">
             <progressbar max="entry[0]" value="entry[1]" animate="false" type="info"><span style="color:black;">{{ entry[1] }} / {{ entry[0] }}</span></progressbar>
         </div>
    </div>
</td>
<td ng-show="node_struct.toggle['slots_used']">
    {{ data.slots_used.value }}
</td>
<td ng-show="node_struct.toggle['slots_reserved']">
    {{ data.slots_reserved.value }}
</td>
<td ng-show="node_struct.toggle['slots_total']">
    {{ data.slots_total.value }}
</td>
<td ng-show="node_struct.toggle['jobs']">
    {{ data.jobs.value }}
</td>
"""

queuestateoper = """
<div ng-repeat="(queue, state) in get_states()" ng-show="queues_defined()" class="row">
    <div class="col-sm-12 btn-group">
        <button type="button" class="btn btn-xs dropdown-toggle" ng-class="get_queue_class(state, 'btn')" data-toggle="dropdown">
            {{ queue }} : {{ state }} <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-show="enable_ok(state)" ng-click="queue_control('enable', queue)">
                <a href="#">Enable {{ queue }}@{{ host.host.value }}</a>
            </li>
            <li ng-show="disable_ok(state)" ng-click="queue_control('disable', queue)">
                <a href="#">Disable {{ queue }}@{{ host.host.value }}</a>
            </li>
            <li ng-show="clear_error_ok(state)" ng-click="queue_control('clear_error', queue)">
                <a href="#">Clear error on {{ queue }}@{{ host.host.value }}</a>
            </li>
        </ul>
    </div>
</div>
<span ng-show="!queues_defined()">
    N/A
</span>
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
            <li ng-show="mode=='w'" ng-click="change_priority()">
                <a href="#">change priority</a>
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

rmsdoneline = """
<td ng-show="done_struct.toggle['job_id']">
    {{ data.rms_job.jobid }}&nbsp;<button type="button" class="pull-right btn btn-xs btn-primary" ng-show="has_rrd(data)" ng-click="show_done_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="done_struct.toggle['task_id']">
    {{ data.rms_job.taskid }}
</td>
<td ng-show="done_struct.toggle['name']">
    {{ data.rms_job.name }}
</td>
<td ng-show="done_struct.toggle['granted_pe']">
    {{ data.granted_pe }}<span ng-show="data.granted_pe">({{ data.slots }})</span>
</td>
<td ng-show="done_struct.toggle['owner']">
    {{ data.rms_job.owner }}
</td>
<td ng-show="done_struct.toggle['queue_time']">
    {{ get_datetime(data.queue_time) }}
</td>
<td ng-show="done_struct.toggle['start_time']">
    {{ get_datetime(data.start_time) }}
</td>
<td ng-show="done_struct.toggle['end_time']">
    {{ get_datetime(data.end_time) }}
</td>
<td ng-show="done_struct.toggle['wait_time']">
    {{ get_waittime(data) }}
</td>
<td ng-show="done_struct.toggle['run_time']">
    {{ get_runtime(data) }}
</td>
<td ng-show="done_struct.toggle['queue']">
    {{ data.rms_queue.name }}
</td>
<td ng-show="done_struct.toggle['exit_status']" ng-class="exit_status_wrapper_class(data)">
    {{ get_exit_status_str(data) }} {{ data.exit_status_str }}
    <div class="pull-right" ng-show="exit_status_class(data)">
        <span ng-class="exit_status_class(data)"></span>
    </div>
</td>
<td ng-show="done_struct.toggle['failed']" title="{{ get_failed_title(data) }}">
    <span class="label" ng-class="get_failed_class(data)"><span ng-class="get_failed_glyphicon(data)"></span></span>&nbsp;{{ get_failed_str(data) }} {{ data.failed_str }}
</td>
<td ng-show="done_struct.toggle['failed']" class="text-center">
    {{ data.failed }}
</td>
<td ng-show="done_struct.toggle['nodelist']">
    {{ show_pe_info(data) }}
</td>
"""

rmswaitline = """
<td ng-show="waiting_struct.toggle['job_id']">
    {{ data.job_id.value }}
</td>
<td ng-show="waiting_struct.toggle['task_id']">
    {{ data.task_id.value }}
</td>
<td ng-show="waiting_struct.toggle['name']">
    {{ data.name.value }}
</td>
<td ng-show="waiting_struct.toggle['requested_pe']">
    {{ data.requested_pe.value }}
</td>
<td ng-show="waiting_struct.toggle['owner']">
    {{ data.owner.value }}
</td>
<td ng-show="waiting_struct.toggle['state']">
    <b>{{ data.state.value }}</b>
</td>
<td ng-show="waiting_struct.toggle['complex']">
    {{ data.complex.value }}
</td>
<td ng-show="waiting_struct.toggle['queue']">
    {{ data.queue.value }}
</td>
<td ng-show="waiting_struct.toggle['queue_time']">
    {{ data.queue_time.value }}
</td>
<td ng-show="waiting_struct.toggle['wait_time']">
    {{ data.wait_time.value }}
</td>
<td ng-show="waiting_struct.toggle['left_time']">
    {{ data.left_time.value }}
</td>
<td ng-show="waiting_struct.toggle['exec_time']">
    {{ data.exec_time.value }}
</td>
<td ng-show="waiting_struct.toggle['prio']">
    {{ data.prio.value }}
</td>
<td ng-show="waiting_struct.toggle['priority']">
    {{ data.priority.value }}
</td>
<td ng-show="waiting_struct.toggle['depends']">
    {{ data.depends.value || '---' }}
</td>
<td ng-show="waiting_struct.toggle['action']">
    <jobaction job="data" operator="rms_operator" mode="'w'"></jobaction>
</td>
"""

rmsrunline = """
<td ng-show="running_struct.toggle['job_id']">
    {{ data.job_id.value }}&nbsp;<button type="button" class="btn btn-xs btn-primary" ng-show="has_rrd(data.nodelist)" ng-click="show_job_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="running_struct.toggle['task_id']">
    {{ data.task_id.value }}
</td>
<td ng-show="running_struct.toggle['name']">
    {{ data.name.value }}
</td>
<td ng-show="running_struct.toggle['real_user']">
    {{ data.real_user.value }}
</td>
<td ng-show="running_struct.toggle['granted_pe']">
    {{ data.granted_pe.value }}
</td>
<td ng-show="running_struct.toggle['owner']">
    {{ data.owner.value }}
</td>
<td ng-show="running_struct.toggle['state']">
    <b>{{ data.state.value }}</b>
</td>
<td ng-show="running_struct.toggle['complex']">
    {{ data.complex.value }}
</td>
<td ng-show="running_struct.toggle['queue_name']">
    {{ data.queue_name.value }}
</td>
<td ng-show="running_struct.toggle['start_time']">
    {{ data.start_time.value }}
</td>
<td ng-show="running_struct.toggle['run_time']">
    {{ data.run_time.value }}
</td>
<td ng-show="running_struct.toggle['left_time']">
    {{ data.left_time.value }}
</td>
<td ng-show="running_struct.toggle['load']">
    {{ data.load.value }}
</td>
<td ng-show="running_struct.toggle['stdout']">
    <span ng-switch on="valid_file(data.stdout.value)">
        <input type="button" ng-class="get_io_link_class(data, 'stdout')" ng-value="data.stdout.value" ng-click="activate_io(data, 'stdout')"></input>
    </span>
</td>
<td ng-show="running_struct.toggle['stderr']">
    <span ng-switch on="valid_file(data.stderr.value)">
        <input type="button" ng-class="get_io_link_class(data, 'stderr')" ng-value="data.stderr.value" ng-click="activate_io(data, 'stderr')"></input>
    </span>
</td>
<td ng-show="running_struct.toggle['files']">
    {{ data.files.value }}
</td>
<td ng-show="running_struct.toggle['nodelist']">
    {{ get_nodelist(data) }}
</td>
<td ng-show="running_struct.toggle['action']">
    <jobaction job="data" operator="rms_operator" mode="'r'"></jobaction>
</td>
"""

change_pri_template = """
<div class="modal-header"><h3>Change priority of job {{ get_job_id() }}</h3></div>
<div class="modal-body">
    <h4>Allowed priority range:</h4>
    <ul class="list-group">
        <li class="list-group-item">lowest priority: <tt>-1023</tt></li>
        <li class="list-group-item">highest priority: <tt>{{ get_max_priority() }}</tt></li>
    </ul>
    <form name="priform" class="form-horizontal">
    <div class="row form-group">
        <div class="col-md-4">
            <label class="control-label pull-right">Priority (actual: {{ job.priority.value }}):</label>
        </div>
        <div class="controls col-md-8">
            <input class="form-control input-sm" type="number" ng-model="cur_priority" min="-1023" max="{{ get_max_priority() }}" required></input>
        </div>
    </div>
    </form>
</div>
<div class="modal-footer">
    <button class="btn btn-primary" ng-click="ok()" ng-show="priform.$valid">Modify</button>
    <button class="btn btn-warning" ng-click="cancel()">Cancel</button>
</div>
""" 

{% endverbatim %}

rms_module = angular.module("icsw.rms", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.codemirror", "icsw.d3", "icsw.dimple", "angular-dimple", "ui.bootstrap.datetimepicker"])


angular_module_setup([rms_module])

LOAD_RE = /(\d+.\d+).*/

class header_struct
    constructor: (@table, h_struct, @hidden_headers) ->
        _dict = {}
        @headers = []
        @attributes = {}
        for entry in h_struct
            @headers.push(entry[0])
            @attributes[entry[0]] = entry[1]
            _dict[entry[0]] = true
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
    get_span: (entry) ->
        if @attributes[entry].span?
            return @attributes[entry].span
        else
            return 1
    get_header: (h_str) ->
        # CamelCase
        h_str = (_entry.substr(0, 1).toUpperCase() + _entry.substr(1) for _entry in h_str.split("_")).join("")
        return h_str
        
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
        @has_rrd = in_list[1]
        # not needed right now?
        @full_name = in_list[2]

class slot_info
    constructor: () ->
        @reset()
    reset: () =>
        @total = 0
        @used = 0
        @reserved = 0
    feed_vector: (in_vec) =>
        if in_vec[0]?
            @total += in_vec[0]
        if in_vec[1]?
            @used += in_vec[1]
        if in_vec[2]?
            @reserved += in_vec[2]
        
DT_FORM = "D. MMM YYYY, HH:mm:ss"

rms_module.controller("rms_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", "$sce", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout, $sce) ->
        access_level_service.install($scope)
        $scope.rms_headers = {{ RMS_HEADERS | safe }}
        $scope.pagRun = paginatorSettings.get_paginator("run", $scope)
        $scope.pagWait = paginatorSettings.get_paginator("wait", $scope)
        $scope.pagDone = paginatorSettings.get_paginator("done", $scope)
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
        $scope.done_list = []
        $scope.device_dict = {}
        $scope.device_dict_set = false
        # slot info
        $scope.slot_info = new slot_info()
        $scope.running_slots = 0
        $scope.waiting_slots = 0
        # set to false to avoid destroying of subscopes (graphs)
        $scope.refresh = true
        # fileinfostruct
        $scope.fis = {}
        $scope.failed_lut = {
            0 : [true, "no failure", "ran and exited normally"]
            1 : [false, "assumedly before job", "failed early in execd"]
            3 : [false, "before writing config", "failed before execd set up local spool"]
            4 : [false, "before writing PID", "shepherd failed to record its pid"]
            6 : [false, "setting processor set", "failed setting up processor set"]
            7 : [false, "before prolog", "failed before prolog"]
            8 : [false, "in prolog", "failed in prolog"]
            9 : [false, "before pestart", "failed before starting PE"]
            10 : [false, "in pestart", "failed in PE starter"]
            11 : [false, "before job", "failed in shepherd before starting job"]
            12 : [true, "before pestop", "ran, but failed before calling PE stop proecdure"]
            13 : [true, "in pestop", "ran, but PE stop procedure failed"]
            14 : [true, "before epilog", "ran, but failed before calling epilog script"]
            15 : [true, "in epilog", "ran, but failed in epilog script"]
            16 : [true, "releasing processor set", "ran, but processor set could not be released"]
            17 : [true, "through signal", "job killed by signal (possibly qdel)"]
            18 : [false, "shepherd returned error", "shepherd died"]
            19 : [false, "before writing exit_status", "shepherd didn't write reports correctly"]
            20 : [false, "found unexpected error file", "shepherd encountered a problem"]
            21 : [false, "in recognizing job", "qmaster asked about an unknown job (not in accounting?)"]
            24 : [true, "migrating (checkpointing jobs)", "ran, will be migrated"]
            25 : [true, "rescheduling", "ran, will be rescheduled"]
            26 : [false, "opening output file", "failed opening stderr/stdout file"]
            27 : [false, "searching requested shell", "failed finding specified shell"]
            28 : [false, "changing to working directory", "failed changing to start directory"]
            29 : [false, "AFS setup", "failed setting up AFS security"]
            30 : [true, "application error returned", "ran and exited 100 - maybe re-scheduled"]
            31 : [false, "accessing sgepasswd file", "failed because sgepasswd not readable (MS Windows)"]
            32 : [false, "entry is missing in password file", "failed because user not in sgepasswd (MS Windows)"]
            33 : [false, "wrong password", "failed because of wrong password against sgepasswd (MS Windows)"]
            34 : [false, "communicating with GE Helper Service", "failed because of failure of helper service (MS Windows)"]
            35 : [false, "before job in GE Helper Service", "failed because of failure running helper service (MS Windows)"]
            36 : [false, "checking configured daemons", "failed because of configured remote startup daemon"]
            37 : [true, "qmaster enforced h_rt, h_cpu or h_vmem limit", "ran, but killed due to exceeding run time limit"]
            38 : [false, "adding supplementary group", "failed adding supplementary gid to job "]
            100 : [true, "assumedly after job", "ran, but killed by a signal (perhaps due to exceeding resources), task died, shepherd died (e.g. node crash),"]
        }
        $scope.exit_status_lut = {
            0 : [1, "ok", ""]
            137 : [-1, "killed", "glyphicon-remove-circle"]
            99 : [0, "rescheduled", "glyphicon-repeat"]
        }
        $scope.running_struct = new header_struct("running", $scope.rms_headers.running_headers, [])
        $scope.waiting_struct = new header_struct("waiting", $scope.rms_headers.waiting_headers, [])
        $scope.done_struct = new header_struct("done", $scope.rms_headers.done_headers, [])
        $scope.node_struct = new header_struct("node", $scope.rms_headers.node_headers, ["state"])
        $scope.rms_operator = false
        $scope.structs = {
            "running" : $scope.running_struct
            "waiting" : $scope.waiting_struct
            "done" : $scope.done_struct
            "node" : $scope.node_struct
        }
        $scope.$on("icsw.disable_refresh", () ->
            $scope.refresh = false
        )
        $scope.$on("icsw.enable_refresh", () ->
            $scope.refresh = true
        )
        $scope.reload = () ->
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
                            # reset counter
                            $scope.running_slots = 0
                            $scope.waiting_slots = 0
                            $scope.files = json.files
                            $scope.run_list = $scope.running_struct.map_headers(json.run_table)
                            $scope.wait_list = $scope.waiting_struct.map_headers(json.wait_table)
                            $scope.node_list = $scope.node_struct.map_headers(json.node_table)
                            $scope.done_list = json.done_table
                            # calculate max load
                            valid_loads = (parseFloat(entry.load.value) for entry in $scope.node_list when entry.load.value.match(LOAD_RE))
                            if valid_loads.length
                                $scope.max_load = _.max(valid_loads)
                                # round to next multiple of 4
                                $scope.max_load = 4 * parseInt(($scope.max_load + 3.9999  ) / 4)
                            else
                                $scope.max_load = 4
                            if $scope.max_load == 0
                                $scope.max_load = 4
                            $scope.slot_info.reset()
                            for entry in $scope.node_list
                                _total = (parseInt(_val) for _val in entry.slots_total.value.split("/"))
                                _used = (parseInt(_val) for _val in entry.slots_used.value.split("/"))
                                _reserved = (parseInt(_val) for _val in entry.slots_reserved.value.split("/"))
                                _size = _.max([_total.length, _used.length, _reserved.length])
                                if _total.length < _size
                                    _total = (_total[0] for _idx in _.range(_size))
                                if _used.length < _size
                                    _used = (_used[0] for _idx in _.range(_size))
                                if _reserved.length < _size
                                    _reserved = (_reserved[0] for _idx in _.range(_size))
                                entry.load_vector = _.zip(_total, _used, _reserved)
                                for _lv in entry.load_vector
                                    if _lv.length and not isNaN(_lv[0])
                                        $scope.slot_info.feed_vector(_lv)
                            # get slot info
                            for _job in $scope.run_list
                                if _job.granted_pe.value == "-"
                                    $scope.running_slots += 1
                                else
                                    $scope.running_slots += parseInt(_job.granted_pe.value.split("(")[1].split(")")[0])
                            for _job in $scope.wait_list
                                if _job.requested_pe.value == "-"
                                    $scope.waiting_slots += 1
                                else
                                    $scope.waiting_slots += parseInt(_job.requested_pe.value.split("(")[1].split(")")[0])
                        )
                        if not $scope.device_dict_set
                            node_names = (entry[0].value for entry in json.node_table)
                            $scope.device_dict_set = true
                            call_ajax
                                url      : "{% url 'rms:get_node_info' %}"
                                data     :
                                    devnames : angular.toJson(node_names)
                                dataType : "json"
                                success  : (json) =>
                                    $scope.$apply(() ->
                                        for name of json
                                            _new_di = new device_info(name, json[name])
                                            $scope.device_dict[name] = _new_di
                                            $scope.device_dict[_new_di.pk] = _new_di
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
            io_id = "#{job.job_id.value}.#{job.task_id.value}.#{io_type}"
            if io_id in $scope.io_list
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.activate_io = (job, io_type) ->
            io_id = "#{job.job_id.value}.#{job.task_id.value}.#{io_type}"
            if io_id not in $scope.io_list
                # create new tab
                $scope.io_list.push(io_id)
                $scope.io_dict[io_id] = new io_struct(job.job_id.value, job.task_id.value, io_type)
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
                    "host"    : host.host.value
                    "command" : command 
                }
                success  : (xml) =>
                    parse_xml_response(xml)
        )
        $scope.$on("job_control", (event, job, command, force) ->
            call_ajax
                url      : "{% url 'rms:control_job' %}"
                data     : {
                    "job_id"  : job.job_id.value
                    "task_id" : job.task_id.value
                    "command" : command 
                }
                success  : (xml) =>
                    parse_xml_response(xml)
        )
        $scope.get_running_info = () ->
            return "running (#{$scope.run_list.length} jobs, #{$scope.running_slots} slots)"
        $scope.get_waiting_info = () ->
            return "waiting (#{$scope.wait_list.length} jobs, #{$scope.waiting_slots} slots)"
        $scope.get_done_info = () ->
            return "done (#{$scope.done_list.length} jobs)"
        $scope.get_node_info = () ->
            return "node (#{$scope.node_list.length} nodes, #{$scope.slot_info.used} of #{$scope.slot_info.total} slots used)"
        $scope.show_rrd = (event, name_list, start_time, end_time, title, job_mode, selected_job) ->
            dev_pks = ($scope.device_dict[name].pk for name in name_list).join(",")
            start_time = if start_time then start_time else 0
            end_time = if end_time then end_time else 0
            job_mode = if job_mode then job_mode else "none"
            selected_job = if selected_job then selected_job else "0"
            rrd_txt = """
<div class="panel panel-default">
    <div class="panel-body">
        <h2>#{title}</h2>
        <div ng-controller='rrd_ctrl'>
            <rrdgraph
                devicepk='#{dev_pks}'
                selectkeys="load.*,net.all.*,mem.used.phys$,^swap.*"
                draw="1"
                mergedevices="0"
                graphsize="240x100"
                fromdt="#{start_time}"
                todt="#{end_time}"
                jobmode="#{job_mode}"
                selectedjob="#{selected_job}"
            >
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
]).controller("lic_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", "$sce", "$resource", "d3_service", "dimple_service"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout, $sce, $resource, d3_service, dimple_service) -> 
        wait_list = restDataSource.add_sources([
            ["{% url 'rest:device_list' %}", {}],
            ["{% url 'rest:ext_license_list' %}", {}],
        ])
        $q.all(wait_list).then( (data) ->
            $scope.device_list = data[0]
            $scope.ext_license_list = data[1]
            
            # for testing:
            #$scope.ext_license_list[1].selected = true
            #$scope.license_select_change()

            $scope.update_lic_overview_data()
        )

        $scope.$watch('timerange', (unused) -> $scope.update_lic_overview_data())
        $scope.$watch('licdaterangestart', (unused) -> $scope.update_lic_overview_data())
        $scope.$watch('multi_view', (unused) -> $scope.update_lic_overview_data())
        
        $scope.view_mode = 'default'
        
        $scope.set_view_mode = (mode) ->
            if mode == $scope.view_mode
                $scope.view_mode = 'default'
            else
                $scope.view_mode = mode
        
        $scope.update_lic_overview_data = () ->
            if $scope.ext_license_list
                for lic in $scope.ext_license_list
                    if $scope.multi_view
                        lic.usage = ""
                    else
                        do (lic) ->
                            lic_utils.get_lic_data($resource, 'default', lic.idx, $scope.timerange, $scope.licdaterangestart, (new_data) ->
                                if new_data.length > 0
                                    lic.usage = "(" + lic_utils.calc_avg_usage(new_data) + "%)"
                                else
                                    lic.usage = ""
                            )
       
        $scope.dimpleloaded = false
        d3_service.d3().then( (d3) ->
            dimple_service.dimple().then( (dimple) ->
                $scope.dimpleloaded = true
            )
        )
        $scope.license_select_change = () ->
            $scope.ext_license_selected = []
            if $scope.ext_license_list
                for lic in $scope.ext_license_list
                    if lic.selected
                        $scope.ext_license_selected.push(lic)
        $scope.license_select_change()  # init by empty list 
        
        $scope.get_li_sel_class = (li) ->
            if li.selected
                return "btn btn-small btn-success"
            else
                return "btn btn-small"
        $scope.toggle_li_sel = (li) ->
            li.selected = !li.selected
            $scope.license_select_change()

        $scope.set_timerange = (tr) ->
            $scope.timerange = tr
        $scope.set_timerange("week")
        $scope.licdaterangestart = moment().startOf("day")
        $scope.multi_view = false
        $scope.cur_time = moment().format()
        # for testing:
        #$scope.licdaterangestart = moment("Wed Oct 15 2014 00:00:00 GMT+0200 (CEST)")
        #$scope.cur_time = "Wed Oct 15 2014 00:00:00 GMT+0200 (CEST)"

]).directive("licgraph", ["$templateCache", "$resource", ($templateCache, $resource) ->
    return {
        restrict : "EA"
        template : """
{% verbatim %}
<div ng-if="dimpleloaded">
    <div ng-if="!fixed_range">
        <h3>License: {{ lic_name }} {{ header_addition }}</h3>
    </div>
    <div ng-if="lic_data_show.length > 0">
        <graph data="lic_data_show" width="500" height="300">
            <x field="date" order-by="idx" title="null"></x>
            <y field="value" title="License usage"></y>
            <stacked-area field="type"/>
            <!--
            the data is meant differently than displayed in legend currently
            -->
            <legend></legend>
        </graph>
    </div>
    <div ng-if="lic_data.length == 0">
        no data available
    </div>
</div>
{% endverbatim %}
"""
        scope : {
            timerange: '='
            dimpleloaded: '='
            licdaterangestart: '='
            viewmode: '='
        }
        link : (scope, el, attrs) ->
            # can't reuse other attributes as they are shared with parent scope
            scope.fixed_range = attrs.fixedtimerange? && attrs.fixedlicdaterangestart?
            scope.lic_id = attrs.lic
            scope.lic_name = attrs.licname

            scope.set_lic_data = () ->
                # we get lic_data and lic_data_min_max by default
                if scope.viewmode == "show_min_max"
                    scope.lic_data_show = scope.lic_data_min_max
                else if scope.viewmode == "show_user"
                    scope.lic_data_show = []
                else if scope.viewmode == "show_device"
                    scope.lic_data_show = []
                else if scope.viewmode == "show_version"
                    if scope.lic_data_version
                        scope.lic_data_show = scope.lic_data_version
                    else
                        scope.update_lic_data(scope.viewmode)
                else
                    scope.lic_data_show = scope.lic_data
            scope.update_lic_data = (viewmode) ->
                # call with argument to allow obtaining general data when in view mode
                tr = if scope.fixed_range then attrs.fixedtimerange else scope.timerange
                start_date = if scope.fixed_range then attrs.fixedlicdaterangestart else scope.licdaterangestart
                
                # prepare data for dimple
                # only define continuation function per mode
                create_common = (entry) -> return {"idx": entry.idx, "date": entry.display_date, "full_date": entry.full_start_date}
                if viewmode == 'default'
                    cont = (new_data) ->
                        scope.lic_data = []
                        scope.lic_data_min_max = []
                        for entry in new_data
                            common = create_common(entry)

                            used = _.clone(common)
                            used["value"] = entry.used
                            used["type"] = "used"
                            used["order"] = 1

                            issued = _.clone(common)
                            issued["value"] = entry.issued - entry.used
                            issued["type"] = "unused"
                            issued["order"] = 2

                            scope.lic_data.push(used)
                            scope.lic_data.push(issued)

                            usedMin = _.clone(common)
                            usedMin["value"] = entry.used_min
                            usedMin["type"] = "min used"
                            usedMin["order"] = 1

                            usedAvg = _.clone(common)
                            usedAvg["value"] = entry.used - entry.used_min
                            usedAvg["type"] = "avg used"
                            usedAvg["order"] = 2

                            usedMax = _.clone(common)
                            usedMax["value"] = entry.used_max - entry.used
                            usedMax["type"] = "max used"
                            usedMax["order"] = 3

                            issuedMinMax = _.clone(common)
                            issuedMinMax["value"] = entry.issued_max - entry.used_max  # use issued_max as used_max can be greater than issued
                            issuedMinMax["type"] = "unused"
                            issuedMinMax["order"] = 4

                            scope.lic_data_min_max.push(usedMin)
                            scope.lic_data_min_max.push(usedAvg)
                            scope.lic_data_min_max.push(usedMax)
                            scope.lic_data_min_max.push(issuedMinMax)

                        if new_data.length > 0
                            scope.header_addition = "(" + lic_utils.calc_avg_usage(new_data) + "% usage)"
                else if viewmode == 'show_version'
                    cont = (new_data) ->
                        scope.lic_data_version = []
                        for entry in new_data
                            common = create_common(entry)

                            version = _.clone(common)
                            version["value"] = entry.frequency
                            version["type"] = "#{entry.ext_license_version_name} (#{entry.vendor_name})"
                            version["order"] = 0
                            scope.lic_data_version.push(version)
                lic_utils.get_lic_data($resource, viewmode, scope.lic_id, tr, start_date, (new_data) ->
                    #cont( _.sortBy(new_data, 'full_start_date') )
                    cont(new_data)
                    scope.set_lic_data()
                )

            if !scope.fixed_range
                # need to watch by string and not by var, probably because var originates from parent scope
                scope.$watch('timerange', (unused) -> scope.update_lic_data(scope.viewmode))
                scope.$watch('licdaterangestart', (unused) -> scope.update_lic_data(scope.viewmode))
            else
                # no updates for fixed range
                scope.update_lic_data(scope.viewmode)
            scope.$watch('viewmode', (unused) -> scope.set_lic_data())
}]).directive("running", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("running_table.html")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagRun.conf.filter = attrs["filter"]
    }
).directive("waiting", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("waiting_table.html")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagWait.conf.filter = attrs["filter"]
    }
).directive("done", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("done_table.html")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagDone.conf.filter = attrs["filter"]
    }
).directive("node", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("node_table.html")
        link : (scope, el, attrs) ->
            scope.get_class = (data) ->
                parts = data.state.raw.join("").split("")
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
).directive("rmsdoneline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsdoneline.html")
        link : (scope, el, attrs) ->
            scope.struct_name = attrs["struct"]
            scope.get_datetime = (dt) ->
                if dt
                    return moment.unix(dt).format(DT_FORM)
                else
                    return "---"
            scope.get_runtime = (data) ->
                if data.start_time and data.end_time
                    _et = moment.unix(data.end_time)
                    _st = moment.unix(data.start_time)
                    _diff = moment.duration(_et.diff(_st, "seconds"), "seconds")
                    return _diff.humanize()
                else
                    return "---"     
            scope.get_waittime = (data) ->
                if data.queue_time and data.start_time
                    _et = moment.unix(data.start_time)
                    _st = moment.unix(data.queue_time)
                    _diff = moment.duration(_et.diff(_st, "seconds"), "seconds")
                    return _diff.humanize()
                else
                    return "---"     
            scope.get_display_data = (data) ->
                return scope[scope.struct_name].display_data(data)
            scope.show_pe_info = (data) ->
                r_list = []
                if data.rms_pe_info.length
                    for _entry in data.rms_pe_info
                        r_list.push("#{_entry.hostname} (#{_entry.slots})")
                else
                    if data.device of scope.device_dict
                        r_list.push("#{scope.device_dict[data.device].full_name} (#{data.slots})")
                    else
                        r_list.push("---")
                return r_list.join(",")
            scope.has_rrd = (data) ->
                if data.rms_pe_info.length
                    any_rrd = false
                    for _entry in data.rms_pe_info
                        if _entry.device of scope.device_dict
                            if scope.device_dict[_entry.device].has_rrd
                                any_rrd = true
                    return any_rrd
                else
                    if data.device of scope.device_dict
                        return scope.device_dict[data.device].has_rrd
                    else
                        return false    
            scope.get_rrd_nodes = (nodelist) ->
                rrd_nodes = (scope.device_dict[entry].name for entry in nodelist when entry of scope.device_dict and scope.device_dict[entry].has_rrd)
                return rrd_nodes
            scope.show_done_rrd = (event, data) ->
                if data.rms_pe_info.length
                    nodelist = (entry.device for entry in data.rms_pe_info)
                else
                    nodelist = [data.device]
                rrd_nodes = scope.get_rrd_nodes(nodelist)
                job_id = data.rms_job.jobid
                if data.rms_job.taskid
                    job_id = "#{job_id}.#{data.rms_job.taskid}"
                if rrd_nodes.length > 1
                    rrd_title = "finished job #{job_id} on nodes " + rrd_nodes.join(",")
                else
                    rrd_title = "finished job #{job_id} on node " + rrd_nodes[0]
                scope.show_rrd(event, rrd_nodes, data.start_time, data.end_time, rrd_title, "selected", job_id)
            scope.exit_status_wrapper_class = (data) ->
                if data.exit_status of scope.exit_status_lut
                    _td_type = scope.exit_status_lut[data.exit_status][0]
                    if _td_type == 0
                        return "warn"
                    else if _td_type == 1
                        return "ok"
                    else
                        return "danger"     
                else
                    if data.exit_status > 128
                        return "danger"
                    else if data.exit_status
                        return "warn"
                    else
                        return "ok"
            scope.exit_status_class = (data) ->
                if data.exit_status of scope.exit_status_lut
                    _glyph = scope.exit_status_lut[data.exit_status][2]
                    if _glyph
                        return "glyphicon #{_glyph}"
                    else
                        return ""
                else
                    return ""        
            scope.get_exit_status_str = (data) ->
                if data.exit_status of scope.exit_status_lut
                    return scope.exit_status_lut[data.exit_status][1]
                else
                    return data.exit_status
            scope.get_failed_str = (data) ->
                if data.failed of scope.failed_lut
                    return scope.failed_lut[data.failed][1]
                else
                    return data.failed
            scope.get_failed_class = (data) ->
                if data.failed of scope.failed_lut
                    return if scope.failed_lut[data.failed][0] then "label-success" else "label-danger"
                else
                    return "label-warning"
            scope.get_failed_glyphicon = (data) ->
                if data.failed of scope.failed_lut
                    return if scope.failed_lut[data.failed][0] then "glyphicon glyphicon-ok" else "glyphicon glyphicon-remove"
                else
                    return "glyphicon glyphicon-minus"
            scope.get_failed_title = (data) ->
                if data.failed of scope.failed_lut
                    return scope.failed_lut[data.failed][2]
                else
                    return ""
    }
).directive("rmswaitline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmswaitline.html")
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
                nodes = job.nodelist.value.split(",")
                r_list = []
                _.forEach(_.countBy(nodes), (key, value) ->
                    if key == 1
                        r_list.push(value)
                    else
                        r_list.push("#{value}(#{key})")
                )
                return r_list.join(",")
            scope.get_rrd_nodes = (nodelist) ->
                rrd_nodes = (entry for entry in nodelist.devs when entry of scope.device_dict and scope.device_dict[entry].has_rrd)
                return rrd_nodes
            scope.has_rrd = (nodelist) ->
                rrd_nodes = scope.get_rrd_nodes(nodelist.raw)
                return if rrd_nodes.length then true else false
            scope.show_job_rrd = (event, job) ->
                rrd_nodes = scope.get_rrd_nodes(job.nodelist.raw)
                job_id = job.job_id.value
                if job.task_id.value
                    job_id = "#{job_id}.#{job.task_id.value}"
                if rrd_nodes.length > 1
                    rrd_title = "running job #{job_id} on nodes " + rrd_nodes.join(",")
                else
                    rrd_title = "running job #{job_id} on node " + rrd_nodes[0]
                scope.show_rrd(event, rrd_nodes, job.start_time.raw, undefined, rrd_title, "selected", job_id)
    }
).directive("rmsnodeline", ($templateCache, $sce, $compile) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsnodeline.html")
        link : (scope, el, attrs) ->
            scope.valid_load = (load) ->
                # return 1 or 0, not true or false
                return if load.value.match(LOAD_RE) then 1 else 0
            scope.get_load = (load) ->
                cur_m = load.value.match(LOAD_RE)
                if cur_m
                    return String((100 * parseFloat(load.value)) / scope.max_load)
                else
                    return 0
            scope.has_rrd = (name) ->
                if name.value of scope.device_dict
                    return scope.device_dict[name.value].has_rrd
                else
                    return false
            scope.show_node_rrd = (event, node) ->
                scope.show_rrd(event, [node.host.value], undefined, undefined, "node #{node.host.value}", "none", 0)
    }
).directive("headertoggle", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("header_toggle.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).directive("jobaction", ($compile, $templateCache, $modal) ->
    return {
        restrict : "EA"
        #template : $templateCache.get("queue_state.html")
        scope:
            job : "="
            operator : "="
            mode : "="
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
                scope.$watch("job", (job) ->
                    scope.job = job
                )
                cp_scope = ($scope, $modalInstance, job, oper) ->
                    $scope.job = job
                    $scope.cur_priority = parseInt($scope.job.priority.value)
                    $scope.get_max_priority = () ->
                        return if oper then 1024 else 0
                    $scope.get_job_id = () ->
                        _id = $scope.job.job_id.value
                        if $scope.job.task_id.value
                            _id = "#{_id}." + $scope.job.task_id.value
                        return _id
                    $scope.ok = () ->
                        _job_id = $scope.get_job_id()
                        $modalInstance.close([$scope.cur_priority, _job_id])
                    $scope.cancel = () ->
                        $modalInstance.dismiss("cancel")
                scope.change_priority = () ->
                    c_modal = $modal.open
                        template : $templateCache.get("change_pri.html")
                        controller : cp_scope
                        backdrop : "static"
                        resolve :
                            job : () =>
                                return scope.job
                            oper: () =>
                                return is_oper
                    c_modal.result.then(
                        (_tuple) ->
                            new_pri = _tuple[0]
                            job_id = _tuple[1]
                            call_ajax
                                url      : "{% url 'rms:change_job_priority' %}"
                                data:
                                    "job_id": job_id
                                    "new_pri" : new_pri
                                success  : (xml) =>
                                    if parse_xml_response(xml)
                                        scope.$apply(
                                            scope.job.priority.value = new_pri
                                        )
                    )
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
                    states = scope.host.state.value.split("/")
                    queues = scope.host.queues.value.split("/")
                    if queues.length != states.length
                        states = (states[0] for queue in queues)
                    return _.zipObject(queues, states)
                scope.queues_defined = () ->
                    return if scope.host.state.value.length then true else false
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
            full_id = if scope.job.task_id.value then "#{scope.job.job_id.value}.#{scope.job.task_id.value}" else scope.job.job_id.value
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
).controller("lic_liveview_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        $scope.servers = []
        $scope.licenses = []
        $scope.lic_overview = []
        $scope.server_open = false
        $scope.overview_open = true
        $scope.update = () ->
            call_ajax
                url      : "{% url 'lic:license_liveview' %}"
                dataType : "xml"
                success  : (xml) =>
                    if parse_xml_response(xml)
                        $scope.$apply(() ->
                            _open_list = (_license.name for _license in $scope.licenses when _license.open)
                            $scope.servers = (new license_server($(_entry)) for _entry in $(xml).find("license_info > license_servers > server"))
                            $scope.licenses = (new license($(_entry)) for _entry in $(xml).find("license_info > licenses > license"))
                            $scope.lic_overview = (new license_overview($(_entry)) for _entry in $(xml).find("license_overview > licenses > license"))
                            for _lic in $scope.licenses
                                if _lic.name in _open_list
                                    _lic.open = true
                            $scope.cur_timeout = $timeout($scope.update, 30000)
                        )
        $scope.update()
]).run(($templateCache) ->
    $templateCache.put("running_table.html", running_table)
    $templateCache.put("waiting_table.html", waiting_table)
    $templateCache.put("done_table.html", done_table)
    $templateCache.put("node_table.html", node_table)
    $templateCache.put("headers.html", headers)
    $templateCache.put("rmswaitline.html", rmswaitline)
    $templateCache.put("rmsdoneline.html", rmsdoneline)
    $templateCache.put("rmsrunline.html", rmsrunline)
    $templateCache.put("rmsnodeline.html", rmsnodeline)
    $templateCache.put("header_toggle.html", header_toggle)
    $templateCache.put("iostruct.html", iostruct)
    $templateCache.put("queue_state_oper.html", queuestateoper)
    $templateCache.put("queue_state.html", queuestate)
    $templateCache.put("job_action_oper.html", jobactionoper)
    $templateCache.put("job_action.html", jobaction)
    $templateCache.put("files_info.html", filesinfo)
    $templateCache.put("change_pri.html", change_pri_template)
)

class license_overview
    constructor : (@xml) ->
        for _sa in ["name", "attribute"]
            @[_sa] = @xml.attr(_sa)
        for _si in ["sge_used_issued", "external_used", "used",
                    "reserved", "in_use", "free", "limit", "sge_used_requested",
                    "total", "sge_used"]
            @[_si] = parseInt(@xml.attr(_si))
        @is_used = if parseInt(@xml.attr("in_use")) then true else false
        @show = if parseInt(@xml.attr("show")) then true else false
        
class license_server
    constructor : (@xml) ->
        @info = @xml.attr("info")
        @port = parseInt(@xml.attr("port"))
        @address = @xml.attr("address")

class license
    constructor : (@xml) ->
        @open = false
        @name = @xml.attr("name")
        @key = @name
        for _lc in ["used", "reserved", "free", "issued"]
            @[_lc] = parseInt(@xml.attr(_lc))
        @versions = (new license_version($(sub_xml), @) for sub_xml in @xml.find("version"))
        @all_usages = []
        for version in @versions
            for usage in version.usages
                @all_usages.push(usage)

class license_version
    constructor : (@xml, @license) ->
        @vendor = @xml.attr("vendor")
        @version = @xml.attr("version")
        @key = @license.key + "." + @version
        @usages = (new license_usage($(sub_xml), @) for sub_xml in @xml.find("usages > usage"))

class license_usage
    constructor: (@xml, @version) ->
        for _ta in ["client_long", "client_short", "user", "client_version"]
            @[_ta] = @xml.attr(_ta)
        @num = parseInt(@xml.attr("num"))
        @checkout_time = moment.unix(parseInt(@xml.attr("checkout_time")))
        @absolute_co = @checkout_time.format("dd, Do MM YYYY, hh:mm:ss")
        @relative_co = @checkout_time.fromNow()

 
        
# can't put this into the controller due to isolated scope
lic_utils = {
    get_lic_data: ($resource, viewmode, lic_id, timerange, start_date, cont) ->
        lic_resource = switch
            when viewmode == "show_version" then $resource("{% url 'rest:license_version_state_coarse_list' %}", {})
            else $resource("{% url 'rest:license_state_coarse_list' %}", {})
        query_data = {
            'lic_id': lic_id
            'duration_type' : timerange
            'date' : moment(start_date).unix()  # ask server in utc
        }
        lic_resource.query(query_data, (new_data) ->
            cont(new_data)
        )
    calc_avg_usage: (new_data) ->
        sum_used = 0
        sum_issued = 0
        for entry in new_data
            sum_used += entry.used
            sum_issued += entry.issued
        return Math.round( 100 * (sum_used / sum_issued) ) 
}

add_rrd_directive(rms_module)

{% endinlinecoffeescript %}

</script>
