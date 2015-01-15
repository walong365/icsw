{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

device_rrd_module = angular.module("icsw.device.rrd", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.bootstrap.datetimepicker", "angular-ladda"])

angular_module_setup([device_rrd_module])

add_rrd_directive(device_rrd_module)

{% endinlinecoffeescript %}

</script>
