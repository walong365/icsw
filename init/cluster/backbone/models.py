#!/usr/bin/python-init

from django.db import models
from django.contrib.auth.models import User, Group, Permission
import datetime
from django.db.models import Q

def only_wf_perms(in_list):
    return [entry.split("_", 1)[1] for entry in in_list if entry.startswith("backbone.wf_")]

class apc_device(models.Model):
    idx = models.AutoField(db_column="idx", primary_key=True)
    device = models.ForeignKey("device")
    power_on_delay = models.IntegerField(null=True, blank=True)
    reboot_delay = models.IntegerField(null=True, blank=True)
    apc_type = models.CharField(max_length=765, blank=True)
    version_info = models.TextField(blank=True)
    num_outlets = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'apc_device'

class app_config_con(models.Model):
    idx = models.AutoField(db_column="app_config_con_idx", primary_key=True)
    application = models.ForeignKey("application")
    config = models.ForeignKey("new_config")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'app_config_con'

class app_devgroup_con(models.Model):
    idx = models.AutoField(db_column="app_devgroup_con_idx", primary_key=True)
    application = models.ForeignKey("application")
    device_group = models.ForeignKey("device_group")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'app_devgroup_con'

class app_instpack_con(models.Model):
    idx = models.AutoField(db_column="app_instpack_con_idx", primary_key=True)
    application = models.ForeignKey("application")
    inst_package = models.ForeignKey("inst_package")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'app_instpack_con'

class application(models.Model):
    idx = models.AutoField(db_column="application_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    description = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'application'

class architecture(models.Model):
    idx = models.AutoField(db_column="architecture_idx", primary_key=True)
    architecture = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'architecture'

class ccl_dgroup_con(models.Model):
    idx = models.AutoField(db_column="ccl_dgroup_con_idx", primary_key=True)
    ccl_event = models.ForeignKey("ccl_event")
    device_group = models.ForeignKey("device_group")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_dgroup_con'

class ccl_dloc_con(models.Model):
    idx = models.AutoField(db_column="ccl_dloc_con_idx", primary_key=True)
    ccl_event = models.ForeignKey("ccl_event")
    device_location = models.ForeignKey("device_location")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_dloc_con'

class ccl_event(models.Model):
    idx = models.AutoField(db_column="ccl_event_idx", primary_key=True)
    device = models.ForeignKey("device")
    rrd_data = models.ForeignKey("rrd_data")
    device_class = models.ForeignKey("device_class")
    threshold = models.FloatField(null=True, blank=True)
    threshold_class = models.IntegerField()
    cluster_event = models.ForeignKey("cluster_event")
    hysteresis = models.FloatField(null=True, blank=True)
    disabled = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_event'

class ccl_event_log(models.Model):
    idx = models.AutoField(db_column="ccl_event_log_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    ccl_event = models.ForeignKey("ccl_event")
    cluster_event = models.ForeignKey("cluster_event")
    passive = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_event_log'

class ccl_user_con(models.Model):
    idx = models.AutoField(db_column="ccl_user_con_idx", primary_key=True)
    ccl_event = models.ForeignKey("ccl_event")
    user = models.ForeignKey("user")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ccl_user_con'

class cluster_event(models.Model):
    idx = models.AutoField(db_column="cluster_event_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=96)
    description = models.CharField(max_length=384, blank=True)
    color = models.CharField(max_length=18, blank=True)
    command = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'cluster_event'


class config_blob(models.Model):
    idx = models.AutoField(db_column="config_blob_idx", primary_key=True)
    name = models.CharField(max_length=192)
    descr = models.CharField(max_length=765)
    config = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'config_blob'

class config_bool(models.Model):
    idx = models.AutoField(db_column="config_bool_idx", primary_key=True)
    name = models.CharField(max_length=192)
    descr = models.CharField(max_length=765)
    config = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'config_bool'

class config_int(models.Model):
    idx = models.AutoField(db_column="config_int_idx", primary_key=True)
    name = models.CharField(max_length=192)
    descr = models.CharField(max_length=765)
    config = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'config_int'

class config_script(models.Model):
    idx = models.AutoField(db_column="config_script_idx", primary_key=True)
    name = models.CharField(max_length=192)
    descr = models.CharField(max_length=765)
    enabled = models.IntegerField(null=True, blank=True)
    priority = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    value = models.TextField(blank=True)
    error_text = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'config_script'

class config_str(models.Model):
    idx = models.AutoField(db_column="config_str_idx", primary_key=True)
    name = models.CharField(max_length=192)
    descr = models.CharField(max_length=765)
    config = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'config_str'

class config_type(models.Model):
    # deprecated, do not use
    idx = models.AutoField(db_column="config_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    identifier = models.CharField(unique=True, max_length=6)
    description = models.CharField(max_length=384)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'config_type'

class device(models.Model):
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    # FIXME
    device_group = models.ForeignKey("device_group", related_name="device_group")
    device_type = models.ForeignKey("device_type")
    axnumber = models.CharField(max_length=192, blank=True)
    alias = models.CharField(max_length=384, blank=True)
    comment = models.CharField(max_length=384, blank=True)
    snmp_class = models.ForeignKey("snmp_class", null=True)
    switch = models.ForeignKey("device", null=True, related_name="switch_device")
    switchport = models.IntegerField(null=True, blank=True)
    ng_device_templ = models.ForeignKey("ng_device_templ", null=True)
    ng_ext_host = models.IntegerField(null=True, blank=True)
    device_location = models.ForeignKey("device_location", null=True)
    device_class = models.ForeignKey("device_class")
    rrd_class = models.ForeignKey("rrd_class", null=True)
    save_rrd_vectors = models.BooleanField()
    etherboot_valid = models.BooleanField()
    kernel_append = models.CharField(max_length=384, blank=True)
    newkernel = models.CharField(max_length=192, blank=True)
    new_kernel = models.ForeignKey("kernel", null=True, related_name="new_kernel")
    actkernel = models.CharField(max_length=192, blank=True)
    act_kernel = models.ForeignKey("kernel", null=True, related_name="act_kernel")
    act_kernel_build = models.IntegerField(null=True, blank=True)
    kernelversion = models.CharField(max_length=192, blank=True)
    stage1_flavour = models.CharField(max_length=48, blank=True)
    dom0_memory = models.IntegerField(null=True, blank=True)
    xen_guest = models.BooleanField()
    newimage = models.CharField(max_length=765, blank=True)
    new_image = models.ForeignKey("image", null=True, related_name="new_image")
    actimage = models.CharField(max_length=765, blank=True)
    act_image = models.ForeignKey("image", null=True, related_name="act_image")
    imageversion = models.CharField(max_length=192, blank=True)
    partition_table = models.ForeignKey("partition_table", null=True, related_name="new_partition_table")
    act_partition_table = models.ForeignKey("partition_table", null=True, related_name="act_partition_table")
    partdev = models.CharField(max_length=192, blank=True)
    fixed_partdev = models.IntegerField(null=True, blank=True)
    bz2_capable = models.IntegerField(null=True, blank=True)
    newstate = models.ForeignKey("status", null=True)
    rsync = models.BooleanField()
    rsync_compressed = models.BooleanField()
    prod_link = models.IntegerField(null=True, blank=True)
    recvstate = models.TextField(blank=True, null=True)
    reqstate = models.TextField(blank=True, null=True)
    bootnetdevice = models.ForeignKey("device", null=True, related_name="boot_net_device")
    bootserver = models.ForeignKey("device", null=True, related_name="boot_server")
    reachable_via_bootserver = models.IntegerField(null=True, blank=True)
    dhcp_mac = models.IntegerField(null=True, blank=True)
    dhcp_write = models.IntegerField(null=True, blank=True)
    dhcp_written = models.IntegerField(null=True, blank=True)
    dhcp_error = models.CharField(max_length=765, blank=True)
    propagation_level = models.IntegerField(null=True, blank=True)
    last_install = models.CharField(max_length=192, blank=True)
    last_boot = models.CharField(max_length=192, blank=True)
    last_kernel = models.CharField(max_length=192, blank=True)
    root_passwd = models.CharField(max_length=192, blank=True)
    device_mode = models.BooleanField()
    relay_device = models.ForeignKey("device", null=True)
    nagios_checks = models.BooleanField()
    show_in_bootcontrol = models.BooleanField()
    cpu_info = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return u"%s%s" % (self.name,
                          " (%s)" % (self.comment) if self.comment else "")
    class Meta:
        db_table = u'device'

class device_class(models.Model):
    idx = models.AutoField(db_column="device_class_idx", primary_key=True)
    classname = models.CharField(max_length=192, blank=False, unique=True)
    priority = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_class'

class device_config(models.Model):
    idx = models.AutoField(db_column="device_config_idx", primary_key=True)
    device = models.ForeignKey("device")
    new_config = models.ForeignKey("new_config")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_config'

class device_connection(models.Model):
    idx = models.AutoField(db_column="device_connection_idx", primary_key=True)
    parent = models.ForeignKey("device", related_name="parent_device")
    child = models.ForeignKey("device", related_name="child_device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_connection'

class device_selection(models.Model):
    idx = models.AutoField(db_column="device_selection_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    user = models.ForeignKey("user", null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_selection'

class device_device_selection(models.Model):
    idx = models.AutoField(db_column="device_device_selection_idx", primary_key=True)
    device_selection = models.ForeignKey("device_selection")
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_device_selection'

class device_group(models.Model):
    idx = models.AutoField(db_column="device_group_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=384)
    #device = models.ForeignKey("device", null=True, blank=True, related_name="group_device")
    # must be an IntegerField, otherwise we have a cycle reference
    #device = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", db_column="device", null=True, blank=True, related_name="group_device")
    # flag
    cluster_device_group = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_group'
    def __unicode__(self):
        return u"%s%s%s" % (
            self.name,
            " (%s)" % (self.description) if self.description else "",
            "[*]" if self.cluster_device_group else ""
        )

class device_location(models.Model):
    idx = models.AutoField(db_column="device_location_idx", primary_key=True)
    location = models.CharField(max_length=192, blank=False, unique=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_location'

class device_relationship(models.Model):
    idx = models.AutoField(db_column="device_relationship_idx", primary_key=True)
    host_device = models.ForeignKey("device", related_name="host_device")
    domain_device = models.ForeignKey("device", related_name="domain_device")
    relationship = models.CharField(max_length=9, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_relationship'

class device_rsync_config(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    new_config = models.ForeignKey("new_config")
    device = models.ForeignKey("device")
    last_rsync_time = models.DateTimeField(null=True, blank=True)
    status = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_rsync_config'

class device_shape(models.Model):
    idx = models.AutoField(db_column="device_shape_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=192)
    x_dim = models.FloatField(null=True, blank=True)
    y_dim = models.FloatField(null=True, blank=True)
    z_dim = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_shape'

class device_type(models.Model):
    idx = models.AutoField(db_column="device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=24)
    description = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return self.description
    class Meta:
        db_table = u'device_type'

class device_variable(models.Model):
    idx = models.AutoField(db_column="device_variable_idx", primary_key=True)
    device = models.ForeignKey("device")
    is_public = models.BooleanField()
    name = models.CharField(max_length=765)
    description = models.CharField(max_length=765, blank=True)
    var_type = models.CharField(max_length=3)
    val_str = models.TextField(blank=True, null=True)
    val_int = models.IntegerField(null=True, blank=True)
    val_blob = models.TextField(blank=True, null=True)
    val_date = models.DateTimeField(null=True, blank=True)
    val_time = models.TextField(blank=True, null=True) # This field type is a guess.
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'device_variable'

class devicelog(models.Model):
    idx = models.AutoField(db_column="devicelog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    log_status = models.ForeignKey("log_status", null=True)
    text = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'devicelog'

class distribution(models.Model):
    idx = models.AutoField(db_column="distribution_idx", primary_key=True)
    distribution = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'distribution'

class dmi_entry(models.Model):
    idx = models.AutoField(db_column="dmi_entry_idx", primary_key=True)
    device = models.ForeignKey("device")
    dmi_type = models.IntegerField()
    handle = models.IntegerField()
    dmi_length = models.IntegerField()
    info = models.CharField(max_length=765)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'dmi_entry'

class dmi_ext_key(models.Model):
    idx = models.AutoField(db_column="dmi_ext_key_idx", primary_key=True)
    dmi_key = models.ForeignKey("dmi_key")
    ext_value_string = models.CharField(max_length=765)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'dmi_ext_key'

class dmi_key(models.Model):
    idx = models.AutoField(db_column="dmi_key_idx", primary_key=True)
    dmi_entry = models.ForeignKey("dmi_entry")
    key_string = models.CharField(max_length=765)
    value_string = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'dmi_key'

class extended_log(models.Model):
    idx = models.AutoField(db_column="extended_log_idx", primary_key=True)
    devicelog = models.ForeignKey("devicelog", null=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    users = models.CharField(max_length=765, blank=True)
    subject = models.CharField(max_length=765, blank=True)
    description = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'extended_log'

class genstuff(models.Model):
    idx = models.AutoField(db_column="genstuff_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=384, blank=True)
    value = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'genstuff'

class hopcount(models.Model):
    idx = models.AutoField(db_column="hopcount_idx", primary_key=True)
    s_netdevice = models.ForeignKey("netdevice", related_name="hopcount_s_netdevice")
    d_netdevice = models.ForeignKey("netdevice", related_name="hopcount_d_netdevice")
    value = models.IntegerField(null=True, blank=True)
    trace = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'hopcount'

class hw_entry(models.Model):
    idx = models.AutoField(db_column="hw_entry_idx", primary_key=True)
    device = models.ForeignKey("device")
    hw_entry_type = models.ForeignKey("hw_entry_type")
    iarg0 = models.IntegerField(null=True, blank=True)
    iarg1 = models.IntegerField(null=True, blank=True)
    sarg0 = models.CharField(max_length=765, blank=True)
    sarg1 = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'hw_entry'

class hw_entry_type(models.Model):
    idx = models.AutoField(db_column="hw_entry_type_idx", primary_key=True)
    identifier = models.CharField(max_length=24)
    description = models.CharField(max_length=765)
    iarg0_descr = models.CharField(max_length=765, blank=True)
    iarg1_descr = models.CharField(max_length=765, blank=True)
    sarg0_descr = models.CharField(max_length=765, blank=True)
    sarg1_descr = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'hw_entry_type'

class ibc_connection(models.Model):
    idx = models.AutoField(db_column="ibc_connection_idx", primary_key=True)
    device = models.ForeignKey("device")
    slave_device = models.ForeignKey("device", null=True, related_name="slave_device")
    slave_info = models.CharField(max_length=192, blank=True)
    blade = models.IntegerField()
    state = models.CharField(max_length=96, blank=True)
    blade_exists = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ibc_connection'

class ibc_device(models.Model):
    idx = models.AutoField(db_column="ibc_device_idx", primary_key=True)
    device = models.ForeignKey("device")
    blade_type = models.CharField(max_length=192, blank=True)
    num_blades = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ibc_device'

class image(models.Model):
    idx = models.AutoField(db_column="image_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=True)
    source = models.CharField(max_length=384, blank=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    builds = models.IntegerField(null=True, blank=True)
    build_machine = models.CharField(max_length=192, blank=True)
    # not a foreign key to break cyclic dependencies
    #device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField()
    size_string = models.TextField(blank=True)
    sys_vendor = models.CharField(max_length=192, blank=True)
    sys_version = models.CharField(max_length=192, blank=True)
    sys_release = models.CharField(max_length=192, blank=True)
    bitcount = models.IntegerField(null=True, blank=True)
    architecture = models.ForeignKey("architecture")
    full_build = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'image'

class image_excl(models.Model):
    idx = models.AutoField(db_column="image_excl_idx", primary_key=True)
    image = models.ForeignKey("image")
    exclude_path = models.TextField()
    valid_for_install = models.BooleanField()
    valid_for_upgrade = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'image_excl'

class inst_package(models.Model):
    idx = models.AutoField(db_column="inst_package_idx", primary_key=True)
    package = models.ForeignKey("package")
    location = models.TextField()
    native = models.BooleanField()
    last_build = models.IntegerField(null=True, blank=True)
    present_on_disk = models.BooleanField()
    package_set = models.ForeignKey("package_set", null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'inst_package'

class instp_device(models.Model):
    idx = models.AutoField(db_column="instp_device_idx", primary_key=True)
    inst_package = models.ForeignKey("inst_package")
    device = models.ForeignKey("device")
    install = models.BooleanField()
    upgrade = models.BooleanField()
    del_field = models.BooleanField(db_column='del') # Field renamed because it was a Python reserved word. Field name made lowercase.
    nodeps = models.BooleanField()
    forceflag = models.BooleanField()
    status = models.TextField()
    install_time = models.DateTimeField(null=True, blank=True)
    error_line_num = models.IntegerField(null=True, blank=True)
    error_lines = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'instp_device'

class kernel(models.Model):
    idx = models.AutoField(db_column="kernel_idx", primary_key=True)
    name = models.CharField(max_length=384)
    kernel_version = models.CharField(max_length=384)
    major = models.CharField(max_length=192, blank=True)
    minor = models.CharField(max_length=192, blank=True)
    patchlevel = models.CharField(max_length=192, blank=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    builds = models.IntegerField(null=True, blank=True)
    build_machine = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    #master_server = models.ForeignKey("device", null=True, related_name="master_server")
    master_server = models.IntegerField(null=True)
    master_role = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    #device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField()
    config_name = models.CharField(max_length=192, blank=True)
    cpu_arch = models.CharField(max_length=192, blank=True)
    sub_cpu_arch = models.CharField(max_length=192, blank=True)
    target_dir = models.CharField(max_length=765, blank=True)
    comment = models.TextField(blank=True)
    enabled = models.BooleanField()
    initrd_version = models.IntegerField(null=True, blank=True)
    initrd_built = models.DateTimeField(null=True, blank=True)
    module_list = models.TextField(blank=True)
    target_module_list = models.TextField(blank=True)
    xen_host_kernel = models.BooleanField()
    xen_guest_kernel = models.BooleanField()
    bitcount = models.IntegerField(null=True, blank=True)
    stage1_lo_present = models.BooleanField()
    stage1_cpio_present = models.BooleanField()
    stage1_cramfs_present = models.BooleanField()
    stage2_present = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel'

class kernel_build(models.Model):
    idx = models.AutoField(db_column="kernel_build_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    build_machine = models.CharField(max_length=192, blank=True)
    device = models.ForeignKey("device", null=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel_build'

class kernel_local_info(models.Model):
    idx = models.AutoField(db_column="kernel_local_info_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    info_blob = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel_local_info'

class kernel_log(models.Model):
    idx = models.AutoField(db_column="kernel_log_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    log_str = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'kernel_log'

class log_source(models.Model):
    idx = models.AutoField(db_column="log_source_idx", primary_key=True)
    identifier = models.CharField(max_length=192)
    name = models.CharField(max_length=192)
    device = models.ForeignKey("device", null=True)
    description = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'log_source'

class log_status(models.Model):
    idx = models.AutoField(db_column="log_status_idx", primary_key=True)
    identifier = models.CharField(max_length=12, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'log_status'

class lvm_lv(models.Model):
    idx = models.AutoField(db_column="lvm_lv_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    lvm_vg = models.ForeignKey("lvm_vg")
    size = models.BigIntegerField(null=True, blank=True)
    mountpoint = models.CharField(max_length=192)
    mount_options = models.CharField(max_length=384, blank=True)
    fs_freq = models.IntegerField(null=True, blank=True)
    fs_passno = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192)
    partition_fs = models.ForeignKey("partition_fs")
    warn_threshold = models.IntegerField(null=True, blank=True)
    crit_threshold = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'lvm_lv'

class lvm_vg(models.Model):
    idx = models.AutoField(db_column="lvm_vg_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    name = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'lvm_vg'

class mac_ignore(models.Model):
    idx = models.AutoField(db_column="mac_ignore_idx", primary_key=True)
    macadr = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'mac_ignore'

class macbootlog(models.Model):
    idx = models.AutoField(db_column="macbootlog_idx", primary_key=True)
    device = models.ForeignKey("device")
    type = models.CharField(max_length=96)
    ip = models.CharField(max_length=96)
    macadr = models.CharField(max_length=192)
    log_source = models.ForeignKey("log_source", null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'macbootlog'

class ms_outlet(models.Model):
    idx = models.AutoField(db_column="msoutlet_idx", primary_key=True)
    device = models.ForeignKey("device")
    slave_device = models.ForeignKey("device", null=True, related_name="ms_slave_device")
    slave_info = models.CharField(max_length=192, blank=True)
    outlet = models.IntegerField()
    state = models.CharField(max_length=96, blank=True)
    t_power_on_delay = models.IntegerField(null=True, blank=True)
    t_power_off_delay = models.IntegerField(null=True, blank=True)
    t_reboot_delay = models.IntegerField(null=True, blank=True)
    power_on_delay = models.IntegerField(null=True, blank=True)
    power_off_delay = models.IntegerField(null=True, blank=True)
    reboot_delay = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'msoutlet'

class netbotz_picture(models.Model):
    idx = models.AutoField(db_column="netbotz_picture_idx", primary_key=True)
    device = models.ForeignKey("device")
    year = models.IntegerField()
    month = models.IntegerField()
    day = models.IntegerField()
    hour = models.IntegerField()
    minute = models.IntegerField()
    second = models.IntegerField()
    path = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'netbotz_picture'

class netdevice(models.Model):
    idx = models.AutoField(db_column="netdevice_idx", primary_key=True)
    device = models.ForeignKey("device")
    devname = models.CharField(max_length=36)
    macadr = models.CharField(max_length=177, blank=True)
    driver_options = models.CharField(max_length=672, blank=True)
    speed = models.IntegerField(null=True, blank=True)
    netdevice_speed = models.ForeignKey("netdevice_speed")
    driver = models.CharField(max_length=384, blank=True)
    routing = models.BooleanField()
    penalty = models.IntegerField(null=True, blank=True)
    dhcp_device = models.IntegerField(null=True, blank=True)
    ethtool_options = models.IntegerField(null=True, blank=True)
    fake_macadr = models.CharField(max_length=177, blank=True)
    network_device_type = models.ForeignKey("network_device_type")
    description = models.CharField(max_length=765, blank=True)
    is_bridge = models.BooleanField()
    bridge_name = models.CharField(max_length=765, blank=True)
    vlan_id = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'netdevice'

class netdevice_speed(models.Model):
    idx = models.AutoField(db_column="netdevice_speed_idx", primary_key=True)
    speed_bps = models.BigIntegerField(null=True, blank=True)
    check_via_ethtool = models.BooleanField()
    full_duplex = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'netdevice_speed'

class net_ip(models.Model):
    idx = models.AutoField(db_column="netip_idx", primary_key=True)
    ip = models.CharField(max_length=48)
    network = models.ForeignKey("network")
    netdevice = models.ForeignKey("netdevice")
    penalty = models.IntegerField(null=True, blank=True)
    alias = models.CharField(max_length=765, blank=True)
    alias_excl = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'netip'

class network(models.Model):
    idx = models.AutoField(db_column="network_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=255, blank=False)
    network_type = models.ForeignKey("network_type")
    master_network = models.ForeignKey("network", null=True, related_name="rel_master_network", blank=True)
    short_names = models.BooleanField()
    name = models.CharField(max_length=192, blank=False)
    penalty = models.PositiveIntegerField(default=1)
    postfix = models.CharField(max_length=12, blank=True)
    info = models.CharField(max_length=255, blank=True)
    network = models.IPAddressField()
    netmask = models.IPAddressField()
    broadcast = models.IPAddressField()
    gateway = models.IPAddressField()
    gw_pri = models.IntegerField(null=True, blank=True, default=1)
    write_bind_config = models.BooleanField()
    write_other_network_config = models.BooleanField()
    start_range = models.IPAddressField(default="0.0.0.0")
    end_range = models.IPAddressField(default="0.0.0.0")
    date = models.DateTimeField(auto_now_add=True)
    network_device_type = models.ManyToManyField("network_device_type")
    class Meta:
        db_table = u'network'
    def __unicode__(self):
        return u"%s" % (self.name)

class network_device_type(models.Model):
    idx = models.AutoField(db_column="network_device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=48, blank=False)
    description = models.CharField(max_length=192)
    mac_bytes = models.PositiveIntegerField(default=6)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'network_device_type'
    def __unicode__(self):
        return u"%s (%s [%d])" % (
            self.identifier,
            self.description,
            self.mac_bytes)
    
class network_network_device_type(models.Model):
    idx = models.AutoField(db_column="network_network_device_type_idx", primary_key=True)
    network = models.ForeignKey("network")
    network_device_type = models.ForeignKey("network_device_type")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'network_network_device_type'

class network_type(models.Model):
    idx = models.AutoField(db_column="network_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=3,
                                  choices=(("b", "boot"),
                                           ("p", "prod"),
                                           ("s", "slave"),
                                           ("o", "other"),
                                           ("l", "local")))
    description = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'network_type'
    def __unicode__(self):
        return u"%s (%s)" % (self.description,
                             self.identifier)

class new_config(models.Model):
    idx = models.AutoField(db_column="new_config_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=765)
    priority = models.IntegerField(null=True, blank=True)
    new_config_type = models.ForeignKey("new_config_type")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'new_config'

class new_config_type(models.Model):
    idx = models.AutoField(db_column="new_config_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'new_config_type'

class new_rrd_data(models.Model):
    idx = models.AutoField(db_column="new_rrd_data_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    descr = models.CharField(max_length=765, blank=True)
    descr1 = models.CharField(max_length=192, blank=True)
    descr2 = models.CharField(max_length=192, blank=True)
    descr3 = models.CharField(max_length=192, blank=True)
    descr4 = models.CharField(max_length=192, blank=True)
    unit = models.CharField(max_length=96, blank=True)
    info = models.CharField(max_length=255, blank=True)
    from_snmp = models.IntegerField(null=True, blank=True)
    base = models.IntegerField(null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)
    var_type = models.CharField(max_length=3, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'new_rrd_data'

class ng_ccgroup(models.Model):
    idx = models.AutoField(db_column="ng_ccgroup_idx", primary_key=True)
    ng_contact = models.ForeignKey("ng_contact")
    ng_contactgroup = models.ForeignKey("ng_contactgroup")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_ccgroup'

class ng_cgservicet(models.Model):
    idx = models.AutoField(db_column="ng_cgservicet_idx", primary_key=True)
    ng_contactgroup = models.ForeignKey("ng_contactgroup")
    ng_service_templ = models.ForeignKey("ng_service_templ")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_cgservicet'

class ng_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    config = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    ng_check_command_type = models.ForeignKey("ng_check_command_type")
    ng_service_templ = models.ForeignKey("ng_service_templ", null=True)
    name = models.CharField(max_length=192)
    command_line = models.CharField(max_length=765)
    description = models.CharField(max_length=192, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_check_command'

class ng_check_command_type(models.Model):
    idx = models.AutoField(db_column="ng_check_command_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_check_command_type'

class ng_contact(models.Model):
    idx = models.AutoField(db_column="ng_contact_idx", primary_key=True)
    user = models.ForeignKey("user")
    snperiod = models.BooleanField()
    hnperiod = models.BooleanField()
    snrecovery = models.BooleanField()
    sncritical = models.BooleanField()
    snwarning = models.BooleanField()
    snunknown = models.BooleanField()
    hnrecovery = models.BooleanField()
    hndown = models.BooleanField()
    hnunreachable = models.BooleanField()
    sncommand = models.CharField(max_length=192, blank=True)
    hncommand = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_contact'

class ng_contactgroup(models.Model):
    idx = models.AutoField(db_column="ng_contactgroup_idx", primary_key=True)
    name = models.CharField(max_length=192)
    alias = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_contactgroup'

class ng_device_contact(models.Model):
    idx = models.AutoField(db_column="ng_device_contact_idx", primary_key=True)
    device_group = models.ForeignKey("device_group")
    ng_contactgroup = models.ForeignKey("ng_contactgroup")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_device_contact'

class ng_device_templ(models.Model):
    idx = models.AutoField(db_column="ng_device_templ_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    ng_service_templ = models.ForeignKey("ng_service_templ")
    ccommand = models.CharField(max_length=192, blank=True)
    max_attempts = models.IntegerField(null=True, blank=True)
    ninterval = models.IntegerField(null=True, blank=True)
    ng_period = models.IntegerField(null=True, blank=True)
    nrecovery = models.BooleanField()
    ndown = models.BooleanField()
    nunreachable = models.BooleanField()
    is_default = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_device_templ'

class ng_ext_host(models.Model):
    idx = models.AutoField(db_column="ng_ext_host_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    icon_image = models.CharField(max_length=192, blank=True)
    icon_image_alt = models.CharField(max_length=192, blank=True)
    vrml_image = models.CharField(max_length=192, blank=True)
    statusmap_image = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_ext_host'

class ng_period(models.Model):
    idx = models.AutoField(db_column="ng_period_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    alias = models.CharField(max_length=255, blank=True)
    sunrange = models.CharField(max_length=48, blank=True)
    monrange = models.CharField(max_length=48, blank=True)
    tuerange = models.CharField(max_length=48, blank=True)
    wedrange = models.CharField(max_length=48, blank=True)
    thurange = models.CharField(max_length=48, blank=True)
    frirange = models.CharField(max_length=48, blank=True)
    satrange = models.CharField(max_length=48, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_period'

class ng_service(models.Model):
    idx = models.AutoField(db_column="ng_service_idx", primary_key=True)
    name = models.CharField(max_length=192)
    alias = models.CharField(max_length=192, blank=True)
    command = models.CharField(max_length=192, blank=True)
    parameter1 = models.CharField(max_length=192, blank=True)
    parameter2 = models.CharField(max_length=192, blank=True)
    parameter3 = models.CharField(max_length=192, blank=True)
    parameter4 = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_service'

class ng_service_templ(models.Model):
    idx = models.AutoField(db_column="ng_service_templ_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=True)
    volatile = models.BooleanField()
    nsc_period = models.IntegerField(null=True, blank=True)
    max_attempts = models.IntegerField(null=True, blank=True)
    check_interval = models.IntegerField(null=True, blank=True)
    retry_interval = models.IntegerField(null=True, blank=True)
    ninterval = models.IntegerField(null=True, blank=True)
    nsn_period = models.IntegerField(null=True, blank=True)
    nrecovery = models.BooleanField()
    ncritical = models.BooleanField()
    nwarning = models.BooleanField()
    nunknown = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ng_service_templ'

class package(models.Model):
    idx = models.AutoField(db_column="package_idx", primary_key=True)
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=255)
    release = models.CharField(max_length=255)
    architecture = models.ForeignKey("architecture")
    size = models.IntegerField(null=True, blank=True)
    pgroup = models.TextField()
    summary = models.TextField()
    distribution = models.ForeignKey("distribution")
    vendor = models.ForeignKey("vendor")
    buildtime = models.IntegerField(null=True, blank=True)
    buildhost = models.CharField(max_length=765, blank=True)
    packager = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'package'

class package_set(models.Model):
    idx = models.AutoField(db_column="package_set_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'package_set'

class partition(models.Model):
    idx = models.AutoField(db_column="partition_idx", primary_key=True)
    partition_disc = models.ForeignKey("partition_disc")
    mountpoint = models.CharField(max_length=192)
    partition_hex = models.CharField(max_length=6, blank=True)
    size = models.IntegerField(null=True, blank=True)
    mount_options = models.CharField(max_length=255, blank=True)
    pnum = models.IntegerField()
    bootable = models.BooleanField()
    fs_freq = models.IntegerField(null=True, blank=True)
    fs_passno = models.IntegerField(null=True, blank=True)
    partition_fs = models.ForeignKey("partition_fs")
    lut_blob = models.TextField(blank=True, null=True)
    warn_threshold = models.IntegerField(null=True, blank=True)
    crit_threshold = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'partition'

class partition_disc(models.Model):
    idx = models.AutoField(db_column="partition_disc_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    disc = models.CharField(max_length=192)
    priority = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'partition_disc'

class partition_fs(models.Model):
    idx = models.AutoField(db_column="partition_fs_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=48)
    identifier = models.CharField(max_length=3)
    descr = models.CharField(max_length=765, blank=True)
    hexid = models.CharField(max_length=6)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'partition_fs'

class partition_table(models.Model):
    idx = models.AutoField(db_column="partition_table_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=255, blank=True)
    valid = models.BooleanField()
    modify_bootloader = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'partition_table'

class pci_entry(models.Model):
    idx = models.AutoField(db_column="pci_entry_idx", primary_key=True)
    device_idx = models.ForeignKey("device")
    domain = models.IntegerField(null=True, blank=True)
    bus = models.IntegerField(null=True, blank=True)
    slot = models.IntegerField(null=True, blank=True)
    func = models.IntegerField(null=True, blank=True)
    vendor = models.CharField(max_length=18)
    vendorname = models.CharField(max_length=192)
    device = models.CharField(max_length=18)
    devicename = models.CharField(max_length=192)
    class_field = models.CharField(max_length=18, db_column='class') # Field renamed because it was a Python reserved word. Field name made lowercase.
    classname = models.CharField(max_length=192)
    subclass = models.CharField(max_length=18)
    subclassname = models.CharField(max_length=192)
    revision = models.CharField(max_length=96)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'pci_entry'

class peer_information(models.Model):
    idx = models.AutoField(db_column="peer_information_idx", primary_key=True)
    s_netdevice = models.ForeignKey("netdevice", related_name="peer_s_netdevice")
    d_netdevice = models.ForeignKey("netdevice", related_name="peer_d_netdevice")
    penalty = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'peer_information'

class pi_connection(models.Model):
    idx = models.AutoField(db_column="pi_connection_idx", primary_key=True)
    package = models.ForeignKey("package")
    image = models.ForeignKey("image")
    install_time = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'pi_connection'

class rrd_class(models.Model):
    idx = models.AutoField(db_column="rrd_class_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    step = models.IntegerField()
    heartbeat = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_class'

class rrd_data(models.Model):
    idx = models.AutoField(db_column="rrd_data_idx", primary_key=True)
    rrd_set = models.ForeignKey("rrd_set")
    descr = models.CharField(max_length=765)
    descr1 = models.CharField(max_length=189)
    descr2 = models.CharField(max_length=189, blank=True)
    descr3 = models.CharField(max_length=189, blank=True)
    descr4 = models.CharField(max_length=189, blank=True)
    unit = models.CharField(max_length=96, blank=True)
    info = models.CharField(max_length=255, blank=True)
    from_snmp = models.BooleanField()
    base = models.IntegerField(null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)
    var_type = models.CharField(max_length=3, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_data'

class rrd_data_store(models.Model):
    idx = models.AutoField(db_column="rrd_data_store_idx", primary_key=True)
    device = models.ForeignKey("device")
    recv_time = models.IntegerField()
    data = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_data_store'

class rrd_rra(models.Model):
    idx = models.AutoField(db_column="rrd_rra_idx", primary_key=True)
    rrd_class = models.ForeignKey("rrd_class")
    cf = models.CharField(max_length=192)
    steps = models.IntegerField()
    rows = models.IntegerField()
    xff = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_rra'

class rrd_set(models.Model):
    idx = models.AutoField(db_column="rrd_set_idx", primary_key=True)
    device = models.ForeignKey("device")
    filename = models.CharField(max_length=765, blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'rrd_set'

class session_data(models.Model):
    idx = models.AutoField(db_column="session_data_idx", primary_key=True)
    session_id = models.CharField(unique=True, max_length=96)
    value = models.TextField()
    user = models.ForeignKey("user")
    remote_addr = models.TextField(blank=True)
    alias = models.CharField(max_length=255, blank=True)
    login_time = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    forced_logout = models.BooleanField()
    rebuild_server_routes = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'session_data'

class sge_complex(models.Model):
    idx = models.AutoField(db_column="sge_complex_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    total_time = models.CharField(max_length=192, blank=True)
    slot_time = models.CharField(max_length=192, blank=True)
    pe_slots_min = models.IntegerField(null=True, blank=True)
    pe_slots_max = models.IntegerField(null=True, blank=True)
    default_queue = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_complex'

class sge_host(models.Model):
    idx = models.AutoField(db_column="sge_host_idx", primary_key=True)
    host_name = models.CharField(max_length=255)
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_host'

class sge_job(models.Model):
    idx = models.AutoField(db_column="sge_job_idx", primary_key=True)
    job_uid = models.CharField(unique=True, max_length=255)
    jobname = models.CharField(max_length=255)
    jobnum = models.IntegerField()
    taskid = models.IntegerField(null=True, blank=True)
    jobowner = models.CharField(max_length=255)
    jobgroup = models.CharField(max_length=255)
    log_path = models.TextField()
    sge_user = models.ForeignKey("sge_user")
    queue_time = models.DateTimeField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_job'

class sge_job_run(models.Model):
    idx = models.AutoField(db_column="sge_job_run_idx", primary_key=True)
    sge_job = models.ForeignKey("sge_job")
    account = models.CharField(max_length=384)
    sge_userlist = models.ForeignKey("sge_userlist")
    sge_project = models.ForeignKey("sge_project")
    priority = models.IntegerField(null=True, blank=True)
    granted_pe = models.CharField(max_length=192)
    slots = models.IntegerField(null=True, blank=True)
    failed = models.IntegerField(null=True, blank=True)
    failed_str = models.CharField(max_length=765, blank=True)
    exit_status = models.IntegerField(null=True, blank=True)
    masterq = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    start_time_sge = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    end_time_sge = models.DateTimeField(null=True, blank=True)
    sge_ru_wallclock = models.IntegerField(null=True, blank=True)
    sge_cpu = models.IntegerField(null=True, blank=True)
    sge_mem = models.FloatField(null=True, blank=True)
    sge_io = models.IntegerField(null=True, blank=True)
    sge_iow = models.IntegerField(null=True, blank=True)
    sge_maxvmem = models.IntegerField(null=True, blank=True)
    sge_parsed = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_job_run'

class sge_log(models.Model):
    idx = models.AutoField(db_column="sge_log_idx", primary_key=True)
    sge_job = models.ForeignKey("sge_job")
    sge_queue = models.ForeignKey("sge_queue")
    sge_host = models.ForeignKey("sge_host")
    log_level = models.IntegerField(null=True, blank=True)
    log_str = models.CharField(max_length=765)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_log'

class sge_pe_host(models.Model):
    idx = models.AutoField(db_column="sge_pe_host_idx", primary_key=True)
    sge_job_run = models.ForeignKey("sge_job_run")
    device = models.ForeignKey("device")
    hostname = models.CharField(max_length=255)
    num_slots = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_pe_host'

class sge_project(models.Model):
    idx = models.AutoField(db_column="sge_project_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    oticket = models.FloatField(null=True, blank=True)
    fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_project'

class sge_queue(models.Model):
    idx = models.AutoField(db_column="sge_queue_idx", primary_key=True)
    queue_name = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_queue'

class sge_ul_ult(models.Model):
    idx = models.AutoField(db_column="sge_ul_ult_idx", primary_key=True)
    sge_userlist = models.ForeignKey("sge_userlist")
    sge_userlist_type = models.ForeignKey("sge_userlist_type")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_ul_ult'

class sge_user(models.Model):
    idx = models.AutoField(db_column="sge_user_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    oticket = models.FloatField(null=True, blank=True)
    fshare = models.FloatField(null=True, blank=True)
    default_project = models.ForeignKey("sge_project", null=True)
    cluster_user = models.ForeignKey("user")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_user'

class sge_user_con(models.Model):
    idx = models.AutoField(db_column="sge_user_con_idx", primary_key=True)
    user = models.ForeignKey("user")
    sge_config = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_user_con'

class sge_userlist(models.Model):
    idx = models.AutoField(db_column="sge_userlist_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    oticket = models.FloatField(null=True, blank=True)
    fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_userlist'

class sge_userlist_type(models.Model):
    idx = models.AutoField(db_column="sge_userlist_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sge_userlist_type'

class snmp_class(models.Model):
    idx = models.AutoField(db_column="snmp_class_idx", primary_key=True)
    name = models.CharField(max_length=192)
    descr = models.CharField(max_length=765)
    read_community = models.CharField(max_length=192)
    write_community = models.CharField(max_length=192)
    snmp_version = models.IntegerField(null=True, blank=True)
    update_freq = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'snmp_class'

class snmp_config(models.Model):
    idx = models.AutoField(db_column="snmp_config_idx", primary_key=True)
    config = models.IntegerField(null=True, blank=True)
    new_config = models.ForeignKey("new_config")
    snmp_mib = models.ForeignKey("snmp_mib")
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'snmp_config'

class snmp_mib(models.Model):
    idx = models.AutoField(db_column="snmp_mib_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    descr = models.CharField(max_length=765, blank=True)
    mib = models.CharField(max_length=255)
    rrd_key = models.CharField(max_length=192)
    unit = models.CharField(max_length=96, blank=True)
    base = models.IntegerField(null=True, blank=True)
    factor = models.FloatField(null=True, blank=True)
    var_type = models.CharField(max_length=3, blank=True)
    special_command = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'snmp_mib'

class status(models.Model):
    idx = models.AutoField(db_column="status_idx", primary_key=True)
    status = models.CharField(unique=True, max_length=255)
    prod_link = models.BooleanField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'status'

class sys_partition(models.Model):
    idx = models.AutoField(db_column="sys_partition_idx", primary_key=True)
    partition_table = models.ForeignKey("partition_table")
    name = models.CharField(max_length=192)
    mountpoint = models.CharField(max_length=192)
    mount_options = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'sys_partition'

class capability(models.Model):
    idx = models.AutoField(db_column="capability_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=45)
    mother_capability = models.IntegerField(null=True, blank=True)
    mother_capability_name = models.CharField(max_length=45, blank=True, null=True)
    priority = models.IntegerField(null=True, blank=True)
    defvalue = models.IntegerField(null=True, blank=True)
    enabled = models.BooleanField()
    description = models.CharField(max_length=765, blank=True)
    modulename = models.CharField(max_length=384, blank=True, null=True)
    left_string = models.CharField(max_length=192, blank=True)
    right_string = models.CharField(max_length=384, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        # just for compatibility reasons
        self.authorized_by = "None"
        self.enabled = False
    def authorize(self, source):
        self.authorized_by, self.enabled = (source, True)
    class Meta:
        db_table = u'capability'

class user(models.Model):
    idx = models.AutoField(db_column="user_idx", primary_key=True)
    active = models.BooleanField()
    login = models.CharField(unique=True, max_length=255)
    uid = models.IntegerField(unique=True)
    group = models.ForeignKey("group")
    aliases = models.TextField(blank=True, null=True)
    export = models.ForeignKey("new_config", null=True, related_name="export")
    export_scr = models.ForeignKey("new_config", null=True, related_name="export_scr")
    home = models.TextField(blank=True, null=True)
    scratch = models.TextField(blank=True, null=True)
    shell = models.CharField(max_length=765, blank=True)
    password = models.CharField(max_length=48, blank=True)
    cluster_contact = models.BooleanField()
    uservname = models.CharField(max_length=765, blank=True)
    usernname = models.CharField(max_length=765, blank=True)
    usertitan = models.CharField(max_length=765, blank=True)
    useremail = models.CharField(max_length=765, blank=True)
    userpager = models.CharField(max_length=765, blank=True)
    usertel = models.CharField(max_length=765, blank=True)
    usercom = models.CharField(max_length=765, blank=True)
    nt_password = models.CharField(max_length=255, blank=True)
    lm_password = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self.user_vars = {}
        self.capabilities = {}
        try:
            self.django_user = User.objects.get(username=self.login)
        except User.DoesNotExist:
            self.django_user = None
        for cur_cap in self.user_cap_set.all().select_related("capability"):
            self.add_capability(cur_cap.capability)
        self.secondary_groups = []
        self.sge_servers = {}
        self.login_serers = {}
    def create_django_user(self):
        new_du = User(
            username=self.login,
            first_name=self.uservname,
            last_name=self.usernname,
            email=self.useremail,
            is_staff=True,
            is_superuser=False)
        new_du.save()
        self.django_user = new_du
        return new_du
    def add_capability(self, cap):
        self.capabilities[cap.pk] = cap
        self.capabilities[cap.name] = cap
    def add_sge_server(self, srv_dev):
        self.sge_servers[srv_dev.pk] = srv_dev
    def get_sge_servers(self):
        return self.sge_servers.keys()
    def add_user_var(self, u_var):
        self.user_vars[u_var.pk] = u_var
    def save_modified_user_vars(self):
        print "save_modified_user_vars"
    def capability_ok(self, cap_name, only_user=False):
        # do not use, superuser has all rights
        #return self.django_user.has_perm("wf_%s" % (cap_name))
        #print cap_name, cap_name in self.capabilities, cap_name in self.group.capabilities
        if only_user:
            return cap_name in self.capabilities
        else:
            return cap_name in self.capabilities or cap_name in self.group.capabilities 
    def get_num_capabilities(self):
        return len(self.capabilities)
    def get_all_permissions(self, *args):
        return self.django_user.get_all_permissions(*args)
    def get_group_permissions(self, *args):
        return self.django_user.get_group_permissions(*args)
    def add_secondary_groups(self):
        self.secondary_groups = list(group.objects.filter(Q(user_group__user=self.pk)))
    def get_secondary_groups(self):
        return self.secondary_groups
    def get_suffix(self):
        return "userX%dX" % (self.pk)
    class Meta:
        db_table = u'user'
        permissions = {
            ("wf_apc", "APC control"),
            ("wf_bc", "Boot control"),
            ("wf_cc", "Cluster configuration"),
            ("wf_ccl", "Cluster location config"),
            ("wf_ccn", "Cluster network"),
            ("wf_ncd", "Generate new devices"),
            ("wf_conf", "Configuration"),
            ("wf_sc", "Clusterinfo"),
            ("wf_clo", "Clusterlog"),
            ("wf_info", "Information"),
            ("wf_uhw", "Update hardware info"),
            ("wf_hwi", "Hardware info"),
            ("wf_ic", "Image control"),
            ("wf_rms", "Resource managment system"),
            ("wf_jsko", "Kill jobs from other users"),
            ("wf_sacl", "Show all cells"),
            ("wf_jsoi", "Show stdout / stderr and filewatch-info for all users"),
            ("wf_jsyi", "Jobsystem information (SGE)"),
            ("wf_kc", "Kernel control"),
            ("wf_mu", "Modify Users"),
            ("wf_bu", "Browse Users"),
            ("wf_mg", "Modify Groups"),
            ("wf_bg", "Browse Groups"),
            ("wf_user", "User configuration"),
            ("wf_sql", "Display SQL statistics"),
            ("wf_prf", "Profile webfrontend"),
            ("wf_li", "User config"),
            ("wf_mp", "Modify personal userdata (pwd)"),
            ("wf_mpsh", "Show hidden user vars"),
            ("wf_na", "Monitoring daemon"),
            ("wf_nap", "Nagios Problems"),
            ("wf_nai", "Nagios Misc"),
            ("wf_nbs", "Netbotz show"),
            ("wf_pi", "Package install"),
            ("wf_pu", "Partition configuration"),
            ("wf_jsqm", "Queue information (SGE)"),
            ("wf_ch", "Cluster history"),
            ("wf_ri", "Rsync install"),
            ("wf_csc", "Server configuration"),
            ("wf_si", "Session info"),
            ("wf_xeng", "Xen"),
            ("wf_xeni", "Xen Information"),
        }
    def __unicode__(self):
        return u"%s (%d; %s, %s)" % (
            self.login,
            self.pk,
            self.uservname or "novname",
            self.usernname or "nonname")

class group(models.Model):
    idx = models.AutoField(db_column="ggroup_idx", primary_key=True)
    active = models.BooleanField()
    groupname = models.CharField(db_column="ggroupname", unique=True, max_length=48)
    gid = models.IntegerField(unique=True)
    homestart = models.TextField(blank=True)
    scratchstart = models.TextField(blank=True)
    respvname = models.CharField(max_length=765, blank=True)
    respnname = models.CharField(max_length=765, blank=True)
    resptitan = models.CharField(max_length=765, blank=True)
    respemail = models.CharField(max_length=765, blank=True)
    resptel = models.CharField(max_length=765, blank=True)
    respcom = models.CharField(max_length=765, blank=True)
    groupcom = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self.capabilities = {}
        self.users = {}
        try:
            self.django_group = Group.objects.get(name=self.groupname)
        except Group.DoesNotExist:
            self.django_group = None
        for sub_cap in self.group_cap_set.all().select_related("capability"):
            self.add_capability(sub_cap.capability)
    def create_django_group(self):
        new_dg = Group(name=self.groupname)
        new_dg.save()
        self.django_group = new_dg
        return self.django_group
    def add_capability(self, cap):
        self.capabilities[cap.pk] = cap
        self.capabilities[cap.name] = cap
    def get_num_capabilities(self):
        return len(self.capabilities)
    def has_capability(self, cap_name):
        return cap_name in self.capabilities
    def add_user(self, cur_user):
        self.users[cur_user.pk] = cur_user
        self.users[cur_user.login] = cur_user
    def get_user(self, user_ref):
        return self.users[user_ref]
    def get_suffix(self):
        return "groupX%dX" % (self.pk)
    def get_num_users(self):
        return len([key for key in self.users if type(key) == unicode])
    class Meta:
        db_table = u'ggroup'
    def __unicode__(self):
        return "%s (%d)" % (self.groupname,
                            self.pk)

class group_cap(models.Model):
    idx = models.AutoField(db_column="ggroupcap_idx", primary_key=True)
    group = models.ForeignKey("group", db_column="ggroup_id")
    capability = models.ForeignKey("capability")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'ggroupcap'

class user_device_login(models.Model):
    idx = models.AutoField(db_column="user_device_login_idx", primary_key=True)
    user = models.ForeignKey("user")
    device = models.ForeignKey("device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_device_login'

# for secondary groups
class user_group(models.Model):
    idx = models.AutoField(db_column="user_ggroup_idx", primary_key=True)
    group = models.ForeignKey("group")
    user = models.ForeignKey("user")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_ggroup'

class user_var(models.Model):
    idx = models.AutoField(db_column="user_var_idx", primary_key=True)
    user = models.ForeignKey("user")
    name = models.CharField(max_length=189)
    hidden = models.BooleanField()
    type = models.CharField(max_length=3, blank=True)
    editable = models.BooleanField()
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_var'

class user_cap(models.Model):
    idx = models.AutoField(db_column="usercap_idx", primary_key=True)
    user = models.ForeignKey("user")
    capability = models.ForeignKey("capability")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'usercap'

class vendor(models.Model):
    idx = models.AutoField(db_column="vendor_idx", primary_key=True)
    vendor = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'vendor'

class wc_files(models.Model):
    idx = models.AutoField(db_column="wc_files_idx", primary_key=True)
    device = models.ForeignKey("device")
    disk_int = models.IntegerField(null=True, blank=True)
    config = models.CharField(max_length=255, blank=True)
    uid = models.IntegerField(null=True, blank=True)
    gid = models.IntegerField(null=True, blank=True)
    mode = models.IntegerField(null=True, blank=True)
    dest_type = models.CharField(max_length=3)
    source = models.CharField(max_length=765)
    dest = models.CharField(max_length=765)
    error_flag = models.BooleanField()
    content = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'wc_files'

class xen_device(models.Model):
    idx = models.AutoField(db_column="xen_device_idx", primary_key=True)
    device = models.ForeignKey("device")
    memory = models.IntegerField()
    max_memory = models.IntegerField()
    builder = models.CharField(max_length=15, blank=True)
    cmdline = models.CharField(max_length=765, blank=True)
    vcpus = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'xen_device'

class xen_vbd(models.Model):
    idx = models.AutoField(db_column="xen_vbd_idx", primary_key=True)
    xen_device = models.ForeignKey("xen_device")
    vbd_type = models.CharField(max_length=15, blank=True)
    sarg0 = models.CharField(max_length=765, blank=True)
    sarg1 = models.CharField(max_length=765, blank=True)
    sarg2 = models.CharField(max_length=765, blank=True)
    sarg3 = models.CharField(max_length=765, blank=True)
    iarg0 = models.IntegerField(null=True, blank=True)
    iarg1 = models.IntegerField(null=True, blank=True)
    iarg2 = models.IntegerField(null=True, blank=True)
    iarg3 = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'xen_vbd'
