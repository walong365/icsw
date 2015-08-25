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
    "icsw.config.image",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).directive("icswImageOverview",
    ["$templateCache",
     ($templateCache) ->
        controller: "icswImageOverviewCtrl"
        template: $templateCache.get("icsw.image.overview")

]).service("icswImageOverviewService", ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url: ICSW_URLS.REST_IMAGE_LIST
        edit_template: "image.form"
        delete_confirm_str: (obj) -> return "Really delete image '#{obj.name}' ?"
    }
]).controller("icswImageOverviewCtrl",
    ["$scope", "$compile", "$templateCache", "Restangular", "blockUI", "ICSW_URLS",
    ($scope, $compile, $templateCache, Restangular, blockUI, ICSW_URLS) ->
        $scope.arch_rest = Restangular.all(ICSW_URLS.REST_ARCHITECTURE_LIST.slice(1))
        $scope.arch_rest.getList().then((response) ->
            $scope.architectures = response
        )
        $scope.new_entries = []
        $scope.bump_version = (obj) ->
            obj.version++
            obj.put()
        $scope.bump_release = (obj) ->
            obj.release++
            obj.put()
        $scope.delete_ok = (obj) ->
            num_refs = obj.imagedevicehistory_set.length + obj.new_image.length
            return if num_refs == 0 then true else false
]).directive("icswImageHead", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.image.head")
]).directive("icswImageRow", ["$templateCache", "icswSelectionGetDeviceService", "$q", ($templateCache, icswSelectionGetDeviceService, $q) ->
    restrict: "EA"
    template: $templateCache.get("icsw.image.row")
    link: (scope, el, attrs) ->
        scope.$watch('obj', (image)->
            image.usecount_tooltip = ""

            promises = [[], []]
            for pk in image.imagedevicehistory_set
                promises[0].push icswSelectionGetDeviceService(pk)

            for pk in image.new_image
                promises[1].push icswSelectionGetDeviceService(pk)

            wait_list = $q.all(
                [$q.all(promises[0]),
                 $q.all(promises[1])]
            )
            wait_list.then((results) ->
                image.usecount_tooltip = ""
                if results[0].length + results[1].length > 0
                    image.usecount_tooltip += (pre.name for pre in results[0]).join(', ')
                    image.usecount_tooltip += " / "
                    image.usecount_tooltip += (post.name for post in results[1]).join(', ')
            )
        )
]).directive("icswImageHeadNew", ["$templateCache", ($templateCache) ->
    # used in new images table
    restrict: "EA"
    template: $templateCache.get("icsw.image.head.new")
]).directive("icswImageRowNew", ["$templateCache", ($templateCache) ->
    # used in new images table
    restrict: "EA"
    template: $templateCache.get("icsw.image.row.new")
]).directive("icswImageScanButton",
    ["ICSW_URLS", "blockUI", "icswSimpleAjaxCall",
     (ICSW_URLS, blockUI, icswSimpleAjaxCall) ->
         restrict: 'E'
         template: """
<icsw-tools-button type="search" value="Scan for images" ng-click="scan_for_images()"></icsw-tools-button>
"""
         scope:
            'new_entries': '=newEntries'
         link: (scope, el, attrs)  ->
             scope.scan_for_images = () =>
                 blockUI.start()
                 icswSimpleAjaxCall(
                     url     : ICSW_URLS.SETUP_RESCAN_IMAGES
                     title   : "scanning for new images"
                 ).then(
                     (xml) ->
                         blockUI.stop()
                         # update list in-place
                         scope.new_entries.length = 0
                         $(xml).find("found_images found_image").each (idx, new_img) =>
                             new_img = $(new_img)
                             new_obj = {
                                 "name"    : new_img.attr("name")
                                 "vendor"  : new_img.attr("vendor")
                                 "version" : new_img.attr("version")
                                 "arch"    : new_img.attr("arch")
                                 "present" : parseInt(new_img.attr("present"))
                             }
                             scope.new_entries.push(new_obj)
                     (error) ->
                         blockUI.stop()
                 )
]).directive("icswImageBuildButton",
    ["ICSW_URLS", "icswSimpleAjaxCall",
     (ICSW_URLS, icswSimpleAjaxCall) ->
         restrict: 'E'
         template: """
<icsw-tools-button type="image" size="xs" ng-click="build_image()"></icsw-tools-button>
"""
         scope:
             'reload': '='
             'image': '&'
         link: (scope, el, attrs) ->
             scope.build_image = () ->
                 icswSimpleAjaxCall(
                     url: ICSW_URLS.SETUP_BUILD_IMAGE
                     data:
                         image_pk: scope.image().idx
                 ).then(
                     (xml) ->
                         scope.reload()
                 )
]).directive("icswImageNewImages",
    ["ICSW_URLS", "blockUI", "icswSimpleAjaxCall", "icswImageOverviewService", "$interval",
     (ICSW_URLS, blockUI, icswSimpleAjaxCall, icswImageOverviewService, $interval) ->
         restrict: 'E'
         templateUrl: "icsw.image.new-images"
         scope:
            'new_entries': '=newEntries'
            'reload': '='
         link: (scope, el, attrs) ->
             scope.take_image = (obj) =>
                 blockUI.start()
                 icswSimpleAjaxCall(
                     url     : ICSW_URLS.SETUP_USE_IMAGE
                     data    :
                         "img_name" : obj.name
                     title   : "scanning for new images"
                 ).then(
                     (xml) ->
                         blockUI.stop()
                         scope.new_entries.length = 0
                         scope.reload()
                     (error) ->
                         blockUI.stop()
                 )
             update_interval_handle = $interval(
                 () -> scope.reload()
                 30000
             )

             scope.$on(
                 "$destroy"
                 () -> $interval.cancel(update_interval_handle)
             )
])
