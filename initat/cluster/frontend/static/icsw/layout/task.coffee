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
).service("icswProcessService",
[
    "$q", "$rootScope", "ICSW_SIGNALS", "icswComplexModalService", "blockUI",
    "$compile", "$templateCache", "ICSW_CONFIG_JSON",
(
    $q, $rootScope, ICSW_SIGNALS, icswComplexModalService, blockUI,
    $compile, $templateCache, ICSW_CONFIG_JSON,
) ->
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
        constructor: (@json) ->
            @name = @json.name
            @info = "#{@json.name} (#{@json.app})"

    console.log ICSW_CONFIG_JSON
    struct = {
        active_task: null
        task_container: new icswContainer("json[name]")
    }

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
            edit_scope.edit_obj = {task: struct.active_task.idx}
        else
            edit_scope.edit_obj = {task: 0}

        edit_scope.task_changed = () ->
            edit_scope.active_task = edit_scope.task_container.list[edit_scope.edit_obj.task]

        edit_scope.task_changed()

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.task.choose.task"))(edit_scope)
                title: "Choose task"
                closable: true
                ok_label: "Select"
                cancel_label: "Cancel task"
                ok_callback: (modal) ->
                    d = $q.defer()
                    struct.active_task = edit_scope.active_task
                    _signal()
                    d.resolve("done")
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    struct.active_task = null
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
    # signal after init
    _signal()

    return {
        get_struct: () ->
            return struct

        choose_task: () ->
            return _choose_task()
    }
]).factory("icswProcessOverviewReact",
[
    "icswUserService", "icswOverallStyle", "icswProcessService", "$rootScope",
    "ICSW_SIGNALS",
(
    icswUserService, icswOverallStyle, icswProcessService, $rootScope,
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
            @setState({struct: icswProcessService.get_struct()})
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
                            disabled: true
                        }
                        span(
                            {
                                className: "glyphicon glyphicon-triangle-left"
                            }
                        )
                    )
                )
                _cs = "1 / #{_task.json.taskStep.length}"
                _el_list.push(
                    span(
                        {
                            key: "infot"
                            className: "cursorpointer"
                            title: _task.info
                            onClick: (event) ->
                                icswProcessService.choose_task()
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
                            className: "label label-default cursorpointer"
                            title: "No task active"
                            onClick: (event) ->
                                icswProcessService.choose_task()
                        }
                        "NTA"
                    )
                )
                _a_style = {}
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
