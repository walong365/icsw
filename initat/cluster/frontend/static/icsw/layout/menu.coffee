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
).controller("menu_base", ["$scope", "$timeout", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswParseXMLResponseService", "icswAcessLevelService", "initProduct", "icswLayoutSelectionDialogService", "icswActiveSelectionService", "$q", "icswUserService",
    ($scope, $timeout, $window, ICSW_URLS, icswSimpleAjaxCall, icswParseXMLResponseService, icswAcessLevelService, initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService, $q, icswUserService) ->
        $scope.is_authenticated = false
        # init background jobs
        $scope.NUM_BACKGROUND_JOBS = 0
        # init service types
        $scope.ICSW_URLS = ICSW_URLS
        $scope.initProduct = initProduct
        $scope.quicksel = false
        $scope.CURRENT_USER = {}
        $scope.HANDBOOK_PDF_PRESENT = false
        $scope.HANDBOOK_CHUNKS_PRESENT = false
        $scope.HANDBOOK_PAGE = "---"
        icswAcessLevelService.install($scope)
        $scope.progress_iters = 0
        $scope.cur_gauges = {}
        $scope.num_gauges = 0
        $q.all(
            [
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
                $scope.HANDBOOK_PDF_PRESENT = data[0].HANDBOOK_PDF_PRESENT
                $scope.HANDBOOK_CHUNKS_PRESENT = data[0].HANDBOOK_CHUNKS_PRESENT
                $scope.is_authenticated = data[1].authenticated
                $scope.CURRENT_USER = data[1]
        )
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
]).factory("icswReactMenuFactory",
    ["icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", (icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall) ->
        # console.log icswAcessLevelService
        {input, ul, li, a, span} = React.DOM
        rebuild_config = (cache_mode) ->
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
                    # $scope.progress_iters = 5
                    # $scope.update_progress_bar()
            )
        menu_rebuild_mon_config = React.createClass(
            render: () ->
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
                return li(
                    {key: "li"}
                    [
                        a(
                            {href: @props.href, key: "a"}
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
                _items = []
                _idx = 0
                for entry in @props.entries
                    _idx++
                    _key = "item#{_idx}"
                    if entry.name?
                        if not entry.disable?
                            _add = true
                            if entry.rights?
                                _add = icswAcessLevelService.has_all_menu_permissions(entry.rights)
                            if entry.licenses? and _add
                                _add = icswAcessLevelService.has_all_valid_licenses(entry.licenses)
                            if _add
                                if angular.isFunction(entry.name)
                                    _items.push(
                                        React.createElement(entry.name, {key: _key})
                                    )
                                else
                                    _items.push(
                                        React.createElement(menu_line, entry)
                                    )
                    else
                        _items.push(
                            li({className: "divider", key: _key})
                        )
                if _items.length
                    _res = li(
                        {key: "menu"}
                        a(
                            {className: "dropdown-toggle", "data-toggle": "dropdown", key: "a"}
                            [
                                span(
                                    {className: "fa #{@props.icon} fa-lg fa_top", key: "span"}
                                )
                                span({key: "text"}, @props.name)
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
        menu_comp = React.createClass(
            displayName: "menubar"
            propTypes:
                React.PropTypes.object.isRequired
            render: () ->
                # todo: check for service_type
                user = @props
                # console.log icswAcessLevelService.has_menu_permission("user.modify_tree")
                # console.log @props
                _res = ul(
                    {key: "topmenu", className: "nav navbar-nav"}
                    [
                        React.createElement(
                            menu_header
                            {
                                key: "dev"
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
                                key: "mon",
                                name: "Monitoring",
                                icon: "fa-gears",
                                entries: [
                                    {
                                        name: "Basic setup"
                                        rights: ["mon_check_command.setup_monitoring"]
                                        icon: "fa-bars"
                                        href: ICSW_URLS.MON_SETUP
                                    }
                                    {
                                        name: "Device settings"
                                        rights: ["mon_check_command.setup_monitoring", "device.change_monitoring"]
                                        icon: "fa-laptop"
                                        href: ICSW_URLS.MON_DEVICE_CONFIG
                                    }
                                    {}
                                    {
                                        name: "Cluster / Dependency setup"
                                        licenses: ["md_config_server"]
                                        rights: ["mon_check_command.setup_monitoring"]
                                        icon: "fa-chain"
                                        href: ICSW_URLS.MON_SETUP_CLUSTER
                                    }
                                    {
                                        name: "Escalation setup"
                                        licenses: ["md_config_server"]
                                        rights: ["mon_check_command.setup_monitoring"]
                                        icon: "fa-bolt"
                                        href: ICSW_URLS.MON_SETUP_ESCALATION
                                    }
                                    {}
                                    {
                                        name: "Monitoring hints"
                                        licenses: ["md_config_server"]
                                        rights: ["mon_check_command.setup_monitoring"]
                                        icon: "fa-info"
                                        href: ICSW_URLS.MON_MONITORING_HINTS
                                    }
                                    {
                                        name: "Disk"
                                        licenses: ["md_config_server"]
                                        rights: ["mon_check_command.setup_monitoring"]
                                        icon: "fa-hdd-o"
                                        href: ICSW_URLS.MON_MONITORING_DISK
                                    }
                                    {}
                                    {
                                        name: "Icinga"
                                        licenses: ["md_config_server"]
                                        icon: "fa-share-alt"
                                        href: ICSW_URLS.MON_CALL_ICINGA
                                    }
                                    {
                                        rights: ["mon_check_command.setup_monitoring"]
                                        licenses: ["md_config_server"]
                                        name: menu_rebuild_mon_config
                                    }
                                    {
                                        name: "Build Info"
                                        rights: ["mon_check_command.setup_monitoring"]
                                        icon: "fa-info-circle"
                                        href: ICSW_URLS.MON_BUILD_INFO
                                    }
                                ]
                            }
                        )
                        React.createElement(
                            menu_header
                            {
                                key: "stat",
                                name: "Status",
                                icon: "fa-line-chart"
                                entries: [
                                    {
                                        name: "Monitoring dashboard"
                                        rights: ["mon_check_command.show_monitoring_dashboard"]
                                        licenses: ["monitoring_dashboard"]
                                        icon: "fa-dot-circle-o"
                                        href: ICSW_URLS.MON_LIVESTATUS
                                    }
                                    {
                                        name: "Graph"
                                        rights: ["backbone.device.show_graphs"]
                                        licenses: ["graphing"]
                                        icon: "fa-line-chart"
                                        href: ICSW_URLS.MON_GRAPH
                                    }
                                    {
                                        name: "Status History"
                                        rights: ["backbone.device.show_status_history"]
                                        licenses: ["reporting"]
                                        icon: "fa-pie-chart"
                                        href: ICSW_URLS.MON_STATUS_HISTORY
                                    }
                                    {}
                                    {
                                        name: "Key performance indicators"
                                        rights: ["kpi.kpi"]
                                        licenses: ["kpi"]
                                        icon: "fa-code-fork"
                                        href: ICSW_URLS.BASE_KPI
                                    }
                                    {}
                                    {
                                        name: "WMI and IPMI Event logs"
                                        rights: ["device.discovery_server"]
                                        licenses: ["discovery_server"]
                                        icon: "fa-list-alt"
                                        href: ICSW_URLS.DISCOVERY_EVENT_LOG_OVERVIEW
                                    }
                                ]
                            }
                        )
                        React.createElement(
                            menu_header
                            {
                                key: "clus",
                                name: "Cluster"
                                icon: "fa-cubes"
                                entries: [
                                    {
                                        name: "Nodeboot"
                                        rights: ["device.change_boot"]
                                        licenses: ["netboot"]
                                        icon: "fa-rocket"
                                        href: ICSW_URLS.BOOT_SHOW_BOOT
                                    }
                                    {
                                        name: "Packet install"
                                        rights: ["package.package_install"]
                                        licenses: ["package_install"]
                                        icon: "fa-download"
                                        href: ICSW_URLS.PACK_REPO_OVERVIEW
                                    }
                                    {}
                                    {
                                        name: "Images and Kernels"
                                        rights: ["image.modify_images", "kernel.modify_kernels"]
                                        licenses: ["netboot"]
                                        icon: "fa-linux"
                                        href: ICSW_URLS.PACK_REPO_OVERVIEW
                                    }
                                    {
                                        name: "Partition overview"
                                        rights: ["partition_fs.modify_partitions"]
                                        licenses: ["netboot"]
                                        icon: "fa-database"
                                        href: ICSW_URLS.SETUP_PARTITION_OVERVIEW
                                    }
                                ]
                            }
                        )
                        React.createElement(
                            menu_header
                            {
                                key: "rms"
                                name: "RMS"
                                icon: "fa-cubes"
                                entries: [
                                    {
                                        name: "RMS overview"
                                        licenses: ["rms"]
                                        icon: "fa-table"
                                        href: ICSW_URLS.RMS_OVERVIEW
                                    }
                                    {
                                        disable: true
                                        name: "License overview"
                                        licenses: ["ext_license"]
                                        href: ICSW_URLS.LIC_OVERVIEW
                                    }
                                    {
                                        name: "License LiveView"
                                        licenses: ["ext_license"]
                                        icon: "fa-line-chart"
                                        href: ICSW_URLS.LIC_LICENSE_LIVEVIEW
                                    }
                                ]
                            }
                        )
                        React.createElement(
                            menu_header
                            {
                                key: "sys"
                                name: "System"
                                icon: "fa-cog"
                                entries: [
                                    {
                                        name: "User"
                                        rights: ["group.group_admin"]
                                        icon: "fa-user"
                                        href: ICSW_URLS.USER_OVERVIEW
                                    }
                                    {
                                        name: "History"
                                        rights: ["user.snapshots"]
                                        licenses: ["snapshot"]
                                        icon: "fa-history"
                                        href: ICSW_URLS.SYSTEM_HISTORY_OVERVIEW
                                    }
                                    {
                                        name: "License"
                                        rights: if user.is_superuser then [] else ["deny"]
                                        icon: "fa-key"
                                        href: ICSW_URLS.USER_GLOBAL_LICENSE
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
).directive("icswMenuDirective", ["icswReactMenuFactory", "icswAcessLevelService", (icswReactMenuFactory, icswAcessLevelService) ->
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
                    return icswAcessLevelService.acl_valid()
                (new_val) ->
                    _render()
            )
    }
])
