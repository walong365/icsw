# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

angular.module(
    "icsw.layout.task",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).service("icswTaskService",
[
    "$q", "$rootScope", "ICSW_SIGNALS", "icswComplexModalService", "blockUI",
    "$compile", "$templateCache", "ICSW_CONFIG_JSON", "$state", "icswLanguageTool",
    "hotkeys",
(
    $q, $rootScope, ICSW_SIGNALS, icswComplexModalService, blockUI,
    $compile, $templateCache, ICSW_CONFIG_JSON, $state, icswLanguageTool,
    hotkeys,
) ->
    # default language
    def_lang = icswLanguageTool.get_lang()

    class icswContainer
        constructor: (@id_path) ->
            @idx = 0
            @list = []
            @lut = {}

        feed: (el) =>
            el.idx = @idx
            @list.push(el)
            if @id_path? and @id_path
                @lut[_.get(el, @id_path)] = el
            @idx++
            console.log @lut, @list

    class icswTaskDef
        # taskdefinition, container for Defined Tasks
        constructor: (@json) ->
            # simple settings
            @name = @json.name
            @info = "#{@json.name} (#{@json.app})"
            @link()

        link: () =>
            _idx = 0
            for step in @json.taskStep
                _idx++
                _state = $state.get(step.routeName)
                # default value
                step.$$info_str = "#{step.routeName} N/A"
                step.$$idx = _idx
                if _state.icswData?
                    _data = _state.icswData
                    if _data.description.en?
                        step.$$info_str = "#{_data.description[def_lang].text}"
                    else if _data.$$menuEntry
                        step.$$info_str = _data.$$menuEntry.name

    class icswTask
        # actual task, adds state control
        constructor: (tdef) ->
            @task_def = tdef
            @start()

        start: () =>
            # start task
            @_step_idx = 0
            @link()

        step_forward: () =>
            _max_step = @task_def.json.taskStep.length
            if @_step_idx < _max_step - 1
                @_step_idx++
                @link()

        step_backward: () =>
            if @_step_idx
                @_step_idx--
                @link()

        link: () =>
            @$$forward_ok = @_step_idx < @task_def.json.taskStep.length - 1
            @$$backward_ok = @_step_idx > 0
            @active_step = @task_def.json.taskStep[@_step_idx]
            console.log @active_step
            $state.go(@active_step.routeName)
            @$$info_str = " #{@_step_idx + 1} / #{@task_def.json.taskStep.length} "
            _signal()

    struct = {
        # contains an icswTask definition or null
        active_task: null
        # task container
        task_container: new icswContainer("json[name]")
        # keyboard shortcuts defined
        keys_defined: false
    }

    # key helper functions
    update_keys = () ->
        _remove_keys()
        _add_keys()

    _add_keys = () ->
        if not struct.keys_defined
            struct.keys_defined = true
            hotkeys.add(
                combo: "f3"
                description: "Select task"
                allowIn: ["INPUT"]
                callback: (event) ->
                    _choose_task()
                    event.preventDefault()
            )
            if struct.active_task
                hotkeys.add(
                    combo: "f4"
                    description: "One step forward"
                    allowIn: ["INPUT"]
                    callback: (event) ->
                        if struct.active_task
                            struct.active_task.step_forward()
                        event.preventDefault()
                )
                hotkeys.add(
                    combo: "f6"
                    description: "One step backward"
                    allowIn: ["INPUT"]
                    callback: (event) ->
                        if struct.active_task
                            struct.active_task.step_backward()
                        event.preventDefault()
                )

    _remove_keys = () ->
        if struct.keys_defined
            struct.keys_defined = false
            hotkeys.del("f3")
            hotkeys.del("f4")
            hotkeys.del("f6")

    _signal = () ->
        $rootScope.$emit(ICSW_SIGNALS("ICSW_PROCESS_SETTINGS_CHANGED"))

    _init_tasks = () ->
        _task_list = ICSW_CONFIG_JSON.tasks.task
        for _task in _task_list
            struct.task_container.feed(new icswTaskDef(_task))

    _choose_task = () ->
        edit_scope = $rootScope.$new(true)
        edit_scope.task_container = struct.task_container
        # need object for ui-select to work properly
        if struct.active_task
            edit_scope.edit_obj = {task: struct.active_task.task_def.idx}
            edit_scope.running_task = struct.active_task
            cancel_label = "Cancel task"
        else
            edit_scope.edit_obj = {task: 0}
            edit_scope.running_task = null
            cancel_label = "Cancel"

        edit_scope.task_changed = () ->
            edit_scope.active_task = edit_scope.task_container.list[edit_scope.edit_obj.task]

        edit_scope.task_changed()

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.task.choose.task"))(edit_scope)
                title: "Choose task"
                closable: true
                ok_label: "Select"
                cancel_label: cancel_label
                ok_callback: (modal) ->
                    d = $q.defer()
                    struct.active_task = new icswTask(edit_scope.active_task)
                    update_keys()
                    _signal()
                    d.resolve("done")
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    struct.active_task = null
                    update_keys()
                    _signal()
                    d.resolve("done")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "done"
                edit_scope.$destroy()
                _signal()
        )
    # init tasks
    _init_tasks()
    # update keys
    update_keys()
    # signal after init
    _signal()

    # task control
    step_forward = (task) ->
        task.step_forward()
        _signal()

    return {
        get_struct: () ->
            return struct

        choose_task: () ->
            return _choose_task()

    }
]).factory("icswTaskOverviewReact",
[
    "icswUserService", "icswOverallStyle", "icswTaskService", "$rootScope",
    "ICSW_SIGNALS",
(
    icswUserService, icswOverallStyle, icswTaskService, $rootScope,
    ICSW_SIGNALS,
) ->
    {ul, li, a, span, h4, div, p, strong, h3, i, hr, button} = React.DOM
    return React.createClass(
        # propTypes:
        #    side: React.PropTypes.string

        displayName: "ProcessOverview"

        getInitialState: () ->
            return {
                counter: 0
                struct: null
            }

        componentWillMount: () ->
            @setState({struct: icswTaskService.get_struct()})
            @_dereg_handler = $rootScope.$on(ICSW_SIGNALS("ICSW_PROCESS_SETTINGS_CHANGED"), () =>
                console.log "ipc"
                @force_redraw()
            )

        componentWillUmount: () ->
            @_dereg_handler()

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            # console.log "RR", @state
            # _menu_struct = icswRouteHelper.get_struct()
            # menus = (entry for entry in _menu_struct.menu_node.entries when entry.data.side == @props.side)
            _el_list = []
            _task = @state.struct.active_task
            _task_active = if _task then true else false
            if _task_active
                _el_list.push(
                    button(
                        {
                            key: "bwb"
                            type: "button"
                            className: "btn btn-xs btn-default"
                            disabled: not _task.$$backward_ok
                            onClick: (event) ->
                                _task.step_backward()
                        }
                        span(
                            {
                                className: "glyphicon glyphicon-triangle-left"
                            }
                        )
                    )
                )
                _cs = _task.$$info_str
                _el_list.push(
                    span(
                        {
                            key: "infot"
                            className: "cursorpointer"
                            title: _task.info
                            onClick: (event) ->
                                icswTaskService.choose_task()
                        }
                        _cs
                    )
                )
                _el_list.push(
                    button(
                        {
                            key: "bwf"
                            type: "button"
                            className: "btn btn-xs btn-default"
                            disabled: not _task.$$forward_ok
                            onClick: (event) ->
                                _task.step_forward()
                        }
                        span(
                            {
                                className: "glyphicon glyphicon-triangle-right"
                            }
                        )
                    )
                )
                _a_style = {padding: "12px"}
            else
                _el_list.push(
                    span(
                        {
                            key: "np"
                            className: "label label-primary cursorpointer"
                            title: "No task active"
                            style: {fontSize: "24px"}
                            onClick: (event) ->
                                icswTaskService.choose_task()
                        }
                        "?"
                    )
                )
                _a_style = {padding: "12px"}
            _res = li(
                {}
                a(
                    {
                        style: _a_style
                    }
                    _el_list
                )
            )
            return _res
    )
])
