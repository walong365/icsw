# Copyright (C) 2012-2015 init.at
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

monitoring_cluster_module = angular.module("icsw.monitoring.escalation",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"])


monitoring_cluster_module.directive('icswMonitoringEscalation', () ->
    return {
        restrict     : "EA"
        templateUrl  : "icsw.monitoring.escalation"
    }
).service('icswMonitoringEscalationRestService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object
    data = {
        mon_period  : get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
        mon_device_esc_templ    : get_rest(ICSW_URLS.REST_MON_DEVICE_ESC_TEMPL_LIST.slice(1))
        mon_service_esc_templ   : get_rest(ICSW_URLS.REST_MON_SERVICE_ESC_TEMPL_LIST.slice(1))
    }
    _rest_data_present = (tables) ->
        ok = true
        for table in tables
            if not data[table].length
                ok = false
        return ok
    data['_rest_data_present'] = _rest_data_present

    return data
]).service('icswMonitoringServiceEscalationService', ["icswMonitoringEscalationRestService", (icswMonitoringEscalationRestService) ->
    return {
        rest_handle         : icswMonitoringEscalationRestService.mon_service_esc_templ
        edit_template       : "mon.service.esc.templ.form"
        mon_period          : icswMonitoringEscalationRestService.mon_period
        delete_confirm_str  : (obj) ->
            return "Really delete Service escalation template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "first_notification" : 1
                "last_notification" : 2
                "esc_period" : (entry.idx for entry in icswMonitoringEscalationRestService.mon_period)[0]
                "ninterval" : 2
                "nrecovery" : true
                "ncritical" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        rest_data_present  : () ->
            return icswMonitoringEscalationRestService._rest_data_present(["mon_period"])
    }
]).service('icswMonitoringDeviceEscalationService', ["icswMonitoringEscalationRestService", (icswMonitoringEscalationRestService) ->
    return  {
        rest_handle           : icswMonitoringEscalationRestService.mon_device_esc_templ
        edit_template         : "mon.device.esc.templ.form"
        mon_period            : icswMonitoringEscalationRestService.mon_period
        mon_service_esc_templ : icswMonitoringEscalationRestService.mon_service_esc_templ
        delete_confirm_str    : (obj) ->
            return "Really delete Device escalation template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "first_notification" : 1
                "last_notification" : 2
                "esc_period" : (entry.idx for entry in icswMonitoringEscalationRestService.mon_period)[0]
                "mon_service_esc_templ" : (entry.idx for entry in icswMonitoringEscalationRestService.mon_service_esc_templ)[0]
                "ninterval" : 2
                "nrecovery" : true
                "ndown" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        rest_data_present  : () ->
            return icswMonitoringEscalationRestService._rest_data_present(["mon_period", "mon_service_esc_templ"])
    }
])
