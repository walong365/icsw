angular.module(
    "icsw.user.settings",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload",
    ]
).controller("icswUserLicenseCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$timeout", "$modal", "$window", "ICSW_URLS", 'FileUploader', 'blockUI',
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout, $modal, $window, ICSW_URLS, FileUploader, blockUI) ->
        $scope.licenses = []
        wait_list = restDataSource.add_sources([
            [ICSW_URLS.REST_CLUSTER_LICENSE_LIST, {}]
        ])
        $q.all(wait_list).then(
            (data) ->
                $scope.licenses = data[0]
                $scope.lic_lut = _.transform(
                    $scope.licenses
                    (memo, val) ->
                        memo[val.name] = val
                    {}
                )
        )
        $scope.get_lic_class = (lic) ->
            if lic.enabled
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.get_services = (lic) ->
            # console.log lic, $scope.licenses, lic of $scope.licenses
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
            # Restangular.restangularizeElement(null, lic, ICSW_URLS.REST_CLUSTER_LICENSE_DETAIL.slice(1).slice(0, -2))
            lic.enabled = !lic.enabled
            lic.put()
        $scope.uploader = new FileUploader(
                scope : $scope
                url : ICSW_URLS.USER_UPLOAD_LICENSE_FILE
                queueLimit : 1
                alias : "license_file"
                formData : [
                     "csrfmiddlewaretoken" : $window.CSRF_TOKEN
                ]
                removeAfterUpload : true
        )
        $scope.upload_list = []
        $scope.uploader.onBeforeUploadItem = () ->
            blockUI.start()
        $scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            $scope.uploader.clearQueue()
]).directive("icswUserLicenseOverview",
    ["$templateCache", 'FileUploader', 'blockUI', 'ICSW_URLS', '$window',
    ($templateCache, FileUploader, blockUI, ICSW_URLS, $window) ->
        return {
            restrict : "EA"
            controller: 'icswUserLicenseCtrl'
            template : $templateCache.get("icsw.user.license.overview")
            link: (scope, el, attrs) ->


        }
])

