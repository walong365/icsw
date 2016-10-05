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
["$timeout",
($timeout) ->
    link : (scope, el, attr) ->
        $el = el[0]
        header_height = 25
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

        scope.$watchGroup([scope.gettotal_height, scope.get_header_height], (newV, oldV, _scope) ->
            if newV != oldV
                scope.setupScrolling(newV[0])
            )

        timeoutPromise = undefined
        delayInMs = 100;
        scope.setupScrolling = (newValue) ->
            newHeight = if newValue? then newValue else scope.gettotal_height()
            $timeout.cancel(timeoutPromise)
            timeoutPromise = $timeout(()->
                header_height = scope.get_header_height()

                x_scroll_diff = panel_body.scrollWidth - $(panel_body).width()
                y_scroll_diff = panel_body.scrollHeight - $(panel_body).height()

                $(panel_body).css("height", newValue - header_height - 2)
                $(panel_body).css("overflow-x", if attr.noXScroll? then "hidden" else "auto")
                $(panel_body).css("overflow-y", if attr.noYScroll? then "hidden" else "auto")
                # x_scroll_diff2 = panel_body.scrollWidth - $(panel_body).width()
                # y_scroll_diff2 = panel_body.scrollHeight - $(panel_body).height()
            , delayInMs)
])

