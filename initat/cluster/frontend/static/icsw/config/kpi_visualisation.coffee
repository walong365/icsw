# Copyright (C) 2015 init.at
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
    "icsw.config.kpi_visualisation",
    [
        "icsw.tools.utils", "icsw.d3", "icsw.tools", "icsw.tools.status_history_utils"
    ]
).directive("icswConfigKpiEvaluationGraph",
    ["icswConfigKpiDataService", "d3_service", "$timeout", "$filter", "icswConfigKpiVisUtils",
    (icswConfigKpiDataService, d3_service, $timeout, $filter, icswConfigKpiVisUtils) ->
        return {
            restrict: "E"
            templateUrl: "icsw.config.kpi.evaluation_graph"
            scope:
                kpiIdx: '&kpiIdx'
            link: (scope, el, attrs) ->
                scope.width = 700
                scope.height = 600
                scope.fun = () -> console.log 'yay'

                scope.kpi_set_to_show = undefined

                top_bottom_padding = 10

                draw_height = scope.height - top_bottom_padding * 2
                draw_width = scope.width - 50  # space for labels on the right side

                scope.tree = undefined
                d3_service.d3().then((d3) ->
                    scope.svg_el = el[0].getElementsByClassName("kpi-visualisation-svg")[0]
                    scope.svg = d3.select(scope.svg_el)
                        .append("g")
                        .attr("transform", "translate(0, #{top_bottom_padding})")
                    scope.tree = d3.layout.tree()
                        .size([draw_width, draw_height])
                        .children((node) ->
                            if node.hide_children then null else return node.origin.operands)
                        #.nodeSize([130, 70])  # this would be nice but changes layout horribly
                        .separation((a, b) -> return 3)
                )

                scope.redraw = () ->
                    # TODO: clear svg
                    if !scope.tree?
                        # wait for tree
                        $timeout(scope.redraw, 200)
                    else
                        if scope.kpiIdx()?
                            kpi = icswConfigKpiDataService.get_kpi(scope.kpiIdx())
                            if kpi.enabled and kpi.result?  # only for enabled's
                                scope.data = kpi.result.json
                                console.log 'drawing', scope.kpiIdx(), kpi, scope.data
                                scope.update_dthree()

                scope.update_dthree = () ->
                    nodes = scope.tree.nodes(scope.data)
                    links = scope.tree.links(nodes)

                    # fixed depth (now handled via nodeSize)
                    # nodes.forEach((d) -> d.y = d.depth * 70)

                    my_translate = (x, y) -> return [x, draw_height - y]

                    diagonal = d3.svg.diagonal()
                        .projection((d) -> return my_translate(d.x, d.y))

                    link = scope.svg.selectAll(".link")
                        .data(links)
#
                    link.enter()
                        .append("g")
                        .attr("class", "link")
                        .append("path")
                        .attr("fill", "none")
                        .attr("stroke", "#ff8888")
                        .attr("stroke-width", "1.5px")
                        .attr("d", diagonal);

                    duration = 0.001  # milliseconds

                    link.transition()
                        .duration(duration)
                        .select("path")
                        .attr("d", diagonal);

                    link.exit().remove()

                    node = scope.svg.selectAll(".node")
                        .data(nodes)

                    node.enter()
                        .append("g")
                        .attr("class", "node")
                        .style("cursor", "pointer")
                        #.attr("transform", (d) -> return "translate(" + d.x + "," + d.y + ")")
                        .attr("transform", (d) -> return "translate(" + my_translate(d.x, d.y).join(",") + ")")

                    node.transition()
                        .duration(duration)
                        .attr("transform", (d) -> return "translate(" + my_translate(d.x, d.y).join(",") + ")")

                    node.exit().remove()


                    #node.append("circle")
                    #    .attr("r", 4.5)

                    #node.append("text")
                    #    #.attr("dx", (d) -> return if d.children then -8 else 8)
                    #    .attr("dx", (d) -> return 8)
                    #    .attr("dy", 3)
                    #    #.style("text-anchor", (d) -> return if d.children then "end" else "start")
                    #    .style("text-anchor", (d) -> return "start")

                    node
                        .html((d) ->
                            res = "<circle r=\"4.5\"></circle> {"
                            cur_height = 3

                            if d.origin.type == 'initial'
                                res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{cur_height}\"> initial data (#{d.objects.length} objects) </text>"
                            else
                                i = 0
                                for kpi_obj in d.objects
                                    if i > 2 # only 3 elems
                                        res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{cur_height}\"> ... </text>"
                                        break
                                    s = icswConfigKpiVisUtils.kpi_obj_to_string(kpi_obj)
                                    s = $filter('limit_text')(s, 40)
                                    res += "<text style=\"font-size: 11px\" dx=\"8\" dy=\"#{cur_height}\"> #{s} </text>"
                                    cur_height += 14
                                    i += 1
                                res += "}"
                                res += "<text style=\"font-size: 11px\" dx=\"0\" dy=\"-15\" text-anchor=\"middle\">"
                                res += "#{d.origin.type}" #{ JSON.stringify(d.origin.arguments)} "
                                res += "(" + (k+"="+v for k, v of d.origin.arguments).join(", ") + ")"
                                res += "</text>"
                            return res
                        )
                        #.text((d) ->
                        #    if d.objects.length > 3
                        #        return "#{d.objects.length} objects"
                        #    else
                        #        return "{" + (d.host_name for d in d.objects).join("\n") + "}"
                        #).each((d) ->
                        #    for ch in d.objects
                        #        d.append("text")
                        #             .text((e) -> e)
                        #)

                    node.on("click", scope.on_node_click)
                    node.on("mouseenter", scope.on_mouse_enter)
                    node.on("mouseleave", scope.on_mouse_leave)

                scope.on_node_click = (node) ->
                    if node.hide_children
                        # unhide recursively
                        unhide_rec = (node) ->
                            node.hide_children = false
                            for child in node.origin.operands
                                unhide_rec(child)

                        unhide_rec(node)
                    else
                        # hide locally
                        node.hide_children = true

                    console.log 'node hide', node.hide_children
                    scope.redraw()
                scope.on_mouse_enter = (node) ->
                    scope.$apply(
                        scope.kpi_set_to_show = node
                    )
                scope.on_mouse_leave = (node) ->
                    scope.$apply(
                        #scope.kpi_set_to_show = undefined
                    )

                scope.$watch(
                    () -> return scope.kpiIdx()
                    () -> scope.redraw()
                )
        }
]).directive("icswConfigKpiShowKpiSet",
    ["icswConfigKpiDataService", "icswConfigKpiVisUtils",
    (icswConfigKpiDataService, icswConfigKpiVisUtils) ->
        return {
            templateUrl: "icsw.config.kpi.show_kpi_set"
            scope: {
                kpi_set: "=kpiSet"
            }
            link: (scope, el, attrs) ->
                icswConfigKpiVisUtils.add_to_scope(scope)
                #scope.$watch(
                #    () -> return scope._get_kpi_set()
                #    (new_set) -> scope.kpi_set = new_set
                #)
    }
]).directive("icswConfigKpiShowKpiObject",
    ["icswConfigKpiDataService", "icswConfigKpiVisUtils", "status_utils_functions",
    (icswConfigKpiDataService, icswConfigKpiVisUtils, status_utils_functions) ->
        return {
            templateUrl: "icsw.config.kpi.show_kpi_object"
            scope: {
                kpi_obj: "=kpiObj"
            }
            replace: true
            link: (scope, el, attrs) ->
                icswConfigKpiVisUtils.add_to_scope(scope)

                scope.update = () ->
                    if scope.kpi_obj.aggregated_tl
                        # dict to list representation
                        status_util_compat_data = ({state: st, value: val} for st, val of scope.kpi_obj.aggregated_tl)
                        [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(status_util_compat_data)
                        console.log 'servi',  scope.service_data

                scope.$watch(
                    () -> return scope.kpi_obj.kpi_id
                    scope.update
                )

        }
]).service("icswConfigKpiVisUtils", () ->
    ret = {
        kpi_obj_to_string: (kpi_obj, verbose) ->
            kpi_obj_to_string_concise = (kpi_obj) ->
                parts = []
                if kpi_obj.host_name
                    parts.push kpi_obj.host_name.split(".")[0]
                if kpi_obj.service_info?
                    parts.push kpi_obj.service_info
                else if kpi_obj.check_command
                    parts.push kpi_obj.check_command

                if kpi_obj.aggregated_tl?
                    parts.push "{" + ( "#{k}: #{(v*100).toFixed(2)}%" for k, v of kpi_obj.aggregated_tl).join(", ") + "}"

                if parts.length
                    return parts.join(":")
                else
                    return JSON.stringify(kpi_obj)

            kpi_obj_to_string_verbose = (kpi_obj) ->
                parts = []
                if kpi_obj.host_name
                    parts.push "Host: #{kpi_obj.host_name.split(".")[0]}"
                if kpi_obj.service_info? # show as in status history, i.e. prefer service_info
                    parts.push "Service: #{kpi_obj.service_info}"
                else if kpi_obj.check_command
                    parts.push "Service: #{kpi_obj.check_command}"

                if kpi_obj.result?
                    parts.push "Result: #{kpi_obj.result}"


                if kpi_obj.aggregated_tl?
                    parts.push "{" + ( "#{k}: #{(v*100).toFixed(2)}%" for k, v of kpi_obj.aggregated_tl).join(", ") + "}"

                return parts.join(",")

            return if verbose then kpi_obj_to_string_verbose(kpi_obj) else kpi_obj_to_string_concise(kpi_obj)
    }

    contents = Object.keys(ret)
    ret.add_to_scope = (scope) ->
        for c in contents
            scope[c] = ret[c]

    return ret
)
