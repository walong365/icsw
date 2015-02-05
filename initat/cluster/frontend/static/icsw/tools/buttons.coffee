

button_module = angular.module(
    "icsw.tools.button",
    [
    ]
).directive('icswToolsModifyButton', () ->
    return {
        restrict: 'E',
        template: """
<input ng-type="type" name="button" class="btn btn-primary btn-xs" value="icsw modify"/></td>
"""
#<input type="button" class="btn btn-primary btn-xs" ng-click="local_click($event)" value="modify new"/></td>
        scope:
            click: '&'
        link: (scope, element, attrs) ->
            if attrs.type?
                scope.type = attrs.type
            else
                scope.type = "button"

            # TODO: xs vs primaryAction


            element.bind("click", (ev) ->
                attrs.click({event: ev})
            )
            scope.local_click = (ev) ->
                scope.attr({event: ev})

})
