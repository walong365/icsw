{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

partition_table_module = angular.module("icsw.partition_table", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([partition_table_module])

class part_edit_mixin extends angular_edit_mixin
    constructor : (scope, templateCache, compile, modal, Restangular) ->
        super(scope, templateCache, compile, modal, Restangular)
        @change_signal = "icsw.part_changed"
         

angular_add_simple_list_controller(
    partition_table_module,
    "partition_table_base",
    {
        rest_url            : "{% url 'rest:partition_table_list' %}"
        edit_template       : "partition_table.html"
        delete_confirm_str  : (obj) -> return "Really delete partition table '#{obj.name}' ?"
        use_modal           : false
        template_cache_list : ["partition_table_row.html", "partition_table_head.html"]
        rest_map            : [
            {"short" : "partition_fs", "url" : "{% url 'rest:partition_fs_list' %}"}
        ]
        new_object : {
            "name" : "new_part"
            "sys_partition_set" : []
            "lvm_vg_set" : []
            "partition_disc_set" : []
            "lvm_lv_set" : []
        }
        post_delete : ($scope) ->
            $scope.close_modal()
        fn:
            delete_ok:  (obj) ->
                num_refs = obj.act_partition_table.length + obj.new_partition_table.length
                return if num_refs == 0 then true else false
        
    }
)

partition_table_module.directive("disklayout", ($compile, $modal, $templateCache, Restangular) ->
    return {
        restrict : "EA"
        scope : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                scope.$on("icsw.part_changed", (args) ->
                    if not scope.create_mode
                        scope.validate()
                )
                scope.get_partition_fs = () ->
                    for entry in scope.rest_data.partition_fs
                        entry.full_info = "#{entry.name}" + if entry.need_mountpoint then " (need mountpoint)" else "" 
                    return scope.rest_data.partition_fs
                scope.validate = () ->
                    $.ajax
                        url : "{% url 'setup:validate_partition' %}"
                        data : {
                            "pt_pk" : scope.edit_obj.idx
                        }
                        success : (xml) ->
                            parse_xml_response(xml)
                            error_list = []
                            $(xml).find("problem").each (idx, cur_p) =>
                                cur_p = $(cur_p)
                                error_list.push(
                                    {
                                        "msg" : cur_p.text()
                                        "level" : parseInt(cur_p.attr("level"))
                                        "global" : if parseInt(cur_p.attr("g_problem")) then true else false
                                    }
                                )
                            is_valid = if parseInt($(xml).find("problems").attr("valid")) then true else false
                            scope.$apply(
                                scope.edit_obj.valid = is_valid
                                scope.error_list = error_list
                            )
                scope.error_list = []
                # watch edit_obj and validate if changed
                scope.$watch("edit_obj", () ->
                    if not scope.create_mode
                        scope.validate()
                )
                scope.layout_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
                scope.layout_edit.create_template = "partition_disc.html"
                scope.layout_edit.create_rest_url = Restangular.all("{% url 'rest:partition_disc_list' %}".slice(1))
                scope.layout_edit.create_list = scope.edit_obj.partition_disc_set
                scope.layout_edit.new_object = (scope) ->
                    return {
                        "partition_table" : scope.edit_obj.idx
                        "disc"            : "/dev/sd"
                    }
                scope.sys_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
                scope.sys_edit.create_template = "partition_sys.html"
                scope.sys_edit.create_rest_url = Restangular.all("{% url 'rest:sys_partition_list'%}".slice(1))
                scope.sys_edit.create_list = scope.edit_obj.sys_partition_set
                scope.sys_edit.new_object = (scope) ->
                    return {
                        "partition_table" : scope.edit_obj.idx
                        "name"            : "new"
                        "mount_options"   : "defaults"
                        "mountpoint"      : "/"
                    }
                element.replaceWith($compile($templateCache.get("layout.html"))(scope))
    }
).directive("partclean", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        replace : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                # dirty but working
                # console.log element.parent().find("tr[class*='icsw_dyn']").length
                element.parent().find("tr[class*='icsw_dyn']").remove()
    }
).directive("partdisc", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        #replace : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                scope.disc_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
                scope.disc_edit.create_template = "partition.html"
                scope.disc_edit.edit_template = "partition_disc.html"
                scope.disc_edit.modify_rest_url = "{% url 'rest:partition_disc_detail' 1 %}".slice(1).slice(0, -2)
                scope.disc_edit.create_rest_url = Restangular.all("{% url 'rest:partition_list' %}".slice(1))
                scope.disc_edit.create_list = scope.disc.partition_set
                scope.disc_edit.delete_list = scope.edit_obj.partition_disc_set
                scope.disc_edit.delete_confirm_str = (obj) -> "Really delete disc '#{obj.disc}' ?"
                scope.disc_edit.new_object = (scope) ->
                    return {
                        "size" : 128
                        "partition_disc" : scope.disc.idx
                        "partition_fs" : (entry.idx for entry in scope.rest_data.partition_fs when entry.name == "btrfs")[0]
                        "fs_freq" : 1
                        "fs_passno" : 2
                        "pnum" : 1
                        "warn_threshold" : 85
                        "crit_threshold" : 95
                        "mount_options" : "defaults"
                        "partition_hex" : "82"
                    }
                element.replaceWith($compile($templateCache.get("part_disc.html"))(scope))
                #element.append($compile($templateCache.get("part_disc.html"))(scope))
    }
).directive("part", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("part.html")
        link : (scope, element, attrs) ->
            scope.part_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
            scope.part_edit.edit_template = "partition.html"
            scope.part_edit.modify_rest_url = "{% url 'rest:partition_detail' 1 %}".slice(1).slice(0, -2)
            scope.part_edit.delete_list = scope.disc.partition_set
            scope.part_edit.delete_confirm_str = (obj) -> "Really delete partition '#{obj.pnum}' ?"
            #element.replaceWith($compile($templateCache.get("part.html"))(scope))
            #element.append($compile($templateCache.get("part.html"))(scope))
    }
).directive("partsys", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("sys_part.html")
        #compile: (tElement, tAttrs) ->
        link : (scope, element, attrs) ->
            # console.log scope, element, attrs, scope.layout
            scope.sys_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
            scope.sys_edit.edit_template = "partition_sys.html"
            scope.sys_edit.modify_rest_url = "{% url 'rest:sys_partition_detail' 1 %}".slice(1).slice(0, -2)
            scope.sys_edit.delete_list = scope.edit_obj.sys_partition_set
            scope.sys_edit.delete_confirm_str = (obj) -> "Really delete sys partition '#{obj.name}' ?"
            #element.replaceWith($compile($templateCache.get("sys_part.html"))(scope))
            #element.append($compile($templateCache.get("sys_part.html"))(scope))
    }
)

{% endinlinecoffeescript %}

</script>
