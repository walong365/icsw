# Copyright (C) 2017 init.at
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
    "icsw.layout.widgets",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).component("icswWidget", {
    template: ["$templateCache", ($templateCache) -> return $templateCache.get("icsw.layout.widgets")]
    controller: "icswWidgetCtrl as ctrl"
    bindings: {}
}).controller("icswWidgetCtrl",
[
    "$timeout", "icswComplexModalService", "$controller", "$injector",
    "$rootScope", "$compile", "$templateCache",
(
    $timeout, icswComplexModalService, $controller, $injector,
    $rootScope, $compile, $templateCache,
) ->

    @show_overlay = ($event, name) ->
        if name not in @struct.open
            # check rights ?
            @struct.open.push(name)
            # console.log $injector.get("icswMonitoringControlInfoCtrl")
            sub_scope = $controller("icswMonitoringControlInfoCtrl", {$scope: $rootScope.$new(true)})
            msg = $compile($templateCache.get("icsw.monitoring.control.info"))(sub_scope)
            icswComplexModalService(
                message: msg
            )
            console.log "so", name

    @$onInit = () ->
        @struct = {
            open: []
        }
        console.log "WC"
    return null
])
