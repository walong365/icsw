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

menu_module = angular.module(
    "icsw.layout.menu",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).controller("icswMenuBaseCtrl",
[
    "$scope", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswAcessLevelService",
    "initProduct", "icswLayoutSelectionDialogService", "icswActiveSelectionService",
    "$q", "icswUserService", "blockUI", "$state", "icswSystemLicenseDataService",
    "$rootScope", "ICSW_SIGNALS", "$timeout",
(
    $scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswAcessLevelService,
    initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService,
    $q, icswUserService, blockUI, $state, icswSystemLicenseDataService,
    $rootScope, ICSW_SIGNALS, $timeout,
) ->
    # init service types
    $scope.ICSW_URLS = ICSW_URLS
    $scope.initProduct = initProduct
    $scope.struct = {
        # current user
        current_user: undefined
        # selection string
        selection_string: "N/A"
        # focus search field
        focus_search: false
        # typeahead is loading
        typeahead_loading: false
        # search-strings
        search_string: ""
    }
    $scope.HANDBOOK_PDF_PRESENT = false
    $scope.HANDBOOK_CHUNKS_PRESENT = false
    $scope.HANDBOOK_PAGE = "---"
    icswAcessLevelService.install($scope)

    # typeahead functions
    $scope.get_selections = (view_value) ->
        console.log "gs", view_value
        defer = $q.defer()
        $scope.struct.typeahead_loading = true
        $timeout(
            () ->
                $scope.struct.typeahead_loading = false
                defer.resolve(["a", "b", "aqweqe", "123"])
            1000
        )
        return defer.promise

    $q.all(
        [
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.MAIN_GET_DOCU_INFO
                    dataType: "json"
                }
            )
            icswUserService.load($scope.$id)
        ]
    ).then(
        (data) ->
            $scope.HANDBOOK_PDF_PRESENT = data[0].HANDBOOK_PDF_PRESENT
            $scope.HANDBOOK_CHUNKS_PRESENT = data[0].HANDBOOK_CHUNKS_PRESENT
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get().user
        $scope.struct.focus_search = true
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        $scope.struct.current_user = undefined
    )

    $scope.get_progress_style = (obj) ->
        return {width: "#{obj.value}%"}

    $scope.redirect_to_init = () ->
        window.location = "http://www.initat.org"
        return false

    $scope.device_selection = ($event) ->
        icswLayoutSelectionDialogService.quick_dialog("right")

    $scope.handbook_url = "/"
    $scope.handbook_url_valid = false

    $scope.$watch(
        "initProduct",
        (new_val) ->
            if new_val.name?
                $scope.handbook_url_valid = true
                $scope.handbook_url = "/icsw/docu/handbook/#{new_val.name.toLowerCase()}_handbook.pdf"
        true
    )

    # not needed, now handled in menubar-component
    # $scope.$watch(
    #    "size",
    #    (new_val) ->
    #        console.log "size=", new_val
    #        $rootScope.$emit(ICSW_SIGNALS("ICSW_RENDER_MENUBAR"))
    # )

    # load license tree
    icswSystemLicenseDataService.load($scope.$id).then(
        (data) ->
    )

    # $scope.device_selection = () ->
    #    console.log "SHOW_DIALOG"
    #     icswLayoutSelectionDialogService.show_dialog()

    # apply selected theme if theme is set in session
]).directive("icswLayoutMenubar",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar")
    }
]).service("icswMenuProgressService",
[
    "ICSW_SIGNALS", "$rootScope",
(
    ICSW_SIGNALS, $rootScope
) ->
    _settings = {
        # progress bar counter
        rebuilding: 0
    }
    return {
        set_rebuilding: (count) ->
            if count != _settings.rebuilding
                _settings.rebuilding = count
                $rootScope.$emit(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), _settings)
        get_rebuilding: () ->
            return _settings.rebuilding
    }
]).directive("icswMenuProgressBars",
[
    "$templateCache", "ICSW_URLS", "$timeout", "icswSimpleAjaxCall", "initProduct",
    "icswMenuProgressService", "icswLayoutSelectionDialogService", "ICSW_SIGNALS",
    "$rootScope", "$state",
(
    $templateCache, ICSW_URLS, $timeout, icswSimpleAjaxCall, initProduct,
    icswMenuProgressService, icswLayoutSelectionDialogService, ICSW_SIGNALS,
    $rootScope, $state
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar.progress")
        scope: {}
        link: (scope, el, attrs) ->
            scope.initProduct = initProduct
            scope.num_gauges = 0
            scope.progress_iters = 0
            scope.cur_gauges = {}
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                scope.update_progress_bar()
            )

            scope.go_mainboard = ($event)->
                $state.go("main.dashboard")

            scope.update_progress_bar = () ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.BASE_GET_GAUGE_INFO
                        hidden: true
                    }
                ).then(
                    (xml) =>
                        cur_pb = []
                        $(xml).find("gauge_info gauge_element").each (idx, cur_g) ->
                            cur_g = $(cur_g)
                            idx = cur_g.attr("idx")
                            if idx of scope.cur_gauges
                                scope.cur_gauges[idx].info = cur_g.text()
                                scope.cur_gauges[idx].value = parseInt(cur_g.attr("value"))
                            else
                                scope.cur_gauges[idx] = {info : cur_g.text(), value : parseInt(cur_g.attr("value"))}
                            cur_pb.push(idx)
                        del_pbs = (cur_idx for cur_idx of scope.cur_gauges when cur_idx not in cur_pb)
                        for del_pb in del_pbs
                            delete scope.cur_gauges[del_pb]
                        #for cur_idx, value of $scope.cur_gauges
                        scope.num_gauges = cur_pb.length
                        if cur_pb.length or scope.progress_iters
                            if scope.progress_iters
                                scope.progress_iters--
                            $timeout(scope.update_progress_bar, 1000)
                        if not cur_pb.length
                            icswMenuProgressService.set_rebuilding(0)
                )
    }
]).directive("icswBackgroundJobInfo",
[
    "$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "$timeout", "$state",
    "$rootScope", "ICSW_SIGNALS",
(
    $templateCache, ICSW_URLS, icswSimpleAjaxCall, $timeout, $state,
    $rootScope, ICSW_SIGNALS
) ->
    @backg_timer = null
    return {
        restrict: "EA"
        template: '<button type="button" ng-click="redirect_to_bgj_info()" title="number of background jobs"></button>'
        replace: true
        link: (scope, el, attrs) ->
            scope.background_jobs = 0
            el.hide()
            scope.redirect_to_bgj_info = () ->
                if scope.has_menu_permission('background_job.show_background')
                    $state.go("main.backgroundinfo")
                return false
            el.removeClass()
            el.addClass("btn btn-xs btn-warning")
            get_background_job_class = () ->
                if scope.background_jobs < 4
                    return "btn btn-xs btn-warning"
                else
                    return "btn btn-xs btn-danger"
            reload = () ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.MAIN_GET_NUMBER_OF_BACKGROUND_JOBS
                        dataType: "json"
                    }
                ).then(
                    (data) ->
                        scope.background_jobs = data["background_jobs"]
                        if scope.background_jobs
                            el.show()
                            el.removeClass()
                            el.addClass(get_background_job_class())
                            el.text(scope.background_jobs)
                        else
                            el.hide()
                )
                # reload every 30 seconds
                @backg_timer = $timeout(reload, 30000)
            reload()
            $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
                if @backg_timer?
                    $timeout.cancel(@backg_timer)
            )
    }
]).factory("icswReactMenuFactory",
[
    "icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI",
    "icswMenuProgressService", "$state", "icswRouteHelper",
(
    icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall, blockUI,
    icswMenuProgressService, $state, icswRouteHelper,
) ->
    # console.log icswAcessLevelService
    {input, ul, li, a, span, h4, div, p, strong} = React.DOM
    react_dom = ReactDOM
    menu_line = React.createClass(
        displayName: "menuline"
        render: () ->
            state = @props.state
            data = state.icswData
            #console.log "D=", data
            a_attrs = {
                key: "a"
                className: "icswMenuColor"
            }
            if data.menuEntry.href?
                a_attrs.href = data.menuEntry.href
            else
                a_attrs.href = data.menuEntry.sref
            if data.menuEntry.labelClass
                return li(
                    {key: "li"}
                    [
                        a(
                            a_attrs
                            [
                                span(
                                    {className: "label #{data.menuEntry.labelClass}", key: "spanl"}
                                    [
                                        span(
                                            {className: "fa #{data.menuEntry.icon} fa_icsw", key: "span"}
                                        )
                                    ]
                                )
                                " #{data.menuEntry.name}"
                            ]
                        )
                    ]
                )
            else
                return li(
                    {key: "li"}
                    [
                        a(
                            a_attrs
                            [
                                span(
                                    {className: "fa #{data.menuEntry.icon} fa_icsw", key: "span"}
                                )
                                " #{data.menuEntry.name}"
                            ]
                        )
                    ]
                )
    )
    menu_header = React.createClass(
        displayName: "menuheader"
        getDefaultProps: () ->
        render: () ->
            items_added = 0
            items_per_column = {}

            for state in @props.entries
                data = state.icswData

                if data.menuEntry.column?
                    items_per_column[data.menuEntry.column] =
                    [
                        li(
                            {
                                key: data.key + data.menuEntry.columnname + "_li"
                            }
                            [
                                p(
                                    {
                                        key: data.key + data.menuEntry.columnname + "_p"
                                    }
                                    [
                                        strong(
                                            {
                                                key: data.key + data.menuEntry.columnname + "_strong"
                                            }
                                            [
                                              data.menuEntry.columnname
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                else
                    items_per_column[0] = []

            for state in @props.entries
                data = state.icswData
                _key = data.key
                if data.menuEntry.isHidden? and data.menuEntry.isHidden
                    continue
                if data.$$allowed
                    column = 0
                    if data.menuEntry.column?
                        column = data.menuEntry.column

                    if angular.isFunction(state.name)
                        items_per_column[column].push(
                            React.createElement(state.name, {key: _key})
                        )
                        items_added += 1
                    else
                        items_per_column[column].push(
                            React.createElement(menu_line, {key: _key, state: state})
                        )
                        items_added += 1

            if items_added > 0
                state = @props.state
                header = state.icswData.menuHeader
                key= "mh_#{state.icswData.key}"

                ul_items = []

                columns = 0

                for column in Object.keys(items_per_column)
                    columns += 1

                for column in Object.keys(items_per_column)
                    items = items_per_column[column]

                    ul_item = ul(
                        {
                            key: key + column + "_ul"
                            className: "col-sm-" + 12 / columns + " list-unstyled"
                        }
                        items
                    )

                    ul_items.push(ul_item)

                _res = li(
                    {
                        key: "menu_" + key
                    }
                    [
                        a(
                            {
                                className: "cursorpointer dropdown-toggle"
                                # dataToggle is not working
                                "data-toggle": "dropdown"
                                key: "menu.head_" + key
                            }
                            [
                                span(
                                    {
                                        className: "fa #{header.icon} fa-lg fa_top"
                                        key: "span_" + key
                                    }
                                )
                                span(
                                    {
                                        key: "text_" + key
                                    }
                                    header.name
                                )
                            ]
                        )
                        ul(
                            {
                                key: key + "dropdown-menu_ul"
                                className: "dropdown-menu col-sm-5"
                            }
                            li(
                                {
                                }
                                [

                                    div(
                                        {
                                            key: key + "yamm-content_div"
                                            className: "yamm-content"
                                        }
                                        [
                                            div(
                                                {
                                                    key: key + "row_div"
                                                    className: "row"
                                                }
                                                ul_items
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    ]
                )
            else
                _res = null
            return _res
    )
    
    class MenuHeader
        constructor: (@state) ->
            @entries = []

        add_entry: (entry) =>
            @entries.push(entry)

        get_react: () =>
            # order entries
            return React.createElement(
                menu_header
                {
                    key: @state.icswData.key + "_top"
                    state: @state
                    entries: _.orderBy(@entries, "icswData.menuEntry.ordering")
                }
            )
    
    menu_comp = React.createClass(
        displayName: "menubar"

        update_dimensions: () ->
            @setState(
                {
                    width: $(window).width()
                    height: $(window).height()
                }
            )
        getInitialState: () ->
            return {
                counter: 0
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        componentWillMount: () ->
            # register eventhandler
            $(window).on("resize", @update_dimensions)
    
        componentWillUnmount: () ->
            # remove eventhandler
            $(window).off("resize", @update_dimensions)
    
        render: () ->
            _menu_struct = icswRouteHelper.get_struct()
            # may not be valid
            # console.log "mv", _menu_struct.valid
            if _menu_struct.valid
                menus = (new MenuHeader(state) for state in _menu_struct.menu_header_states)
                # console.log menus.length
                for state in _menu_struct.menu_states
                    # find menu
                    menu = (entry for entry in menus when entry.state.icswData.menuHeader.key == state.icswData.menuEntry.menukey)
                    if menu.length
                        menu[0].add_entry(state)
                    else
                        console.error("No menu with name #{state.icswData.menuEntry.menukey} found (#{state.icswData.pageTitle})")
                        console.log "Menus known:", (entry.state.icswData.menuHeader.key for entry in menus).join(", ")

            else
                menus = []

            if menus.length
                _res =
                    div(
                        {
                            className: "yamm"
                        }
                        [
                            ul(
                                {
                                    key: "topmenu"
                                    className: "nav navbar-nav"
                                }
                                (
                                    menu.get_react() for menu in _.orderBy(menus, "state.icswData.menuHeader.ordering")
                                )
                            )
                        ]
                    )
            else
                _res = null
            return _res
    )
    return menu_comp
]).directive("icswMenuDirective",
[
    "icswReactMenuFactory", "icswAcessLevelService", "icswMenuProgressService",
    "$rootScope", "ICSW_SIGNALS",
(
    icswReactMenuFactory, icswAcessLevelService, icswMenuProgressService,
    $rootScope, ICSW_SIGNALS
) ->
    return {
        restrict: "EA"
        replace: true
        scope: true
        link: (scope, el, attrs) ->
            _element = ReactDOM.render(
                React.createElement(
                    icswReactMenuFactory
                )
                el[0]
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_CHANGED"), (event) ->
                _element.force_redraw()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                console.log "mps", settings
                # _render()
            )
    }
]).directive("icswLayoutSubMenubar",
[
    "$templateCache", "icswUserService", "$rootScope", "$compile", "ICSW_SIGNALS",
    "$state",
(
    $templateCache, icswUserService, $rootScope, $compile, ICSW_SIGNALS,
    $state,
) ->
    return {
        restrict: "E"
        controller: "icswLayoutSubMenubarCtrl"
        template: $templateCache.get("icsw.layout.submenubar")
        scope: true
    }
]).controller("icswLayoutSubMenubarCtrl"
[
    "$scope", "icswLayoutSelectionDialogService", "$rootScope", "icswBreadcrumbs",
    "icswUserService", "$state", "$q", "icswDeviceTreeService", "ICSW_SIGNALS",
    "icswDispatcherSettingTreeService", "icswAssetPackageTreeService",
    "icswActiveSelectionService",
(
    $scope, icswLayoutSelectionDialogService, $rootScope, icswBreadcrumbs,
    icswUserService, $state, $q, icswDeviceTreeService, ICSW_SIGNALS
    icswDispatcherSettingTreeService, icswAssetPackageTreeService,
    icswActiveSelectionService
) ->
    $scope.struct = {
        current_user: undefined
        # any devices / groups selected
        any_selected: false
        # selection string
        select_txt: "---"
        # breadcrumb list
        bc_list: []
        # device tree is valid
        tree_valid: false
        # selection
        selection_list: []
        # emitted selection
        em_selection_list: []
        # emitted and selected list in sync
        in_sync: false
        # selection button title
        title_str: ""
    }

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get().user
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        $scope.struct.current_user = undefined
    )

    $scope.device_selection = ($event) ->
        icswLayoutSelectionDialogService.quick_dialog("right")

    $rootScope.$on(ICSW_SIGNALS("ICSW_BREADCRUMBS_CHANGED"), (event, bc_list) ->
        $scope.struct.bc_list.length = 0
        for entry in bc_list
            $scope.struct.bc_list.push(entry)
    )

    _fetch_selection_list = () ->
        $scope.struct.selection_list.length = 0
        for entry in icswActiveSelectionService.current().get_devsel_list()
            $scope.struct.selection_list.push(entry)

    _fetch_em_selection_list = () ->
        $scope.struct.em_selection_list.length = 0
        for entry in icswActiveSelectionService.current().get_devsel_list()
            $scope.struct.em_selection_list.push(entry)

    $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), (event, tree) =>
        $scope.struct.tree_valid = true
        _fetch_selection_list()
        _fetch_em_selection_list()
        _update_selection_txt()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_SELECTION_CHANGED"), (event) ->
        if $scope.struct.tree_valid
            _fetch_selection_list()
            _update_selection_txt()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"), (event) ->
        if $scope.struct.tree_valid
            _fetch_em_selection_list()
            _update_selection_txt()
    )

    _get_list = (in_sel) ->
        if in_sel.length
            sel_groups = in_sel[3].length
            sel_devices = in_sel[1].length
        else
            sel_groups = 0
            sel_devices = 0
        group_plural = if sel_groups == 1 then "group" else "groups"
        device_plural = if sel_devices == 1 then "device" else "devices"
        group_plural = if sel_groups == 1 then "group" else "groups"
        device_plural = if sel_devices == 1 then "device" else "devices"
        _list = []
        if sel_devices
            _list.push("#{sel_devices} #{device_plural}")
        if sel_groups
            _list.push("#{sel_groups} #{group_plural}")
        return _list

    _update_selection_txt = () ->
        _em_list = _get_list($scope.struct.em_selection_list)
        _list = _get_list($scope.struct.selection_list)
        $scope.struct.in_sync = _.isEqual($scope.struct.selection_list, $scope.struct.em_selection_list)
        if $scope.struct.in_sync
            $scope.struct.title_str = "Current selection, in sync"
        else
            $scope.struct.title_str = "Current selection, not in sync}"
        $scope.struct.any_selected = if _em_list.length > 0 then true else false
        $scope.struct.select_txt = _em_list.join(", ")

    $scope.select_all = ($event) ->
        icswActiveSelectionService.current().select_all()
        icswActiveSelectionService.send_selection(icswActiveSelectionService.current())

    $scope.activate_state = (entry) ->
        $state.go(entry.sref, null, {icswRegister: false})

]).service('icswBreadcrumbs',
[
    "$state", "icswRouteHelper", "$rootScope", "ICSW_SIGNALS",
(
    $state, icswRouteHelper, $rootScope, ICSW_SIGNALS,
) ->
    # list of breadcrumbs
    bc_list = []

    add_state = (state) ->
        if state.icswData?
            _add = false
            if state.icswData.menuEntry? and state.icswData.menuEntry.sref?
                _add = true
                _add_struct = {
                    icon: state.icswData.menuEntry.icon
                    sref: state.name
                    name: state.icswData.menuEntry.name
                    has_devsel: state.icswData.hasDevselFunc
                }
            else if state.icswData.pageTitle?
                _add = true
                _add_struct = {
                    icon: ""
                    sref: state.name
                    name: state.icswData.pageTitle
                    has_devsel: state.icswData.hasDevselFunc
                }
            if _add
                _.remove(bc_list, (entry) -> return entry.sref == _add_struct.sref)
                # state with menu entry
                bc_list.push(_add_struct)
                if bc_list.length > 6
                    bc_list = bc_list.slice(1)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_BREADCRUMBS_CHANGED"), bc_list)

            # console.log bc_list.length, (entry.name for entry in bc_list)

    return {
        add_state: (state) ->
            add_state(state)
    }
])
