<?php
//
// Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
//
// Send feedback to: <lang@init.at>
// 
// This file belongs to the webfrontend package
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
require_once "htmltools.php";
function get_display_list($vars,$presel_str="",$tables=array(),$plain=0,$ignore_meta_dev=1) {
    $varkeys=array_keys($vars);
    $actgroup="none";
    // parse additional tables
    $add_tables="";
    foreach ($tables as $short=>$long) $add_tables.=", $long $short";
    $machgroups=array();
    $num_mach=0;
    if ($ignore_meta_dev) {
        $sql_md_str=" dt.identifier != 'MD' AND ";
    } else {
        $sql_md_str="";
    }
    //$machgroups[$actgroup]=array(-1,0,0,array());
    // new code
    if ($plain) {
        $mres=query("SELECT DISTINCT d.name,dg.name AS dgname,dg.device_group_idx FROM device_group dg,  device_type dt $add_tables, device d WHERE d.device_group=dg.device_group_idx AND $sql_md_str d.device_type=dt.device_type_idx $presel_str ORDER BY dg.name,d.name");
    } else {
        $mres=query("SELECT DISTINCT d.name,dg.name AS dgname,dg.device_group_idx FROM device_group dg, netdevice n, device_type dt $add_tables, device d WHERE d.device_group=dg.device_group_idx AND $sql_md_str d.device_type=dt.device_type_idx AND n.device=d.device_idx $presel_str ORDER BY dg.name,d.name");
    }
    while ($mfr=mysql_fetch_object($mres)) {
        if (!in_array($mfr->dgname,array_keys($machgroups))) $machgroups[$mfr->dgname]=array("idx"=>$mfr->device_group_idx,"num"=>0,"selected"=>0,"list"=>array(),"description"=>$mfr->dgname);
        if ($mfr->name) {
            $num_mach++;
            $machgroups[$mfr->dgname]["num"]++;
            $machgroups[$mfr->dgname]["list"][]=$mfr->name;
        }
    }
    // old code
    if (0) {
        $mres=query("SELECT d.name,d.device_group_idx FROM device_group d");
        while ($mfr=mysql_fetch_object($mres)) {
            if ($plain) {
                $mr2=query("SELECT DISTINCT d.name FROM device d, device_type dt $add_tables WHERE $sql_md_str d.device_group=$mfr->device_group_idx AND d.device_type=dt.device_type_idx $presel_str");
            } else {
                $mr2=query("SELECT DISTINCT d.name FROM device d, netdevice n, device_type dt $add_tables WHERE $sql_md_str d.device_group=$mfr->device_group_idx AND d.device_type=dt.device_type_idx AND n.device=d.device_idx $presel_str");
            }
            $act_list=array();
            if (mysql_num_rows($mr2)) {
                $num_mach+=mysql_num_rows($mr2);
                while ($mfr2=mysql_fetch_object($mr2)) {
                    $act_list[]=$mfr2->name;
                }
                $machgroups[$mfr->name]=array("idx"=>$mfr->device_group_idx,"num"=>mysql_num_rows($mr2),"selected"=>0,"list"=>$act_list,"description"=>$mfr->name);
            }
        }
    }
    $hiddenmach="";
    $mlist=array();
    if (in_array("selgroup",$varkeys)) {
        foreach ($vars["selgroup"] as $group) {
            if (in_array($group,array_keys($machgroups))) {
                $machgroups[$group]["selected"]=1;
                foreach ($machgroups[$group]["list"] as $mach) $mlist[]=$mach;
            }
        }
    }
    if (in_array("selmach",$varkeys)) $mlist=array_merge($vars["selmach"],$mlist);
    if (in_array("selmachmac",$varkeys)) $mlist=array_merge($vars["selmachmac"],$mlist);
    $mlist=array_unique($mlist);
    foreach (array_keys($machgroups) as $group) {
        $a_tg=array_values($machgroups[$group]["list"]);
        $a_is=array_values(array_intersect(array_values($mlist),$a_tg));
        sort($a_is);
        sort($a_tg);
        if ($a_is == $a_tg) {
            $machgroups[$group]["selected"]=1;
            $hiddenmach.="<input type=hidden name=\"selgroup[]\" value=\"$group\" />\n";
        }
    }
    if (count($mlist)) {
        $optsel="AND ( d.name='".implode("' OR d.name='",$mlist)."' )";
    } else {
        $optsel="AND 0";
    }
    $mres=query("SELECT d.name,dg.name as dgname FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx $optsel");
    if (mysql_num_rows($mres)) {
        while ($mfr=mysql_fetch_object($mres)) {
            $hiddenmach.="<input type=hidden name=\"selmach[]\" value=\"$mfr->name\" />\n";
        }
    }
    if ($plain) {
        $mres=query("SELECT d.name,dg.name AS dgname FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx $optsel");
    } else {
        $mres=query("SELECT d.name,dg.name AS dgname FROM device d, device_group dg, netdevice n WHERE n.device=d.device_idx AND d.device_group=dg.device_group_idx $optsel");
    }
    $mmachgroups=array();
    while ($mfr=mysql_fetch_object($mres)) {
        $mmachgroups[$mfr->name]=$mfr->dgname;
    }
    $unique_mgs=array_values(array_unique(array_values($mmachgroups)));
    asort($unique_mgs);
    $mach_mg_a=array_count_values(array_values($mmachgroups));
    // build array for the display of the machine(s)
    // format: [key:machinegroup]=>(num_mach,tot_mach,array(machs))
    $display_a=array();
    foreach ($unique_mgs as $idx=>$grp_name) {
        $mach_array=array();
        foreach ($mmachgroups as $machname=>$grpname) {
            if ($grpname == $grp_name) $mach_array[]=$machname;
        }
        sort($mach_array);
        $display_a[$grp_name]=array($mach_mg_a[$grp_name],$machgroups[$grp_name]["num"],$mach_array);
    }
    $actmach=array_keys($mmachgroups);
    // return array: display-array, machgroup-array, hidden machine(group) selection string, array of actual machines, mysql-preselection string
    return array($display_a,$machgroups,$hiddenmach,$actmach,$optsel);
}
function optimize_hostlist($hlist) {
    $tlist=array();
    foreach ($hlist as $acth) {
        preg_match("/^(\D+)(\d*)$/",$acth,$ahs);
        $mnp=$ahs[1];
        $rn=(int)$ahs[2];
        if (!in_array($mnp,array_keys($tlist))) {
            $tlist[$mnp]=array();
        }
        $tlist[$mnp][$rn]=$ahs[2];
        //echo $ahs[1]." - ".$rn."*<br>";
    }
    $nhlist=array();
    foreach ($tlist as $mnp=>$ahl) {
        ksort($ahl);
        $oidx=-6666;
        $sidx=-6666;
        $ohl=array();
        foreach (array_keys($ahl) as $idx) {
            $nadd=1;
            if ($idx != $oidx+1) {
                if ($sidx != -6666) {
                    $ohl[]=get_noderange_str($sidx,$oidx,$mnp,$ahl);
                }
                $sidx=$idx;
            }
            $oidx=$idx;
        }
        if ($nadd) {
            $ohl[]=get_noderange_str($sidx,$oidx,$mnp,$ahl);
        }
        $nhlist[]=implode(" ; ",$ohl);
    }
    return implode(" : ",$nhlist);
}
function get_noderange_str($n1,$n2,$pfix,$field) {
    $f1=$field[$n1];
    $f2=$field[$n2];
    if ($n1 == $n2) {
        return "$pfix$f1";
    } else if ($n1+1 == $n2) {
        return "$pfix$f1/$f2";
    } else {
        return "$pfix$f1-$pfix$f2";
    }
}
function split_ip($ip) {
    $ret_f=array();
    foreach (explode(".",$ip) as $ip_sp) $ret_f[]=(int)$ip_sp;
    return $ret_f;
}
function get_netbits($mask) {
    $decmask=0;
    foreach (explode(".",$mask) as $msk) {
        $decmask=$decmask*256+(int)$msk;
    }
    $bits=32;
    while (!($decmask & 1) && $bits) {
        $bits--;
        $decmask=($decmask>>1);
    }
    if ($bits == 8) {
      return "A";
    } else if ($bits == 16) {
      return "B";
    } else if ($bits == 24) {
      return "C";
    } else {
      return "$bits";
    }
}
// IP-stuff
function is_ip($ip) {
    $is_i=0;
    $ip_p=explode(".",$ip);
    if (count($ip_p) == 4) {
        $num_ok=0;
        foreach ($ip_p as $ip_sp) {
            $ip_i=(int)$ip_sp;
            if (strval($ip_i)==$ip_sp && $ip_i >= 0 && $ip_i <=255) $num_ok++;
        }
        if ($num_ok==4) $is_i=1;
    }
    return $is_i;
}
function increase_ip($ip,$incr=1) {
    $ip_f=explode(".",$ip);
    if ($incr) {
        $ip_f[3]=strval(((int)$ip_f[3])+1);
        if ($ip_f[3]=="256") {
            $ip_f[3]="0";
            $ip_f[2]=strval(((int)$ip_f[2])+1);
        }
    }
    return implode(".",$ip_f);
}
function valid_ip($ip,$net_idx,$nets) {
    $val_i=0;
    if (is_ip($ip)) {
        $check_net=$nets[$net_idx];
        $ip_p=split_ip($ip);
        $nm_p=split_ip($check_net->netmask);
        $nw_p=split_ip($check_net->network);
        $val_i=1;
        for ($idx=0;$idx<4;$idx++) {
            if (($ip_p[$idx]&$nm_p[$idx]) != $nw_p[$idx]) {
                $val_i=0;
                break;
            }
        }
    }
    return $val_i;
}
function is_netdev_name($ndn) {
    $is_nd=0;
    if ($ndn=="lo" || preg_match("/^(eth|myri|nbi)\d+:*\d*$/",$ndn)) $is_nd=1;
    return $is_nd;
}
function is_macaddr($mac) {
    $is_m=0;
    $mac=strtolower($mac);
    if ($mac) {
        if (preg_match("/^([a-f0-9]{2}:){5}[a-f0-9]{2}$/",$mac)) $is_m=1;
    }
    return $is_m;
}
function is_set($name,&$vars) {
    if (isset($vars[$name]) && $vars[$name]) {
        return 1;
    } else {
        return 0;
    }
}
function process_ret(&$ls,$server,$port,$command,$ret_str,$nodes) {
    if (preg_match("/^ok (.*)$/",$ret_str,$ret_p)) {
        $idx=0;
        $res_array=array();
        $ret_p=explode("#",$ret_p[1]);
        $main_res=array_shift($ret_p);
        $ls->add_message("Sending $command to $server (port $port), ".get_plural("device",count($nodes),1).": ".optimize_hostlist($nodes),$main_res,1);
        foreach ($ret_p as $mach_res) {
            $node=$nodes[$idx++];
            if (preg_match("/^error .*$/",$mach_res)) {
                $suc=0;
            } else if (preg_match("/^warn .*$/",$mach_res)) {
                $suc=2;
            } else {
                $suc=1;
            }
            if (!in_array($mach_res,array_keys($res_array))) $res_array[$mach_res]=array(array(),$suc);
            $res_array[$mach_res][0][]=$node;
        }    
        foreach ($res_array as $mach_res=>$stuff) {
            list($mlist,$suc)=$stuff;
            $ls->add_message("&nbsp;&nbsp;-&nbsp;&nbsp;node result for ".optimize_hostlist($mlist),$mach_res,$suc);
        }
    } else {
        $ls->add_message("Cannot send $command to $server (port $port) ".optimize_hostlist($nodes),$ret_str,0);
    }
}
?>
