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
        "icsw.tools.utils", "icsw.d3",
    ]
).directive("icswConfigKpiEvaluationGraph",
    ["icswConfigKpiDataService", "d3_service", "$timeout",
    (icswConfigKpiDataService, d3_service, $timeout) ->
        return {
            restrict: "E"
            #templateNamespace: "svg"
            #replace: true
            template: """
<div>
    <svg width="600" height="600" class="kpi-visualisation-svg" style="float: left"></svg>
    <div style="float: left; width: 400px">
        obj:
        {{a}}
    </div>
</div>
"""
            scope:
                kpiIdx: '&kpiIdx'
            link: (scope, el, attrs) ->

                d3_service.d3().then((d3) ->
                    scope.svg_el = el[0].getElementsByClassName("kpi-visualisation-svg")[0]
                    scope.svg = d3.select(scope.svg_el)
                        .append("g")
                        .attr("transform", "translate(10,-30)")
                    scope.tree = d3.layout.tree()
                        .size([400, 550])
                        .children((node) -> return node.origin.operands ) # if node.? then node.parents else null)

                )
                scope.tree = undefined

                height = 600

                scope.redraw = () ->
                    if !scope.tree?
                        # wait for tree
                        $timeout(scope.redraw, 200)
                    else
                        if scope.kpiIdx()?
                            kpi = icswConfigKpiDataService.get_kpi(scope.kpiIdx())
                            if kpi.enabled and kpi.result?  # only for enabled's
                                data = kpi.result.json
                                console.log 'drawing', scope.kpiIdx(), kpi, data
                                nodes = scope.tree.nodes(data)
                                links = scope.tree.links(nodes)

                                diagonal = d3.svg.diagonal()
                                    .projection((d) -> return [d.x, height - d.y])

                                link = scope.svg.selectAll(".link")
                                    .data(links)
                                    .enter()
                                    .append("g")
                                    .attr("class", "link")

                                link.append("path")
                                    .attr("fill", "none")
                                    .attr("stroke", "#ff8888")
                                    .attr("stroke-width", "1.5px")
                                    .attr("d", diagonal);

                                node = scope.svg.selectAll(".node")
                                    .data(nodes)
                                    .enter()
                                    .append("g")
                                    .attr("class", "node")
                                    .style("cursor", "pointer")
                                    # diagonal:
                                    #.attr("transform", (d) -> return "translate(" + d.y + "," + d.x + ")")
                                    .attr("transform", (d) -> return "translate(" + d.x + "," + (height - d.y) + ")")

                                #node.append("circle")
                                #    .attr("r", 4.5)

                                #node.append("text")
                                #    #.attr("dx", (d) -> return if d.children then -8 else 8)
                                #    .attr("dx", (d) -> return 8)
                                #    .attr("dy", 3)
                                #    #.style("text-anchor", (d) -> return if d.children then "end" else "start")
                                #    .style("text-anchor", (d) -> return "start")

                                node.html((d) ->
                                        res = "<circle r=\"4.5\"></circle> {"
                                        cur_height = 3
                                        i = 0
                                        for ch in d.objects
                                            if i > 2 # only 3 elems
                                                res += "<text dx=\"8\" dy=\"#{cur_height}\"> ... </text>"
                                                break
                                            res += "<text dx=\"8\" dy=\"#{cur_height}\"> #{ch} </text>"
                                            cur_height += 14
                                            i += 1
                                        res += "}"
                                        res += "<text dx=\"0\" dy=\"-25\" text-anchor=\"middle\">"
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
                    console.log 'click', node
                scope.on_mouse_enter = (node) ->
                    console.log 'enter', node
                    scope.a = node.objects
                scope.on_mouse_leave = (node) ->
                    console.log 'leave', node
                    scope.a = undefined

                scope.$watch(
                    () -> return scope.kpiIdx()
                    () -> scope.redraw()
                )
        }
])