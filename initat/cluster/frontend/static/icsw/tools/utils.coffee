# Copyright (C) 2012-2015 init.at
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

angular.module(
    "icsw.tools.utils", []
).controller('icswToolsDummyCtrl', ["$scope", ($scope) ->
]).directive('icswToolsTdCheckbox', [() ->
    return {
        restrict: 'A'
        scope: {
            onClick: '&'
            isChecked: '&'
        }
        template: """
<span ng-class="{'glyphicon': true, 'glyphicon-ok': checked, 'glyphicon-minus': !checked}"></span>
"""
        link: (scope, el, attrs) ->
            el.addClass("text-center")
            scope.$watch(
                () -> scope.isChecked()
                (new_val) ->
                    scope.checked = new_val
                    if new_val
                        el.addClass('success')
                    else
                        el.removeClass('success')
            )
            el.bind('click', () ->
                scope.$apply(
                    scope.onClick()
                )
            )
    }
])
