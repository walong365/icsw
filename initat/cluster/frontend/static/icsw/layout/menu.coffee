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
    "$q", "icswUserService", "blockUI", "$state",
(
    $scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswAcessLevelService,
    initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService,
    $q, icswUserService, blockUI, $state,
) ->
    # init service types
    $scope.ICSW_URLS = ICSW_URLS
    $scope.initProduct = initProduct
    # flag: show navbar
    $scope.show_navbar = false
    $scope.CURRENT_USER = undefined
    $scope.HANDBOOK_PDF_PRESENT = false
    $scope.HANDBOOK_CHUNKS_PRESENT = false
    $scope.HANDBOOK_PAGE = "---"
    icswAcessLevelService.install($scope)
    $q.all(
        [
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.MAIN_GET_DOCU_INFO,
                    dataType: "json"
                }
            ),
            icswUserService.load(),
        ]
    ).then(
        (data) ->
            $scope.HANDBOOK_PDF_PRESENT = data[0].HANDBOOK_PDF_PRESENT
            $scope.HANDBOOK_CHUNKS_PRESENT = data[0].HANDBOOK_CHUNKS_PRESENT
    )
    $scope.get_progress_style = (obj) ->
        return {"width" : "#{obj.value}%"}
    $scope.redirect_to_init = () ->
        window.location = "http://www.initat.org"
        return false
    $scope.handbook_url = "/"
    $scope.handbook_url_valid = false
    $scope.$watch(
        "initProduct",
        (new_val) ->
            if new_val.name?
                $scope.handbook_url_valid = true
                $scope.handbook_url = "/cluster/doc/#{new_val.name.toLowerCase()}_handbook.pdf"
        true
    )
    # not needed, now handled in menubar-component
    # $scope.$watch(
    #    "size",
    #    (new_val) ->
    #        console.log "size=", new_val
    #        $rootScope.$emit(ICSW_SIGNALS("ICSW_RENDER_MENUBAR"))
    # )

    $scope.$on("$stateChangeStart", (event, to_state, to_params, from_state, from_params) ->
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "state_cs", to_state.name, to_main, from_state.name, from_main
        if to_main and not from_main
            true
        else if to_state.name == "login"
            # logout if logged in
            if icswUserService.user_present()
                icswUserService.logout()
            icswUserService.force_logout()
            $scope.CURRENT_USER = undefined
            $scope.show_navbar = false
    )
    route_counter = 0

    $scope.$on("$stateChangeSuccess", (event, to_state, to_params, from_state, from_params) ->
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "success", to_state.name, to_main, from_state.name, from_main
        route_counter++
        if to_state.name == "logout"
            blockUI.start("Logging out...")
            icswUserService.logout().then(
                (json) ->
                    blockUI.stop()
                    $scope.CURRENT_USER = undefined
            )
        else if not from_main and to_main
            $scope.CURRENT_USER = icswUserService.get()
            $scope.show_navbar = true
            # console.log to_params, $scope
        else
            # we allow one gentle transfer
            if route_counter >= 2 and false  # add one SinglePageApp License check
                # reduce flicker
                $(document.body).hide()
                $window.location.reload()

    )
    $scope.$on("$stateChangeError", (event, to_state, to_params) ->
        console.log "error moving to #{to_state.name}"
        $state.go("login")
    )
    # $scope.device_selection = () ->
    #    console.log "SHOW_DIALOG"
    #     icswLayoutSelectionDialogService.show_dialog()
]).directive("icswLayoutMenubar", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar")
    }
]).service("icswMenuProgressService", ["ICSW_SIGNALS", "$rootScope", (ICSW_SIGNALS, $rootScope) ->
    _settings = {
        # progress bar counter
        "rebuilding": 0
    }
    return {
        "set_rebuilding": (count) ->
            if count != _settings.rebuilding
                _settings.rebuilding = count
                $rootScope.$emit(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), _settings)
        "get_rebuilding": () ->
            return _settings.rebuilding
    }
]).directive("icswMenuProgressBars",
[
    "$templateCache", "ICSW_URLS", "$timeout", "icswSimpleAjaxCall", "initProduct",
    "icswMenuProgressService", "icswLayoutSelectionDialogService", "ICSW_SIGNALS", "$rootScope",
(
    $templateCache, ICSW_URLS, $timeout, icswSimpleAjaxCall, initProduct,
    icswMenuProgressService, icswLayoutSelectionDialogService, ICSW_SIGNALS, $rootScope
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
            scope.device_quickselection = (onoff) ->
                icswLayoutSelectionDialogService.quick_dialog(onoff)
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                scope.update_progress_bar()
            )
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
]).directive("icswBackgroundJobInfo", ["$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "$timeout", "$state", ($templateCache, ICSW_URLS, icswSimpleAjaxCall, $timeout, $state) ->
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
                $timeout(reload, 30000)
            reload()
    }
]).factory("icswReactMenuFactory",
    ["icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI", "icswMenuProgressService", "$state", (icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall, blockUI, icswMenuProgressService, $state) ->
        # console.log icswAcessLevelService
        {input, ul, li, a, span, h4} = React.DOM
        react_dom = ReactDOM
        rebuild_config = (cache_mode) ->
            blockUI.start()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.MON_CREATE_CONFIG
                    data: {
                        "cache_mode": cache_mode
                    }
                    title: "create config"
                }
            ).then(
                (xml) ->
                    blockUI.stop()
                    icswMenuProgressService.set_rebuilding(1)
                    # make at least five iterations to catch slow startup of md-config-server
                    # $scope.progress_iters = 5
                    # $scope.update_progress_bar()
                (xml) ->
                    blockUI.stop()
                    icswMenuProgressService.set_rebuilding(1)
            )
        menu_rebuild_mon_config = React.createClass(
            render: () ->
                _disabled = if icswMenuProgressService.get_rebuilding() then true else false
                return li(
                    {className: "text-left", key: "bmc"}
                    ul(
                        {className: "list-group", style: {marginBottom: "10px", marginTop: "5px"}}
                        [
                            li(
                                {className: "list-group-item", key: "mr.alw"}
                                input(
                                    {
                                        className: "btn btn-success btn-xs",
                                        type: "button",
                                        value: "\uf021 rebuild config (cached, RC)"
                                        title: "fully cached (using also the routing cache)"
                                        disabled: _disabled
                                        onClick: () ->
                                            rebuild_config("ALWAYS")
                                    }
                                )
                            )
                            li(
                                {className: "list-group-item", key: "mr.dyn"}
                                input(
                                    {
                                        className: "btn btn-warning btn-xs",
                                        type: "button",
                                        value: "\uf021 rebuild config (dynamic)"
                                        title: "refresh depends on timeout settings"
                                        disabled: _disabled
                                        onClick: () ->
                                            rebuild_config("DYNAMIC")
                                    }
                                )
                            )
                            li(
                                {className: "list-group-item", key: "mr.ref"}
                                input(
                                    {
                                        className: "btn btn-danger btn-xs",
                                        type: "button",
                                        value: "\uf021 rebuild config (refresh)"
                                        title: "rebuild network and contact devices"
                                        disabled: _disabled
                                        onClick: () ->
                                            rebuild_config("REFRESH")
                                    }
                                )
                            )
                        ]
                    )
                )
        )
        menu_line = React.createClass(
            displayName: "menuline"
            render: () ->
                if @props.href?
                    a_attrs = {href: @props.href, key: "a"}
                else
                    a_attrs = {href: @props.sref, key: "a"}
                if @props.labelClass
                    return li(
                        {key: "li"}
                        [
                            a(
                                a_attrs
                                [
                                    span(
                                        {className: "label #{@props.labelClass}", key: "spanl"}
                                        [
                                            span(
                                                {className: "fa #{@props.icon} fa_icsw", key: "span"}
                                            )
                                        ]
                                    )
                                    " #{@props.name}"
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
                                        {className: "fa #{@props.icon} fa_icsw", key: "span"}
                                    )
                                    " #{@props.name}"
                                ]
                            )
                        ]
                    )
        )
        menu_header = React.createClass(
            displayName: "menuheader"
            getDefaultProps: () ->
            render: () ->
                _idx = 0
                _items = []
                # _idx = 0
                # flag for last entry was a valid one
                valid_entry = false
                for entry in @props.entries
                    _idx++
                    _key = "item#{_idx}"
                    if entry.name? and not entry.disable?
                        _add = true
                        if entry.rights?
                            if angular.isFunction(entry.rights)
                                _add = entry.rights(@props.user, @props.acls)
                            else
                                _add = icswAcessLevelService.has_all_menu_permissions(entry.rights)
                        if entry.licenses? and _add
                            _add = icswAcessLevelService.has_all_valid_licenses(entry.licenses)
                            if not _add
                                console.warn "license(s) #{entry.licenses} missing"
                        if entry.service_types? and _add
                            _add = icswAcessLevelService.has_all_service_types(entry.service_types)
                            if not _add
                                console.warn "service_type(s) #{entry.service_types} missing"
                        if _add
                            # console.log _key
                            if entry.preSpacer and valid_entry
                                _items.push(
                                    li({className: "divider", key: _key + "_pre"})
                                )

                            if angular.isFunction(entry.name)
                                _items.push(
                                    React.createElement(entry.name, {key: _key})
                                )
                            else
                                _items.push(
                                    React.createElement(menu_line, entry, {key: _key})
                                )
                            valid_entry = true
                            if entry.postSpacer and valid_entry
                                _items.push(
                                    li({className: "divider", key: _key + "_post"})
                                )
                                valid_entry = false
                if _items.length

                    _res = li(
                        {key: "menu"}
                        a(
                            {className: "dropdown-toggle", "data-toggle": "dropdown", key: "menu.head"}
                            [
                                span({className: "fa #{@props.icon} fa-lg fa_top", key: "span"})
                                span({key: "text#{_idx}"}, @props.name)
                            ]
                        )
                        ul(
                            {className: "dropdown-menu", key: "ul"}
                            _items
                        )
                    )
                else
                    _res = null
                return _res
        )

        class MenuHeader
            constructor: (@key, @name, @icon, @ordering) ->
                @entries = []
            add_entry: (entry) =>
                @entries.push(entry)
            get_react: (user, acls) =>
                # order entries
                return React.createElement(
                    menu_header
                    {
                        key: @key
                        name: @name
                        icon: @icon
                        entries: (_entry.get_react() for _entry in _.orderBy(@entries, "ordering"))
                        user: user
                        acls: acls
                    }
                )

        class MenuEntry
            constructor: (@name, @rights, @licenses, @service_types, @icon, @ordering, @sref, @preSpacer, @postSpacer, @labelClass) ->
            get_react: () =>
                return {
                    name: @name
                    rights: @rights
                    icon: @icon
                    sref: @sref
                    licenses: @licenses
                    service_types: @service_types
                    preSpacer: @preSpacer
                    postSpacer: @postSpacer
                    labelClass: @labelClass
                }

        menu_comp = React.createClass(
            displayName: "menubar"
            propTypes:
                React.PropTypes.object.isRequired
            update_dimensions: () ->
                @setState(
                    {
                        width: $(window).width()
                        height: $(window).height()
                    }
                )
            componentWillMount: () ->
                # register eventhandler
                $(window).on("resize", @update_dimensions)

            componentWillUnmount: () ->
                # remove eventhandler
                $(window).off("resize", @update_dimensions)

            componentDidMount: () ->
                mb_height = $(react_dom.findDOMNode(@)).parents("nav").height()
                # console.log "fMENUBAR_HEIGHT=", mb_height
                $("body").css("padding-top", mb_height + 1)
            componentDidUpdate: () ->
                mb_height = $(react_dom.findDOMNode(@)).parents("nav").height()
                # console.log "uMENUBAR_HEIGHT=", mb_height
                $("body").css("padding-top", mb_height + 1)
            render: () ->
                menus = []
                for state in $state.get()
                    if state.data? and state.data.menuHeader?
                        _hdr = state.data.menuHeader
                        menus.push(
                            new MenuHeader(
                                _hdr.key
                                _hdr.name
                                _hdr.icon
                                _hdr.ordering
                            )
                        )
                for state in $state.get()
                    if state.data? and state.data.menuEntry?
                        # find menu
                        _entry = state.data.menuEntry
                        menu = (entry for entry in menus when entry.key == _entry.menukey)
                        if menu.length

                            menu[0].add_entry(
                                new MenuEntry(
                                    _entry.name or state.data.pageTitle
                                    state.data.rights
                                    state.data.licenses
                                    state.data.service_types
                                    _entry.icon
                                    _entry.ordering
                                    $state.href(state)
                                    _entry.preSpacer?
                                    _entry.postSpacer?
                                    if _entry.labelClass? then _entry.labelClass else ""
                                )
                            )
                        else
                            console.error("No menu with name #{_entry.menukey} found")
                # todo: check for service_type
                user = @props.user
                acls = @props.acls
                extra_menus = (menu.get_react(user, acls) for menu in _.orderBy(menus, "ordering"))
                # console.log icswAcessLevelService.has_menu_permission("user.modify_tree")
                # console.log @props
                _res = ul(
                    {key: "topmenu", className: "nav navbar-nav"}
                    extra_menus
                )
                return _res
        )
        return menu_comp
    ]
).directive("icswMenuDirective",
[
    "icswReactMenuFactory", "icswAcessLevelService", "icswMenuProgressService", "$rootScope", "ICSW_SIGNALS",
(
    icswReactMenuFactory, icswAcessLevelService, icswMenuProgressService, $rootScope, ICSW_SIGNALS
) ->
    return {
        restrict: "EA"
        replace: true
        scope:
            user: "="
        link: (scope, el, attrs) ->
            _user = undefined
            _acls = undefined
            _render = () ->
                if _user and _acls
                    ReactDOM.render(
                        React.createElement(icswReactMenuFactory, {"user": _user, "acls": _acls})
                        el[0]
                    )
            $rootScope.$on(ICSW_SIGNALS("ICSW_USER_CHANGED"), (event, user) ->
                # console.log "uc", user
                _user = user
                # console.log "user_render"
                _render()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_ACLS_CHANGED"), (event, acls) ->
                # console.log "ac", acls
                _acls = acls
                # console.log "acls_render"
                _render()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                # console.log "mps", settings
                _render()
            )
            # $rootScope.$on(ICSW_SIGNALS("ICSW_RENDER_MENUBAR"), (event, settings) ->
            #     # console.log "mps", settings
            #     _render()
            # )

    }
])
