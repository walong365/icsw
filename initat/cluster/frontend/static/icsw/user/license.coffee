# Copyright (C) 2012-2015 init.at
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
    "icsw.user.license",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload", "gettext",
    ]
).controller("icswUserLicenseCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$timeout", "$modal",
     "$window", "ICSW_URLS", 'FileUploader', 'blockUI', 'icswParseXMLResponseService', 'icswUserLicenseDataService',
     "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout, $modal,
     $window, ICSW_URLS, FileUploader, blockUI, icswParseXMLResponseService, icswUserLicenseDataService,
     access_level_service) ->
        $scope.get_service_state = (srv) ->
            if $window.SERVICE_TYPES[srv] ? false
                return "success"
            else
                return "danger"
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
        $scope.uploader.onCompleteItem = (item, response, status, headers) ->
            # must not give direct response to the parse service
            response = "<document>" + response + "</document>"
            icswParseXMLResponseService(response)
            icswUserLicenseDataService.reload_data()
            access_level_service.reload()
        $scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            $scope.uploader.clearQueue()
]).directive("icswUserLicenseOverview", ["icswUserLicenseDataService", (icswUserLicenseDataService) ->
    return {
        restrict : "EA"
        controller: 'icswUserLicenseCtrl'
        templateUrl : "icsw.user.license.overview"
        link: (scope, el, attrs) ->
            scope.your_licenses_open = false
            scope.lic_packs_open = false
            scope.lic_upload_open = true
            scope.$watch(
                () -> icswUserLicenseDataService.license_packages.length
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
]).directive("icswUserLicenseYourLicenses",
    ["icswUserLicenseDataService", "$window",
     (icswUserLicenseDataService, $window) ->
        return {
            restrict : "EA"
            templateUrl : "icsw.user.license.your_licenses"
            scope: true
            link: (scope, el, attrs) ->
                icswUserLicenseDataService.add_to_scope(scope)
                scope.get_merged_key_list = (a, b) ->
                    if !a?
                        a = {}
                    if !b?
                        b = {}
                    return _.unique(Object.keys(a).concat(Object.keys(b)))
                _lic_state_cache = {}
                scope._state = (license_id) ->
                    # NOTE: caching currently breaks updating info on new license file uploading new
                    #if !_lic_state_cache[license_id]?  # calculation can also return undefined if data isn't loaded yet
                    #    _lic_state_cache[license_id] =
                    #        icswUserLicenseDataService.calculate_license_state(icswUserLicenseDataService.license_packages,
                    #            license_id, $window.CLUSTER_ID)
                    #return _lic_state_cache[license_id]

                    return icswUserLicenseDataService.calculate_license_state(icswUserLicenseDataService.license_packages,
                        license_id, $window.CLUSTER_ID)
        }
]).directive("icswUserLicensePackages", ["icswUserLicenseDataService", "$window", (icswUserLicenseDataService, $window) ->
    return {
        restrict : "EA"
        controller: 'icswUserLicenseCtrl'
        templateUrl : "icsw.user.license.packages"
        link: (scope, el, attrs) ->
            icswUserLicenseDataService.add_to_scope(scope)
            scope.cluster_accordion_open = {
                0: true  # show first accordion which is the cluster id of this cluster by the ordering below
            }
            scope.package_order_fun = (pack) ->
                return moment(pack.date).unix()
            scope.cluster_order_fun = (data) ->
                # order by is_this_cluster, cluster_id
                prio = 0
                if data[0] == $window.CLUSTER_ID
                    prio -= 1
                return [prio, data[0]]
            scope.get_list = (obj) ->
                if !obj.__transformed_list?
                    obj.__transformed_list = ([k, v] for k, v of obj)
                return obj.__transformed_list

            scope.get_cluster_title = (cluster_id) ->
                if cluster_id == $window.CLUSTER_ID
                    return "Current cluster (#{cluster_id})"
                else
                    return "Cluster #{cluster_id}"
    }
]).service("icswUserLicenseDataService", ["Restangular", "ICSW_URLS", "gettextCatalog", (Restangular, ICSW_URLS, gettextCatalog) ->
    data = {
        all_licenses: []
        license_packages: []
        # no reload:
        license_violations: Restangular.all(ICSW_URLS.ICSW_LIC_GET_LICENSE_VIOLATIONS.slice(1)).customGET().$object
    }

    reload_data = () ->
        Restangular.all(ICSW_URLS.ICSW_LIC_GET_ALL_LICENSES.slice(1)).getList().then((new_list) ->
            data.all_licenses.length = 0
            for entry in new_list
                data.all_licenses.push(entry)
        )

        Restangular.all(ICSW_URLS.ICSW_LIC_GET_LICENSE_PACKAGES.slice(1)).getList().then((new_list) ->
            data.license_packages.length = 0
            for entry in new_list
                data.license_packages.push(entry)
        )

    reload_data()

    data.reload_data = reload_data

    data.get_license_by_id = (id) ->
        return _.find(data.all_licenses, (elem) -> return elem.id == id)

    data.add_to_scope = (scope) ->
        for k, v of data
            if k != 'add_to_scope'
                scope[k] = v


    # NOTE: code below here is just utils, but we can't have it in a proper service since that would create a circular dependency
    _get_license_state = (lic) ->
        # NOTE: keep grace period in sync with py
        if moment(lic.valid_from) < moment() and moment() < (moment(lic.valid_to).add(2, 'weeks'))
            if moment() < moment(lic.valid_to)
                return ([[0], {
                    state_id: 'valid'
                    state_str: gettextCatalog.getString('Valid')
                    date_info: gettextCatalog.getString('until') + ' ' + moment(lic.valid_to).format("YYYY-MM-DD")
                }])
            else
                return ([[3], {
                    state_id: 'grace'
                    state_str: gettextCatalog.getString('In grace period')
                    date_info: gettextCatalog.getString('since') + ' ' + moment(lic.valid_to).format("YYYY-MM-DD")
                }])
        else if moment(lic.valid_from) < moment()
            return ([[5, moment(lic.valid_to)], {
                state_id: 'expired'
                state_str: gettextCatalog.getString('Expired')
                date_info: gettextCatalog.getString('since') + ' ' + moment(lic.valid_to).format("YYYY-MM-DD")
            }])
        else
            return ([[8, moment(lic.valid_from)], {
                state_id: 'valid_in_future'
                state_str: gettextCatalog.getString('Will be valid')
                date_info: gettextCatalog.getString('on') + ' ' + moment(lic.valid_from).format("YYYY-MM-DD")
            }])
    get_license_state_bootstrap_class = (state) ->
        if state?
            return {'valid': 'success', 'expired': 'danger', 'in_grace_period': 'warning', 'valid_in_future': 'warning',
            'parameter_violated': 'danger'}[state]
        else
            return ""
    get_license_state_icon_class = (state) ->
        if state?
            return {'valid': 'fa fa-check', 'expired': 'fa fa-times', 'in_grace_period': 'fa fa-clock-o', 'valid_in_future': 'fa fa-clock-o',
            'parameter_violated': 'fa fa-times'}[state]
        else
            return ""
    get_license_state = (lic) ->
        state =  _get_license_state(lic)
        return if state? then state[1] else undefined

    angular.extend(data, {
        get_license_bootstrap_class : (lic) ->
            state = get_license_state(lic)
            return if state? then get_license_state_bootstrap_class(state.state_id) else undefined
        get_license_state : get_license_state
        get_license_state_bootstrap_class : get_license_state_bootstrap_class
        get_license_state_icon_class: get_license_state_icon_class
        calculate_license_state: (packages, license_id=undefined, cluster_id=undefined) ->
            # calculate the current state of either all licenses in a package or of a certain one for a given cluster_id or all cluster_ids

            # TODO: split up for licadmin and user.license view
            state = undefined
            if packages.length
                states = []
                # build list [priority, data] in states
                for pack in packages

                    check_licenses = (lic_list) ->
                        for pack_lic in lic_list
                            # HACK in licadmin mode, license_id is db index, and in django mode, it's id string, hence both comparisons
                            if !license_id? or pack_lic.id == license_id or pack_lic.license == license_id
                                if !pack_lic?
                                    return  # TODO: investigate
                                lic_state = _get_license_state(pack_lic)
                                lic_state[1].package = pack
                                lic_state[1].lic = pack_lic
                                states.push(lic_state)

                    if pack.licenses?
                        # has list of licenses (usually call from licadmin)
                        if !cluster_id?
                            check_licenses(pack.licenses)
                        else
                            # HACK: in licadmin mode, cluster_id is index in db
                            check_licenses(pack.licenses.filter((elem) -> return elem.cluster_id == cluster_id))
                    else
                        # has dict of cluster_licenses (get_license_packages django view)
                        for cluster_id_iter, cluster_lic_list of pack.cluster_licenses
                            # HACK: in django mode, cluster_id is string (actual cluster id)
                            if cluster_id_iter == cluster_id
                                check_licenses(cluster_lic_list)

                states.sort()
                if states.length
                    state = states[0][1]

            # this is user.license only:
            if data.license_violations[license_id]? and data.license_violations[license_id].type == 'hard'
                if !state?
                    state = {}
                state.state_id = "parameter_violated"
                state.state_str = gettextCatalog.getString('License parameter violated')
            return state
    })

    return data
]).run(["toaster", "icswUserLicenseDataService", "$rootScope", (toaster, icswUserLicenseDataService, $rootScope) ->
    $rootScope.$watch(
        () -> return Object.keys(icswUserLicenseDataService.license_violations).length
        () ->
            if icswUserLicenseDataService.license_violations? and icswUserLicenseDataService.license_violations.plain?
                for lic, data of icswUserLicenseDataService.license_violations.plain()
                    msg = "Your license for #{data['name']} is violated.\nPlease check the license page for details."
                    toaster.pop("warning", "License violated", msg, 10000)
    )
])
