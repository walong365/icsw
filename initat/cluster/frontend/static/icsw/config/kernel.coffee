DT_FORM = "YYYY-MM-DD HH:mm"

kernel_module = angular.module(
    "icsw.config.kernel",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).directive("icswKernelOverview", ["$templateCache", ($templateCache) ->
    template: $templateCache.get("icsw.kernel.overview")
]).service("icswKernelOverviewService", ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url            : ICSW_URLS.REST_KERNEL_LIST
        edit_template       : "kernel.form"
        delete_confirm_str  : (obj) -> return "Really delete kernel '#{obj.name}' ?"
        get_initrd_built : (kernel) ->
            if kernel.initrd_built
                return moment(kernel.initrd_built).format(DT_FORM)
            else
                return "N/A"
        get_flag_value : (kernel, flag_name) ->
            return if kernel[flag_name] then "yes" else "no"
    }
]).controller("icswKernelOverviewCtrl", ["$scope", "$compile", "$templateCache", "Restangular", "blockUI", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $compile, $templateCache, restangular, blockUI, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
        $scope.delete_ok = (obj) ->
            num_refs = obj.act_kernel.length + obj.new_kernel.length
            return if num_refs == 0 then true else false
        $scope.scan_for_kernels = (reload_func) =>
            blockUI.start()
            icswCallAjaxService
                url     : ICSW_URLS.SETUP_RESCAN_KERNELS
                title   : "scanning for new kernels"
                success : (xml) =>
                    blockUI.stop()
                    reload_func()
]).directive("icswKernelHead", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.kernel.head")
]).directive("icswKernelRow", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    template: $templateCache.get("icsw.kernel.row")
])
