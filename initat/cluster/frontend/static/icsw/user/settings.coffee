angular.module(
    "icsw.user.settings",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).controller("icswUserSettingsCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", "$window", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal, $window, ICSW_URLS) ->
        wait_list = restDataSource.add_sources([
            [ICSW_URLS.REST_CLUSTER_SETTING_LIST, {}]
        ])
        $q.all(wait_list).then(
            (data) ->
                $scope.edit_obj = (entry for entry in data[0] when entry.name == "GLOBAL")[0]
                #console.log $scope.edit_obj
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
            Restangular.restangularizeElement(null, lic, ICSW_URLS.REST_CLUSTER_LICENSE_DETAIL.slice(1).slice(0, -2))
            lic.enabled = !lic.enabled
            lic.put()
]).directive("icswUserSettingsOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.settings.overview")
    }
]).directive("icswUserSettingsForm", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("global.settings.form")
    }
])
