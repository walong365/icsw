# Copyright (C) 2012-2017 init.at
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
    "hotkeys", "icswMenuSettings",
(
    $q, $rootScope, ICSW_SIGNALS, icswComplexModalService, blockUI,
    $compile, $templateCache, ICSW_CONFIG_JSON, $state, icswLanguageTool,
    hotkeys, icswMenuSettings,
) ->
    # default language
    def_lang = icswLanguageTool.get_lang()

    G_STRUCT = {
        modal_open: false
    }

    class icswContainer
        constructor: (@id_path) ->
            @list = []
            @lut = {}

        reset: () =>
            @list.length = 0

        feed: (el) =>
            @list.push(el)
            if @id_path? and @id_path
                @lut[_.get(el, @id_path)] = el
                @lut[el.task_def_id] = el
            # console.log @lut, @list

    class icswTaskDef
        # taskdefinition, container for Defined Tasks
        constructor: (@json) ->
            struct.task_def_id++
            @task_def_id = struct.task_def_id
            # simple settings
            @name = @json.name
            @info = "#{@json.name} (#{@json.app})"
            @link()

        link: () =>
            _idx = 0
            for step in @json.taskStep
                _state = $state.get(step.routeName)
                # default value
                step.$$info_str = "#{step.routeName} N/A"
                step.$$idx = _idx
                _idx++
                if _state.icswData?
                    _data = _state.icswData
                    if _data.description[def_lang]?
                        step.$$info_str = "#{_data.description[def_lang].text}"
                    else if _data.$$menuEntry
                        step.$$info_str = _data.$$menuEntry.name

    class icswTask
        # actual task, adds state control
        constructor: (tdef, settings) ->
            struct.task_id++
            @task_id = struct.task_id
            @$$step_valid = false
            @task_def = tdef
            @settings = {}
            _.assignIn(@settings, settings)
            console.log "s=", @settings
            @start()

        hide_guide: () =>
            @settings.show_guide = false
            _signal()

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

        set_active_node: (node) =>
            @_step_idx = node.$$idx
            @link()

        link: () =>
            @$$forward_ok = @_step_idx < @task_def.json.taskStep.length - 1
            @$$backward_ok = @_step_idx > 0
            @active_step = @task_def.json.taskStep[@_step_idx]
            # console.log @active_step
            @$$info_str = " #{@_step_idx + 1} / #{@task_def.json.taskStep.length} "
            # valid (current route matches)
            @$$step_valid = true
            # console.log "S", @active_step
            if @active_step.routeParams
                _params = @active_step.routeParams
            else
                _params = {}
            $state.go(@active_step.routeName, _params)
            _signal()

        check_validity: () =>
            if $state.current.name == @active_step.routeName
                _valid = true
            else
                _valid = false
            if _valid != @$$step_valid
                @$$step_valid = false
                _signal()

    struct = {
        # contains an icswTask definition or null
        active_task: null
        # task container
        task_container: new icswContainer("json[name]")
        # keyboard shortcuts defined
        keys_defined: false
        # task definition id
        task_def_id: 0
        # running task id
        task_id: 0
        # current menu layout
        menu_layout: ""
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
                description: "Select Task"
                allowIn: ["INPUT"]
                callback: (event) ->
                    _choose_task()
                    event.preventDefault()
            )
            if struct.active_task
                hotkeys.add(
                    combo: "pageup"
                    description: "One Step forward"
                    callback: (event) ->
                        if struct.active_task
                            struct.active_task.step_forward()
                        event.preventDefault()
                )
                hotkeys.add(
                    combo: "pagedown"
                    description: "One Step backward"
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
        $rootScope.$emit(ICSW_SIGNALS("ICSW_TASK_SETTINGS_CHANGED"))

    _init_tasks = () ->
        _layout = icswMenuSettings.get_menu_layout()
        _task_list = ICSW_CONFIG_JSON[_layout].tasks.task
        struct.menu_layout = _layout
        struct.task_container.reset()
        for _task in _task_list
            struct.task_container.feed(new icswTaskDef(_task))

    _choose_task = () ->
        if G_STRUCT.modal_open
            return
        G_STRUCT.modal_open = true
        edit_scope = $rootScope.$new(true)
        edit_scope.task_container = struct.task_container
        # need object for ui-select to work properly
        if struct.active_task
            console.log "*", struct.active_task
            edit_scope.edit_obj = {
                task_def: struct.active_task.task_def.task_def_id
            }
            edit_scope.running_task = struct.active_task
            edit_scope.settings = edit_scope.running_task.settings
            cancel_label = "Cancel Task"
        else
            edit_scope.settings = {
                show_guide: true
            }
            edit_scope.edit_obj = {
                task_def: edit_scope.task_container.list[0].task_def_id
            }
            edit_scope.running_task = null
            cancel_label = "Cancel"

        edit_scope.task_changed = () ->
            edit_scope.new_task_def = edit_scope.task_container.lut[edit_scope.edit_obj.task_def]

        edit_scope.task_changed()

        edit_scope.lgi_class = (item) ->
            _class = ["list-group-item"]
            if struct.active_task and edit_scope.new_task_def.task_def_id == edit_scope.running_task.task_def.task_def_id
                # modifying current task
                if item.$$idx == struct.active_task._step_idx
                    _class.push("active")
            return _class.join(" ")

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.task.choose.task"))(edit_scope)
                title: "Choose Task"
                closable: true
                ok_label: "Select"
                cancel_label: cancel_label
                ok_callback: (modal) ->
                    d = $q.defer()
                    if struct.active_task and edit_scope.new_task_def.task_def_id == edit_scope.running_task.task_def.task_def_id
                        # modify current task
                        true
                    else
                        # create new task
                        struct.active_task = new icswTask(edit_scope.new_task_def, edit_scope.settings)
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
                # console.log "done"
                edit_scope.$destroy()
                $rootScope.task_modal = undefined
                G_STRUCT.modal_open = false
                _signal()
        )

    _stop_active_task = () ->
        struct.active_task = null

    # init tasks
    _init_tasks()
    # update keys
    # update_keys()
    # signal after init
    _signal()

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        _add_keys()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        _remove_keys()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_SETTINGS_CHANGED"), () ->
        if struct.menu_layout != icswMenuSettings.get_menu_layout()
            _init_tasks()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_STATE_CHANGED"), () ->
        if struct.active_task
            struct.active_task.check_validity()
    )

    return {
        get_struct: () ->
            return struct

        stop_active_task: () ->
            return _stop_active_task()

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
            @_dereg_handler = $rootScope.$on(ICSW_SIGNALS("ICSW_TASK_SETTINGS_CHANGED"), () =>
                # console.log "ipc"
                @force_redraw()
            )

        componentWillUnmount: () ->
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
                            className: "label label-default cursorpointer fa fa-star wizardbutton"
                            title: "No Task active"
                            # style: {fontSize: "24px"}
                            onClick: (event) ->
                                icswTaskService.choose_task()
                        }
                        " "
                    )
                )
                _a_style = {padding: "12px"}
            _res = li(
                {}
                a(
                    {
                        # style: _a_style
                        className: "task-wizard"
                    }
                    _el_list
                )
            )
            return _res
    )
]).directive("icswTaskProgressOverview",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        controller: "icswTaskProgressOverviewCtrl",
        template: $templateCache.get("icsw.task.progress.overview")
        scope: true
    }
]).controller("icswTaskProgressOverviewCtrl",
[
    "$scope", "$q", "icswTaskService", "$rootScope", "ICSW_SIGNALS",
    "icswToolsSimpleModalService",
(
    $scope, $q, icswTaskService, $rootScope, ICSW_SIGNALS,
    icswToolsSimpleModalService,
) ->
    $scope.struct = {
        # display flag
        display: false
        # task struct
        task_struct: null
        # active task
        active_task: null
    }
    _update = () ->
        if $scope.struct.task_struct.active_task
            $scope.struct.active_task = $scope.struct.task_struct.active_task
            $scope.struct.display = $scope.struct.active_task.settings.show_guide
        else
            $scope.struct.active_task = null
            $scope.struct.display = false

    $rootScope.$on(ICSW_SIGNALS("ICSW_TASK_SETTINGS_CHANGED"), () ->
        $scope.struct.task_struct = icswTaskService.get_struct()
        _update()
    )

    $scope.hide_guide = ($event) ->
        if $scope.struct.active_task
            $scope.struct.active_task.hide_guide()

    $scope.stop_task = ($event) ->
        if $scope.struct.active_task
            icswToolsSimpleModalService("Really stop current task ?").then(
                (ok) ->
                    icswTaskService.stop_active_task()
                    _update()
            )

    $scope.choose_task = ($event) ->
        return icswTaskService.choose_task()
]).factory("icswTaskProgressDisplayReact",
[
    "icswUserService", "icswOverallStyle", "icswTaskService", "$rootScope",
    "ICSW_SIGNALS",
(
    icswUserService, icswOverallStyle, icswTaskService, $rootScope,
    ICSW_SIGNALS,
) ->
    {div, g, circle, svg, title, text} = React.DOM
    return React.createClass(
        # propTypes:
        #    side: React.PropTypes.string

        displayName: "TaskProgressDisplay"

        componentWillMount: () ->
            @dereg_0 = $rootScope.$on(ICSW_SIGNALS("ICSW_TASK_SETTINGS_CHANGED"), () =>
                @force_redraw()
            )
            console.log "mount"

        componentWillUnmount: () ->
            console.log "unmount"
            @dereg_0()

        getInitialState: () ->
            return {
                counter: 0
                struct: null
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            _struct = icswTaskService.get_struct()
            height = 30
            step_x = 60

            draw_circle = (node, active_task) ->
                _x = step_x * node.$$idx
                _y = height / 2
                _done = active_task._step_idx > node.$$idx
                _current = active_task._step_idx == node.$$idx

                if _done
                    _fill = "svg-dev-up"
                else if _current
                    if active_task.$$step_valid
                        _fill = "svg-dev-down"
                    else
                        _fill = "svg-srv-warn"
                else
                    _fill = "svg-inactive"  # svg-white
                return g(
                    {
                        key: "node#{node.$$idx}"
                        transform: "translate(#{_x}, #{_y})"
                        className: "cursorpointer"
                        onClick: (event) =>
                            active_task.set_active_node(node)
                    }
                    circle(
                        {
                            key: "c"
                            r: "18"
                            className: "svg-lightstroke #{_fill}"
                            style: {
                                strokeWidth: "2px"
                            }
                        }
                    )
                    title(
                        {
                            key: "title"
                        }
                        node.$$info_str
                    )
                    if active_task.task_def.json.taskStep.length-1 > node.$$idx
                        text(
                            {
                                key: "arrow"
                                fontFamily: "FontAwesome"
                                fontSize: 18
                                x: 22
                                y: 6
                                className: "svg-lighttxt-color"
                                #dangerouslySetInnerHTML: {__html: "&#xf061;"}
                                dangerouslySetInnerHTML: {__html: "&#xf178;"}
                            }

                        )
                )

            if not _struct.active_task
                return null
            return div(
                {
                    key: "top"
                }
                svg(
                    {
                        key: "top"
                        width: "98%"
                        height: "40"
                        viewBox: "0 -5 200 40"
                    }
                    (
                        draw_circle(node, _struct.active_task) for node in _struct.active_task.task_def.json.taskStep
                    )
                )
            )
    )
]).directive("icswTaskProgressDisplay",
[
    "$q", "icswTaskProgressDisplayReact",
(
    $q, icswTaskProgressDisplayReact,
) ->
    return {
        restrict: "EA"
        replace: true
        link: (scope, el, attrs) ->
            _element = ReactDOM.render(
                React.createElement(
                    icswTaskProgressDisplayReact
                    {}
                )
                el[0]
            )
            scope.$on("$destroy", () ->
                ReactDOM.unmountComponentAtNode(el[0])
            )
    }
])
