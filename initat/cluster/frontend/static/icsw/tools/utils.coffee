
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