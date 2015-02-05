

button_module = angular.module(
    "icsw.tools.button",
    [
    ]
).directive('icswToolsModifyButton', () ->
    return {
        restrict: 'E',
        template: """
<input ng-attr-type="{{type}}" name="button" class="btn btn-primary {{additional_class}}" value="modify"/></input>
"""
        scope:
            click: '&'  # http://stackoverflow.com/questions/17556703/angularjs-directive-call-function-specified-in-attribute-and-pass-an-argument-to
        link: (scope, element, attrs) ->
            if attrs.type?
                scope.type = attrs.type
            else
                scope.type = "button"

            if attrs.size?
                scope.additional_class = "btn-xs"
            else
                scope.additional_class = ""

            element.bind("click", (ev) ->
                if scope.click?
                    scope.click({event: ev})
            )

})
