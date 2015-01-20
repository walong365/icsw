{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

# customized by BM, based on:

#! angular-dimple - 1.1.4 - 2014-11-10
#*   https://github.com/esripdx/angular-dimple
#*   Licensed ISC 
angular.module("angular-dimple", [
  "angular-dimple.graph"
  "angular-dimple.legend"
  "angular-dimple.x"
  "angular-dimple.y"
  "angular-dimple.r"
  "angular-dimple.line"
  "angular-dimple.bar"
  "angular-dimple.stacked-bar"
  "angular-dimple.area"
  "angular-dimple.stacked-area"
  "angular-dimple.scatter-plot"
  "angular-dimple.ring"
])
.constant("MODULE_VERSION", "0.0.1")
.value "defaults",
  foo: "bar"

angular.module("angular-dimple.area", [])
.directive("area", [->
  restrict: "E"
  replace: true
  require: [
    "area"
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
        area.lineMarkers = true
      else
        values = dimple.getUniqueValues($scope.data, $attrs.field)
        angular.forEach values, (value) ->
          area = chart.addSeries([$attrs.field], dimple.plot.area)
          graphController.filter $attrs
          area.lineMarkers = true
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
angular.module("angular-dimple.bar", []).directive("dimplebar", [->
  restrict: "E"
  replace: true
  require: [
    "dimplebar"
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
      bar = chart.addSeries([$attrs.field], dimple.plot.bar)
      graphController.filter $attrs
      graphController.draw()
      return
    graphController = $controllers[1]
    lineController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addBar()  if newValue is true
      return

    return
])
angular.module("angular-dimple.graph", []).directive("graph", [->
  restrict: "E"
  replace: true
  scope:
    data: "="
    color: "="

  require: ["graph"]
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
angular.module("angular-dimple.legend", []).directive("dimplelegend", [->
  restrict: "E"
  replace: true
  require: [
    "dimplelegend"
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
angular.module("angular-dimple.line", []).directive("line", [->
  restrict: "E"
  replace: true
  require: [
    "line"
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
      line = chart.addSeries([$attrs.field], dimple.plot.line)
      graphController.filter $attrs
      line.lineMarkers = true
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
angular.module("angular-dimple.r", []).directive("r", [->
  restrict: "E"
  replace: true
  require: [
    "r"
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
angular.module("angular-dimple.ring", []).directive("ring", [->
  restrict: "E"
  replace: true
  require: [
    "ring"
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
angular.module("angular-dimple.scatter-plot", []).directive("scatterPlot", [->
  restrict: "E"
  replace: true
  require: [
    "scatterPlot"
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
angular.module("angular-dimple.stacked-area", []).directive("stackedArea", [->
  restrict: "E"
  replace: true
  require: [
    "stackedArea"
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
      area.lineMarkers = false
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
angular.module("angular-dimple.stacked-bar", []).directive("stackedBar", [->
  restrict: "E"
  replace: true
  require: [
    "stackedBar"
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
        bar = chart.addSeries([$attrs.series], dimple.plot.bar)
      else
        bar = chart.addSeries([$attrs.field], dimple.plot.bar)
      graphController.filter $attrs
      graphController.draw()
      return
    graphController = $controllers[1]
    lineController = $controllers[0]
    chart = graphController.getChart()
    $scope.$watch "dataReady", (newValue, oldValue) ->
      addBar()  if newValue is true
      return

    return
])
angular.module("angular-dimple.x", []).directive("x", [->
  restrict: "E"
  replace: true
  require: [
    "x"
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
angular.module("angular-dimple.y", []).directive("y", [->
  restrict: "E"
  replace: true
  require: [
    "y"
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

{% endinlinecoffeescript %}

</script>
