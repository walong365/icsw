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
    "icsw.layout.routing",
    [
        "ui.router",
    ]
).config(["$stateProvider", "$urlRouterProvider",
    ($stateProvider, $urlRouterProvider) ->
        $urlRouterProvider.otherwise("/login")
        $stateProvider.state(
            "login"
            {
                url: "/login",
                templateUrl: "icsw/login.html"
                data:
                    pageTitle: "ICSW Login"
            }
        ).state(
            "logout"
            {
                url: "/logout",
                templateUrl: "icsw/login.html"
                data:
                    pageTitle: "ICSW Logout"
            }
        ).state(
            "main",
            {
                url: "/main"
                abstract: true
                templateUrl: "icsw/main.html"
                data:
                    pageTitle: "ICSW Main page"
                resolve:
                    user: ["$q", "icswUserService", ($q, icswUserService) ->
                        _defer = $q.defer()
                        icswUserService.load().then(
                            (user) ->
                                if user.idx
                                    _defer.resolve(user)
                                else
                                    _defer.reject(user)
                        )
                        return _defer.promise
                    ]
            }
        ).state(
            "simple1"
            {
                url: "/simple1"
                template: '
<div class="col-md-4 col-xs-12 col-lg-6">
    <div icsw-device-livestatus-fullburst icsw-element-size="size" ls-devsel="ls_devsel" ls-filter="ls_filter"></div>
</div>
<div class="col-md-4 col-xs-12 col-lg-6">
    <div icsw-device-livestatus-maplist ls-devsel="ls_devsel" ls-filter="ls_filter"></div>
</div>
<div class="col-md-4 col-xs-12 col-lg-8">
    <icsw-config-category-location-show ls-devsel="ls_devsel" ls-filter="ls_filter"></icsw-config-category-location-show>
</div>
<div class="col-md-4 col-xs-12 col-lg-2">
    <icsw-device-livestatus-cat-tree ls-filter="ls_filter"></icsw-device-livestatus-cat-tree>
</div>
<div class="col-md-4 col-xs-12 col-lg-8">
    <icsw-device-livestatus-table-view ls-filter="ls_filter" filtered-entries="filtered_entries" ls-devsel="ls_devsel"></icsw-device-livestatus-table-view>
</div>
'
            }
        ).state(
            "simple2",
            {
                url: "/simple2"
                template: '
<div class="col-md-4 col-xs-12 col-lg-6">
    <div icsw-device-livestatus-fullburst icsw-element-size="size" ls-devsel="ls_devsel" ls-filter="ls_filter"></div>
</div>
<div class="col-md-4 col-xs-12 col-lg-6">
    <div icsw-device-livestatus-maplist ls-devsel="ls_devsel" ls-filter="ls_filter"></div>
</div>
<div class="col-md-4 col-xs-12 col-lg-8">
    <icsw-device-livestatus-table-view ls-filter="ls_filter" filtered-entries="filtered_entries" ls-devsel="ls_devsel"></icsw-device-livestatus-table-view>
</div>
<div class="col-md-4 col-xs-12 col-lg-2">
    <icsw-device-livestatus-cat-tree ls-filter="ls_filter"></icsw-device-livestatus-cat-tree>
</div>
'
            }
        )
]).directive('updateTitle', ['$rootScope', '$timeout', ($rootScope, $timeout) ->
    return {
        link: (scope, el) ->
            listener = (event, to_state) ->
                title = "ICSW page"
                if to_state.data && to_state.data.pageTitle
                    title = to_state.data.pageTitle

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
