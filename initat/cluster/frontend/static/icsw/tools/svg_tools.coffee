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

# svg tools

angular.module(
    "icsw.svg_tools",
    []
).factory("svg_tools", () ->
    _has_class_svg = (s_target, name) ->
        classes = s_target.attr("class")
        if !classes
            return false
        return if classes.search(name) == -1 then false else true
            
    _find_element = (s_target) ->
        # iterative search
        if _has_class_svg(s_target, "draggable")
            return s_target
        s_target = s_target.parent()
        if s_target.length
            return _find_element(s_target)
        else
            return null
            
    return {
        has_class_svg: _has_class_svg

        get_abs_coordinate: (svg_el, x, y) ->
            screen_ctm = svg_el.getScreenCTM()
            svg_point = svg_el.createSVGPoint()
            svg_point.x = x
            svg_point.y = y
            first = svg_point.matrixTransform(screen_ctm.inverse())
            return first
            
        find_draggable_element: (s_target) ->
            return _find_element(s_target)
    }
)

angular.module(
    "icsw.mouseCapture",
    []
).factory('mouseCaptureFactory', [() ->
    # mouseCaptureFactory for ReactJS, no $rootScope.$digest Cycles are triggered
    $element = document
    mouse_capture_config = null
    mouse_move = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_move
            mouse_capture_config.mouse_move(event)
    mouse_up = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_up
            mouse_capture_config.mouse_up(event)
    return {
        register_element: (element) ->
            $element = $(element)
        acquire: (event, config) ->
            this.release()
            mouse_capture_config = config
            $element.bind("mousemove", mouse_move)
            $element.bind("mouseup", mouse_up)
        release: () ->
            if mouse_capture_config
                if mouse_capture_config.released
                    mouse_capture_config.released()
                mouse_capture_config = null;
                $element.unbind("mousemove", mouse_move)
                $element.unbind("mouseup", mouse_up)
    }
])

angular.module(
    "icsw.dragging",
    [
        "icsw.mouseCapture"
    ]
).factory("dragging",
[
    "mouseCaptureFactory",
(
    mouseCaptureFactory
) ->
    return {
        start_drag: (event, threshold, config) ->
            dragging = false
            x = event.clientX
            y = event.clientY
            mouse_move = (event) ->
                if !dragging
                    if Math.abs(event.clientX - x) > threshold or Math.abs(event.clientY - y) > threshold
                        dragging = true;
                        if config.dragStarted
                            config.dragStarted(x, y, event)
                        if config.dragging
                            config.dragging(event.clientX, event.clientY, event)
                else 
                    if config.dragging
                        config.dragging(event.clientX, event.clientY, event);
                    x = event.clientX
                    y = event.clientY
            released = () ->
                if dragging
                    if config.dragEnded
                        config.dragEnded()
                else 
                    if config.clicked
                        config.clicked()
            mouse_up = (event) ->
                mouseCaptureFactory.release()
                event.stopPropagation()
                event.preventDefault()
            mouseCaptureFactory.acquire(event, {
                mouse_move: mouse_move
                mouse_up: mouse_up
                released: released
            })
            event.stopPropagation()
            event.preventDefault()
    }
])
