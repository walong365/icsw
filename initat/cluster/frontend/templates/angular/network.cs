{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

nw_types_dict = [
    {"value":"b", "name":"boot"}
    {"value":"p", "name":"prod"}
    {"value":"s", "name":"slave"}
    {"value":"o", "name":"other"}
    {"value":"l", "name":"local"}
]

network_module = angular.module("icsw.network", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"]
).directive('icswRestTable', (Restangular, $parse, $injector, $compile, $templateCache, $modal) ->
    return {
    # TODO: move to common
        restrict: 'E',
        link: (scope, element, attrs) ->
            scope.config_service = $injector.get(attrs.configService)

            scope.config_service.use_modal ?= true

            scope.data_received = (data) ->
                scope[attrs.targetList] = data

            scope.rest = Restangular.all(scope.config_service.rest_url.slice(1))

            scope.reload = () ->
                scope.rest.getList().then(scope.data_received)
                if scope.config_service.after_reload
                    scope.config_service.after_reload()


            scope.reload()

            # interface functions to use in directive body
            scope.edit = (event, obj) ->
                scope.pre_edit_obj = angular.copy(obj)
                scope.create_or_edit(event, false, obj)
            scope.create = (event) ->
                if typeof(scope.config_service.new_object) == "function"
                    scope.new_obj = scope.config_service.new_object()
                else
                    scope.new_obj = scope.config_service.new_object
                scope.create_or_edit(event, true, scope.new_obj)
            scope.create_or_edit = (event, create_or_edit, obj) ->
                scope.edit_obj = obj
                scope.create_mode = create_or_edit
                if scope.fn and scope.fn.create_or_edit
                    scope.fn.create_or_edit(scope, scope.create_mode, obj)
                if scope.config_service.use_modal
                    scope.edit_div = $compile($templateCache.get(scope.config_service.edit_template))(scope)
                    scope.edit_div.simplemodal
                        #opacity      : 50
                        position     : [event.clientY - 50, event.clientX - 50]
                        #autoResize   : true
                        #autoPosition : true
                        onShow: (dialog) =>
                            dialog.container.draggable()
                            $("#simplemodal-container").css("height", "auto")
                            scope.modal_active = true
                        onClose: (dialog) =>
                            scope.close_modal()
                else
                    scope.modal_active = true
            scope.modify = () ->
                if not scope.form.$invalid
                    if scope.create_mode
                        scope.rest.post(scope.new_obj).then((new_data) ->
                            scope.entries.push(new_data)
                            scope.close_modal()
                            if scope.config_service.object_created
                                scope.config_service.object_created(scope.new_obj, new_data, scope)
                        )
                    else
                        scope.edit_obj.put().then(
                            (data) ->
                                handle_reset(data, scope.entries, scope.edit_obj.idx)
                                if scope.fn and scope.fn.object_modified
                                    scope.fn.object_modified(scope.edit_obj, data, scope)
                                scope.close_modal()
                            (resp) -> handle_reset(resp.data, scope.entries, scope.edit_obj.idx)
                        )
                else
                    noty
                        text : "form validation problem"
                        type : "warning"
            scope.form_error = (field_name) ->
                # temporary fix, FIXME
                # scope.form should never be undefined
                if scope.form?
                    if scope.form[field_name].$valid
                        return ""
                    else
                        return "has-error"
                else
                    return ""
            scope.hide_modal = () ->
                # hides dummy modal
                if not scope.fn.use_modal and scope.modal_active
                    scope.modal_active = false
            scope.close_modal = () ->
                if scope.config_service.use_modal
                    $.simplemodal.close()
                scope.modal_active = false
                if scope.fn and scope.fn.modal_closed
                    scope.fn.modal_closed(scope)
                    if scope.config_settings.use_modal
                        try
                            # fixme, call digest cycle and ignore if cycle is already running
                            scope.$digest()
                        catch exc
            scope.get_action_string = () ->
                return if scope.create_mode then "Create" else "Modify"
            scope.delete = (obj) ->
                c_modal = $modal.open
                    template : $templateCache.get("simple_confirm.html")
                    controller : simple_modal_ctrl
                    backdrop : "static"
                    resolve :
                        question : () ->
                            return scope.config_service.delete_confirm_str(obj)
                c_modal.result.then(
                    () ->
                        obj.remove().then((resp) ->
                            noty
                                text : "deleted instance"
                            remove_by_idx(scope.entries, obj.idx)
                            if scope.config_service.post_delete
                                scope.config_service.post_delete(scope, obj)
                        )
                )
}).service('icswNetworkDeviceTypesService', () ->
    return {
        # TODO: move to icsw.network in new dir structure
        rest_url           : "{% url 'rest:network_device_type_list' %}"
        delete_confirm_str : (obj) ->
            return "Really delete Network type '#{obj.description}' ?"
        edit_template      : "network_device_type.html"
        new_object: {
                "identifier"  : "eth"
                "description" : "new network device type"
                "name_re"     : "^eth.*$"
                "mac_bytes"   : 6
                "allow_virtual_interfaces" : true
        }
    }
).service('icswNetworkTypesService', () ->
    return {
        # TODO: move to icsw.network in new dir structure
        rest_url            : "{% url 'rest:network_type_list' %}"
        edit_template       : "network_type.html"
        delete_confirm_str  : (obj) -> return "Really delete Network type '#{obj.description}' ?"
        new_object          : {"identifier" : "p", description : ""}
        object_created      : (new_obj) -> new_obj.description = ""
        network_types       : nw_types_dict  # for create/edit dialog
    }
).controller('icswCommonDummyCtrl', () ->
    # TODO: move to common
).service('icswNetworksService', (Restangular, $q, icswTools) ->

    networks_rest = Restangular.all("{% url 'rest:network_list' %}".slice(1)).getList({"_with_ip_info" : true}).$object
    network_types_rest = Restangular.all("{% url 'rest:network_type_list' %}".slice(1)).getList({"_with_ip_info" : true}).$object
    network_device_types_rest = Restangular.all("{% url 'rest:network_device_type_list' %}".slice(1)).getList({"_with_ip_info" : true}).$object

    network_display = {}
    get_defer = (q_type) ->
        d = $q.defer()
        result = q_type.then(
           (response) ->
               d.resolve(response)
        )
        return d.promise

    hide_network =  () ->
        network_display.active_network = null
        network_display.iplist = []

    return {
        # TODO: move to icsw.network in new dir structure
        rest_url            : "{% url 'rest:network_list' %}"
        edit_template       : "network.html"
        networks            : networks_rest
        network_types       : network_types_rest
        network_device_types: network_device_types_rest
        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"
        new_object          : () ->
            return {
                "identifier"   : "new network",
                "network_type" : (entry["idx"] for key, entry of network_types_rest when typeof(entry) == "object" and entry and entry["identifier"] == "o")[0]
                "enforce_unique_ips" : true
                "num_ip"       : 0
            }
        network_display     : network_display
        show_network        : (obj) ->
            if network_display.active_network == obj
                hide_network()
            else
                network_display.active_network = obj
                q_list = [
                    get_defer(Restangular.all("{% url 'rest:net_ip_list' %}".slice(1)).getList({"network" : obj.idx, "_order_by" : "ip"}))
                    get_defer(Restangular.all("{% url 'rest:netdevice_list' %}".slice(1)).getList({"net_ip__network" : obj.idx}))
                    get_defer(Restangular.all("{% url 'rest:device_list' %}".slice(1)).getList({"netdevice__net_ip__network" : obj.idx}))
                ]
                $q.all(q_list).then((data) ->
                    iplist = data[0]
                    netdevices = icswTools.build_lut(data[1])
                    devices = icswTools.build_lut(data[2])
                    for entry in iplist
                        nd = netdevices[entry.netdevice]
                        entry.netdevice_name = nd.devname
                        entry.device_full_name = devices[nd.device].full_name
                    network_display.iplist = iplist
                )
        hide_network : hide_network
        after_reload : () ->
             hide_network()
        fn:
            get_production_networks : ($scope) ->
                prod_idx = (entry for key, entry of $scope.rest_data.network_types when typeof(entry) == "object" and entry and entry["identifier"] == "p")[0].idx
                return (entry for key, entry of $scope.entries when typeof(entry) == "object" and entry and entry.network_type == prod_idx)
            is_slave_network : ($scope, nw_type) ->
                if nw_type
                    return (entry for key, entry of $scope.rest_data.network_types when typeof(entry) == "object" and entry and entry["idx"] == nw_type)[0].identifier == "s"
                else
                    return false
            has_master_network : (edit_obj) ->
                return if edit_obj.master_network then true else false
    }
)


{% endinlinecoffeescript %}

</script>
