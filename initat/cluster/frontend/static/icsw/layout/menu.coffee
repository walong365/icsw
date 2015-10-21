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

menu_module = angular.module(
    "icsw.layout.menu",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).controller("menu_base", ["$scope", "$timeout", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswParseXMLResponseService", "access_level_service", "initProduct", "icswLayoutSelectionDialogService", "icswActiveSelectionService", "$q", "icswUserService",
    ($scope, $timeout, $window, ICSW_URLS, icswSimpleAjaxCall, icswParseXMLResponseService, access_level_service, initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService, $q, icswUserService) ->
        $scope.is_authenticated = false
        # init background jobs
        $scope.NUM_BACKGROUND_JOBS = 0
        # init service types
        $scope.SERVICE_TYPES = {}
        $scope.ICSW_URLS = ICSW_URLS
        $scope.initProduct = initProduct
        $scope.quicksel = false
        $scope.CURRENT_USER = {}
        $scope.HANDBOOK_PDF_PRESENT = false
        $scope.HANDBOOK_CHUNKS_PRESENT = false
        $scope.HANDBOOK_PAGE = "---"
        access_level_service.install($scope)
        $scope.progress_iters = 0
        $scope.cur_gauges = {}
        $scope.num_gauges = 0
        $q.all(
            [
                icswSimpleAjaxCall(
                    {
                        "url": ICSW_URLS.MAIN_ROUTING_INFO
                        "dataType": "json"
                    }
                ),
                icswSimpleAjaxCall(
                    {
                        "url": ICSW_URLS.MAIN_GET_DOCU_INFO,
                        "dataType": "json"
                    }
                ),
                icswUserService.load(),
            ]
        ).then(
            (data) ->
                $scope.SERVICE_TYPES = data[0].service_types
                $scope.HANDBOOK_PDF_PRESENT = data[1].HANDBOOK_PDF_PRESENT
                $scope.HANDBOOK_CHUNKS_PRESENT = data[1].HANDBOOK_CHUNKS_PRESENT
                $scope.is_authenticated = data[2].authenticated
                $scope.CURRENT_USER = data[2]
        )
        # testing
        # $timeout(
        #    () ->
        #        icswUserService.load().then((data) ->
        #            console.log "*", data
        #        )
        #    2000
        # )
        $scope.get_progress_style = (obj) ->
            return {"width" : "#{obj.value}%"}
        $scope.update_progress_bar = () ->
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.BASE_GET_GAUGE_INFO
                    hidden: true
                }
            ).then(
                (xml) =>
                    cur_pb = []
                    if icswParseXMLResponseService(xml)
                        $(xml).find("gauge_info gauge_element").each (idx, cur_g) ->
                            cur_g = $(cur_g)
                            idx = cur_g.attr("idx")
                            if idx of $scope.cur_gauges
                                $scope.cur_gauges[idx].info = cur_g.text()
                                $scope.cur_gauges[idx].value = parseInt(cur_g.attr("value"))
                            else
                                $scope.cur_gauges[idx] = {info : cur_g.text(), value : parseInt(cur_g.attr("value"))}
                            cur_pb.push(idx)
                    del_pbs = (cur_idx for cur_idx of $scope.cur_gauges when cur_idx not in cur_pb)
                    for del_pb in del_pbs
                        delete $scope.cur_gauges[del_pb]
                    #for cur_idx, value of $scope.cur_gauges
                    $scope.num_gauges = cur_pb.length
                    if cur_pb.length or $scope.progress_iters
                        if $scope.progress_iters
                            $scope.progress_iters--
                        $timeout($scope.update_progress_bar, 1000)
            )
        $scope.redirect_to_init = () ->
            window.location = "http://www.init.at"
            return false
        $scope.redirect_to_handbook = () ->
            window.location = "/cluster/doc/#{initProduct.name.toLowerCase()}_handbook.pdf"
            return false
        $scope.handbook_url = "/"
        $scope.$watch("initProduct", (new_val) ->
            if new_val.name?
                $scope.handbook_url = "/cluster/doc/#{new_val.name.toLowerCase()}_handbook.pdf"
        )
        $scope.rebuild_config = (cache_mode) ->
            # console.log ICSW_URLS.MON_CREATE_CONFIG, "+++"
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
                    # make at least five iterations to catch slow startup of md-config-server
                    $scope.progress_iters = 5
                    $scope.update_progress_bar()
            )
        $scope.$watch("navbar_size", (new_val) ->
            if new_val
                if $scope.is_authenticated
                    $("body").css("padding-top", parseInt(new_val["height"]) + 1)
        )
        $scope.device_selection = () ->
            icswLayoutSelectionDialogService.show_dialog($scope)
        $scope.device_quicksel = (onoff) ->
            if onoff != $scope.quicksel
                $scope.quicksel = onoff
                if $scope.quicksel
                    icswLayoutSelectionDialogService.quick_dialog($scope)
]).directive("icswLayoutMenubar", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar")
    }
]).factory("icswLayoutMenuAddon", () ->
    addons = []
    return addons
).directive("icswLayoutMenubarAddons", ["$templateCache", "$compile", "$window", "icswLayoutMenuAddon", ($templateCache, $compile, $window, icswLayoutMenuAddon) ->
    return {
        restrict: "EA"
        compile: (tElement, tAttr) ->
            return (scope, el, attrs) ->

                new_elems = []

                for addon in icswLayoutMenuAddon
                    _template_str = "<#{addon}></#{addon}>"
                    _new_el = $compile(_template_str)(scope).children()
                    new_elems.push(_new_el)

                el.replaceWith(new_elems)
    }
]).directive("icswBackgroundJobInfo", ["$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "$timeout", ($templateCache, ICSW_URLS, icswSimpleAjaxCall, $timeout) ->
    return {
        restrict: "EA"
        template: '<button type="button" ng-click="redirect_to_bgj_info()" title="number of background jobs"></button>'
        replace: true
        link: (scope, el, attrs) ->
            scope.background_jobs = 0
            el.hide()
            scope.redirect_to_bgj_info = () ->
                if scope.has_menu_permission('background_job.show_background')
                    window.location = ICSW_URLS.USER_BACKGROUND_JOB_INFO
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
                ).then((data) ->
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
]).factory(
    "icswReactMenuFactory",
    ["access_level_service", "ICSW_URLS", (access_level_service, ICSW_URLS) ->
        # console.log access_level_service
        {div, ul, li, a, span} = React.DOM
        _counter = 0
        _key_counter = 0
        menu_line = React.createClass(
            render: () ->
                return li(
                    {}
                    [
                        a(
                            {href: @props.href}
                            [
                                span(
                                    {className: "fa #{@props.icon} fa_icsw"}
                                )
                                " #{@props.name}"
                            ]
                        )
                    ]
                )
        )
        menu_header = React.createClass(
            getDefaultProps: () ->
            render: () ->
                _key_counter++
                # console.log @props.rights, access_level_service.has_any_menu_permission(@props.rights)
                _items = []
                for entry in @props.entries
                    if entry.name?
                        if not entry.disable?
                            _add = true
                            if entry.rights?
                                _add = access_level_service.has_any_menu_permission(entry.rights)
                            if _add
                                _items.push(
                                    React.createElement(menu_line, entry)
                                )
                    else
                        _items.push(
                            li({className: "divider"})
                        )
                if _items.length
                    _res = li(
                        {}
                        a(
                            {className: "dropdown-toggle", "data-toggle": "dropdown"
                            }
                            [
                                span(
                                    {className: "fa #{@props.icon} fa-lg fa_top"}
                                )
                                span({}, @props.name)
                            ]
                        )
                        ul(
                            {className: "dropdown-menu"}
                            _items
                        )
                    )
                else
                    _res = null
                return _res
        )
        menu_comp = React.createClass(
            propTypes:
                React.PropTypes.object.isRequired
            render: () ->
                _counter++
                console.log "render", @props, _counter
                # console.log access_level_service.has_menu_permission("user.modify_tree")
                # console.log @props
                _res = ul(
                    {key: "tl", className: "nav navbar-nav"}
                    [
                        # "test #{_counter}"
                        React.createElement(
                            menu_header
                            {
                                key: 4
                                name: "Device"
                                icon: "fa-hdd-o"
                                entries: [
                                    {
                                        name: "Create new device"
                                        rights: ["user.modify_tree"]
                                        icon: "fa-plus-circle"
                                        href: ICSW_URLS.MON_CREATE_DEVICE
                                    }
                                    {}
                                    {
                                        name: "General"
                                        rights: ["user.modify_tree"]
                                        icon: "fa-bars"
                                        href: ICSW_URLS.DEVICE_DEVICE_GENERAL
                                    }
                                    {
                                        name: "Network"
                                        rights: ["device.change_network"]
                                        icon: "fa-sitemap"
                                        href: ICSW_URLS.NETWORK_DEVICE_NETWORK
                                    }
                                    {
                                        name: "Configurations"
                                        rights: ["device.change_config"]
                                        icon: "fa-check-square-o"
                                        href: ICSW_URLS.CONFIG_SHOW_CONFIGS
                                    }
                                    {
                                        name: "Device Configurations"
                                        rights: ["device.change_config"]
                                        icon: "fa-check-square"
                                        href: ICSW_URLS.DEVICE_SHOW_CONFIGS
                                    }
                                    {
                                        name: "Device variables"
                                        rights: ["device.change_variables"]
                                        icon: "fa-code"
                                        href: ICSW_URLS.DEVICE_VARIABLES
                                    }
                                    {
                                        name: "Device category"
                                        rights: ["user.modify_category_tree"]
                                        icon: "fa-table"
                                        href: ICSW_URLS.BASE_DEVICE_CATEGORY
                                    }
                                    {
                                        name: "Device location"
                                        rights: ["user.modify_category_tree"]
                                        icon: "fa-map-marker"
                                        href: ICSW_URLS.BASE_DEVICE_LOCATION
                                    }
                                    {
                                        name: "Device connections"
                                        rights: ["device.change_connection"]
                                        icon: "fa-plug"
                                        href: ICSW_URLS.DEVICE_CONNECTIONS
                                    }
                                    {}
                                    {
                                        name: "Device tree"
                                        rights: ["user.modify_tree"]
                                        icon: "fa-list"
                                        href: ICSW_URLS.DEVICE_TREE_SMART
                                    }
                                    {
                                        name: "Domain name tree"
                                        rights: ["user.modify_domain_name_tree"]
                                        icon: "fa-list-alt"
                                        href: ICSW_URLS.NETWORK_DOMAIN_NAME_TREE
                                    }
                                    {}
                                    {
                                        disable: true
                                        name: "Discovery"
                                        rights: ["device.discovery_server"]
                                        href: ICSW_URLS.DISCOVERY_OVERVIEW
                                    }

                                ]
                            }
                        )
                        React.createElement(
                            menu_header
                            {
                                key: 6,
                                name: "Monitoring",
                                icon: "fa-gears",
                                entries: [
                                    {
                                        name: "bla"
                                        rights: ["device.change_config"]
                                    }
                                ]
                            }
                        )
                    ]
                )
                return _res
        )
        return menu_comp
    ]
).directive("icswMenuDirective", ["icswReactMenuFactory", "access_level_service", (icswReactMenuFactory, access_level_service) ->
    return {
        restrict: "EA"
        replace: true
        scope:
            user: "="
        link: (scope, el, attrs) ->
            _user = undefined
            _render = () ->
                if _user
                    ReactDOM.render(
                        React.createElement(icswReactMenuFactory, _user)
                        el[0]
                    )
            scope.$watch("user", (new_val) ->
                _user = new_val
                _render()
            )
            scope.$watch(
                () ->
                    return access_level_service.acl_valid()
                (new_val) ->
                    _render()
            )
    }
])
