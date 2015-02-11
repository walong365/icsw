
# customized by BM, based on:

#! angular-dimple-init - 1.1.4 - 2014-11-10
#*   https://github.com/esripdx/angular-dimple
#*   Licensed ISC 
angular.module("icsw.tools.angular-dimple-init", [
  "icsw.tools.angular-dimple-init.graphDimple"
  "icsw.tools.angular-dimple-init.legendDimple"
  "icsw.tools.angular-dimple-init.x"
  "icsw.tools.angular-dimple-init.y"
  "icsw.tools.angular-dimple-init.r"
  "icsw.tools.angular-dimple-init.lineDimple"
  "icsw.tools.angular-dimple-init.barDimple"
  "icsw.tools.angular-dimple-init.stacked-bar"
  "icsw.tools.angular-dimple-init.areaDimple"
  "icsw.tools.angular-dimple-init.stacked-area"
  "icsw.tools.angular-dimple-init.scatter-plot"
  "icsw.tools.angular-dimple-init.ring"
])
.constant("MODULE_VERSION", "0.0.1")
.value "defaults",
  foo: "bar"

angular.module("icsw.tools.angular-dimple-init.areaDimple", [])
.directive("icswToolsDimpleArea", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleArea"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addArea = ->
      if $attrs.value
        area = chart.addSeries([$attrs.field], dimple.plot.area)
        graphController.filter $attrs
        area.lineDimpleMarkers = true
      else
        values = dimple.getUniqueValues($scope.data, $attrs.field)
        angular.forEach values, (value) ->
          area = chart.addSeries([$attrs.field], dimple.plot.area)
          graphController.filter $attrs
          area.lineDimpleMarkers = true
          return

      graphController.draw()
      return
    graphController = $controllers[1]
    areaController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addArea()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.barDimple", []).directive("icswToolsDimpleBar", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleBar"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addBar = ->
      filteredData = undefined
      barDimple = chart.addSeries([$attrs.field], dimple.plot.barDimple)
      graphController.filter $attrs
      graphController.draw()
      return
    graphController = $controllers[1]
    lineDimpleController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addBar()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.graphDimple", []).directive("icswToolsDimpleGraph", [->
  restrict: "E"
  replace: true
  scope:
    data: "="
    color: "="

  require: ["icswToolsDimpleGraph"]
  transclude: true
  link: (scope, element, attrs, controllers, transclude) ->
    graphController = controllers[0]
    graphController._createChart()
    scope.dataReady = false
    scope.filters = []
    chart = graphController.getChart()
    transition = undefined
    if attrs.transition
      transition = attrs.transition
    else
      transition = 750
    scope.$watch "data", (newValue, oldValue) ->
      if newValue
        scope.dataReady = true
        graphController.setData()
        chart.draw transition
      return

    transclude scope, (clone) ->
      element.append clone
      return

    return

  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
      chart = undefined
      id = (Math.random() * 1e9).toString(36).replace(".", "_")
      $element.append "<div class=\"dimple-graph\" id=\"dng-" + id + "\"></div>"
      @_createChart = ->
        
        # create an svg element
        width = (if $attrs.width then $attrs.width else "100%")
        height = (if $attrs.height then $attrs.height else "100%")
        svg = dimple.newSvg("#dng-" + id + "", width, height)
        data = $scope.data
        
        # create the dimple chart using the d3 selection of our <svg> element
        chart = new dimple.chart(svg, data)
        if $attrs.margin
          chart.setMargins $attrs.margin
        else
          chart.setMargins 60, 60, 20, 40
        
        # auto style
        autoStyle = (if $attrs.autoStyle is "false" then true else false)
        chart.noFormats = autoStyle
        
        # Apply palette styles
        if $attrs.color
          palette = $scope.color
          i = 0

          while i < palette.length
            chart.assignColor palette[i].name, palette[i].fill, palette[i].stroke, palette[i].opacity
            i++
        return

      @getChart = ->
        chart

      @setData = ->
        chart.data = $scope.data
        return

      @draw = ->
        chart.draw()
        return

      @getID = ->
        id

      @filter = (attrs) ->
        $scope.filters.push attrs.value  if attrs.value isnt `undefined`
        chart.data = dimple.filterData($scope.data, attrs.field, $scope.filters)  if $scope.filters.length
        if attrs.filter isnt `undefined`
          console.log "i see a filter"
          thisFilter = attrs.filter.split(":")
          field = thisFilter[0]
          value = [thisFilter[1]]
          chart.data = dimple.filterData($scope.data, field, value)
        return
  ]
])
angular.module("icsw.tools.angular-dimple-init.legendDimple", []).directive("icswToolsDimpleLegend", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleLegend"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addLegend = ->
      left = (if $attrs.left then $attrs.left else "10%")
      top = (if $attrs.top then $attrs.top else "4%")
      height = (if $attrs.height then $attrs.height else "10%")
      width = (if $attrs.width then $attrs.width else "90%")
      position = (if $attrs.position then $attrs.position else "left")
      chart.addLegend left, top, width, height, position
      return
    graphController = $controllers[1]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addLegend()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.lineDimple", []).directive("icswToolsDimpleLine", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleLine"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addLine = ->
      filteredData = undefined
      lineDimple = chart.addSeries([$attrs.field], dimple.plot.lineDimple)
      graphController.filter $attrs
      lineDimple.lineDimpleMarkers = true
      graphController.draw()
      return
    graphController = $controllers[1]
    chart = graphController.getChart()
    drawn = false
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addLine()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.r", []).directive("icswToolsDimpleR", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleR"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addAxis = ->
      r = chart.addMeasureAxis("p", $attrs.field)
      if $attrs.title and $attrs.title isnt "null"
        r.title = $attrs.title
      else r.title = null  if $attrs.title is "null"
      return
    graphController = $controllers[1]
    chart = graphController.getChart()
    $scope.$watch "data", (newValue, oldValue) ->
      addAxis()  if newValue
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.ring", []).directive("icswToolsDimpleRing", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleRing"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    setData = (data, series) ->
      series.data = data
      return
    addRing = ->
      thickness = undefined
      ring = chart.addSeries([$attrs.field], dimple.plot.pie)
      if $attrs.thickness and not $attrs.diameter
        thickness = (100 - $attrs.thickness) + "%"
        ring.innerRadius = thickness
      else if $attrs.thickness and $attrs.diameter
        thickness = ($attrs.diameter - $attrs.thickness) + "%"
        ring.innerRadius = thickness
      else
        ring.innerRadius = "50%"
      ring.outerRadius = ($attrs.diameter) + "%"  if $attrs.diameter
      graphController.filter $attrs
      graphController.draw()
      return
    graphController = $controllers[1]
    areaController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "data", (newValue, oldValue) ->
      addRing()  if newValue
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.scatter-plot", []).directive("icswToolsDimpleScatterPlot", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleScatterPlot"
    "^graph"
  ]
  controller: [->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addScatterPlot = ->
      array = []
      array.push $attrs.series  if $attrs.series
      array.push $attrs.field
      array.push $attrs.label  if $attrs.label or $attrs.label is ""
      scatterPlot = chart.addSeries(array, dimple.plot.bubble)
      scatterPlot.aggregate = dimple.aggregateMethod.avg
      graphController.filter $attrs
      graphController.draw()
      return
    graphController = $controllers[1]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addScatterPlot()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.stacked-area", []).directive("icswToolsDimpleStackedArea", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleStackedArea"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addArea = ->
      if $attrs.series
        area = chart.addSeries([$attrs.series], dimple.plot.area)
      else
        area = chart.addSeries([$attrs.field], dimple.plot.area)
      
      area.addOrderRule (valA, valB) ->
        if valA.order < valB.order
          -1
        else
          1

      graphController.filter $attrs
      area.lineDimpleMarkers = false
      graphController.draw()
      return
    graphController = $controllers[1]
    areaController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addArea()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.stacked-bar", []).directive("icswToolsDimpleStackedBar", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleStackedBar"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addBar = ->
      if $attrs.series
        barDimple = chart.addSeries([$attrs.series], dimple.plot.barDimple)
      else
        barDimple = chart.addSeries([$attrs.field], dimple.plot.barDimple)
      graphController.filter $attrs
      graphController.draw()
      return
    graphController = $controllers[1]
    lineDimpleController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addBar()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.x", []).directive("icswToolsDimpleX", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleX"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addAxis = ->
      if $attrs.groupBy
        if $attrs.type is "Measure"
          x = chart.addMeasureAxis("x", [
            $attrs.groupBy
            $attrs.field
          ])
        else if $attrs.type is "Percent"
          x = chart.addPctAxis("x", $attrs.field)
        else if $attrs.type is "Time"
          x = chart.addTimeAxis("x", $attrs.field)
          x.tickFormat = $attrs.format  if $attrs.format
        else
          x = chart.addCategoryAxis("x", [
            $attrs.groupBy
            $attrs.field
          ])
        x.addGroupOrderRule $attrs.orderBy  if $attrs.orderBy
      else
        if $attrs.type is "Measure"
          x = chart.addMeasureAxis("x", $attrs.field)
        else if $attrs.type is "Percent"
          x = chart.addPctAxis("x", $attrs.field)
        else if $attrs.type is "Time"
          x = chart.addTimeAxis("x", $attrs.field)
          x.tickFormat = $attrs.format  if $attrs.format
        else
          x = chart.addCategoryAxis("x", $attrs.field)
        x.addOrderRule $attrs.orderBy  if $attrs.orderBy
      if $attrs.title and $attrs.title isnt "null"
        x.title = $attrs.title
      else x.title = null  if $attrs.title is "null"
      return
    graphController = $controllers[1]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addAxis()  if newValue is true
      return

    return
])
angular.module("icsw.tools.angular-dimple-init.y", []).directive("icswToolsDimpleY", [->
  restrict: "E"
  replace: true
  require: [
    "icswToolsDimpleY"
    "^graph"
  ]
  controller: [
    "$scope"
    "$element"
    "$attrs"
    ($scope, $element, $attrs) ->
  ]
  link: ($scope, $element, $attrs, $controllers) ->
    addAxis = ->
      if $attrs.groupBy
        if $attrs.type is "Category"
          y = chart.addCategoryAxis("y", $attrs.field)
        else if $attrs.type is "Percent"
          y = chart.addPctAxis("y", $attrs.field)
        else if $attrs.type is "Time"
          y = chart.addTimeAxis("x", $attrs.field)
          y.tickFormat = $attrs.format  if $attrs.format
        else
          y = chart.addMeasureAxis("y", $attrs.field)
        y.addGroupOrderRule $attrs.orderBy  if $attrs.orderBy
      else
        if $attrs.type is "Category"
          y = chart.addCategoryAxis("y", $attrs.field)
        else if $attrs.type is "Percent"
          y = chart.addPctAxis("y", $attrs.field)
        else if $attrs.type is "Time"
          y = chart.addTimeAxis("x", $attrs.field)
          y.tickFormat = $attrs.format  if $attrs.format
        else
          y = chart.addMeasureAxis("y", $attrs.field)
        y.addOrderRule $attrs.orderBy  if $attrs.orderBy
      if $attrs.title and $attrs.title isnt "null"
        y.title = $attrs.title
      else y.title = null  if $attrs.title is "null"
      return
    graphController = $controllers[1]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addAxis()  if newValue is true
      return

    return
])

