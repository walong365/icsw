# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

# livestatus connector components

angular.module(
    "icsw.livestatus.comp.connect",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).service("icswMonLivestatusConnector",
[
    "$q", "$rootScope", "$injector",
(
    $q, $rootScope, $injector,
) ->
    # creates a DisplayPipeline
    class icswMonLivestatusConnector
        constructor: (name, spec) ->
            @setup_ok = false
            @name = name
            # connection specification as text
            @spec_src = spec
            console.log "Connector #{@name} (spec: #{@spec_src})"
            @root_element = undefined
            @resolve()

        resolve: () =>
            # dict element name -> service
            elements = {}

            # simple iteratee for resolving

            _resolve_iter = (in_obj, depth=0) =>
                if _.keys(in_obj).length != 1
                    console.error in_obj
                    throw new Error("Only one element allowed at any level")
                for key, value of in_obj
                    if key not of elements
                        # console.log key, depth
                        elements[key] = $injector.get(key)
                    for _el in value
                        _resolve_iter(_el, depth+1)

            # list of display elements
            @display_elements = []
            # build dependencies
            el_idx = 0
            _build_iter = (in_obj, depth=0) =>
                for key, value of in_obj
                    el_idx++
                    node = new elements[key]()
                    node.link_with_connector(@, el_idx)
                    if node.has_template
                        @display_elements.push(node)
                    if depth == 0
                        @root_element = node
                        @root_element.check_for_emitter()
                    for _el in value
                        node.add_child_node(_build_iter(_el, depth+1))
                return node
                    
            # interpret and resolve spec_src
            @spec_json = angular.fromJson(@spec_src)
            # resolve elements
            _resolve_iter(@spec_json)
            # build tree
            _build_iter(@spec_json)
            @init_gridster()
            
            @setup_ok = true
            
        init_gridster: () =>
            @gridsterOpts = {
                columns: 6
                pushing: true
                floating: true
                swapping: false
                width: 'auto'
                colWidth: 'auto'
                rowHeight: '200'
                margins: [4, 4]
                outerMargin: true
                isMobile: true
                mobileBreakPoint: 600
                mobileModeEnabled: true
                minColumns: 1
                minRows: 2
                maxRows: 100,
                defaultSizeX: 2
                defaultSizeY: 1
                minSizeX: 1
                maxSizeX: null
                minSizeY: 1
                maxSizeY: null
                resizable: {
                   enabled: true,
                   handles: ["n", 'w', 'ne', 'se', 'sw', 'nw']
                   stop: (event, element, options) =>
                       @ps_changed()
                }
                draggable: {
                   enabled: true
                   handle: '.my-class'
                   stop: (event, element, options) =>
                       @ps_changed()
                }
            }

        ps_changed: () =>
            console.log "psc"
            
        new_devsel: (devs) =>
            # start loop
            console.log @root_element, "*"
            @root_element.new_devsel(devs)
]).directive("icswConnectElementDisplay",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "E"
        scope:
            con_element: "=icswConnectElement"
        controller: "icswConnectElementCtrl"
        link: (scope, element, attrs) ->
            _outer = $templateCache.get("icsw.connect.element")
            _content = scope.con_element.template
            console.log "C=", scope.con_element
            _template_content = _outer + _content + "</div></div>"
            element.append($compile(_template_content)(scope))
            #scope.$on('gridster-item-initialized', ($event, element) ->
            #    console.log "init", element, element.row, element.col
            #)

    }
]).controller("icswConnectElementCtrl", [
    "$scope", "icswRouteHelper", "$templateCache", "$compile", "$q",
    "$state",
(
    $scope, icswRouteHelper, $templateCache, $compile, $q,
    $state,
) ->
    $scope.close = () ->
        $scope.con_element.close()

])
