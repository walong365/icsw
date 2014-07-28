{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

enter_password_template = """
<div class="modal-header"><h3>Please enter the new password</h3></div>
<div class="modal-body">
    <form name="form">
        <div ng-class="dyn_check(pwd.pwd1)">
            <label>Password:</label>
            <input type="password" ng-model="pwd.pwd1" placeholder="enter password" ng-trim="false" class="form-control"></input>
        </div>
        <div ng-class="dyn_check(pwd.pwd2)">
            <label>again:</label>
            <input type="password" ng-model="pwd.pwd2" placeholder="confirm password" ng-trim="false" class="form-control"></input>
        </div>
    </form>
</div>
<div class="modal-footer">
    <div ng-class="pwd_error_class">
       {% verbatim %}
           {{ pwd_error }}
       {% endverbatim %}
    </div>
    <div>
        <button class="btn btn-primary" ng-click="check()">Check</button>
        <button class="btn btn-success" ng-click="ok()" ng-show="check()">Save</button>
        <button class="btn btn-warning" ng-click="cancel()">Cancel</button>
    </div>
</div>
"""

angular_add_password_controller = (module, name) ->
    module.run(($templateCache) ->
        $templateCache.put("set_password.html", enter_password_template)
    )
    module.controller("password_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
        ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
            $scope.$on("icsw.enter_password", () ->
                $modal.open
                    template : $templateCache.get("set_password.html")
                    controller : ($scope, $modalInstance, scope) ->
                        $scope.pwd = {
                            "pwd1" : ""
                            "pwd2" : ""
                        }
                        $scope.dyn_check = (val) ->
                            $scope.check()
                            _rc = []
                            if val.length < 8
                                _rc.push("has-error")
                            return _rc.join(" ")
                        $scope.ok = () ->
                            $modalInstance.close(true)
                            scope.$emit("icsw.set_password", $scope.pwd.pwd1)
                        $scope.check = () ->
                            if $scope.pwd.pwd1 == "" and $scope.pwd.pwd1 == $scope.pwd.pwd2
                                $scope.pwd_error = "empty passwords"
                                $scope.pwd_error_class = "alert alert-warning"
                                return false
                            else if $scope.pwd.pwd1.length >= 8 and $scope.pwd.pwd1 == $scope.pwd.pwd2
                                $scope.pwd_error = "passwords match"
                                $scope.pwd_error_class = "alert alert-success"
                                return true
                            else
                                $scope.pwd_error = "passwords do not match or too short"
                                $scope.pwd_error_class = "alert alert-danger"
                                return false
                        $scope.cancel = () ->
                            $modalInstance.dismiss("cancel")
                    backdrop : "static"
                    resolve:
                        scope: () ->
                            return $scope
            )
    ])

password_test_module = angular.module("icsw.password.test", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([password_test_module])

angular_add_password_controller(password_test_module)

root.angular_add_password_controller = angular_add_password_controller

{% endinlinecoffeescript %}

</script>
