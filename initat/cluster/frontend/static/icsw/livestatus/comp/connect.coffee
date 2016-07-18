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
).provider("icswLivestatusPipeRegister", () ->
    _elements = []
    return {
        add: (name, dynamic_add) ->
            _elements.push(
                {
                    name: name
                    dynamic_add: dynamic_add
                }
            )

        $get: () ->
            return _elements
    }
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
            # is an asynchronous emitter
            @__dp_async_emit = false
            # only get notified when the devicelist changes
            @__dp_notify_only_on_devchange = false
            # is leaf (no childs)
            @__dp_is_leaf_node = true
            # notifier for downstream elements
            if @is_emitter
                # @notifier = $q.defer()
                @__dp_childs = []
            # for internal data
            @show_content = true
            # for frontend / content
            @$$show_content = true
            # for frontend / header
            @$$show_header = true
            console.log "init #{@name} (recv: #{@is_receiver}, emit: #{@is_emitter})"

        close: () =>
            # called on destroy
            if @pipeline_pre_close?
                @pipeline_pre_close()
            if @is_emitter
                for _child in @__dp_childs
                    _child.__dp_parent_notifier.reject(_child.__dp_element_id)

        prefix: () ->
            return "Element #{@name} (#{@__dp_element_id}@#{@__dp_depth})"

        log: (what) ->
            console.log "#{@prefix()}: #{what}"

        warn: (what) ->
            console.warn "#{@prefix()}: #{what}"

        error: (what) ->
            console.error "#{@prefix()}: #{what}"

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
            if @is_emitter and @__dp_childs.length
                # only for emitters
                title = "#{title} to " + (entry.__dp_element_id for entry in @__dp_childs).join(", ")
            if @__dp_is_leaf_node
                title = "#{title}, leafnode"
            @__dp_title = title

        hide_element: ($event) =>
            @__dp_connector.hide_element(@)
        
        toggle_element: ($event) ->
            @show_content = !@show_content
            @set_display_flags()

        delete_element: ($event) ->
            @__dp_connector.delete_element(@, $event)

        create_element: ($event) ->
            @__dp_connector.create_element(@, $event)

        # santify checks
        check_for_emitter: () =>
            if not @is_emitter or @is_receiver
                throw new error("node is not an emitter but a receiver")

        feed_data: (mon_data) ->
            # feed data, used to insert data into the pipeline
            # console.log "fd", mon_data
            (_child.__dp_parent_notifier.notify(mon_data) for _child in @__dp_childs)

        add_child_node: (node) ->
            @__dp_is_leaf_node = false
            if not @is_emitter
                throw new error("Cannot add childs to non-emitting element")
            @__dp_childs.push(node)
            node.link_to_parent(@)

        new_data_received: (new_data) =>
            @error "new data received, to be overwritten", new_data
            return new_data
            
        pipeline_resolve_called: (resolved) =>
            @error "resolve called #{resolved} for #{@name}"

        pipeline_reject_called: (rejected) =>
            @error "reject called #{rejected} for #{@name}"

        pipeline_settings_changed: (settings) =>
            @__dp_connector.element_settings_changed(@, settings)

        restore_settings: (settings) =>
            @error "restore settings called (#{settings})"

        get_position_dict: () =>
            return {
                row: @row
                col: @col
                sizeX: @sizeX
                sizeY: @sizeY
                open: @__dp_shown
            }

        restore_position: (el) =>
            @row = el.row
            @col = el.col
            @sizeX = el.sizeX
            @sizeY = el.sizeY
            @__dp_shown = el.open

        # display / hide / toggle functions
        set_display_flags: () =>
            if @show_content
                # better: go to full state model
                if @__dp_saved_sizeY?
                    @sizeY = @__dp_saved_sizeY
            else
                @__dp_saved_sizeY = @sizeY
                @sizeY = 1
            if @__dp_connector.global_display_state in [1]
                @$$show_content = false
            else
                @$$show_content = @show_content
            @$$show_header = @__dp_connector.global_display_state in [0, 1]

        # link with connector
        link_with_connector: (connector, id, depth, path_str) =>
            @__dp_connector = connector
            @__dp_element_id = id
            @__dp_depth = depth
            # path encoded as json-string
            @__dp_path_str = path_str
            @__dp_shown = true
            @display_name = "#{@name} ##{@__dp_element_id}"

        remove_child: (child) ->
            @close_child(child)
            _.remove(@__dp_childs, (entry) -> return entry.__dp_element_id == child.__dp_element_id)
            if not @__dp_childs.length
                @__dp_is_leaf_node = true
            @build_title()

        close_child: (child) ->
            if @is_emitter
                child.__dp_parent_notifier.reject("reject #{child.__dp_element_id}")

        remove_from_parent: () ->
            # delete child via calling remove_child on parent
            @__dp_parent.remove_child(@)

        link_to_parent: (parent) ->
            @__dp_parent = parent
            @__dp_parent_notifier = $q.defer()
            @__dp_parent_notifier.promise.then(
                (resolved) =>
                    if @is_emitter
                        (_child.__dp_parent_notifier.resolve(resolved) for _child in @__dp_childs)
                    @pipeline_resolve_called(resolved)
                (rejected) =>
                    @log("rejected #{rejected}")
                    @log("close")
                    @close()
                    @pipeline_reject_called(rejected)
                (recv_data) =>
                    if @__dp_notify_only_on_devchange
                        _cur_dl = angular.toJson(_.sortBy((dev.$$icswDevice.idx for dev in recv_data.hosts)))
                        if not @__dp_prev_device_list?
                            _notify = true
                        else 
                            _notify = @__dp_prev_device_list != _cur_dl
                        @__dp_prev_device_list = _cur_dl
                    else 
                        _notify = true
                    if _notify
                        emit_data = @new_data_received(recv_data)
                        if @is_emitter
                            if @__dp_async_emit
                                # asynchronous emitter, emit_data must be none
                                if emit_data?
                                    @error "async emitter is emitting synchronous data:", emit_data
                            else
                                if emit_data?
                                    @_check_emit_id("sync", emit_data)
                                    @emit_data_downstream(emit_data)
                                else
                                    @error "emitter is emitting none ..."
            )

        _check_emit_id: (etype, result) =>
            if @__dp_current_data_id? and result.id != @__dp_current_data_id
                @warn "id of #{etype} emit data changed from #{@__dp_current_data_id} to #{result.id}"
            @__dp_current_data_id = result.id

        set_async_emit_data: (result) =>
            if !@__dp_async_emit
                @error "synchronous emitter is emitting asynchronous data"
            @_check_emit_id("async", result)
            result.result_notifier.promise.then(
                (resolved) =>
                    @log "async data resolve: #{resolved}"
                (rejected) =>
                    @log "async data reject: #{rejected}"
                (generation) =>
                    @emit_data_downstream(result)
            )
            
        emit_data_downstream: (emit_data) ->
            (_child.__dp_parent_notifier.notify(emit_data) for _child in @__dp_childs)


]).service("icswMonLivestatusPipeConnector",
[
    "$q", "$rootScope", "$injector", "icswToolsSimpleModalService", "$window", "icswComplexModalService",
    "$templateCache", "$compile", "icswLivestatusPipeRegister",
(
    $q, $rootScope, $injector, icswToolsSimpleModalService, $window, icswComplexModalService,
    $templateCache, $compile, icswLivestatusPipeRegister,
) ->
    # creates a DisplayPipeline
    class icswMonLivestatusPipeConnector
        constructor: (name, user, spec) ->
            @setup_ok = false
            # name
            @name = name
            # user
            @user = user
            # connection specification as text
            @spec_src = spec
            console.log "Connector #{@name} (spec #{@spec_src}, user #{@user.user.login})"
            @root_element = undefined
            # 0 ... show all
            # 1 ... no content
            # 2 ... no header
            @global_display_state = 2
            # position dict
            @_pos_str = ""
            @build_structure()

        close: () =>
            # called when parent controller gets destroyed
            # close root element (==source)
            @root_element.close()
            console.log "C"

        toggle_running: () =>
            @running = !@running
            for el in @all_elements
                if el.set_running_flag?
                    el.set_running_flag(@running)

        toggle_global_display_state: () =>
            @global_display_state++
            if @global_display_state > 2
                @global_display_state =0
            (_element.set_display_flags() for _element in @all_elements)

        get_panel_class: () =>
            if @running
                return "panel panel-success"
            else
                return "panel panel-warning"

        _resolve_element_name: (name) =>
            if name not of @element_dict
                @element_dict[name] = $injector.get(name)

        _create_and_add_element: (parent_el, name) =>
            @num_total_elements++
            if parent_el is null
                path = []
                depth = 0
            else
                path = angular.fromJson(parent_el.__dp_path_str)
                depth = parent_el.__dp_depth + 1
            _path = _.concat(path, [[depth, @num_total_elements, name]])
            _path_str =  angular.toJson(_path)
            node = new @element_dict[name]()
            node.link_with_connector(@, @num_total_elements, depth, _path_str)
            if _path_str of @settings
                node.restore_settings(@settings[_path_str])
            if _path_str of @positions
                node.restore_position(@positions[_path_str])
            @all_elements.push(node)
            if node.__dp_has_template
                if node.__dp_shown
                    @display_elements.push(node)
                else
                    @hidden_elements.push(node)
            return node

        build_structure: () =>
            # dict element name -> service
            @element_dict = {}

            # simple iteratee for resolving

            _resolve_iter = (in_obj, depth=0) =>
                if _.keys(in_obj).length == 0
                    throw new Error("empty object found at depth #{depth}")
                else if _.keys(in_obj).length != 1
                    throw new Error("Only one element allowed at any level")
                for key, value of in_obj
                    @_resolve_element_name(key)
                    for _el in value
                        _resolve_iter(_el, depth+1)

            @all_elements = []
            # list of display elements
            @display_elements = []
            # list of hidden elements
            @hidden_elements = []
            @num_total_elements = 0
            # check for existing settings
            @_settings_name = "$$icswDashboardSettings_#{@name}"
            @_positions_name = "$$icswDashboardPositions_#{@name}"
            # settings dict
            if @user.has_var(@_settings_name)
                @settings = angular.fromJson(@user.get_var(@_settings_name).json_value)
            else
                @settings = {}
            # position dict
            if @user.has_var(@_positions_name)
                @positions = angular.fromJson(@user.get_var(@_positions_name).json_value)
            else
                @positions = {}
            # console.log "settings=", @_settings_name, @settings
            # build dependencies
            _build_iter = (in_obj, parent) =>
                for key, value of in_obj
                    node = @_create_and_add_element(parent, key)
                    if node.depth == 0
                        @root_element = node
                        @root_element.check_for_emitter()
                    for _el in value
                        node.add_child_node(_build_iter(_el, node))
                return node

            # interpret and resolve spec_src
            @spec_json = angular.fromJson(@spec_src)
            # resolve elements
            _resolve_iter(@spec_json)
            # build tree
            _build_iter(@spec_json, null)
            for el in @all_elements
                if el.__dp_has_template
                    el.build_title()
            @num_display_elements = @display_elements.length
            @num_hidden_elements = @hidden_elements.length
            (_element.set_display_flags() for _element in @all_elements)
            # save positions
            @save_positions()
            @init_gridster()
            @running = true
            @setup_ok = true

        hide_element: (hide_el) =>
            @hidden_elements.push(hide_el)
            hide_el.__dp_shown = false
            _.remove(@display_elements, (entry) -> return entry.__dp_element_id == hide_el.__dp_element_id)
            @num_hidden_elements++
            @layout_changed()

        unhide_element: (show_el) ->
            @display_elements.push(show_el)
            show_el.__dp_shown = true
            _.remove(@hidden_elements, (entry) -> return entry.__dp_element_id == show_el.__dp_element_id)
            @num_hidden_elements--
            @layout_changed()

        delete_element: (element, $event) =>
            # delete element permanently
            icswToolsSimpleModalService("Really delete DPE #{element.__dp_raw_title} ?").then(
                (del_it) =>
                    @_delete_element(element)
            )
            
        create_element: (element, $event) =>
            # add an element to the current element
            sub_scope = $rootScope.$new(true)
            sub_scope.allowed_elements = (
                {
                    name: el.name
                } for el in icswLivestatusPipeRegister when el.dynamic_add
            )
            sub_scope.struct = {
                new_element: sub_scope.allowed_elements[0].name
            }
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.connect.create.element"))(sub_scope)
                    title: "Add DisplayPipe Element"
                    # css_class: "modal-wide"
                    ok_label: "Add"
                    closable: true
                    ok_callback: (modal) =>
                        d = $q.defer()
                        _name = sub_scope.struct.new_element
                        # resolve element name to object
                        @_resolve_element_name(_name)
                        node = @_create_and_add_element(element, _name)
                        element.add_child_node(node)
                        d.resolve("created")
                        return d.promise
                    cancel_callback: (modal) ->
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    sub_scope.$destroy()
            )

        element_settings_changed: (element, settings_str) =>
            @settings[element.__dp_path_str] = settings_str
            @user.set_json_var(@_settings_name, angular.toJson(@settings))

        _delete_element: (element) =>
            _.remove(@display_elements, (entry) -> return entry.__dp_element_id == element.__dp_element_id)
            _.remove(@hidden_elements, (entry) -> return entry.__dp_element_id == element.__dp_element_id)
            _.remove(@all_elements, (entry) -> return entry.__dp_element_id == element.__dp_element_id)
            @num_total_elements--
            @num_hidden_elements = @hidden_elements.length
            @num_display_elements = @display_elements.length
            element.remove_from_parent()

        init_gridster: () =>
            NUM_COLUMS = 20
            c_width = _.max([80, $window.innerWidth / NUM_COLUMS])
            r_height = c_width
            @gridsterOpts = {
                columns: NUM_COLUMS
                pushing: true
                floating: true
                swapping: false
                width: 'auto'
                colWidth: 'auto'
                rowHeight: r_height
                margins: [1, 1]
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
                   handles: ['ne', 'se', 'sw', 'nw']
                   stop: (event, element, options) =>
                       @layout_changed()
                }
                draggable: {
                   enabled: true
                   handle: '.icsw-draggable'
                   stop: (event, element, options) =>
                       @layout_changed()
                }
            }

        _get_positions: () =>
            p_dict = {}
            for el in @all_elements
                if el.__dp_has_template
                    p_dict[el.__dp_path_str] = el.get_position_dict()
            return p_dict

        layout_changed: () =>
            @save_positions()

        save_positions: () =>
            cur_pos = @_get_positions()
            _cur_str = angular.toJson(cur_pos)
            if _cur_str != @_pos_str
                @_pos_str = _cur_str
                @user.set_json_var(
                    @_positions_name
                    @_pos_str
                )

        new_devsel: (devs) =>
            # start loop
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
