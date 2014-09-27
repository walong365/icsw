{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

partition_table_module = angular.module("icsw.partition_table", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular"])

angular_module_setup([partition_table_module])

class part_edit_mixin extends angular_edit_mixin
    constructor : (scope, templateCache, compile, modal, Restangular) ->
        super(scope, templateCache, compile, modal, Restangular)
        @change_signal = "icsw.part_changed"
         

partition_table_module.controller("partition_table_base", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
        $scope.entries = []
        $scope.edit_pts = []
        $scope.pagSettings = paginatorSettings.get_paginator("parts", $scope)
        $scope.pagSettings.conf.filter_settings = {
          
        }
        $scope.reload = (cb_func) ->
            wait_list = [
                restDataSource.reload(["{% url 'rest:partition_table_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:partition_fs_list' %}", {}]),
            ]
            $q.all(wait_list).then((data) ->
                $scope.entries = data[0]
                $scope.partition_fs = data[1]
                if cb_func?
                    cb_func()
            )
        $scope.create = () ->
            names = (entry.name for entry in $scope.entries)
            _idx = -1
            while true
                _idx += 1                  
                new_name = if _idx then "new_part_#{_idx}" else "new_part"
                if not (new_name in names)
                    break
            Restangular.all("{% url 'rest:partition_table_list' %}".slice(1)).post(
                {
                    "name" : new_name
                    "sys_partition_set" : []
                    "lvm_vg_set" : []
                    "partition_disc_set" : []
                    "lvm_lv_set" : []
                }
            ).then((data) ->
                $scope.reload(() ->
                    $scope.edit_part(data)
                )
            )
        $scope.delete_ok = (obj) ->
            return if obj.new_partition_table.length + obj.act_partition_table.length == 0 then true else false
        $scope.not_open = (obj) ->
            return if (entry for entry in $scope.edit_pts when entry.idx == obj.idx).length then false else true
        $scope.close_part = (obj) ->
            $scope.edit_pts = (entry for entry in $scope.edit_pts when entry.idx != obj.idx)
        $scope.delete = (obj) ->
            simple_modal($modal, $q, "really delete partition table '#{obj.name}' ?").then(
                () ->
                    obj.remove().then(
                        $scope.close_part(obj)
                        $scope.entries = (entry for entry in $scope.entries when entry.idx != obj.idx)
                    )
            )
        $scope.edit_part = (obj) ->
            edit_part = (entry for entry in $scope.entries when entry.idx == obj.idx)[0]
            edit_part.tab_active = true
            $scope.edit_pts.push(edit_part)
        $scope.reload()
]).directive("disklayout", ($compile, $modal, $templateCache, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("layout.html")
        scope  : true
        replace : false
        link : (scope, element, attrs) ->
            scope.part = scope.$eval(attrs["partTable"])
            scope.partition_fs = scope.$eval(attrs["partitionFs"])
            scope.edit_obj = scope.part
            scope.$on("icsw.part_changed", (args) ->
                if not scope.create_mode
                    scope.validate()
            )
            scope.valid_label_types = [
                {
                    "label" : "msdos",
                    "info_string" : "MSDOS",
                },
                {
                    "label" : "gpt",
                    "info_string" : "GPT",
                },
            ]
            scope.get_partition_fs = () ->
                for entry in scope.partition_fs
                    entry.full_info = "#{entry.name}" + if entry.need_mountpoint then " (need mountpoint)" else "" 
                return scope.partition_fs
            scope.partition_need_mountpoint = (part) ->
                if part.partition_fs
                    return (entry.need_mountpoint for entry in scope.partition_fs when entry.idx == part.partition_fs)[0]
                else
                    return true
            scope.validate = () ->
                if !scope.part.idx?
                    return
                call_ajax
                    url : "{% url 'setup:validate_partition' %}"
                    data : {
                        "pt_pk" : scope.part.idx
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
            scope.layout_edit.create_list = scope.part.partition_disc_set
            scope.layout_edit.modify_data_after_post = (new_disc) ->
                new_disc.partition_set = []
                new_disc.sys_partition_set = []
            scope.layout_edit.new_object = (scope) ->
                return {
                    "partition_table"   : scope.edit_obj.idx
                    "disc"              : "/dev/sd"
                    "label_type"        : "gpt"
                }
            scope.sys_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
            scope.sys_edit.create_template = "partition_sys.html"
            scope.sys_edit.create_rest_url = Restangular.all("{% url 'rest:sys_partition_list'%}".slice(1))
            scope.sys_edit.create_list = scope.part.sys_partition_set
            scope.sys_edit.new_object = (scope) ->
                return {
                    "partition_table" : scope.edit_obj.idx
                    "name"            : "new"
                    "mount_options"   : "defaults"
                    "mountpoint"      : "/"
                }
            scope.modify = () ->
                scope.part.put()
    }
).directive("partdata", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        scope : false
        template : $templateCache.get("partition_table.html")
        link : (scope, element, attrs) ->
             scope.edit_obj = scope.data
    }
).directive("partdisc", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        #replace : true
        scope : true
        template : $templateCache.get("part_disc.html")
        link : (scope, element, attrs) ->
            if scope.disc.partition_set.length
                # dirty hack but working
                element.after($("<tr>").append($templateCache.get("part_header.html")))
            scope.partition_fs = scope.$eval(attrs["partitionFs"])
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
                    "partition_fs" : (entry.idx for entry in scope.partition_fs when entry.name == "btrfs")[0]
                    "fs_freq" : 1
                    "fs_passno" : 2
                    "pnum" : 1
                    "warn_threshold" : 85
                    "crit_threshold" : 95
                    "mount_options" : "defaults"
                    "partition_hex" : "82"
                }
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
    }
).directive("partsys", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("sys_part.html")
        link : (scope, element, attrs) ->
            scope.sys_edit = new part_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
            scope.sys_edit.edit_template = "partition_sys.html"
            scope.sys_edit.modify_rest_url = "{% url 'rest:sys_partition_detail' 1 %}".slice(1).slice(0, -2)
            scope.sys_edit.delete_list = scope.edit_obj.sys_partition_set
            scope.sys_edit.delete_confirm_str = (obj) -> "Really delete sys partition '#{obj.name}' ?"
    }
).directive("partitiontablerow", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("partition_table_row.html")
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
)

{% endinlinecoffeescript %}

</script>
