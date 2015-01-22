{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_overview_module = angular.module("icsw.monitoring_overview", 
            ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "smart-table",
             "smart_table_utils", "status_utils", "icsw.device.livestatus"])

monitoring_overview_module.controller("monitoring_overview_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", "msgbus",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout, msgbus) ->
        $scope.filter_settings = {"str_filter": "", "only_selected": true}

        $scope.filter_predicate = (entry) ->
            selected = $scope.get_selected_entries()
            if (!$scope.filter_settings.only_selected) || selected.length == 0
                sel_flag = true
            else
                sel_flag = _.contains(selected, entry)
                    
            try
                str_re = new RegExp($scope.filter_settings.str_filter, "gi")
            catch err
                str_re = new RegExp("^$", "gi")

            # string filter
            sf_flag = entry.name.match(str_re)

            return sf_flag and sel_flag

        wait_list = restDataSource.add_sources([
            ["{% url 'rest:device_list' %}", {}],
        ])
        $device_list = []
        $q.all(wait_list).then( (data) ->
            $scope.device_list = data[0]
            $scope.update_data()
        )

        $scope.get_selected_entries = () ->
            return (entry for entry in $scope.entries when entry.selected)

        $scope.yesterday = moment().subtract(1, "days")
        $scope.last_week = moment().subtract(1, "weeks")

        $scope.entries = []
        $scope.$watch(
                () -> [$scope.entries, $scope.filter_settings]
                () ->
                    $scope.entries_filtered = (entry for entry in $scope.entries when $scope.filter_predicate(entry))
                true)

        $scope.update_data = () ->
            # currently only called on external selection change
            # if this is to be called more often, take care to not destroy selection
            
            if $scope.device_list
                set_initial_sel = $scope.initial_sel.length > 0

                new_entries = []
                for dev in $scope.device_list
                    if ! dev.is_meta_device
                        entry = {
                            'idx': dev.idx
                            'name': dev.name
                        }
                        if set_initial_sel
                            entry['selected'] = _.contains($scope.initial_sel, dev.idx)
                        new_entries.push(entry)
                $scope.entries = new_entries

                $scope.initial_sel = []

                # TODO: livestatus:
                #call_ajax
                #    url  : "{% url 'mon:get_node_status' %}"
                #    data : {
                #        "pk_list" : angular.toJson((dev.idx for dev in $scope.device_list))
                #    }
                #    success : (xml) =>
                #        if parse_xml_response(xml)
                #            service_entries = []
                #            $(xml).find("value[name='service_result']").each (idx, node) =>
                #                service_entries = service_entries.concat(angular.fromJson($(node).text()))
                #            host_entries = []
                #            $(xml).find("value[name='host_result']").each (idx, node) =>
                #                host_entries = host_entries.concat(angular.fromJson($(node).text()))
                #            console.log 'serv', service_entries
                #            console.log 'host', host_entries

        $scope.initial_sel = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.initial_sel = _dev_sel
            $scope.update_data()
            $scope.entries = $scope.entries
            # TODO: since single-app move, this now seems to be executed from apply. Use whichever version works in final single-app version
            #$scope.$apply(  # if we do update_data() from this path, angular doesn't realise it
            #    $scope.entries = $scope.entries
            #)
         
        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.new_devsel(args[1])
        )

]).directive("monitoringoverview", ($templateCache, $timeout) ->
    return {
        restrict : "EA"
        templateUrl: "monitoring_overview_template.html"
        link : (scope, el, attrs) ->
}).run(($templateCache) ->
)

{% endinlinecoffeescript %}

</script>
