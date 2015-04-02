
angular.module(
    "icsw.config.kpi",
    [
        "icsw.config.category_tree", "icsw.tools.utils",
    ]
).controller("icswConfigKpiCtrl", [
    "$scope", "ICSW_URLS", "icswConfigKpiDataService", "$timeout",
    ($scope, ICSW_URLS, icswConfigKpiDataService, $timeout) ->

        cur_edit_kpi = undefined

        $scope.get_cur_edit_kpi = () ->
            return cur_edit_kpi
        this.get_cur_edit_kpi = $scope.get_cur_edit_kpi
        $scope.create_new = () ->
            cur_edit_kpi = {
                available_device_categories: []
                available_monitoring_categories: []
                selected_device_monitoring_category_tuple: []
            }

        $scope.on_submit = () ->
            # only create code here for now
             icswConfigKpiDataService.kpi.post(cur_edit_kpi).then(
                 (obj) ->
                     icswConfigKpiDataService.kpi.push(obj)
                     console.log cur_edit_kpi.selected_device_monitoring_category_tuple
                     for tup in cur_edit_kpi.selected_device_monitoring_category_tuple
                         entry = {
                             kpi: obj.idx
                             device_category: tup[0]
                             monitoring_category: tup[1]
                         }
                         icswConfigKpiDataService.selected_device_monitoring_category_tuple.post(entry).then(
                             (obj) -> icswConfigKpiDataService.selected_device_monitoring_category_tuple.push(obj)
                         )
             )

        $scope.load_kpi = (idx) ->
            # load kpi from db into cur_edit_kpi
            cur_edit_kpi = $scope.get_kpi(idx)
            cur_edit_kpi.selected_device_monitoring_category_tuple = []

            for entry in _.filter(icswConfigKpiDataService.selected_device_monitoring_category_tuple, (elem) -> return elem.kpi == idx)
                cur_edit_kpi.selected_device_monitoring_category_tuple.push(
                    [entry.device_category, entry.monitoring_category]
                )

        #$timeout(
        #    () -> $scope.load_kpi(18)
        #    2000
        #)

        $scope.get_cur_device_categories = () ->
            return if cur_edit_kpi? then cur_edit_kpi.available_device_categories else []
        this.get_cur_device_categories = $scope.get_cur_device_categories
        $scope.get_cur_monitoring_categories = () ->
            return if cur_edit_kpi? then cur_edit_kpi.available_monitoring_categories else []
        this.get_cur_monitoring_categories = $scope.get_cur_monitoring_categories

        $scope.get_kpi = (idx) ->
            return _.find(icswConfigKpiDataService.kpi, (elem) -> return elem.idx == idx)
        $scope.get_dev_cat = (idx) ->
            return _.find(icswConfigKpiDataService.category, (elem) -> return elem.idx == idx)
        $scope.get_mon_cat = (idx) ->
            return _.find(icswConfigKpiDataService.category, (elem) -> return elem.idx == idx)


        $scope.is_checked = (dev_cat_id, mon_cat_id) ->
            return _.some(cur_edit_kpi.selected_device_monitoring_category_tuple, (elem) -> elem[0] == dev_cat_id and elem[1] == mon_cat_id)
        $scope.toggle_dev_mon_cat = (dev_cat_id, mon_cat_id) ->
            elem = [dev_cat_id, mon_cat_id]
            if $scope.is_checked(dev_cat_id, mon_cat_id)
                _.remove(cur_edit_kpi.selected_device_monitoring_category_tuple, elem)
            else
                cur_edit_kpi.selected_device_monitoring_category_tuple.push(elem)


]).directive("icswConfigKpi", [() ->
    return {
        restrict : "E"
        templateUrl: "icsw.config.kpi"
        controller: 'icswConfigKpiCtrl'
    }
]).directive("icswConfigKpiConfigure", [() ->
    return {
        restrict : "E"
        templateUrl: "icsw.config.kpi.configure"
        require: "^icswConfigKpi"
        link: (scope, el, attrs, kpi_ctrl) ->
            scope.monitoring_categories = ["base", "http", "mail"]
            scope.device_categories = ["firewall devices", "ökotex devices"]
    }
]).directive("icswConfigKpiDevMonSelection", ['icswConfigKpiDataService', (icswConfigKpiDataService) ->
    return {
        restrict : "E"
        require  : "^icswConfigKpi"
        templateUrl: "icsw.config.kpi.dev_mon_selection"
        link: (scope, el, attrs, kpi_ctrl) ->

            class base_tree_config extends tree_config
                constructor: (@scope, args) ->
                    super(args)
                    @show_selection_buttons = false
                    @show_icons = false
                    @show_select = true
                    @show_descendants = true
                    @show_childs = false
                get_name : (t_entry) ->
                    cat = t_entry.obj
                    if cat.depth > 1
                        r_info = "#{cat.full_name} (#{cat.name})"
                    else if cat.depth
                        r_info = cat.full_name
                    else
                        r_info = "TOP"
                    return r_info
                handle_click: (entry, event) =>
                    return  # TODO: also select?
                selection_changed: (entry) =>
                    # update selection in model
                    if entry.selected
                        @get_category_list().push(entry.obj.idx)
                    else
                        _.remove(@get_category_list(), (rem_item) -> return rem_item == entry.obj.idx)

            class device_category_tree_config extends base_tree_config
                get_category_list: () ->
                    return kpi_ctrl.get_cur_device_categories()
            class monitoring_category_tree_config extends base_tree_config
                get_category_list: () ->
                    return kpi_ctrl.get_cur_monitoring_categories()

            scope.device_category_tree = new device_category_tree_config()
            scope.monitoring_category_tree = new monitoring_category_tree_config()

            scope.$watch(
                () -> icswConfigKpiDataService.category.length
                () -> scope._rebuild_tree()
            )

            scope.$watch(
                () -> return kpi_ctrl.get_cur_edit_kpi()
                () -> scope._rebuild_tree()
            )

            scope._rebuild_tree = () ->

                scope.device_category_tree.clear_root_nodes()
                scope.monitoring_category_tree = new monitoring_category_tree_config()
                roots = []
                lut = {}
                for entry in icswConfigKpiDataService.category
                    lut[entry.idx] = entry
                    entry.children = []
                    if entry.parent
                        lut[entry.parent].children.push(entry)
                    else
                        roots.push(entry)

                add_to_tree_rec = (tree, node, sel_list) ->
                    _do_add_to_tree = (tree, node) ->
                        t_entry = tree.new_node({folder:false, obj:node, expand: true, selected: node.idx in sel_list})
                        for child in node.children
                            t_child = _do_add_to_tree(tree, child)
                            t_entry.add_child(t_child)
                        return t_entry
                    t_root = _do_add_to_tree(tree, node)
                    tree.add_root_node(t_root)

                for root in roots
                    # first level of children are relevant 'roots', i.e. devices, mon, loc, etc
                    for entry in root.children
                        if entry.name == 'device'
                            add_to_tree_rec(scope.device_category_tree, entry, kpi_ctrl.get_cur_device_categories())
                        if entry.name == 'mon'
                            add_to_tree_rec(scope.monitoring_category_tree, entry, kpi_ctrl.get_cur_monitoring_categories())
    }
]).directive("icswConfigKpiDevMonLinker", ['icswConfigKpiDataService', (icswConfigKpiDataService) ->
    return {
        restrict : "E"
        require  : "^icswConfigKpi"
        templateUrl: "icsw.config.kpi.dev_mon_linker"
        link: (scope, el, attrs, kpi_ctrl) ->
    }
]).service("icswConfigKpiDataService", ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object

    category = get_rest(ICSW_URLS.REST_CATEGORY_LIST.slice(1))
    kpi = get_rest(ICSW_URLS.REST_KPI_LIST.slice(1))
    selected_device_monitoring_category_tuple = get_rest(ICSW_URLS.REST_KPI_SELECTED_DEVICE_MONITORING_CATEGORY_TUPLE_LIST.slice(1))

    return {
        category: category
        kpi: kpi
        selected_device_monitoring_category_tuple: selected_device_monitoring_category_tuple
    }
])

