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
).service("icswMonLivestatusPipeBase",
[
    "$q", "$rootScope",
(
    $q, $rootScope,
) ->
    class icswMonLivestatusPipeBase
        # use __dp_ as prefix for quasi-private attributes
        constructor: (@name, @is_receiver, @is_emitter) ->
            @__dp_has_template = false
            # parent element
            @__dp_parent = undefined
            # notifier for downstream elements
            if @is_emitter
                @notifier = $q.defer()
                @__dp_childs = []
            console.log "init #{@name} (recv: #{@is_receiver}, emit: #{@is_emitter})"

        close: () =>
            # called on destroy
            if @pipeline_pre_close?
                @pipeline_pre_close()
            @notifier.reject("pipeline stop")

        # set template
        set_template: (template, title, size_x=4, size_y=4) =>
            @__dp_has_template = true
            # template content, not URL
            @__dp_template = template
            @__dp_raw_title = title
            @sizeX = size_x
            @sizeY = size_y

        build_title: () =>
            title = @__dp_raw_title
            if @__dp_parent
                title = "#{title} from #{@__dp_parent.__dp_element_id}"
            if @__dp_childs
                title = "#{title} to " + (entry.__dp_element_id for entry in @__dp_childs).join(", ")
            @__dp_title = title

        # santify checks
        check_for_emitter: () =>
            if not @is_emitter or @is_receiver
                throw new error("node is not an emitter but a receiver")

        feed_data: (mon_data) ->
            # feed data, used to insert data into the pipeline
            # console.log "fd", mon_data
            @notifier.notify(mon_data)

        add_child_node: (node) ->
            if not @is_emitter
                throw new error("Cannot add childs to non-emitting element")
            @__dp_childs.push(node)
            node.link_to_parent(@, @notifier)

        new_data_received: (new_data) =>
            console.error "new data received, to be overwritten", new_data
            return new_data
            
        pipeline_resolve_called: (resolved) =>
            console.error "resolve called #{resolved} for #{@name}"

        pipeline_reject_called: (rejected) =>
            console.error "reject called #{rejected} for #{@name}"

        # link with connector
        link_with_connector: (@connector, id, depth) =>
            @__dp_element_id = id
            @__dp_depth = depth

        link_to_parent: (parent, parent_not) ->
            @__dp_parent = parent
            parent_not.promise.then(
                (resolved) =>
                    if @is_emitter
                        @notifier.resolve(resolved)
                    @pipeline_resolve_called(resolved)
                (rejected) =>
                    # send it down the pipe
                    if @is_emitter
                        @notifier.reject(rejected)
                    @pipeline_reject_called(rejected)
                (recv_data) =>
                    emit_data = @new_data_received(recv_data)
                    if @is_emitter
                        @emit_data_downstream(emit_data)
            )

        emit_data_downstream: (emit_data) ->
            @notifier.notify(emit_data)


]).service("icswMonLivestatusPipeConnector",
[
    "$q", "$rootScope", "$injector",
(
    $q, $rootScope, $injector,
) ->
    # creates a DisplayPipeline
    class icswMonLivestatusPipeConnector
        constructor: (name, spec) ->
            @setup_ok = false
            @name = name
            # connection specification as text
            @spec_src = spec
            console.log "Connector #{@name} (spec: #{@spec_src})"
            @root_element = undefined
            @build_structure()

        close: () =>
            # called when parent controller gets destroyed
            # close root element (==source)
            @root_element.close()
            console.log "C"

        toggle_running: () =>
            @running = !@running
            @root_element.set_running_flag(@running)
            
        get_panel_class: () =>
            if @running
                return "panel panel-success"
            else
                return "panel panel-warning"

        build_structure: () =>
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
            @num_total_elements = 0
            # build dependencies
            el_idx = 0
            _build_iter = (in_obj, depth=0) =>
                for key, value of in_obj
                    el_idx++
                    node = new elements[key]()
                    @num_total_elements++
                    node.link_with_connector(@, el_idx, depth)
                    if node.__dp_has_template
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
            for el in @display_elements
                el.build_title()
            @num_display_elements = @display_elements.length
            @init_gridster()
            @running = true
            @setup_ok = true

        init_gridster: () =>
            @gridsterOpts = {
                columns: 20
                pushing: true
                floating: true
                swapping: false
                width: 'auto'
                colWidth: 'auto'
                rowHeight: '40'
                margins: [4, 4]
                outerMargin: true
                isMobile: true
                mobileBreakPoint: 600
                mobileModeEnabled: true
                minColumns: 1
                minRows: 2
                maxRows: 100
                defaultSizeX: 4
                defaultSizeY: 4
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
            # console.log "psc"
            
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
            _content = scope.con_element.__dp_template
            # console.log "C=", scope.con_element
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
