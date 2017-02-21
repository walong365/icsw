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
    "icsw.livestatus.comp.tooltip",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
        "icsw.panel_tools",
    ]
).service("icswTooltipTools",
[
    "$q", "$window", "$rootScope", "$templateCache", "$compile",
(
    $q, $window, $rootScope, $templateCache, $compile,
) ->
    # for container element
    _element = null
    # global structure
    _global_structure = null

    create_struct = (kwargs) ->
        _struct = {
            # anchor element
            element: _element
            # dummy scope
            scope: $rootScope.$new(true)
            # current divlayer element
            divlayer: null
            # flag: currently shown
            is_shown: false
            # node type, to create new tooltips on the fly
            node_type: null
            # offsets x / y
            offset_x: 0
            offset_y: 0
        }
        if kwargs?
            for key, value of kwargs
                if not _struct[key]?
                    console.error "unknown key #{key} for icswTooltipTools.struct"
                else
                    _struct[key] = value
        return _struct

    set_element = (element) ->
        _element = element

    delete_struct = (struct) ->
        struct.scope.$destroy()

    position = (struct, event) ->
        if struct.is_shown
            t_os = 10  # Tooltip offset
            top_scroll = $window.innerHeight - event.clientY - struct.divlayer[0].offsetHeight - t_os > 0
            top_offset = if top_scroll then t_os else (struct.divlayer[0].offsetHeight + t_os) * -1
            left_scroll = $window.innerWidth - event.clientX - struct.divlayer[0].offsetWidth - t_os > 0
            left_offset = if left_scroll then t_os else (struct.divlayer[0].offsetWidth + t_os) * -1
            left_offset += struct.offset_x
            top_offset += struct.offset_y
            struct.divlayer.css('left', "#{event.clientX + left_offset}px")
            struct.divlayer.css('top', "#{event.clientY + top_offset}px")

    hide = (struct) ->
        if struct.is_shown
            struct.divlayer.css('left', "-10000px")
            struct.divlayer.css('top', "-10000px")
            struct.is_shown = false
            struct.scope.burst_node = null

    show = (struct, node) ->
        # node is an object with the propery node_type
        if struct.divlayer
            if struct.node_type and struct.node_type != node.node_type
                # remove old divlayer
                struct.divlayer.remove()
                struct.divlayer = null
        if not struct.divlayer
            # template
            _templ = $templateCache.get("icsw.livestatus.tooltip.#{node.node_type}")
            if not _templ?
                _templ = $templateCache.get("icsw.livestatus.tooltip.unknown")
            struct.divlayer = $compile(_templ)(struct.scope)
            struct.element.append(struct.divlayer)
        # copy node_type to detect node_type changes
        struct.node_type = node.node_type
        struct.is_shown = true
        # display variables
        # console.log "node=", node
        struct.scope.$apply(
            () ->
                struct.scope.node = node
        )
        return

    get_global_struct = () ->
        if not _global_structure?
            _global_structure = create_struct()

            _global_structure.show = (bnode) ->
                show(_global_structure, bnode)

            _global_structure.pos = (event) ->
                position(_global_structure, event)

            _global_structure.hide = () ->
                hide(_global_structure)

        return _global_structure

    return {
        # create / delete
        create_struct: create_struct
        delete_struct: delete_struct
        # position
        position: position
        # show / hide
        show: show
        hide: hide
        # element linkage
        set_element: set_element
        get_global_struct: get_global_struct
    }
]).directive("icswTooltipContainer",
[
    "$q", "icswTooltipTools",
(
    $q, icswToolTipTools,
) ->
    return {
       restrict: "EA"
       link: (scope, element, attrs) ->
           icswToolTipTools.set_element(element)
    }
])
