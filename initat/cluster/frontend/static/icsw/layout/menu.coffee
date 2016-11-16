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
    "$scope", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswAccessLevelService",
    "initProduct", "icswLayoutSelectionDialogService", "icswActiveSelectionService",
    "$q", "icswUserService", "blockUI", "$state", "icswSystemLicenseDataService",
    "$rootScope", "ICSW_SIGNALS", "$timeout", "icswOverallStyle",
(
    $scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswAccessLevelService,
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
    icswAccessLevelService.install($scope)

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

    # load license tree
    icswSystemLicenseDataService.load($scope.$id).then(
        (data) ->
    )

    # $scope.device_selection = () ->
    #    console.log "SHOW_DIALOG"
    #     icswLayoutSelectionDialogService.show_dialog()

    # apply selected theme if theme is set in session
]).service("icswMenuSettings",
[
    "$rootScope", "ICSW_SIGNALS",
(
    $rootScope, ICSW_SIGNALS,
) ->
    SETTINGS = {
        # menu help setting
        menu_help: false
        # themes valid
        themes_valid: false
        # user is logged in
        user_loggedin: false
    }

    _get_menu_help = () ->
        return SETTINGS.menu_help

    _set_menu_help = (flag) ->
        SETTINGS.menu_help = flag
        _redraw()
        return _get_menu_help()

    _get_themes_valid = () ->
        return SETTINGS.themes_valid

    _set_themes_valid = () ->
        SETTINGS.themes_valid = true
        _redraw()
        return _get_themes_valid()

    _redraw = () ->
        $rootScope.$emit(ICSW_SIGNALS("ICSW_MENU_SETTINGS_CHANGED"))

    $rootScope.$on(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_CHANGED"), (event) ->
        _redraw()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
        console.log "mps", settings
        _redraw()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"), () ->
        _redraw()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        SETTINGS.user_loggedin = true
        _redraw()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        SETTINGS.user_loggedin = true
        _redraw()
    )

    return {
        set_menu_help: (state) ->
            return _set_menu_help(state)

        get_menu_help: () ->
            return _get_menu_help()

        set_themes_valid: () ->
            return _set_themes_valid()

        get_themes_valid: () ->
            return _get_themes_valid()

        get_settings: () ->
            return SETTINGS
    }

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
        scope: true
        link: (scope, el, attrs) ->
            scope.initProduct = initProduct
            scope.overall_style = icswOverallStyle.get()

            $rootScope.$on(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"), () ->
                scope.overall_style = icswOverallStyle.get()
            )

            scope.go_mainboard = ($event)->
                $state.go("main.dashboard")

    }
]).factory("icswReactMenuBarFactory",
[
    "icswAccessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI",
    "icswMenuProgressService", "$state", "icswRouteHelper", "icswTools",
    "icswUserService", "icswOverallStyle", "icswReactMenuFactory",
(
    icswAccessLevelService, ICSW_URLS, icswSimpleAjaxCall, blockUI,
    icswMenuProgressService, $state, icswRouteHelper, icswTools,
    icswUserService, icswOverallStyle, icswReactMenuFactory,
) ->
    {ul, li, a, span, div, p, strong, h3, hr} = React.DOM
    return React.createClass(
        displayName: "icswMenuBar"
        propTypes:
            side: React.PropTypes.string

        getInitialState: () ->
            return {
                counter: 0
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            _menu_struct = icswRouteHelper.get_struct()
            menus = (entry for entry in _menu_struct.menu_node.entries when entry.data.side == @props.side)
            if menus.length
                _res = div(
                    {
                        className: "yamm"
                    }
                    ul(
                        {
                            className: "nav navbar-nav navbar-#{@props.side} #{icswOverallStyle.get()}"
                        }
                        (
                            React.createElement(
                                icswReactMenuFactory
                                {
                                    key: menu.$$menu_key
                                    menu: menu
                                }
                            ) for menu in menus
                        )
                    )
                )
            else
                _res = null
            return _res
    )
]).config(["$translateProvider", ($translateProvider) ->
    $translateProvider.uniformLanguageTag('bcp47').determinePreferredLanguage()
]).factory("icswReactMenuFactory",
[
    "icswAccessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI",
    "icswMenuProgressService", "$state", "icswRouteHelper", "icswTools",
    "icswUserService", "icswOverallStyle", "icswLanguageTool", "icswMenuSettings",
(
    icswAccessLevelService, ICSW_URLS, icswSimpleAjaxCall, blockUI,
    icswMenuProgressService, $state, icswRouteHelper, icswTools,
    icswUserService, icswOverallStyle, icswLanguageTool, icswMenuSettings,
) ->
    {ul, li, a, span, div, p, strong, h3, hr} = React.DOM

    # default language
    def_lang = icswLanguageTool.get_lang()

    menu_line = React.createClass(
        propTypes: {
            state: React.PropTypes.object
        }

        displayName: "icswMenuEntry"

        render: () ->
            state = @props.state
            data = state.icswData
            a_attrs = {
                key: "a"
            }
            _a_classes = []
            if data.$$allowed
                _a_classes.push("icswMenuColor")
                if data.$$menuEntry.href?
                    a_attrs.href = data.$$menuEntry.href
                else
                    a_attrs.href = data.$$menuEntry.sref
                _mis_span = null
            else
                _a_classes.push("icswMenuDeact")
                a_attrs.pointerEvents = "none"
                a_attrs.title = "Not available: Missing #{data.$$missing_info}"
                _mis_span = span(
                    {
                        className: "label label-default"
                        key: "mis"
                    }
                    data.$$missing_short.join("")
                )
            if data.$$menuEntry.entryClass?
                _a_classes.push(data.$$menuEntry.entryClass)
            if data.$$menuEntry.title?
                a_attrs.title = data.$$menuEntry.title
            if data.description[def_lang]?
                _info_text = data.description[def_lang].text
            else
                _info_text = "Example text for this entry wwwwww wwww qweqw pqow oiudf oijrl woe oiu qw qw f et ze wol qwoeiuqwoieu ln vldeou9z oqaweeh r"
            a_attrs.className = _a_classes.join(" ")
            if icswMenuSettings.get_menu_help()
                help_p = p(
                    {key: "descr"} # , className: "menu-help-text"}
                    _info_text
                    if data.$$allowed then "ok" else "not ok"
                )
            else
                help_p = null
            return li(
                {key: "li"}
                a(
                    a_attrs
                    span(
                        {className: "fa #{data.$$menuEntry.icon} fa_icsw", key: "span"}
                    )
                    " #{data.$$menuEntry.name} "
                    _mis_span
                )
                help_p
            )
    )
    return React.createClass(
        propTypes: {
            menu: React.PropTypes.object
        }
        displayName: "icswMenuHeader"

        render: () ->
            if not icswMenuSettings.get_themes_valid()
                return null
            overall_style = icswOverallStyle.get()
            items_added = 0
            _items = []
            for sg_state in @props.menu.entries
                sg_data = sg_state.data
                # if sg_state.data.hidden?
                #    console.log "***", sg_state.data
                #    _hidden = sg_state.data.hidden
                # else
                #    _hidden = false
                # if not _hidden
                if overall_style != "condensed"
                    _head = li(
                        {
                            key: "#{sg_state.$$menu_key}_li"
                        }
                        p({key: "p"}, strong({key: "strong"}, sg_data.name))
                    )
                else
                    _head = li(
                        {
                            key: "#{sg_state.$$menu_key}_li"
                        }
                        h3({key: "h3"}, sg_data.name)
                    )
                _head_added = false
                for menu_entry in sg_state.entries
                    state = menu_entry.data
                    data = state.icswData
                    _key = menu_entry.$$menu_key
                    # if data.$$menuEntry.isHidden? and data.$$menuEntry.isHidden
                    #     continue
                    if data.$$allowed or true
                        if not _head_added
                            # only add head when first entry is added
                            _head_added = true
                            _items.push(_head)
                        items_added += 1
                        _items.push(
                            React.createElement(menu_line, {key: _key, state: state})
                        )

            if items_added > 0
                state = @props.menu.data
                menu_name = state.name
                menu_title = ""
                _force_icon = false
                if menu_name == "$$USER_INFO"
                    if overall_style == "normal"
                        # ...
                        menu_name = ""
                        _force_icon = true
                    else
                        menu_name = "---"
                        _user = icswUserService.get()
                        # user may not be defined (early draw of menu)
                        if _user?
                            _user = _user.user
                            if _user?
                                menu_name = _user.login
                                menu_title = _user.info
                                if _user.login != _user.login_name
                                    menu_name = "#{menu_name} (via alias #{_user.login_name})"
                            # n title="{{ struct.current_user.full_name }}">{{ struct.current_user.login }}</span>
                            # uct.current_user.login != struct.current_user.login_name"> (via alias {{ struct.current_user.login_name }})</span>
                # header = state.icswData.menuHeader
                key= @props.menu.$$menu_key

                _num_items = _items.length
                # get number of rows
                if _num_items > 12
                    _num_cols = 3
                    _col_style = "col-sm-4"
                else if _num_items > 6
                    _num_cols = 2
                    _col_style = "col-sm-6"
                else
                    _num_cols = 1
                    _col_style = "col-sm-12"
                # entries per col
                _max_per_col = parseInt(_num_items / _num_cols) + 1

                # balance items

                ul_items = []

                add_stream = (stream) ->
                    if stream.length
                        ul_items.push(
                            ul(
                                {
                                    key: "#{key}_c#{ul_items.length}_ul"
                                    className: "#{_col_style} list-unstyled"
                                }
                                stream
                            )
                        )

                _count = 0
                _item_stream = []
                for item in _items
                    if _count == 0
                        add_stream(_item_stream)
                        _item_stream = []
                    if item.type == "li"
                        # element is a header
                        if _count + 1 == _max_per_col
                            # cannot be last in stream
                            add_stream(_item_stream)
                            _item_stream = []
                            _count = 0
                        else if _count
                            # if not first in stream add spacer
                            _item_stream.push(hr({key: "sp#{_count}"}))
                    _item_stream.push(item)
                    _count++
                    if _count == _max_per_col
                        _count = 0
                if _item_stream.length
                    add_stream(_item_stream)

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
                            div(
                                {
                                    key: "yamm-content-div"
                                    className: "yamm-content container-fluid"
                                }
                                div(
                                    {
                                        key:"row_div"
                                        className: "row"
                                    }
                                    ul_items
                                )
                            )
                        )
                    )
                )
            else
                _res = null
            return _res
    )
]).directive("icswMenu",
[
    "icswReactMenuBarFactory", "icswAccessLevelService", "icswMenuProgressService",
    "$rootScope", "ICSW_SIGNALS",
(
    icswReactMenuBarFactory, icswAccessLevelService, icswMenuProgressService,
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
                    icswReactMenuBarFactory
                    {
                        side: scope.side
                    }
                )
                el[0]
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_SETTINGS_CHANGED"), (event) ->
                _element.force_redraw()
            )
    }
]).service("icswReactBackgroundJobInfoFactory",
[
    "$q", "$timeout", "$rootScope", "ICSW_SIGNALS", "icswSimpleAjaxCall",
    "$state", "ICSW_URLS", "icswMenuSettings",
(
    $q, $timeout, $rootScope, ICSW_SIGNALS, icswSimpleAjaxCall,
    $state, ICSW_URLS, icswMenuSettings,
) ->
    {ul, li, div, a, button, span} = React.DOM
    return React.createClass(
        displayName: "icswBackgroundJobInfo"

        getInitialState: () ->
            _reload = () =>
                if @backg_timer
                    $timeout.cancel(@back_timer)
                @backg_timer = $timeout(_reload, 30000)
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.MAIN_GET_NUMBER_OF_BACKGROUND_JOBS
                        dataType: "json"
                    }
                ).then(
                    (data) =>
                        @setState({num_jobs: data["background_jobs"]})
                )

            if not icswMenuSettings.get_settings().user_loggedin and @backg_timer?
                $timeout.cancel(@backg_timer)

            if icswMenuSettings.get_settings().user_loggedin and not @backg_timer?
                _reload()

            return {
                num_jobs: 0
            }
        componentWillMount: () =>
            @backg_timer = null

        render: () ->
            # if @state.num_jobs == 0
            #     return null
            if @state.num_jobs > 4
                _class = "label label-danger cursorpointer fa wizardbutton"
            else
                _class = "label label-warning cursorpointer fa wizardbutton"
                # _class = "btn btn-xs btn-warning"
            return li(
                {}
                a(
                    {
                        className: "task-wizard"
                    }
                    span(
                        {
                            # type: "button"
                            title: "Number of Background Jobs"
                            className: _class
                            # style: {paddingTop: "0px"}
                            onClick: (event) =>
                                $state.go("main.backgroundinfo")
                        }
                        @state.num_jobs
                    )
                )
            )

    )
]).service("icswReactOpenIssuesFactory",
[
    "$q", "$timeout", "$rootScope", "ICSW_SIGNALS", "icswSimpleAjaxCall",
    "$state", "ICSW_URLS", "SetupProgressHelper"
(
    $q, $timeout, $rootScope, ICSW_SIGNALS, icswSimpleAjaxCall,
    $state, ICSW_URLS, SetupProgressHelper
) ->
    {ul, li, div, a, button, p, strong, span, img} = React.DOM
    return React.createClass(
        displayName: "icswOpenIssuesInfo"

        getInitialState: () ->
            _reload = () =>
                SetupProgressHelper.unfulfilled_setup_tasks().then(
                    (unfulfilled_setup_tasks) =>
                        @setState({num_unfulfilled: unfulfilled_setup_tasks})
                )

            $rootScope.$on(ICSW_SIGNALS("ICSW_OPEN_SETUP_TASKS_CHANGED"), () =>
                _reload()
            )

            _reload()

            return {
                num_unfulfilled: 0
            }

        render: () ->
            if @state.num_unfulfilled > -2  # DEBUG set value 0
                return li(
                    {}
                    button(
                        {
                            type: "button"
                            key: "p"
                            className: "btn btn-default btn-xs menu-openissues"
                            onClick: (event) ->
                                $state.go("main.setupprogress")
                                event.preventDefault()
                        }
                        img(
                            {
                                src: ICSW_URLS.STATIC_URL + "/openissues-danger.svg"
                                title: "Open Issues: #{@state.num_unfulfilled}"
                                height: 23
                            }
                        )

                    )
                )
            else
                return null
    )
]).service("icswReactRightMenuFactory",
[
    "$q", "icswReactMenuFactory", "icswRouteHelper", "icswTaskOverviewReact", "icswReactOpenIssuesFactory"
    "icswReactOvaDisplayFactory", "icswOverallStyle", "icswReactBackgroundJobInfoFactory", "icswMenuSettings",
(
    $q, icswReactMenuFactory, icswRouteHelper, icswTaskOverviewReact, icswReactOpenIssuesFactory
    icswReactOvaDisplayFactory, icswOverallStyle, icswReactBackgroundJobInfoFactory, icswMenuSettings,
) ->
    {ul, li, a, span, div, p, strong, h3, hr} = React.DOM
    return React.createClass(
        displayName: "icswRighMenuBar"
        getInitialState: () ->
            return {
                counter: 0
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            if not icswMenuSettings.get_themes_valid()
                return null
            _menu_struct = icswRouteHelper.get_struct()
            menus = (entry for entry in _menu_struct.menu_node.entries when entry.data.side == "right")
            return div(
                {
                    className: "yamm"
                }
                ul(
                    {
                        className: "nav navbar-nav navbar-right #{icswOverallStyle.get()}"
                    }
                    React.createElement(
                        icswReactOpenIssuesFactory
                        {
                            key: "openIssues"
                        }
                    )
                    React.createElement(
                        icswTaskOverviewReact
                        {
                            key: "process"
                        }
                    )
                    React.createElement(
                        icswReactBackgroundJobInfoFactory
                        {
                            key: "bg"
                        }
                    )
                    React.createElement(
                        icswReactOvaDisplayFactory
                        {
                            key: "ova"
                        }
                    )
                    (
                        React.createElement(
                            icswReactMenuFactory
                            {
                                key: menu.$$menu_key
                                menu: menu
                            }
                        ) for menu in menus
                    )
                )
            )
    )
]).directive("icswRightMenu",
[
    "icswReactRightMenuFactory", "icswAccessLevelService", "icswMenuProgressService",
    "$rootScope", "ICSW_SIGNALS",
(
    icswReactRightMenuFactory, icswAccessLevelService, icswMenuProgressService,
    $rootScope, ICSW_SIGNALS
) ->
    return {
        restrict: "EA"
        replace: true
        link: (scope, el, attrs) ->
            _element = ReactDOM.render(
                React.createElement(
                    icswReactRightMenuFactory
                    {}
                )
                el[0]
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_SETTINGS_CHANGED"), (event) ->
                _element.force_redraw()
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
    "icswActiveSelectionService", "icswMenuPath", "icswOverallStyle",
(
    $scope, icswLayoutSelectionDialogService, $rootScope, icswBreadcrumbs,
    icswUserService, $state, $q, icswDeviceTreeService, ICSW_SIGNALS
    icswDispatcherSettingTreeService, icswAssetPackageTreeService,
    icswActiveSelectionService, icswMenuPath, icswOverallStyle,
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
        # overall style
        overall_style: icswOverallStyle.get()
    }

    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"), () ->
        $scope.struct.overall_style = icswOverallStyle.get()
    )

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
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_STATE_CHANGED"), () ->
        $scope.struct.menupath = icswMenuPath.generate_path()
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
            console.warn "empty selection list"
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
    home_link = {
        name: "Home"
        statename: "main.dashboard"
    }

    # no longer needed, just kept for reference
    setup_lut = () ->
        menu_headers = (entry for entry in icswRouteHelper.get_struct().menu_node.entries)
        for header in menu_headers
            icswheader = header.data
            for headersub in header.entries
                icswheadersub = headersub.data
                entryname = if icswheader.name == "$$USER_INFO" then "Usermenu" else icswheader.name
                header_lut[headersub.$$menu_key] = [
                    {
                        icon: icswheader.icon
                        name: entryname
                    }
                ]
                if icswheadersub.hidden? and icswheadersub.hidden
                    true
                else
                    header_lut[headersub.$$menu_key].push(
                        {
                            icon: ""
                            name: icswheadersub.name
                        }
                    )
        return  # keep return

    generate_path = () ->
        # generate path
        _start = $state.$current.$$simpleTreeNode
        if _start?
            _path = []
            while true
                # walk upwards
                _path.push(_start)
                if _start.level == 0
                    break
                _start = _start.parent
            _.reverse(_path)
        else
            # dummy path for dashboard
            _path = [{level: 0}]
        ret_path = []
        for entry in _path
            if entry.level == 0
                # root
                ret_path.push(home_link)
            else if entry.level == 1
                # menu
                entryname = if entry.data.name == "$$USER_INFO" then "Usermenu" else entry.data.name
                ret_path.push({name: entryname, icon: ""})
            else if entry.level == 2
                # subgroup
                ret_path.push({name: entry.data.name, icon: ""})
            else
                # menu entry
                _curr = entry.data.icswData.$$menuEntry
                curr_entry = {
                    name: _curr.name
                    icon: _curr.icon
                }
                ret_path.push(curr_entry)
        return ret_path

    return {
        generate_path: () ->
            generate_path()
    }
])
