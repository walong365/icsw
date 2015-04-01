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

monitoring_basic_module = angular.module("icsw.monitoring.monitoring_basic",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"])

monitoring_basic_module.directive("icswMonitoringBasic", () ->
    return {
        restrict:"EA"
        templateUrl: "icsw.monitoring.basic"
    }
).service('icswMonitoringBasicRestService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url) -> return Restangular.all(url).getList().$object
    data = {
        mon_period         : get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
        user               : get_rest(ICSW_URLS.REST_USER_LIST.slice(1))
        mon_notification   : get_rest(ICSW_URLS.REST_MON_NOTIFICATION_LIST.slice(1))
        mon_service_templ  : get_rest(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1))
        host_check_command : get_rest(ICSW_URLS.REST_HOST_CHECK_COMMAND_LIST.slice(1))
        mon_contact        : get_rest(ICSW_URLS.REST_MON_CONTACT_LIST.slice(1))
        device_group       : get_rest(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1))
        mon_device_templ   : get_rest(ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST.slice(1))
        mon_contactgroup   : get_rest(ICSW_URLS.REST_MON_CONTACTGROUP_LIST.slice(1))
    }
    _rest_data_present = (tables) ->
        ok = true
        for table in tables
            if not data[table].length
                ok = false
        return ok
    data['_rest_data_present'] = _rest_data_present
    return data
]).service('icswMonitoringBasicService', ["ICSW_URLS", "icswMonitoringBasicRestService", (ICSW_URLS, icswMonitoringBasicRestService) ->
    get_use_count =  (obj) ->
            return obj.service_check_period.length   # + obj.mon_device_templ_set.length
    return {
        rest_handle        : icswMonitoringBasicRestService.mon_period
        delete_confirm_str : (obj) ->
            return "Really delete monitoring period '#{obj.name}' ?"
        edit_template      : "mon.period.form"
        new_object         : {
            "alias" : "new period", "mon_range" : "00:00-24:00", "tue_range" : "00:00-24:00", "sun_range" : "00:00-24:00",
            "wed_range" : "00:00-24:00", "thu_range" : "00:00-24:00", "fri_range" : "00:00-24:00", "sat_range" : "00:00-24:00"
        }
        object_created     : (new_obj) -> new_obj.name = ""
        get_use_count      : get_use_count
        delete_ok          : (obj) ->
            return get_use_count(obj) == 0
    }
]).service('icswMonitoringNotificationService', ["ICSW_URLS", "icswMonitoringBasicRestService", (ICSW_URLS, icswMonitoringBasicRestService) ->
    return {
        rest_handle         : icswMonitoringBasicRestService.mon_notification
        edit_template       : "mon.notification.form"
        delete_confirm_str  : (obj) ->
            return "Really delete monitoring notification '#{obj.name}' ?"
        new_object          : {"name" : "", "channel" : "mail", "not_type" : "service"}
        object_created      : (new_obj) -> new_obj.name = ""
    }
]).service('icswMonitoringContactService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    ret = {
           rest_handle: icswMonitoringRestService.mon_contact
           edit_template: "mon.contact.form"
           delete_confirm_str: (obj) ->
               return "Really delete monitoring contact '#{obj.user}' ?"
           new_object: () ->
               return {
               "user": (entry.idx for entry in icswMonitoringRestService.user)[0]
               "snperiod": (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
               "hnperiod": (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
               "snrecovery": true
               "sncritical": true
               "hnrecovery": true
               "hndown": true
               }
           object_created: (new_obj) -> new_obj.user = null
           rest_data_present: () ->
               return icswMonitoringRestService._rest_data_present(["mon_period", "user"])
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
]).service('icswMonitoringServiceTemplateService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    return {
        rest_handle         : icswMonitoringRestService.mon_service_templ
        edit_template       : "mon.service.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete service template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "nsn_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "nsc_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 2
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created    : (new_obj) -> new_obj.name = null
        mon_period        : icswMonitoringRestService.mon_period
        rest_data_present : () ->
            return icswMonitoringRestService._rest_data_present(["mon_period"])
    }
]).service('icswMonitoringDeviceTemplateService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    ret = {
        rest_handle         : icswMonitoringRestService.mon_device_templ
        edit_template       : "mon.device.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete device template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "mon_service_templ" : (entry.idx for entry in icswMonitoringRestService.mon_service_templ)[0]
                "host_check_command" : (entry.idx for entry in icswMonitoringRestService.host_check_command)[0]
                "mon_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "not_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 5
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ndown"     : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created  : (new_obj) -> new_obj.name = null
        rest_data_present : () ->
            return icswMonitoringRestService._rest_data_present(["mon_period", "mon_service_templ", "host_check_command"])
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
]).service('icswMonitoringHostCheckCommandService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    return {
        rest_handle: icswMonitoringRestService.host_check_command
        edit_template: "host.check.command.form"
        delete_confirm_str: (obj) ->
            return "Really delete host check command '#{obj.name}' ?"
        new_object: {"name": ""}
        object_created: (new_obj) -> new_obj.name = null
    }
]).service('icswMonitoringContactgroupService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    ret = {
        rest_handle: icswMonitoringRestService.mon_contactgroup
        edit_template: "mon.contactgroup.form"
        delete_confirm_str: (obj) ->
            "Really delete Contactgroup '#{obj.name}' ?"
        new_object: {"name": ""}
        object_created: (new_obj) -> new_obj.name = null
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
])
