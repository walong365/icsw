# Copyright (C) 2012-2016 init.at
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

# panel tools

angular.module(
    "icsw.panel_tools",
    []
).directive("icswPanelScroller",
# corrects panel height for scrolling (dashboard panels)
# expects 2 child html elements (first header, 2nd body)
# trigger manually by calling scope.setupScrolling without parameter
["$timeout", "$rootScope", "ICSW_SIGNALS",
($timeout, $rootScope, ICSW_SIGNALS) ->
    link : (scope, el, attr) ->
        $el = el[0]
        header_height = 25
        scope.panelbody_height = 0
        if el.children().length == 2
            panel_body = el.children()[1]
            angular.element(document).ready(() ->
                header_height = $(el.children()[0])[0].offsetHeight
            )
        else
            el.css("overflow", "auto")
        scope.gettotal_height = () ->
            $el.offsetHeight
        scope.get_header_height = () ->
            $(el.children()[0])[0].offsetHeight

        # FIXME: call setupScrolling per parent scope instead of watching it
        scope.$watch(scope.gettotal_height, (newV, oldV) ->
            if newV != oldV
                scope.setupScrolling(newV[0])
            )

        $rootScope.$on(ICSW_SIGNALS("ICSW_TRIGGER_PANEL_LAYOUTCHECK"), () ->
            scope.setupScrolling()
            )
        timeoutPromise = undefined
        delayInMs = 100;

        scope.setupScrolling = (newValue) ->
            newHeight = if newValue? then newValue else scope.gettotal_height()
            $timeout.cancel(timeoutPromise)
            timeoutPromise = $timeout(()->
                header_height = scope.get_header_height()
                # x_scroll_diff = panel_body.scrollWidth - $(panel_body).width()
                # y_scroll_diff = panel_body.scrollHeight - $(panel_body).height()
                scope.panelbody_height = newHeight - header_height - 2
                $(panel_body).css("height", scope.panelbody_height)
                $(panel_body).css("overflow-x", if attr.noXScroll? then "hidden" else "auto")
                $(panel_body).css("overflow-y", if attr.noYScroll? then "hidden" else "auto")
            , delayInMs)

]).directive("icswSubMaxHeight",
# corrects height for sub elements (svg container)
# expects 2 child html elements (header, 2nd container)
# trigger manually by calling scope.setupHeight without parameter
["$timeout",
($timeout) ->
    link : (scope, el, attr) ->
        struct =
            main_c : undefined
            header_c: undefined
            body_c: undefined

        childwatcher = scope.$watch(
            () ->
                $(el.children()[0]).children().length
            (nv, ov) ->
                if nv == 2
                    struct.main_c = el.children()[0]
                    struct.header_c = $(struct.main_c).children()[0]
                    struct.body_c = $(struct.main_c).children()[1]
                    setup_watcher()
                    childwatcher()
        )
        setup_watcher = ()->
            scope.$watch(
                () ->
                    scope.panelbody_height
                (newValue, oldValue) ->
                    header_height = $(struct.header_c).outerHeight(true)
                    newHeight = newValue - header_height - 3
                    if newHeight > 0
                        $(struct.body_c).css("height", newHeight)
            )

])

