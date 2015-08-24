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
).directive("icswImageOverview", ["$templateCache", ($templateCache) ->
    controller: "icswImageOverviewCtrl"
    template: $templateCache.get("icsw.image.overview")
]).service("icswImageOverviewService", ["ICSW_URLS", (ICSW_URLS) ->
    _scope = undefined
    return {
        rest_url: ICSW_URLS.REST_IMAGE_LIST
        edit_template: "image.form"
        delete_confirm_str: (obj) -> return "Really delete image '#{obj.name}' ?"
        init_fn: (scope) ->
            _scope = scope
        reload_list : () ->
            _scope.reload()
    }
]).controller("icswImageOverviewCtrl", ["$scope", "$compile", "$templateCache", "Restangular", "blockUI", "ICSW_URLS", "icswSimpleAjaxCall", "icswImageOverviewService",
    ($scope, $compile, $templateCache, Restangular, blockUI, ICSW_URLS, icswSimpleAjaxCall, icswImageOverviewService) ->
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
        $scope.scan_for_images = () =>
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.SETUP_RESCAN_IMAGES
                title   : "scanning for new images"
            ).then(
                (xml) ->
                    blockUI.stop()
                    new_list = []
                    $(xml).find("found_images found_image").each (idx, new_img) =>
                        new_img = $(new_img)
                        new_obj = {
                            "name"    : new_img.attr("name")
                            "vendor"  : new_img.attr("vendor")
                            "version" : new_img.attr("version")
                            "arch"    : new_img.attr("arch")
                            "present" : parseInt(new_img.attr("present"))
                        }
                        new_list.push(new_obj)
                    $scope.new_entries = new_list
                (error) ->
                    blockUI.stop()
            )
        $scope.take_image = (obj) =>
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.SETUP_USE_IMAGE
                data    :
                    "img_name" : obj.name
                title   : "scanning for new images"
            ).then(
                (xml) ->
                    blockUI.stop()
                    $scope.new_entries = []
                    icswImageOverviewService.reload_list()
                (error) ->
                    blockUI.stop()
            )
]).directive("icswImageHead", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.image.head")
]).directive("icswImageRow", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.image.row")
]).directive("icswImageHeadNew", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.image.head.new")
]).directive("icswImageRowNew", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.image.row.new")
])
