{% load coffeescript %}

<script type="text/javascript"/>

{% inlinecoffeescript %}

login_module = angular.module("icsw.login", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap"])

login_module.controller("login_ctrl", ["$scope",
    ($scope) ->
        $scope.login_hints = {{ login_hints | safe }}
        $scope.medium_screen = () ->
            return "{{ LOGIN_SCREEN_TYPE }}" == "medium"
        $scope.big_screen = () ->
            return "{{ LOGIN_SCREEN_TYPE }}" == "big"
])

{% endinlinecoffeescript %}

</script>
