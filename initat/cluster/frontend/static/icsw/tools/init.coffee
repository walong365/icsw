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
    "icsw.tools",
    [
        "toaster"
        "uiGmapgoogle-maps"
        "icsw.menu"
    ]
).service("icswBaseMixinClass", [() ->
    # hm, not really needed ... ?
    module_keywords = ["extended", "included"]
    class icswBaseMixinClass
        @extend: (obj) ->
            for key, value of obj when key not in module_keywords
                @[key] = value

            obj.extended?.apply(@)
            this

        @include: (obj) ->
            for key, value of obj when key not in moduleKeywords
                # Assign properties to the prototype
                @::[key] = value

            obj.included?.apply(@)
            this
        
]).service("createSVGElement", [() ->
    return (name, settings) ->
        ns = "http://www.w3.org/2000/svg"
        node = document.createElementNS(ns, name)
        for key, value  of settings
            if value?
                node.setAttribute(key, value)
        return $(node)
]).service("icswOverallStyle",
[
    "$q", "ICSW_SIGNALS", "$rootScope",
(
    $q, ICSW_SIGNALS, $rootScope,
) ->
    _style = "normal"
    return {
        get: () ->
            return _style
        set: (name) ->
            _style = name
            $rootScope.$emit(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"))
    }
]).controller("icswBodyCtrl",
[
    "$scope", "icswOverallStyle", "$rootScope", "ICSW_SIGNALS",
(
    $scope, icswOverallStyle, $rootScope, ICSW_SIGNALS,
) ->
    icswOverallStyle.set("condensed");
    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERALL_STYLE_CHANGED"), () ->
        $scope.overall_style = icswOverallStyle.get()
    )
    $scope.overall_style = icswOverallStyle.get()
]).directive("icswDeviceListInfo",
[
   "$q", "icswSimpleAjaxCall", "$templateCache", "ICSW_URLS",
(
    $q, icswSimpleAjaxCall, $templateCache, ICSW_URLS,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.list.info")
        scope:
            device_list: "=icswDeviceList"
        link: (scope, element, attrs) ->
            scope.struct = {
                # loading
                is_loading: true
                # header
                header: ""
            }
            scope.$watchCollection(
                "device_list"
                (new_list) ->
                    scope.struct.is_loading = true
                    scope.struct.header = "#{scope.device_list.length} devices"
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.DEVICE_DEVICE_LIST_INFO
                        data:
                            pk_list: angular.toJson((dev.idx for dev in new_list))
                        dataType: "json"
                    ).then(
                        (result) ->
                            scope.struct.is_loading = false
                            scope.struct.header = result.header
                    )
            )

    }
]).directive("icswAutoFocus",
[
    "$timeout",
(
    $timeout,
) ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            _af_set = false
            _set_autofocus = () ->
                _af_set = true
                $timeout(
                    () ->
                        element[0].focus()
                    1
                )
            if attrs.icswAutoFocus
                scope.$watch(
                    () ->
                        scope.$eval(attrs.icswAutoFocus)
                    (new_val) ->
                        if new_val and not _af_set
                            _set_autofocus()
                )
            else
                # no attribute set, autofocus immediately
                _set_autofocus()
    }
]).service("icswCSRFService",
[
    "$http", "ICSW_URLS", "$q",
(
    $http, ICSW_URLS, $q
) ->
    csrf_token = undefined
    _waiting = []
    _fetching = false

    fetch_token = () ->
        _fetching = true
        $http(
            {
                method: 'GET'
                data: "json"
                url: ICSW_URLS.SESSION_GET_CSRF_TOKEN
            }
        ).then(
            (data) ->
                _fetching = false
                csrf_token = data.data.token
                for _wait in _waiting
                    _wait.resolve(csrf_token)
        )

    get_token = () ->
        _defer = $q.defer()
        if csrf_token
            _defer.resolve(csrf_token)
        else
            _waiting.push(_defer)
            if not _fetching
                fetch_token()
        return _defer.promise

    # prefetch
    fetch_token()

    return {
        get_token: () ->
            return get_token()
        clear_token: () ->
            csrf_token = undefined
    }
]).service("icswGoogleMapConfig",
[
    "uiGmapMapScriptLoader", "$q", "icswSystemLicenseDataService",
(
    uiGmapMapScriptLoader, $q, icswSystemLicenseDataService,
) ->
    _load_pending = false
    _is_init = false
    _map = undefined
    _pending_clients = []

    init = () ->
        defer = $q.defer()
        if _is_init
            defer.resolve(_map)
        else if _load_pending
            _pending_clients.push(defer)
        else
            _load_pending = true
            icswSystemLicenseDataService.load("gmap_init").then(
                (data) ->
                    uiGmapMapScriptLoader.load(
                        {
                            # defaults, please check when updating google-maps-angular !
                            key: data.cluster_info.GOOGLE_MAPS_KEY
                            v: '3.25'  # defaults to latest 3.X anyhow
                            libraries: 'weather,geometry,visualization'
                            transport: "https"
                            china: false
                            language: "en"
                            preventLoad: false
                        }
                    ).then(
                        (map) ->
                            _is_init = true
                            _load_pending = false
                            _map = map
                            defer.resolve(_map)
                            for _client in _pending_clients
                                _client.resolve(_map)
                            _pending_clients.length = 0
                    )
            )
        return defer.promise

    return {
        init: () ->
            return init()
    }
]).config([
    "blockUIConfig",
(
    blockUIConfig
) ->
    blockUIConfig.delay = 0
    blockUIConfig.message = "Loading, please wait ..."
    blockUIConfig.autoBlock = false
    blockUIConfig.autoInjectBodyBlock = false
]).config([
    "hotkeysProvider",
(
    hotkeysProvider,
) ->
    hotkeysProvider.templateHeader = "<h1>ICSW Key Help</h1>"
    hotkeysProvider.includeCheatSheet = true
    hotkeysProvider.cheatSheetHotkey = "F1"
]).config([
    "toasterConfig",
(
    toasterConfig
) ->
    # close on click
    toasterConfig["tap-to-dismiss"] = true
    toasterConfig.limit = 8
    # hide close button
    toasterConfig["close-button"] = false
    toasterConfig["time-out"] = {
        # timeout for error after 30 seconds
        "toast-error": 30000
        "toast-warning": 10000
        "toast-info": 5000
        "toast-success": 5000
    }
]).config([
    "$httpProvider",
(
    $httpProvider
) ->
    $httpProvider.defaults.xsrfCookieName = 'csrftoken'
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'

]).service("icswParseXMLResponseService",
[
    "toaster",
(
    toaster
) ->
    return (xml, min_level, show_error=true, hidden=false) ->
        # use in combination with icswCallAjaxService, or otherwise make sure to wrap
        # the <response> from the server in some outer tag (similar to usage in license.coffee)
        success = false
        if $(xml).find("response header").length
            ret_state = $(xml).find("response header").attr("code")
            if parseInt(ret_state) < (if min_level then min_level else 40)
                success = true
            $(xml).find("response header messages message").each (idx, cur_mes) ->
                cur_mes = $(cur_mes)
                cur_level = parseInt(cur_mes.attr("log_level"))
                if cur_level < 30
                    if not hidden
                        toaster.pop("success", "", cur_mes.text())
                else if cur_level == 30
                    if not hidden
                        toaster.pop("warning", "", cur_mes.text())
                else
                    if show_error
                        toaster.pop("error", "An Error occured", cur_mes.text())
        else
            if xml != null
                toaster.pop("error", "A critical error occured", "error parsing response")
        return success
]).provider("icswRouteExtension",
[
    "$stateProvider", "ICSW_CONFIG_JSON",
(
    $stateProvider, ICSW_CONFIG_JSON,
) ->
    _key_idx = 0
    class icswRouteExtension
        constructor: (args) ->
            # console.log _key_idx, args
            _key_idx++
            @_extension = true
            # list of needed rights
            @rights = []
            # list of needed licenses
            @licenses = []
            # list of needed service_types (== routes)
            @serviceTypes = []
            # pageTitle:
            @pageTitle = ""
            # dashboardEntry
            @dashboardEntry = {}
            # flag: valid for quicklink
            @validForQuicklink = false
            # has deviceselection function
            @hasDevselFunc = false
            # description field
            @description = {}
            for key, value of args
                if not @[key]?
                    console.error "unknown icswRouteExtension #{key}=#{value}", @
                else
                    @[key] = value
            # for _check in ["menuEntry", "menuHeader", "routeSubGroup", "dashboardEntry"]
            for _check in ["dashboardEntry"]
                _attr = "$$#{_check}"
                if args and _check of args
                    @[_attr] = true
                else
                    @[_attr] = false
            # feed states
            for _attr_name in ["rights", "licenses", "serviceTypes"]
                _src = @[_attr_name]
                _dest = "$$#{_attr_name}_info"
                if angular.isFunction(_src)
                    @[_dest] = "func"
                else
                    if _src.length
                        @[_dest] = _src.join(", ")
                    else
                        @[_dest] = "---"
            # flags: rights ok
            @$$allowed = false
            # unique key
            @key = "ire_#{_key_idx}"
            if @$$dashboardEntry
                # set defaults for dashboard
                for [_name, _default, _log] in [
                    ["headerClass", "default", false]
                    ["sizeX", 2, true]
                    ["sizeY", 2, true]
                    ["allowShow", true, false]
                    ["allowState", false, false]
                    ["defaultEnabled", false, false]
                ]
                    if not @dashboardEntry[_name]?
                        @dashboardEntry[_name] = _default
                        if _log
                            console.error "missing attribute #{_name} in dashboardEntry for", @

    _add_route = (name, resolve_map) ->
        # console.log ICSW_CONFIG_JSON
        # reads from ICSW_CONFIG_JSON and adds to $stateProvider
        if name not of ICSW_CONFIG_JSON.routes
            throw new Error("stateName '#{name}' not found in ICSW_CONFIG_JSON")
        _data = ICSW_CONFIG_JSON.routes[name]
        if not _data.icswData? or not _data.stateData?
            throw new Error("icswData or stateData not found for stateName '#{name}'")
        _ext = new icswRouteExtension(_data.icswData)
        _struct.entries.push(_ext)
        _state_data = angular.copy(_data.stateData)
        if not _state_data.params?
            _state_data.params = {
                targetTab: null
            }

        if resolve_map?
            _state_data.resolve = resolve_map
        _state_data.icswData = _ext
        $stateProvider.state(name, _state_data)
        return _ext


    _struct = {
        entries: []
    }

    return {
        $get: () ->
            # needed for access from services / factories
            return _struct

        add_route: (name, resolve_map) ->
            # could be omitted be adding all states found
            return _add_route(name, resolve_map)
    }
]).service("icswRouteHelper",
[
    "icswRouteExtension", "$state", "$rootScope", "ICSW_SIGNALS", "icswAccessLevelService",
    "icswTools", "ICSW_CONFIG_JSON",
(
    icswRouteExtension, $state, $rootScope, ICSW_SIGNALS, icswAccessLevelService,
    icswTools, ICSW_CONFIG_JSON,
) ->
    _init = false
    _user = undefined
    _acls = undefined
    _acls_valid = false

    class SimpleTreeNode
        constructor: (in_data) ->
            @data = in_data
            @root = @
            @parent = null
            @level = 0
            @num_childs = 0
            @num_elements = 0
            @entries = []

        link: (parent, root) ->
            @root = root
            @parent = parent
            @level = parent.level + 1
            # create link in data
            @data.$$simpleTreeNode = @
            # create menu_key
            @$$menu_key = "l#{@level}c#{@parent.num_childs}e#{@root.num_elements}"

        add_node: (data) =>
            @root.num_elements++
            @num_childs++
            _sub_node = new SimpleTreeNode(data)
            # link and increase level
            _sub_node.link(@, @root)
            @entries.push(_sub_node)
            return _sub_node

    _struct = {
        # is valid
        valid: false
        # list of all states
        icsw_states: []
        allowed_states: []
        quicklink_states: [] 
        dashboard_states: []
        menu_states: []
        menu_node: null
    }

    _check_rights = () ->
        # states for menus entries
        _struct.menu_states.length = 0
        # states for menu_headers
        _struct.menu_node = new SimpleTreeNode(null)
        # allowed states
        _struct.allowed_states.length = 0
        # states for quicklknk
        _struct.quicklink_states.length = 0
        # dashboard states
        _struct.dashboard_states.length = 0
        if _init
            # console.log "U/ACLS:", _user, _acls, _init, _acls
            #if _acls?
            #    console.log _acls.global_permissions

            # create menu

            for menuHeader in ICSW_CONFIG_JSON.menu.menuHeader
                _cur_menu = _struct.menu_node.add_node(menuHeader)

                # add subgroup(s)

                for routeSubGroup in menuHeader.routeSubGroup
                    _cur_sg = _cur_menu.add_node(routeSubGroup)

                    # add menu entries

                    for menuEntry in routeSubGroup.menuEntry
                        state = $state.get(menuEntry.routeName)
                        if state? and state
                            data = state.icswData
                            data.$$menuEntry = menuEntry
                            menuEntry.sref = $state.href(state)
                            _add = true
                            _missing_info = []
                            _missing_short = []
                            if data.rights?
                                if _user and _acls_valid
                                    if data.rights[0] == "$$CHECK_FOR_SUPERUSER"
                                        if _user?
                                            if _user.user.is_superuser
                                                _add = true
                                            else
                                                _add = false
                                        else
                                            _add = false
                                    else
                                        # console.log data.rights
                                        _add = icswAccessLevelService.has_all_menu_permissions(data.rights)
                                    if not _add
                                        _missing_info.push("User Rights")
                                        _missing_short.push("R")
                                    if data.licenses? and _add
                                        _add = icswAccessLevelService.has_all_valid_licenses(data.licenses)
                                        if not _add
                                            _missing_info.push("License")
                                            _missing_short.push("L")
                                            # console.warn "license(s) #{data.licenses} missing"
                                    if data.serviceTypes? and _add
                                        _add = icswAccessLevelService.has_all_service_types(data.serviceTypes)
                                        if not _add
                                            _missing_info.push("Service Type")
                                            _missing_short.push("S")
                                            # console.warn "service_type(s) #{data.serviceTypes} missing"
                                else
                                    _add = false
                            data.$$allowed = _add
                            data.$$missing_info = _missing_info.join(", ")
                            data.$$missing_short = _missing_short
                            # console.log "*", _add, state.name
                            # always add state to menu
                            _cur_sg.add_node(state)
                            if data.$$allowed
                                _struct.allowed_states.push(state)
                                if data.$$menuEntry
                                    _struct.menu_states.push(state)
                                if data.validForQuicklink
                                    _struct.quicklink_states.push(state)
                                if data.$$dashboardEntry
                                    _struct.dashboard_states.push(state)
                        else
                            console.error "unknown state #{menuEntry.routeName}"
                # if data.$$routeSubGroup
                #    _struct.route_sub_groups.push(state)
            # signal: we have changed the rights

        if _init and _user? and _acls_valid
            _struct.valid = true
            # signal: we have changed the rights with valid user and acls
            $rootScope.$emit(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_VALID"))
        else
            _struct.valid = false
            $rootScope.$emit(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_INVALID"))

        # console.log "RR", _init, _struct.valid, _user, _acls, _struct.icsw_states.length
        # emit this signal at last so that struct.valid is already set
        $rootScope.$emit(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_CHANGED"))
                    

    init_struct = () ->
        # all states (regardles of license and rights)
        _struct.icsw_states = (state for state in $state.get() when state.icswData?)
        _init = true
        # console.log "init states, count:", _struct.icsw_states.length
        _check_rights()

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), (event, user) ->
        _user = user
        _check_rights()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_ACLS_CHANGED"), (event, acls) ->
        _acls = acls
        if _acls?
            _acls_valid = _acls.acls_are_valid
        else
            _acls_valid = false
        _check_rights()
    )

    return {
        get_struct: () ->
            if not _init
                init_struct()
            return _struct
            
        check_rights: (user) ->
            _user = user
            _check_rights()
    }
]).directive("icswSelMan",
[
    "$rootScope", "ICSW_SIGNALS", "DeviceOverviewSettings",
    "icswActiveSelectionService", "icswDeviceTreeService",
(
    $rootScope, ICSW_SIGNALS, DeviceOverviewSettings,
    icswActiveSelectionService, icswDeviceTreeService
) ->
    # important: for icsw-sel-man to work the controller has to be specified separatedly (and not via overloading the link-function)
    # selection manager directive
    # selman=1 ... popup mode (show devices defined by attribute)
    # selman=0 ... single or multi device mode, depend on sidebar selection
    return {
        restrict: "A"
        priority: -100
        compile: (target_el, target_attrs) ->
            # console.log "comp selman"
            return {
                pre: (scope, el, attrs) ->
                    # console.log "pre selman"
                    # console.log "link selman to scope", scope
                    # is an active selection (listen to icswDeviceList)
                    _active_selection = if parseInt(attrs.icswSelMan) then true else false
                    # store selection list
                    scope.$icsw_selman_list  = []

                    scope.$on("$destroy", () ->
                        if ! _active_selection
                            icswActiveSelectionService.unregister_receiver()
                    )

                    _new_sel = (sel) ->
                        if scope.new_devsel?
                            scope.$icsw_selman_list.length = 0
                            for entry in sel
                                scope.$icsw_selman_list.push(entry)
                            # console.log "called new_devsel for", scope.$id
                            scope.new_devsel(scope.$icsw_selman_list)
                        else
                            console.warn "no new_devsel() function defined in scope", scope

                    _get_selection = () ->
                        # console.log "emit", scope.$id
                        # console.log "icsw_overview_emit_selection received"
                        if DeviceOverviewSettings.is_active()
                            console.warn "overlay is active"
                        else
                            _tree = icswDeviceTreeService.current()
                            if _tree?
                                # filter illegal selection elements
                                _new_sel(
                                    (_tree.all_lut[pk] for pk in icswActiveSelectionService.current().tot_dev_sel when _tree.all_lut[pk]?)
                                )
                            else
                                console.error "tree not valid, ignoring, triggering load"
                                icswDeviceTreeService.load(scope.$id).then(
                                    (tree) ->
                                )

                    if _active_selection
                        if attrs["icswSelectDevice"] != undefined
                            _tree = icswDeviceTreeService.current()
                            _device = _tree.all_lut[attrs["icswSelectDevice"]]

                            scope.new_devsel([_device])
                        # popup mode, watch for changes (i.e. tab activation)
                        else
                            scope.$watch(
                                attrs["icswDeviceList"]
                                (new_val) ->
                                    if new_val?
                                        _new_sel(new_val)
                            )
                    else
                        # register get_selection when selection changes
                        dereg = $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION_DTL"), (event) ->
                            _get_selection()
                        )
                        # very important: unregister $on
                        scope.$on("$destroy", () ->
                            dereg()
                        )
                        icswActiveSelectionService.register_receiver()
                        # get selection on the first run
                        _get_selection()
                # post: (scope, el, attrs) ->
                #    console.log "post selman"
            }
    }
]).directive("icswElementSize",
[
    "$parse",
(
    $parse
) ->
    # save size of element in scope (specified via icswElementSize)
    return (scope, element, attrs) ->
        fn = $parse(attrs["icswElementSize"])
        # console.log "fn=", fn
        scope.$watch(
            ->
                return {
                    width: element.width()
                    height: element.height()
                }
            (new_val) ->
                # console.log "F", new_val, element, element.outerHeight(), element.parent().height()
                fn.assign(scope, new_val)
            true
        )
]).service("ICSW_SIGNALS", [() ->
    _dict = {

        # global signals (for $rootScope)

        ICSW_ACLS_CHANGED: "icsw.acls.changed"
        # user login / logout
        ICSW_USER_LOGGEDOUT: "icsw.user.loggedout"
        ICSW_USER_LOGGEDIN: "icsw.user.loggedin"
        # device selection receiver registered / unregistered
        ICSW_DSR_REGISTERED: "icsw.dsr.registered"
        ICSW_DSR_UNREGISTERED: "icsw.dsr.unregistered"
        # breadcrumbs changed
        ICSW_BREADCRUMBS_CHANGED: "icsw.breadcrumbs.changed"
        # new state reached
        ICSW_STATE_CHANGED: "icsw.state.changed"
        ICSW_DEVICE_TREE_LOADED: "icsw.device.tree.loaded"
        ICSW_CATEGORY_TREE_LOADED: "icsw.category.tree.loaded"
        ICSW_NETWORK_TREE_LOADED: "icsw.network.tree.loaded"
        ICSW_CONFIG_TREE_LOADED: "icsw.config.tree.loaded"
        ICSW_DTREE_FILTER_CHANGED: "icsw.dtree.filter.changed"
        ICSW_FORCE_TREE_FILTER: "icsw.tree.force.filter"
        # device selector closed
        ICSW_SELECTION_BOX_CLOSED: "icsw.selection.box.closed"
        # selection changed
        ICSW_SELECTION_CHANGED: "icsw.selection.changed"
        # device tree loaded version
        ICSW_SELECTION_CHANGED_DTL: "icsw.selection.changed.dtl"
        # selection changed in overview
        ICSW_OVERVIEW_SELECTION_CHANGED: "icsw.overview.selection.changed"
        ICSW_MON_TREE_LOADED: "icsw.mon.tree.loaded"
        ICSW_OVERVIEW_EMIT_SELECTION: "icws.overview.emit.selection"
        ICSW_OVERVIEW_EMIT_SELECTION_DTL: "icws.overview.emit.selection.dtl"
        # sync state has changed (sync -> unsync, unsync -> sync)
        ICSW_SEL_SYNC_STATE_CHANGED: "icsw.sel.sync.state.changed"
        ICSW_SEL_SYNC_STATE_CHANGED_DTL: "icsw.sel.sync.state.changed.dtl"
        #recalculate panel layout when changed
        ICSW_TRIGGER_PANEL_LAYOUTCHECK: "icws.tools.panel_tools.panel_check"
        #setup and recalculate container max size layout
        ICSW_SVG_FULLSIZELAYOUT_SETUP: "icws.tools.panel_tools.fullsize_setup"
        ICSW_NETWORK_TAB_SELECTED: "icsw.network.tab.selected"
        ICSW_DEVICE_SCAN_CHANGED: "icsw.device.scan.changed"
        ICSW_MENU_PROGRESS_BAR_CHANGED: "icsw.menu.progress.bar.changed"
        ICSW_CONFIG_UPLOADED: "icsw.config.uploaded"
        ICSW_DOMAIN_NAME_TREE_CHANGED: "icsw.domain.name.tree.changed"
        ICSW_CATEGORY_TREE_CHANGED: "icsw.category.tree.changed"
        # settings changed
        ICSW_LOCATION_SETTINGS_CHANGED: "icsw.location.settings.changed"
        # gfx list updated
        ICSW_LOCATION_SETTINGS_GFX_UPDATED: "icsw.location.settings.gfx.updated"
        ICSW_USER_GROUP_TREE_LOADED: "icsw.user.group.tree.loaded"
        ICSW_USER_GROUP_TREE_CHANGED: "icsw.user.group.tree.changed"
        # fired when we add / remove a right to a role
        ICSW_USER_GROUP_ROLE_CHANGED: "icsw.user.group.role.changed"
        ICSW_PACKAGE_INSTALL_LIST_CHANGED: "icsw.package.install.list.changed"
        # license tree loaded
        ICSW_LICENSE_DATA_LOADED: "icsw.license.data.loaded"
        # route rights updated
        ICSW_ROUTE_RIGHTS_CHANGED: "icsw.route.rights.changed"
        # route rights updated, user and acls are invalid
        ICSW_ROUTE_RIGHTS_VALID: "icsw.route.rights.valid"
        # route rights updated, user and acls are valid
        ICSW_ROUTE_RIGHTS_INVALID: "icsw.route.rights.invalid"
        # send when fair-share tree is selected
        ICSW_RMS_FAIR_SHARE_TREE_SELECTED: "icsw.rms.fair.share.tree.selected"
        # overall style changed
        ICSW_OVERALL_STYLE_CHANGED: "icsw.overall.style.changed"
        # task settings changed
        ICSW_TASK_SETTINGS_CHANGED: "icsw.task.settings.changed"
        # icsw menu settings changed
        ICSW_MENU_SETTINGS_CHANGED: "icsw.menu.settings.changed"
        # open setup tasks changed
        ICSW_OPEN_SETUP_TASKS_CHANGED: "icsw.open.setup.tasks.changed"
        # livestatus pipeline modified
        ICSW_LIVESTATUS_PIPELINE_MODIFIED: "icsw.livestatus.pipeline.modified"

        # local signals (for local $emit / $on)

        _ICSW_DEVICE_CONFIG_CHANGED: "_icsw.device.config.changed"
        _ICSW_CLOSE_USER_GROUP: "_icsw.close.user.group"
        _ICSW_RMS_UPDATE_DATA: "_icsw.rms.update.data"
        _ICSW_RRD_CROPRANGE_SET: "_icsw.rrd.croprange.set"
        _ICSW_DEVICE_TABS_CHANGED: "_icsw.device.tabs.changed"
        _ICSW_CLOSE_CONFIG: "_icsw.close.config"
        _ICSW_DELETE_CONFIG: "_icsw.delete.config"
        _ICSW_UPDATE_MON_SELECTION: "_icsw.update.mon.selection"
        _ICSW_ROLE_ADD_PERMISSIONS: "_icsw.role.add.permissions"
    }
    _rev_dict = {}
    for key, value of _dict
        _rev_dict[value] = key

    return (name) ->
        if name == "ALL"
            return _dict
        else if name of _dict
            return _dict[name]
        else if name of _rev_dict
            return _rev_dict[name]
        else
            throw new Error("unknown signal '#{name}'")
]).factory("icswTools", [() ->
    id_seed = parseInt(Math.random() * 10000)

    get_unique_id = (prefix) ->
        id_seed++
        id = "unique-ID-#{prefix}-#{id_seed}"
        # console.log "emited unique id #{id}"
        return id

    return {
        get_unique_id: (prefix="obj") ->
            return get_unique_id(prefix)

        get_size_str: (size, factor, postfix) ->
            f_idx = 0
            while size > factor
                size = parseInt(size/factor)
                f_idx += 1
            factor = ["", "k", "M", "G", "T", "P", "E"][f_idx]
            return "#{size} #{factor}#{postfix}"

        build_lut: (in_list) ->
            lut = {}
            for value in in_list
                lut[value.idx] = value
            return lut

        merge_count_dict: (src_dict, add_dict) ->
            return _.mergeWith(
                src_dict
                add_dict
                (x, y) ->
                    if x?
                        return x + y
                    else
                        return y
            )
        order_in_place: (in_array, key_list, order_list) ->
            _tmp_list = _.orderBy(in_array, key_list, order_list)
            in_array.length = 0
            for entry in _tmp_list
                in_array.push(entry)

        remove_by_idx: (in_array, idx) ->
            for c_idx, val of in_array
                if val.idx == idx
                    c_idx = parseInt(c_idx)
                    rest = in_array.slice(c_idx + 1 || in_array.length)
                    in_array.length = if c_idx < 0 then in_array.length + c_idx else c_idx
                    in_array.push.apply(in_array, rest)
                    break

        get_diff_time_ms: (diff_ms) ->
            if diff_ms < 1000
                return "#{diff_ms}ms"
            else
                return "#{diff_ms / 1000}s"
    }
]).service("icswAjaxInfoService",
[
    "$window",
(
    $window
) ->
    class icswAjaxInfo
        constructor: (@top_div_name) ->
            @ajax_uuid = 0
            @ajax_dict = {}
            @top_div = undefined

        new_connection: (settings) =>
            cur_id = @ajax_uuid
            if not @top_div
                @top_div = $(@top_div_name)
            if not @top_div.find("ul").length
                @top_div.append($("<ul>"))
            ai_ul = @top_div.find("ul")
            title_str = settings.title or "pending..."
            # if $window.DEBUG
            #    title_str = "(#{cur_id}) #{title_str}"
            ai_ul.append(
                $("<li>").attr(
                    {
                        id: cur_id
                    }
                ).text(title_str)
            )
            @ajax_dict[cur_id] = {
                state: "pending"
                start: new Date()
            }
            @ajax_uuid++
            return cur_id

        close_connection: (xhr_id) =>
            if xhr_id?
                @ajax_dict[xhr_id]["state"]   = "done"
                @ajax_dict[xhr_id]["runtime"] = new Date() - @ajax_dict[xhr_id]["start"]
                @top_div.find("li##{xhr_id}").remove()
]).service("_icswCallAjaxService",
[
    "icswAjaxInfoService", "icswCSRFService", "$q", "icswInfoModalService", "$window",
(
    icswAjaxInfoService, icswCSRFService, $q, icswInfoModalService, $window,
) ->
    local_ajax_info = new icswAjaxInfoService("div#ajax_info")
    error_info_open = false
    default_ajax_dict =
        type: "POST"
        timeout: 50000
        dataType: "xml"
        headers: {}
        beforeSend: (xhr, settings) ->
            if not settings.hidden
                xhr.inituuid = local_ajax_info.new_connection(settings)
        complete: (xhr, textstatus) ->
            local_ajax_info.close_connection(xhr.inituuid)
        dataFilter: (data, data_type) ->
            return data
        error: (xhr, status, except) ->
            if status == "timeout"
                alert("timeout")
            else
                if xhr.status
                    if not error_info_open
                        error_info_open = true
                        icswInfoModalService(
                            "A critical error occured: #{xhr.statusText} (#{xhr.status})"
                            # wait for ten seconds
                            10000
                        ).then(
                            (done) ->
                                error_info_open = false
                                # reduce flicker
                                $(document.body).hide()
                                $window.location.reload()
                        )
            return false

    return (in_dict) ->
        _ret = $q.defer()
        for key of default_ajax_dict
            if key not of in_dict
                in_dict[key] = default_ajax_dict[key]
        #if "success" of in_dict and in_dict["dataType"] == "xml"
        #    console.log "s", in_dict["success"]
        icswCSRFService.get_token().then(
            (token) ->
                in_dict["headers"]["X-CSRFToken"] = token
                cur_xhr = $.ajax(in_dict)
                _ret.resolve(cur_xhr)
        )

        return _ret.promise

]).service("icswSimpleAjaxCall",
[
    "_icswCallAjaxService", "icswParseXMLResponseService", "$q",
(
    _icswCallAjaxService, icswParseXMLResponseService, $q
) ->
    return (in_dict) ->
        _def = $q.defer()
        if in_dict.ignore_log_level?
            ignore_log_level = true
            delete in_dict.ignore_log_level
        else
            ignore_log_level = false
        if in_dict.hidden?
            hidden = in_dict.hidden
            delete in_dict.hidden
        else
            hidden = false
        if in_dict.show_error?
            show_error = in_dict.show_error
            delete in_dict.show_error
        else
            show_error = true
        in_dict.success = (res) =>
            if in_dict.dataType == "json"
                _def.resolve(res)
            else
                if icswParseXMLResponseService(res, 40, show_error=show_error, hidden=hidden) or ignore_log_level
                    _def.resolve(res)
                else
                    _def.reject(res)
        _icswCallAjaxService(in_dict)

        return _def.promise
]).service("icswAccessLevelService",
[
    "ICSW_URLS", "ICSW_SIGNALS", "Restangular", "$q", "$rootScope",
    "icswSystemLicenseDataService",
(
    ICSW_URLS, ICSW_SIGNALS, Restangular, $q, $rootScope,
    icswSystemLicenseDataService,
) ->
    data = {}

    _changed = () ->
        $rootScope.$emit(ICSW_SIGNALS("ICSW_ACLS_CHANGED"), data)

    _reset = () ->
        data.global_permissions = {}
        # these are not permissions for single objects, but the merged permission set of all objects
        data.object_permissions = {}
        # license tree
        data.license_tree = {}
        # routing info
        data.routing_info = {}
        # acls are valid
        data.acls_are_valid = false

    _last_load = 0
    _reload_pending = false
    _acls_loaded = false

    reload = (force) ->
        if _reload_pending
            console.warn "reload pending in icswAccessLevelService"
            return
        cur_time = moment().unix()
        if Math.abs(cur_time - _last_load) < 5 and not force
            return
        _reload_pending = true
        $q.all(
            [
                Restangular.all(ICSW_URLS.USER_GET_GLOBAL_PERMISSIONS.slice(1)).customGET()
                icswSystemLicenseDataService.load("access_level")
                Restangular.all(ICSW_URLS.USER_GET_OBJECT_PERMISSIONS.slice(1)).customGET()
                Restangular.all(ICSW_URLS.MAIN_ROUTING_INFO.slice(1)).customGET()
            ]
        ).then(
            (r_data) ->
                _reload_pending = false
                _acls_loaded = true
                _last_load = moment().unix()
                data.global_permissions = r_data[0].plain()
                # console.log "************"
                # console.log "__authenticated" of data.global_permissions, data.global_permissions["__authenticated"]
                # console.log "************"
                data.license_tree = r_data[1]
                data.object_permissions = r_data[2].plain()
                data.routing_info = r_data[3].plain()
                # console.log data.routing_info.service_types
                data.acls_are_valid = data.global_permissions["__authenticated"]
                # console.log "Acls set, sending signal"
                _changed()
            (error) ->
                # console.log "NOT LOADED"
                _reset()
                _changed()
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), (event, user) ->
        # console.log "***", user
        reload(true)
    )

    _reset()

    # see lines 205 ff in backbone/models/user.py
    check_level = (obj, ac_name, mask, any) ->
        if ac_name.split(".").length != 3
            alert("illegal ac specifier '#{ac_name}'")
        #console.log ac_name, obj._GLOBAL_, obj.access_levels
        if obj and obj.access_levels?
            # object level permissions
            # no need to check for global permissions because those are mirrored down
            # to the object_level permission on the server
            if not obj._all
                obj._all = obj.access_levels
            if ac_name of obj._all
                if any
                    return if obj._all[ac_name] & mask then true else false
                else
                    return (obj._all[ac_name] & mask) == mask
            else
                return false
        else
            # check global permissions
            obj = data.global_permissions
            if ac_name of obj
                if any
                    if mask
                        return if obj[ac_name] & mask then true else false
                    else
                        return true
                else
                    return (obj[ac_name] & mask) == mask
            else
                return false

    has_menu_permission = (p_name) ->
        if p_name.split(".").length == 2
            p_name = "backbone.#{p_name}"
        _valid = p_name of data.global_permissions or p_name of data.object_permissions
        # if not _valid
        #    console.log "NV", p_name, _.keys(data.global_permissions), _.keys(data.object_permissions)
        return _valid

    has_service_type = (s_name) ->
        return s_name of data.routing_info.service_types

    has_valid_license = (license) ->
        if not data.acls_are_valid
            # not loaded yet
            return false
        return data.license_tree.license_is_valid(license)

    func_dict = {
        # functions to check permissions for single objects
        acl_delete: (obj, ac_name) ->
            return check_level(obj, ac_name, 4, true)

        acl_create: (obj, ac_name) ->
            return check_level(obj, ac_name, 2, true)

        acl_modify: (obj, ac_name) ->
            return check_level(obj, ac_name, 1, true)

        acl_read: (obj, ac_name) ->
            return check_level(obj, ac_name, 0, true)

        acl_any: (obj, ac_name, mask) ->
            return check_level(obj, ac_name, mask, true)

        acl_all: (obj, ac_name, mask) ->
            return check_level(obj, ac_name, mask, false)

        acl_valid: () ->
            return data.acls_are_valid

        # check if permission exists for any object (used for show/hide of entries of menu)
        has_menu_permission: has_menu_permission

        has_service_type: has_service_type

        has_any_menu_permission: (permissions) ->
            for p in permissions
                if has_menu_permission(p)
                    return true
            return false

        has_all_menu_permissions: (permissions) ->
            for p in permissions
                if not has_menu_permission(p)
                    return false
            return true

        has_valid_license: has_valid_license

        get_routing_info: () ->
            return data.routing_info

        has_any_valid_license: (licenses) ->
            for l in licenses
                if has_valid_license(l)
                    return true
            return false

        has_all_valid_licenses: (licenses) ->
            for l in licenses
                if not has_valid_license(l)
                    return false
            return true

        has_all_service_types: (stypes) ->
            for s in stypes
                if not has_service_type(s)
                    return false
            return true
    }

    return angular.extend(
        {
            install: (scope) ->
                angular.extend(scope, func_dict)
            reload: () ->
                reload(false)
        }
        func_dict
    )

]).service("initProduct",
[
    "ICSW_URLS", "Restangular",
(
    ICSW_URLS, Restangular
) ->
    product = {}
    Restangular.all(ICSW_URLS.USER_GET_INIT_PRODUCT.slice(1)).customGET().then(
        (new_data) ->
            # update dict in place
            angular.extend(product, new_data)
            product.menu_gfx_url = "#{ICSW_URLS.STATIC_URL}/#{new_data.name.toLowerCase()}-flat-trans.png"
            product.menu_gfx_big_url = "#{ICSW_URLS.STATIC_URL}/#{new_data.name.toLowerCase()}-trans.png"
    )
    return product

]).run([
    "Restangular", "toaster",
(
    Restangular, toaster
) ->
    Restangular.setRestangularFields(
        {
            id: "idx"
        }
    )
    Restangular.setResponseInterceptor((data, operation, what, url, response, deferred) ->
        if data.log_lines
            for entry in data.log_lines
                toaster.pop(
                    {
                        20: "success"
                        30: "warning"
                        40: "error"
                        50: "error"
                    }[entry[0]]
                    entry[1]
                    ""
                )
        if data._change_list
            $(data._change_list).each (idx, entry) ->
                toaster.pop("success", "", entry[0] + " : " + entry[1])
            delete data._change_list
        if data._messages
            $(data._messages).each (idx, entry) ->
                toaster.pop("success", "", entry)
        return data
    )

    Restangular.setErrorInterceptor((resp) ->
        error_list = []
        if typeof(resp.data) == "string"
            if resp.data
                resp.data = {
                    error: resp.data
                }
            else
                resp.data = {}
        for key, value of resp.data
            key_str = if key == "__all__" then "error: " else "#{key} : "
            if key != "_reset_list"
                if Array.isArray(value)
                    for sub_val in value
                        if sub_val.non_field_errors
                            error_list.push(key_str + sub_val.non_field_errors.join(", "))
                        else
                            error_list.push(key_str + String(sub_val))
                else
                    if (typeof(value) == "object" or typeof(value) == "string") and (not key.match(/^_/) or key == "__all__")
                        error_list.push(key_str + if typeof(value) == "string" then value else value.join(", "))
        new_error_list = []
        for _err in error_list
            if _err not in new_error_list
                new_error_list.push(_err)
                toaster.pop("error", _err, "")
        return true
    )
]).service("icswInfoModalService",
[
    "$q", "$timeout",
(
    $q, $timeout,
) ->
    return (info, timeout=0) ->
        if timeout
            info = "#{info}, closing in #{timeout / 1000} seconds"
        d = $q.defer()
        BootstrapDialog.show
            message: info
            draggable: true
            animate: false
            size: BootstrapDialog.SIZE_SMALL
            title: "Info"
            closable: false
            buttons: [
                {
                     icon: "glyphicon glyphicon-ok"
                     cssClass: "btn-success"
                     label: "Yes"
                     action: (dialog) ->
                        dialog.close()
                        d.resolve()
                },
            ]
            onshow: (dialog) ->
                if timeout
                    $timeout(
                        () ->
                            dialog.close()
                            d.resolve()
                        timeout
                    )
            iconshow: (modal) =>
                height = $(window).height() - 100
                modal.getModal().find(".modal-body").css("max-height", height)
        return d.promise
]).service("icswComplexModalService",
[
    "$q", "icswToolsSimpleModalService",
(
    $q, icswToolsSimpleModalService
) ->
    return (in_dict) ->
        # build buttons list
        buttons = []
        if in_dict.ok_callback
            buttons.push(
                {
                    label: if in_dict.ok_label? then in_dict.ok_label else "Modify"
                    icon: "fa fa-save"
                    cssClass: "btn-success"
                    action: (modal) ->
                        in_dict.ok_callback(modal).then(
                            (ok) ->
                                console.log "cms/modify/ok returned #{ok}"
                                modal.close()
                            (notok) ->
                                console.log "cms/modify/notok returned #{notok}"
                        )
                        return false
                }
            )
        if "show_delete_callback" of in_dict
            _sdc = in_dict.show_delete_callback
        else
            _sdc = true
        if in_dict.closeable?
            is_closeable = in_dict.closeable
        else
            is_closeable = false
        if in_dict.delete_callback and _sdc
            buttons.push(
                {
                    label: if in_dict.delete_label? then in_dict.delete_label else "Delete"
                    icon: "fa fa-remove"
                    cssClass: "btn-danger"
                    action: (modal) ->
                        d = $q.defer()
                        if in_dict.delete_ask?
                            icswToolsSimpleModalService("Really delete ?").then(
                                (ok) ->
                                    d.resolve("yes with ask")
                                (nto) ->
                                    d.reject("no with ask")
                            )
                        else
                            d.resolve("no ask")
                        d.promise.then(
                            (answer) ->
                                in_dict.delete_callback(modal).then(
                                    (ok) ->
                                        console.log "cms/delete/ok returned #{answer} / #{ok}"
                                        modal.close()
                                    (notok) ->
                                        console.log "cms/delete/notok returned #{answer} / #{notok}"
                                )
                        )
                        return false
                }
            )
        if in_dict.cancel_callback
            buttons.push(
                {
                    label: if in_dict.cancel_label? then in_dict.cancel_label else "Cancel"
                    hotkey: 27
                    icon: "fa fa-undo"
                    cssClass: "btn-warning"
                    action: (modal) ->
                        in_dict.cancel_callback(modal).then(
                            (ok) ->
                                console.log "cms/cancel/ok returned #{ok}"
                                modal.close()
                            (notok) ->
                                console.log "cms/cancel/notok returned #{notok}"
                        )
                        return false
                }
            )
        d = $q.defer()
        bs_dict = {
            message: in_dict.message
            draggable: true
            closeable: is_closeable
            size: BootstrapDialog.SIZE_WIDE
            animate: false
            title: in_dict.title or "ComplexModalDialog"
            cssClass: in_dict.css_class or "modal-tall"
            onshow: (modal) =>
                height = $(window).height() - 100
                modal.getModal().find(".modal-body").css("max-height", height)
                if in_dict.show_callback?
                    in_dict.show_callback(modal)
            onshown: (modal) =>
                if in_dict.shown_callback?
                    in_dict.shown_callback(modal)
            onhidden: (modal) =>
                if in_dict.hidden_callback?
                    in_dict.hidden_callback(modal)
                d.resolve("closed")
            buttons: buttons
        }
        if in_dict.closable?
            bs_dict.closable = true
        else
            bs_dict.closable = false
        BootstrapDialog.show bs_dict
        return d.promise

]).service("icswToolsSimpleModalService",
[
    "$q",
(
    $q
) ->
    return (question) ->
        d = $q.defer()
        BootstrapDialog.show
            message: question
            draggable: true
            animate: false
            size: BootstrapDialog.SIZE_SMALL
            title: "Please confirm"
            closable: false
            buttons: [
                {
                     icon: "glyphicon glyphicon-ok"
                     cssClass: "btn-success"
                     label: "Yes"
                     action: (dialog) ->
                        dialog.close()
                        d.resolve()
                },
                {
                    icon: "glyphicon glyphicon-remove"
                    label: "No"
                    keycode: 20
                    cssClass: "btn-danger"
                    action: (dialog) ->
                        dialog.close()
                        d.reject()
                },
            ]
            iconshow: (modal) =>
                height = $(window).height() - 100
                modal.getModal().find(".modal-body").css("max-height", height)
        return d.promise
]).service("icswToolsUUID", [() ->
    return () ->
        s4 = () -> Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
        uuid = "#{s4()}#{s4()}-#{s4()}-#{s4()}-#{s4()}-#{s4()}#{s4()}#{s4()}"
        return uuid
])

d3js_module = angular.module(
    "icsw.d3",
    []
).factory("d3_service",
[
    "$document", "$q", "$rootScope", "ICSW_URLS",
(
    $document, $q, $rootScope, ICSW_URLS,
) ->
    d = $q.defer()
    on_script_load = () ->
        $rootScope.$apply(
            () -> d.resolve(window.d3)
        )
    script_tag = $document[0].createElement('script')
    script_tag.type = "text/javascript"
    script_tag.async = true
    script_tag.src = ICSW_URLS.D3_MIN_JS
    script_tag.onreadystatechange = () ->
        if this.readyState == 'complete'
            on_script_load()
    script_tag.onload = on_script_load
    s = $document[0].getElementsByTagName('body')[0]
    s.appendChild(script_tag)
    return {
        d3: ()->
            return d.promise
    }
])

dimple_module = angular.module(
    "icsw.dimple", []
).factory("dimple_service",
[
    "$document", "$q", "$rootScope", "ICSW_URLS",
(
    $document, $q, $rootScope, ICSW_URLS,
) ->
    d = $q.defer()
    on_script_load = () ->
        $rootScope.$apply(
            () ->
                d.resolve(window.dimple)
        )
    script_tag = $document[0].createElement('script')
    script_tag.type = "text/javascript"
    script_tag.async = true
    script_tag.src = ICSW_URLS.DIMPLE_MIN_JS
    script_tag.onreadystatechange = () ->
        if this.readyState == 'complete'
            on_script_load()
    script_tag.onload = on_script_load
    s = $document[0].getElementsByTagName('body')[0]
    s.appendChild(script_tag)
    return {
        "dimple" : () ->
            return d.promise
    }
])


angular.module(
    "init.csw.filters", []
).filter(
    "ip_fixed_width", () ->
        return (in_str) ->
            if in_str
                ip_field = in_str.split(".")
            else
                ip_field = ["?", "?", "?", "?"]
            return ("QQ#{part}".substr(-3, 3) for part in ip_field).join(".").replace(/Q/g, "&nbsp;")
).filter(
    "range", () ->
        return (in_value, upper_value) ->
            return (_val for _val in [1..parseInt(upper_value)])
).filter(
    "yesno1", () ->
        return (in_value) ->
            return if in_value then "yes" else "---"
).filter(
    "yesno2", () ->
        return (in_value) ->
            return if in_value then "yes" else "no"
).filter(
    "yesno3", ["$sce", ($sce) ->
        return (in_value) ->
            if in_value
                _r_str = "<span class='label label-success'>yes</span>"
            else
                _r_str = "---"
            return $sce.trustAsHtml(_r_str)
]).filter(
    "yesno4", ["$sce", ($sce) ->
        return (in_value) ->
            if in_value
                _r_str = "<span class='label label-success'>yes</span>"
            else
                _r_str = "<span class='label label-warning'>no</span>"
            return $sce.trustAsHtml(_r_str)
]).filter("limit_text", () ->
    return (text, max_len, show_info) ->
        if text.length > max_len
            if show_info
                return text[0..max_len] + "... (#{max_len}/#{text.length})"
            else
                return text[0..max_len] + "..."
        else
            return text
).filter("limit_text_no_dots", () ->
    return (text, max_len) ->
        if text.length > max_len
            return text[0..max_len]
        else
            return text
).filter("datetime1", () ->
    return (cur_dt) ->
        return moment(cur_dt).format("ddd, D. MMM YYYY, HH:mm:ss") + ", " + moment(cur_dt).fromNow()
).filter("datetime_concise", () ->
    return (cur_dt) ->
        return moment(cur_dt).format("DD.MM.YYYY HH:mm:ss")
).filter("get_size", () ->
    return (size, base_factor, factor, postfix="B", float_digits=0) ->
        size = size * base_factor
        f_idx = 0
        while size > factor
            size = parseFloat(parseInt(size)/factor)
            f_idx += 1
        factor_pf = ["", "k", "M", "G", "T", "P", "E"][f_idx]
        if not float_digits
            size = parseInt(size)
        else
            size = "#{size}".substring(0, "#{parseInt(size)}".length + 1 + float_digits)
        return "#{size} #{factor_pf}#{postfix}"
).filter("props_filter", () ->
    return (items, props) ->
        if angular.isArray(items)
            out = []
            for item in items
                for prop in Object.keys(props)
                    text = props[prop].toLowerCase()
                    if item[prop].toString().toLowerCase().indexOf(text) != -1
                        out.push(item)
                        break
        else
            # not an array, ignore filter
            out = items
        return out
).service("icswCachingCall",
[
    "$interval", "$timeout", "$q", "Restangular",
(
    $inteval, $timeout, $q, Restangular
) ->

    class LoadInfo
        constructor: (@key, @url, @options) ->
            @client_dict = {}
            @client_pk_list = {}
            # initial value is null (== no filtering)
            @pk_list = null

        add_pk_list: (client, pk_list) =>
            if pk_list != null
                # got a non-null pk_list
                if @pk_list == null
                    # init pk_list if the list was still null
                    @pk_list = []
                @pk_list = _.uniq(@pk_list.concat(pk_list))
            @client_pk_list[client] = pk_list
            _defer = $q.defer()
            @client_dict[client] = _defer
            return _defer

        load: () =>
            opts = {}
            for key, value of @options
                if value == "<PKS>"
                    if @pk_list != null
                        # only set options when pk_list was not null
                        opts[key] = angular.toJson(@pk_list)
                else
                    opts[key] = value
            Restangular.all(@url.slice(1)).getList(opts).then(
                (result) =>
                    for c_id, _defer of @client_dict
                        _c_pk_list = @client_pk_list[c_id]
                        if !_c_pk_list or _c_pk_list.length == @pk_list.length
                            _defer.resolve(result)
                        else
                            local_result = []
                            for _pk_res in _.zip(@pk_list, result)
                                if _pk_res[0] in _c_pk_list
                                    local_result.push(_pk_res[1])
                            _defer.resolve(local_result)
                    @client_dict = {}
                    @pk_list = null
            )
    start_timeout = {}
    load_info = {}

    schedule_load = (key, schedule_wait_timeout) ->
        # called when new listeners register
        # don't update immediately, wait until more controllers have registered
        if start_timeout[key]?
            $timeout.cancel(start_timeout[key])
            delete start_timeout[key]
        if schedule_wait_timeout
            # schedule_wait_timeout given, delay by given timespan
            if not start_timeout[key]?
                start_timeout[key] = $timeout(
                    () ->
                        load_info[key].load()
                    schedule_wait_timeout
                )
        else
            # no delay given, load immediately
            load_info[key].load()

    add_client = (client, url, options, pk_list) ->
        # create unique key
        url_key = _key(url, options, pk_list)
        if url_key not of load_info
            # init load info if not already present
            load_info[url_key] = new LoadInfo(url_key, url, options)
        # add pk list to current LoadInfo
        return load_info[url_key].add_pk_list(client, pk_list)

    _key = (url, options, pk_list) ->
        url_key = url
        for key, value of options
            url_key = "#{url_key},#{key}=#{value}"
        if pk_list == null
            # distinguish calls with pk_list == null (all devices required)
            url_key = "#{url_key}Z"
        return url_key

    return {
        fetch: (client, url, options, pk_list, schedule_wait_timeout=0) ->
            _defer = add_client(client, url, options, pk_list)
            schedule_load(_key(url, options, pk_list), schedule_wait_timeout)
            return _defer.promise
    }
]).service("icswTreeBase",
[
    "Restangular", "ICSW_URLS", "gettextCatalog", "icswSimpleAjaxCall", "$q",
    "icswCachingCall", "$rootScope", "ICSW_SIGNALS", "icswTools",
(
    Restangular, ICSW_URLS, gettextCatalog, icswSimpleAjaxCall, $q,
    icswCachingCall, $rootScope, ICSW_SIGNALS, icswTools,
) ->
    class icswTreeBase
        constructor: (@name, @tree_class, @rest_map, @signal, @clear_signal=undefined) ->
            @_result = undefined
            @_load_called = false
            @_cancel_load = false
            @_fetch_dict = {}
            @_call_dict = {
                load: 0
                fetch: 0
                reload: 0
            }

        # public fnuctions
        reload: (client) =>
            @_call_dict.reload++
            return @load_data(client).promise

        load: (client) =>
            if @_load_called
                @_call_dict.fetch++
                return @fetch_data(client).promise
            else
                @_call_dict.load++
                return @load_data(client).promise

        is_valid: () =>
            # returns true if the result is already set
            if @_result?
                return true
            else
                return false

        # to be overridden
        extra_calls: (client) =>
            return []
            
        # accessor functions
        get_result: () =>
            return @_result
        
        # clear_result
        clear_result: () =>
            @_result = undefined
            @_load_called = false
            if @signal
                if @clear_signal?
                    $rootScope.$emit(ICSW_SIGNALS(@clear_signal), @_result)
                else
                    $rootScope.$emit(ICSW_SIGNALS(@signal), @_result)

        cancel_pending_load: () =>
            if @_load_called
                @_cancel_load = true

        # public get_load_signal function
        get_load_signal: (result) =>
            return @signal

        # function to determine signal to send after load, needed for unauthenticated user get
        _get_load_signal: (result) =>
            if @signal
                return @get_load_signal(result)
            else
                return null

        # private functions
        load_data: (client) =>
            @_load_called = true
            if angular.isArray(@rest_map[0])
                # full map
                _rest_calls = (
                    icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in @rest_map
                )
            else
                # simple map, no options
                _rest_calls = (
                    icswCachingCall.fetch(client, _entry, {}, []) for _entry in @rest_map
                )
            _wait_list = _.concat(
                _rest_calls
                @extra_calls(client)
            )
            _start = new Date().getTime()
            @_load_defer = $q.defer()
            $q.all(_wait_list).then(
                (data) =>
                    _map_len = @rest_map.length
                    _tot_len = _wait_list.length
                    _extra_len = _tot_len - _map_len
                    _end = new Date().getTime()
                    # runtime in milliseconds
                    #noinspection JSUnresolvedVariable
                    _run_time = icswTools.get_diff_time_ms(_end - _start)
                    console.log " -> #{@name} loaded in #{_run_time} (#{_map_len} + #{_extra_len})"
                    if @_cancel_load
                        # load should be canceled, for forced logout for instance
                        @_cancel_load = false
                    else
                        # result already set, update result
                        if @_result?
                            @update_result(data...)
                        else
                            @init_result(data...)
                        if @new_data_set?
                            @new_data_set()
                        @send_results()
                        # signal if required
                        _send_signal = @_get_load_signal(@_result)
                        if _send_signal
                            # console.log "emit", _send_signal, @_result
                            $rootScope.$emit(ICSW_SIGNALS(_send_signal), @_result)
            )
            return @_load_defer

        init_result: (args...) =>
            @_result = new @tree_class(args...)

        update_result: (args...) =>
            @_result.update(args...)

        send_results: () =>
            @_load_defer.resolve(@_result)
            for client of @_fetch_dict
                # resolve clients
                @_fetch_dict[client].resolve(@_result)
            # reset fetch_dict
            @_fetch_dict = {}

        fetch_data: (client) =>
            if client not of @_fetch_dict
                # register client
                _defer = $q.defer()
                @_fetch_dict[client] = _defer
            if @_result
                # resolve immediately
                @_fetch_dict[client].resolve(@_result)
            return @_fetch_dict[client]

]).filter('capitalize', [() ->
    return (input, all) ->
        if (!!input)
            return input.replace(/([^\W_]+[^\s-]*) */g, (txt) -> return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase())
]).directive("icswToolsAccordionChevron",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.tools.accordion.chevron")
        scope: {
            flag: "=icswFlag"
        }
    }
]).service("icswLanguageTool",
[
    "$translate",
(
    $translate,
) ->
    def_lang = $translate.use().split("-")[0]
    if def_lang not in ["en", "de"]
        def_lang = "en"

    def_lang = "en"

    return {
        get_lang: () ->
            return def_lang
    }
]).service("icswFormTools",
[
    "toaster",
(
    toaster,
) ->
    show_form_error = (form) ->
        _errors = []
        for _why, value of form.$error
            for entry in value
                _errors.push("<li>#{_why}: #{entry.$name}</li>")

        _pf = if _errors.length > 1 then "s" else ""
        toaster.pop(
            {
                type: "warning"
                title: "#{_errors.length} form validation problem#{_pf}"
                body: "<ul>" + _errors.join("") + "</ul>"
                bodyOutputType: "trustedHtml"
            }
        )

    check_form = (form, wait_defer) ->
        if form.$invalid
            show_form_error(form)
            if wait_defer?
                wait_defer.reject("form not valid")
            return false
        else
            return true

    return {
        show_form_error: (form) ->
            return show_form_error(form)

        check_form: (form, wait_defer) ->
            return check_form(form, wait_defer)
    }

]).service("icswWebSocketService",
[
    "$q", "$window",
(
    $q, $window,
) ->
    get_url = (model_name) ->
        return "ws://#{$window.location.host}/icsw/ws/#{model_name}/"

    register_ws = (model_name) ->
        ws = new WebSocket(get_url(model_name))
        return ws

    return {
        register_ws: register_ws
    }
])
