<?php
//-*ics*- ,CAP,name:'cc',descr:'Cluster configuration',enabled:1,defvalue:0,scriptname:'/php/clusterconfig.php',left_string:'Clusterconfig',right_string:'Cluster configuration',pri:0,capability_group_name:'conf'
//-*ics*- ,CAP,name:'ccl',descr:'Cluster location config',enabled:0,defvalue:0,mother_capability_name:'cc'
//-*ics*- ,CAP,name:'ccn',descr:'Cluster network',enabled:0,defvalue:0,mother_capability_name:'cc'
//-*ics*- ,CAP,name:'ncd',descr:'Generate new devices',enabled:1,defvalue:0,mother_capability_name:'cc'
//
// Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
//
// Send feedback to: <lang@init.at>
// 
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License Version 2 as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
//
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
function show_network_info($nstuff) {
    $class_str="Unknown Class";
    if ($nstuff->netmask=="255.0.0.0") {
        $class_str="Class A";
    } else if ($nstuff->netmask=="255.255.0.0") {
        $class_str="Class B";
    } else if ($nstuff->netmask=="255.255.255.0") {
        $class_str="Class C";
    }
    $sqpf="{$nstuff->postfix}";
    $fqpf="{$sqpf}.{$nstuff->name}";
    $nodename="node001";
    echo " $class_str, entry for '$nodename': '$nodename$fqpf'";
    if ($nstuff->short_names) echo " and '$nodename$sqpf'";
}
function get_all_snmp_mibs() {
    $mres=query("SELECT * FROM snmp_mib");
    $mibs=array();
    while ($mfr=mysql_fetch_object($mres)) $mibs[$mfr->snmp_mib_idx]=$mfr;
    return $mibs;
}
function get_snmp_classes() {
    $mres=query("SELECT * FROM snmp_class");
    $sc=array();
    $sc[0]->name="not set";
    $sc[0]->descr="";
    $sc[0]->update_freq=0;
    while ($mfr=mysql_fetch_object($mres)) $sc[$mfr->snmp_class_idx]=$mfr;
    return $sc;
}
function get_nag_time_periods() {
    $mres=query("SELECT * FROM ng_period");
    $ps=array();
    while ($mfr=mysql_fetch_object($mres)) $ps[$mfr->ng_period_idx]=$mfr;
    return $ps;
}
function get_nag_contacts() {
    $mres=query("SELECT * FROM ng_contact");
    $ct=array();
    while ($mfr=mysql_fetch_object($mres)) {
        $ct[$mfr->ng_contact_idx]=$mfr;
        $cg[$mfr->ng_contact_idx]->groups=array();
    }
    return $ct;
}
function get_nag_contact_groups() {
    $mres=query("SELECT * FROM ng_contactgroup");
    $cg=array();
    while ($mfr=mysql_fetch_object($mres)) {
        $cg[$mfr->ng_contactgroup_idx]=$mfr;
        $cg[$mfr->ng_contactgroup_idx]->contacts=array();
        $cg[$mfr->ng_contactgroup_idx]->devgroups=array();
        $cg[$mfr->ng_contactgroup_idx]->service_templates=array();
    }
    return $cg;
}
function get_nag_service_templates() {
    $mres=query("SELECT * FROM ng_service_templ");
    $st=array(0=>"unset");
    while ($mfr=mysql_fetch_object($mres)) {
        $st[$mfr->ng_service_templ_idx]=$mfr;
        $st[$mfr->ng_service_templ_idx]->groups=array();
    }
    return $st;
}
function get_config_vartypes() {
    $cvt=array("str"=>"String","int"=>"Integer","blob"=>"Blob");
    return $cvt;
}
function get_nag_services() {
    $mres=query("SELECT * FROM ng_service");
    $ns=array();
    while ($mfr=mysql_fetch_object($mres)) {
        $ns[$mfr->ng_service_idx]=$mfr;
    }
    return $ns;
}
function get_nag_device_templates() {
    // parse nagios device templates
    $mres=query("SELECT * FROM ng_device_templ");
    $ng_devices=array(0=>"unset");
    while ($mfr=mysql_fetch_object($mres)) $ng_devices[$mfr->ng_device_templ_idx]=$mfr;
    return $ng_devices;
}
function get_nag_ext_hosts() {
    // parse nagios device templates
    $mres=query("SELECT * FROM ng_ext_host ORDER BY name");
    $ng_hosts=array(0=>"unset");
    while ($mfr=mysql_fetch_object($mres)) $ng_hosts[$mfr->ng_ext_host_idx]=$mfr;
    return $ng_hosts;
}
function get_device_shapes() {
    // parse device shapes
    $mres=query("SELECT ds.name,ds.description,ds.device_shape_idx FROM device_shape ds");
    $ds_shapes=array(0=>"unset");
    while ($mfr=mysql_fetch_object($mres)) $ds_shapes[$mfr->device_shape_idx]="$mfr->name ($mfr->description)";
    return $ds_shapes;
}
function get_config_types() {
    $mres=query("SELECT * FROM config_type c");
    $config_types=array();
    while ($mfr=mysql_fetch_object($mres)) $config_types[$mfr->config_type_idx]=$mfr;
    return $config_types;
}
function get_switches() {
    // parse switches
    $mres=query("SELECT d.name,d.device_idx FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='S'");
    $switches=array(0=>"unset");
    while ($mfr=mysql_fetch_object($mres)) $switches[$mfr->device_idx]="$mfr->name";
    return $switches;
}
function get_masterswitches() {
    // parse masterswitches
    $mres=query("SELECT d.name,d.device_idx FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='AM'");
    $mswitches=array(0=>"unset");
    while ($mfr=mysql_fetch_object($mres)) $mswitches[$mfr->device_idx]="$mfr->name";
    return $mswitches;
}
function get_ms_outlets() {
    $msoutlets=array(0=>"unset");
    for ($idx=1;$idx < 9;$idx++) $msoutlets[$idx]="$idx";
    return $msoutlets;
}
function get_networks() {
    $nets=array();
    $mres=query("SELECT n.*,nt.description,nt.identifier as ntid FROM network n, network_type nt WHERE n.network_type=nt.network_type_idx");
    while ($mfr=mysql_fetch_object($mres)) {
        $nets[$mfr->network_idx]=$mfr;
    }
    return $nets;
}
function get_network_types() {
    $netts=array();
    $mres=query("SELECT nt.* FROM network_type nt ");
    while ($mfr=mysql_fetch_object($mres)) {
        $netts[$mfr->network_type_idx]=$mfr;
    }
    return $netts;
}
function get_device_types() {
    $dev_types=array();
    $mres=query("SELECT * FROM device_type");
    while ($mfr=mysql_fetch_object($mres)) {
        $dev_types[$mfr->device_type_idx]=$mfr;
    }
    return $dev_types;
}
function get_device_groups() {
    $dev_groups=array();
    $mres=query("SELECT dg.*, d.device_idx FROM device_group dg LEFT JOIN device d ON dg.device=d.device_idx");
    while ($mfr=mysql_fetch_object($mres)) {
	// devices without meta_devs
        $mfr->device_count=0;
	// devices total (with meta_devs)
	$mfr->tot_device_count=0;
        $dev_groups[$mfr->device_group_idx]=$mfr;
    }
    return $dev_groups;
}
function get_devices(&$dgs) {
    $devices=array();
    $mres=query("SELECT d.*,dt.identifier FROM device d,device_type dt WHERE d.device_type=dt.device_type_idx ORDER BY d.device_group,d.name");
    while ($mfr=mysql_fetch_object($mres)) {
        $dgs[$mfr->device_group]->tot_device_count++;
	if ($mfr->identifier != "MD") $dgs[$mfr->device_group]->device_count++;
        $mfr->boot_devs=array();
        $devices[$mfr->device_idx]=$mfr;
    }
    // check for bootable devices
    $mres=query("SELECT DISTINCT n.netdevice_idx,n.devname,d.device_idx FROM device d, netip ni, netdevice n, network nw, network_type nt WHERE n.device=d.device_idx AND ((ni.netdevice=n.netdevice_idx AND ni.network=nw.network_idx AND nw.network_type=nt.network_type_idx AND nt.identifier='b') OR n.dhcp_device)");
    while ($mfr=mysql_fetch_object($mres)) {
        //echo " $mfr->device_idx $mfr->devname<br>";
        $devices[$mfr->device_idx]->boot_devs[$mfr->devname]=$mfr->netdevice_idx;
    }
    return $devices;
}
function get_partition_tables() {
    $p_tables=array(0=>"unset");
    $mres=query("SELECT * FROM partition_table ORDER BY name");
    while ($mfr=mysql_fetch_object($mres)) $p_tables[$mfr->partition_table_idx]="$mfr->name".($mfr->valid ? "" : " (*)");
    return $p_tables;
}
function get_boot_servers() {
    $boot_server=array();
    $boot_server_idx=array();
    $mres=query("SELECT d.device_idx,d.name FROM device d, deviceconfig dc, config c WHERE dc.device=d.device_idx AND dc.config=c.config_idx AND c.name='mother_server'");
    while ($mfr=mysql_fetch_object($mres)) {
        $boot_server[$mfr->device_idx]=$mfr->name;
        $boot_server_idx[$mfr->name]=$mfr->device_idx;
    }
    return array($boot_server,$boot_server_idx);
}
function is_netspeed($spd) {
    return preg_match("/^-*\d+$/",$spd);
}
function get_all_routing_netdevices() {
    $all_r_devs=array();
    $mres=query("SELECT n.*,d.name FROM netdevice n, device d WHERE n.routing=1 AND n.device=d.device_idx ORDER BY d.name,n.devname");
    while($mfr=mysql_fetch_object($mres)) $all_r_devs[$mfr->netdevice_idx]=$mfr;
    return $all_r_devs;
}
function get_peer_information() {
    $p_i=array();
    $pi_s=array();
    $mres=query("SELECT pi.*,ns.devname AS nsn,nd.devname AS ndn,ds.name AS dsn,dd.name AS ddn FROM peer_information pi, netdevice ns, netdevice nd,device ds,device dd WHERE (pi.s_netdevice=ns.netdevice_idx AND ns.device=ds.device_idx) AND (pi.d_netdevice=nd.netdevice_idx AND nd.device=dd.device_idx) ORDER BY ndn,ddn,nsn,dsn");
    while ($mfr=mysql_fetch_object($mres)) {
        if (!in_array($mfr->s_netdevice,$pi_s)) {
            $pi_s[]=$mfr->s_netdevice;
            $p_i[$mfr->s_netdevice]=array();
        }
        if (!in_array($mfr->d_netdevice,array_keys($p_i[$mfr->s_netdevice]))) {
            $p_i[$mfr->s_netdevice][$mfr->d_netdevice]=array($mfr->penalty,$mfr->ndn,$mfr->ddn);
        }
        if (!in_array($mfr->d_netdevice,$pi_s)) {
            $pi_s[]=$mfr->d_netdevice;
            $p_i[$mfr->d_netdevice]=array();
        }
        if (!in_array($mfr->s_netdevice,array_keys($p_i[$mfr->d_netdevice]))) {
            $p_i[$mfr->d_netdevice][$mfr->s_netdevice]=array($mfr->penalty,$mfr->nsn,$mfr->dsn);
        }
    }
    //print_r($p_i);
    return $p_i;
}
function add_sib_config($vars,$all_nag_names,$all_snmp_mibs,$log_stack,$stuff) {
    $stuff->check_priority_change($vars,&$log_stack);
    $stuff->check_for_new_var(&$vars,&$log_stack);
    $stuff->check_for_new_nagios(&$vars,&$log_stack,&$all_nag_names);
    $stuff->check_for_new_snmp(&$vars,&$log_stack,&$all_snmp_mibs);
    $stuff->check_for_var_change(&$vars,&$log_stack);
    $stuff->check_for_nagios_change(&$vars,&$log_stack,&$all_nag_names);
    $stuff->check_for_snmp_change(&$vars,&$log_stack,&$all_snmp_mibs);
    return;
}
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["cc_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);
    // user capabilities
    $ucl=usercaps($sys_db_con);
    // check dtype
    $l_type="location";
    $n_type="network";
    $nag_type="nagios";
    $c_type="config";
    $mod_type="modify";
    // global : show global config options (for example for hardware settings)
    // eml    : also show entry if machine_list is empty
    // display array
    $dc_types=array();
    $dc_types["-- Device specific settings --"]=array("global"=>0,"eml"=>1,"disabled"=>1);
    if ($ucl["ccl"]) $dc_types[$l_type]=array("global"=>1,"eml"=>0,"sc"=>"cm_loc");
    if ($ucl["ccn"]) {
	$dc_types[$n_type]=array("global"=>0,"eml"=>0,"sc"=>"cm_net");
	//$dc_types[$nag_type]=array("global"=>0,"eml"=>0,"sc"=>"cm_nag");
    }
    $config_types=get_config_types();
    foreach ($config_types as $idx=>$stuff) {
        $dc_types["$c_type ($stuff->name)"]=array("name"=>$stuff->name,"description"=>$stuff->description,"idx"=>$idx,"global"=>1,"eml"=>0,"sc"=>"cm_id_{$stuff->identifier}");
    }
    $dc_types["-- Device specific config settings --"]=array("global"=>0,"eml"=>1,"disabled"=>1);
    foreach ($config_types as $idx=>$stuff) {
        $dc_types["$c_type ($stuff->name), options"]=array("name"=>$stuff->name,"description"=>$stuff->description,"idx"=>$idx,"global"=>0,"eml"=>0,"sc"=>"cm_idds_{$stuff->identifier}");
    }
    $dc_types["-- Global settings --"]=array("global"=>0,"eml"=>1,"disabled"=>1);
    foreach (array("device groups","devices","network","Nagios","SNMP") as $ct) $dc_types["$mod_type $ct"]=array("global"=>0,"eml"=>1,"sc"=>"cg_$ct");
    foreach ($config_types as $idx=>$stuff) {
        $dc_types["$mod_type config ($stuff->name)"]=array("global"=>0,"eml"=>1,"sc"=>"cg_config_$stuff->identifier");
    }
    $valid_types=array();
    foreach ($dc_types as $name=>$info) {
        if (!isset($info["disabled"])) $valid_types[]=strtolower($info["sc"]);
    }
    $dtype=$valid_types[0];
    if (in_array("dtype",$varkeys)) $dtype=strtolower($vars["dtype"]);
    if (!in_array($dtype,$valid_types)) $dtype=$valid_types[0];
    foreach ($dc_types as $name=>$stuff) {
        if (isset($stuff["sc"]) && $stuff["sc"]==$dtype) $dc_stuff=$stuff;
    }
    
    $sc_types=array("dn"=>array("do nothing"),
                    "sc"=>array("show config(s)"),
                    "cc"=>array("create config(s)"),
                    "scc"=>array("show and create config(s)"));
    $valid_sc_types=array_keys($sc_types);
    $show_conf="";
    $create_conf="";
    $show_content="";
    $hiddensctype="";
    if (in_array("showconf",$varkeys)) {
        $show_conf="on";
        $hiddensctype.="<input type=hidden name=\"showconf\" />\n";
    }
    if (in_array("createconf",$varkeys)) {
        $create_conf="on";
        $hiddensctype.="<input type=hidden name=\"createconf\" />\n";
    }
    if (in_array("showcontent",$varkeys)) {
        $show_content="on";
        $hiddensctype.="<input type=hidden name=\"showcontent\" />\n";
    }
    $hiddendtype="<input type=hidden name=\"dtype\" value=\"$dtype\" />\n";
    htmlhead();
    clusterhead($sys_config,"Cluster config page",$style="formate.css",
                array("th.config" =>array("background-color:#e2d2d2","text-align:right" ),
                      "td.config" =>array("background-color:#f2e2e2","text-align:right" ),
                      "td.nconfig"=>array("background-color:#f2e2e2","text-align:center"),
                      "th.delnew" =>array("background-color:#ddbb99","text-align:center"),
                      "td.delnew" =>array("background-color:#eeccaa","text-align:center"),
                      "th.use"    =>array("background-color:#eedd88","text-align:center"),
                      "td.use1"   =>array("background-color:#ffdd88","text-align:center"),
                      "td.use2"   =>array("background-color:#eecc88","text-align:center"),
                      "td.use3"   =>array("background-color:#ccbb88","text-align:center"),
                      "th.select" =>array("background-color:#77bb55","text-align:center"),
                      "td.select" =>array("background-color:#88cc66","text-align:center"),
                      "td.hloccr" =>array("background-color:#f2e2e2","text-align:right" ),
                      "td.hloccl" =>array("background-color:#f2e2e2","text-align:left"  ),
                      "td.blind"  =>array("background-color:#f2e2e2","text-align:left"  ),
                      "th.net"    =>array("background-color:#ffddee","text-align:center"),
                      "td.net"    =>array("background-color:#ddddbb","text-align:center"),
                      "td.net1"   =>array("background-color:#ddddbb","text-align:center"),
                      "td.net2"   =>array("background-color:#ccccaa","text-align:center"),
                      "td.netl"   =>array("background-color:#ddddbb","text-align:left"  ),
                      "td.netnew" =>array("background-color:#eeeecc","text-align:center"),
                      "td.ip"     =>array("background-color:#ddcccc","text-align:center","border-spacing:2px"),
                      "td.ipnew"  =>array("background-color:#eedddd","text-align:center","border-spacing:2px"),
                      "td.peer"   =>array("background-color:#ccccdd","text-align:left"  ),
                      "td.peernew"=>array("background-color:#ddddee","text-align:left"  )
                      )
                );
    clusterbody($sys_config,"Cluster config",array("bc"),array("conf"));
    $no_neg_field=array(0=>"default",1=>"on",3=>"off");
    $no_dpl_field=array(0=>"default",1=>"full",3=>"half");
    $no_spd_field=array(0=>"default",1=>"10 MBit",3=>"100 Mbit",5=>"1 GBit",7=>"10 GBit");
//     foreach ($no_neg_field as $s1=>$l1) {
//         foreach ($no_dpl_field as $s2=>$l2) {
//             foreach ($no_spd_field as $s3=>$l3) {
//                 echo strval($s1 | $s2 << 2 | $s3 << 4)." : $s1:$l1 , $s2:$l2 , $s3:$l3 <br>";
//             }
//         }
//     }
    if ($ucl["cc"]) {
        $log_stack=new messagelog();
        list($boot_server,$boot_server_idx)=get_boot_servers();
        $dev_types=get_device_types();
        $dev_groups=get_device_groups();
        $devs=get_devices($dev_groups);
        $networks=get_networks();
        $all_routing_devices=get_all_routing_netdevices();
        $peer_information=get_peer_information();
        $network_types=get_network_types();
        $refresh_tk_array=array();
        $remove_bs_array=array();
        $remove_dev_array=array();
        $new_bs_array=array();
        $del_bs_array=array();
        // to store the previous value of write_macadr
        $write_macadr_state=array();
        $nag_service_templates=get_nag_service_templates();
        $config_vts=get_config_vartypes();
        $all_snmp_mibs=get_all_snmp_mibs();
        $snmp_classes=get_snmp_classes();
        foreach ($boot_server as $idx=>$name) {
            $refresh_tk_array[$name]=array();
            $remove_bs_array[$name]=array();
            $new_bs_array[$name]=array();
            $write_macadr_state=array();
        }
        if ($ucl["ncd"]) {
	    // check for idx of meta_device
	    $md_devt=0;
	    foreach ($dev_types as $idx=>$stuff) {
		if ($stuff->identifier == "MD") $md_devt=$idx;
	    }
            // check for new devices/device_groups
            foreach ($dev_groups as $devg_idx=>$dev_g) {
                $dgr="deldevgroup_$devg_idx";
                if (isset($vars[$dgr]) && $vars[$dgr] && (!$dev_g->device_count)) {
		    if ($dev_g->device && $md_devt) query ("DELETE FROM device WHERE device_group=$devg_idx AND device_type=$md_devt");
                    query("DELETE FROM device_group WHERE device_group_idx=$devg_idx");
                    $log_stack->add_message("deleted device_group '{$dev_g->name}'","ok",1);
                } else {
                    $dgn=0;
                    $dgd=0;
                    if (isset($vars["devgroupname_$devg_idx"])) {
			$dgn=$vars["devgroupname_$devg_idx"];
			if (isset($vars["devgroupdescr_$devg_idx"])) $dgd=$vars["devgroupdescr_$devg_idx"];
			if ($dgn && $dgd) {
			    if ($dgn != $dev_g->name || $dgd != $dev_g->description) {
				update_table("device_group","name='".mysql_escape_string($dgn)."',description='".mysql_escape_string($dgd)."' WHERE device_group_idx=$devg_idx");
				$log_stack->add_message("modified device_group '{$dev_g->name}' to name '$dgn', description '$dgd'","ok",1);
			    }
			}
			$nmd=0;
			if (isset($vars["devgroupmg_$devg_idx"])) $nmd=1;
			if ($nmd && ! $dev_g->device_idx) {
			    if ($md_devt) {
				$newdev_idx=insert_table_set("device","name='METADEV_".mysql_escape_string($dgn)."',device_group=$devg_idx,device_type=$md_devt");
				if ($newdev_idx) {
				    $log_stack->add_message("added Meta-device to device_group '{$dev_g->name}'","ok",1);
				    update_table("device_group","device=$newdev_idx WHERE device_group_idx=$devg_idx");
				}
			    } else {
				$log_stack->add_message("cannot added Meta-device to device_group '{$dev_g->name}'","MetaDevicetype missing",0);
			    }
			} else if (!$nmd && $dev_g->device_idx) {
			    if ($md_devt) {
				query("DELETE FROM device WHERE device_group=$devg_idx AND device_type=$md_devt");
				update_table("device_group","device=0 WHERE device_group_idx=$devg_idx");
				$log_stack->add_message("removed Meta-device from device_group '{$dev_g->name}'","ok",1);
			    } else {
				$log_stack->add_message("cannot delete Meta-device from device_group '{$dev_g->name}'","MetaDevicetype missing",0);
			    }
			}
		    }
                }
            }
            $ndgn="newdevgroupname";
            $ndgd="newdevgroupdescr";
            if (is_set($ndgn,&$vars) && is_set($ndgd,&$vars) && $vars[$ndgn]) {
                $ndgn=$vars[$ndgn];
                $ndgd=$vars[$ndgd];
                if (is_set("newdevgroupcdg",&$vars)) {
                    $cdg=1;
                } else {
                    $cdg=0;
                }
                $ndg_idx=insert_table("device_group","0,'".mysql_escape_string($ndgn)."','".mysql_escape_string($ndgd)."',0,$cdg,null");
                if ($ndg_idx) {
                    $log_stack->add_message("created new device_group '$ndgn' (description '$ndgd')","ok",1);
                    if (isset($vars["newdevgroupmg"])) {
                        if ($md_devt) {
                            $newdev_idx=insert_table_set("device","name='METADEV_".mysql_escape_string($ndgn)."',device_group=$ndg_idx,device_type=$md_devt");
                            if ($newdev_idx) {
                                $log_stack->add_message("added Meta-device to device_group '$ndgn'","ok",1);
                                update_table("device_group","device=$newdev_idx WHERE device_group_idx=$ndg_idx");
                            }
                        } else {
                            $log_stack->add_message("cannot added Meta-device to device_group '$ndgn'","MetaDevicetype missing",0);
                        }
                        
                    }
                } else {
                    $log_stack->add_message("cannot add new device_group","SQL problem",0);
                }
            }
            $all_devices=array();
            foreach ($devs as $dev_idx=>$dev) {
                $all_devices[$dev->name]=array($dev->device_group);
                $refresh_tk=0;
                $dgr="deldev_$dev_idx";
                //echo $dgr;
                if (isset($vars[$dgr]) && $vars[$dgr]) {
                    if ($dev->bootserver) {
                        $remove_dev_array[$dev_idx]=array($dev->name,$dev_groups[$dev->device_group]->name);
                        $remove_bs_array[$boot_server[$dev->bootserver]][]=$dev->name;
                    } else {
                        $remove_dev_array[$dev_idx]=array($dev->name,$dev_groups[$dev->device_group]->name);
                    }
                } else {
                    if (isset($vars["devname_$dev_idx"]) && isset($vars["devgroup_$dev_idx"]) && isset($vars["devtype_$dev_idx"]) && isset($vars["bootnetdevice_$dev_idx"]) && isset($vars["devbootserver_$dev_idx"])) {
                        $devbs=$vars["devbootserver_$dev_idx"];
                        if ($devbs != $dev->bootserver) {
                            if ($dev->dhcp_write) {
                                if ($devbs) $write_macadr_state[$boot_server[$devbs]][]=$dev->name;
                            }
                            if ($dev->bootserver) $remove_bs_array[$boot_server[$dev->bootserver]][]=$dev->name;
                            if ($devbs) {
                                $new_bs_array[$boot_server[$devbs]][]=$dev->name;
                            } else {
                                $del_bs_array[]=$dev->name;
                            }
                        }
                        $devn=$vars["devname_$dev_idx"];
                        $devg=$vars["devgroup_$dev_idx"];
                        $devt=$vars["devtype_$dev_idx"];
                        $devbd=$vars["bootnetdevice_$dev_idx"];
                        $devsnmp=$vars["devsnmp_$dev_idx"];
                        if ($devn && $devg && $devt) {
                            if ($devn != $dev->name || $devg != $dev->device_group || $devt != $dev->device_type || $devbd != $dev->bootnetdevice || $devsnmp != $dev->snmp_class) {
                                update_table("device","name='".mysql_escape_string($devn)."',device_group=$devg,bootnetdevice=$devbd,device_type=$devt,snmp_class=$devsnmp WHERE device_idx=$dev_idx");
                                $refresh_tk=1;
                            }
                        }
                    }
                }
                if ($refresh_tk && $dev->bootserver) $refresh_tk_array[$boot_server[$dev->bootserver]][]=$dev->name;
            }
            if (is_set("newdevname",&$vars)) {
                $ndevn=$vars["newdevname"];
                $ndevg=$vars["newdevgroup"];
                $ndevt=$vars["newdevtype"];
                $ndevsnmp=$vars["newdevsnmp"];
                $ndevbs=$vars["newdevbootserver"];
                if ($ndevn && $ndevg && $ndevt) {
                    if (isset($vars["newdevrange"]) && $vars["newdevrange"]) {
                        $num_d=$vars["ndr_digits"];
                        $lower=$vars["ndr_lower"];
                        $upper=$vars["ndr_upper"];
                        $ndevn_array=array();
                        if (preg_match("/^\d+$/",$lower) && preg_match("/^\d+$/",$upper)) {
                            $lower=(int)$lower;
                            $upper=(int)$upper;
                            if ($upper >= $lower) {
                                $f_str=sprintf("%%s%%0%dd",$num_d);
                                for ($idx=$lower;$idx<=$upper;$idx++) $ndevn_array[]=sprintf($f_str,$ndevn,$idx);
                            }
                        }
                    } else {
                        $ndevn_array=array($ndevn);
                    }
                    foreach ($ndevn_array as $ndevn) {
                        if (in_array($ndevn,array_keys($all_devices))) {
                            $log_stack->add_message("failed to create device '$ndevn' in device_group '{$dev_groups[$ndevg]->name}'","name already used",0);
                        } else {
                            query("INSERT INTO device SET name='".mysql_escape_string($ndevn)."',device_group=$ndevg,device_type=$ndevt,snmp_class=$ndevsnmp,bootserver=$ndevbs");
                            $log_stack->add_message("created device '$ndevn' in device_group '{$dev_groups[$ndevg]->name}'","ok",1);
                            $all_devices[$ndevn]=array($ndevg);
                        }
                    }
                }
            }
            foreach ($refresh_tk_array as $server=>$nodes) {
                if (count($nodes)) {
                    //echo "****<br>";
                    $rets=contact_server($sys_config,"mother_server",8001,"refresh_tk ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    process_ret($log_stack,$server,8001,"refresh_tk",$rets,$nodes);
                }
            }
            foreach ($remove_bs_array as $server=>$nodes) {
                if (count($nodes)) {
                    $rets=contact_server($sys_config,"mother_server",8001,"delete_macadr ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    process_ret($log_stack,$server,8001,"delete_macadr",$rets,$nodes);
                    $rets=contact_server($sys_config,"mother_server",8001,"remove_bs ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    process_ret($log_stack,$server,8001,"remove_bs",$rets,$nodes);
                }
            }
            if (count($del_bs_array)) {
                update_table("device","bootserver=0 WHERE (name='".implode("' OR name='",$del_bs_array)."')");
            } 
            foreach ($remove_dev_array as $dev_idx=>$dev_stuff) {
                list($dev_name,$dg_name)=$dev_stuff;
                query("DELETE FROM device WHERE device_idx=$dev_idx");
                $log_stack->add_message("deleted device '$dev_name' from device_group '$dg_name'","ok",1);
            }
            foreach ($new_bs_array as $server=>$nodes) {
                if (count($nodes)) {
                    // set the mother-server again
                    foreach ($nodes as $node) {
                        $write_array=array("bootserver={$boot_server_idx[$server]}");
			// restore write_macadr if needed
			if (in_array($server,array_keys($write_macadr_state))) {
			  if (in_array($node,$write_macadr_state[$server])) $write_array[]="dhcp_write=1";
			}
                        update_table("device",implode(",",$write_array)." WHERE name='$node'");
                    }
                    $rets=contact_server($sys_config,"mother_server",8001,"new_bs ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    process_ret($log_stack,$server,8001,"new_bs",$rets,$nodes);
                    $rets=contact_server($sys_config,"mother_server",8001,"write_macadr ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    process_ret($log_stack,$server,8001,"write_macadr",$rets,$nodes);
                }
            }
            // re-read device groups
            $dev_groups=get_device_groups();
            $devs=get_devices($dev_groups);
        }
        // parse the device selection
        list($display_a,$machgroups,$hiddenmach,$actmach,$optsel)=get_display_list($vars,"",array(),1);
        // simple protocol
        $hcproto=array();
        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
        hidden_sid();
        if (count($machgroups)) {
            message ("Please select devicegroup or device(s) by their name:");
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\" summary=\"selection table\"><tr>";
            echo "<td>";
            echo "<select name=\"selgroup[]\" multiple size=5>";
            foreach ($machgroups as $mg=>$mgv) {
                echo "<option value=\"$mg\"";
                if ($mgv["selected"]) echo " selected ";
                echo ">$mg";
                if ($mgv["num"]) echo " (".$mgv["num"]." ".get_plural("device",$mgv["num"]).")";
                echo "</option>\n";
            }
            echo "</select>";
            echo "</td>\n";
            echo "<td>&nbsp;&nbsp;</td>";
            echo "<td><select name=\"selmach[]\" size=5 multiple>";
            foreach ($machgroups as $act_group=>$display_g) {
                if ($display_g["num"]) {
                    $num_mach=sizeof($display_g["list"]);
                    $mach_str=get_plural("device",$num_mach);
                    echo "<option value=d disabled>$act_group [ $num_mach $mach_str ]\n";
                    $mres=query("SELECT d.name,d.comment FROM device d WHERE ( d.name='".implode("' OR d.name='",$display_g["list"])."') ORDER BY d.name");
                    while ($mfr=mysql_fetch_object($mres)) {
                        echo "<option value=\"$mfr->name\"";
                        $name=$mfr->name;
                        if (in_array($name,$actmach)) echo " selected ";
                        echo ">$name";
                        if ($mfr->comment) echo " ($mfr->comment)";
                    }
                    echo "</option>\n";
                }
            }
            echo "</select></td>";
            echo "</tr></table></div>\n";
        }
        echo "<h3>Actual Displaytype is ";
        echo "<select name=\"dtype\" >";
        foreach ($dc_types as $name=>$info) {
            if ($info["eml"] || count($machgroups)) {
                echo "<option value=\"".strtolower($info['sc'])."\" ";
                if (isset($info["disabled"])) {
                    echo " disabled ";
                } else if (strtolower($info["sc"])==$dtype) {
                    echo " selected ";
                }
                echo ">$name</option>\n";
            }
        }
        echo "</select>, ";
        echo "show config: <input type=checkbox name=\"showconf\" ".($show_conf ? "checked" : "")." />, ";
	echo "create config: <input type=checkbox name=\"createconf\" ".($create_conf ? "checked " : "" )." />, ";
	echo "show content: <input type=checkbox name=\"showcontent\" ".($show_content ? "checked " : "")." />, ";
        echo "<input type=submit value=\"select\" /></h3>\n";
        echo "</form>\n";
        $device_locations=array();
        $nag_device_templates=array();
        $nag_ext_hosts=array();
        $device_classes=array();
        $switches=array();
        $ds_shapes=array();
        $partition_tables=array();
        // parse available configs
        if (preg_match("/^cm_id_(.*)$/",$dtype,$id_match)) {
            $gc2=get_glob_configs(array(),$id_match[1]);
            // count configs for the selected type
            $num_configs=count($gc2);
            $num_max_rows=min(3,$num_configs);
            $extra_rows=$num_max_rows-$num_configs%$num_max_rows;
            if ($extra_rows == $num_max_rows) $extra_rows=0;
        } elseif ($dtype=="cm_loc") {
            $device_classes=get_device_classes();
            $device_locations=get_device_locations();
            $nag_device_templates=get_nag_device_templates();
            $nag_ext_hosts=get_nag_ext_hosts();
            $partition_tables=get_partition_tables();
            $ds_shapes=get_device_shapes();
            $switches=get_switches();
            $mswitches=get_masterswitches();
            $msoutlets=get_ms_outlets();
        }
        // check for new config-options
        if (preg_match("/^cg_config_(.*)$/",$dtype,$c_id)) {
            $gc2=get_glob_configs(array(),$c_id[1]);
            $all_nag_names=array();
            foreach ($gc2 as $cname=>$config) {
                if (is_set($gc2[$cname]->compose_prefix()."_del",&$vars)) {
                    $log_stack->add_message("deleted config named '$cname'","ok",1);
                    foreach (array("ng_check_command","snmp_config","config_str","config_int","config_blob","deviceconfig") as $tname) {
                        query("DELETE FROM $tname WHERE config=$config->config_idx");
                    }
                    query("DELETE FROM config WHERE config_idx=$config->config_idx");
                    //echo "DEL $cname<br>";
                    unset($gc2[$cname]);
                } else {
                    $all_nag_names=array_merge($all_nag_names,$config->get_nagios_names());
                }
            }
            foreach ($gc2 as $cname=>$stuff) {
                add_sib_config(&$vars,&$all_nag_names,&$all_snmp_mibs,&$log_stack,&$gc2[$cname]);
            }
            if (is_set("newconf",&$vars)) {
                $new_conf_name=$vars["newconf"];
                $new_conf_pri=$vars["newconf_pri"];
                $new_conf_descr=$vars["newconf_descr"];
                $add_it=1;
                if (in_array($new_conf_name,array_keys($gc2))) {
                    $add_it=0;
                    $log_stack->add_message("cannot add new config named '$new_conf_name'","name already used",0);
                }
                if (!preg_match("/^-*\d+$/",$new_conf_pri)) {
                    $add_it=0;
                    $log_stack->add_message("cannot add new config named '$new_conf_name'","parse error for pri",0);
                }
                if ($add_it) {
                    // get config-type idx
                    foreach ($config_types as $cidx=>$cid) {
                        if ($cid->identifier == $c_id[1]) break;
                    }
                    $ins=insert_table("config","0,'".mysql_escape_string($new_conf_name)."','".
                                      mysql_escape_string($new_conf_descr)."',$new_conf_pri,$cidx,null");
                    if ($ins) {
                        $log_stack->add_message("added new config named '$new_conf_name', pri $new_conf_pri","OK",1);
                        $gc2[$new_conf_name]=new config($new_conf_name,$new_conf_descr,$c_id[1],$new_conf_pri,$ins);
                        if ($c_id[1] == "e") {
                            $gc2[$new_conf_name]->add_new_variable("str","export","Export entry","/e_dir",&$log_stack);
                            $gc2[$new_conf_name]->add_new_variable("str","import","Import entry","/i_dir",&$log_stack);
                        }
                    } else {
                        $log_stack->add_message("cannot add new config named '$new_conf_name', pri $new_conf_pri","SQL error",1);
                    }
                }
            }
        } else if (strtolower($dtype) == "cg_network") {
            $all_net_ids=array();
            foreach ($networks as $idx=>$n_stuff) $all_net_ids[]=$n_stuff->identifier;
            foreach ($networks as $idx=>$n_stuff) {
                if (is_set("netidentifier_$idx",&$vars)) {
                    if (is_set("netdel_$idx",&$vars)) {
                        $log_stack->add_message("Deleted Network with identifier '$n_stuff->identifier'","ok",1);
                        unset($all_net_ids[array_search($n_stuff->identifier,$all_net_ids,FALSE)]);
                        query("DELETE FROM network WHERE network_idx=$idx");
                        unset($networks[$idx]);
                    } else {
                        $c_array=array();
                        $new_id=$vars["netidentifier_$idx"];
                        if ($new_id != $n_stuff->identifier) {
                            if (in_array($new_id,$all_net_ids)) {
                                $log_stack->add_message("Cannot change netidentifier from '$n_stuff->identifier' to '$new_id'","identifier already used",0);
                            } else {
                                $log_stack->add_message("Changed netidentifier from '$n_stuff->identifier' to '$new_id'","ok",1);
                                unset($all_net_ids[array_search($n_stuff->identifier,$all_net_ids,FALSE)]);
                                $all_net_ids[]=$new_id;
                                $networks[$idx]->identifier=$new_id;
                                $c_array["identifier"]="'".mysql_escape_string($new_id)."'";
                            }
                        }
                        if (is_set("netshort_{$idx}",&$vars) xor $n_stuff->short_names) {
                            $networks[$idx]->short_names=1-$n_stuff->short_names;
                            $c_array["short_names"]=1-$n_stuff->short_names;
                        }
                        if (is_set("netwbc_{$idx}",&$vars) xor $n_stuff->write_bind_config) {
                            $networks[$idx]->write_bind_config=1-$n_stuff->write_bind_config;
                            $c_array["write_bind_config"]=1-$n_stuff->write_bind_config;
                        }
                        if (is_set("netwonc_{$idx}",&$vars) xor $n_stuff->write_other_network_config) {
                            $networks[$idx]->write_other_network_config=1-$n_stuff->write_other_network_config;
                            $c_array["write_other_network_config"]=1-$n_stuff->write_other_network_config;
                        }
                        foreach (array("Postfix"=>array("postfix","postfix","s"),
                                       "Name"=>array("name","name","s"),
                                       "Info"=>array("info","info","s"),
                                       "Penalty"=>array("penalty","penalty","i"),
                                       "Gateway Priority"=>array("gw_pri","gwpri","i"),
                                       "Network Type"=>array("network_type","type","i"),
                                       "Master network"=>array("master_network","master","i"),
                                       "Network"=>array("network","network","n"),
                                       "Gateway"=>array("gateway","gateway","n"),
                                       "Broadcast"=>array("broadcast","broadcast","n"),
                                       "Netmask"=>array("netmask","netmask","n")) as $info_str=>$stuff) {
                            list($sql_name,$http_name,$sql_type)=$stuff;
                            $new_v=trim($vars["net{$http_name}_{$idx}"]);
                            if ($new_v != $n_stuff->$sql_name) {
                                $nv_str=0;
                                if ($sql_type=="s") {
                                    $c_array[$sql_name]="'".mysql_escape_string($new_v)."'";
                                } else if ($sql_type == "n") {
                                    if (is_ip($new_v)) {
                                        $c_array[$sql_name]="'".mysql_escape_string($new_v)."'";
                                    } else {
                                        $nv_str="not a valid IPV4-String";
                                    }
                                } else {
                                    if (strval(intval($new_v)) == $new_v) {
                                        $c_array[$sql_name]=$new_v;
                                    } else {
                                        $nv_str="not an integer";
                                    }
                                }
                                if ($nv_str) {
                                    $log_stack->add_message("Cannot change $info_str to '$new_v' for $n_stuff->identifier",$nv_str,0);
                                } else {
                                    $log_stack->add_message("Changed $info_str from '{$n_stuff->$sql_name}' to '$new_v'","ok",1);
                                    $networks[$idx]->$sql_name=$new_v;
                                }
                                //echo "$sql_name<br>";
                            }
                        }
                        if ($c_array) {
                            $sql_array=array();
                            foreach ($c_array as $vn=>$vv) $sql_array[]="$vn=$vv";
                            $sql_str=implode(",",$sql_array);
                            $up=update_table("network","$sql_str WHERE network_idx=$idx");
                        }
                    }
                }
            }
            if (is_set("netidentifier_new",&$vars)) {
                $new_id=$vars["netidentifier_new"];
                if (in_array($new_id,$all_net_ids)) {
                    $log_stack->add_message("Cannot add network with netidentifier '$new_id'","identifier already used",0);
                } else {
                    $c_array["identifier"]="'".mysql_escape_string($new_id)."'";
                    $all_net_ids[]=$new_id;
                    $all_ok=1;
                    if (is_set("netshort_new",&$vars)) $c_array["short_names"]=1;
                    if (is_set("netwbc_new",&$vars)) {
			$c_array["write_bind_config"]=1;
		    } else {
			$c_array["write_bind_config"]=0;
		    }
                    if (is_set("netwonc_new",&$vars)) {
			$c_array["write_other_network_config"]=1;
		    } else {
			$c_array["write_other_network_config"]=0;
		    }
                    foreach (array("Postfix"=>array("postfix","postfix","s"),
                                   "Name"=>array("name","name","s"),
                                   "Info"=>array("info","info","s"),
                                   "Penalty"=>array("penalty","penalty","i"),
                                   "Gateway Priority"=>array("gw_pri","gwpri","i"),
                                   "Network Type"=>array("network_type","type","i"),
                                   "Master network"=>array("master_network","master","i"),
                                   "Network"=>array("network","network","n"),
                                   "Gateway"=>array("gateway","gateway","n"),
                                   "Broadcast"=>array("broadcast","broadcast","n"),
                                   "Netmask"=>array("netmask","netmask","n")) as $info_str=>$stuff) {
                        list($sql_name,$http_name,$sql_type)=$stuff;
                        $new_v=trim($vars["net{$http_name}_new"]);
                        $nv_str=0;
                        if ($sql_type=="s") {
                            $c_array[$sql_name]="'".mysql_escape_string($new_v)."'";
                        } else if ($sql_type == "n") {
                            if (is_ip($new_v)) {
                                $c_array[$sql_name]="'".mysql_escape_string($new_v)."'";
                            } else {
                                $nv_str="not a valid IPV4-String";
                            }
                        } else {
                            if (strval(intval($new_v)) == $new_v) {
                                $c_array[$sql_name]=$new_v;
                            } else {
                                $nv_str="not an integer";
                            }
                        }
                        if ($nv_str) {
                            $log_stack->add_message("Cannot set $info_str to '$new_v' for $new_id",$nv_str,0);
                            $all_ok=0;
                        } else {
                            $log_stack->add_message("Set $info_str for new_net to '$new_v'","ok",1);
                        }
                    }
                    if ($all_ok) {
                        $sql_array=array();
                        foreach ($c_array as $vn=>$vv) $sql_array[]="$vn=$vv";
                        $sql_str=implode(",",$sql_array);
                        $up=insert_table_set("network","$sql_str");
                        if ($up) {
                            $log_stack->add_message("Added new network","ok",1);
                            $networks=get_networks();
                        } else {
                            $log_stack->add_message("Cannot add new network","SQL-Error",1);
                        }
                    }
                }
            }
        } else if (strtolower($dtype)=="cg_snmp") {
            // check for mib to delete
            foreach ($all_snmp_mibs as $idx=>$stuff) {
                if (is_set("delmib_$idx",&$vars)) {
                    $log_stack->add_message("Deleted MIB name $stuff->name","ok",1);
                    unset($all_snmp_mibs[$idx]);
                    query("DELETE FROM snmp_mib WHERE snmp_mib_idx=$idx");
                }
            }
            // check for new mib
            $all_snmp_names=array();
            foreach($all_snmp_mibs as $idx=>$stuff) $all_snmp_names[]=$stuff->name;
            if (is_set("newmib",&$vars)) {
                if (is_set("newmibname",&$vars) && is_set("newmibmib",&$vars)) {
                    $mib_name=$vars["newmibname"];
                    if (in_array($mib_name,$all_snmp_names)) {
                        $log_stack->add_message("cannot add new SNMP-MIB '$mib_name'","duplicate name",0);
                    } else {
                        $mib_descr=$vars["newmibdescr"];
                        $mib_mib=$vars["newmibmib"];
                        $mib_key=$vars["newmibkey"];
                        if (is_set("newmibbase",&$vars)) {
                            $mib_base=min(1,abs(intval($vars["newmibbase"])));
                        } else {
                            $mib_base=1;
                        }
                        if (is_set("newmibfactor",&$vars)) {
                            $mib_factor=$vars["newmibfactor"];
                        } else {
                            $mib_factor=1.;
                        }
                        if (!$mib_factor) $mib_factor=1.;
                        $mib_vartype=$vars["newmibvart"];
                        $mib_unit=$vars["newmibunit"];
                        $ins_idx=insert_table("snmp_mib","0,'".mysql_escape_string($mib_name)."','".mysql_escape_string($mib_descr)."','".
                                              mysql_escape_string($mib_mib)."','".mysql_escape_string($mib_key)."','".mysql_escape_string($mib_unit).
                                              "',$mib_base,$mib_factor,'$mib_vartype',null");
                        $log_stack->add_message("Added new MIB named '$mib_name' (MIB $mib_mib)","ok",1);
                    }
                } else {
                    $log_stack->add_message("Cannot add new MIB","empty name and/or MIB",0);
                }
            }
            $all_snmp_mibs=get_all_snmp_mibs();
        } else if (strtolower($dtype)=="cg_nagios") {
            $time_array=array("mon"=>"Monday","tue"=>"Tuesday","wed"=>"Wednesday","thu"=>"Thursday","fri"=>"Friday","sat"=>"Saturday","sun"=>"Sunday");
            $hno_array=array("d"=>"Down","u"=>"Unreachable","r"=>"Recovery");
            $sno_array=array("w"=>"Warning","u"=>"Unknown","c"=>"Critical","r"=>"Recovery");
            $interval_f=array(0=>"never");
            for ($i=1;$i < 10; $i++) $interval_f[$i]=get_plural("min",$i,1);
            for ($i=10;$i < 61; $i+=5) $interval_f[$i]=get_plural("min",$i,1);
            $max_attempts_f=array();
            for ($i=1;$i < 10; $i++) $max_attempts_f[$i]=get_plural("time",$i,1);
            for ($i=10;$i < 61; $i+=5) $max_attempts_f[$i]=get_plural("time",$i,1);
            $nag_periods=get_nag_time_periods();
            $nag_contacts=get_nag_contacts();
            $nag_contact_groups=get_nag_contact_groups();
            $nag_service_templates=get_nag_service_templates();
            $nag_services=get_nag_services();
            $nag_device_templates=get_nag_device_templates();
            // create connection between contactgroups and contacts
            $mres=query("SELECT * FROM ng_ccgroup");
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->ng_contact,array_keys($nag_contacts)) && in_array($mfr->ng_contactgroup,array_keys($nag_contact_groups))) {
                    $nag_contacts[$mfr->ng_contact]->groups[]=$mfr->ng_contactgroup;
                    $nag_contact_groups[$mfr->ng_contactgroup]->contacts[]=$mfr->ng_contact;
                } else {
                    query("DELETE FROM ng_ccgroup WHERE ng_ccgroup_idx=$mfr->ng_ccgroup_idx");
                    $log_stack->add_message("deleted stale contact-contact_group connection","ok",1);
                }
            }
            // create connection between contactgroups and service_templates
            $mres=query("SELECT * FROM ng_cgservicet");
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->ng_contactgroup,array_keys($nag_contact_groups)) && in_array($mfr->ng_service_templ,array_keys($nag_service_templates))) {
                    $nag_service_templates[$mfr->ng_service_templ]->groups[]=$mfr->ng_contactgroup;
                    $nag_contact_groups[$mfr->ng_contactgroup]->service_templates[]=$mfr->ng_service_templ;
                } else {
                    query("DELETE FROM ng_cgservicet WHERE ng_cgservicet_idx=$mfr->ng_cgservicet_idx");
                    $log_stack->add_message("deleted stale contact_group-service_template connection","ok",1);
                }
            }
            // create connection between contacgroups and devices
            $mres=query("SELECT * FROM ng_device_contact");
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->ng_contactgroup,array_keys($nag_contact_groups)) && in_array($mfr->device_group,array_keys($dev_groups))) {
                    $nag_contact_groups[$mfr->ng_contactgroup]->devgroups[]=$mfr->device_group;
                } else {
                    query("DELETE FROM ng_device_contact WHERE ng_device_contact_idx=$mfr->ng_device_contact_idx");
                    $log_stack->add_message("deleted stale contact_group-device_group connection","ok",1);
                }
            }
            foreach ($nag_periods as $idx=>$stuff) {
                if (is_set("nagtimedel_$idx",&$vars)) {
                    query("DELETE FROM ng_period WHERE ng_period_idx=$idx");
                    $log_stack->add_message("deleted nagios time_period named '$stuff->name'","ok",1);
                    unset($nag_periods[$idx]);
                }
            }
            if (is_set("nagtimenew",&$vars)) {
                $new_ntp_name=trim($vars["nag_tpn_name"]);
                if ($new_ntp_name) {
                    $all_ok=1;
                    $time_set_array=array();
                    foreach ($time_array as $short=>$long) {
                        $act_tv=trim($vars["nag_tpn_$short"]);
                        if (!preg_match("/^(\d+):(\d+)-(\d+):(\d+)$/",$act_tv,$sp)) {
                            $log_stack->add_message("cannot parse time for $long ($act_tv)","parse error",0);
                            $all_ok=0;
                        } else {
                            $time_set_array[]="'$act_tv'";
                        }
                    }
                    if ($all_ok) {
                        $ins_ok=query("INSERT INTO ng_period VALUES(0,'".mysql_escape_string($new_ntp_name).
                                      "','".mysql_escape_string(trim($vars["nag_tpn_alias"])).
                                      "',".implode(",",$time_set_array).",null)");
                        if ($ins_ok) {
                            $log_stack->add_message("added nagios time_period named '$new_ntp_name'","ok",1);
                            $nag_periods=get_nag_time_periods();
                        } else {
                            $log_stack->add_message("cannot add nagios time_period named '$new_ntp_name'","SQL-error",0);
                        }
                    }
                } else {
                    $log_stack->add_message("cannot add new nagios time period: empty name","empty name",0);
                }
            }
            foreach ($nag_contact_groups as $idx=>$stuff) {
                if (is_set("nag_cong_del_$idx",&$vars)) {
                    unset($nag_contact_groups[$idx]);
                    query("DELETE FROM ng_contactgroup WHERE ng_contactgroup_idx=$idx");
                    $log_stack->add_message("deleted nagios contact_group named 'stuff->name'","ok",1);
                } else {
                    if (is_set("nag_cong_dummy_$idx",&$vars)) {
                        $new_alias=trim($vars["nag_cong_alias_$idx"]);
                        if ($new_alias != $stuff->alias) {
                            query("UPDATE ng_contactgroup SET alias='".mysql_escape_string($new_alias)."' WHERE ng_contactgroup_idx=$idx");
                            $nag_contact_groups[$idx]->alias=$new_alias;
                        }
                        if (is_set("nag_cong_mem_$idx",&$vars)) {
                            $new_members=$vars["nag_cong_mem_$idx"];
                        } else {
                            $new_members=array();
                        }
                        $act_members=$stuff->contacts;
                        foreach ($act_members as $act_member) {
                            if (!in_array($act_member,$new_members)) query("DELETE FROM ng_ccgroup WHERE ng_contact=$act_member AND ng_contactgroup=$idx");
                        }
                        foreach ($new_members as $new_member) {
                            if (!in_array($new_member,$act_members)) query("INSERT INTO ng_ccgroup VALUES(0,$new_member,$idx,null)");
                        }
                        if (is_set("nag_cong_devg_$idx",&$vars)) {
                            $new_devgroups=$vars["nag_cong_devg_$idx"];
                        } else {
                            $new_devgroups=array();
                        }
                        $act_devgroups=$stuff->devgroups;
                        foreach ($act_devgroups as $act_devg) {
                            if (!in_array($act_devg,$new_devgroups)) query("DELETE FROM ng_device_contact WHERE device_group=$act_devg AND ng_contactgroup=$idx");
                        }
                        foreach ($new_devgroups as $new_devg) {
                            if (!in_array($new_devg,$act_devgroups)) query("INSERT INTO ng_device_contact VALUES(0,$new_devg,$idx,null)");
                        }
                        if (is_set("nag_cong_servt_$idx",&$vars)) {
                            $new_servtemps=$vars["nag_cong_servt_$idx"];
                        } else {
                            $new_servtemps=array();
                        }
                        $act_service_templates=$stuff->service_templates;
                        foreach ($act_service_templates as $act_servt) {
                            if (!in_array($act_servt,$new_servtemps)) query("DELETE FROM ng_cgservicet WHERE ng_service_templ=$act_servt AND ng_contactgroup=$idx");
                        }
                        foreach($new_servtemps as $new_servt) {
                            if (!in_array($new_servt,$act_service_templates)) query("INSERT INTO ng_cgservicet VALUES(0,$idx,$new_servt,null)");
                        }
                    }
                }
            }
            if (is_set("nagnewcong",&$vars)) {
                $newnagcg_name=trim($vars["newcongname"]);
                $newnagcg_alias=trim($vars["newcongalias"]);
                if ($newnagcg_name) {
                    $ins=insert_table("ng_contactgroup","0,'".mysql_escape_string($newnagcg_name)."','".mysql_escape_string($newnagcg_alias)."',null");
                    if ($ins) {
                        $log_stack->add_message("added new contactgroup named '$newnagcg_name'","ok",1);
                        $nag_contact_groups=get_nag_contact_groups();
                        // create contact connections
                        if (is_set("nag_cong_mem_new",&$vars)) {
                            foreach ($vars["nag_cong_mem_new"] as $c_idx) query("INSERT INTO ng_ccgroup VALUES(0,$c_idx,$ins,null)");
                        }
                        // create device connections
                        if (is_set("nag_cong_devg_new",&$vars)) {
                            foreach ($vars["nag_cong_devg_new"] as $c_idx) query("INSERT INTO ng_device_contact VALUES(0,$c_idx,$ins,null)");
                        }
                        // create service_templates connections
                        if (is_set("nag_cong_servt_new",&$vars)) {
                            foreach ($vars["nag_cong_servt_new"] as $s_idx) query("INSERT INTO ng_cgservicet VALUES(0,$ins,$s_idx,null)");
                        }
                    } else {
                        $log_stack->add_message("cannot add contactgroup named '$newnagcg_name'","SQL-error",0);
                    }
                } else {
                    $log_stack->add_message("empty contact_group name","error",0);
                }
            }
                    
            foreach ($nag_contacts as $idx=>$stuff) {
                if (is_set("nag_con_del_$idx",&$vars)) {
                    unset($nag_contacts[$idx]);
                    query("DELETE FROM ng_contact WHERE ng_contact_idx=$idx");
                    $log_stack->add_message("deleted nagios contact named 'XXXXXX'","ok",1);
                } else {
                    if (is_set("nag_con_hnp_$idx",&$vars)) {
                        $c_array=array();
                        if ($vars["nag_con_hnp_$idx"] != $stuff->hnperiod) {
                            $c_array[]="hnperiod=".strval($vars["nag_con_hnp_$idx"]);
                            $nag_contacts[$idx]->hnperiod=$vars["nag_con_hnp_$idx"];
                        }
                        if ($vars["nag_con_snp_$idx"] != $stuff->snperiod) {
                            $c_array[]="snperiod=".strval($vars["nag_con_snp_$idx"]);
                            $nag_contacts[$idx]->snperiod=$vars["nag_con_snp_$idx"];
                        }
                        foreach ($hno_array as $short=>$long) {
                            $var_n="hn".strtolower($long);
                            if (is_set("nag_con_hno_{$short}_{$idx}",&$vars) xor $stuff->$var_n) {
                                $c_array[]="$var_n=".strval(1-$stuff->$var_n);
                                $nag_contacts[$idx]->$var_n=1-$stuff->$var_n;
                            }
                        }
                        foreach ($sno_array as $short=>$long) {
                            $var_n="sn".strtolower($long);
                            if (is_set("nag_con_sno_{$short}_{$idx}",&$vars) xor $stuff->$var_n) {
                                $c_array[]="$var_n=".strval(1-$stuff->$var_n);
                                $nag_contacts[$idx]->$var_n=1-$stuff->$var_n;
                            }
                        }
                        if (count($c_array)) {
                            $up=update_table("ng_contact",implode(",",$c_array)." WHERE ng_contact_idx=$idx");
                            if ($up) {
                                $log_stack->add_message("modified nagios contact named 'XXXXXX'","ok",1);
                            } else {
                                $log_stack->add_message("cannot modify nagios contact named 'XXXXXX'","SQL Error",0);
                            }
                        }
                    }
                }
            }
            if (is_set("nagnewcontact",&$vars)) {
                $sn_options=array();
                foreach (array("r","c","w","u") as $sn_opt) {
                    if (is_set("nag_con_sno_$sn_opt",&$vars)) {
                        $sn_options[]="1";
                    } else {
                        $sn_options[]="0";
                    }
                }
                $hn_options=array();
                foreach (array("r","d","u") as $hn_opt) {
                    if (is_set("nag_con_hno_$hn_opt",&$vars)) {
                        $hn_options[]="1";
                    } else {
                        $hn_options[]="0";
                    }
                }
                $ins_ok=query("INSERT INTO ng_contact VALUES(0,{$vars['nag_con_name']},{$vars['nag_con_hnp']},{$vars['nag_con_snp']},".implode(",",$sn_options).",".implode(",",$hn_options).",'notify-by-email','host-notify-by-email',null)");
                if ($ins_ok) {
                    $log_stack->add_message("added nagios_contact name 'XXXX'","ok",1);
                    $nag_contacts=get_nag_contacts();
                } else {
                    $log_stack->add_message("cannot add nagios_contact name 'XXXX'","SQL-error",0);
                }
            }
            // create connection between contactgroups and contacts
            $mres=query("SELECT * FROM ng_ccgroup");
            foreach ($nag_contacts as $idx=>$stuff) $nag_contacts[$idx]->groups=array();
            foreach ($nag_contact_groups as $idx=>$stuff) {
                $nag_contact_groups[$idx]->contacts=array();
                $nag_contact_groups[$idx]->devgroups=array();
                $nag_contact_groups[$idx]->service_templates=array();
            }
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->ng_contact,array_keys($nag_contacts)) && in_array($mfr->ng_contactgroup,array_keys($nag_contact_groups))) {
                    $nag_contacts[$mfr->ng_contact]->groups[]=$mfr->ng_contactgroup;
                    $nag_contact_groups[$mfr->ng_contactgroup]->contacts[]=$mfr->ng_contact;
                } else {
                    query("DELETE FROM ng_ccgroup WHERE ng_ccgroup_idx=$mfr->ng_ccgroup_idx");
                    $log_stack->add_message("deleted stale contact-contact_group connection","ok",1);
                }
            }
            // create connection between contactgroups and service_templates
            $mres=query("SELECT * FROM ng_cgservicet");
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->ng_contactgroup,array_keys($nag_contact_groups)) && in_array($mfr->ng_service_templ,array_keys($nag_service_templates))) {
                    $nag_service_templates[$mfr->ng_service_templ]->groups[]=$mfr->ng_contactgroup;
                    $nag_contact_groups[$mfr->ng_contactgroup]->service_templates[]=$mfr->ng_service_templ;
                } else {
                    query("DELETE FROM ng_cgservicet WHERE ng_cgservicet_idx=$mfr->ng_cgservicet_idx");
                    $log_stack->add_message("deleted stale contact_group-service_template connection","ok",1);
                }
            }
            // create connection between contacgroups and devices
            $mres=query("SELECT * FROM ng_device_contact");
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->ng_contactgroup,array_keys($nag_contact_groups)) && in_array($mfr->device_group,array_keys($dev_groups))) {
                    $nag_contact_groups[$mfr->ng_contactgroup]->devgroups[]=$mfr->device_group;
                } else {
                    query("DELETE FROM ng_device_contact WHERE ng_device_contact_idx=$mfr->ng_device_contact_idx");
                    $log_stack->add_message("deleted stale contact_group-device_group connection","ok",1);
                }
            }
            foreach ($nag_service_templates as $idx=>$stuff) {
                if ($idx) {
                    if (is_set("nag_st_del_$idx",&$vars)) {
                        query("DELETE FROM ng_service_templ WHERE ng_service_templ_idx=$idx");
                        $log_stack->add_message("deleted Nagios service_template named '$stuff->name'","ok",1);
                        unset($nag_service_templates[$idx]);
                    } else if (is_set("nag_st_$idx",&$vars)) {
                        $sql_c_array=array();
                        // check for integers
                        foreach (array("ma"=>"max_attempts","nscp"=>"nsc_period","nsnp"=>"nsn_period",
                                       "ci"=>"check_interval","ri"=>"retry_interval","ni"=>"ninterval") as $short=>$long) {
                            $vn="nag_st_{$short}_{$idx}";
                            if ($vars[$vn] != $stuff->$long) {
                                $sql_c_array[]="$long={$vars[$vn]}";
                                $nag_service_templates[$idx]->$long=$vars[$vn];
                            }
                        }
                        // check for flags
                        foreach (array("vol"=>"volatile","nr"=>"nrecovery","nc"=>"ncritical","nw"=>"nwarning","nu"=>"nunknown") as $short=>$long) {
                            $flag=is_set("nag_st_{$short}_{$idx}",&$vars);
                            if ($flag != $stuff->$long) {
                                $sql_c_array[]="$long=$flag";
                                $nag_service_templates[$idx]->$long=$flag;
                            }
                        }
                        if (count($sql_c_array)) {
                            $sql_str=implode(",",$sql_c_array);
                            update_table("ng_service_templ","$sql_str WHERE ng_service_templ_idx=$idx");
                        }
                    }
                }
            }
            if (is_set("nagnewservtemp",&$vars)) {
                $newservname=trim($vars["nagnewservtempname"]);
                if ($newservname) {
                    $sql_str="'$newservname',".is_set("nagnewservtemp_vol",&$vars);
                    foreach (array("nscp","ma","ci","ri","ni","nsnp") as $cv) {
                        $sql_str.=",".$vars["nagnewservtemp_$cv"];
                    }
                    foreach (array("r","c","w","u") as $cv) {
                        $sql_str.=",".is_set("nagnewservtemp_n$cv",&$vars);
                    }
                    $ins=insert_table("ng_service_templ","0,$sql_str,null");
                    if ($ins) {
                        $log_stack->add_message("added new service template named '$newservname'","ok",1);
                        $nag_service_templates=get_nag_service_templates();
                    } else {
                        $log_stack->add_message("cannot add new service template named '$newservname'","SQL Error",1);
                    }
                } else {
                    $log_stack->add_message("cannot add new Serivce template","empty name",0);
                }
            }
            foreach ($nag_device_templates as $idx=>$stuff) {
                if (is_set("nag_dt_del_$idx",&$vars)) {
                    query("DELETE FROM ng_device_templ WHERE ng_device_templ_idx=$idx");
                    $log_stack->add_message("deleted Nagios Device_template named '$stuff->name'","ok",1);
                    unset($nag_device_templates[$idx]);
                } else if (is_set("nag_dt_$idx",&$vars)) {
                    $sql_c_array=array();
                    foreach (array("ma"=>"max_attempts","st"=>"ng_service_templ",
                                   "ni"=>"ninterval","nsnp"=>"ng_period") as $short=>$long) {
                        $vn="nag_dt_{$short}_{$idx}";
                        if ($vars[$vn] != $stuff->$long) {
                            $sql_c_array[]="$long={$vars[$vn]}";
                            $nag_device_templates[$idx]->$long=$vars[$vn];
                        }
                    }
                    // check for flags
                    foreach (array("nr"=>"nrecovery","nd"=>"ndown","nu"=>"nunreachable") as $short=>$long) {
                        $flag=is_set("nag_dt_{$short}_{$idx}",&$vars);
                        if ($flag != $stuff->$long) {
                            $sql_c_array[]="$long=$flag";
                            $nag_device_templates[$idx]->$long=$flag;
                        }
                    }
                    if (count($sql_c_array)) {
                        $sql_str=implode(",",$sql_c_array);
                        update_table("ng_device_templ","$sql_str WHERE ng_device_templ_idx=$idx");
                    }
                }
            }
            if (is_set("nag_devtemp_def",&$vars)) {
                $nag_dt_default_idx=$vars["nag_devtemp_def"];
                if (is_set("nagnewdevtemp",&$vars)) {
                    $newdevname=trim($vars["nagnewdevtempname"]);
                    if ($newdevname) {
                        $sql_str="'".mysql_escape_string($newdevname)."',{$vars['nagnewdevst']},'check-host-alive'";
                        foreach (array("ma","ni","nsnp") as $cv) {
                            $sql_str.=",".$vars["nagnewdevtemp_$cv"];
                        }
                        foreach (array("r","d","u") as $cv) {
                            $sql_str.=",".is_set("nagnewdevtemp_n$cv",&$vars);
                        }
                        if ($nag_dt_default_idx == "new") {
                            $new_is_default=1;
                        } else {
                            $new_is_default=0;
                        }
                        $ins=insert_table("ng_device_templ","0,$sql_str,$new_is_default,null");
                        if ($ins) {
                            $log_stack->add_message("added new device template named '$newdevname'","ok",1);
                            $nag_device_templates=get_nag_device_templates();
                            if ($new_is_default) $nag_dt_default_idx=$ins;
                        } else {
                            $log_stack->add_message("cannot add new device template named '$newdevname'","SQL Error",1);
                        }
                    } else {
                        $log_stack->add_message("cannot add new Device template","empty name",0);
                    }
                }
                // check for radio-button
                if ($nag_dt_default_idx!="new") {
                    foreach ($nag_device_templates as $idx=>$stuff) {
                        // check for default-radio
                        $act_is_default=0;
                        if ($nag_dt_default_idx == $idx) $act_is_default=1;
                        if ($act_is_default != $stuff->is_default) {
                            $nag_device_templates[$idx]->is_default=$act_is_default;
                            update_table("ng_device_templ","is_default=$act_is_default WHERE ng_device_templ_idx=$idx");
                        }
                    }
                }
                // check for (possibly deleted ng_device_templ); skip first template (is none)
                if (count($nag_device_templates) > 1) {
                    $act_default_idx=0;
                    foreach ($nag_device_templates as $idx=>$stuff) {
                        if ($stuff->is_default) $act_default_idx=$idx;
                    }
                    if (!$act_default_idx) {
                        $nag_device_templates[$idx]->is_default=1;
                        update_table("ng_device_templ","is_default=1 WHERE ng_device_templ_idx=$idx");
                    }
                }
            }
        }
        if ($create_conf) {
            $mres=query("SELECT d.bootserver,d.name FROM device d WHERE 1 $optsel");
            $tk_r_array=array();
            while ($mfr=mysql_fetch_object($mres)) {
                if ($mfr->bootserver) {
                    $bs_name=$boot_server[$mfr->bootserver];
                    if (!in_array($bs_name,array_keys($tk_r_array))) $tk_r_array[$bs_name]=array();
                    $tk_r_array[$bs_name][]=$mfr->name;
                }
            }
            foreach ($tk_r_array as $server=>$nodes) {
                if (count($nodes)) {
                    $serv_result=contact_server($sys_config,"config_server",8005,"create_config ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    $log_stack->add_message("create config on $server",$serv_result,preg_match("/^ok.*$/",$serv_result));
                }
            }
        }
        if (!preg_match("/^cg_.*$/",$dtype)) {
            // the big array
            $big_array=array("Location"        =>array("s","hloc","device_location",$device_locations),
                             "Class"           =>array("s","hcl","device_class",$device_classes),
                             "AX-Number"       =>array("t","axn","axnumber",0),
                             "Nagios device"   =>array("s","ngd","ng_device_templ",$nag_device_templates),
                             "Nagios picture"  =>array("s","nge","ng_ext_host",$nag_ext_hosts),
                             "bz2 capable"     =>array("T","bz2","bz2_capable",0),
                             "Partition"       =>array("s","pt","partition_table",$partition_tables),
                             "Partition prefix"=>array("t","ptp","partdev",0),
                             "fixed prefix"    =>array("T","fptp","fixed_partdev",0)
                             //"X-Coord (2d)" =>array("r","x2d","x_2d",0),
                             //"Y-Coord (2d)" =>array("r","y2d","y_2d",0),
                             //"bla2"         =>array("n","","",0),
                             //"X-Coord (3d)" =>array("r","x3d","x_3d",0),
                             //"Y-Coord (3d)" =>array("r","y3d","y_3d",0),
                             //"Z-Coord (3d)" =>array("r","z3d","z_3d",0),
                             //"Theta"        =>array("r","theta","theta",0),
                             //"Phi"          =>array("r","phi","phi",0),
                             //"Device shape" =>array("s","dsh","device_shape",$ds_shapes)
                             );
            $sel_array=array();
            foreach ($big_array as $key=>$val) {
                list($stype,$b1,$field,$stuff)=$val;
                if ($field) $sel_array[]="d.$field";
            }
            $machs=array();
            $mres=query("SELECT d.name,d.device_idx,".implode(",",$sel_array).",dt.identifier,d.bootnetdevice,d.bootserver FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx $optsel ORDER BY d.name",$sys_db_con);
            while ($mfr=mysql_fetch_object($mres)) {
                $mfr->ms_outlets=array();
                $mfr->dev_config=array();
                $machs[$mfr->name]=$mfr;
            }
            if ($dtype == "cm_loc") {
                $mres=query("SELECT m.*,d.name FROM msoutlet m, device d WHERE m.slave_device=d.device_idx $optsel");
                while ($mfr=mysql_fetch_object($mres)) $machs[$mfr->name]->ms_outlets[]=$mfr;
            }
            if (preg_match("/^cm_id_(.*)$/",$dtype,$id_match)) {
                $mfr->dev_config=array();
                $mres=query("SELECT dc.deviceconfig_idx,dc.config,d.name FROM deviceconfig dc,config c,device d,config_type ct WHERE ct.config_type_idx=c.config_type AND dc.device=d.device_idx AND ct.identifier='{$id_match[1]}' AND dc.config=c.config_idx $optsel");
                while ($mfr=mysql_fetch_object($mres)) $machs[$mfr->name]->dev_config[$mfr->deviceconfig_idx]=$mfr->config;
            } else if (preg_match("/^cm_idds_(.*)$/",$dtype,$id_match)) {
                $mfr->dev_config=array();
                $mres=query("SELECT d.device_idx,d.name as dname, c.name,c.descr,c.config_type,c.priority,c.config_idx FROM config c, deviceconfig dc, config_type ct, device d WHERE ct.config_type_idx=c.config_type AND ct.identifier='{$id_match[1]}' AND dc.config=c.config_idx AND dc.device=d.device_idx $optsel ORDER BY c.config_type,c.priority");
                while ($mfr=mysql_fetch_object($mres)) {
                    $machs[$mfr->dname]->dev_config[$mfr->name]=new config($mfr->name,$mfr->descr,$mfr->config_type,$mfr->priority,$mfr->config_idx,$mfr->device_idx);
                    $machs[$mfr->dname]->dev_config[$mfr->name]->set_prefix("cd{$mfr->device_idx}");
                    $machs[$mfr->dname]->dev_config[$mfr->name]->set_add_str(", device $mfr->dname");
                }
                
                foreach (array(array("str","cs"),array("int","ci"),array("blob","cb")) as $stuff) {
                    list($long,$short)=$stuff;
                    $mres=query("SELECT d.name as dname, {$short}.name,{$short}.descr,{$short}.value,{$short}.config,{$short}.config_{$long}_idx as idx, c.name as cname, c.config_idx FROM config c,config_type ct, config_$long $short, deviceconfig dc, device d WHERE c.config_type=ct.config_type_idx AND {$short}.config=c.config_idx AND {$short}.device=d.device_idx $optsel");
                    while ($mfr=mysql_fetch_object($mres)) {
                        $machs[$mfr->dname]->dev_config[$mfr->cname]->add_variable($long,$mfr->name,$mfr->descr,$mfr->value,$mfr->idx);
                        //$machs[$mfr->dname]->dev_config[$mfr->cname]["{$long}s"][$mfr->name]=$mfr;
                    }
                }
                // nagios stuff
                $mres=query("SELECT d.name as dname, c.name as cname, n.* FROM ng_check_command n, config c, config_type ct, device d, deviceconfig dc WHERE ct.config_type_idx=c.config_type AND n.config=c.config_idx AND n.device=d.device_idx AND dc.device=d.device_idx AND dc.config=c.config_idx $optsel");
                while ($mfr=mysql_fetch_object($mres)) {
                    //$machs[$mfr->dname]->dev_config[$mfr->cname]["nagios"][$mfr->ng_check_command_idx]=$mfr;
                    $machs[$mfr->dname]->dev_config[$mfr->cname]->add_nagios($mfr->name,$mfr->description,$mfr->ng_check_command_idx,$mfr->ng_service_templ,$mfr->command_line);
                }
                // snmp stuff
                $mres=query("SELECT d.name as dname, c.name as cname, s.* FROM snmp_config s, config c, config_type ct, device d, deviceconfig dc WHERE ct.config_type_idx=c.config_type AND s.config=c.config_idx AND s.device=d.device_idx AND dc.device=d.device_idx AND dc.config=c.config_idx $optsel");
                while ($mfr=mysql_fetch_object($mres)) {
                    //$machs[$mfr->dname]->dev_config[$mfr->cname]["snmp"][$mfr->snmp_config_idx]=$mfr;
                    $machs[$mfr->dname]->dev_config[$mfr->cname]->add_snmp($mfr->snmp_mib,$mfr->snmp_config_idx);
                }
            }
            if ($dtype == "cm_net" && 0) {
                // check connectivity
                $mres=query("SELECT p.s_netdevice,p.d_netdevice FROM peer_information p");
                $peers=array();
                $peer_nds=array();
                while ($mfr=mysql_fetch_object($mres)) {
                    if (!in_array($mfr->s_netdevice,array_keys($peers))) $peers[$mfr->s_netdevice]=array();
                    if (!in_array($mfr->d_netdevice,array_keys($peers))) $peers[$mfr->d_netdevice]=array();
                    $peers[$mfr->s_netdevice][]=$mfr->d_netdevice;
                    $peers[$mfr->d_netdevice][]=$mfr->s_netdevice;
                }
                $mres=query("SELECT n.netdevice_idx,d.name,n.devname,n.routing FROM device d, netdevice n WHERE n.device=d.device_idx AND (n.netdevice_idx=".implode(" OR n.netdevice_idx=",array_keys($peers)).")");
                $peer_nds=array();
                while ($mfr=mysql_fetch_object($mres)) {
                    if ($mfr->devname == "lo") {
                        unset($peers[$mfr->netdevice_idx]);
                    } else {
                        $peer_nds[$mfr->netdevice_idx]=$mfr;
                    }
                }
                $peer_count=array();
                foreach ($peers as $source=>$dest) $peer_count[$source]=count($dest);
                $con_nums=array_unique(array_values($peer_count));
                rsort($con_nums);
                $num_circles=count($con_nums);
                if ($num_circles) {
                    asort($peer_count);
                    //                     foreach ($peer_count as $source=>$count) {
                    //                         echo "{$peer_nds[$source]->name} [{$peer_nds[$source]->devname}] : {$peer_count[$source]}<br>";
                    //                     }
                    $pi_v=pi();
                    $im_size=400;
                    $im = @ImageCreate ($im_size,$im_size);
                    $background_color = ImageColorAllocate ($im, 200, 255, 255);
                    $black=ImageColorAllocate($im,0,0,0);
                    $red=ImageColorAllocate($im,255,90,90);
                    $center=$im_size/2;
                    for ($idx=0;$idx<$num_circles;$idx++) {
                        $act_rad=((($im_size*0.9)/$num_circles)*($idx+1))/2;
                        ImageEllipse($im,$center,$center,$act_rad*2,$act_rad*2,$black);
                        $con_num=$con_nums[$idx];
                        // get number of devices with this connection number
                        $loc_f=array();
                        foreach ($peer_count as $source=>$count) {
                            if ($count == $con_num) $loc_f[]=$source;
                        }
                        $num_d=count($loc_f);
                        for ($j=0;$j<$num_d;$j++) {
                            $act_angle=(float)($pi_v/($num_d))*(2*$j)+(float)($pi_v*$idx/$num_circles);
                            $x=$center+$act_rad*cos($act_angle);
                            $y=$center+$act_rad*sin($act_angle);
                            ImageFilledRectangle($im,$x-2,$y-2,$x+2,$y+2,$red);
                            $peer_nds[$loc_f[$j]]->x=$x;
                            $peer_nds[$loc_f[$j]]->y=$y;
                            //print_r($peer_nds[$loc_f[$j]]);
                        }
                    }
                    foreach ($peers as $source=>$targets) {
                        foreach($targets as $target) {
                            ImageLine($im,$peer_nds[$source]->x,$peer_nds[$source]->y,$peer_nds[$target]->x,$peer_nds[$target]->y,$red);
                        }
                    }
                    $png_name="/pics/test.png";
                    $picdir=get_root_dir().$png_name;
                    ImagePng ($im,$picdir);
                    echo "<img src=\"$png_name\" />";
                }
            }
            // bootserver
            $masterswitch_change=0;
            $nagios_config_change=0;
            $peer_information_change=0;
            unset($old_name);
            foreach ($machs as $name=>$mfr_ref) {
                $mfr=&$machs[$name];
                // network
                $refresh_tk=0;
                if ($dtype == "cm_net") {
                    $new_netdevice_idx=0;
                    $var_pf="{$name}_newnetdev";
                    if (is_set($var_pf,&$vars)) {
                        if (isset($old_name)) {
                            $log_stack->add_message("setting Network properties of device '$name' to properties of '$old_name'","ok",1);
                            $old_dev=&$machs[$old_name];
                            foreach ($old_dev->netdevices as $ndev_idx => $ndev_stuff) {
                                $old_nd_name=$ndev_stuff->devname;
                                if ($old_nd_name == "lo") {
                                    $incr="no";
                                } else {
                                    $incr="yes";
                                }
                                $log_stack->add_message("Copying netdevice $old_nd_name (IP-increase: $incr)","ok",1);
                                $ins_idx=insert_table_set("netdevice","device=$mfr->device_idx,devname='".mysql_escape_string($old_nd_name).
                                                          "',driver='".mysql_escape_string($ndev_stuff->driver)."',speed=$ndev_stuff->speed,routing=$ndev_stuff->routing,driver_options='".
                                                          mysql_escape_string($ndev_stuff->driver_options)."',dhcp_device=$ndev_stuff->dhcp_device,ethtool_options=$ndev_stuff->ethtool_options");
                                if ($ins_idx) {
                                    foreach ($ndev_stuff->netips as $nip_idx => $ip_stuff) {
                                        $nip=$ip_stuff->ip;
                                        $log_stack->add_message("Copying netip $nip (increase: $incr)","ok",1);
                                        $ins2_idx=insert_table_set("netip","ip='".increase_ip($nip,$incr=="yes")."',netdevice=$ins_idx,network=$ip_stuff->network");
                                    }
                                    // peer information
                                    if (in_array($ndev_idx,array_keys($peer_information))) {
                                        foreach ($peer_information[$ndev_idx] as $p_dest=>$p_stuff) {
                                            $peer_information_change=1;
                                            list($pne,$v0,$v1)=$p_stuff;
                                            if ($incr=="yes") {
                                                insert_table("peer_information","0,$ins_idx,$p_dest,$pne,null");
                                                $peer_information[$p_dest][$ins_idx]=array($pne,$old_nd_name,$name);
                                                $peer_information[$ins_idx][$p_dest]=array($pne,$all_routing_devices[$p_dest]->devname,$all_routing_devices[$p_dest]->name);
                                            } else {
                                                insert_table("peer_information","0,$ins_idx,$ins_idx,$pne,null");
                                                $peer_information[$ins_idx][$ins_idx]=array($pne,$old_nd_name,$name);
                                            }
                                        }
                                    }
                                } else {
                                    $log_stack->add_message("cannot add network-device '$old_nd_name' to device '$name'","SQL Error",0);
                                }
                            }
                        } else {
                            $log_stack->add_message("cannot set Network properties of device '$name'","no parent device found",0);
                        }
                    }
                    if (is_set("{$var_pf}_dn",&$vars)) {
                        $nnd_n=$vars["{$var_pf}_dn"];
                        if ($nnd_n != "eth") {
                            $nnd_a=$vars["{$var_pf}_al"];
                            $nnd_mac=$vars["{$var_pf}_mac"];
                            $nnd_fmac=$vars["{$var_pf}_fmac"];
                            $nnd_spd=$vars["{$var_pf}_spd"];
                            if (is_set("{$var_pf}_rt",$vars)) {
                                $nnd_rt=1;
                            } else {
                                $nnd_rt=0;
                            }
                            if (is_set("{$var_pf}_dhcp",&$vars)) {
                                $nnd_dhcp=1;
                            } else {
                                $nnd_dhcp=0;
                            }
                            $n_bo=($vars["{$var_pf}_no_n"] | ($vars["{$var_pf}_no_d"]<<2)|($vars["{$var_pf}_no_s"]<<4));
                            $nnd_opt=$vars["{$var_pf}_opt"];
                            if ($nnd_n && is_macaddr($nnd_mac) && is_netspeed($nnd_spd) && is_netdev_name($nnd_n) && is_macaddr($nnd_fmac)) {
                                $nnd_dr=$vars["{$var_pf}_dr"];
                                if ($nnd_n == "lo" && !$nnd_a) $nnd_a="localhost";
                                $ins_idx=insert_table_set("netdevice","device=$mfr->device_idx,devname='".mysql_escape_string($nnd_n).
                                                          "',macadr='".mysql_escape_string($nnd_mac).
                                                          "',driver='".mysql_escape_string($nnd_dr)."',speed=$nnd_spd,routing=$nnd_rt,driver_options='".mysql_escape_string($nnd_opt).
                                                          "',dhcp_device=$nnd_dhcp,ethtool_options=$n_bo,fake_macadr='".mysql_escape_string($nnd_fmac)."'");
                                $new_netdevice_idx=$ins_idx;
                                $refresh_tk=1;
                                if ($nnd_n == "lo") {
                                    $peer_information_change=1;
                                    $ins=insert_table("peer_information","0,$ins_idx,$ins_idx,1,null");
                                    $log_str="added netdevice '$nnd_n', macadr '$nnd_mac', driver '$nnd_dr' to device $name (and generated a peer_information entry)";
                                    $peer_information[$ins_idx][$ins_idx]=array(1,$nnd_n,$name);
                                } else {
                                    $log_str="added netdevice '$nnd_n', macadr '$nnd_mac', driver '$nnd_dr' to device $name";
                                    if ($nnd_fmac != "00:00:00:00:00:00") $log_str.=" (fake_macadr $nnd_fmac)";
                                }
                                $log_stack->add_message($log_str,"ok",1);
                            } else {
                                if (!is_macaddr($nnd_mac)) $log_stack->add_message("cannot add netdevice '$nnd_n' to device $name","parse macaddr",0);
                                if (!is_macaddr($nnd_fmac)) $log_stack->add_message("cannot add netdevice '$nnd_n' to device $name","parse fake_macaddr",0);
                                if (!is_netspeed($nnd_spd)) $log_stack->add_message("cannot add netdevice '$nnd_n' to device $name","parse netspeed",0);
                                if (!is_netdev_name($nnd_n)) $log_stack->add_message("cannot add netdevice '$nnd_n' to device $name","parse netdevname",0);
                            }
                        }
                    }
                    $mfr->netdevices=array();
                    $mres2=query("SELECT * FROM netdevice n WHERE n.device=$mfr->device_idx ORDER BY n.devname");
                    while ($mfr2=mysql_fetch_object($mres2)) {
                        $var_pf="{$name}_nd_{$mfr2->netdevice_idx}";
                        if (is_set("{$var_pf}_dummy",$vars) && !$vars["{$var_pf}_dn"]) {
                            query("DELETE FROM netip WHERE netdevice=$mfr2->netdevice_idx");
                            query("DELETE FROM netdevice WHERE netdevice_idx=$mfr2->netdevice_idx");
                            query("DELETE FROM peer_information WHERE s_netdevice=$mfr2->netdevice_idx OR d_netdevice=$mfr2->netdevice_idx");
                            $log_stack->add_message("deleted netdevice '{$mfr2->devname}' from device $name","ok",1);
                            $peer_information_change=1;
                            $refresh_tk=1;
                        } else {
                            if (is_set("{$var_pf}_dn",$vars)) {
                                $n_dn=$vars["{$var_pf}_dn"];
                                $n_spd=$vars["{$var_pf}_spd"];
                                if ($n_dn != "lo") {
                                    $n_dr=$vars["{$var_pf}_dr"];
                                    $n_mac=$vars["{$var_pf}_mac"];
                                    $n_fmac=$vars["{$var_pf}_fmac"];
                                    $n_opt=$vars["{$var_pf}_opt"];
                                    $n_bo=($vars["{$var_pf}_no_n"] | ($vars["{$var_pf}_no_d"]<<2)|($vars["{$var_pf}_no_s"]<<4));
                                } else {
                                    $n_dr=$mfr2->driver;
                                    $n_mac=$mfr2->macadr;
                                    $n_fmac=$mfr2->fake_macadr;
                                    $n_opt=$mfr2->driver_options;
                                    $n_bo=$mfr2->ethtool_options;
                                }
                                if (is_set("{$var_pf}_rt",$vars)) {
                                    $n_rt=1;
                                } else {
                                    $n_rt=0;
                                }
                                if (is_set("{$var_pf}_dhcp",&$vars)) {
                                    $n_dhcp=1;
                                } else {
                                    $n_dhcp=0;
                                }
                                if ($n_rt) {
                                    $n_rt=1;
                                } else {
                                    $n_rt=0;
                                }
                                //echo "*$n_dn*$n_al*$n_spd*$n_dr*$n_mac*<br>";
                                if ($n_dn && is_netspeed($n_spd) && is_netdev_name($n_dn) && is_macaddr($n_fmac) && is_macaddr($n_mac) &&
                                    ($n_dn != $mfr2->devname || $n_spd != $mfr2->speed || $n_dr != $mfr2->driver || $n_bo != $mfr2->ethtool_options ||
                                     $n_rt != $mfr2->routing || $n_opt != $mfr2->driver_options || $n_dhcp != $mfr2->dhcp_device) || $n_fmac != $mfr2->fake_macadr || $n_mac != $mfr2->macadr) {
                                    update_table("netdevice","devname='".mysql_escape_string($n_dn)."',speed=$n_spd,driver='".mysql_escape_string($n_dr)."',driver_options='".mysql_escape_string($n_opt).
                                                 "',routing=$n_rt,dhcp_device=$n_dhcp,ethtool_options=$n_bo,fake_macadr='".mysql_escape_string($n_fmac).
                                                 "',macadr='".mysql_escape_string($n_mac)."' WHERE netdevice_idx=$mfr2->netdevice_idx");
                                    $mfr2->devname=$n_dn;
                                    $mfr2->speed=$n_spd;
                                    $mfr2->driver=$n_dr;
                                    $mfr2->routing=$n_rt;
                                    $mfr2->driver_options=$n_opt;
                                    $mfr2->dhcp_device=$n_dhcp;
                                    $mfr2->ethtool_options=$n_bo;
                                    $mfr2->fake_macadr=$n_fmac;
                                    $mfr2->macadr=$n_mac;
                                    $refresh_tk=1;
                                }
                            }
                            $mfr->netdevices[$mfr2->netdevice_idx]=$mfr2;
                            $mfr->netdevices[$mfr2->netdevice_idx]->netips=array();
                            if ($mfr2->netdevice_idx == $new_netdevice_idx) $var_pf="{$name}_ndn";
                            // check for new netip
                            if (is_set("{$var_pf}_new_ip",&$vars)) {
                                $new_ip=$vars["{$var_pf}_new_ip"];
                                if ($new_ip != "0.0.0.0") {
                                    $new_ip=$vars["{$var_pf}_new_ip"];
                                    $new_nw=$vars["{$var_pf}_new_nw"];
                                    $new_al=$vars["{$var_pf}_new_al"];
                                    if (is_set("{$var_pf}_new_alx",&$vars)) {
                                        $new_alx=1;
                                    } else {
                                        $new_alx=0;
                                    }
                                    if (!$new_nw) {
                                        $new_nw=0;
                                        $match_bits=-1;
                                        // find best matching network
                                        foreach ($networks as $netw_idx=>$netw_stuff) {
                                            if (valid_ip($new_ip,$netw_idx,$networks)) {
                                                $new_mb=get_netbits($netw_stuff->netmask);
                                                if ($new_mb > $match_bits) {
                                                    $new_nw=$netw_idx;
                                                    $match_bits=$new_mb;
                                                }
                                            }
                                        }
                                    }
                                    if ($new_nw) {
                                        if (valid_ip($new_ip,$new_nw,$networks)) {
                                            query("INSERT INTO netip SET ip='$new_ip',netdevice=$mfr2->netdevice_idx,network=$new_nw,alias='".mysql_escape_string($new_al)."',alias_excl=$new_alx");
                                            $log_stack->add_message("added ip '$new_ip' to netdevice '{$mfr2->devname}', device $name","ok",1);
                                            if ($networks[$new_nw]->ntid == "b" && !$mfr_ref->bootnetdevice) {
                                                $log_stack->add_message(" - setting netdevice '{$mfr2->devname}' as bootnetdevice for device $name","ok",1);
                                                update_table("device","bootnetdevice=$mfr2->netdevice_idx WHERE name='$name'");
                                            }
                                            $refresh_tk=1;
                                        } else {
                                            $log_stack->add_message("cannot add ip '$new_ip' to netdevice '{$mfr2->devname}', device $name","ip error",0);
                                        }
                                    } else {
                                        $log_stack->add_message("cannot add ip '$new_ip' to netdevice '{$mfr2->devname}', device $name","no network found",0);
                                    }
                                }
                            }
                            // check for new peer_information
                            if (is_set("{$var_pf}_newp",$vars)) {
                                $peer_information_change=1;
                                $new_pi1=$vars["{$var_pf}_newp"];
                                $new_pi2=$mfr2->netdevice_idx;
                                $new_penalty=1;
                                $ins_idx=insert_table("peer_information","0,$new_pi1,$new_pi2,$new_penalty,null");
                                $log_stack->add_message("added peer_information from '{$mfr2->devname}' on $name to '{$all_routing_devices[$new_pi1]->devname}' on {$all_routing_devices[$new_pi1]->name}","ok",1);
                                $peer_information[$new_pi1][$new_pi2]=array($new_penalty,$mfr2->devname,$name);
                                $peer_information[$new_pi2][$new_pi1]=array($new_penalty,$all_routing_devices[$new_pi1]->devname,$all_routing_devices[$new_pi1]->name);
                            }
                            // check for peers to delete
                            if (in_array($mfr2->netdevice_idx,array_keys($peer_information))) {
                                if (count($peer_information[$mfr2->netdevice_idx])) {
                                    $peer_idxs=array_keys($peer_information[$mfr2->netdevice_idx]);
                                    foreach ($peer_idxs as $p_idx) {
                                        $pi_d_name="{$var_pf}_{$p_idx}_del";
                                        if (is_set($pi_d_name,&$vars)) {
                                            $peer_information_change=1;
                                            query("DELETE FROM peer_information WHERE (s_netdevice=$mfr2->netdevice_idx AND d_netdevice=$p_idx) OR (s_netdevice=$p_idx AND d_netdevice=$mfr2->netdevice_idx)");
                                            if (in_array($p_idx,array_keys($all_routing_devices))) {
                                                $log_stack->add_message("deleted peer_information from '{$mfr2->devname}' on $name to '{$all_routing_devices[$p_idx]->devname}' on {$all_routing_devices[$p_idx]->name}","ok",1);
                                            } else if ($p_idx == $mfr2->netdevice_idx) {
                                                $log_stack->add_message("deleted loopback peer_information for '{$mfr2->devname}'","ok",1);
                                            } else {
                                                $log_stack->add_message("deleted peer_information for '{$mfr2->devname}'","ok",1);
                                            }
                                            unset($peer_information[$mfr2->netdevice_idx][$p_idx]);
                                            if ($p_idx != $mfr2->netdevice_idx) unset($peer_information[$p_idx][$mfr2->netdevice_idx]);
                                        }
                                    }
                                }
                            }
                            $mres3=query("SELECT * FROM netip i WHERE i.netdevice=$mfr2->netdevice_idx");
                            while ($mfr3=mysql_fetch_object($mres3)) {
                                $var_pf="{$name}_ni_{$mfr3->netip_idx}";
                                if (is_set("{$var_pf}_del",$vars)) {
                                    query("DELETE FROM netip WHERE netip_idx=$mfr3->netip_idx");
                                    $refresh_tk=1;
                                } else {
                                    if (is_set("{$var_pf}_ip",$vars)) {
                                        $i_ip=$vars["{$var_pf}_ip"];
                                        $i_nw=$vars["{$var_pf}_nw"];
                                        $i_al=$vars["{$var_pf}_al"];
                                        if (is_set("{$var_pf}_alx",&$vars)) {
                                            $i_alx=1;
                                        } else {
                                            $i_alx=0;
                                        }
                                        if (!$i_nw) {
                                            foreach ($networks as $netw_idx=>$netw_stuff) {
                                                if (valid_ip($i_ip,$netw_idx,$networks)) {
                                                    $i_nw=$netw_idx;
                                                    break;
                                                }
                                            }
                                        }
                                        if ($i_nw) {
                                            if ($i_ip != $mfr3->ip || $i_nw != $mfr3->network) {
                                                $new_nw=0;
                                                $match_bits=-1;
                                                // find best matching network
                                                foreach ($networks as $netw_idx=>$netw_stuff) {
                                                    if (valid_ip($i_ip,$netw_idx,$networks)) {
                                                        $new_mb=get_netbits($netw_stuff->netmask);
                                                        if ($new_mb > $match_bits) {
                                                            $new_nw=$netw_idx;
                                                            $match_bits=$new_mb;
                                                        }
                                                    }
                                                }
                                                if (valid_ip($i_ip,$new_nw,$networks)) {
                                                    //echo "*$i_ip*$i_nw*<br>";
                                                    $log_stack->add_message("changed ip '$mfr3->ip' to '$i_ip' for netdevice '{$mfr2->devname}', device $name","ok",1);
                                                    update_table("netip","ip='".mysql_escape_string($i_ip)."',network=$new_nw WHERE netip_idx=$mfr3->netip_idx");
                                                    if ($networks[$new_nw]->ntid != "b" && $mfr_ref->bootnetdevice==$mfr2->netdevice_idx) {
                                                        $log_stack->add_message(" - removing netdevice '{$mfr2->devname}' as bootnetdevice for device $name","ok",1);
                                                        update_table("device","bootnetdevice=0 WHERE name='$name'");
                                                    } 
                                                    if ($networks[$new_nw]->ntid == "b" && !$mfr_ref->bootnetdevice) {
                                                        $log_stack->add_message(" - setting netdevice '{$mfr2->devname}' as bootnetdevice for device $name","ok",1);
                                                        update_table("device","bootnetdevice=$mfr2->netdevice_idx WHERE name='$name'");
                                                    }
                                                    $mfr3->ip=$i_ip;
                                                    $mfr3->network=$new_nw;
                                                    $refresh_tk=1;
                                                } else {
                                                    $log_stack->add_message("cannot alter ip of netdevice '{$mfr2->devname}' to ip '$i_ip', device $name","ip error",0);
                                                }
                                            }
                                        } else {
                                            $log_stack->add_message("cannot alter ip of netdevice '{$mfr2->devname}' to ip '$i_ip', device $name","no network found",0);
                                        }
                                    }
                                    $mfr->netdevices[$mfr2->netdevice_idx]->netips[$mfr3->netip_idx]=$mfr3;
                                }
                            }
                        }
                    }
                    //print_r($mfr->netdevices);
                }
                if ($refresh_tk && $mfr->bootserver) $refresh_tk_array[$boot_server[$mfr->bootserver]][]=$name;
                if (in_array("{$name}_dummy",array_keys($vars))) {
                    if ($dtype=="cm_loc") {
                        foreach ($big_array as $str=>$stuff) {
                            list($var_type,$var_hname,$var_name,$d_array)=$stuff;
                            if ($var_hname) {
                                $avn="g$var_hname";
                                if ((isset($vars[$avn]) && ($var_type != "s" || $vars[$avn] < 0)) || !isset($vars[$avn])) $avn="{$name}_$var_hname";
                                if ($var_name) {
                                    if ($var_type == "T") {
                                        if (isset($vars[$avn]) != $mfr->$var_name) {
                                            update_table("device","$var_name='".isset($vars[$avn])."' WHERE name='$name'");
                                            $mfr->$var_name=isset($vars[$avn]);
                                        }
                                    } else {
                                        if (isset($vars[$avn]) && $vars[$avn] != $mfr->$var_name) {
                                            if ($var_type == "s") {
                                                $mfr->$var_name=$vars[$avn];
                                                $new_var=$vars[$avn];
                                                update_table("device","$var_name=$new_var WHERE name='$name'");
                                                $nagios_config_change=1;
                                            } elseif ($var_type == "r") {
                                                $new_var=doubleval($vars[$avn]);
                                                $mfr->$var_name=$new_var;
                                                update_table("device","$var_name=$new_var WHERE name='$name'");
                                                $nagios_config_change=1;
                                            } elseif ($var_type == "i") {
                                                $new_var=intval($vars[$avn]);
                                                $mfr->$var_name=$new_var;
                                                update_table("device","$var_name=$new_var WHERE name='$name'");
                                                $nagios_config_change=1;
                                            } elseif ($var_type == "t") {
                                                $new_var=strval($vars[$avn]);
                                                $mfr->$var_name=$new_var;
                                                update_table("device","$var_name='$new_var' WHERE name='$name'");
                                                $nagios_config_change=1;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        $hm_coms=array();
                        foreach (array_keys($vars) as $varn) {
                            if (preg_match("/^{$name}_hm(.)_(\d+)$/",$varn,$var_p)) {
                                $hm_idx=$var_p[2];
                                $hm_com=$var_p[1];
                                if (!in_array($hm_idx,array_keys($hm_coms))) $hm_coms[$hm_idx]=array();
                                $hm_coms[$hm_idx][$hm_com]=$vars[$varn];
                            }
                        }
                        if ($hm_coms) {
                            $loc_ms_change=0;
                            foreach (array_keys($hm_coms) as $hm_idx) {
                                $hm_stuff=$hm_coms[$hm_idx];
                                preg_match("/(\d+)\.(\d+)\.(.*)/",$hm_stuff["p"],$hm_op);
                                if ($hm_op[1] != $hm_stuff["s"] || $hm_op[2] != $hm_stuff["o"] || $hm_op[3] != $hm_stuff["i"]) $loc_ms_change=1;
                            }
                            if ($loc_ms_change) {
                                $masterswitch_change=1;
                                $sql_str="slave_device=0,slave_info='' WHERE slave_device=$mfr->device_idx";
                                update_table("msoutlet",$sql_str);
                                foreach ($hm_coms as $idx=>$stuff) {
                                    if ($stuff["s"] != "0" && $stuff["s"] != 0) {
                                        $sql_str="slave_device=$mfr->device_idx,slave_info='".$stuff["i"]."' WHERE outlet=".$stuff["o"]." AND device=".$stuff["s"];
                                        update_table("msoutlet",$sql_str);
                                    }
                                }
                            
                            }
                        }
                    } elseif (preg_match("/^cm_id_.*$/",$dtype)) {
                        foreach ($gc2 as $cname=>$config) {
                            $c_idx=$config->config_idx;
                            $avn="{$name}_{$c_idx}";
                            $avng="globalset_$c_idx";
                            if (!is_set($avng,$vars)) $vars[$avng]="keep";
                            if ((is_set($avn,$vars) || $vars[$avng]=="set") && !in_array($c_idx,array_values($mfr->dev_config))) {
                                // insert deviceconfig
                                $ins_idx=insert_table("deviceconfig","0,$mfr->device_idx,$c_idx,null");
                                $mfr->dev_config[$ins_idx]=$c_idx;
                                $nagios_config_change=1;
                            } elseif ((!is_set($avn,$vars) || $vars[$avng]=="del") && in_array($c_idx,array_values($mfr->dev_config))) {
                                // delete deviceconfig
                                query("DELETE FROM deviceconfig WHERE device=$mfr->device_idx AND config=$c_idx");
                                unset($mfr->dev_config[array_search($c_idx,$mfr->dev_config,FALSE)]);
                                $nagios_config_change=1;
                            }
                        }
                    } elseif (preg_match("/^cm_idds_.*$/",$dtype)) {
                        $all_nag_names=array();
                        foreach ($mfr->dev_config as $cname=>$stuff) {
                            foreach ($stuff->nagios as $nag_idx=>$nag_stuff) $all_nag_names[]=$nag_stuff->name;
                        }
                        foreach ($mfr->dev_config as $cname=>$stuff) {
                            add_sib_config(&$vars,&$all_nag_names,&$all_snmp_mibs,&$log_stack,&$mfr->dev_config[$cname]);
                        }
                    }
                }
                unset($mfr);
                $old_name=$name;
            }
            foreach ($refresh_tk_array as $server=>$nodes) {
                if (count($nodes)) {
                    $rets=contact_server($sys_config,"mother_server",8001,"refresh_tk ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    process_ret($log_stack,$server,8001,"refresh_tk",$rets,$nodes);
                }
            }
            if ($nagios_config_change) {
                $nm_host=get_server_host($sys_config,"nagios_master");
                if ($nm_host) {
                    $rets=contact_server($sys_config,"nagios_master",8010,"rebuild_config",$timeout=0);
                    process_ret($log_stack,$nm_host,8010,"rebuild_config",$rets,array());
                }
            }
            //print_r($sys_config);
            if ($peer_information_change) {
                $rh_host=get_server_host($sys_config,"rebuild_hopcount");
                if ($rh_host) {
                    $rets=contact_server($sys_config,"rebuild_hopcount",8004,"rebuild_hopcount",$timeout=0);
                    process_ret($log_stack,$rh_host,8004,"rebuild_hopcount",$rets,array());
                }
            }
            if ($log_stack->get_num_messages()) $log_stack->print_messages();
            //print_r($refresh_tk_array);
            if ($masterswitch_change && $dtype=="cm_loc") {
                foreach ($machs as $name=>$mfr_ref) $machs[$name]->ms_outlets=array();
                $mres=query("SELECT m.*,d.name FROM msoutlet m, device d WHERE m.slave_device=d.device_idx $optsel");
                while ($mfr=mysql_fetch_object($mres)) $machs[$mfr->name]->ms_outlets[]=$mfr;
            }
            $num_disp_rows=3;
            if (sizeof($machs)) {
                if (sizeof($display_a) > 1) {
                    $tot_mach=0;
                    $tot_grp=0;
                    foreach ($display_a as $lk=>$lv) {
                        $tot_grp+=1;
                        list($n1)=$lv;
                        $tot_mach+=$n1;
                    }
                    message("Found $tot_mach devices in $tot_grp devicegroups");
                } else {
                    reset($display_a);
                    list($n1,$n2,$mach_list)=current($display_a);
                    if ($n1 == 1) {
                        message("Found device {$mach_list[0]} in devicegroup ".key($display_a));
                    } else {
                        message("Found $n1 devices in devicegroup ".key($display_a));
                    }
                }
                // read wc_files if necessary
                $row_size=1;
                if ($show_conf) {
                    foreach ($machs as $mach_name=>$mach) $machs[$mach_name]->wc=array();
                    $mres=query("SELECT w.*,d.name FROM wc_files w, device d WHERE w.device=d.device_idx $optsel ORDER BY w.dest");
                    while ($mfr=mysql_fetch_object($mres)) {
                        $machs[$mfr->name]->wc[]=$mfr;
                    }
                    if ($show_content) $row_size=2;
                }
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                hidden_sid();
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                // number of devices display
                echo "<table class=\"normal\">\n";
                $devs_shown=0;
                foreach ($display_a as $act_group=>$display_g) {
                    list($n1,$n2,$mach_list)=$display_g;
                    if (count($display_a) > 1) echo "<tr><td colspan=\"10\" class=\"machinegroup\">devicegroup: $act_group , selected $n1 of $n2 devices</td></tr>\n";
                    foreach ($mach_list as $mach_name) {
                        $devs_shown++;
                        $ip=&$machs[$mach_name];
                        echo "<tr>";
                        if (preg_match("/^cm_idds_(.*)$/",$dtype,$id_match)) {
                            echo "<td class=\"group\" colspan=\"7\" >$ip->name (".get_plural("configs set",count($ip->dev_config),1).") </td>\n";
                        } else {
                            echo "<td class=\"nameup\">$ip->name</td>\n";
                        }
                        echo "<input type=\"hidden\" name=\"$mach_name.dummy\" />";
                        if ($dtype=="cm_loc") {
                            echo "<td class=\"blind\" colspan=\"9\">";
                            echo "<table class=\"blind\">\n";
                            $act_row=0;
                            foreach ($big_array as $str=>$stuff) {
                                if (!$act_row++) echo "<tr>";
                                list($var_type,$var_hname,$var_name,$d_array)=$stuff;
                                echo "<td class=\"hloccr\">";
                                if ($var_type == "n") {
                                    echo "&nbsp</td><td class=\"hloccl\">&nbsp;</td>";
                                } else {
                                    echo "$str :</td><td class=\"hloccl\">";
                                    if ($var_type == "s") {
                                        echo "<select name=\"$mach_name.$var_hname\">";
                                        foreach ($d_array as $idx=>$what) {
                                            if (is_object($what)) $what=$what->name;
                                            echo "<option value=\"$idx\" ";
                                            if ($idx == $ip->$var_name) echo " selected ";
                                            echo ">$what</option>";
                                        }
                                        echo "</select>\n";
                                    } else if ($var_type=="T") {
                                        echo "<input type=checkbox name=\"$mach_name.$var_hname\" ".($ip->$var_name ? " checked " : "" )."/>";
                                    } else if (in_array($var_type,array("r","i","t"))) {
                                        echo "<input name=\"$mach_name.$var_hname\" maxlength=\"15\" size=\"12\" value=\"{$ip->$var_name}\" />";;
                                    }
                                }
                                echo "</td>";
                                if ($act_row == $num_disp_rows) {
                                    $act_row=0;
                                    echo "</tr>\n";
                                }
                            }
                            $idx=0;
                            foreach ($ip->ms_outlets as $act_mso) {
                                echo "<tr><td class=\"hloccr\">";
                                echo "<input type=hidden name=\"$mach_name.hmp.$idx\" value=\"{$act_mso->device}.{$act_mso->outlet}.{$act_mso->slave_info}\" />";
                                echo "Apc <select name=\"$mach_name.hms.$idx\" >";
                                foreach ($mswitches as $ms_idx=>$ms_name) {
                                    echo "<option value=\"$ms_idx\" ";
                                    if ($ms_idx == $act_mso->device) echo " selected ";
                                    echo ">$ms_name</option>";
                                }
                                echo "</select></td><td class=\"hloccl\">Outlet <select name=\"$mach_name.hmo.$idx\" >";
                                foreach ($msoutlets as $ol_idx=>$ms_name) {
                                    echo "<option value=\"$ol_idx\" ";
                                    if ($ol_idx == $act_mso->outlet) echo " selected ";
                                    echo ">$ms_name</option>";
                                }
                                echo "</select></td>";
                                echo "<td class=\"hloccr\">Info :</td><td class=\"hloccl\"><input name=\"$mach_name.hmi.$idx\" maxlength=\"63\" size=\"20\" value=\"{$act_mso->slave_info}\" /></td>";
                                echo "<td class=\"hloccl\" colspan=2>actual state is $act_mso->state, power on/off reboot delay is $act_mso->power_on_delay/$act_mso->power_off_delay/$act_mso->reboot_delay secs.";
                                //print_r($act_mso);
                                echo "</td></tr>\n";
                                $idx++;
                            }
                            echo "<tr><td class=\"hloccr\" >";
                            echo "<input type=hidden name=\"$mach_name.hmp.$idx\" value=\"0.0.\" />";
                            echo "New Apc <select name=\"$mach_name.hms.$idx\" >";
                            foreach ($mswitches as $ms_idx=>$ms_name) echo "<option value=\"$ms_idx\" >$ms_name</option>\n";
                            echo "</select></td><td class=\"hloccl\">Outlet <select name=\"$mach_name.hmo.$idx\" >";
                            foreach ($msoutlets as $ol_idx=>$ms_name) echo "<option value=\"$ol_idx\" >$ms_name</option>\n";
                            echo "</select></td>";
                            echo "<td class=\"hloccr\">Info :</td><td class=\"hloccl\" colspan=3><input name=\"$mach_name.hmi.$idx\" maxlength=\"63\" size=\"20\" />";
                            echo "</td></tr>\n";
                            echo "</table>";
                            echo "</td>\n";
                        } else  if (preg_match("/^cm_id_(.*)$/",$dtype,$id_match)) {
                            if ($ip->identifier == "H" || $dtype=="cm_id_h") {
                                echo "<td class=\"blind\" colspan=\"9\">";
                                echo "<table class=\"blind\">\n";
                                $num_rows=0;
                                foreach ($gc2 as $cname=>$conf) {
                                    $idx=$conf->config_idx;
                                    if (!$num_rows) echo "<tr>";
                                    echo "<td class=\"config\">$cname";
                                    if ($conf->descr) echo " ($conf->descr)";
                                    echo "</td>\n";
                                    echo "<td class=\"select\"><input type=\"checkbox\" name=\"$mach_name.$idx\"";
                                    if (in_array($idx,$ip->dev_config)) echo " checked ";
                                    echo "/></td>\n";
                                    if (++$num_rows == $num_max_rows) {
                                        echo "</tr>\n";
                                        $num_rows=0;
                                    }
                                }
                                if ($extra_rows) {
                                    $er=$extra_rows;
                                    while ($er--) echo "<td class=\"config\">&nbsp;</td><td class=\"select\">&nbsp;</td>";
                                    echo "</tr>\n";
                                }
                                echo "</table>\n";
                                echo "</td>\n";
                            } else {
                                echo "<td class=\"nconfig\" colspan=\"9\">not configurable</td>";
                            }
                        } else  if (preg_match("/^cm_idds_(.*)$/",$dtype,$id_match)) {
                            echo "</td></tr>\n";
                            if (count($ip->dev_config)) {
                                foreach ($ip->dev_config as $cname=>$stuff) {
                                    $ip->dev_config[$cname]->print_html_mask(0,&$config_vts,$nag_service_templates,&$all_snmp_mibs);
                                }
                            } else {
                                echo "<td class=\"nconfig\" colspan=\"9\">no options set</td>";
                            }
                        } else if ($dtype == "cm_net") {
                            echo "<td class=\"blind\" colspan=\"8\">";
                            echo "<table class=\"simplefull\" >\n";
                            echo "<tr>";
                            foreach (array("Device","Drv / IP","MAC / R / FakeMAC","ethtool / opts / speed / peer") as $nstr) echo "<th class=\"net\">$nstr</th>\n";
                            echo "</tr>\n";
			    $net_idx=1;
                            foreach ($ip->netdevices as $netdevice_idx=>$netdevice) {
				$net_idx=3-$net_idx;
                                echo "<tr>";
                                //print_r($peer_information);
                                if (in_array($netdevice_idx,array_keys($peer_information))) {
                                    $num_peers=count($peer_information[$netdevice_idx]);
                                    $peer_idxs=array_keys($peer_information[$netdevice_idx]);
                                } else {
                                    $num_peers=0;
                                    $peer_idxs=array();
                                }
                                if (count($netdevice->netips)) {
                                    $num_ips=count($netdevice->netips);
                                    $ip_idxs=array_keys($netdevice->netips);
                                } else {
                                    $num_ips=0;
                                    $ip_idxs=array();
                                }
                                $num_ippi=max($num_ips,$num_peers);
                                $num_ipps=$num_ippi+3;
                                if ($netdevice->devname == "lo") $num_ipps--;
                                $var_nd_pf="$mach_name.nd.$netdevice_idx";
                                echo "<input type=hidden name=\"{$var_nd_pf}.dummy\" value=\"1\"/>\n";
                                echo "<td class=\"net$net_idx\" rowspan=\"$num_ipps\"><input name=\"{$var_nd_pf}.dn\" maxlength=\"15\" size=\"5\" value=\"$netdevice->devname\" />".($ip->bootnetdevice==$netdevice_idx ? " (b)" : "")."</td>";
                                echo "<td class=\"net$net_idx\" colspan=\"2\">";
                                if ($ip->bootnetdevice==$netdevice_idx) {
                                    echo "<input type=hidden name=\"{$var_nd_pf}.mac\" value=\"$netdevice->macadr\" />";
                                    echo $netdevice->macadr;
                                } else {
                                    echo "<input name=\"{$var_nd_pf}.mac\" maxlenght=\"17\" size=\"17\" value=\"$netdevice->macadr\" />";
                                }
                                echo " (<input type=checkbox name=\"{$var_nd_pf}.dhcp\" ";
                                if ($netdevice->dhcp_device) echo " checked ";
                                echo "/>);";
                                echo "Routing:<input type=checkbox name=\"{$var_nd_pf}.rt\" ";
                                if ($netdevice->routing) echo " checked ";
                                echo "/></td>\n";
                                if ($netdevice->devname == "lo") {
                                    echo "<td class=\"net$net_idx\">speed: <input name=\"{$var_nd_pf}.spd\" maxlength=\"15\" size=\"12\" value=\"$netdevice->speed\" /></td>\n";
                                } else {
                                    echo "<td class=\"net$net_idx\">autoneg: <select name=\"{$var_nd_pf}.no_n\" >";
                                    foreach ($no_neg_field as $short=>$long) {
                                        echo "<option value=\"$short\" ".((($netdevice->ethtool_options>>0) & 3) == $short ? "selected" : "")." >$long</option>\n";
                                    }
                                    echo "</select>, \n";
                                    echo "duplex: <select name=\"{$var_nd_pf}.no_d\" >";
                                    foreach ($no_dpl_field as $short=>$long) {
                                        echo "<option value=\"$short\" ".((($netdevice->ethtool_options>>2) & 3) == $short ? "selected" : "")." >$long</option>\n";
                                    }
                                    echo "</select>, \n";
                                    echo "speed: <select name=\"{$var_nd_pf}.no_s\" >";
                                    foreach ($no_spd_field as $short=>$long) {
                                        echo "<option value=\"$short\"" .((($netdevice->ethtool_options>>4) & 7) == $short ? "selected" : "")." >$long</option>\n";
                                    }
                                    echo "</select></td>\n";
                                }
                                echo "</tr>\n";
                                if ($netdevice->devname != "lo"){
                                    echo "<tr>";
                                    echo "<td class=\"net$net_idx\" rowspan=\"1\">Driver:<input name=\"{$var_nd_pf}.dr\" maxlength=\"15\" size=\"12\" value=\"$netdevice->driver\" /></td>\n";
                                    echo "<td class=\"net$net_idx\" rowspan=\"1\">fakeMac:<input name=\"{$var_nd_pf}.fmac\" maxlength=\"17\" size=\"17\" value=\"$netdevice->fake_macadr\" /></td>\n";
                                    echo "<td class=\"net$net_idx\" rowspan=\"1\">opts:<input name=\"{$var_nd_pf}.opt\" maxlength=\"190\" size=\"32\" value=\"$netdevice->driver_options\" />, ";
                                    echo "<input name=\"{$var_nd_pf}.spd\" maxlength=\"15\" size=\"12\" value=\"$netdevice->speed\" />\n";
                                    echo "</td></tr>\n";
                                }
                                for ($i=0;$i<$num_ippi;$i++) {
                                    echo "<tr>";
                                    if ($i < $num_ips) {
                                        $netip_idx=$ip_idxs[$i];
                                        $netip=$netdevice->netips[$netip_idx];
                                        $var_ip_pf="$mach_name.ni.$netip_idx";
                                        echo "<td class=\"ip\" colspan=\"2\"><input type=checkbox name=\"$var_ip_pf.del\" />\n";
                                        echo "<input name=\"$var_ip_pf.ip\" maxlength=\"15\" size=\"12\" value=\"$netip->ip\" />\n";
                                        echo "<select name=\"$var_ip_pf.nw\" >";
                                        echo "<option value=\"0\" >auto select</option>\n";
                                        foreach ($networks as $network_idx=>$network) {
                                            echo "<option value=\"$network_idx\" ";
                                            if ($network_idx==$netip->network) echo " selected ";
                                            echo ">$network->identifier ($network->ntid) $network->network / ".strval(get_netbits($network->netmask))."</option>\n";
                                        }
                                        echo "</select>";
                                        echo ", alias: <input name=\"$var_ip_pf.al\" maxlength=\"64\" size=\"12\" value=\"$netip->alias\"/>\n";
                                        echo ", excl: <input type=checkbox name=\"$var_ip_pf.alx\" ".($netip->alias_excl ? " checked " : "")." />\n";
                                        echo "</td>";
                                    } else {
                                        echo "<td colspan=\"2\" class=\"ip\">no IP</td>";
                                    }
                                    if ($i < $num_peers) {
                                        $peer_idx=$peer_idxs[$i];
                                        list($penalty,$n_name,$d_name)=$peer_information[$netdevice_idx][$peer_idx];
                                        echo "<td class=\"peer\" colspan=\"1\">del: <input type=checkbox name=\"{$var_nd_pf}.{$peer_idx}.del\"/>, to '$n_name' on $d_name (penalty $penalty)</td>";
                                    } else {
                                        echo "<td class=\"peer\" colspan=\"1\">no peer</td>";
                                    }
                                    echo "</tr>\n";
                                }
                                echo "<tr><td class=\"ipnew\" colspan=\"2\">New:<input name=\"{$var_nd_pf}.new.ip\" maxlength=\"15\" size=\"12\" value=\"0.0.0.0\" />\n";
                                echo "<select name=\"{$var_nd_pf}.new.nw\" >";
                                echo "<option value=\"0\" >auto select</option>\n";
                                foreach ($networks as $network_idx=>$network) {
                                    echo "<option value=\"$network_idx\" >$network->identifier ($network->ntid) $network->network / ".strval(get_netbits($network->netmask))."</option>\n";
                                }
                                echo "</select>";
                                echo ", alias: <input name=\"{$var_nd_pf}.new.al\" maxlength=\"64\" size=\"12\" value=\"\"/>\n";
                                echo ", excl: <input type=checkbox name=\"{$var_nd_pf}.new.alx\" />\n";
                                echo "</td>";
                                echo "<td class=\"peernew\" colspan=\"3\"><select name=\"{$var_nd_pf}.newp\" >";
                                echo "<option value=\"0\" selected >--- none ---------------</option>\n";
                                foreach ($all_routing_devices as $netdev_idx=>$netdev) {
                                    if (($netdev_idx != $netdevice_idx) && !in_array($netdev_idx,$peer_idxs)) {
                                        echo "<option value=\"$netdev_idx\" >$netdev->devname ($netdev->macadr) on $netdev->name</option>\n";
                                    }
                                }
                                echo "</select>";
                                echo "</td>";
                                echo "</tr>\n";
                            }
                            echo "<tr>";
                            echo "<td class=\"netnew\" rowspan=\"3\">";
                            if (count($ip->netdevices)) {
                                echo "New:";
                            } else {
                                echo "New or Increase (<input type=checkbox name=\"$mach_name.newnetdev\"/>):\n";
                            }
                            echo "<input name=\"$mach_name.newnetdev.dn\" maxlength=\"15\" size=\"5\" value=\"eth\" /></td>\n";
                            echo "<td class=\"netnew\">Alias:<input name=\"$mach_name.newnetdev.al\" maxlength=\"15\" size=\"12\" /></td>\n";
                            echo "<td class=\"netnew\"><input name=\"$mach_name.newnetdev.mac\" maxlength=\"17\" size=\"16\" value=\"00:00:00:00:00:00\"/> (<input type=checkbox name=\"{$mach_name}.newnetdev.dhcp\" />); Routing:<input type=checkbox name=\"$mach_name.newnetdev.rt\" /></td>\n";
                            echo "<td class=\"netnew\">autoneg: <select name=\"{$mach_name}.newnetdev.no_n\" >";
                            foreach ($no_neg_field as $short=>$long) {
                                echo "<option value=\"$short\">$long</option>\n";
                            }
                            echo "</select>, \n";
                            echo "duplex: <select name=\"{$mach_name}.newnetdev.no_d\" >";
                            foreach ($no_dpl_field as $short=>$long) {
                                echo "<option value=\"$short\">$long</option>\n";
                            }
                            echo "</select>, \n";
                            echo "speed: <select name=\"{$mach_name}.newnetdev.no_s\" >";
                            foreach ($no_spd_field as $short=>$long) {
                                echo "<option value=\"$short\">$long</option>\n";
                            }
                            echo "</select>\n";
                            echo "</td></tr>\n";
                            echo "<tr><td class=\"netnew\">Driver:<input name=\"$mach_name.newnetdev.dr\" maxlength=\"32\" size=\"12\" value=\"eepro100\"/></td>\n";
                            echo "<td class=\"netnew\" rowspan=\"1\">fakeMac:<input name=\"$mach_name.newnetdev.fmac\" maxlength=\"17\" size=\"17\" value=\"00:00:00:00:00:00\" /></td>\n";
                            echo "<td class=\"netnew\">opts:<input name=\"$mach_name.newnetdev.opt\" maxlength=\"190\" size=\"32\" value=\"\"/>, \n";
                            echo "<input name=\"$mach_name.newnetdev.spd\" maxlength=\"17\" size=\"12\" value=\"10000000\"/></td>\n";
                            echo "</tr>\n";
                            // new netip for new netdevice
                                echo "<tr><td class=\"ipnew\" colspan=\"2\">New:<input name=\"$mach_name.ndn.new.ip\" maxlength=\"15\" size=\"12\" value=\"0.0.0.0\" />\n";
                                echo "<select name=\"$mach_name.ndn.new.nw\" >";
                                echo "<option value=\"0\" >auto select</option>\n";
                                foreach ($networks as $network_idx=>$network) {
                                    echo "<option value=\"$network_idx\" >$network->identifier ($network->ntid) $network->network / ".strval(get_netbits($network->netmask))."</option>\n";
                                }
                                echo "</select>";
                                echo "</td>";
                                echo "<td class=\"peernew\" colspan=\"3\"><select name=\"$mach_name.ndn.newp\" >";
                                echo "<option value=\"0\" selected >--- none ---------------</option>\n";
                                foreach ($all_routing_devices as $netdev_idx=>$netdev) {
                                    if (($netdev_idx != $netdevice_idx) && !in_array($netdev_idx,$peer_idxs)) {
                                        echo "<option value=\"$netdev_idx\" >$netdev->devname ($netdev->macadr) on $netdev->name</option>\n";
                                    }
                                }
                                echo "</select>";
                                echo "</td>";
                                echo "</tr>\n";
                            echo "</table></td>\n";
			} else if($dtype=="cm_nag") {
			    echo "<td class=\"blind\" colspan=\"9\"><table class=\"simplefull\">\n";
			    echo "</table></td>\n";
                        } else {
                            echo "<td class=\"nconfig\">unknown config-type $dtype</td>";
                        }
                        if (!preg_match("/^cm_idds_.*$/",$dtype)) echo "</tr>\n";
			if ($show_conf) {
			    if (count($ip->wc)) {
				$num_array=array("f"=>0,"c"=>0,"d"=>0,"l"=>0,"e"=>0,"-"=>0);
				$tot_num=0;
				foreach ($ip->wc as $conf) {
				    $tot_num++;
				    $num_array[$conf->dest_type]++;
				}
				echo "<tr><td class=\"netnew\" colspan=\"10\">$tot_num configs found ({$num_array['f']} files, {$num_array['c']} copies, {$num_array['l']} links, {$num_array['d']} directories), {$num_array['e']} errors</td></tr>\n";
				foreach (array_keys($num_array) as $fc_type) {
				    if (in_array($fc_type,array("f","-"))) {
                        $act_rowspan=$row_size;
				    } else {
                        $act_rowspan=1;
				    }
				    if ($num_array[$fc_type]) {
                        foreach ($ip->wc as $conf) {
                            if ($conf->dest_type==$fc_type) {
                                $lines=explode("\n",trim($conf->content));
                                echo "<tr><td class=\"name\" rowspan=\"$act_rowspan\" >$conf->dest</td><td class=\"net\" rowspan=\"$act_rowspan\">\n";
                                echo "$fc_type</td><td class=\"hloccr\">$conf->disk_int</td><td class=\"hloccr\">$conf->uid</td><td class=\"hloccr\">$conf->gid</td><td class=\"hloccr\">$conf->mode</td>\n";
                                if (in_array($fc_type,array("f","-"))) {
                                    echo "<td class=\"hloccr\">".sprintf("%d",strlen($conf->content))." bytes , ".count($lines)." lines</td>";
                                } else {
                                    echo "<td class=\"hloccr\">&nbsp;</td>";
                                }
                                echo "<td class=\"hloccl\">from $conf->config</td><td class=\"hloccl\">$conf->source</td></tr>\n";
                                if ($act_rowspan > 1) {
                                    echo "<tr><td colspan=\"8\" class=\"hloccl\">";
                                    $max_cols=80;
                                    $max_lines=min(count($lines),10);
                                    echo "<textarea rows=\"$max_lines\" cols=\"$max_cols\"readonly wrap=\"off\">";
                                    foreach ($lines as $line) {
                                        echo htmlspecialchars($line)."\n";
                                    }
                                    echo "</textarea>";
                                    echo "</td>";
                                    echo "</tr>\n";
                                }
                            }
                        }
				    }
				}
			    } else {
                    echo "<tr><td class=\"netnew\" colspan=\"10\">No configs found</td></tr>\n";
			    }
			}
                    }
                }
                echo "</table>\n";
                if ($dc_stuff["global"] && $devs_shown > 1) {
                    message("Global settings",$type=2);
                    echo "<table class=\"simplesmall\">\n";
                    echo "<tr><td>";
                    echo "<table class=\"normal\">\n";
                    if ($dtype == "cm_loc") {
                        echo "<tr>";
                        echo "<td class=\"blind\">";
                        echo "<table class=\"blind\">\n";
                        $act_row=0;
                        foreach ($big_array as $str=>$stuff) {
                            if (!$act_row++) echo "<tr>";
                            list($var_type,$var_hname,$var_name,$d_array)=$stuff;
                            if ($var_type == "n") {
                                echo "<td class=\"hloccr\">&nbsp;</td><td class=\"hloccl\">&nbsp;</td>\n";
                            } else {
                                echo "<td class=\"hloccr\">$str:</td><td class=\"hloccl\">";
                                if ($var_type=="s") {
                                    echo "<select name=\"g$var_hname\">";
                                    echo "<option value=\"-1\">keep</option>\n";
                                    foreach ($d_array as $idx=>$what) {
                                        if (is_object($what)) $what=$what->name;
                                        echo "<option value=\"$idx\" >$what</option>";
                                    }
                                    echo "</select>\n";
                                } else if ($var_type=="T") {
                                    echo "<input type=checkbox name=\"g$var_hname\" />";
                                } else {
                                    echo "---\n";
                                }
                                echo "</td>\n";
                            }
                            if ($act_row == $num_disp_rows) {
                                $act_row=0;
                                echo "</tr>\n";
                            }
                        }
                        echo "</table>\n";
                        echo "</td></tr>\n";
                    } else if (preg_match("/^cm_id_(.*)$/",$dtype,$id_match)) {
                        echo "<tr>";
                        for ($idx=0;$idx<$num_max_rows;$idx++) {
                            echo "<th class=\"config\">Config</th><th colspan=\"3\" class=\"use\">keep/del/set</th>\n";
                        }
                        echo "</tr>\n";
                        $num_rows=0;
                        foreach ($gc2 as $cname=>$conf) {
                            $idx=$conf->config_idx;
                            if (!$num_rows++) echo "<tr>";
                            echo "<td class=\"config\">$cname";
                            if ($conf->descr) echo " ($conf->descr)";
                            echo "</td>\n";
                            echo "<td class=\"use1\"><input type=radio name=\"globalset.$idx\" checked value=\"keep\" /></td>\n";
                            echo "<td class=\"use2\"><input type=radio name=\"globalset.$idx\" value=\"del\" /></td>\n";
                            echo "<td class=\"use3\"><input type=radio name=\"globalset.$idx\" value=\"set\" /></td>\n";
                            if ($num_rows == $num_max_rows) {
                                echo "</tr>\n";
                                $num_rows=0;
                            }
                        }
                        if ($extra_rows) {
                            $er=$extra_rows;
                            while ($er--) echo "<td class=\"config\">&nbsp;</td><td class=\"use1\">&nbsp;</td><td class=\"use2\">&nbsp;</td><td class=\"use3\">&nbsp;</td>\n";
                            echo "</tr>\n";
                        }
                    } else {
                        message("Unknown config-type $dtype");
                    }
                }
                echo "</table>\n";
                echo "</td></tr>\n";
                echo "</table>\n";
                echo "<div class=\"center\"><input type=submit value=\"submit\"></div>";
                echo "</form>";
            } else {
                message ("No devices found");
            }
# ----------------------------------------------------------------------------------------------------
        } else {
# ----------------------------------------------------------------------------------------------------
            if ($log_stack->get_num_messages()) $log_stack->print_messages();
            // modify part
            if ($dtype=="cg_device groups") {
                message("Device group config");
                //print_r($dev_groups);
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                if (count($dev_groups)) {
                    message(get_plural("Devicegroup",count($dev_groups),1)." defined",$type=1);
                } else {
                    message("No Devicegroups defined",$type=1);
                }
                echo "<table class=\"normal\">\n";
                $cdg_used=0;
                foreach (array(1,0) as $cdg_value) {
                    $first_match=1;
                    foreach ($dev_groups as $devg_idx=>$dev_group) {
                        if ($dev_group->cluster_device_group==$cdg_value) {
                            if ($first_match) {
                                $first_match=0;
                                if ($cdg_value) {
                                    echo "<tr><th class=\"name\" colspan=\"4\">ClusterDeviceGroup</th></tr>\n";
                                } else {
                                    echo "<tr><th class=\"delnew\"># of devs, del</th><th class=\"name\">DevGroup name</th><th class=\"delnew\">MetaDev</th><th class=\"group\">DevGroup description</th></tr>\n";
                                }
                            }
                            echo "<tr>";
                            echo "<td class=\"config\">".($dev_group->cluster_device_group ? "ClusterDevGroup" : "$dev_group->device_count");
                            if (!$dev_group->device_count) {
                                echo ", delete: <input type=checkbox name=\"deldevgroup_$devg_idx\" />";
                            }
                            echo "</td>";
                            echo "<td class=\"nameup\"><input name=\"devgroupname_$devg_idx\" maxlength=\"60\" size=\"40\" value=\"$dev_group->name\"/></td>\n";
                            echo "<td class=\"delnew\"><input type=checkbox name=\"devgroupmg_$devg_idx\" ".($dev_group->device ? "checked" : "")." /></td>\n";
                            if ($dev_group->cluster_device_group) $cdg_used=1;
                            echo "<td class=\"group\"><input name=\"devgroupdescr_$devg_idx\" maxlength=\"100\" size=\"40\" value=\"$dev_group->description\"/></td>\n";
                            echo "</tr>\n";
                        }
                    }
                }
                echo "<tr>";
                echo "<td class=\"config\">new group:</td>\n";
                echo "<td class=\"nameup\"><input name=\"newdevgroupname\" maxlength=\"60\" size=\"40\" value=\"\"/></td>\n";
                echo "<td class=\"delnew\"><input type=checkbox name=\"newdevgroupmg\" checked />";
                echo ($cdg_used ? "" : ", cdg:<input type=checkbox name=\"newdevgroupcdg\" />")."</td>\n";
                echo "<td class=\"group\"><input name=\"newdevgroupdescr\" maxlength=\"100\" size=\"40\" value=\"New Group\"/></td>\n";
                echo "</tr></table>\n";
                echo "<div class=\"center\"><input type=submit value=\"submit\"></div></form>";
# -- network ----------------------------------------------------
            } else if ($dtype=="cg_network") {
# -- network ----------------------------------------------------
                message("Network config");
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                echo "<table class=\"normal\">\n";
                echo "<tr>";
                echo "<th class=\"name\">Identifier</th><th class=\"delnew\">Del</th><th class=\"delnew\">Short</th>\n";
                echo "<th class=\"name\" colspan=\"4\">Network Data</th></tr>\n";
                foreach ($networks as $net_idx=>$network) {
                    echo "<tr>";
                    echo "<td class=\"name\" rowspan=4><input name=\"netidentifier_$net_idx\" maxlength=\"20\" size=\"20\" value=\"$network->identifier\"/></td>\n";
                    echo "<td class=\"delnew\" rowspan=4><input type=checkbox name=\"netdel_$net_idx\" /></td>";
                    echo "<td class=\"delnew\" rowspan=4><input type=checkbox name=\"netshort_$net_idx\" ".($network->short_names ? "checked" : "")." /></td>\n";
                    echo "<td class=\"name\">Postfix:<input name=\"netpostfix_$net_idx\" maxlength=\"8\" size=\"8\" value=\"$network->postfix\"/></td>\n";
                    echo "<td class=\"name\">Name:<input name=\"netname_$net_idx\" maxlength=\"20\" size=\"20\" value=\"$network->name\"/></td>\n";
                    echo "<td class=\"name\">Info:<input name=\"netinfo_$net_idx\" maxlength=\"28\" size=\"28\" value=\"$network->info\"/></td>\n";
                    echo "<td class=\"name\">Write config for: BIND<input type=checkbox name=\"netwbc_$net_idx\" ".($network->write_bind_config ? "checked" : "")." />, ";
                    echo "OtherNet<input type=checkbox name=\"netwonc_$net_idx\" ".($network->write_other_network_config ? "checked" : "")." />";
		    echo "</td></tr>\n";
                    echo "<tr>";
                    echo "<td class=\"type\">Penalty:<input name=\"netpenalty_$net_idx\" maxlength=\"5\" size=\"5\" value=\"$network->penalty\"/></td>\n";
                    echo "<td class=\"group\">Type:<select name=\"nettype_$net_idx\">";
                    foreach ($network_types as $nt_idx=>$ntt) {
                        echo "<option value=\"$nt_idx\" ";
                        if ($network->network_type == $nt_idx) echo " selected ";
                        echo ">$ntt->identifier ($ntt->description)</option>\n";
                    }
                    echo "</select></td>\n";
                    foreach (array("network","gateway") as $nv_name) {
                        echo "<td class=\"net\">".ucfirst($nv_name).":<input name=\"net{$nv_name}_{$net_idx}\" maxlength=\"20\" size=\"20\" value=\"{$network->$nv_name}\"/></td>\n";
                    }
                    echo "</tr>\n";
                    echo "<tr>";
                    echo "<td class=\"type\">GwPri:<input name=\"netgwpri_$net_idx\" maxlength=\"5\" size=\"5\" value=\"$network->gw_pri\"/></td>\n";
                    echo "<td class=\"group\">MasterNet:<select name=\"netmaster_$net_idx\">";
                    echo "<option value=\"0\" ";
                    if (!$network->master_network) echo " selected ";
                    echo ">not set\n";
                    foreach ($networks as $master_idx=>$master) {
                        if ($master_idx != $net_idx) {
                            echo "<option value=\"$master_idx\" ";
                            if ($network->master_network == $master_idx) echo " selected ";
                            echo ">$master->identifier ($master->info)</option>\n";
                        }
                    }
                    echo "</select></td>\n";
                    foreach (array("netmask","broadcast") as $nv_name) {
                        echo "<td class=\"net\">".ucfirst($nv_name).":<input name=\"net{$nv_name}_{$net_idx}\" maxlength=\"20\" size=\"20\" value=\"{$network->$nv_name}\"/></td>\n";
                    }
                    echo "</tr>\n";
                    echo "<tr><td class=\"name\" colspan=\"4\">Info:";
                    show_network_info($network);
                    echo "</td></tr>\n";
                }
                echo "<tr><td class=\"net\" colspan=\"7\">New Net</td></tr>\n";
                echo "<tr>";
                echo "<td class=\"name\" rowspan=\"3\" colspan=\"2\"><input name=\"netidentifier_new\" maxlength=\"20\" size=\"20\" value=\"\"/></td>\n";
                echo "<td class=\"delnew\" rowspan=3><input type=checkbox name=\"netshort_new\" checked /></td>\n";
                echo "<td class=\"name\">Postfix:<input name=\"netpostfix_new\" maxlength=\"8\" size=\"8\" value=\"\"/></td>\n";
                echo "<td class=\"name\">Name:<input name=\"netname_new\" maxlength=\"20\" size=\"20\" value=\"init.at\"/></td>\n";
                echo "<td class=\"name\">Info:<input name=\"netinfo_new\" maxlength=\"28\" size=\"28\" value=\"New network\"/></td>\n";
		echo "<td class=\"name\">Write config for BIND:<input type=checkbox name=\"netwbc_new\" checked />, OtherNet:<input type=checkbox name=\"netwonc_new\"/></td></tr>\n";
                echo "<tr>";
                echo "<td class=\"type\">Penalty:<input name=\"netpenalty_new\" maxlength=\"5\" size=\"5\" value=\"0\"/></td>\n";
                echo "<td class=\"group\">Type:<select name=\"nettype_new\">";
                foreach ($network_types as $nt_idx=>$ntt) {
                    echo "<option value=\"$nt_idx\" >$ntt->identifier ($ntt->description)</option>\n";
                }
                echo "</select></td>\n";
                foreach (array("network"=>"192.168.1.0","gateway"=>"192.168.1.1") as $nv_name=>$nv_val) {
                    echo "<td class=\"net\">".ucfirst($nv_name).":<input name=\"net{$nv_name}_new\" maxlength=\"20\" size=\"20\" value=\"$nv_val\"/></td>\n";
                }
                echo "</tr>\n";
                echo "<tr>";
                echo "<td class=\"type\">GwPri:<input name=\"netgwpri_new\" maxlength=\"5\" size=\"5\" value=\"0\"/></td>\n";
                echo "<td class=\"group\">MasterNet:<select name=\"netmaster_new\">";
                echo "<option value=\"0\" selected >not set\n";
                foreach ($networks as $master_idx=>$master) {
                    echo "<option value=\"$master_idx\" >$master->identifier ($master->info)</option>\n";
                }
                echo "</select></td>\n";
                foreach (array("netmask"=>"255.255.255.0","broadcast"=>"192.168.1.255") as $nv_name=>$nv_val) {
                    echo "<td class=\"net\">".ucfirst($nv_name).":<input name=\"net{$nv_name}_new\" maxlength=\"20\" size=\"20\" value=\"$nv_val\"/></td>\n";
                }
                echo "</tr>\n";
                echo "</table>\n";
                echo "<div class=\"center\"><input type=submit value=\"submit\" /></div></form>\n";
# -- config ----------------------------------------------------
            } else if (preg_match("/^cg_config_(.*)$/",$dtype,$c_id)) {
# -- config ----------------------------------------------------
                $c_name="";
                foreach ($config_types as $idx=>$stuff) {
                    if ($stuff->identifier == $c_id[1]) $c_name=$stuff->name;
                }
                message("Modify config for $c_name");
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"name\" colspan=\"2\">New/Del</th>\n";
                echo "<th class=\"type\" colspan=\"1\">Type</th>\n";
                echo "<th class=\"type\" colspan=\"1\">Name</th>\n";
                echo "<th class=\"type\" colspan=\"1\">Value</th>\n";
                echo "<th class=\"type\" colspan=\"1\">Command/Descr</th>\n";
                echo "</tr>\n";
                foreach ($gc2 as $cname=>$stuff) {
                    $gc2[$cname]->print_html_mask(1,$config_vts,&$nag_service_templates,&$all_snmp_mibs);
                }
                echo "<tr><td class=\"name\" colspan=\"6\">NewConf: <input name=\"newconf\" value=\"\" maxlength=\"32\" size=\"12\"/>, \n";
                echo "Pri: <input name=\"newconf_pri\" value=\"0\" maxlength=\"10\" size=\"5\"/>, \n";
                echo "Description for new entry: <input name=\"newconf_descr\" value=\"New config\" maxlength=\"128\" size=\"32\"/></td>\n";
                echo "</tr>\n";
                echo "</table>\n";
                echo "<div class=\"center\"><input type=submit value=\"submit\"></div></form>";
# -- nagios ----------------------------------------------------
            } else if ($dtype=="cg_nagios") {
# -- nagios ----------------------------------------------------
                message("Nagios config");
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                $all_users=getusers();
                $user_idx_table=array();
                foreach ($all_users as $login=>$stuff) $user_idx_table[$stuff->user_idx]=$stuff;
                message("Time periods",$type=1);
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"name\">Name</th><th class=\"net\">Alias</th>";
                foreach ($time_array as $short=>$long) echo "<th class=\"group\">$long</th>\n";
                echo "</tr>\n";
                foreach ($nag_periods as $idx=>$stuff) {
                    echo "<tr><td class=\"name\"><input type=checkbox name=\"nagtimedel_$idx\"/>$stuff->name</td>\n";
                    echo "<td class=\"net\">$stuff->alias</td>\n";
                    foreach ($time_array as $short=>$long) {
                        $t_var="{$short}range";
                        echo "<td class=\"group\">{$stuff->$t_var}</td>\n";
                    }
                    echo "</tr>\n";
                }
                echo "<tr><td class=\"name\"><input type=checkbox name=\"nagtimenew\"/><input name=\"nag_tpn_name\" value=\"new_timerange\" maxlength=\"60\" size=\"20\"/></td>\n";
                echo "<td class=\"net\"><input name=\"nag_tpn_alias\" value=\"New Timerange alias\" maxlength=\"60\" size=\"20\"/></td>\n";
                foreach ($time_array as $short=>$long) echo "<td class=\"group\"><input name=\"nag_tpn_$short\" maxlength=\"40\" size=\"14\" value=\"00:00-24:00\"/></td>\n";
                echo "</tr>\n";
                echo "</table>";
                message("Contact Groups",$type=1);
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"name\">Name</th><th class=\"net\">Alias</th><th class=\"type\">Members</th><th class=\"group\">DeviceGroups</th><th class=\"type\">Service templates</th></tr>\n";
                $sel_size=min(4,max(count($nag_contacts),count($dev_groups),count($nag_service_templates)-1));
                foreach ($nag_contact_groups as $idx=>$stuff) {
                    echo "<tr>";
                    echo "<td class=\"name\"><input type=checkbox name=\"nag_cong_del_$idx\"/>";
                    echo "$stuff->name";
                    echo "<input type=hidden name=\"nag_cong_dummy_$idx\" value=\"on\"/></td>";
                    echo "<td class=\"net\"><input name=\"nag_cong_alias_$idx\" maxlength=\"60\" size=\"20\" value=\"$stuff->alias\"/></td>";
                    echo "<td class=\"type\">";
                    if (count($nag_contacts)) {
                        echo "<select name=\"nag_cong_mem_{$idx}[]\" multiple size=\"$sel_size\" >";
                        foreach ($nag_contacts as $n_idx=>$n_stuff) {
                            echo "<option value=\"$n_idx\" ";
                            if (in_array($n_idx,$stuff->contacts)) echo " selected ";
                            $user=$user_idx_table[$n_stuff->user];
                            $full_name=trim("$user->uservname $user->usernname");
                            echo ">$user->login";
                            if ($full_name) echo " ($full_name)";
			    if ($user->useremail) {
				echo ", $user->useremail";
			    } else {
				echo ", nomail";
			    }
                            echo "</option>\n";
                        }
                        echo "</select></td>\n";
                    } else {
                        echo "<input type=hidden name=\"nag_cong_mem_{$idx}\"  />";
                    }
                    echo "<td class=\"group\">";
                    echo "<select name=\"nag_cong_devg_{$idx}[]\" multiple size=\"$sel_size\" >";
                    foreach ($dev_groups as $g_idx=>$d_stuff) {
                        echo "<option value=\"$g_idx\" ";
                        if (in_array($g_idx,$stuff->devgroups)) echo " selected ";
                        echo " >$d_stuff->name</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "<td class=\"type\">";
                    echo "<select name=\"nag_cong_servt_{$idx}[]\" multiple size=\"$sel_size\" >";
                    foreach ($nag_service_templates as $s_idx=>$s_stuff) {
                        if ($s_idx) {
                            echo "<option value=\"$s_idx\" ";
                            if (in_array($s_idx,$stuff->service_templates)) echo " selected ";
                            echo " >$s_stuff->name</option>\n";
                        }
                    }
                    echo "</select></td>\n";
                    echo "</tr>";
                }
                echo "<tr>";
                echo "<td class=\"name\"><input type=checkbox name=\"nagnewcong\"/>";
                echo "<input name=\"newcongname\" maxlength=\"60\" size=\"40\" value=\"newgroup\"/>";
                echo "</td>\n";
                echo "<td class=\"net\"><input name=\"newcongalias\" maxlength=\"60\" size=\"40\" value=\"newalias\"/></td>\n";
                echo "<td class=\"type\">";
                if (count($nag_contacts)) {
                    echo "<select name=\"nag_cong_mem_new[]\" multiple size=\"$sel_size\" >";
                    foreach ($nag_contacts as $idx=>$n_stuff) {
                        $user=$user_idx_table[$n_stuff->user];
                        $full_name=trim("$user->uservname $user->usernname");
                        echo "<option value=\"$idx\" >$user->login";
                        if ($full_name) echo " ($full_name)";
                        echo "</option>\n";
                    }
                    echo "</select>\n";
                } else {
                    echo "<input type=hidden name=\"nag_cong_mem_new\" />";
                }
                echo "</td>\n";
                echo "<td class=\"group\">";
                echo "<select name=\"nag_cong_devg_new[]\" multiple size=\"$sel_size\" >";
                foreach ($dev_groups as $idx=>$d_stuff) {
                    echo "<option value=\"$idx\" >$d_stuff->name</option>\n";
                }
                echo "</select></td>\n";
                echo "<td class=\"type\">";
                echo "<select name=\"nag_cong_servt_new[]\" multiple size=\"$sel_size\" >";
                foreach ($nag_service_templates as $s_idx=>$s_stuff) {
                    if ($s_idx) echo "<option value=\"$s_idx\" >$s_stuff->name</option>\n";
                }
                echo "</select></td>\n";
                echo "</tr>\n";
                echo "</table>";
                if (count($nag_periods)) {
                    message("Contacts",$type=1);
                    echo "<table class=\"normal\">\n";
                    echo "<tr><th class=\"name\">Name</th><th class=\"net\">Host not. period</th><th class=\"type\">Host options</th>\n";
                    echo "<th class=\"net\">Service not. period</th>";
                    echo "<th class=\"type\">Service options</th>\n";
                    echo "</tr>\n";
                    foreach ($nag_contacts as $idx=>$stuff) {
                        echo "<tr>";
                        echo "<td class=\"name\"><input type=checkbox name=\"nag_con_del_$idx\"/>";
                        $user=$user_idx_table[$stuff->user];
                        $full_name=trim("$user->uservname $user->usernname");
                        echo "$user->login";
                        if ($full_name) echo " ($full_name)";
                        if ($user->useremail) {
                            $u_email=$user->useremail;
                        } else {
                            $u_email="root@localhost";
                        }
                        echo ", $u_email";
                        echo "</td>";
                        echo "<td class=\"net\"><select name=\"nag_con_hnp_$idx\">";
                        foreach ($nag_periods as $p_idx=>$p_stuff) {
                            echo "<option value=\"$p_idx\" ";
                            if ($p_idx == $stuff->hnperiod) echo " selected ";
                            echo ">$p_stuff->name ($p_stuff->alias)</option>\n";
                        }
                        echo "</select></td>\n";
                        echo "<td class=\"type\">";
                        foreach ($hno_array as $short=>$long) {
                            echo "$long: <input type=checkbox name=\"nag_con_hno_{$short}_$idx\" ";
                            $var_n="hn".strtolower($long);
                            if ($stuff->$var_n) echo " checked ";
                            echo "/>, ";
                        }
                        echo "</td>\n";
                        echo "<td class=\"net\"><select name=\"nag_con_snp_$idx\">";
                        foreach ($nag_periods as $p_idx=>$p_stuff) {
                            echo "<option value=\"$p_idx\" ";
                            if ($p_idx == $stuff->snperiod) echo " selected ";
                            echo ">$p_stuff->name ($p_stuff->alias)</option>\n";
                        }
                        echo "</select></td>\n";
                        echo "<td class=\"type\">";
                        foreach ($sno_array as $short=>$long) {
                            echo "$long: <input type=checkbox name=\"nag_con_sno_{$short}_$idx\" ";
                            $var_n="sn".strtolower($long);
                            if ($stuff->$var_n) echo " checked ";
                            echo "/>, ";
                        }
                        echo "</td>\n";
                        echo "</tr>";
                    }
                    echo "<tr>";
                    echo "<td class=\"name\"><input type=checkbox name=\"nagnewcontact\"/>";
                    echo "<select name=\"nag_con_name\">";
                    foreach ($all_users as $login=>$stuff) {
                        $full_name=trim("$stuff->uservname $stuff->usernname");
                        echo "<option value=\"$stuff->user_idx\">$login";
                        if ($full_name) echo " ($full_name)";
                        if ($stuff->useremail) {
                            $u_email=$stuff->useremail;
                        } else {
                            $u_email="root@localhost";
                        }
                        echo ", $u_email";
                        echo "</option>\n";
                    }
                    echo "</select>\n";
                    echo "<td class=\"net\"><select name=\"nag_con_hnp\">";
                    foreach ($nag_periods as $idx=>$stuff) {
                        echo "<option value=\"$idx\">$stuff->name ($stuff->alias)</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "<td class=\"type\">";
                    foreach ($hno_array as $short=>$long) {
                        echo "$long: <input type=checkbox name=\"nag_con_hno_$short\"/>, ";
                    }
                    echo "</td>\n";
                    echo "<td class=\"net\"><select name=\"nag_con_snp\">";
                    foreach ($nag_periods as $idx=>$stuff) {
                        echo "<option value=\"$idx\">$stuff->name ($stuff->alias)</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "<td class=\"type\">";
                    foreach ($sno_array as $short=>$long) {
                        echo "$long: <input type=checkbox name=\"nag_con_sno_$short\"/>, ";
                    }
                    echo "</td>\n";
                    echo "</tr>\n";
                    echo "</table>";
                    message("Service templates",$type=1);
                    echo "<table class=\"normal\">\n";
                    echo "<tr><th class=\"name\">Name</th><th class=\"group\">Volatile</th><th class=\"type\">Check period</th><th class=\"net\">Max attempts</th>\n";
                    echo "<th class=\"net\">Check Iv.</th><th class=\"net\">Retry Iv.</th><th class=\"type\">Notif. period</th><th class=\"net\">Notif. Iv.</th>\n";
                    echo "<th class=\"group\">NR</th><th class=\"group\">NC</th><th class=\"group\">NW</th><th class=\"group\">NU</th>\n";
                    echo "</tr>\n";
                    foreach ($nag_service_templates as $idx=>$stuff) {
                        if ($idx) {
                            echo "<tr><td class=\"name\"><input type=checkbox name=\"nag_st_del_$idx\"/>$stuff->name</td>\n";
                            echo "<td class=\"group\"><input type=hidden name=\"nag_st_$idx\" value=\"set\"/><input type=checkbox name=\"nag_st_vol_$idx\"";
                            if ($stuff->volatile) echo " checked ";
                            echo "/></td>\n";
                            echo "<td class=\"type\"><select name=\"nag_st_nscp_$idx\">";
                            foreach ($nag_periods as $p_idx=>$p_stuff) {
                                echo "<option value=\"$p_idx\" ";
                                if ($stuff->nsc_period==$p_idx) echo " selected ";
                                echo ">$p_stuff->name</option>\n";
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"net\"><select name=\"nag_st_ma_$idx\">";
                            foreach ($max_attempts_f as $m_idx=>$m_name) {
                                echo "<option value=\"$m_idx\" ";
                                if ($stuff->max_attempts==$m_idx) echo " selected ";
                                echo ">$m_name</option>\n";
                            }
                            echo "</select></td>\n";
                            foreach (array("ci"=>"check","ri"=>"retry") as $short=>$long) {
                                $vname="{$long}_interval";
                                echo "<td class=\"net\"><select name=\"nag_st_{$short}_$idx\">";
                                foreach ($interval_f as $i_idx=>$i_name) {
				    if ($i_idx) {
					echo "<option value=\"$i_idx\"";
					if ($i_idx==$stuff->$vname) echo " selected ";
					echo ">$i_name</option>\n";
				    }
                                }
                                echo "</select></td>\n";
                            }
                            echo "<td class=\"type\"><select name=\"nag_st_nsnp_$idx\">";
                            foreach ($nag_periods as $p_idx=>$p_stuff) {
                                echo "<option value=\"$p_idx\" ";
                                if ($stuff->nsn_period==$p_idx) echo " selected ";
                                echo ">$p_stuff->name</option>\n";
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"net\"><select name=\"nag_st_ni_$idx\">";
                            foreach ($interval_f as $i_idx=>$i_name) {
                                echo "<option value=\"$i_idx\"";
                                if ($i_idx==$stuff->ninterval) echo " selected ";
                                echo ">$i_name</option>\n";
                            }
                            echo "</select></td>\n";
                            foreach (array("r"=>"nrecovery","c"=>"ncritical","w"=>"nwarning","u"=>"nunknown") as $short=>$long) {
                                echo "<td class=\"group\"><input type=checkbox name=\"nag_st_n{$short}_$idx\" ";
                                if ($stuff->$long) echo " checked ";
                                echo "/></td>\n";
                            }
                            echo "</tr>\n";
                        }
                    }
                    echo "<tr><td class=\"name\"><input type=checkbox name=\"nagnewservtemp\" />";
                    echo "<input name=\"nagnewservtempname\" maxlength=\"60\" size=\"20\" value=\"templ\"/></td>\n";
                    echo "<td class=\"group\"><input type=checkbox name=\"nagnewservtemp_vol\"/></td>\n";
                    echo "<td class=\"type\"><select name=\"nagnewservtemp_nscp\">";
                    foreach ($nag_periods as $p_idx=>$p_stuff) echo "<option value=\"$p_idx\">$p_stuff->name</option>\n";
                    echo "</select></td>\n";
                    echo "<td class=\"net\"><select name=\"nagnewservtemp_ma\">";
                    foreach ($max_attempts_f as $m_idx=>$m_name) echo "<option value=\"$m_idx\">$m_name</option>\n";
                    echo "</select></td>\n";
                    echo "<td class=\"net\"><select name=\"nagnewservtemp_ci\">";
                    foreach ($interval_f as $i_idx=>$i_name) {
			if ($i_idx) echo "<option value=\"$i_idx\">$i_name</option>\n";
		    }
                    echo "</select></td>\n";
                    echo "<td class=\"net\"><select name=\"nagnewservtemp_ri\">";
                    foreach ($interval_f as $i_idx=>$i_name) {
			if ($i_idx) echo "<option value=\"$i_idx\">$i_name</option>\n";
		    }
                    echo "</select></td>\n";
                    echo "<td class=\"type\"><select name=\"nagnewservtemp_nsnp\">";
                    foreach ($nag_periods as $p_idx=>$p_stuff) echo "<option value=\"$p_idx\">$p_stuff->name</option>\n";
                    echo "</select></td>\n";
                    echo "<td class=\"net\"><select name=\"nagnewservtemp_ni\">";
                    foreach ($interval_f as $i_idx=>$i_name) echo "<option value=\"$i_idx\">$i_name</option>\n";
                    echo "</select></td>\n";
                    foreach (array("r"=>1,"c"=>1,"w"=>0,"u"=>0) as $act_ns=>$act_def) {
                        echo "<td class=\"group\"><input type=checkbox name=\"nagnewservtemp_n$act_ns\" ";
                        if ($act_def) echo " checked ";
                        echo "/></td>\n";
                    }
                    echo "</tr>\n";
                    echo "</table>";
                    if (count($nag_service_templates)-1) {
                        message("Device templates",$type=1);
                        echo "<table class=\"normal\">\n";
                        echo "<tr><th class=\"name\">Name</th><th class=\"net\">Default</th><th class=\"group\">Service template</th><th class=\"net\">Max attempts</th>\n";
                        echo "<th class=\"net\">Not. Iv.</th><th class=\"type\">Notif. period</th>\n";
                        echo "<th class=\"group\">NR</th><th class=\"group\">ND</th><th class=\"group\">NU</th>\n";
                        echo "</tr>\n";
                        $default_set=0;
                        foreach ($nag_device_templates as $idx=>$stuff) {
                            if ($idx) {
                                echo "<tr><td class=\"name\"><input type=checkbox name=\"nag_dt_del_$idx\"/>$stuff->name</td>\n";
                                echo "<td class=\"net\"><input type=radio name=\"nag_devtemp_def\" value=\"$idx\" ";
                                if ($stuff->is_default) {
                                    echo " checked ";
                                    $default_set=$idx;
                                }
                                echo "/></td>\n";
                                echo "<td class=\"group\"><input type=hidden name=\"nag_dt_$idx\" value=\"set\"/>";
                                echo "<select name=\"nag_dt_st_$idx\">\n";
                                foreach ($nag_service_templates as $ns_idx=>$ns_stuff) {
                                    if ($ns_idx) {
                                        echo "<option value=\"$ns_idx\" ";
                                        if ($stuff->ng_service_templ==$ns_idx) echo " selected ";
                                        echo ">$ns_stuff->name</option>\n";
                                    }
                                }
                                echo "</select></td>\n";
                                echo "<td class=\"net\"><select name=\"nag_dt_ma_$idx\">";
                                foreach ($max_attempts_f as $m_idx=>$m_name) {
                                    echo "<option value=\"$m_idx\" ";
                                    if ($stuff->max_attempts==$m_idx) echo " selected ";
                                    echo ">$m_name</option>\n";
                                }
                                echo "</select></td>\n";
                                echo "<td class=\"net\"><select name=\"nag_dt_ni_$idx\">";
                                foreach ($interval_f as $i_idx=>$i_name) {
                                    echo "<option value=\"$i_idx\"";
                                    if ($i_idx==$stuff->ninterval) echo " selected ";
                                    echo ">$i_name</option>\n";
                                }
                                echo "</select></td>\n";
                                echo "<td class=\"type\"><select name=\"nag_dt_nsnp_$idx\">";
                                foreach ($nag_periods as $p_idx=>$p_stuff) {
                                    echo "<option value=\"$p_idx\" ";
                                    if ($stuff->ng_period==$p_idx) echo " selected ";
                                    echo ">$p_stuff->name</option>\n";
                                }
                                echo "</select></td>\n";
                                foreach (array("r"=>"nrecovery","d"=>"ndown","u"=>"nunreachable") as $short=>$long) {
                                    echo "<td class=\"group\"><input type=checkbox name=\"nag_dt_n{$short}_$idx\" ";
                                    if ($stuff->$long) echo " checked ";
                                    echo "/></td>\n";
                                }
                                echo "</tr>\n";
                            }
                        }
                        echo "<tr><td class=\"name\"><input type=checkbox name=\"nagnewdevtemp\" />";
                        echo "<input name=\"nagnewdevtempname\" maxlength=\"60\" size=\"20\" value=\"dtempl\"/></td>\n";
                        echo "<td class=\"net\"><input type=radio name=\"nag_devtemp_def\" value=\"new\" ";
                        if (!$default_set) echo " checked ";
                        echo "/></td>\n";
                        echo "<td class=\"group\"><select name=\"nagnewdevst\">\n";
                        foreach ($nag_service_templates as $ns_idx=>$ns_stuff) {
                            if ($ns_idx) echo "<option value=\"$ns_idx\">$ns_stuff->name</option>\n";
                        }
                        echo "</select></td>\n";
                        echo "<td class=\"net\"><select name=\"nagnewdevtemp_ma\">";
                        foreach ($max_attempts_f as $m_idx=>$m_name) echo "<option value=\"$m_idx\">$m_name</option>\n";
                        echo "</select></td>\n";
                        echo "<td class=\"net\"><select name=\"nagnewdevtemp_ni\">";
                        foreach ($interval_f as $i_idx=>$i_name) echo "<option value=\"$i_idx\">$i_name</option>\n";
                        echo "</select></td>\n";
                        echo "<td class=\"type\"><select name=\"nagnewdevtemp_nsnp\">";
                        foreach ($nag_periods as $p_idx=>$p_stuff) echo "<option value=\"$p_idx\">$p_stuff->name</option>\n";
                        echo "</select></td>\n";
                        foreach (array("r"=>1,"d"=>1,"u"=>0) as $act_ns=>$act_def) {
                            echo "<td class=\"group\"><input type=checkbox name=\"nagnewdevtemp_n$act_ns\" ";
                            if ($act_def) echo " checked ";
                            echo "/></td>\n";
                        }
                        echo "</tr>\n";
                        echo "</table>";
                    } else {
                        message("No Service-templates defined");
                    }
                } else {
                    message("No timeperiods defined so far...",$type=1);
                }
                echo "<div class=\"center\"><input type=submit value=\"submit\"></div></form>";
                echo "</form>\n";
# -- device ----------------------------------------------------
            } else if ($dtype=="cg_devices") {
# -- device ----------------------------------------------------
                message("Device config");
                //print_r($devs);
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"delnew\">del</th><th class=\"name\">Device name</th><th class=\"group\">Devicegroup</th><th class=\"select\">SNMP-class</th>\n";
                echo "<th class=\"type\">Device type</th><th class=\"net\">Bootdev</th><th class=\"select\">Bootserver</th></tr>\n";
                $last_g=-1;
                foreach ($devs as $dev_idx=>$dev) {
                    if (!$dev_groups[$dev->device_group]->cluster_device_group) {
                        if ($dev->device_group != $last_g) {
                            $last_g=$dev->device_group;
                            echo "<tr><td class=\"netnew\" colspan=\"7\" >DeviceGroup {$dev_groups[$last_g]->name}</td></tr>\n";
                        }
                        if ($dev->identifier != "MD") {
                        echo "<tr>";
                        echo "<td class=\"delnew\"><input type=checkbox name=\"deldev_$dev_idx\" /></td>";
                        echo "<td class=\"name\"><input name=\"devname_$dev_idx\" maxlength=\"60\" size=\"20\" value=\"$dev->name\"/>";
                        if ($dev->comment) echo ", $dev->comment";
                        echo "</td>";
                        echo "<td class=\"group\"><select name=\"devgroup_$dev_idx\">";
                        foreach ($dev_groups as $dg_idx=>$dev_group) {
                            if (!$dev_group->cluster_device_group) {
                                echo "<option value=\"$dg_idx\" ";
                                if ($dev->device_group == $dg_idx) echo " selected ";
                                echo ">$dev_group->name</option>\n";
                            }
                        }
                        echo "</select></td>";
                        echo "<td class=\"select\"><select name=\"devsnmp_$dev_idx\">";
                        foreach ($snmp_classes as $snmp_idx=>$snmp_stuff) {
                            echo "<option value=\"$snmp_idx\" ";
                            if ($dev->snmp_class == $snmp_idx) echo " selected ";
                            echo ">$snmp_stuff->name ($snmp_stuff->update_freq)</option>\n";
                        }
                        echo "</select></td>";
                        echo "<td class=\"type\"><select name=\"devtype_$dev_idx\">";
                        foreach ($dev_types as $dg_idx=>$dev_type) {
                            echo "<option value=\"$dg_idx\" ";
                            if ($dev->device_type == $dg_idx) echo " selected ";
                            echo ">$dev_type->description ($dev_type->identifier)</option>\n";
                        }
                        echo "</select></td>";
                        echo "<td class=\"net\">";
                        if (count($dev->boot_devs)) {
                            echo "<select name=\"bootnetdevice_$dev_idx\">";
                            echo "<option value=\"0\">None</option>\n";
                            foreach ($dev->boot_devs as $bdn=>$bdi) {
                                echo "<option value=\"$bdi\"";
                                if ($bdi == $dev->bootnetdevice) echo " selected ";
                                echo ">$bdn</option>\n";
                            }
                            echo "</select>";
                        } else {
                            echo "<input type=hidden name=\"bootnetdevice_$dev_idx\" value=\"0\" />&nbsp;";
                        }
                        echo "</td>";
                        echo "<td class=\"select\">";
                        if (count($boot_server)) {
                            echo "<select name=\"devbootserver_$dev_idx\">";
                            echo "<option value=\"0\">None</option>\n";
                            foreach ($boot_server as $idx=>$name) {
                                echo "<option value=\"$idx\" ";
                                if ($idx == $dev->bootserver) echo " selected ";
                                echo ">$name</option>\n";
                            }
                            echo "</select>";
                        } else {
                            echo "<input type=hidden name=\"devbootserver_$dev_idx\" value=\"0\" />&nbsp;";
                        }
                        echo "</td>";
                        echo "</tr>\n";
                        }
                    }
                }
                echo "<tr><th class=\"delnew\">New</th><th class=\"type\" colspan=\"6\" >New device(s)</th></tr>\n";
                echo "<tr>";
                echo "<td class=\"nameup\" colspan=\"2\"><input name=\"newdevname\" maxlength=\"60\" size=\"20\" value=\"\"/></td>";
                echo "<td class=\"group\"><select name=\"newdevgroup\">";
                foreach ($dev_groups as $dg_idx=>$dev_group) {
                    if (!$dev_group->cluster_device_group) echo "<option value=\"$dg_idx\">$dev_group->name</option>\n";
                }
                echo "</select></td>";
                echo "<td class=\"select\"><select name=\"newdevsnmp\">";
                foreach ($snmp_classes as $snmp_idx=>$snmp_stuff) {
                    echo "<option value=\"$snmp_idx\" >$snmp_stuff->name ($snmp_stuff->update_freq)</option>\n";
                }
                echo "</select></td>";
                echo "<td class=\"type\"><select name=\"newdevtype\">";
                foreach ($dev_types as $dg_idx=>$dev_type) {
                    echo "<option value=\"$dg_idx\">$dev_type->description ($dev_type->identifier)</option>\n";
                }
                echo "</select></td>";
                echo "<td class=\"net\">&nbsp;</td>\n";
                echo "<td class=\"select\">";
                if (count($boot_server)) {
                    echo "<select name=\"newdevbootserver\">";
                    echo "<option value=\"0\">None</option>\n";
                    foreach ($boot_server as $idx=>$name) {
                        echo "<option value=\"$idx\">$name</option>\n";
                    }
                    echo "</select>";
                } else {
                    echo "<input type=hidden name=\"newdevbootserver\" value=\"0\" />&nbsp;";
                }
                echo "</td>";
                echo "</tr>";
                echo "<tr><td class=\"name\" colspan=\"3\">Ref. device: ";
                echo "<select name=\"newdevrefdev\" >";
                echo "<option value=\"0\" selected >None</option>\n";
                foreach ($all_devices as $devn=>$dev_stuff) {
                    list($dev_g)=$dev_stuff;
                    echo "<option value=\"0\" >$devn ({$dev_groups[$dev_g]->name})</option>\n";
                }
                echo "</select>";
                echo "</td>\n";
                echo "<td class=\"group\" colspan=\"5\">Range: <input type=checkbox name=\"newdevrange\" />&nbsp;;&nbsp;\n";
                echo "Number of digits:<select name=\"ndr_digits\">";
                for ($r=1;$r<5;$r++) {
                    echo "<option value=\"$r\">$r</option>\n";
                }
                echo "</select>&nbsp;;&nbsp;\n";
                echo "from <input name=\"ndr_lower\" maxlength=\"8\" size=\"10\" value=\"1\"/>&nbsp;&nbsp;";
                echo "to <input name=\"ndr_upper\" maxlength=\"8\" size=\"10\" value=\"16\"/></td>";
                echo "</tr>\n";
                echo "</table>\n";
                echo "<div class=\"center\"><input type=submit value=\"submit\"></div></form>";
# -- SNMP ----------------------------------------------------
            } else if ($dtype=="cg_snmp") {
# -- SNMP ----------------------------------------------------
                message("SNMP config");
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                echo $hiddenmach;
                echo $hiddendtype;
                echo $hiddensctype;
                $all_mvts=array("i"=>"Integer","f"=>"Float");
                $all_units=array("1","1/s","Byte","Byte/s","%","C","RPM","s","A");
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"delnew\">del</th><th class=\"name\">Name</th><th class=\"group\">Descr</th><th class=\"select\">MIB</th>\n";
                echo "<th class=\"type\">RRD key</th><th class=\"net\">unit</th><th class=\"select\">Base</th><th class=\"name\">Factor</th><th class=\"group\">Var_Type</th></tr>\n";
                foreach ($all_snmp_mibs as $idx=>$snmp_stuff) {
                    echo "<tr>";
                    echo "<td class=\"delnew\"><input type=checkbox name=\"delmib_$idx\"/></td>\n";
                    echo "<td class=\"name\">$snmp_stuff->name</td>\n";
                    echo "<td class=\"group\">$snmp_stuff->descr</td>\n";
                    echo "<td class=\"select\">$snmp_stuff->mib</td>\n";
                    echo "<td class=\"type\">$snmp_stuff->rrd_key</td>\n";
                    echo "<td class=\"net\"><select >";
                    foreach ($all_units as $unit) {
                        echo "<option value=\"$unit\" ";
                        if ($snmp_stuff->unit == $unit) echo " selected ";
                        echo ">$unit</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "<td class=\"select\">$snmp_stuff->base</td>\n";
                    echo "<td class=\"name\">$snmp_stuff->factor</td>\n";
                    echo "<td class=\"group\">{$all_mvts[$snmp_stuff->var_type]}</td>\n";
                    echo "</tr>\n";
                }
                echo "<tr>";
                echo "<td class=\"delnew\"><input type=checkbox name=\"newmib\"/></td>\n";
                echo "<td class=\"name\"><input name=\"newmibname\" size=\"20\" maxlength=\"63\" value=\"newmib\" /></td>\n";
                echo "<td class=\"group\"><input name=\"newmibdescr\" size=\"20\" maxlength=\"254\" value=\"description\"/></td>\n";
                echo "<td class=\"select\"><input name=\"newmibmib\" size=\"24\" maxlength=\"127\" value=\".\"/></td>\n";
                echo "<td class=\"type\"><input name=\"newmibkey\" size=\"8\" maxlength=\"63\" value=\"\"/></td>\n";
                echo "<td class=\"net\"><select name=\"newmibunit\" >";
                foreach ($all_units as $unit) {
                    echo "<option value=\"$unit\">$unit</option>\n";
                }
                echo "</select></td>\n";
                echo "<td class=\"select\"><input name=\"newmibbase\" size=\"8\" maxlength=\"20\" value=\"1\"/></td>\n";
                echo "<td class=\"name\"><input name=\"newmibfactor\" size=\"8\" maxlength=\"20\" value=\"1.\"/></td>\n";
		
                echo "<td class=\"group\"><select name=\"newmibvart\">";
                foreach ($all_mvts as $tp=>$descr) {
                    echo "<option value=\"$tp\">$descr</option>\n";
                }
                echo "</select>";
                echo "</td>\n";
                echo "</tr>\n";
                echo "</table>\n";
                echo "<div class=\"center\"><input type=submit value=\"submit\"></div></form>";
            } else {
                message("Unknown config-type $dtype");
            }
        }
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
