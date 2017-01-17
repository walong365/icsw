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
    "$timeout", "icswComplexModalService", "$controller",
    "$rootScope", "$compile", "$templateCache", "$q",
(
    $timeout, icswComplexModalService, $controller,
    $rootScope, $compile, $templateCache, $q,
) ->
    OV_STRUCT = {
        monitoring: {
            ctrl: "icswMonitoringControlInfoCtrl"
            template: "icsw.monitoring.control.info"
            title: "Monitoring control"
        }
    }
    @show_overlay = ($event, name) ->
        $event.preventDefault()
        $event.stopPropagation()
        if not _.some(entry.name == name for entry in @struct.open)
            _def = OV_STRUCT[name]
            # check rights ?
            @struct.open.push({name: name})
            sub_scope = $rootScope.$new(true)
            $controller(_def.ctrl, {$scope: sub_scope})
            msg = $compile($templateCache.get(_def.template))(sub_scope)
            icswComplexModalService(
                title: _def.title
                message: msg
                closeable: true
                ok_label: "close"
                ok_callback: () ->
                    _defer = $q.defer()
                    _defer.resolve("close")
                    return _defer.promise
            ).then(
                (done) =>
                    # console.log @
                    sub_scope.$destroy()
                    _.remove(@struct.open, (entry) -> return entry.name == name)
            )
            @struct.menu_open = false

    @$onInit = () ->
        @struct = {
            open: []
            menu_open: false
        }
    return null
])
