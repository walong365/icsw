

button_module = angular.module(
    "icsw.tools.button",
    [
    ]
).directive('icswToolsButton', () ->
    return {
        restrict: 'E',
        template: """
<button ng-attr-type="{{button_type}}" name="button" class="btn {{css_class}} {{additional_class}} {{icon_class}}" title="{{button_value}}">
    {{value}} {{button_value}}
</button>
"""
        scope:
            click: '&'  # http://stackoverflow.com/questions/17556703/angularjs-directive-call-function-specified-in-attribute-and-pass-an-argument-to
            isShow: '&'
        link: (scope, element, attrs) ->

            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload"
            # - click: gets executed on click
            # - buttonType: inserted into type, so use "button" or "submit" (default is "button")
            # - size: inserted into "btn-{{size}}", no default

            if attrs.type == "modify"
                scope.css_class = "btn-primary"
                scope.button_value = "modify"
                scope.icon_class = "fa fa-wrench"
            else if attrs.type == "create"
                scope.css_class = "btn-success"
                scope.button_value = "create"
                scope.icon_class = "fa fa-plus-circle"
            else if attrs.type == "delete"
                scope.css_class = "btn-danger"
                scope.button_value = "delete"
                scope.icon_class = "fa fa-trash"
            else if attrs.type == "reload"
                scope.css_class = "btn-warning"
                scope.button_value = "reload"
                scope.icon_class = "fa fa-refresh"
            else if attrs.type == "show"
                scope.css_class = "btn-success"
                scope.button_value = "show/hide"
                scope.icon_class = ""
                scope.$watch(scope.isShow
                    (new_val) ->
                        if new_val
                            scope.value = "show"
                        else
                            scope.value = "hide"
                )
            else
                console.error "Invalid button type: ", attrs.type


            if attrs.buttonType?
                scope.button_type = attrs.buttonType
            else
                scope.button_type = "button"

            if attrs.size?
                scope.additional_class = "btn-xs"
            else
                scope.additional_class = ""

            element.bind("click", (ev) ->
                if scope.click?
                    scope.click({$event: ev})
            )

})
