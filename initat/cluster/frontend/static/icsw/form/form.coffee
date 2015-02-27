
network_module = angular.module("icsw.form",
    [
    ]
).controller('icswFormCtrl', [() ->
]).directive('icswForm', [() ->
    return {
        restrict: 'E'
        controller: 'icswFormCtrl'
        link: (scope, el, attrs, form_ctrl) ->
    }


]).directive('icswFormField', [() ->
    return {
        template: """
<div class="form-group" >
    <label for="{{id}}" class="control-label col-sm-3">
        {{label}}{{asterisk}}
    </label>
    <div class="controls col-sm-8">
        <input class="textinput textInput form-control"  />
    </div>
</div>
"""
        scope: true
        restrict: 'E'
        require: '^icswForm'
        link: (scope, el, attrs, form_ctrl) ->
            #attrs.name for model
    }
])