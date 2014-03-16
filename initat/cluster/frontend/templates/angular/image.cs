{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

image_module = angular.module("icsw.image", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([image_module])

angular_add_simple_list_controller(
    image_module,
    "image_base",
    {
        rest_url            : "{% url 'rest:image_list' %}"
        edit_template       : "image.html"
        delete_confirm_str  : (obj) -> return "Really delete image '#{obj.name}' ?"
        template_cache_list : ["image_row.html", "image_head.html", "image_new_row.html", "image_new_head.html"]
    }
)

image_module.controller("image", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.arch_rest = Restangular.all("{% url 'rest:architecture_list' %}".slice(1))
        $scope.arch_rest.getList().then((response) ->
            $scope.architectures = response
        )
        $scope.new_entries = []
        $scope.delete_ok = (obj) ->
            num_refs = obj.act_image.length + obj.new_image.length
            return if num_refs == 0 then true else false
        $scope.scan_for_images = () =>
            $.blockUI()
            call_ajax
                url     : "{% url 'setup:rescan_images' %}"
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
                    $.unblockUI()
                    $scope.$apply(() ->
                        $scope.new_entries = new_list
                    )
        $scope.take_image = (obj) =>
            $.blockUI()
            call_ajax
                url     : "{% url 'setup:use_image' %}"
                data    : 
                    "img_name" : obj.name
                title   : "scanning for new images"
                success : (xml) =>
                    $.unblockUI()
                    $scope.$apply(() ->
                        $scope.new_entries = []
                    )
                    if parse_xml_response(xml)
                        $scope.reload()
])

{% endinlinecoffeescript %}

</script>
