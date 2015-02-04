

button_module = angular.module(
    "icsw.tools.button",
    [
    ]
).directive('icswModifyButton', () ->
    return {
        restrict: 'E',
        template: """
<input type="button" class="btn btn-primary btn-xs" value="modify new"/></td>
"""
#<input type="button" class="btn btn-primary btn-xs" ng-click="local_click($event)" value="modify new"/></td>
        scope:
            click: '&'
        link: (scope, element, attrs) ->
            element.bind("click", (ev) ->
                scope.click({event: ev})
            )
            scope.local_click = (ev) ->
                scope.click({event: ev})

})