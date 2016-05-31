# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

angular.module(
    "icsw.system.license",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload", "gettext",
        "icsw.backend.system.license",
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.syslicenseoverview", {
            url: "/syslicenseoverview"
            templateUrl: "icsw/main/license/overview.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "License information"
                valid_for_quicklink: true
                rights: (user, acls) ->
                    if user.is_superuser
                        return true
                    else
                        return false
                menuEntry:
                    menukey: "sys"
                    name: "License"
                    icon: "fa-key"
                    ordering: 20
        }
    )
]).controller("icswSystemLicenseCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$uibModal",
    "ICSW_URLS", 'FileUploader', "icswCSRFService", "blockUI", "icswParseXMLResponseService",
    "icswSystemLicenseDataService", "icswAcessLevelService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $uibModal,
    ICSW_URLS, FileUploader, icswCSRFService, blockUI, icswParseXMLResponseService,
    icswSystemLicenseDataService, icswAcessLevelService,
) ->
    $scope.struct = {
        # data valid
        data_valid: false
        # license tree
        license_tree: undefined
    }
    load = () ->
        $q.all(
            [
                icswSystemLicenseDataService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.license_tree = data[0]
                $scope.struct.data_valid = true
        )
    load()
    
    $scope.uploader = new FileUploader(
        scope: $scope
        url: ICSW_URLS.USER_UPLOAD_LICENSE_FILE
        queueLimit: 1
        alias: "license_file"
        formData: []
        removeAfterUpload: true
    )

    icswCSRFService.get_token().then(
        (token) ->
            $scope.uploader.formData.push({"csrfmiddlewaretoken": token})
    )
    $scope.upload_list = []

    $scope.uploader.onBeforeUploadItem = () ->
        blockUI.start()

    $scope.uploader.onCompleteItem = (item, response, status, headers) ->
        # must not give direct response to the parse service
        response = "<document>" + response + "</document>"
        icswParseXMLResponseService(response)
        icswSystemLicenseDataService.reload()
        icswAcessLevelService.reload()

    $scope.uploader.onCompleteAll = () ->
        blockUI.stop()
        $scope.uploader.clearQueue()

]).directive("icswSystemLicenseOverview",
[
    "$q",
(
    $q,
) ->
    return {
        restrict : "EA"
        controller: 'icswSystemLicenseCtrl'
        templateUrl : "icsw.system.license.overview"
        link: (scope, el, attrs) ->
            scope.your_licenses_open = false
            scope.lic_packs_open = false
            scope.lic_upload_open = true
            if false
                scope.$watch(
                    () -> icswSystemLicenseDataService.license_packages.length
                    (new_val, old_val) ->
                        scope.license_views_disabled = new_val == 0
                        # only change accordion states on actual change
                        if old_val == 0 and new_val > 0
                            scope.your_licenses_open = true
                            scope.lic_packs_open = true
                        if old_val > 1 and new_val == 0
                            scope.your_licenses_open = false
                            scope.lic_packs_open = false
                )
    }
]).directive("icswSystemLicenseLocalLicenses",
[
    "$q",
 (
     $q,
 ) ->
        return {
            restrict : "EA"
            templateUrl : "icsw.system.license.local.licenses"
            scope: {
                license_tree: "=icswLicenseTree"
            }
            controller: "icswSystemLicenseLocalLicensesCtrl"
        }
]).controller("icswSystemLicenseLocalLicensesCtrl", [
    "$scope",
(
    $scope,
) ->
    # console.log "$scope=", $scope, $scope.license_tree

    $scope.get_merged_key_list = (a, b) ->
        if !a?
            a = {}
        if !b?
            b = {}
        return _.uniq(Object.keys(a).concat(Object.keys(b)))

    $scope.undefined_to_zero = (x) ->
        return if x? then x else 0
]).directive("icswSystemLicensePackages",
[
    "icswSimpleAjaxCall", "ICSW_URLS",
(
    icswSimpleAjaxCall, ICSW_URLS,
) ->
    return {
        restrict : "EA"
        controller: 'icswSystemLicenseCtrl'
        templateUrl : "icsw.system.license.packages"
        link: (scope, el, attrs) ->
            scope.cluster_accordion_open = {
                0: true  # show first accordion which is the cluster id of this cluster by the ordering below
            }
            scope.package_order_fun = (pack) ->
                return moment(pack.date).unix()

            scope.cluster_order_fun = (data) ->
                # order by is_this_cluster, cluster_id
                prio = 0
                if data[0] == scope.struct.license_tree.cluster_info.CLUSTER_ID
                    prio -= 1
                return [prio, data[0]]

            scope.get_list = (obj) ->
                if !obj.__transformed_list?
                    # cluster-id, license
                    obj.__transformed_list = ([k, v] for k, v of obj)
                return obj.__transformed_list

            scope.get_cluster_title = (cluster_id) ->
                if cluster_id == scope.struct.license_tree.cluster_info.CLUSTER_ID
                    return "Current cluster (#{cluster_id})"
                else
                    return "Cluster #{cluster_id}"
    }
])
