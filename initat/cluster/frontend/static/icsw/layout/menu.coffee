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
    "$rootScope", "ICSW_SIGNALS", "$timeout", "icswOverallStyle",
(
    $scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswAcessLevelService,
    initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService,
    $q, icswUserService, blockUI, $state, icswSystemLicenseDataService,
    $rootScope, ICSW_SIGNALS, $timeout, icswOverallStyle,
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
        # overall style
        overall_style: icswOverallStyle.get()
    }
    $scope.HANDBOOK_PDF_PRESENT = false
    $scope.HANDBOOK_CHUNKS_PRESENT = false
    $scope.HANDBOOK_PAGE = "---"
    icswAcessLevelService.install($scope)

    # typeahead functions
    $scope.get_selections = (view_value) ->
        # console.log "gs", view_value
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
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.MAIN_GET_OVERALL_STYLE
                    dataType: "json"
                }
            )
        ]
    ).then(
        (data) ->
            $scope.HANDBOOK_PDF_PRESENT = data[0].HANDBOOK_PDF_PRESENT
            $scope.HANDBOOK_CHUNKS_PRESENT = data[0].HANDBOOK_CHUNKS_PRESENT
            icswOverallStyle.set(data[2].overall_style)
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get().user
        $scope.struct.focus_search = true
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        $scope.struct.current_user = undefined
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"), () ->
        $scope.struct.overall_style = icswOverallStyle.get()
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
    "$rootScope", "$state", "icswOverallStyle",
(
    $templateCache, ICSW_URLS, $timeout, icswSimpleAjaxCall, initProduct,
    icswMenuProgressService, icswLayoutSelectionDialogService, ICSW_SIGNALS,
    $rootScope, $state, icswOverallStyle,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar.progress")
        scope: {}
        link: (scope, el, attrs) ->
            scope.initProduct = initProduct
            scope.overall_style = icswOverallStyle.get()
            scope.num_gauges = 0
            scope.progress_iters = 0
            scope.cur_gauges = {}
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                scope.update_progress_bar()
            )

            $rootScope.$on(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"), () ->
                scope.overall_style = icswOverallStyle.get()
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
        template: '<button type="button" ng-click="redirect_to_bgj_info()" title="Number of Background Jobs" style="margin-top:27px;margin-left:15px;"></button>'
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
                    return "btn btn-xs btn-warning pull-right"
                else
                    return "btn btn-xs btn-danger pull-right"
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
            $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
                if @backg_timer?
                    $timeout.cancel(@backg_timer)
                reload()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
                if @backg_timer?
                    $timeout.cancel(@backg_timer)
            )
    }
]).factory("icswReactMenuFactory",
[
    "icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI",
    "icswMenuProgressService", "$state", "icswRouteHelper", "icswTools",
    "icswUserService", "icswOverallStyle",
(
    icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall, blockUI,
    icswMenuProgressService, $state, icswRouteHelper, icswTools,
    icswUserService, icswOverallStyle,
) ->
    # console.log icswAcessLevelService
    {ul, li, a, span, h4, div, p, strong, h3, i} = React.DOM
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
            if data.menuEntry.entryClass?
                a_attrs.className = "#{a_attrs.className} #{data.menuEntry.entryClass}"
            if data.menuEntry.title?
                a_attrs.title = data.menuEntry.title
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
            overall_style = icswOverallStyle.get()
            items_added = 0
            items_per_column = {}

            col_idx = -1
            for sg_state in @props.entries
                col_idx++
                sg_data = sg_state.data
                # console.log "d=", data
                items_per_column[col_idx] = []
                if sg_state.data.hidden?
                    _hidden = sg_state.data.hidden
                else
                    _hidden = false
                if not _hidden
                    if overall_style == "condensed"
                        items_per_column[col_idx].push(
                            li(
                                {
                                    key: "#{sg_data.key}_li"
                                }
                                h3({key: "h3"}, sg_data.name)
                            )
                        )
                    else
                        items_per_column[col_idx].push(
                            li(
                                {
                                    key: "#{sg_data.key}_li"
                                }
                                p({key: "p"}, strong({key: "strong"}, sg_data.name))
                            )
                        )

                for state in sg_data.entries
                    data = state.icswData
                    _key = data.key
                    if data.menuEntry.isHidden? and data.menuEntry.isHidden
                        continue
                    if data.$$allowed
                        items_added += 1
                        if angular.isFunction(state.name)
                            items_per_column[col_idx].push(
                                React.createElement(state.name, {key: _key})
                            )
                        else
                            items_per_column[col_idx].push(
                                React.createElement(menu_line, {key: _key, state: state})
                            )

            if items_added > 0
                state = @props
                menu_name = state.name
                menu_title = ""
                _force_icon = false
                if menu_name == "$$USER_INFO"
                    if overall_style == "normal"
                        # ...
                        menu_name = ""
                        _force_icon = true
                    else
                        _user = icswUserService.get().user
                        if _user?
                            menu_name = _user.login
                            menu_title = _user.info
                            if _user.login != _user.login_name
                                menu_name = "#{menu_name} (via alias #{_user.login_name})"
                            # n title="{{ struct.current_user.full_name }}">{{ struct.current_user.login }}</span>
                            # uct.current_user.login != struct.current_user.login_name"> (via alias {{ struct.current_user.login_name }})</span>
                        else
                            menu_name = "---"
                # header = state.icswData.menuHeader
                key= "mh_#{state.menu_key}"

                ul_items = []

                columns = @props.entries.length

                for column, items of items_per_column

                    ul_item = ul(
                        {
                            key: key + column + "_ul"
                            className: "col-sm-" + 12 / columns + " list-unstyled"
                        }
                        items
                    )

                    ul_items.push(ul_item)
                _m_item = []
                if state.icon? and state.icon != "" and (overall_style == "condensed" or _force_icon)
                    _m_item.push span(
                        {
                            className: "fa #{state.icon} fa-lg"
                            #style: {paddingRight: "5px"}
                            key: "span"
                        }
                    )
                if menu_name? and menu_name != ""
                    _m_item.push span(
                        {
                            key: "text"
                        }
                        menu_name
                    )
                if overall_style == "normal"
                    _m_item.push span(
                        {
                            className: "caret"
                            key: "caretdown"
                        }
                    )
                if state.name == "$$USER_INFO" and overall_style == "normal"
                    # addon for admin submenu
                    _user = icswUserService.get()
                    if _user? and _user.user?
                        _user = _user.user
                        menu_subname = _user.login
                        if _user.login != _user.login_name
                            menu_subname = "#{menu_subname} (via alias #{_user.login_name})"
                        _m_item.push div(
                            {
                                key: "div_username"
                            }
                            menu_subname
                     )
                _res = li(
                    {
                        className: "dropdown"
                        key: "menu_#{key}"
                    }
                    [
                        a(
                            {
                                className: "cursorpointer dropdown-toggle"
                                # dataToggle is not working
                                "data-toggle": "dropdown"
                                key: "head"
                                title: menu_title
                            }
                            _m_item
                        )
                        ul(
                            {
                                key: "dropdown"
                                className: "dropdown-menu"
                            }
                            li(
                                {
                                    key: "li"
                                }
                                [

                                    div(
                                        {
                                            key: "yamm-content-div"
                                            className: "yamm-content container-fluid"
                                        }
                                        [
                                            div(
                                                {
                                                    key:"row_div"
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
    
    menu_comp = React.createClass(
        propTypes:
            side: React.PropTypes.string
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
            menus = (entry for entry in _menu_struct.menu_header_states when entry.data.side == @props.side)
            if menus.length
                _res = div(
                    {
                        className: "yamm"
                    }
                    [
                        ul(
                            {
                                key: "topmenu"
                                className: "nav navbar-nav navbar-#{@props.side} #{icswOverallStyle.get()}"
                            }
                            (
                                menu.get_react(menu_header) for menu in menus
                            )
                        )
                    ]
                )
            else
                _res = null
            return _res
    )
    return menu_comp
]).directive("icswMenu",
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
        scope:
            side: "@icswMenuSide"
        link: (scope, el, attrs) ->
            _element = ReactDOM.render(
                React.createElement(
                    icswReactMenuFactory
                    {
                        side: scope.side
                    }
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
    "icswActiveSelectionService", "icswMenuPath",
(
    $scope, icswLayoutSelectionDialogService, $rootScope, icswBreadcrumbs,
    icswUserService, $state, $q, icswDeviceTreeService, ICSW_SIGNALS
    icswDispatcherSettingTreeService, icswAssetPackageTreeService,
    icswActiveSelectionService, icswMenuPath
) ->
    $scope.struct = {
        current_user: undefined
        # any devices / groups selected
        any_selected: false
        # selection string
        select_txt: "---"
        # breadcrumb list
        bc_list: []
        # current selection is in sync (coupled with a saved selection)
        sel_synced: false
        # negated sel_synced
        sel_unsynced: true
        # selection
        selection_list: []
        # emitted selection
        em_selection_list: []
        # emitted and selected list in sync
        in_sync: false
        # selection button title
        title_str: ""
        # info string for lock icon
        lock_info: ""
        # menu path
        menupath: []
    }
    menu_path = icswMenuPath
    menu_path.setup_lut()

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get().user
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        $scope.struct.current_user = undefined
        $scope.struct.selection_list.length = 0
        $scope.struct.em_selection_list.length = 0
    )

    $scope.device_selection = ($event) ->
        icswLayoutSelectionDialogService.quick_dialog("right", "Dd")

    $scope.device_selection_ss = ($event) ->
        icswLayoutSelectionDialogService.quick_dialog("right", "Ss")

    $rootScope.$on(ICSW_SIGNALS("ICSW_BREADCRUMBS_CHANGED"), (event, bc_list) ->
        $scope.struct.bc_list.length = 0
        for entry in bc_list
            $scope.struct.bc_list.push(entry)
        $scope.struct.menupath = menu_path.get_path()
    )

    _fetch_selection_list = (l_type) ->
        # list to handle, can be selection or em_selection (for emitted)
        _cur_sel = icswActiveSelectionService.current()
        # console.log "FeSeLi", l_type, _cur_sel.get_devsel_list()
        d_list = $scope.struct["#{l_type}_list"]
        d_list.length = 0
        for entry in _cur_sel.get_devsel_list()
            # store as copy of sorted list
            d_list.push((_val for _val in entry).sort())
        # also check sync state
        _update_sync_state()

    _update_sync_state = () ->
        _cur_sel = icswActiveSelectionService.current()
        $scope.struct.sel_synced = if _cur_sel.db_idx then true else false
        $scope.struct.sel_unsynced = ! $scope.struct.sel_synced
        if $scope.struct.sel_synced
            $scope.struct.lock_info = "In sync with saved selection '#{_cur_sel.db_obj.name}'"
        else
            $scope.struct.lock_info = "Not in sync with a saved selection"
        _update_selection_txt()

    # wait for domain_tree_loaded save flags
    $rootScope.$on(ICSW_SIGNALS("ICSW_SELECTION_CHANGED_DTL"), (event) ->
        _fetch_selection_list("selection")
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_SEL_SYNC_STATE_CHANGED_DTL"), (event) ->
        _update_sync_state()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION_DTL"), (event) ->
        _fetch_selection_list("em_selection")
    )

    _get_list = (in_sel) ->
        if in_sel.length
            sel_groups = in_sel[3].length
            sel_devices = in_sel[1].length
        else
            console.error "empty selection list"
            sel_groups = 0
            sel_devices = 0
        group_plural = if sel_groups == 1 then "Group" else "Groups"
        device_plural = if sel_devices == 1 then "Device" else "Devices"
        _list = []
        if sel_devices
            _list.push("#{sel_devices} #{device_plural}")
        if sel_groups
            _list.push("#{sel_groups} #{group_plural}")
        return _list

    _update_selection_txt = () ->
        _em_list = _get_list($scope.struct.em_selection_list)
        _list = _get_list($scope.struct.selection_list)
        # console.log $scope.struct.em_selection_list.length, $scope.struct.selection_list.length
        # console.log $scope.struct.em_selection_list, $scope.struct.selection_list
        $scope.struct.in_sync = _.isEqual($scope.struct.selection_list, $scope.struct.em_selection_list)
        if $scope.struct.in_sync
            $scope.struct.title_str = "Current selection, in sync"
        else
            $scope.struct.title_str = "Current selection, not in sync"
        $scope.struct.any_selected = if _em_list.length > 0 then true else false
        $scope.struct.select_txt = _em_list.join(", ")

    $scope.select_all = ($event) ->
        icswActiveSelectionService.current().select_all().then(
            (done) ->
                icswActiveSelectionService.send_selection(icswActiveSelectionService.current())
        )

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
]).service('icswMenuPath',
[
    "$state", "icswRouteHelper",
(
    $state, icswRouteHelper
) ->
    header_lut = {}
    home_link = {name : "Home", statename : "main.dashboard" }

    setup_lut = () ->
        menu_headers = icswRouteHelper.get_struct().menu_header_states
        for header in menu_headers
            icswheader = header.data
            for icswheadersub in icswheader.entries
                entryname = if icswheader.name == "$$USER_INFO" then "Usermenu" else icswheader.name
                header_lut[icswheadersub.data.subgroupkey] = [
                    {
                        icon: icswheader.icon
                        name: entryname
                    }
                ]
                if icswheadersub.data.hidden? and icswheadersub.data.hidden
                    true
                else
                    header_lut[icswheadersub.data.subgroupkey].push(
                        {
                            icon: ""
                            name: icswheadersub.data.name
                        }
                    )
        return  # keep return

    generatePath = (state) ->
        _curr = state.$current.icswData.menuEntry
        curr_entry = {
            name: _curr.name
            icon: _curr.icon
        }
        ret_path = [home_link]
        if header_lut[_curr.subgroupkey]?
            ret_path = ret_path.concat header_lut[_curr.subgroupkey]
        if curr_entry.name?
            ret_path.push curr_entry
        ret_path

    return {
        get_path: () ->
            generatePath($state)
        setup_lut: () ->
            setup_lut()
    }
])
