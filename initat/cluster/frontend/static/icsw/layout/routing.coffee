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
    $stateProvider.state(
        "login"
        {
            url: "/login",
            templateUrl: "icsw/login.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "ICSW Login"
        }
    ).state(
        "logout"
        {
            url: "/logout",
            templateUrl: "icsw/logout.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "ICSW Logout"
        }
    ).state(
        "main",
        {
            url: "/main"
            abstract: true
            templateUrl: "icsw/main.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "ICSW Main page"
            resolve:
                user: ["$q", "icswUserService", "icswRouteHelper", ($q, icswUserService, icswRouteHelper) ->
                    _defer = $q.defer()
                    icswUserService.load("router").then(
                        (user) ->
                            if user.user.idx
                                # check rights, acls might still be missing, TODO, Fixme ...
                                icswRouteHelper.check_rights(user)
                                _defer.resolve(user)
                            else
                                _defer.reject(user)
                    )
                    return _defer.promise
                ]
            # hotkeys: [
            #     ["s", "Show device selection", "show devsel"]
            # ]
            controller: "icswMainCtrl"
        }
    )
]).controller("icswMainCtrl", [
    "$scope", "hotkeys", "icswLayoutSelectionDialogService", "icswUserService",
    "$rootScope", "ICSW_SIGNALS", "icswRouteHelper", "icswSystemLicenseDataService",
    "icswBreadcrumbs",
(
    $scope, hotkeys, icswLayoutSelectionDialogService, icswUserService,
    $rootScope, ICSW_SIGNALS, icswRouteHelper, icswSystemLicenseDataService,
    icswBreadcrumbs,
) ->
    hotkeys.bindTo($scope).add(
        combo: "s"
        description: "Show device selection"
        callback: () ->
            icswLayoutSelectionDialogService.quick_dialog()
    ).add(
        combo: "ctrl+h"
        description: "Show help"
        allowIn: ["INPUT", "SELECT", "TEXTAREA"]
        callback: (event) ->
            hotkeys.toggleCheatSheet()
            event.preventDefault()
    )
    $scope.struct = {
        current_user: undefined
        route_counter: 0
    }

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        $scope.struct.current_user = icswUserService.get()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDOUT"), () ->
        $scope.struct.current_user = undefined
    )

    $scope.$on("$stateChangeStart", (event, to_state, to_params, from_state, from_params, options) ->
        if options.icswRegister?
            # copy to to_params
            to_params.icswRegister = options.icswRegister
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "$stateChangeStart from '#{from_state.name}' (#{from_main}) to '#{to_state.name}' (#{to_main})"
        if to_main and not from_main
            if to_state.icswData? and not to_state.icswData.$$allowed and $scope.struct.current_user.is_authenticated()
                console.error "target state not allowed", to_state.icswData.$$allowed, $scope.struct.current_user
                event.preventDefault()
    )

    $scope.$on("$stateChangeSuccess", (event, to_state, to_params, from_state, from_params) ->
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "$stateChangeSuccess from '#{from_state.name}' (#{from_main}) to '#{to_state.name}' (#{to_main})"
        $scope.struct.route_counter++
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
        console.log "tm", to_main
        if to_main
            if to_params.icswRegister? and not to_params.icswRegister
                # to not register statechange from breadcrumb line
                true
            else
                icswBreadcrumbs.add_state(to_state)
    )
    $scope.$on("$stateChangeError", (event, to_state, to_params, from_state, from_params, error) ->
        console.error "error moving to state #{to_state.name} (#{to_state}), error is #{error}"
        _to_login = true
        if to_state.icswData?
            if to_state.icswData.redirectToFromOnError
                _to_login = false
        if _to_login
            $state.go("login")
        else
            $state.go(from_state, from_params)
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
                if to_state.icswData && to_state.icswData.pageTitle
                    title = to_state.icswData.pageTitle

                $timeout(
                    ()->
                        el.text(title)
                    0
                    false
                )
            $rootScope.$on("$stateChangeSuccess", listener)
    }
]).run(["$window", ($window) ->
      window = angular.element($window)
      window.on("beforeunload", (event) ->
           # not working ...
           # event.preventDefault()
      )
])
