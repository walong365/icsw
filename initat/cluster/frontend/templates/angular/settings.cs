{% load i18n coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

settings_module = angular.module("icsw.settings", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

angular_add_password_controller(settings_module)

settings_module.controller("settings_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", "$window", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal, $window) ->
        wait_list = restDataSource.add_sources([
            ["{% url 'rest:cluster_setting_list' %}", {}]
        ])
        $q.all(wait_list).then(
            (data) ->
                $scope.edit_obj = (entry for entry in data[0] when entry.name == "GLOBAL")[0]
        )
        $scope.update_settings = () ->
            $scope.edit_obj.put().then(
               (data) ->
               (resp) ->
            )
        $scope.get_lic_class = (lic) ->
            if lic.enabled
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.get_services = (lic) ->
            if lic of $window.CLUSTER_LICENSE
                return $window.CLUSTER_LICENSE[lic].services
            else
                return []
        $scope.get_service_state = (srv) ->
            if $window.SERVICE_TYPES[srv] ? false
                return "success"
            else
                return "danger"
        $scope.get_lic_value = (lic) ->
            return if lic.enabled then "enabled" else "disabled"
        $scope.change_lic = (lic) ->
            Restangular.restangularizeElement(null, lic, "{% url 'rest:cluster_license_detail' 1 %}".slice(1).slice(0, -2))
            lic.enabled = !lic.enabled
            lic.put()
])

{% endinlinecoffeescript %}

</script>

