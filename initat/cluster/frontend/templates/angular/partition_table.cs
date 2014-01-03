{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

partition_table_module = angular.module("icsw.partition_table", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([partition_table_module])

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
            {"short" : "partition_fs"      , "url" : "{% url 'rest:partition_fs_list' %}"}
        ]
        post_delete : ($scope) ->
            $scope.close_modal()
        fn:
            delete_ok:  (obj) ->
                num_refs = obj.act_partition_table.length + obj.new_partition_table.length
                return if num_refs == 0 then true else false
        
    }
)

class edit_mixin
    constructor : (@scope, @templateCache, @compile, @modal, @Restangular) ->
    create : (event) =>
        if @new_object
            @scope.new_obj = @new_object(@scope)
        else
            @scope.new_obj = {}
        @create_or_edit(event, true, @scope.new_obj)
    edit : (obj, event) =>
        @create_or_edit(event, false, obj)
    create_or_edit : (event, create_or_edit, obj) =>
        @scope._edit_obj = obj
        @scope.pre_edit_obj = angular.copy(obj)
        @scope.create_mode = create_or_edit
        @scope.cur_edit = @
        if not @scope.create_mode
            @Restangular.restangularizeElement(null, @scope._edit_obj, @modify_rest_url)
        @scope.action_string = if @scope.create_mode then "Create" else "Modify"
        @edit_div = @compile(@templateCache.get(if @scope.create_mode then @create_template else @edit_template))(@scope)
        @edit_div.simplemodal
            #opacity      : 50
            position     : [event.pageY, event.pageX]
            #autoResize   : true
            #autoPosition : true
            onShow: (dialog) => 
                dialog.container.draggable()
                $("#simplemodal-container").css("height", "auto")
                @_modal_close_ok = false
                @scope.modal_active = true
            onClose: (dialog) =>
                @close_modal()
    close_modal : () =>
        $.simplemodal.close()
        #console.log scope.pre_edit_obj.pnum, scope._edit_obj.pnum
        if @scope.modal_active
            @scope.$emit("icsw.em.modal_closed")
            #console.log "*", @_modal_close_ok, @scope.pre_edit_obj
            if not @_modal_close_ok and not @scope.create_mode
                # not working right now, hm ...
                true
                #@scope._edit_obj = angular.copy(@scope.pre_edit_obj)
                #console.log @scope._edit_obj.pnum, @scope.pre_edit_obj.pnum
                #@scope._edit_obj.pnum = 99
                #console.log @scope._edit_obj, @scope.pre_edit_obj
        @scope.modal_active = false
    form_error : (field_name) =>
        if @scope.form[field_name].$valid
            return ""
        else
            return "has-error"
    modify : () ->
        # console.log @scope.form.$invalid, @scope.create_mode, @scope.new_obj
        if not @scope.form.$invalid
            if @scope.create_mode
                @create_rest_url.post(@scope.new_obj).then((new_data) =>
                    #console.log @create_list, new_data
                    @create_list.push(new_data)
                    @close_modal()
                    @_modal_close_ok = true
                )
            else
                @scope._edit_obj.put().then(
                    (data) => 
                        handle_reset(data, @scope._edit_obj, null)
                        @_modal_close_ok = true
                        @close_modal()
                    (resp) => handle_reset(resp.data, @scope._edit_obj, null)
                )
        else
            console.log "inv", @scope.form
    modal_ctrl : ($scope, $modalInstance, question) ->
        $scope.question = question
        $scope.ok = () ->
            $modalInstance.close(true)
        $scope.cancel = () ->
            $modalInstance.dismiss("cancel")
    delete_obj : (obj) =>
        c_modal = @modal.open
            template : @templateCache.get("simple_confirm.html")
            controller : @modal_ctrl
            backdrop : "static"
            resolve :
                question : () =>
                    if @delete_confirm_str
                        return @delete_confirm_str(obj)
                    else
                        return "Really delete object ?"
        c_modal.result.then(
            () =>
                # add restangular elements
                @Restangular.restangularizeElement(null, obj, @modify_rest_url)
                obj.remove().then((resp) =>
                    noty
                        text : "deleted instance"
                    remove_by_idx(@delete_list, obj.idx)
                )
        )

partition_table_module.directive("disklayout", ($compile, $modal, $templateCache, Restangular) ->
    return {
        restrict : "EA"
        scope : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                scope.$on("icsw.em.modal_closed", (args) ->
                    scope.validate()
                )
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
                scope.layout_edit = new edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
                scope.layout_edit.create_template = "partition_disc.html"
                scope.layout_edit.create_rest_url = Restangular.all("{% url 'rest:partition_disc_list' %}".slice(1))
                scope.layout_edit.create_list = scope.edit_obj.partition_disc_set
                scope.layout_edit.new_object = (scope) ->
                    return {
                        "partition_table" : scope.edit_obj.idx
                        "disc"            : "/dev/sd"
                    }
                scope.sys_edit = new edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
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
)

partition_table_module.directive("partclean", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        replace : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                # dirty but working
                # console.log element.parent().find("tr[class*='icsw_dyn']").length
                element.parent().find("tr[class*='icsw_dyn']").remove()
    }
)

partition_table_module.directive("partdisc", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        #replace : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                scope.disc_edit = new edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
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
)

partition_table_module.directive("part", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("part.html")
        link : (scope, element, attrs) ->
            scope.part_edit = new edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
            scope.part_edit.edit_template = "partition.html"
            scope.part_edit.modify_rest_url = "{% url 'rest:partition_detail' 1 %}".slice(1).slice(0, -2)
            scope.part_edit.delete_list = scope.disc.partition_set
            scope.part_edit.delete_confirm_str = (obj) -> "Really delete partition '#{obj.pnum}' ?"
            #element.replaceWith($compile($templateCache.get("part.html"))(scope))
            #element.append($compile($templateCache.get("part.html"))(scope))
    }
)

partition_table_module.directive("partsys", ($compile, $templateCache, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("sys_part.html")
        #compile: (tElement, tAttrs) ->
        link : (scope, element, attrs) ->
            # console.log scope, element, attrs, scope.layout
            scope.sys_edit = new edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
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
