<?php
//-*ics*- ,CAP,name:'apc',descr:'APC control',defvalue:0,enabled:1,scriptname:'/php/apccontrol.php',left_string:'APC Control',right_string:'APC Masterswitches',capability_group_name:'conf',pri:0
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
require_once "apctools.php";
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["apc_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    // possible values (excluding single-apc view "so")
    $sellist=array("overview"=>array("Overview","ov"),
                   "power-on-delays"=>array("Power on delays","po"));
                   //"control"=>array("Cluster control","co"));
    // default value
    $actapc="overview";
    $var_keys=array_keys($vars);
    if (in_array("apcsel",$var_keys)) {
        $actapc=$vars["apcsel"];
    } else if (in_array("selmach",$var_keys)) {
        $actmach=$vars["selmach"];
        $mres=query("SELECT d.name FROM msoutlet m, device d WHERE m.device=d.device_idx AND m.msoutlet_idx=$actmach");
        if (mysql_affected_rows()==1) {
            $mfr=mysql_fetch_object($mres);
            $actapc=$mfr->name;
        }
    }
    $apccommand="so";
    foreach($sellist as $c_v=>$c_s) {
        if ($c_v==$actapc) $apccommand=$c_s[1];
    }
    htmlhead();
    clusterhead($sys_config,"APC control page",$style="formate.css",
                array("th.apcname"=>array("background-color:#eeeeff"),
                      "td.apcname"=>array("background-color:#ccccee","text-align:left"),
                      "td.apcnameup"=>array("background-color:#ccccee","text-align:left"),
                      "td.apcnamedown"=>array("color:#ffffff","background-color:#ff5555","text-align:left"),
                      "th.apcf0"=>array("background-color:#ffeeff"),
                      "td.apcf0"=>array("background-color:#eeddee","text-align:center"),
                      "td.apcf0up"=>array("background-color:#eeddee","text-align:center"),
                      "td.apcf0down"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "th.apcf1"=>array("background-color:#eeeeff"),
                      "td.apcf1"=>array("background-color:#eeeeee","text-align:center"),
                      "td.apcf1up"=>array("background-color:#eeeedd","text-align:center"),
                      "td.apcf1down"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "th.apcf2"=>array("background-color:#ffeedd"),
                      "td.apcf2"=>array("background-color:#eeddcc","text-align:center"),
                      "td.apcf2up"=>array("background-color:#eedddd","text-align:center"),
                      "td.apcf2down"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "input.apcoffl"=>array("background-color:#ff8888","font-size:large"),
                      "input.apconl"=>array("background-color:#88ff88","font-size:large")
                      )
                );
    clusterbody($sys_config,"APC control",array("bc"),array("conf"));

    // log status
    $log_status=get_log_status();
    $ucl=usercaps($sys_db_con);
    if ($ucl["apc"]) {
        $boot_server=array();
        $do_list=array();
        $mres=query("SELECT d.device_idx,d.name FROM device d, deviceconfig dc, config c WHERE dc.device=d.device_idx AND dc.config=c.config_idx AND c.name='mother_server'");
        while ($mfr=mysql_fetch_object($mres)) {
            $boot_server[$mfr->device_idx]=$mfr->name;
            $do_list[$mfr->name]=array();
        }
        $apclist=array();
        $apcs=array();
        $mres=query("SELECT d.device_idx,d.name,i.ip,d.bootserver FROM device d, device_type dt, netip i, netdevice n WHERE dt.device_type_idx=d.device_type AND dt.identifier='AM' AND i.netdevice=n.netdevice_idx AND n.device=d.device_idx AND d.bootserver > 0 ORDER BY d.name");
        $first_apc=0;
        $apc_resolve_dict=array();
        while ($mfr=mysql_fetch_object($mres)) {
            $apcs[$mfr->device_idx]=new apc($mfr->ip,$mfr->name,$mfr->device_idx,$mfr->bootserver);
            $apclist[$mfr->name]=$mfr->device_idx;
            if (!$first_apc++) $sellist["-"]=array("----------------","");
            $sellist[$mfr->name]=array("APC $mfr->name (bs=".$boot_server[$mfr->bootserver].")","");
            $apc=&$apcs[$mfr->device_idx];
            $apc_resolve_dict[$apc->ip]=&$apc;
            // limit list of apcs to check
            if ($apccommand != "so" || ($apccommand == "so" && $mfr->name==$actapc)) $do_list[$boot_server[$mfr->bootserver]][]=$apc->ip;
        }
        update_apc_info($sys_config,$do_list,$apc_resolve_dict);
        $mres=query("SELECT d.device_idx,d.name,m.slave_info,d.comment,m.device,m.outlet,m.msoutlet_idx,dg.name AS dgname FROM device d, device_group dg,msoutlet m WHERE dg.device_group_idx=d.device_group AND m.slave_device=d.device_idx ORDER BY d.name");
        $mctmlist=array();
        $machcon=0;
        while ($mfr=mysql_fetch_object($mres)) {
            $machcon=1;
            $mctmlist[$mfr->msoutlet_idx]=array($mfr->name,$mfr->device,$mfr->outlet,$mfr->comment,$mfr->slave_info);
            if (isset($apcs[$mfr->device])) {
                $apcs[$mfr->device]->set_outlet_info($mfr->outlet,$mfr->name,$mfr->dgname,$mfr->device_idx,$mfr->comment,$mfr->slave_info);
            }
        }
        $mess_str="Please select APC";
        if ($machcon) $mess_str.=" or device:";
        message($mess_str);
        echo "<table class=\"simplesmall\"><tr>";
        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=get>";
        echo "<td>";
        hidden_sid();
        echo "<select name=\"apcsel\" size=\"5\">";
        foreach (array_keys($apcs) as $apcn) {
            //echo "$apcn<br>";
            $apcref=&$apcs[$apcn];
            $mres2=query("SELECT DISTINCT dg.name FROM device_group dg, device d, msoutlet m WHERE d.device_group=dg.device_group_idx AND m.device=$apcref->idx AND m.slave_device=d.device_idx");
            $mga=array();
            while ($mfr2=mysql_fetch_object($mres2)) $mga[]=$mfr2->name;
            $apcref->groups=implode("; ",$mga);
        }
        foreach ($sellist as $mg=>$mg_a) {
            list($name,$bla)=$mg_a;
            echo "<option value=\"$mg\"";
            if ($mg == "-")  echo " disabled ";
            if ($mg == $actapc) echo " selected ";
            echo ">$name";
            if (in_array($mg,array_keys($apclist))) {
                if (strlen($apcs[$apclist[$mg]]->groups)) echo " [ ".$apcs[$apclist[$mg]]->groups." ]";
            }
        }
        echo "</select>";
        echo "</td><td>";
        echo "<input type=submit value=\"select\" />\n";
        echo "</td></form>";
        //echo "</form>";
        if ($machcon) {
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=get>";
            echo "<td>&nbsp;&nbsp;</td><td>";
            hidden_sid();
            echo "<select name=\"selmach\" size=\"5\" >";
            foreach ($mctmlist as $mctm=>$msw_vars) {
                echo "<option value=\"$mctm\" ";
                if (isset($actmach) && $mctm==$actmach) echo " selected ";
                list($msn,$msw,$msout,$msc,$msi)=$msw_vars;
                $apc=&$apcs[$msw];
                if ($msc) $msn.=" ($msc)";
                echo ">$msn on $apc->name, outlet $msout";
                if ($msi) echo ", $msi";
            }
            echo "</select></td><td><input type=submit value=\"select\" /></td></form>\n";
        }
        echo "</tr></table>\n";
        if ($apccommand=="so") {
	    $hcproto=new messagelog();
            foreach ($apcs as $apcnum=>$apc_x) {
                if ($apc_x->name == $actapc) {
                    $sstr=$apc_x->create_apc_string($sys_config,$vars,$apc_outlet_states,$apc_master_states,$apc_p_delays,$apc_r_delays,$log_status);
                    //echo "<br>$sstr<br>";
                    //print_r($sstr);
                    if (strlen($sstr) && $apc_x->up) {
                        $ret=contact_server($sys_config,"mother_server",8001,"apc_com $apc_x->ip $sstr",$timeout=30,$hostname=$boot_server[$apc_x->bootserver]);
                        $apc_x->ping($sys_config,$boot_server);
                        $apc_x->rescan();
                        $rets=preg_split("/#/",$ret);
                        //print_r($rets);
                        $front=array_shift($rets);
                        if (count($rets)) {
                            foreach ($rets as $act_r) {
                                $infstr="Contact APC $apc_x->name on {$boot_server[$apc_x->bootserver]}";
                                $hcproto->add_message($infstr,$act_r,preg_match("/^ok.*$/",$act_r));
                            }
                        } else {
                            $hcproto->add_message($ret,"error",0);
                        }
                    }
                }
            }
	    if ($hcproto->get_num_messages()) $hcproto->print_messages("");
            // calculate power-on delays
            foreach (array_keys($apcs) as $apcnum) {
                $apc=&$apcs[$apcnum];
                if ($apc->name == $actapc) {
                    if ($apc->up && $apc->state == "ok") {
                        $messtr="Masterswitch $apc->name, IP=$apc->ip";
                        message($messtr,$type=0);
                        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
                        hidden_sid();
                        echo "<input type=hidden name=\"apcsel\" value=\"$apc->name\"/>";
                        echo "<center>Power on delay = <select name=\"apc_$apc->idx.m\">";
                        foreach ($apc_p_delays as $acti=>$acta) {
                            list($acts,$act_mi)=$acta;
                            echo "<option value=$acti";
                            if ($apc->pod == $acti) echo " selected ";
                            echo ">$acts";
                        }
                        echo "</select>, reboot delay = $apc->rd, total power-on delay is ".get_podtstr($apc->pod)."</center>\n";
                        echo "<table class=\"normal\">";
                        echo "<tr>";
                        echo "<th class=\"apcname\">Outlet</th>";
                        echo "<th class=\"apcf0\">state</th>";
                        echo "<th class=\"apcf0\">delay</th>";
                        echo "<th class=\"apcf0\">control</th>";
                        echo "<th class=\"apcf0\">PwrOn delay</th>";
                        echo "<th class=\"apcf0\">PwrOff delay</th>";
                        echo "<th class=\"apcf0\">reboot delay</th>";
                        echo "</tr>";
                        foreach (array_keys($apc->states) as $out) {
                            echo "<tr>";
                            echo "<td class=\"apcname\">".$apc->getoutname($out)."</td>";
                            echo "<td class=\"apcf0\">".$apc->states[$out]["state"]."</td>";
                            echo "<td class=\"apcf0\">".get_podtstr(pod_add($apc->states[$out]["pond"],$apc->pod))."</td>";
                            echo "<td class=\"apcf0\"><select name=\"apc.$apc->idx".".o$out\" >";
                            foreach ($apc_outlet_states as $acti=>$acts) {
                                echo "<option value=\"$acti\"";
                                if ($acti==0) echo " selected ";
                                echo ">$acts</option>\n";
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"apcf0\"><select name=\"apc.$apc->idx".".p$out\">";
                            foreach ($apc_p_delays as $acti=>$acta) {
                                list($acts,$act_mi)=$acta;
                                echo "<option value=\"$acti\"";
                                if ($apc->states[$out]["pond"]==$acti) echo " selected ";
                                echo ">$acts</option>\n";
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"apcf0\"><select name=\"apc.$apc->idx".".P$out\">";
                            foreach ($apc_p_delays as $acti=>$acta) {
                                list($acts,$act_mi)=$acta;
                                echo "<option value=\"$acti\"" ;
                                if ($apc->states[$out]["poffd"]==$acti) echo " selected ";
                                echo ">$acts</option>\n";
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"apcf0\"><select name=\"apc.$apc->idx".".r$out\">";
                            foreach ($apc_r_delays as $acti=>$acta) {
                                list($acts,$act_mi)=$acta;
                                echo "<option value=\"$acti\"";
                                if ($apc->states[$out]["rebd"]==$acti) echo " selected ";
                                echo ">$acts</option>\n";
                            }
                            echo "</select></td>";
                            echo "</tr>";  
                        }
                        echo "</table>";
                        message("Global options",$type=2);
                        echo "<table class=\"simplesmall\">";
                        $num=0;
                        foreach ($apc_master_states as $short=>$long) {
                            //foreach (array(0=>"Nothing",-1=>"Refresh",1=>"Immediate on",2=>"Immediate off",
                            //           3=>"Immediate reboot",4=>"Delayed on",5=>"Delayed off",
                            //           6=>"Delayed reboot") as $short=>$long) {
                            if (!$num++) echo "<tr>";
                            echo "<td class=\"right\" >$long: <input type=radio name=\"apc_all_control\" value=\"$short\" ";
                            if ($long=="Nothing")  echo " checked ";
                            echo "/></td>\n";
                            if ($num == 4) {
                                $num=0;
                                echo "</tr>\n";
                            }
                        }
                        if ($num) {
                            while ($num++ != 4) echo "<td>&nbsp;</td>";
                            echo "</tr>\n";
                        }
                        echo "</table>\n";
                        echo "<div class=\"center\"><input type=submit value=\"submit\" /></div>\n";
                        echo "</form>";
                    } else {
                        if ($apc->state=="down") {
                            message("MasterSwitch $apc->name, IP=$apc->ip not reachable");
                        } else {
                            message("Unable to control outlets of MasterSwitch $apc->name, IP=$apc->ip");
                        }
                    }
                }
            }
        } else if ($apccommand=="ov") {
            if (sizeof($apcs)) {
                $messtr="APC overview (found ".sizeof($apcs)." APC MasterSwitch";
                if (sizeof($apcs) > 1) $messtr.="es";
                $messtr.=")";
                message($messtr);
                echo "<table class=\"normal\">";
                echo "<tr>";
                echo "<th class=\"apcname\">Name</th>";
                echo "<th class=\"apcf1\">DeviceGroup(s)</th>";
                echo "<th class=\"apcf0\">IP</th>";
                echo "<th class=\"apcf0\">State</th>";
                echo "</tr>";
                foreach (array_keys($apcs) as $apcn) {
                    $apc=&$apcs[$apcn];
                    echo "<tr>";
                    if ($apc->up) {
                        $aps="up";
                    } else {
                        $aps="down";
                    }
                    echo "<td class=\"apcname$aps\">$apc->name</td>";
                    echo "<td class=\"apcf1$aps\">$apc->groups&nbsp;</td>";
                    echo "<td class=\"apcf0$aps\">$apc->ip</td>";
                    echo "<td class=\"apcf0$aps\">$aps</td>";
                    echo "</tr>\n";
                }
                echo "</table>\n";
            } else {
                message("Found no APC-Masterswitches");
            }
        } else if ($apccommand=="po") {
            message ("Overview");
            $pod_list=array();
            foreach (array_keys($apcs) as $apcnum) {
                $apc=&$apcs[$apcnum];
                foreach (array_keys($apc->states) as $out) {
                    if ($apc->states[$out]["type"] != "-") {
                        $actpod=pod_add($apc->states[$out]["pond"],$apc->pod);
                        if (! isset($pod_list[$actpod])) {
                            $pod_list[$actpod]["num"]=0;
                            $pod_list[$actpod]["machlist"]=array();
                            $pod_list[$actpod]["swlist"]=array();
                        }
                        $pod_list[$actpod]["num"]++;
                        $pod_list[$actpod]["machlist"][]=$apc->states[$out]["nodename"];
                        if (!in_array($apc->name,$pod_list[$actpod]["swlist"])) $pod_list[$actpod]["swlist"][]=$apc->name;
                    }
                }
            }
            ksort($pod_list);
            echo "<table class=\"normal\">";
            echo "<tr>";
            echo "<th class=\"podt\">P.o. delay</th><th class=\"num\">Num</th>\n";
            echo "<th class=\"mlist\">Machines</th><th class=\"swlist\">Masterswitches</th>\n";
            foreach (array_keys($pod_list) as $pod) {
                echo "<tr>";
                echo "<td class=\"apcname\">",get_podtstr($pod),"</td>";
                echo "<td class=\"num\">",$pod_list[$pod]["num"],"</td>";
                echo "<td class=\"mlist\">";
                sort($pod_list[$pod]["machlist"]);
                $nfrst=0;
                foreach ($pod_list[$pod]["machlist"] as $mmach) {
                    if ($nfrst) { echo ", "; }
                    $nfrst=1;
                    echo $mmach;
                }
                echo "</td>\n";
                echo "<td class=\"swlist\">";
                sort($pod_list[$pod]["swlist"]);
                $nfrst=0;
                foreach ($pod_list[$pod]["swlist"] as $mmach) {
                    if ($nfrst) { echo ", "; }
                    $nfrst=1;
                    echo $mmach;
                }
                echo "</td>\n";
                echo "</tr>\n";
            }
            echo "</table>";
        } else if ($apccommand=="co") {
            message ("Cluster control");
            foreach (array_keys($apcs) as $apcnum) {
                $apc=&$apcs[$apcnum];
            }
            if (in_array("sdcl",$var_keys)) {
                $ccom="off";
            } else if (in_array("stcl",$var_keys)) {
                $ccom="on";
            } else {
                $ccom=0;
            }
            if ($ccom) {
                echo "<table class=\"normal\">";
                echo "<tr><th class=\"apcname\">Machine</th><th class=\"apcf1\">Time</th><th class=\"apcf2\">action</th></tr>\n";
                $mres=query("SELECT d.device_idx,d.name,d.comment,ms.device as mswitch,ms.outlet,dg.name AS dgname FROM device d, device_group dg, msoutlet ms WHERE ms.slave_device=d.device_idx AND dg.device_group_idx=d.device_group ORDER BY d.name");
                while ($mfr=mysql_fetch_object($mres)) {
                    $sstr="";
                    $outstr="";
                    $out=$mfr->outlet;
                    $name=$mfr->name;
                    $apc=&$apcs[$mfr->mswitch];
                    $cpf="up";
                    //echo "$mfr->mswitch ".$apc->states[$out]["state"]." $ccom<br>";
                    if ($apc->states[$out]["type"] == "C") {
                        $actstate=$apc->states[$out]["state"];
                        if ($actstate=="off" && $ccom=="on") {
                            $sstr.="1".strval($out)."11YEEE";
                            $outstr="Turning on outlet $out on $apc->name";
                        } else if ($actstate=="on" && $ccom=="off") {
                            $sstr.="1".strval($out)."12YEEE";
                            $outstr="Turning off outlet $out on $apc->name";
                            $cpf="down";
                        }
                    }
                    if (strlen($outstr)) {
                        echo "<tr><td class=\"apcname$cpf\">$name";
                        if ($mfr->comment) echo " ($mfr->comment)";
                        echo "</td>\n";
                        echo "<td class=\"apcf1$cpf\">".date("G:i:s",time())."</td>\n";
                        echo "<td class=\"apcf2$cpf\">$outstr</td>";
                        echo "</tr>";
                    }
                    if (strlen($sstr)) {
                        if ($apc->up) {
                            $rets=contact_server($sys_config,"mother_server",8001,"apc_com $apc->ip $sstr",$timeout=30,$hostname=$boot_server[$apc->bootserver]);
                            //print_r($rets);
                        }
                    }
                }
                echo "</table>\n";
                foreach (array_keys($apcs) as $apcnum) {
                    $apc=&$apcs[$apcnum];
                    $apc->rescan();
                }
            }
            $numon=0;
            $numoff=0;
            foreach (array_keys($apcs) as $apcnum) {
                $apc=&$apcs[$apcnum];
                foreach ($apc->states as $key=>$out) {
                    if ($apc->states[$key]["type"] == "C") {
                        $actstate=$apc->states[$key]["state"];
                        if ($actstate=="off") {
                            $numoff++;
                        } else if ($actstate=="on") {
                            $numon++;
                        }
                    }
                }
            }
            if ($numon == 0) {
                $mstr="no machine online,";
            } else {
                $mstr=" $numon ".get_plural("machine",$numon)." online, ";
            }
            if ($numoff == 0) {
                $mstr.=" no machines offline";
            } else {
                $mstr.=" $numoff ".get_plural("machine",$numoff)." offline";
            }
            message ($mstr);
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=get><input type=hidden name=\"apcsel\" value=\"$actapc\" />";
            hidden_sid();
            echo "<center><table>";
            echo "<tr>";
            if ($numon) echo "<td><input class=\"apcoffl\" type=submit name=\"sdcl\" value=\"Bring all machines offline\" /></td>";
            if ($numoff) echo "<td><input class=\"apconl\" type=submit name=\"stcl\" value=\"Bring all machines online\" /></td>";
            echo "</tr>\n";
            echo "</center></table></form>\n";
        } else {
            message ("Internal error ($apccommand)");
        }
    } else {
        message("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
