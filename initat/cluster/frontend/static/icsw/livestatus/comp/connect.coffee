# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

# livestatus connector components

angular.module(
    "icsw.livestatus.comp.connect",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
        "icsw.panel_tools",
    ]
).provider("icswLivestatusPipeRegister", () ->
    _struct = {
        # list of all elements
        elements: []
        # is resolved
        resolved: false
        # lut
        lut: {}
    }

    return {
        add: (name, dynamic_add) ->
            _struct.elements.push(
                {
                    name: name
                    dynamic_add: dynamic_add
                }
            )

        $get: () ->
            return _struct
    }
).service("icswLivestatusPipeFunctions",
[
    "$injector", "icswLivestatusPipeRegister",
(
    $injector, icswLivestatusPipeRegister,
) ->
    resolve = () ->
        _struct = icswLivestatusPipeRegister
        if not _struct.resolved
            _struct.resolved = true
            for entry in _struct.elements
                # set class
                entry.class = $injector.get(entry.name)
                # set object
                entry.object = new entry.class()
                _struct.lut[entry.name] = entry
        return _struct

    return {
        resolve: () ->
            return resolve()
    }

]).service("icswWidgetImage",
[
    "ICSW_URLS",
(
    ICSW_URLS
) ->
    img_lut = {
        icswLivestatusSelDevices: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_data-selection.svg"
            img: "#{ICSW_URLS.STATIC_URL}/data-selection.svg"
        }
        icswLivestatusDataSource: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_data-source.svg"
            img: "#{ICSW_URLS.STATIC_URL}/data-source.svg"
        }
        icswLivestatusMonCategoryFilter: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_monitoring-category-filter.svg"
            img: "#{ICSW_URLS.STATIC_URL}/monitoring-category-filter.jpg"
        }
        icswLivestatusDeviceCategoryFilter: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_device-category-filter.svg"
            img: "#{ICSW_URLS.STATIC_URL}/device-category-filter.jpg"
        }
        icswLivestatusMonCategoryFilterBurst: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_monitoring-category-filter-burst.svg"
            img: "#{ICSW_URLS.STATIC_URL}/monitoring-category-filter-burst.svg"
        }
        icswLivestatusDeviceCategoryFilterBurst: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_device-category-filter-burst.svg"
            img: "#{ICSW_URLS.STATIC_URL}/device-category-filter-burst.svg"
        }
        icswLivestatusFullBurst: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_burst.svg"
            img: "#{ICSW_URLS.STATIC_URL}/burst.svg"
        }
        icswLivestatusFilterService: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_basefilter.svg"
            img: "#{ICSW_URLS.STATIC_URL}/basefilter.svg"
        }
        icswLivestatusTopologySelector: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_network-topology-filter.svg"
            img: "#{ICSW_URLS.STATIC_URL}/network-topology-filter.jpg"
        }
        icswLivestatusNetworkTopology: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_network-topology.svg"
            img: "#{ICSW_URLS.STATIC_URL}/network-topology.jpg"
        }
        icswLivestatusLocationMap: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_location-images.svg"
            img: "#{ICSW_URLS.STATIC_URL}/location-images.jpg"
        }
        icswLivestatusGeoLocationDisplay: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_geolocation.svg"
            img: "#{ICSW_URLS.STATIC_URL}/geolocation.jpg"
        }
        icswLivestatusMonTabularDisplay: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_service-tabular.svg"
            img: "#{ICSW_URLS.STATIC_URL}/service-tabular.jpg"
        }
        icswLivestatusDeviceTabularDisplay: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_device-tabular.svg"
            img: "#{ICSW_URLS.STATIC_URL}/device-tabular.jpg"
        }
        icswLivestatusInfoDisplay: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_quickinfo.svg"
            img: "#{ICSW_URLS.STATIC_URL}/quickinfo.svg"
        }
        empty: {
            icon: "#{ICSW_URLS.STATIC_URL}/icon_quickinfo.svg"
            img: "#{ICSW_URLS.STATIC_URL}/quickinfo.svg"
        }
    }
    getimage: (name) ->
        if name of img_lut
            return img_lut[name]
        else
            return img_lut["empty"]

]).service("icswMonLivestatusPipeBase",
[
    "$q", "$rootScope", "icswLivestatusLayoutHelpers", "icswWidgetImage",
(
    $q, $rootScope, icswLivestatusLayoutHelpers, icswWidgetImage
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
            #@get_image()
            if @is_receiver
                if @is_emitter
                    # filter
                    @$$type = "F"
                else
                    # receiver
                    @$$type = "R"
            else
                # emitter
                @$$type = "E"
            @$$imgdata = icswWidgetImage.getimage(@name)
            # for frontend / content
            @$$show_content = true
            # for frontend / header
            @$$show_header = false
            # console.log "init #{@name} (recv: #{@is_receiver}, emit: #{@is_emitter})"

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

        # flags for modify layout
        is_deletable: () ->
            return if @__dp_depth and @__dp_is_leaf_node and @__dp_has_template then true else false

        get_layout_name: () =>
            if @__dp_has_template
                return @$$dp_title
            else if @name == "icswLivestatusDataSource"
                return "Data Source"
            else if @name == "icswLivestatusSelDevices"
                return "Device Selection"
            else
                return @name

        get_layout_title: () =>
            if @__dp_has_template
                return @$$dp_title_full
            else
                return @name

        # set template
        set_template: (template, title, size_x=4, size_y=4, no_y_scroll=false) =>
            @__dp_has_template = true
            # template content, not URL
            @__dp_template = template
            @$$dp_title = title
            @sizeX = size_x
            @sizeY = size_y
            @no_y_scroll = no_y_scroll

        build_title: () =>
            title = @$$dp_title
            if @__dp_parent
                title = "#{title} from #{@__dp_parent.__dp_element_id}"
            if @is_emitter and @__dp_childs.length
                # only for emitters
                title = "#{title} to " + (entry.__dp_element_id for entry in @__dp_childs).join(", ")
            if @__dp_is_leaf_node
                title = "#{title}, leafnode"
            @$$dp_title_full = title

        hide_element: ($event) =>
            @__dp_connector.hide_element(@)
        
        toggle_element: ($event) ->
            @show_content = !@show_content
            @set_display_flags()

        delete_element: ($event) ->
            icswLivestatusLayoutHelpers.delete_node($event, @__dp_struct)

        create_element: ($event) ->
            icswLivestatusLayoutHelpers.create_node($event, @__dp_struct)

        # santify checks
        check_for_emitter: () =>
            if not @is_emitter or @is_receiver
                throw new error("node is not an emitter but a receiver")

        add_child_node: (node) ->
            @__dp_is_leaf_node = false
            if not @is_emitter
                throw new error("Cannot add childs to non-emitting element")
            @__dp_childs.push(node)
            node.link_to_parent(@)

        new_data_received_cached: (new_data) =>
            # cache it to re-emit it if necessary
            # this function must NOT be overwritten
            if new_data?
                @__dp_cached_data = new_data
                return @new_data_received(new_data)
            else
                return @new_data_received(@__dp_cached_data)

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
            @$$show_header = @__dp_connector.global_display_state == 1

        # link with connector
        link_with_connector: (struct, connector, id, depth, path_str) =>
            # structure for connector access
            @__dp_struct = struct
            @__dp_connector = connector
            # id, unique integer in connector
            @__dp_element_id = id
            @__dp_depth = depth
            # path encoded as json-string
            @__dp_path_str = path_str
            @__dp_shown = true
            @display_name = "#{@name} ##{@__dp_element_id}"

        is_same: (other) ->
            return @__dp_element_id == other.__dp_element_id

        remove_child: (child) ->
            @close_child(child)
            _.remove(@__dp_childs, (entry) -> return entry.__dp_element_id == child.__dp_element_id)
            _.remove(@__dp_struct.childs, (entry) -> return entry.node.__dp_element_id == child.__dp_element_id)
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
                        emit_data = @new_data_received_cached(recv_data)
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
    "$q", "$rootScope", "icswToolsSimpleModalService", "$window", "icswComplexModalService",
    "$templateCache", "$compile", "icswLivestatusPipeRegister", "$timeout", "ICSW_SIGNALS",
    "icswLivestatusPipeFunctions",
(
    $q, $rootScope, icswToolsSimpleModalService, $window, icswComplexModalService,
    $templateCache, $compile, icswLivestatusPipeRegister, $timeout, ICSW_SIGNALS,
    icswLivestatusPipeFunctions,
) ->
    C_ID = 0
    # creates a DisplayPipeline
    class icswMonLivestatusPipeConnector
        constructor: (pipespec_obj, user) ->
            # resolve all elements
            icswLivestatusPipeFunctions.resolve()
            C_ID++
            @connector_id = C_ID
            @setup_ok = false
            # object
            @object = pipespec_obj
            # name
            @name = pipespec_obj.name
            # user
            @user = user
            # connection specification as text
            @spec_json = angular.fromJson(@object.json_spec)
            console.log "Connector '#{@name}' (spec #{@object}, user #{@user.user.login})"
            @root_element = undefined
            # 0 ... only content, no dragNdrop, no resize - DASHBOARD LOCKED
            # 1 ... with header, dragNdrop, resize - DASHBOARD UNLOCKED
            @global_display_state = 0
            @set_unlocked_flag(false)
            # position dict
            @_pos_str = ""
            # dendrogram root
            @dd_root = undefined
            @build_structure()

        close: () =>
            # called when parent controller gets destroyed
            # close root element (==source)
            @root_element.close()
            console.log "C"

        set_unlocked_flag: (flag) =>
            @is_unlocked = flag
            if @is_unlocked
                @$$is_unlocked_btn_class = "btn btn-warning"
                @$$is_unlocked_i_class = "fa fa-unlock"
                @$$is_unlocked_info_str = "Layout unlocked"
            else
                @$$is_unlocked_btn_class = "btn btn-success"
                @$$is_unlocked_i_class = "fa fa-lock"
                @$$is_unlocked_info_str = "Layout locked"


        toggle_global_display_state: () =>
            @global_display_state++
            if @global_display_state > 1
                @global_display_state = 0
            (_element.set_display_flags() for _element in @all_elements)
            is_unlocked = @global_display_state == 1
            @set_unlocked_flag(is_unlocked)

        get_panel_class: () =>
            if @running
                return "panel panel-success"
            else
                return "panel panel-warning"

        create_and_add_element: (parent_struct, name) =>
            @num_total_elements++
            @running_element_id++
            if parent_struct is null
                path = []
                depth = 0
            else
                path = angular.fromJson(parent_struct.node.__dp_path_str)
                depth = parent_struct.node.__dp_depth + 1
            _path = _.concat(path, [[depth, @running_element_id, name]])
            _path_str =  angular.toJson(_path)
            if name not of icswLivestatusPipeRegister.lut
                console.error "PipeElement '#{name}' not known in lut", icswLivestatusPipeRegister.lut
            node = new icswLivestatusPipeRegister.lut[name].class()
            _struct = {
                connector: @
                id: name
                name: name
                parent: parent_struct
                parent_id: if parent_struct then parent_struct.id else null
                node: node
                childs: []
            }
            node.link_with_connector(_struct, @, @running_element_id, depth, _path_str)
            if parent_struct
                parent_struct.childs.push(_struct)
                _struct.id = "#{parent_struct.id}.#{_struct.id}"
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
            @build_info_str()
            if parent_struct
                parent_struct.node.add_child_node(_struct.node)
            $rootScope.$emit(ICSW_SIGNALS("ICSW_LIVESTATUS_PIPELINE_MODIFIED"))
            if @record_mode
                # add record
                @records.push({action: "add", struct: _struct})
            return _struct

        build_structure: () =>

            # simple iteratee for resolving

            _resolve_iter = (in_obj, depth=0) =>
                if _.keys(in_obj).length == 0
                    throw new Error("empty object found at depth #{depth}")
                else if _.keys(in_obj).length != 1
                    throw new Error("Only one element allowed at any level")
                for key, value of in_obj
                    for _el in value
                        _resolve_iter(_el, depth+1)

            # build dependencies

            _build_iter = (in_obj, parent_struct) =>
                for key, value of in_obj
                    struct = @create_and_add_element(parent_struct, key)
                    node = struct.node
                    if node.__dp_depth == 0
                        @root_element = node
                        @root_element.check_for_emitter()
                        @pipe_structure = struct
                    (_build_iter(_el, struct) for _el in value)
                return node

            @all_elements = []
            # list of display elements
            @display_elements = []
            # list of hidden elements
            @hidden_elements = []
            @num_total_elements = 0
            # running element id, gets only increads
            @running_element_id = 0
            # check for existing settings
            @_settings_name = "$$icswDashboardSettings_#{@name}"
            @_positions_name = "$$icswDashboardPositions_#{@name}"
            # settings dict
            if @user.has_var(@_settings_name)
                @settings = angular.fromJson(@user.get_var(@_settings_name).json_value)
            else
                @settings = {}
            @__settings_save_pending = false
            # position dict
            if @user.has_var(@_positions_name)
                @positions = angular.fromJson(@user.get_var(@_positions_name).json_value)
            else
                @positions = {}
            # console.log "settings=", @_settings_name, @settings

            # interpret and resolve spec_json
            @pipe_structure = null
            # resolve elements and build pipe_structure
            _resolve_iter(@spec_json)
            # build tree
            _build_iter(@spec_json, null)
            for el in @all_elements
                if el.__dp_has_template
                    el.build_title()
            # console.log "*", @pipe_structure
            @active_struct = @build_current_json()
            @num_display_elements = @display_elements.length
            @num_hidden_elements = @hidden_elements.length
            (_element.set_display_flags() for _element in @all_elements)
            # save positions
            @build_info_str()
            @save_positions()
            @init_gridster()
            @set_running_flag(true)
            @setup_ok = true
            # flag if changes are being recorded
            @record_mode = false

        build_info_str: () =>
            @$$info_str = "#{@name}, #{@num_total_elements} Elements"

        check_for_new_struct: () =>
            new_struct = @build_current_json()
            if angular.toJson(new_struct) != angular.toJson(@active_struct)
                @active_struct = new_struct
                return true
            else
                return false

        build_current_json: () =>
            _iter = (node) ->
                _struct = {}
                if node.is_emitter
                    _childs = (_iter(child) for child in node.__dp_childs)
                else
                    _childs = []
                _struct[node.name] = _childs
                return _struct
            return _iter(@root_element)

        get_struct_by_id: (id) =>
            result = null
            _iter = (head, s_id) =>
                if head.id == s_id
                    result = head
                else
                    (_iter(_child, s_id) for _child in head.childs)
            _iter(@pipe_structure, id)
            return result

        toggle_running: () =>
            @set_running_flag(!@running)

        set_running_flag: (flag) =>
            if @running?
                _prev = @running
            else
                _prev = null
            @running = flag
            if @running != _prev
                if @running
                    @$$running_btn_class = "btn btn-success"
                    @$$running_i_class = "fa fa-heartbeat"
                    @$$running_info_str = "Liveupdates enabled"
                else
                    @$$running_btn_class = "btn btn-warning"
                    @$$running_i_class = "fa fa-ban"
                    @$$running_info_str = "Liveupdates paused"
                for el in @all_elements
                    if el.set_running_flag?
                        el.set_running_flag(@running)
            return _prev

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

        element_settings_changed: (element, settings_str) =>
            @settings[element.__dp_path_str] = settings_str
            if not @__settings_save_pending
                # wait for 500 msecs to avoid redundant update calls
                $timeout(
                    () =>
                        @__settings_save_pending = false
                        @user.set_json_var(@_settings_name, angular.toJson(@settings))
                    500
                )
                @__settings_save_pending = true

        delete_element: (struct) =>
            defer = $q.defer()
            # display element
            element = struct.node
            if @record_mode
                @records.push({action: "remove", struct: element.__dp_struct})
            _.remove(@display_elements, (entry) -> return entry.__dp_element_id == element.__dp_element_id)
            _.remove(@hidden_elements, (entry) -> return entry.__dp_element_id == element.__dp_element_id)
            _.remove(@all_elements, (entry) -> return entry.__dp_element_id == element.__dp_element_id)
            @num_total_elements--
            @num_hidden_elements = @hidden_elements.length
            @num_display_elements = @display_elements.length
            element.remove_from_parent()
            defer.resolve("deleted")
            @build_info_str()
            $rootScope.$emit(ICSW_SIGNALS("ICSW_LIVESTATUS_PIPELINE_MODIFIED"))
            return defer.promise

        start_recording: () =>
            @record_mode = true
            @records = []

        stop_recording: () =>
            @record_mode = false

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
                   enabled: false,
                   handles: ['ne', 'se', 'sw', 'nw']
                   stop: (event, element, options) =>
                       @layout_changed()
                }
                draggable: {
                   enabled: false
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

        get_flat_list: () =>
            # return a flat list of liveview elements
            _iterate = (root_obj) =>
                _list.push(root_obj)
                for value in root_obj.childs
                    _iterate(value)
            _list = []
            _iterate(@pipe_structure)
            return _list

]).service("icswLivestatusLayoutHelpers",
[
    "$q", "icswToolsSimpleModalService", "blockUI", "$rootScope", "ICSW_SIGNALS",
    "icswLivestatusPipeRegister", "icswComplexModalService", "$compile",
    "$templateCache",
(
    $q, icswToolsSimpleModalService, blockUI, $rootScope, ICSW_SIGNALS,
    icswLivestatusPipeRegister, icswComplexModalService, $compile,
    $templateCache,
) ->
    delete_node = (event, node) ->
        connector = node.connector
        defer = $q.defer()
        icswToolsSimpleModalService("Really delete node #{node.node.$$dp_title_full} ?").then(
            (ok) ->
                connector.delete_element(node).then(
                    (done) ->
                        defer.resolve("ok")
                )
            (notok) ->
                defer.reject("no")
        )
        return defer.promise

    create_node = (event, parent_node) ->
        connector = parent_node.connector
        defer = $q.defer()
        sub_scope = $rootScope.$new(true)
        # console.log "Connector = #{connector}"
        sub_scope.allowed_elements = []
        for el in icswLivestatusPipeRegister.elements
            if el.dynamic_add
                sub_scope.allowed_elements.push(
                    {
                        title: el.object.$$dp_title
                        name: el.object.name
                    }
                )
        sub_scope.struct = {
            new_element: sub_scope.allowed_elements[0].name
        }
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.connect.create.element"))(sub_scope)
                title: "Add DisplayPipe Element"
                ok_label: "Add"
                closable: true
                ok_callback: (modal) =>
                    d = $q.defer()
                    _name = sub_scope.struct.new_element
                    # resolve element name to object
                    struct = connector.create_and_add_element(parent_node, _name)
                    parent_node.node.new_data_received_cached()
                    # node = struct.node
                    # parent_node.node.add_child_node(node)
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
                defer.resolve("done")
        )
        return defer.promise

    return {
        delete_node: delete_node
        create_node: create_node
    }
]).service("icswLivestatusClusterDendrogramReact",
[
    "$q", "icswLivestatusLayoutHelpers",
(
    $q, icswLivestatusLayoutHelpers
) ->
    {h3, div, span, svg, g, rect, circle, path, title, text, h4, h3, button, ellipse, image, img} = React.DOM
    return React.createClass(
        displayName: "icswLivestatusClusterDendrogramReact"
        propTypes: {
            connector: React.PropTypes.object
            width: React.PropTypes.number
            height: React.PropTypes.number
        }

        getInitialState: () ->
            return {
                focus_node: null
                active_node: null
            }

        render: () ->
            _path_idx = 0
            _node_idx = 0

            get_node = (node) =>
                _node_idx++
                _el = node.data.node
                if @state.active_node and @state.active_node.data.node.is_same(node.data.node)
                    _color = "#e0ffe0"
                else if @state.focus_node and @state.focus_node.data.node.is_same(node.data.node)
                    _color = "#ffe0e0"
                else
                    _color = "#f0f0ff"
                if _el.__dp_has_template
                    _dasharray = null
                else
                    _dasharray = "5,5"
                # console.log _el.is_receiver, _el.is_emitter
                return g(
                    {
                        key: "node#{_node_idx}"
                        transform: "translate(#{node.y}, #{node.x})"
                        onClick: (event) =>
                            if @state.active_node and @state.active_node.data.node.is_same(node.data.node)
                                @setState({active_node: null, focus_node: null})
                            else
                                @setState({active_node: node, focus_node: node})
                        onMouseEnter: (event) =>
                            @setState({focus_node: node})
                        # onMouseLeave: (event) =>
                        #    @setState({focus_node: null})

                    }
                    title(
                        {
                            key: "title"
                        }
                        _el.get_layout_title()
                    )
                    ellipse(
                        {
                            key: "el"
                            rx: 80
                            ry: 35
                            className: "svg-ls-cd-node"
                            style: {fill: _color, strokeDasharray: _dasharray}
                        }
                    )
                    if _el.$$imgdata.icon
                        image(
                            {
                            x: -60
                            y: -22
                            key: "symbol"
                            height: 50
                            width: 110
                            xlinkHref: _el.$$imgdata.icon
                            }
                        )
                    else
                        text(
                            {
                                key: "text"
                                textAnchor: "middle"
                                fontSize: "30px"
                                alignmentBaseline: "middle"
                            }
                            "#{_el.$$type}"
                        )
                )

            get_path = (node) =>
                if node.parent
                    n = node
                    p = n.parent
                    _path_idx++
                    _path = "M#{n.y},#{n.x}C#{p.y + 100},#{n.x} #{p.y + 100},#{p.x} #{p.y},#{p.x}"
                    return path(
                        {
                            key: "p#{_path_idx}"
                            d: _path
                            className: "svg-ls-cd-link"
                        }
                    )
                else
                    return null

            _border = 50
            _act_node = @state.active_node

            editable = !@props.connector.object.system_pipe
            # console.log "E=", editable
            dd_root = @props.connector.dd_root
            _svg = svg(
                {
                    key: "svgouter"
                    width: "100%"  # width
                    # height: "100%"  # height
                    preserveAspectRatio: "xMidYMid meet"
                    # viewBox: "-#{_border} -#{_border} #{@props.width + _border} #{@props.height + _border}"
                    viewBox: "-90 50 1200 900"
                }
                g(
                    {
                        key: "gouter"
                    }
                    (
                        get_path(node) for node in dd_root.descendants()
                    )
                    (
                        get_node(node) for node in dd_root.descendants()
                    )
                )
            )
            an = @state.active_node
            fn = @state.focus_node
            _an_rows = []

            if an
                if an.data.node.is_emitter and editable
                    _an_rows.push(
                        div(
                            {
                                key: "createb"
                                style: {
                                    float: "left"
                                    margin: "0 0 5px 15px"
                                }
                            }
                            button(
                                {
                                    key: "crateb"
                                    className: "btn btn-xs btn-success"
                                    onClick: (event) =>
                                        icswLivestatusLayoutHelpers.create_node(event, an.data)
                                }
                                "Append Element"
                            )
                        )
                    )
                if an.data.node.is_deletable() and editable
                    _an_rows.push(
                        div(
                            {
                                key: "delb"
                                style: {
                                    float: "left"
                                    margin: "0 0 5px 15px"
                                }
                            }
                            button(
                                {
                                    key: "delb"
                                    className: "btn btn-xs btn-danger"
                                    onClick: (event) =>
                                        icswLivestatusLayoutHelpers.delete_node(event, an.data).then(
                                            (done) =>
                                                @setState({focus_node: null, active_node: null})
                                        )
                                }
                                "Delete Element"
                            )
                        )
                    )
                _an_rows.push(
                    div(
                        {
                            key: "name"
                            className: "col-md-12"
                        }
                        an.data.node.get_layout_name()
                    )
                )
                if an.data.node.$$imgdata.img
                    _an_rows.push(
                        div(
                            {
                                key: "divimg"
                                className: "col-md-12"
                            }
                            img(
                                {
                                    key: "animg"
                                    src: an.data.node.$$imgdata.img
                                    width: 200
                                }
                            )
                        )
                    )

            if an
                _an_div = div(
                    {
                        key: "active"
                        className: "container-fluid"
                    }
                    h3(
                        {
                            key: "head"
                        }
                        "Active Node"
                    )
                    div(
                        {
                            key: "rows"
                            className: "row"
                        }
                        _an_rows
                    )
                )
            else _an_div = ""
            if fn
                _fn_div = div(
                    {
                        key: "focus"
                        className: "container-fluid"
                        style: {
                            minHeight: 200
                            maxHeight: 200
                        }
                    }
                    h3(
                        {
                            key: "head"
                            style: { marginTop: 0 }
                        }
                        "Focus Node"
                    )
                    if fn then fn.data.node.get_layout_name() else ""
                    if fn and fn.data.node.$$imgdata.img
                        div(
                            {
                                key: "divimg"
                                className: ""
                            }
                            img(
                                {
                                    key: "fnimg"
                                    src: fn.data.node.$$imgdata.img
                                    width: 200
                                }
                            )
                        )
                    else ""
                )
            else _fn_div = ""
            _ctrl = div(
                {
                    key: "ctrl"
                }
                _fn_div
                _an_div
            )
            return div(
                {
                    key: "top"
                    className: "container-fluid"
                }
                div(
                    {
                        key: "row"
                        className: "row"
                    }
                    div(
                        {
                            key: "svg"
                            className: "col-md-8"
                            style: { paddingLeft: 0 }
                        }
                        _svg
                    )
                    div(
                        {
                            key: "ctrl"
                            className: "col-md-4"
                        }
                        _ctrl
                    )
                )
            )
    )
]).directive("icswLivestatusClusterDendrogram",
[
    "$q", "d3_service", "icswLivestatusClusterDendrogramReact",
(
    $q, d3_service, icswLivestatusClusterDendrogramReact,
) ->
    return {
        restrict: "E"
        scope: {
            connector: "=icswConnector"
        }
        controller: "icswLivestatusClusterDendrogramCtrl"
        link: (scope, element, attrs) ->
            scope.render_el = (connector, width, height) ->
                scope.struct.react_element = ReactDOM.render(
                    React.createElement(
                        icswLivestatusClusterDendrogramReact
                        {
                            connector: connector
                            width: width
                            height: height
                        }
                    )
                    element[0]
                )
    }
]).controller("icswLivestatusClusterDendrogramCtrl",
[
    "$scope", "d3_service", "$q", "icswLivestatusLayoutHelpers", "$rootScope",
    "ICSW_SIGNALS",
(
    $scope, d3_service, $q, icswLivestatusLayoutHelpers, $rootScope,
    ICSW_SIGNALS,
) ->
    $scope.struct = {
        # d3
        d3: undefined
        # react element
        react_element: null
        # unregister functions
        unreg_fn: []
    }
    _render = () ->
        d3 = $scope.struct.d3
        _flat_list = $scope.struct.connector.get_flat_list()
        tree = d3.cluster().size([1000, 1000])
        stratify = d3.stratify().parentId(
            (node) ->
                # get parent id
                _parts = node.id.split(".")
                _parts.pop(-1)
                return _parts.join(".")
        )
        # get root element
        root = stratify(_flat_list)
        # tree layout
        tree(root)
        # set dendrogram root
        $scope.struct.connector.dd_root = root
        $scope.render_el($scope.struct.connector, 1000, 1000)

    $q.all(
        [
            d3_service.d3()
        ]
    ).then(
        (result) ->
            d3 = result[0]
            $scope.struct.d3 = d3
            $scope.struct.connector = $scope.connector
            $scope.struct.unreg_fn.push(
                $rootScope.$on(ICSW_SIGNALS("ICSW_LIVESTATUS_PIPELINE_MODIFIED"), () ->
                    _render()
                )
            )
            # build tree
            _render()
    )
    $scope.$on("$destroy", () ->
        (_fn() for _fn in $scope.struct.unreg_fn)
    )

]).directive("icswConnectElementDisplay",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile,
) ->
    return {
        restrict: "E"
        scope:
            con_element: "=icswConnectElement"
        controller: "icswConnectElementCtrl"
        link: (scope, element, attrs) ->
            _outer = $templateCache.get("icsw.connect.element")
            _content = scope.con_element.__dp_template

            # not beautiful but working
            scope.no_y_scroll = if scope.con_element.no_y_scroll then "1" else "0"
            _template_content = _outer  + _content + "</div></div>"

            element.append($compile(_template_content)(scope))

    }
]).controller("icswConnectElementCtrl", [
    "$scope",
(
    $scope,
) ->
    $scope.close = () ->
        $scope.con_element.close()
])
