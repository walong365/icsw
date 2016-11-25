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

""" routing component of ICSW """

menu_module = angular.module(
    "icsw.layout.routing",
    [
        "ui.router"
    ]
).config([
    "$stateProvider", "$urlRouterProvider", "icswRouteExtensionProvider",
(
    $stateProvider, $urlRouterProvider, icswRouteExtensionProvider,
) ->
    $urlRouterProvider.otherwise("/login")
    icswRouteExtensionProvider.add_route("login")
    icswRouteExtensionProvider.add_route(
        "main"
        {
            user: ["$q", "icswUserService", "icswRouteHelper", "$state", ($q, icswUserService, icswRouteHelper, $state) ->
                _defer = $q.defer()
                icswUserService.load("router").then(
                    (user) ->
                        if user.user.idx
                            # check rights, acls might still be missing, TODO, Fixme ...
                            # console.log "CR", user, icswRouteHelper.check_rights(user)
                            icswRouteHelper.check_rights(user)
                            _defer.resolve(user)
                        else
                            $state.go("login")
                            _defer.reject(user)
                )
                return _defer.promise
            ]
        }
    )
    icswRouteExtensionProvider.add_route("logout")
]).controller("icswMainCtrl",
[
    "$scope", "hotkeys", "icswLayoutSelectionDialogService", "icswUserService",
    "$rootScope", "ICSW_SIGNALS", "icswRouteHelper", "icswSystemLicenseDataService",
    "icswBreadcrumbs", "$state", "$window", "Restangular", "ICSW_URLS", "icswThemeService",
    "icswMenuSettings",
(
    $scope, hotkeys, icswLayoutSelectionDialogService, icswUserService,
    $rootScope, ICSW_SIGNALS, icswRouteHelper, icswSystemLicenseDataService,
    icswBreadcrumbs, $state, $window, Restangular, ICSW_URLS, icswThemeService,
    icswMenuSettings,
) ->
    _bind_keys = () ->
        hotkeys.bindTo($scope).add(
            # combo: "ctrl+h"
            combo : "f1"
            #description: "Show Help"
            helpVisible: false
            allowIn: ["INPUT", "SELECT", "TEXTAREA"]
            callback: (event) ->
                event.preventDefault()
                hotkeys.toggleCheatSheet()
        ).add(
            combo: "ctrl+s"
            allowIn: ["INPUT", "SELECT", "TEXTAREA"]
            description: "Show Device Selection"
            callback: (event) ->
                event.preventDefault()
                icswLayoutSelectionDialogService.quick_dialog()
        # ).add(
        #    combo: "ctrl"
        #    allowIn: ["INPUT", "SELECT", "TEXTAREA"]
        #    description: "Toggle Theme"
        #    callback: (event) ->
        #        event.preventDefault()
        #        icswThemeService.toggle()
        ).add(
            combo: "f2"
            allowIn: ["INPUT", "SELECT", "TEXTAREA"]
            description: "Toggle Theme"
            callback: (event) ->
                event.preventDefault()
                icswThemeService.toggle()
        ).add(
            combo: "f4"  # F3 for select tasks
            allowIn: ["INPUT", "SELECT", "TEXTAREA"]
            description: "Show/Hide Menu Help"
            callback: (event) ->
                event.preventDefault()
                icswMenuSettings.set_menu_help(!icswMenuSettings.get_menu_help())
        )

    $scope.struct = {
        current_user: undefined
        route_counter: 0
        # device tree is valid ?
        device_tree_valid: false
    }

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_SELECTION_BOX_CLOSED"), () ->
        # rebind keys to reenable ctrl-s
        _bind_keys()
    )

    _bind_keys()

    _wait_dict = {}
    $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), () ->
        $scope.struct.device_tree_valid = true
        for sig_name, flag of _wait_dict
            dtl_func_name = "#{sig_name}_DTL"
            # console.log "delayed emit of #{dtl_func_name}"
            $rootScope.$emit(ICSW_SIGNALS(dtl_func_name))
        # clear wait dict
        _wait_dict = {}
    )
    # get a list of all signals with the domain_tree_loaded postfix
    dtl_func_names = (key for key, value of ICSW_SIGNALS("ALL") when key.match(/_DTL$/))
    for dtl_func_name in dtl_func_names
        # unsafe name
        _unsafe_name = _.replace(dtl_func_name, "_DTL", "")
        # not waiting for this signal
        _wait_dict[_unsafe_name] = false
        $rootScope.$on(ICSW_SIGNALS(_unsafe_name), (event) ->
            _unsafe_name = ICSW_SIGNALS(event.name)
            dtl_func_name = "#{_unsafe_name}_DTL"
            # console.log "got", _unsafe_name, dtl_func_name, event
            if $scope.struct.device_tree_valid
                # tree is valid, emit safe signal
                # console.log "synced emit of #{dtl_func_name}"
                $rootScope.$emit(ICSW_SIGNALS(dtl_func_name))
            else
                # not loaded, store
                _wait_dict[_unsafe_name] = true
        )

    $scope.$on("$stateChangeStart", (event, to_state, to_params, from_state, from_params, options) ->
        console.log "tp", to_params
        if options.icswRegister?
            # copy to to_params
            to_params.icswRegister = options.icswRegister
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "$stateChangeStart from '#{from_state.name}' (#{from_main}) to '#{to_state.name}' (#{to_main})"
        if to_main and not from_main
            if to_state.icswData? and not to_state.icswData.$$allowed
                console.error "target state not allowed", to_state.icswData.$$allowed, $scope.struct.current_user
                event.preventDefault()
                $state.go("login")

    )

    $scope.$on("$stateChangeSuccess", (event, to_state, to_params, from_state, from_params) ->
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "$stateChangeSuccess from '#{from_state.name}' (#{from_main}) to '#{to_state.name}' (#{to_main})"
        $scope.struct.route_counter++
        Restangular.all(
            ICSW_URLS.SESSION_REGISTER_RC.slice(1)
        ).post(
            {
                from: from_state.name
                to: to_state.name
            }
        ).then(
            (res) ->
        )
        if to_state.name == "logout"
            # ignore
            true
        else if not from_main and to_main
            _helper = icswRouteHelper.get_struct()
            # todo, unify rights checking
            # console.log _helper.valid
            # if $scope.struct.current_user? and $state.current.icswData?
            #    if not $state.current.icswData.$$allowed
            #        _to_state = "main.dashboard"
            #        console.error "target state #{to_state.name} not allowed, going to #{_to_state}"
            #        $state.go(_to_state)
            # console.log to_params, $scope
        else
            # we allow one gentle transfer
            if $scope.struct.route_counter >= 2 and not icswSystemLicenseDataService.fx_mode()
                # reduce flicker
                $(document.body).hide()
                $window.location.reload()

        if to_main
            if to_params.icswRegister? and not to_params.icswRegister
                # to not register statechange from breadcrumb line
                true
            else
                icswBreadcrumbs.add_state(to_state)
            $rootScope.$emit(ICSW_SIGNALS("ICSW_STATE_CHANGED"))
    )

    $scope.$on("$stateChangeError", (event, to_state, to_params, from_state, from_params, error) ->
        console.error "error moving to state #{to_state.name} (#{to_state}), error is #{error}"
        $state.go("login")
    )
]).directive('icswUpdateTitle',
[
    '$rootScope', '$timeout',
(
    $rootScope, $timeout
) ->
    return {
        link: (scope, el) ->
            listener = (event, to_state) ->
                title = "ICSW page"
                if to_state.icswData? and to_state.icswData.pageTitle
                    title = to_state.icswData.pageTitle

                $timeout(
                    ()->
                        el.text(title)
                    0
                    false
                )
            $rootScope.$on("$stateChangeSuccess", listener)
    }
])
