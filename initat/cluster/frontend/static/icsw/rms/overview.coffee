# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
LOAD_RE = /(\d+.\d+).*/

class header_struct
    constructor: (@table, h_struct, @hidden_headers, @ICSW_URLS, @icswSimpleAjaxCall) ->
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
        @icswSimpleAjaxCall(
            url      : @ICSW_URLS.RMS_SET_USER_SETTING
            dataType : "json"
            data:
                "data" : angular.toJson({"table" : @table, "row" : entry, "enabled" : @toggle[entry]})
        ).then((json) ->
        )
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
        usercount = {}
        for usage in @all_usages
            if usage.user not of usercount
                usercount[usage.user] = 0
            usercount[usage.user] += usage.num
        for usage in @all_usages
            usage.user_usage = usercount[usage.user]
        @all_usages = _.sortBy(usage for usage in @all_usages, (entry) -> return entry.user)

class license_version
    constructor : (@xml, @license) ->
        @vendor = @xml.attr("vendor")
        @version = @xml.attr("version")
        @key = @license.key + "." + @version
        @usages = _.sortBy(new license_usage($(sub_xml), @) for sub_xml in @xml.find("usages > usage"), (entry) -> return entry.user)

class license_usage
    constructor: (@xml, @version) ->
        for _ta in ["client_long", "client_short", "user", "client_version"]
            @[_ta] = @xml.attr(_ta)
        @num = parseInt(@xml.attr("num"))
        @checkout_time = moment.unix(parseInt(@xml.attr("checkout_time")))
        @absolute_co = @checkout_time.format("dd, Do MM YYYY, hh:mm:ss")
        @relative_co = @checkout_time.fromNow()

class Queue
    constructor: (@name) ->

DT_FORM = "D. MMM YYYY, HH:mm:ss"

rms_module = angular.module(
    "icsw.rms",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.codemirror", "ui.bootstrap.datetimepicker", "angular-ladda"
    ]
).value('ui.config', {
    codemirror : {
        mode : 'text/x-php'
        lineNumbers: true
        matchBrackets: true
    }
}).controller("icswRmsOverviewCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "icswAcessLevelService", "$timeout", "$sce", "ICSW_URLS", "icswSimpleAjaxCall", "$window"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, icswAcessLevelService, $timeout, $sce, ICSW_URLS, icswSimpleAjaxCall, $window) ->
        icswAcessLevelService.install($scope)
        $scope.rms_headers = angular.fromJson($templateCache.get("icsw.rms.rms_headers"))
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
        $scope.queue_list = []
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
        $scope.running_struct = new header_struct("running", $scope.rms_headers.running_headers, [], ICSW_URLS, icswSimpleAjaxCall)
        $scope.waiting_struct = new header_struct("waiting", $scope.rms_headers.waiting_headers, [], ICSW_URLS, icswSimpleAjaxCall)
        $scope.done_struct = new header_struct("done", $scope.rms_headers.done_headers, [], ICSW_URLS, icswSimpleAjaxCall)
        $scope.node_struct = new header_struct("node", $scope.rms_headers.node_headers, ["state"], ICSW_URLS, icswSimpleAjaxCall)
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
        $scope.set_filter_values = (job) ->
            if job.granted_pe?
                job.sv0 = job.granted_pe.value
            if job.name?
                job.sv1 = job.name.value
            if job.owner?
                job.sv2 = job.owner.value
            if job.queue_name?
                job.sv3 = job.queue_name.value
            if job.real_user?
                job.sv4 = job.real_user.value
        $scope.reload = () ->
            $scope.rms_operator = $scope.acl_modify(null, "backbone.user.rms_operator")
            if $scope.update_info_timeout
                $timeout.cancel($scope.update_info_timeout)
            # refresh every 10 seconds
            $scope.update_info_timeout = $timeout($scope.reload, 10000)
            if $scope.refresh
                icswSimpleAjaxCall(
                    url      : ICSW_URLS.RMS_GET_RMS_JSON
                    dataType : "json"
                ).then(
                    (json) ->
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
                        # build queue list
                        $scope.queue_list = []
                        for entry in $scope.node_list
                            i_split = (in_str) ->
                                parts = in_str.split("/")
                                if parts.length != _nq
                                    parts = (parts[0] for _x in [1.._nq])
                                return parts
                            queues = entry.queues.value.split("/")
                            _nq = queues.length
                            states = i_split(entry.state.value)
                            loads = i_split(entry.load.value)
                            types = i_split(entry.type.value)
                            complexes = i_split(entry.complex.value)
                            pe_lists = i_split(entry.pe_list.value)
                            _idx = 0
                            for _vals in _.zip(
                                queues, states, loads, types, complexes, pe_lists,
                                i_split(entry.slots_used.value),
                                i_split(entry.slots_reserved.value),
                                i_split(entry.slots_total.value),
                                i_split(entry.jobs.value),
                            )
                                queue = new Queue(_vals[0])
                                queue.host = entry
                                queue.state = {"value": _vals[1], "raw": entry.state.raw[_idx]}
                                queue.load = {"value": _vals[2]}
                                queue.type = {"value": _vals[3]}
                                queue.complex = {"value": _vals[4]}
                                queue.pe_list = {"value": _vals[5]}
                                queue.slots_used = {"value": _vals[6]}
                                queue.slots_reserved = {"value": _vals[7]}
                                queue.slots_total = {"value": _vals[8]}
                                # job display still buggy, FIXME
                                queue.jobs = {"value": _vals[9]}
                                $scope.queue_list.push(queue)
                                _idx++
                        for entry in $scope.node_list
                            # for filter function
                            entry.sv0 = entry.host.value
                            entry.sv1 = entry.queues.value
                            entry.sv2 = entry.state.value
                            entry.sv3 = entry.pe_list.value
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
                            $scope.set_filter_values(_job)
                            if _job.granted_pe.value == "-"
                                $scope.running_slots += 1
                            else
                                $scope.running_slots += parseInt(_job.granted_pe.value.split("(")[1].split(")")[0])
                        for _job in $scope.wait_list
                            $scope.set_filter_values(_job)
                            if _job.requested_pe.value == "-"
                                $scope.waiting_slots += 1
                            else
                                $scope.waiting_slots += parseInt(_job.requested_pe.value.split("(")[1].split(")")[0])
                        if not $scope.device_dict_set
                            node_names = (entry[0].value for entry in json.node_table)
                            $scope.device_dict_set = true
                            icswSimpleAjaxCall(
                                url      : ICSW_URLS.RMS_GET_NODE_INFO
                                data     :
                                    devnames : angular.toJson(node_names)
                                dataType : "json"
                            ).then((json) ->
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
                            is_ie_below_eleven = /MSIE/.test($window.navigator.userAgent)
                            icswSimpleAjaxCall(
                                url     : ICSW_URLS.RMS_GET_FILE_CONTENT
                                data    :
                                    file_ids: angular.toJson(fetch_list)
                                    is_ie: if is_ie_below_eleven then 1 else 0
                            ).then(
                                (xml) ->
                                    xml = $(xml)
                                    for _id in $scope.io_list
                                        $scope.io_dict[_id].feed(xml)
                                    $scope.$digest()
                            )
            )
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
        $scope.$on("queue_control", (event, queue, command) ->
            icswSimpleAjaxCall(
                url      : ICSW_URLS.RMS_CONTROL_QUEUE
                data     : {
                    "queue"   : queue.name
                    "host"    : queue.host.host.value
                    "command" : command 
                }
            ).then((xml) ->
            )
        )
        $scope.$on("job_control", (event, job, command, force) ->
            icswSimpleAjaxCall(
                url      : ICSW_URLS.RMS_CONTROL_JOB
                data     : {
                    "job_id"  : job.job_id.value
                    "task_id" : job.task_id.value
                    "command" : command 
                }
            ).then((xml) ->
            )
        )
        $scope.get_running_info = () ->
            return "running (#{$scope.run_list.length} jobs, #{$scope.running_slots} slots)"
        $scope.get_waiting_info = () ->
            return "waiting (#{$scope.wait_list.length} jobs, #{$scope.waiting_slots} slots)"
        $scope.get_done_info = () ->
            return "done (#{$scope.done_list.length} jobs)"
        $scope.get_queue_info = () ->
            return "queue (#{$scope.queue_list.length} queues on #{$scope.node_list.length} nodes, #{$scope.slot_info.used} of #{$scope.slot_info.total} slots used)"
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
        <icsw-rrd-graph
            icsw-sel-man="0"
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
        </icsw-rrd-graph>
    </div>
</div>
"""
            # disable refreshing
            $scope.refresh = false
            $scope.rrd_div = angular.element(rrd_txt)
            $compile($scope.rrd_div)($scope)
            $scope.my_modal = BootstrapDialog.show
                message: $scope.rrd_div
                draggable: true
                size: BootstrapDialog.SIZE_WIDE
                title: "device RRDs"
                closable: true
                closeByBackdrop: false
                cssClass: "modal-tall"
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
                onhidden: () ->
                    $scope.refresh = true
            #$scope.rrd_div.simplemodal
            #    opacity      : 50
            #    position     : [event.pageY, event.pageX]
            #    autoResize   : true
            #    autoPosition : true
            #    minWidth     : "1280px"
            #    minHeight   : "800px"
            #    onShow: (dialog) ->
            #        dialog.container.draggable()
            #        #$("#simplemodal-container").css("height", "auto")
            #        #$("#simplemodal-container").css("width", "auto")
            #    onClose: =>
            #        # destroy scopes
            #        $scope.refresh = true
            #        $.simplemodal.close()
        icswSimpleAjaxCall(
            url      : ICSW_URLS.RMS_GET_USER_SETTING
            dataType : "json"
        ).then((json) ->
            for key, value of json
                $scope.structs[key].set_disabled(value)
            $scope.header_filter_set = true
            $scope.reload()
        )
]).directive("icswRmsJobRunningTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.running.table")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagRun.conf.filter = attrs["filter"]
    }
]).directive("icswRmsJobWaitingTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.waiting.table")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagWait.conf.filter = attrs["filter"]
    }
]).directive("icswRmsJobDoneTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.done.table")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagDone.conf.filter = attrs["filter"]
    }
]).directive("icswRmsQueueTable", ["$templateCache",($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.queue.table")
        link : (scope, el, attrs) ->
            scope.get_class = (data) ->
                parts = data.state.raw  # .join("").split("")
                if _.indexOf(parts, "a") >= 0 or _.indexOf(parts, "u") >= 0
                    return "danger"
                else if _.indexOf(parts, "d") >= 0
                    return "warning"
                else
                    return ""
    }
]).directive("icswRmsIoStruct", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.iostruct")
        link : (scope, el, attrs) ->
    }
]).directive("icswRmsTableHeaders", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.table.headers")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
]).directive("icswRmsJobDoneLine", ["$templateCache", "$sce", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.done.line")
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
]).directive("icswRmsJobWaitLine", ["$templateCache", "$sce", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.wait.line")
        link : (scope, el, attrs) ->
            scope.struct_name = attrs["struct"]
            scope.get_display_data = (data) ->
                return scope[scope.struct_name].display_data(data)
    }
]).directive("icswRmsJobVarInfo", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.job.var.info")
        scope:
            job: "=job"
        link : (scope, el, attrs) ->
            scope.popover =
                title: "Jobvars vor Job " + scope.job.rms_job.jobid
                template: "icsw.rms.job.var.info.template"
            _len = parseInt((scope.job.rmsjobvariable_set.length + 1) / 2)
            _vars = scope.job.rmsjobvariable_set
            _new_vars = []
            for _idx in [0.._len - 1]
                _new_vars.push(
                  [
                      _vars[_idx],
                      _vars[_idx + _len]
                  ]
                )
            scope.new_vars = _new_vars
    }
]).directive("icswRmsJobRunLine", ["$templateCache", "$sce", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.run.line")
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
]).directive("icswRmsQueueLine", ["$templateCache", "$sce", "$compile", ($templateCache, $sce, $compile) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.queue.line")
        link : (scope, el, attrs) ->
            scope.valid_load = (load) ->
                # return 1 or 0, not true or false
                if load.value
                    return if load.value.match(LOAD_RE) then 1 else 0
                else
                    return false
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
]).directive("icswRmsTableHeaderToggle", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.table.header.toggle")
        scope:
            struct : "="
    }
]).directive("icswRmsJobAction", ["$compile", "$templateCache", "$modal", "icswUserService", "ICSW_URLS", "icswSimpleAjaxCall", ($compile, $templateCache, $modal, icswUserService, ICSW_URLS, icswSimpleAjaxCall) ->
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

                is_oper = false
                scope.$watch("job", (job) ->
                    scope.job = job
                )

                scope.change_priority = () ->
                    child_scope = scope.$new()
                    child_scope.cur_priority = parseInt(scope.job.priority.value)
                    child_scope.get_job_id = () ->
                        _id = scope.job.job_id.value
                        if scope.job.task_id.value
                            _id = "#{_id}." + scope.job.task_id.value
                        return _id
                    child_scope.get_max_priority = () ->
                        return if is_oper then 1024 else 0
                    msg = $compile($templateCache.get("icsw.rms.change.priority"))(child_scope)

                    on_ok = (new_pri, job_id) ->
                        icswSimpleAjaxCall(
                            url      : ICSW_URLS.RMS_CHANGE_JOB_PRIORITY
                            data:
                                "job_id": job_id
                                "new_pri" : new_pri
                        ).then((xml) ->
                            scope.job.priority.value = new_pri
                        )
                    child_scope.modal = BootstrapDialog.show
                        title: "Change priority of job #{child_scope.get_job_id()}"
                        message: msg
                        draggable: true
                        closable: true
                        closeByBackdrop: false
                        onshow: (modal) =>
                            height = $(window).height() - 100
                            modal.getModal().find(".modal-body").css("max-height", height)

                    child_scope.ok = () ->
                        on_ok(child_scope.cur_priority, child_scope.get_job_id())
                        child_scope.modal.close()

                    child_scope.cancel = () ->
                        child_scope.modal.close()

                icswUserService.load().then((user) ->
                    if scope.operator
                        is_oper = true
                    else if scope.job.real_user == user.login
                        is_oper = true
                    else
                        is_oper = false
                    el.append($compile($templateCache.get(if is_oper then "icsw.rms.job.action.oper" else "icsw.rms.job.action"))(scope))
                )
    }
]).directive("icswRmsQueueState", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        #template : $templateCache.get("queue_state.html")
        scope:
            queue : "="
            operator : "="
        replace : true
        compile : (tElement, tAttr) ->
            return (scope, el, attrs) ->
                scope.queues_defined = () ->
                    return true
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
                    scope.$emit("queue_control", queue, command)
                el.append($compile($templateCache.get(if scope.operator then "icsw.rms.queue.state.oper" else "icsw.rms.queue.state"))(scope))
      
    }
]).directive("icswRmsFileInfo", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        scope:
            job   : "="
            files : "="
            fis   : "="
        template : $templateCache.get("icsw.rms.file.info")
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
            scope.change_display = (file_name) ->
                scope.fis[file_name].show = !scope.fis[file_name].show
    }
]).controller("icswRmsLicenseLiveviewCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$modal", "icswAcessLevelService", "$timeout", "ICSW_URLS", "icswSimpleAjaxCall",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $modal, icswAcessLevelService, $timeout, ICSW_URLS, icswSimpleAjaxCall) ->
        $scope.servers = []
        $scope.licenses = []
        $scope.lic_overview = []
        $scope.server_open = false
        $scope.overview_open = true
        $scope.update = () ->
            icswSimpleAjaxCall(
                url      : ICSW_URLS.LIC_LICENSE_LIVEVIEW
                dataType : "xml"
            ).then((xml) ->
                _open_list = (_license.name for _license in $scope.licenses when _license.open)
                $scope.servers = (new license_server($(_entry)) for _entry in $(xml).find("license_info > license_servers > server"))
                $scope.licenses = (new license($(_entry)) for _entry in $(xml).find("license_info > licenses > license"))
                $scope.lic_overview = (new license_overview($(_entry)) for _entry in $(xml).find("license_overview > licenses > license"))
                for _lic in $scope.licenses
                    if _lic.name in _open_list
                        _lic.open = true
                for _ov in $scope.lic_overview
                    $scope.build_stack(_ov)
                $scope.cur_timeout = $timeout($scope.update, 30000)
            )
        $scope.build_stack = (lic) ->
            total = lic.total
            stack = []
            if lic.used
                if lic.sge_used
                    stack.push(
                        {
                            "value": parseInt(lic.sge_used * 1000 / total)
                            "type": "primary"
                            "out": "#{lic.sge_used}"
                            "title": "#{lic.sge_used} used on cluster"
                        }
                    )
                if lic.external_used
                    stack.push(
                        {
                            "value": parseInt(lic.external_used * 1000 / total)
                            "type": "warning"
                            "out": "#{lic.external_used}"
                            "title": "#{lic.external_used} used external"
                        }
                    )
            if lic.free
                stack.push(
                    {
                        "value": parseInt(lic.free * 1000 / total)
                        "type": "success"
                        "out": "#{lic.free}"
                        "title": "#{lic.free} free"
                    }
                )
            lic.license_stack = stack
        $scope.update()
]).directive("icswRmsLicenseGraph", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        scope: true
        template : $templateCache.get("icsw.rms.license.graph")
        link : (scope, el, attrs) ->
            scope.$watch(attrs["license"], (new_val) ->
                scope.lic = new_val
            )
    }
])
