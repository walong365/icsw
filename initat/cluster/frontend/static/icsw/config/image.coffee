
image_module = angular.module(
    "icsw.config.image",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).directive("icswImageOverview", ["$templateCache", ($templateCache) ->
    template: $templateCache.get("icsw.image.overview")
]).service("icswImageOverviewService", ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url: ICSW_URLS.REST_IMAGE_LIST
        edit_template: "image.form"
        delete_confirm_str: (obj) -> return "Really delete image '#{obj.name}' ?"
    }
]).controller("icswImageOverviewCtrl", ["$scope", "$compile", "$templateCache", "Restangular", "blockUI", "ICSW_URLS",
    ($scope, $compile, $templateCache, Restangular, blockUI, ICSW_URLS) ->
        $scope.arch_rest = Restangular.all(ICSW_URLS.REST_ARCHITECTURE_LIST.slice(1))
        $scope.arch_rest.getList().then((response) ->
            $scope.architectures = response
        )
        $scope.new_entries = []
        $scope.delete_ok = (obj) ->
            num_refs = obj.act_image.length + obj.new_image.length
            return if num_refs == 0 then true else false
        $scope.scan_for_images = () =>
            blockUI.start()
            call_ajax
                url     : ICSW_URLS.SETUP_RESCAN_IMAGES
                title   : "scanning for new images"
                success : (xml) =>
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
                    # dummy object for testing
                    #new_list.push(
                    #    {
                    #        "name"    : "a"
                    #        "vendor"  : "b"
                    #        "version" : "v"
                    #        "arch"    : "d"
                    #        "present" : 0
                    #    }
                    #)
                    blockUI.stop()
                    $scope.$apply(() ->
                        $scope.new_entries = new_list
                    )
        $scope.take_image = (obj) =>
            blockUI.start()
            call_ajax
                url     : ICSW_URLS.SETUP_USE_IMAGE
                data    : 
                    "img_name" : obj.name
                title   : "scanning for new images"
                success : (xml) =>
                    blockUI.stop()
                    $scope.$apply(() ->
                        $scope.new_entries = []
                    )
                    if parse_xml_response(xml)
                        $scope.reload()
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
