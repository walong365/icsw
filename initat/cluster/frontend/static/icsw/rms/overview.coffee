# Copyright (C) 2012-2016 init.at
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

rms_module = angular.module(
    "icsw.rms",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.bootstrap.datetimepicker", "angular-ladda"
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.rmsoverview", {
            url: "/rmsoverview"
            templateUrl: "icsw/main/rms/overview.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "RMS Overview"
                licenses: ["rms"]
                service_types: ["rms-server"]
                rights: ["user.rms_show"]
                menuHeader:
                    key: "rms"
                    name: "RMS"
                    icon: "fa-list-ol"
                    ordering: 90
                menuEntry:
                    menukey: "rms"
                    name: "RMS Overview"
                    icon: "fa-table"
                    ordering: 0
                dashboardEntry:
                    size_x: 4
                    size_y: 6
        }
    )
]).directive("icswRmsOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.overview")
        controller: "icswRMSOverviewCtrl"
        link: (scope, element, attrs) ->
            if attrs.icswRmsTitle?
                scope.struct.header_line = attrs.icswRmsTitle
            if attrs.icswRmsRunningSearch?
                scope.struct.search.running = attrs.icswRmsRunningSearch
            if attrs.icswRmsWaitingSearch?
                scope.struct.search.waiting = attrs.icswRmsWaitingSearch
            if attrs.icswRmsDoneSearch?
                scope.struct.search.done = attrs.icswRmsDoneSearch
    }
]).service("icswRMSTools",
[
    "$q",
(
    $q,
) ->
    failed_lut = {
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

    exit_status_lut = {
        0 : [1, "ok", ""]
        137 : [-1, "killed", "glyphicon-remove-circle"]
        99 : [0, "rescheduled", "glyphicon-repeat"]
    }

    return {
        failed_lut: failed_lut
        exit_status_lut: exit_status_lut
        load_re: /(\d+.\d+).*/
    }

]).service("icswRMSJobVarStruct",
[
    "$q", "icswRMSTools", "icswRMSJobVariable",
(
    $q, icswRMSTools, icswRMSJobVariable,
) ->
    class icswRMSJobVarStruct
        constructor: () ->
            @job_list = []
            @var_list = []
            @reset()
        
        reset: () =>
            @job_list.length = 0
            @build_luts()
            
        build_luts: () =>
            @job_lut = _.keyBy(@job_list, "$$full_job_id")
            if @job_list.length
                @show = true
                if @job_list.length == 1
                    @info = "JobVars for #{@job_list.length} job"
                else
                    @info = "JobVars for #{@job_list.length} jobs"
            else
                @show = false
                @info = "---"
            @build_table(@job_list)

        toggle: (job) =>
            if job.$$full_job_id of @job_lut
                @remove(job)
            else
                @add(job)

        remove: (job) =>
            id = job.$$full_job_id
            _.remove(@job_list, (entry) -> return entry.$$full_job_id == id)
            job.$$jv_shown = false
            job.$$jv_button_class = "btn btn-xs"
            @build_luts()
            
        add: (job) =>
            id = job.$$full_job_id
            if id not of @job_lut
                job.$$jv_shown = true
                job.$$jv_button_class = "btn btn-xs btn-success"
                @job_list.push(job)
                @build_luts()

        feed_start: () ->
            # start feeding of data from server
            @feed_list = []

        feed_job: (job) ->
            @feed_list.push(job)

        feed_end: () ->
            # console.log "f", @feed_list
            @build_table(@feed_list)

        build_table: (in_list) ->
            @num_jobs = in_list.length
            @used_list = in_list
            _names = []
            for job in in_list
                job.$$jv_lut = _.keyBy(job.rmsjobvariable_set, "name")
                for _loc_name in (jv.name for jv in job.rmsjobvariable_set)
                    if _loc_name not in _names
                        _names.push(_loc_name)
            _names.sort()
            @var_list.length = 0
            for _name in _names
                jvar = new icswRMSJobVariable(_name)
                for job in in_list
                    if _name of job.$$jv_lut
                        jvar.feed_var(job, job.$$jv_lut[_name])
                    else
                        jvar.feed_dummy(job)
                @var_list.push(jvar)
            @num_vars = @var_list.length
                
]).service("icswRMSJobVariable",
[
    "$q",
(
    $q,
) ->
    class icswRMSJobVariable
        constructor: (@name) ->
            @values = []
        
        feed_var: (job, jvar) =>
            ivalue = parseInt(jvar.value) || ""
            _cls = if @values.length % 2 then "success" else ""
            @values.push(
                {
                    present: true
                    lcls: "text-left #{_cls}"
                    rcls: "text-right #{_cls}"
                    value: jvar.value
                    int_value: ivalue
                    unit: jvar.unit
                }
            )
        feed_dummy: (job) ->
            _cls = "warning"
            @values.push(
                {
                    present: false
                    lcls: "text-left #{_cls}"
                    rcls: "text-right #{_cls}"
                }
            )
        
]).service("icswRMSIOStruct",
[
    "$q", "icswRMSTools",
(
    $q, icswRMSTools,
) ->
    class icswRMSIOStruct
        constructor: (@full_job_id, @type) ->
            @id = "#{@full_job_id}.#{@type}"
            @text = ""
            # is set to true as soon as we got any data
            @valid = false
            @waiting = true
            @refresh = 0
            @update = true
            @follow_tail = false
            @editor = undefined
            @ace_options = {
                uswWrapMode: false
                showGutter: true
                readOnly: true
                mode: "python"
                onChange: @editor_changed
                onLoad: @editor_loaded
            }

        editor_loaded: (editor) =>
            # console.log "editor=", editor
            @editor = editor
            @editor.setReadOnly(true)

        editor_changed: () =>
            # console.log "EC", @follow_tail, @editor
            # console.log @editor.session.getLength(), @editor.getSession().getDocument().getLength();
            # if @follow_tail
            #     @editor.navigateFileEnd()

        toggle_follow_tail: () =>
            @follow_tail = !@follow_tail
            if @editor and @follow_tail
                @editor.navigateFileEnd()

        get_file_info: () ->
            if @valid
                return "File #{@file_name} (#{@file_size} in #{@file_lines} lines)"
            else if @waiting
                return "waiting for data"
            else
                return "nothing found"

        file_read_error: (xml) =>
            @waiting = false
            @update = false
    
        feed: (xml) =>
            @waiting = false
            found_xml = $(xml).find("response file_info[id='#{@id}']")
            if found_xml.length
                @valid = true
                # set attributes
                @file_name = found_xml.attr("name")
                @file_lines = found_xml.attr("lines")
                @file_size = found_xml.attr("size_str")
                _new_text = found_xml.text()
                if @text != _new_text
                    @text = _new_text
                    @refresh++
                if @editor and @follow_tail
                    @editor.navigateFileEnd()
            else
                @update = false
                @refresh++
              
]).service("icswRMSQueue",
[
    "$q", "icswRMSTools",
(
    $q, icswRMSTools,
) ->
    class icswRMSQueue
        constructor: (@name, @host, state_value, seqno, host_state, load_value, max_load, slot_info, topology) ->
            @state = {
                value: state_value
                raw: host_state
            }
            slot_info = (parseInt(_value) for _value in slot_info)
            @seqno = {value: seqno}
            @load = {value: load_value}
            @slots_info = {
                used: slot_info[0]
                reserved: slot_info[1]
                total: slot_info[2]
            }
            if topology.value.length
                _use = topology.value
                _raw = angular.fromJson(topology.raw)
                # console.log _raw
            else
                _use = "-"
                _raw = null
            @topology_info = _use
            @topology_raw = _raw
            # if @topology.
            _sv = @state.value
            # display flags
            @$$enable_ok = if _sv.match(/d/g) then true else false
            @$$disable_ok = if not _sv.match(/d/g) then true else false
            @$$clear_error_ok = if _sv.match(/e/g) then true else false
            # full queue name
            @$$queue_name = "#{@name}@#{@host.host.value}"
            if _sv.match(/a|u/gi)
                _cls = "danger"
            else if _sv.match(/d/gi)
                _cls = "warning"
            else
                _cls = "success"
            @$$queue_btn_class = "btn-#{_cls}"
            @$$queue_label_class = "label-#{_cls}"

            if @load.value.match(icswRMSTools.load_re)
                @$$load_is_valid = true
                @$$load_percentage = String((100 * parseFloat(@load.value)) / max_load)
            else
                @$$load_is_valid = false
                @$$load_percentage = 0

            if _.indexOf(@state.raw, "a") >= 0 or _.indexOf(@state.raw, "u") >= 0
                @$$tr_class = "danger"
            else if _.indexOf(@state.raw, "d") >= 0
                @$$tr_class = "warning"
            else
                @$$tr_class = ""

]).service("icswRMSSlotInfo",
[
    "$q",
(
    $q,
) ->
    class icswRMSSlotInfo
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

]).service("icswRMSHeaderStruct",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswRMSTools",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswRMSTools,
) ->
    class icswRMSHeaderStruct
        constructor: (@name, h_struct, @struct) ->
            _dict = {}
            @headers = []
            @hidden_headers = []
            @attributes = {}
            for entry in h_struct
                @headers.push(entry[0])
                @attributes[entry[0]] = entry[1]
                _dict[entry[0]] = true
            @toggle = _dict

            # initial info string
            @info = "waiting"

            # list of entries
            @list = []

            @build_cache()

        set_user_disabled : (in_list) =>
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
            _str = (key for key, value of @toggle when not value).join(",")
            # console.log @toggle, _str
            _var_name = "_rms_wf_#{@name}"
            @struct.icsw_user.set_string_var(_var_name, _str).then(
                (ok) ->
                    # done
            )
            @build_cache()

        display_headers : () =>
            return (
                v[0] for v in _.zip.apply(
                    null
                    [@headers, @togglec]
                ) when v[1][0] and v[0] not in @hidden_headers
            )

        add_headers : (data) =>
            # get display list
            return (
                [v[1][1], v[0]] for v in _.zip.apply(
                    null
                    [data, @togglec]
                )
            )

        display_data : (data) =>
            # get display list
            return (
                v[0] for v in _.zip.apply(
                    null
                    [data, @togglec]
                ) when v[1][0]
            )

        get_btn_class : (entry) ->
            if @toggle[entry]
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm"

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

        salt_datetimes: () =>
            DT_FORM = "D. MMM YYYY, HH:mm:ss"

            for entry in @list
                for _name in ["queue_time", "start_time", "end_time"]
                    if entry[_name]?
                        entry["$$#{_name}"] = moment(entry[_name]).format(DT_FORM)
                    else
                        entry["$$#{_name}"] = "---"
                if @name == "done"
                    if entry.start_time? and entry.end_time?
                        _et = moment(entry.end_time)
                        _st = moment(entry.start_time)
                        _diff = moment.duration(_et.diff(_st, "seconds"), "seconds")
                        entry.$$runtime = _diff.humanize()
                    else
                        entry.$$runtime = "---"
                    if entry.queue_time? and entry.start_time?
                        _et = moment(entry.start_time)
                        _st = moment(entry.queue_time)
                        _diff = moment.duration(_et.diff(_st, "seconds"), "seconds")
                        entry.$$waittime = _diff.humanize()
                    else
                        entry.$$waittime = "---"

        feed_xml_list: (simple_list) =>
            # source is XML (running, waiting, node)
            @list.length = 0
            for entry in (_.zipObject(@headers, _line) for _line in simple_list)
                # console.log entry
                @list.push(entry)

        feed_json_list: (simple_list) =>
            # source is json (done)
            # the done-list is already in the correct format
            @list.length = 0
            for entry in simple_list
                # console.log entry
                @list.push(entry)

        set_rrd_flags: () =>
            {name_lut} = @struct
            for entry in @list
                # if entry.rms_pe?
                #     console.log "*", entry
                _names = []
                if entry.rms_pe_info? and entry.rms_pe_info.length
                    # hm, this is not correct ...
                    # done list
                    _names = entry.rms_pe_info
                else if entry.nodelist? and entry.nodelist.raw? and entry.nodelist.raw.devs?
                    # running list
                    _names = entry.nodelist.raw.devs
                else if entry.host?
                    # device name via host
                    _names = [entry.host.value]

                _rrds = false
                for _name in _names
                    if _name of name_lut and name_lut[_name].has_active_rrds
                        _rrds = true
                    if _rrds
                        entry.$$rrd_device_ids = (name_lut[_name].idx for _name in _names when _name of name_lut)
                        # console.log entry.$$rrd_device_ids
                entry.$$has_rrd = _rrds

        set_alter_job_flags: () ->
            {user, rms_operator} = @struct
            for entry in @list
                _alter = rms_operator
                if entry.owner.value == user.login
                    # check for aliases, FIXME
                    _alter = true
                entry.$$alter_job = _alter

        set_full_ids: () ->
            for entry in @list
                if entry.rms_job
                    # for done list
                    full_id = if entry.rms_job.taskid then "#{entry.rms_job.jobid}.#{entry.rms_job.taskid}" else entry.rms_job.jobid
                else
                    # for running, waiting, node
                    full_id = if entry.task_id.value then "#{entry.job_id.value}.#{entry.task_id.value}" else entry.job_id.value
                entry.$$full_job_id = String(full_id)
                # job lookup table
                entry.jobs = {}
        
        check_jobvar_display: () ->
            {jv_struct} = @struct
            for entry in @list
                if entry.rmsjobvariable_set?
                    _num_jv = entry.rmsjobvariable_set.length
                else
                    _num_jv = 0
                entry.$$jv_info = "#{_num_jv} Vars"
                if _num_jv
                    entry.$$jv_present = true
                    if entry.$$full_job_id of jv_struct.job_lut
                        jv_struct.feed_job(entry)
                        entry.$$jv_shown = true
                        entry.$$jv_button_class = "btn btn-xs btn-success"
                    else
                        entry.$$jv_shown = false
                        entry.$$jv_button_class = "btn btn-xs"
                else
                    entry.$$jv_present = false

]).service("icswRMSRunningStruct",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswRMSTools",
    "icswRMSHeaderStruct",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswRMSTools,
    icswRMSHeaderStruct,
) ->
    class icswRMSRunningStruct extends icswRMSHeaderStruct
        constructor: (h_struct, struct) ->
            super("running", h_struct, struct)
            # to save settings after reloads
            @file_info_dict = {}

        feed_list : (simple_list, file_dict) =>
            {io_dict} = @struct
            @feed_xml_list(simple_list)
            @set_rrd_flags()
            @set_alter_job_flags()
            @set_full_ids()
            @check_jobvar_display()
            _running_slots = 0
            for entry in @list
                nodes = entry.nodelist.value.split(",")
                r_list = []
                _.forEach(_.countBy(nodes), (key, value) ->
                    if key == 1
                        r_list.push(value)
                    else
                        r_list.push("#{value}(#{key})")
                )
                entry.$$nodelist = r_list.join(",")
                # check files
                if entry.$$full_job_id of file_dict
                    entry.files = file_dict[entry.$$full_job_id]
                    for file in entry.files
                        if file[0] not of @file_info_dict
                            @file_info_dict[file[0]] = {
                                show: true
                            }
                    entry.file_info_dict = @file_info_dict
                else
                    entry.files = []
                # check stdout / stderr state
                for _io_name in ["stdout", "stderr"]
                    _f_name = "$$#{_io_name}_valid"
                    _fc_name = "$$#{_io_name}_class"
                    _io_id = "#{entry.$$full_job_id}.#{_io_name}"
                    if entry[_io_name].value in ["---", "err", "error", "0 B"]
                        entry[_f_name] = false
                        entry[_fc_name] = "btn btn-xs btn-danger"
                    else
                        entry[_f_name] = true
                        if _io_id of io_dict
                            entry[_fc_name] = "btn btn-xs btn-success"
                        else
                            entry[_fc_name] = "btn btn-xs"
                if entry.granted_pe.value == "-"
                    _running_slots++
                else
                    _running_slots += parseInt(entry.granted_pe.value.split("(")[1].split(")")[0])
            if @list.length
                @info = "running (#{@list.length} jobs, #{_running_slots} slots)"
            else
                @info = "no running"

]).service("icswRMSWaitingStruct",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswRMSTools",
    "icswRMSHeaderStruct", "$templateCache", "$compile", "$rootScope", "$timeout",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswRMSTools,
    icswRMSHeaderStruct, $templateCache, $compile, $rootScope, $timeout,
) ->
    class icswRMSWaitingStruct extends icswRMSHeaderStruct
        constructor: (h_struct, struct) ->
            super("waiting", h_struct, struct)

        feed_list: (simple_list) =>
            # get list of currently open popovers
            if @list?
                _open_pops = (entry.job_id.value for entry in @list when entry.queue_details.$$open)
            else
                _open_pops = []
            @feed_xml_list(simple_list)
            @set_alter_job_flags()
            @set_full_ids()
            _waiting_slots = 0
            for entry in @list
                if entry.requested_pe.value == "-"
                    _waiting_slots++
                else
                    _waiting_slots += parseInt(entry.requested_pe.value.split("(")[1].split(")")[0])
                sub_scope = $rootScope.$new(true)
                sub_scope.j = entry
                sub_scope.d = entry.queue_details.raw
                sub_scope.s = @struct.rms.sched
                @calc_details(sub_scope)
                entry.queue_details.$$compiled = $compile($templateCache.get("icsw.rms.detail.popover"))(sub_scope)
                entry.queue_details.$$sub_scope = sub_scope
            if @list.length
                @calc_details_global()
                $timeout(
                    () =>
                        for entry in @list
                            # console.log entry.queue_details.raw
                            entry.queue_details.popover = (_line.outerHTML for _line in entry.queue_details.$$compiled).join(" ")
                            entry.queue_details.$$sub_scope.$destroy()
                            entry.queue_details.$$open = entry.job_id.value in _open_pops
                    0
                )
                @info = "waiting (#{@list.length} jobs, #{_waiting_slots} slots)"
            else
                @info = "no jobs waiting"
                
        calc_details: (ss) =>
            # calculate scheduling details
            # job
            j = ss.j
            # info dict
            d = ss.d
            # scheduler vars
            v = ss.s.vars
            d.raw_rr_contr = d.rr_contr
            # raw wait time
            d.raw_wt_contr = j.wait_time.raw
            if v.weight_deadline
                d.raw_dl_contr = d.dl_contr / v.weight_deadline
            else
                d.raw_dl_contr = "???"
            d.total_contr = d.rr_contr + d.wt_contr + d.dl_contr
            # priority
            d.eff_norm_pprio = v.weight_priority * d.norm_pprio
            # urgency
            d.eff_norm_urg = v.weight_urgency * d.norm_urg
            # tickets
            d.eff_norm_tickets = v.weight_ticket * d.norm_tickets
            # total
            d.eff_norm = d.eff_norm_pprio + d.eff_norm_urg + d.eff_norm_tickets

        calc_details_global: () =>
            _tot_min = _.min((entry.queue_details.raw.total_contr for entry in @list))
            _tot_max = _.max((entry.queue_details.raw.total_contr for entry in @list))
            if _tot_min == _tot_max
                d = @list[0].queue_details.raw
                d.f = 0.5
            else
                for entry in @list
                    d = entry.queue_details.raw
                    # this must be equal to norm_urg
                    d.f = (d.total_contr - _tot_min) / (_tot_max - _tot_min)

        toggle_popover: (job) =>
            job.queue_details.$$open = !job.queue_details.$$open

]).service("icswRMSDoneStruct",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswRMSTools",
    "icswRMSHeaderStruct",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswRMSTools,
    icswRMSHeaderStruct,
) ->
    class icswRMSDoneStruct extends icswRMSHeaderStruct
        constructor: (h_struct, struct) ->
            super("done", h_struct, struct)

        feed_list : (simple_list) =>
            @feed_json_list(simple_list)
            @salt_datetimes()
            @set_rrd_flags()
            @set_full_ids()
            @check_jobvar_display()
            {name_lut} = @struct
            for entry in @list
                # exit status

                if entry.exit_status of icswRMSTools.exit_status_lut
                    _td_entry = icswRMSTools.exit_status_lut[entry.exit_status]
                    if _td_entry[0] == 0
                        [_cls, _glyph, _str] = ["warn", _td_entry[2], _td_entry[1]]
                    else if _td_entry[0] == 1
                        [_cls, _glyph, _str] = ["ok", _td_entry[2], _td_entry[1]]
                    else
                        [_cls, _glyph, _str] = ["danger", _td_entry[2], _td_entry[1]]
                else
                    if entry.exit_status > 128
                        [_cls, _glyph, _str] = ["danger", "", entry.exit_status]
                    else if entry.exit_status
                        [_cls, _glyph, _str] = ["warn", "", entry.exit_status]
                    else
                        [_cls, _glyph, _str] = ["ok", "", entry.exit_status]
                if _glyph
                    _glyph = "glyphicon #{_glyph}"
                entry.$$exit_status_class = _cls
                entry.$$exit_status_glyph = _glyph
                entry.$$exit_status_str = _str

                # failed state
                if entry.failed of icswRMSTools.failed_lut
                    [_cls, _str, _title] = icswRMSTools.failed_lut[entry.failed]
                    if _title
                        _glyph = "glyphicon glyphicon-ok"
                    else
                        _glyph = "glyphicon glyphicon-minus"
                else
                    [_cls, _str, _title, _glyph] = ["label-warning", entry.failed, "", "glyphicon glyphicon-minus"]
                entry.$$failed_class = _cls
                entry.$$failed_str = _str
                entry.$$failed_glyph = _glyph
                entry.$$failed_title = _title
                # pe_info
                r_list = []
                if entry.rms_pe? and entry.rms_pe.length
                    # console.log "*", entry.pe
                    for _entry in entry.rms_pe
                        r_list.push("#{_entry.hostname} (#{_entry.slots})")
                else
                    if entry.device of name_lut
                        r_list.push("#{name_lut[entry.device].full_name} (#{entry.slots})")
                    else
                        r_list.push("---")
                entry.$$pe_info = r_list.join(",")
            if @list.length
                @info = "done (#{@list.length} jobs)"
            else
                @info = "no jobs finished"

]).service("icswRMSSchedulerStruct",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswRMSTools",
    "icswRMSHeaderStruct",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswRMSTools,
    icswRMSHeaderStruct,
) ->
    # simple key-value store for scheduler config
    class icswRMSSchedulerStruct
        constructor: (@scope) ->
            @vars = {}

        feed_list: (in_dict) =>
            @vars = in_dict

]).service("icswRMSNodeStruct",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswRMSQueue", "icswRMSTools",
    "icswRMSHeaderStruct",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswRMSQueue, icswRMSTools,
    icswRMSHeaderStruct,
) ->
    class icswRMSNodeStruct extends icswRMSHeaderStruct
        constructor: (h_struct, struct) ->
            super("node", h_struct, struct)
            @queue_list = []
            # disable display of this headers
            @hidden_headers = ["state", "slots_reserved", "slots_total"]

        feed_list : (simple_list) =>
            @feed_xml_list(simple_list)
            @set_rrd_flags()

            valid_loads = (parseFloat(entry.load.value) for entry in @list when entry.load.value.match(icswRMSTools.load_re))

            if valid_loads.length
                @max_load = _.max(valid_loads)
                # round to next multiple of 4
                @max_load = 4 * parseInt((@max_load + 3.9999  ) / 4)
            else
                @max_load = 4
            if @max_load == 0
                @max_load = 4

            # build queue list
            @build_queue_list()

        build_queue_list: () =>
            {slot_info} = @struct
            i_split = (in_str, nq) ->
                # one element per queue, if all elements are identical only one is reported
                parts = in_str.split("/")
                if parts.length != nq
                    parts = (parts[0] for _x in [1..nq])
                return parts
            n_split = (in_str) ->
                _rd = {}
                if in_str
                    for _part in in_str.split("/")
                        [_name, _value] = _part.split("::")
                        _rd[_name] = _value
                return _rd
            # empty old list
            @queue_list.length = 0

            for entry in @list

                queues = entry.queues.value.split("/")
                _number_queues = queues.length

                states = i_split(entry.state.value, _number_queues)
                loads = i_split(entry.load.value, _number_queues)
                types = i_split(entry.type.value, _number_queues)
                complexes = i_split(entry.complex.value, _number_queues)
                pe_lists = i_split(entry.pe_list.value, _number_queues)
                seqnos = i_split(entry.seqno.value, _number_queues)

                if entry.slots_total.value
                    # filter out empty slots values
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
                    entry.$$load_vector = _.zip(_total, _used, _reserved)
                    (slot_info.feed_vector(_lv) for _lv in entry.$$load_vector)

                # parse job entry, see sge_tools.py
                job_dict = n_split(entry.jobs.value)
                _idx = 0
                for _vals in _.zip(
                    queues, states, seqnos, loads, types, complexes, pe_lists,
                    i_split(entry.slots_used.value, _number_queues),
                    i_split(entry.slots_reserved.value, _number_queues),
                    i_split(entry.slots_total.value, _number_queues),
                    i_split(entry.jobs.value, _number_queues),
                )
                    queue = new icswRMSQueue(
                        _vals[0]
                        entry
                        _vals[1]
                        _vals[2]
                        entry.state.raw[_idx]
                        _vals[3]
                        @max_load
                        # slots used / reserved / total
                        [_vals[7], _vals[8], _vals[9]]
                        entry.topology
                    )
                    queue.type = {value: _vals[4]}
                    queue.complex = {value: _vals[5]}
                    queue.pe_list = {value: _vals[6]}
                    if _vals[0] of job_dict
                        queue.jobs = {value: job_dict[_vals[0]]}
                    else
                        queue.jobs = {value: ""}
                    @queue_list.push(queue)
                    _idx++
            @info = "queue (#{@queue_list.length} queues on #{@list.length} nodes, #{slot_info.used} of #{slot_info.total} slots used)"


]).controller("icswRMSOverviewCtrl",
[
    "$scope", "$compile", "Restangular", "ICSW_SIGNALS",
    "$q", "icswAcessLevelService", "$timeout", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswDeviceTreeService", "icswUserService",
    "icswRMSTools", "icswRMSHeaderStruct", "icswRMSSlotInfo", "icswRMSRunningStruct",
    "icswRMSWaitingStruct", "icswRMSDoneStruct", "icswRMSNodeStruct",
    "icswComplexModalService", "icswRMSJobVarStruct", "$window", "icswRMSSchedulerStruct",
(
    $scope, $compile, Restangular, ICSW_SIGNALS,
    $q, icswAcessLevelService, $timeout, ICSW_URLS,
    icswSimpleAjaxCall, icswDeviceTreeService, icswUserService,
    icswRMSTools, icswRMSHeaderStruct, icswRMSSlotInfo, icswRMSRunningStruct,
    icswRMSWaitingStruct, icswRMSDoneStruct, icswRMSNodeStruct,
    icswComplexModalService, icswRMSJobVarStruct, $window, icswRMSSchedulerStruct,
) ->
        icswAcessLevelService.install($scope)

        #    scope.show_done_rrd = (event, data) ->
        #        if data.rms_pe_info.length
        #            nodelist = (entry.device for entry in data.rms_pe_info)
        #        else
        #            nodelist = [data.device]
        #        rrd_nodes = scope.get_rrd_nodes(nodelist)
        #        job_id = data.rms_job.jobid
        #        if data.rms_job.taskid
        #            job_id = "#{job_id}.#{data.rms_job.taskid}"
        #        if rrd_nodes.length > 1
        #            rrd_title = "finished job #{job_id} on nodes " + rrd_nodes.join(",")
        #        else
        #            rrd_title = "finished job #{job_id} on node " + rrd_nodes[0]
        #        scope.show_rrd(event, rrd_nodes, data.start_time, data.end_time, rrd_title, "selected", job_id)

        #        scope.show_job_rrd = (event, job) ->
        #        rrd_nodes = scope.get_rrd_nodes(job.nodelist.raw)
        #        job_id = job.job_id.value
        #        if job.task_id.value
        #            job_id = "#{job_id}.#{job.task_id.value}"
        #        if rrd_nodes.length > 1
        #            rrd_title = "running job #{job_id} on nodes " + rrd_nodes.join(",")
        #        else
        #            rrd_title = "running job #{job_id} on node " + rrd_nodes[0]
        #        scope.show_rrd(event, rrd_nodes, job.start_time.raw, undefined, rrd_title, "selected", job_id)

        $scope.draw_rrd = (args...) ->
            # disable fetching
            $scope.struct.do_fetch = false
            # first argument is $event
            entry = args[1]
            # console.log "Draw", args
            sub_scope = $scope.$new(false)
            # set devices
            devices = ($scope.struct.device_tree.all_lut[_pk] for _pk in entry.$$rrd_device_ids)
            # console.log "devs=", devices
            sub_scope.devices = devices
            start_time = 0
            end_time = 0
            job_mode = 0
            selected_job = 0
            _template = """
<icsw-rrd-graph
    icsw-sel-man="1"
    icsw-device-list="devices"
    icsw-select-keys="load.*,net.all.*,mem.used.phys$,^swap.*"
    draw="1"
    mergedevices="0"
    icsw-graph-size="240x100"
    <!-- fromdt="#{start_time}"
    # todt="#{end_time}"
    # jobmode="#{job_mode}"
    # selectedjob="#{selected_job}" -->
></icsw-rrd-graph>
"""
            icswComplexModalService(
                {
                    message: $compile(_template)(sub_scope)
                    title: "RRD"
                    cancel_label: "Close"
                    cancel_callback: (modal) ->
                        defer = $q.defer()
                        defer.resolve("close")
                        return defer.promise
                }
            ).then(
                (fin) ->
                    sub_scope.$destroy()
                    $scope.struct.do_fetch = true
                    # trigger fetch
                    fetch_data()
            )

        $scope.struct = {
            # loading flag
            loading: false
            # updating flag
            updating: false
            # device tree
            device_tree: undefined
            # is rms operator
            rms_operator: false
            # current user (db entry)
            user: undefined
            # current user (icsUser entry)
            icsw_user: undefined
            # initial data present
            initial_data_present: false
            # search fields
            search: {
                running: ""
                waiting: ""
                done: ""
                node: ""
            }
            # rms structs
            rms: {}
            # IO dict (for stdout / stderr display)
            io_dict: {}
            # JobVar Struct (for Job variables, referencing jobs)
            jv_struct: new icswRMSJobVarStruct()
            # fetch timeout
            fetch_timeout: undefined
            # do fetch ?
            do_fetch: true
            # slot info
            slot_info: new icswRMSSlotInfo()
            # draw RRD overlay, not beautifull but working ...
            draw_rrd: $scope.draw_rrd
            # header_line
            header_line: "RMS Overview"
        }

        $scope.initial_load = () ->
            $scope.struct.loading = true
            $scope.struct.initial_data_present = false
            # init io-dict
            $scope.struct.io_dict = {}
            # init jv-dict
            $scope.struct.jv_struct.reset()
            $q.all(
                [
                    icswDeviceTreeService.load($scope.$id)
                    icswUserService.load($scope.$id)
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.RMS_GET_HEADER_DICT
                        dataType: "json"
                    )
                ]
            ).then(
                (data) ->
                    $scope.struct.device_tree = data[0]
                    # build name lookup dict
                    _dt_name_lut = {}
                    for entry in $scope.struct.device_tree.all_list
                        _dt_name_lut[entry.idx] = entry
                        _dt_name_lut[entry.name] = entry
                        _dt_name_lut[entry.full_name] = entry
                    $scope.struct.name_lut = _dt_name_lut
                    $scope.struct.icsw_user = data[1]
                    $scope.struct.user = data[1].user
                    $scope.struct.rms_operator = $scope.acl_modify(null, "backbone.user.rms_operator")
                    $scope.struct.loading = false
                    $scope.struct.rms = {
                        running: new icswRMSRunningStruct(data[2].running_headers, $scope.struct)
                        waiting: new icswRMSWaitingStruct(data[2].waiting_headers, $scope.struct)
                        done: new icswRMSDoneStruct(data[2].done_headers, $scope.struct)
                        node: new icswRMSNodeStruct(data[2].node_headers, $scope.struct)
                        sched: new icswRMSSchedulerStruct($scope.struct)
                    }
                    # apply user settings
                    _u = $scope.struct.icsw_user
                    for key of $scope.struct.rms
                        _var_name = "_rms_wf_#{key}"
                        # console.log key, _var_name
                        if _u.has_var(_var_name)
                            _value = _u.get_var(_var_name).value.split(",")
                            $scope.struct.rms[key].set_user_disabled(_value)
                    # initial data is now present
                    $scope.struct.initial_data_present = true
                    # start reload cycle
                    fetch_data()
            )

        $scope.$on("$destroy", () ->
            if $scope.struct.fetch_timeout
                $timeout.cancel($scope.struct.fetch_timeout)
        )

        $scope.initial_load()

        $scope.$on(ICSW_SIGNALS("_ICSW_RMS_UPDATE_DATA"), () ->
            if not $scope.struct.updating
                fetch_data()
        )

        fetch_data = () ->
            if $scope.struct.fetch_timeout
                $timeout.cancel($scope.struct.fetch_timeout)
            if $scope.struct.do_fetch and not $scope.struct.updating
                # only one update
                $scope.struct.updating = true
                icswSimpleAjaxCall(
                    url: ICSW_URLS.RMS_GET_RMS_JSON
                    dataType: "json"
                ).then(
                    (json) ->
                        # console.log "json=", json
                        # feed scheduler at first
                        $scope.struct.rms.sched.feed_list(json.sched_conf)
                        # reset counter
                        $scope.struct.slot_info.reset()
                        $scope.struct.jv_struct.feed_start()

                        $scope.struct.rms.running.feed_list(json.run_table, json.files)
                        # console.log json.wait_table
                        $scope.struct.rms.waiting.feed_list(json.wait_table)
                        $scope.struct.rms.done.feed_list(json.done_table)
                        $scope.struct.rms.node.feed_list(json.node_table)

                        $scope.struct.jv_struct.feed_end()

                        # fetch file ids
                        fetch_list = (struct.id for key, struct of $scope.struct.io_dict when struct.update)
                        if fetch_list.length
                            is_ie_below_eleven = /MSIE/.test($window.navigator.userAgent)
                            icswSimpleAjaxCall(
                                url: ICSW_URLS.RMS_GET_FILE_CONTENT
                                data:
                                    file_ids: angular.toJson(fetch_list)
                                    is_ie: if is_ie_below_eleven then 1 else 0
                            ).then(
                                (xml) ->
                                    xml = $(xml)
                                    for key, struct of $scope.struct.io_dict
                                        struct.feed(xml)
                                (error) ->
                                    # mark all io_structs with an update stop
                                    for key, struct of $scope.struct.io_dict
                                        struct.file_read_error()
                            )
                        $scope.struct.updating = false
                        $scope.struct.fetch_timeout = $timeout(fetch_data, 15000)
                    (error) ->
                        $scope.struct.updating = false
                        $scope.struct.fetch_timeout = $timeout(fetch_data, 15000)
            )

        $scope.close_io = (io_struct) ->
            # delay closing
            $timeout(
                () ->
                    delete $scope.struct.io_dict[io_struct.id]
                5
            )

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

]).directive("icswRmsJobRunningTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.running.table")
        scope:
            struct: "=icswRmsStruct"
            gstruct: "=icswRmsGlobal"
        controller: "icswRmsJobRunningCtrl"
    }
]).controller("icswRmsJobRunningCtrl",
[
    "$scope", "icswRMSIOStruct", "ICSW_SIGNALS",
(
    $scope, icswRMSIOStruct, ICSW_SIGNALS,
) ->
    $scope.activate_io = (job, io_type) ->
        io_id = "#{job.$$full_job_id}.#{io_type}"
        if io_id not of $scope.gstruct.io_dict
            new_io = new icswRMSIOStruct(job.$$full_job_id, io_type)
            $scope.gstruct.io_dict[io_id] = new_io
            # activate tab
            new_io.active = true
            $scope.$emit(ICSW_SIGNALS("_ICSW_RMS_UPDATE_DATA"))

]).directive("icswRmsJobWaitingTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.waiting.table")
        scope:
            struct: "=icswRmsStruct"
            gstruct: "=icswRmsGlobal"
    }
]).directive("icswRmsJobDoneTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.rms.job.done.table")
        scope:
            struct: "=icswRmsStruct"
            gstruct: "=icswRmsGlobal"
        controller: "icswRmsJobDoneCtrl"
    }
]).controller("icswRmsJobDoneCtrl",
[
    "$scope", "icswRMSIOStruct", "ICSW_SIGNALS",
(
    $scope, icswRMSIOStruct, ICSW_SIGNALS,
) ->
]).directive("icswRmsQueueTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.queue.table")
        scope:
            struct: "=icswRmsStruct"
            gstruct: "=icswRmsGlobal"
    }
]).directive("icswRmsIoStruct",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.iostruct")
    }
]).directive("icswRmsTableHeaders",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.table.headers")
        scope:
            struct: "=icswRmsStruct"
    }
]).directive("icswRmsTableHeaderToggle",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.table.header.toggle")
        scope:
            struct: "=icswRmsStruct"
    }
]).directive("icswRmsJobDoneLine", ["$templateCache", "$sce", ($templateCache, $sce) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.job.done.line")
    }
]).directive("icswRmsJobWaitLine", ["$templateCache", "$sce", ($templateCache, $sce) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.job.wait.line")
    }
]).directive("icswRmsJobVarInfo", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.job.var.info")
        scope:
            struct: "=icswRmsJvStruct"
    }
]).directive("icswRmsJobRunLine",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.job.run.line")
    }
]).directive("icswRmsQueueLine",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.queue.line")
    }
]).directive("icswRmsJobAction",
[
    "$compile", "$templateCache", "$uibModal", "ICSW_URLS", "$q",
    "icswSimpleAjaxCall", "icswComplexModalService", "blockUI", "icswToolsSimpleModalService",
    "ICSW_SIGNALS",
(
    $compile, $templateCache, $uibModal, ICSW_URLS, $q,
    icswSimpleAjaxCall, icswComplexModalService, blockUI, icswToolsSimpleModalService,
    ICSW_SIGNALS,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.job.action")
        scope:
            job: "=icswRmsJob"
            job_type: "=icswRmsJobType"
            is_oper: "=icswRmsIsOperator"
        replace: true
        link: (scope, el, attrs) ->

            scope.job_control = (command, force) ->
                _cmd = if force then "force delete" else "delete"
                icswToolsSimpleModalService("Really #{_cmd} job #{scope.job.$$full_job_id} ?").then(
                    (doit) ->
                        blockUI.start("deleting job")
                        icswSimpleAjaxCall(
                            url: ICSW_URLS.RMS_CONTROL_JOB
                            data: {
                                job_id: scope.job.job_id.value
                                task_id: scope.job.task_id.value
                                command: command
                            }
                        ).then(
                            (xml) ->
                                scope.$emit(ICSW_SIGNALS("_ICSW_RMS_UPDATE_DATA"))
                                blockUI.stop()
                            (error) ->
                                blockUI.stop()
                        )
                )

            scope.change_priority = () ->
                
                # new isolated scope
                child_scope = scope.$new(false)

                child_scope.job = scope.job
                child_scope.cur_priority = parseInt(scope.job.priority.value)

                child_scope.max_priority = if scope.is_oper then 1024 else 0
                    
                icswComplexModalService(
                    {
                        message: $compile($templateCache.get("icsw.rms.change.priority"))(child_scope) 
                        ok_label: "Modify"
                        title: "Modify priority of job #{child_scope.job.$$full_job_id}"
                        ok_callback: (modal) ->
                            d = $q.defer()
                            blockUI.start("modifying priority")
                            icswSimpleAjaxCall(
                                url: ICSW_URLS.RMS_CHANGE_JOB_PRIORITY
                                data:
                                    job_id: child_scope.job.job_id.value
                                    new_pri: child_scope.cur_priority
                            ).then(
                                (xml) ->
                                    scope.job.priority.value = child_scope.cur_priority
                                    blockUI.stop()
                                    scope.$emit(ICSW_SIGNALS("_ICSW_RMS_UPDATE_DATA"))
                                    d.resolve("done")
                                (error) ->
                                    blockUI.stop()
                                    d.resolve("done")
                            )
                            return d.promise
                        cancel_callback: (modal) ->
                            d = $q.defer()
                            d.resolve("done")
                            return d.promise
                    }
                ).then(
                    (fin) ->
                        child_scope.$destroy()
                )
    }
]).directive("icswRmsQueueState",
[
    "$compile", "$templateCache", "blockUI", "icswSimpleAjaxCall",
    "ICSW_URLS", "ICSW_SIGNALS",
(
    $compile, $templateCache, blockUI, icswSimpleAjaxCall,
    ICSW_URLS, ICSW_SIGNALS,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.rms.queue.state.oper")
        scope:
            queue: "=icswRmsQueue"
        replace: true
        link: (scope, element, attrs) ->
            scope.queue_control = (command, queue) ->
                blockUI.start("modifying queue #{queue.$$queue_name}...")
                icswSimpleAjaxCall(
                    url: ICSW_URLS.RMS_CONTROL_QUEUE
                    data: {
                        queue: queue.name
                        host: queue.host.host.value
                        command: command
                    }
                ).then(
                    (xml) ->
                        scope.$emit(ICSW_SIGNALS("_ICSW_RMS_UPDATE_DATA"))
                        blockUI.stop()
                    (error) ->
                        blockUI.stop()
                )

    }
]).directive("icswRmsFileInfo",
[
    "$compile", "$templateCache",
(
    $compile, $templateCache
) ->
    return {
        restrict: "EA"
        scope:
            job: "=icswRmsJob"
        template: $templateCache.get("icsw.rms.file.info")
    }
]).service("icswRmsTopologyInfoReact",
[
    "$q",
(
    $q,
) ->
    {div, g, text, line, polyline, path, svg, h3, rect} = React.DOM
    return React.createClass(
        propTypes: {
            topo: React.PropTypes.array
        }

        render: () ->
            get_color = (node) ->
                if node.u
                    return "#dd8888"
                else
                    return "#f0f0f0"

            if @props.topo
                # baseline size
                _bs = 10
                _num_sockets = 0
                _num_cores = 0
                _num_threads = 0
                _rect_list = []
                _x = 0
                for _s in @props.topo
                    _num_sockets++
                    _rect_list.push(
                        rect(
                            {
                                key: "s#{_num_sockets}"
                                x: _x
                                y: 0
                                width: _bs * _s.l.length
                                height: _bs
                                style: {fill: get_color(_s), strokeWidth: "1px", stroke: "black"}
                            }
                        )
                    )
                    for _c in _s.l
                        _num_cores++
                        _rect_list.push(
                            rect(
                                {
                                    key: "c#{_num_cores}"
                                    x: _x
                                    y: _bs
                                    width: _bs
                                    height: _bs
                                    style: {fill: get_color(_c), strokeWidth: "1px", stroke: "black"}
                                }
                            )
                        )
                        _x += _bs
                        if c.l?
                            for _t in _c.l
                                _num_threads++
                        else
                            # at least one thread per core
                            _num_threads++
                _w = _num_cores * _bs
                _h = 2 * _bs

                # console.log @props.topo, _num_sockets, _num_cores, _num_threads
                return svg(
                    {
                        key: "svg.top"
                        width: "#{_w}px"
                        height: "#{_h}px"
                    }
                    g(
                        {
                            key: "svg.g"
                        }
                        _rect_list
                    )
                )
            else
                return div(
                    {
                        key: "top"
                    }
                    "N/A"
                )
    )
]).directive("icswRmsTopologyInfo",
[
    "$q", "icswRmsTopologyInfoReact",
(
    $q, icswRmsTopologyInfoReact,
) ->
    return {
        restrict: "E"
        link: (scope, element, attrs) ->
            _el = ReactDOM.render(
                React.createElement(
                    icswRmsTopologyInfoReact
                    {
                        topo: scope.queue.topology_raw
                    }
                )
                element[0]
            )
            scope.$on(
                "$destroy"
                () ->
                    ReactDOM.unmountComponentAtNode(element[0])
            )
    }
])
