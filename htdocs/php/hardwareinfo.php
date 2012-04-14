<?php
//-*ics*- ,CAP,name:'hwi',defvalue:0,enabled:1,descr:'Hardware info',scriptname:'/php/hardwareinfo.php',left_string:'Hardwareinfo',right_string:'Cluster hardware',capability_group_name:'info',pri:-20
//-*ics*- ,CAP,name:'uhw',defvalue:0,enabled:1,descr:'Update hardware info',mother_capability_name:'hwi'
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
function get_mret($what,$class,$opt="",$nsv="Q",$mline=1) {
    if ($mline != 1) {
        $mlc=" rowspan=$mline ";
    } else {
        $mlc="";
    }
    if ($nsv != "Q" && $what==$nsv) {
        return "<td class=\"$class\" $mlc>not set</td>";
    } else {
        return "<td class=\"$class\" $mlc>$what$opt</td>";
    }
}
class device {
    var $name,$comment,$bootserver,$cpus,$pci_list;
    function device($name,$comment,$bs) {
        $this->name=$name;
        $this->comment=$comment;
        $this->bootserver=$bs;
        $this->cpus=array();
        $this->pci_list=array();
        $this->p_mem=0;
        $this->v_mem=0;
        $this->size_hd=0;
        $this->num_hd=0;
        $this->gfx_info="";
    }
    function get_name($mline=1) {
        $opt="";
        if ($this->comment) $opt=" ($this->comment)";
        if (!$this->bootserver) $opt.=", no bs";
        return get_mret($this->name,"name",$opt,"Q",$mline) ;
    }
    function add_cpu($type,$speed) {
        $this->cpus[]=array($type,$speed);
    }
    function get_cpu_num() {
        return get_mret(count($this->cpus),"mem","",$nsv=-1);
    }
    function get_cpu_speed() {
        $c_array=array();
        foreach ($this->cpus as $speed) {
            $mhz=$speed[0];
            if (in_array($mhz,array_keys($c_array))) {
                $c_array[$mhz]++;
            } else {
                $c_array[$mhz]=1;
            }
        }
        $s_array=array();
        foreach ($c_array as $type=>$num) {
            if ($num == 1) {
                $s_array[]="$type";
            } else {
                $s_array[]="$num x $type";
            }
        }
        return get_mret(implode(" / ",$s_array),"mem","",$nsv=-1);
    }
    function get_cpu_types() {
        $c_array=array();
        foreach ($this->cpus as $cpu) {
            $cpu_t=$cpu[1];
            if (in_array($cpu_t,array_keys($c_array))) {
                $c_array[$cpu_t]++;
            } else {
                $c_array[$cpu_t]=1;
            }
        }
        $s_array=array();
        foreach ($c_array as $type=>$num) {
            if ($num == 1) {
                $s_array[]="$type";
            } else {
                $s_array[]="$num x $type";
            }
        }
        return get_mret(implode(",",$s_array),"mem","",$nsv=-1);
    }
    function set_p_mem($mem) {
        $this->p_mem=(int)($mem/1024);
    }
    function set_v_mem($mem) {
        $this->v_mem=(int)($mem/1024);
    }
    function get_p_mem() {
        return get_mret($this->p_mem,"mem"," MB",$nsv="0");
    }
    function get_v_mem() {
        return get_mret($this->v_mem,"mem"," MB",$nsv="0");
    }
    function set_disk_info($num,$ds) {
        $this->num_hd=$num;
        $this->size_hd=$ds;
    }
    function get_disk_size() {
        if ($this->size_hd > 1000) {
            return get_mret(sprintf("%.2f",$this->size_hd/1000),"temp"," TB",$nsv=-1);
        } else {
            return get_mret($this->size_hd,"temp"," GB",$nsv=-1);
        }
    }
    function get_disk_num() {
        return get_mret($this->num_hd,"mem","",$nsv=-1);
    }
    function set_gfx_info($gfx) {
        $this->gfx_info=$gfx;
    }
    function get_gfx_info() {
        return get_mret($this->gfx_infom,"gfx");
    }
}
function get_gfx($gfx) { return get_mret($gfx,"gfx") ; }

require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["hwi_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    // parse the machine selection
    list($display_a,$machgroups,$hiddenmach,$actmach,$optsel)=get_display_list($vars," AND dt.identifier='H'");
    htmlhead();
    $clustername=$sys_config["CLUSTERNAME"];
    clusterhead($sys_config,"Hardware information page",$style="formate.css",
                array("th.load"=>array("background-color:#ffffff"),
                      "td.load"=>array("background-color:#eeffee","text-align:center"),
                      "td.loadw"=>array("background-color:#ccffcc","text-align:center"),
                      "th.mem"=>array("background-color:#f4f4ff"),
                      "td.mem"=>array("background-color:#fff4e4","text-align:center"),
                      "th.load"=>array("background-color:#ffffff"),
                      "td.load"=>array("background-color:#eeffee","text-align:center"),
                      "th.temp"=>array("background-color:#ffffff"),
                      "td.temp"=>array("background-color:#ffeeee","text-align:center"),
                      "th.gfx"=>array("background-color:#ffeeff"),
                      "td.gfx"=>array("background-color:#eeddee","text-align:center"),
                      "th.pci1"=>array("background-color:#ddddff"),
                      "th.pci2"=>array("background-color:#d5d5f7"),
                      "th.pci3"=>array("background-color:#cdcdef"),
                      "th.pci4"=>array("background-color:#c5c5e7"),
                      "td.pci1"=>array("background-color:#eeeeff"),
                      "td.pci2"=>array("background-color:#e6e6f7"),
                      "td.pci3"=>array("background-color:#dedeef"),
                      "td.pci4"=>array("background-color:#d6d6e7")
                      )
                );
    clusterbody($sys_config,"Hardware info",array(),array("info"));
    $varkeys=array_keys($vars);
    // check pci-show mode
    $show_pci=0;
    if (in_array("show_pci",$varkeys)) $show_pci=$vars["show_pci"];
    $hiddenshow_pci="<input type=hidden name=\"show_pci\" value=\"$show_pci\" />";
    $ucl=usercaps($sys_db_con);
    if ($ucl["hwi"]) {
        if ($ucl["uhw"]) {
            $boot_server=array();
            $mres=query("SELECT d.device_idx,d.name,d.bootserver FROM device d, deviceconfig dc, config c WHERE dc.device=d.device_idx AND dc.config=c.config_idx AND c.name='mother_server'");
            while ($mfr=mysql_fetch_object($mres)) $boot_server[$mfr->device_idx]=$mfr->name;
            $update_array=array();
            foreach ($boot_server as $idx=>$name)  $update_array[$name]=array();
            $mres=query("SELECT d.name,d.bootserver FROM device d WHERE d.bootserver > 0 $optsel",$sys_db_con);
            if (mysql_num_rows($mres)) {
                while ($mach=mysql_fetch_object($mres)) {
                    if ((isset($vars[$mach->name."_uhi"]) && $vars[$mach->name."_uhi"]) || (isset($vars["update_all"]) && $vars["update_all"])) $update_array[$boot_server[$mach->bootserver]][]=$mach->name;
                }
            }
            foreach ($update_array as $server=>$nodes) {
                if (count($nodes)) {
                    if (sizeof($update_array)) $rets=contact_server($sys_config,"mother_server",8001,"refresh_hwi ".implode(":",$nodes),$timeout=0,$server);
                }
            }
        }
        if (count($machgroups)) {
            message ("Please select machinegroup or machine(s) by their name:");
            echo "<div class=\"center\">";
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            echo "<table class=\"simplesmall\"><tr><td>";
            hidden_sid();
            echo "<select name=\"selgroup[]\" multiple size=5>";
            foreach ($machgroups as $mg=>$mgv) {
                echo "<option value=\"$mg\"";
                if ($mgv["selected"]) echo " selected";
                echo ">$mg";
                if ($mgv["num"]) echo " (".$mgv["num"]." ".get_plural("device",$mgv["num"]).")";
                echo "\n";
            }
            echo "</select></td>\n";
            echo "<td>&nbsp;&nbsp;</td>";
            echo "<td><select name=\"selmach[]\" size=5 multiple>";
            foreach ($machgroups as $act_group=>$display_g) {
                if ($display_g["num"]) {
                    $num_mach=sizeof($display_g["list"]);
                    $mach_str=get_plural("machine",$num_mach);
                    echo "<option value=d disabled>$act_group [ $num_mach $mach_str ]\n";
                    $mres=query("SELECT d.name,d.comment FROM device d WHERE d.name='".implode("' OR d.name='",$display_g["list"])."' ORDER BY d.name",$sys_db_con);
                    while ($mfr=mysql_fetch_object($mres)) {
                        echo "<option value=\"$mfr->name\"";
                        $name=$mfr->name;
                        if (in_array($name,$actmach)) echo " selected";
                        echo ">$name";
                        if ($mfr->comment) echo " ($mfr->comment)";
                        echo "\n";
                    }
                }
            }
            echo "</select></td>";
            echo "</tr>\n";
            echo "<tr><td colspan=\"3\">";
            echo "show pci-maps:<input type=checkbox name=\"show_pci\" ".($show_pci ? "checked" : "")."/>\n";
            echo ", <input type=submit value=\"select\" /></td>";
            echo "</tr></table></form>";
            echo "</div>\n";
        } else {
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            $mess_str="No machines found in database, <input type=submit value=\"retry\" />";
            message($mess_str,$type=2);
            echo "</form>";
        }
        if (sizeof($display_a)) {
            if (sizeof($display_a) > 1) {
                $tot_mach=0;
                $tot_grp=0;
                foreach ($display_a as $lk=>$lv) {
                    $tot_grp+=1;
                    list($n1)=$lv;
                    $tot_mach+=$n1;
                }
                $mes_str="Found $tot_mach machines in $tot_grp machinegroups";
            } else {
                reset($display_a);
                list($n1,$n2,$mach_list)=current($display_a);
                if ($n1 == 1) {
                    $mes_str="Found machine ".$mach_list[0]." in machinegroup ".key($display_a);
                } else {
                    $mes_str="Found $n1 machines in machinegroup ".key($display_a);
                }
            }
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            echo $hiddenshow_pci;
            message($mes_str);
            $gfxlist=array();
            $gfxcount=array();
            $gfxnum=0;
            echo $hiddenmach;
            echo "<table class=\"normal\">";
            echo "<tr><th class=\"name\">Hostname</th>";
            if ($ucl["uhw"]) echo "<th class=\"mem\">Update</th>";
            if ($show_pci) {
                echo "<th class=\"load\" >B</th>\n";
                echo "<th class=\"load\" >S</th>\n";
                echo "<th class=\"load\" >F</th>\n";
                 echo "<th class=\"pci1\">Subclass</th>\n";
                 echo "<th class=\"pci2\">Vendor</th>\n";
                 echo "<th class=\"pci3\">Device</th>\n";
                 echo "<th class=\"pci4\">Revision</th>\n";
                $colspan_size=9;
            } else {
                echo "<th class=\"load\">CPU(s)</th><th class=\"load\">MHz</th>\n";
                echo "<th class=\"mem\">nCPU</th><th class=\"load\">MemPhys</th>\n";
                echo "<th class=\"temp\">MemSwap</th><th class=\"temp\">HDSpace</th><th class=\"mem\">NumHd</th>\n";
                echo "<th class=\"gfx\">GfxType</th>\n";
                $colspan_size=10;
            }
            echo "</tr>\n";
            $num_hl=0;
            foreach ($display_a as $act_group=>$display_g) {
                list($n1,$n2,$mach_list)=$display_g;
                if (sizeof($display_a) > 1) echo "<tr><td colspan=$colspan_size class=\"machinegroup\">machinegroup: $act_group , selected $n1 of $n2 machines</td></tr>\n";
                $mres=query("SELECT d.bootserver,d.name,d.comment FROM device d, device_group dg WHERE dg.name='$act_group' AND dg.device_group_idx=d.device_group $optsel",$sys_db_con);
                $devices=array();
                while ($mach=mysql_fetch_object($mres)) {
                    $devices[$mach->name]=new device($mach->name,$mach->comment,$mach->bootserver);
                }
                if ($show_pci) {
                    $mres=query("SELECT d.name,d.bootserver,d.name,d.comment,p.* FROM device d, device_group dg, pci_entry p WHERE p.device_idx=d.device_idx AND dg.name='$act_group' AND dg.device_group_idx=d.device_group $optsel ORDER BY d.name",$sys_db_con);
                } else {
                    $mres=query("SELECT d.name,d.bootserver,d.name,d.comment,ht.identifier,hw.iarg0,hw.iarg1,hw.sarg0,hw.sarg1,ht.iarg0_descr,ht.iarg1_descr,ht.sarg0_descr,ht.sarg1_descr FROM device d, device_group dg, hw_entry hw, hw_entry_type ht WHERE hw.hw_entry_type=ht.hw_entry_type_idx AND hw.device=d.device_idx AND dg.name='$act_group' AND dg.device_group_idx=d.device_group $optsel ORDER BY d.name",$sys_db_con);
                }
                while ($mach=mysql_fetch_object($mres)) {
                    $dev_struct=&$devices[$mach->name];
                    if ($show_pci) {
                        $dev_struct->pci_list[]=$mach;
                    } else {
                        if ($mach->identifier == "cpu") {
                            $dev_struct->add_cpu($mach->iarg0,$mach->sarg0);
                        } else if ($mach->identifier == "mem") {
                            $dev_struct->set_p_mem($mach->iarg0);
                            $dev_struct->set_v_mem($mach->iarg1);
                        } else if ($mach->identifier == "disks") {
                            $dev_struct->set_disk_info($mach->iarg0,$mach->iarg1);
                        } else if ($mach->identifier == "gfx") {
                            $dev_struct->set_gfx_info($mach->sarg0);
                        }
                    }
                    unset($dev_struct);
                }
                foreach ($devices as $dev_name => $dev_struct) {
                    if ($show_pci) {
                        $mult_row=count($dev_struct->pci_list);
                        if (!$mult_row) $mult_row++;
                    } else {
                        $mult_row=1;
                    }
                    echo $dev_struct->get_name($mult_row);
                    if ($ucl["uhw"]) {
                        echo "<td class=\"mem\" rowspan=$mult_row>";
			if ($dev_struct->bootserver) {
			    echo "<input type=checkbox name=\"$dev_struct->name.uhi\" value=\"update\" \>";
			} else {
			    echo "&nbsp;";
			}
			echo "</td>\n";
                    }
                    if ($show_pci) {
                        $pci_f=array();
                        $bus_count=array();
                        $slot_count=array();
                        foreach ($dev_struct->pci_list as $pci_e) {
                            $bus=sprintf("%02x",$pci_e->bus);
                            $slot=sprintf("%02x",$pci_e->slot);
                            $func=sprintf("%01x",$pci_e->func);
                            if (!in_array($bus,array_keys($pci_f))) {
                                $pci_f[$bus]=array();
                                $bus_count[$bus]=0;
                                $slot_count[$bus]=array();
                            }
                            if (!in_array($slot,array_keys($pci_f[$bus]))) {
                                $pci_f[$bus][$slot]=array();
                                $slot_count[$bus][$slot]=0;
                            }
                            $pci_f[$bus][$slot][$func]=$pci_e;
                            $bus_count[$bus]++;
                            $slot_count[$bus][$slot]++;
                        }
                        //print_r($pci_f);
                        $line=0;
                        $bus_f=array_keys($pci_f);
                        sort($bus_f);
                        foreach ($bus_f as $bus) {
                            $slot_f=array_keys($pci_f[$bus]);
                            sort($slot_f);
                            $s_bus=$bus;
                            // bus linenumber
                            $bus_ln=0;
                            foreach ($slot_f as $slot) {
                                $func_f=array_keys($pci_f[$bus][$slot]);
                                sort($func_f);
                                $s_slot=$slot;
                                // slot linenumber
                                $slot_ln=0;
                                foreach ($func_f as $func) {
                                    $pci_e=&$pci_f[$bus][$slot][$func];
                                    if ($line++) echo "<tr>";
                                    if (!$bus_ln++) echo "<td class=\"load\" rowspan={$bus_count[$bus]}>$bus</td>\n";
                                    if (!$slot_ln++) echo "<td class=\"load\" rowspan={$slot_count[$bus][$slot]}>$slot</td>\n";
                                    echo "<td class=\"load\">$func</td>\n";
                                    echo "<td class=\"pci1\">$pci_e->subclassname</td><td class=\"pci2\">$pci_e->vendorname</td><td class=\"pci3\">$pci_e->devicename</td><td class=\"pci4\">$pci_e->revision</td>";
                                    if ($line < count($pci_f)) echo "</tr>";
                                }
                            }
                        }
                        if (!$line) echo "<td class=\"loadw\" colspan=7>No PCI-map found</td>";
                    } else {
                        echo $dev_struct->get_cpu_types(),$dev_struct->get_cpu_speed(),$dev_struct->get_cpu_num();
                        echo $dev_struct->get_p_mem(),$dev_struct->get_v_mem();
                        echo $dev_struct->get_disk_size(),$dev_struct->get_disk_num();
                        $gfx_info=$dev_struct->gfx_info;
                        if (strlen($gfx_info) == 0 || $gfx_info == "<UNKNOWN>") {
                            if (strlen($mach->cputype)) {
                                echo get_gfx("Headless");#
                                    $num_hl++;
                            } else {
                                echo get_gfx("not set");
                            }
                        } else {
                            if (! in_array($gfx_info,array_keys($gfxlist))) {
                                $gfxnum++;
                                $gfxlist[$gfx_info]=$gfxnum;
                                $gfxcount[$gfx_info]=1;
                            } else {
                                $gfxcount[$gfx_info]++;
                            }
                            echo get_gfx("( {$gfxlist[$gfx_info]} )");
                        }
                    }
                    echo "</tr>\n";
                }
            }
            echo "</table>";
            if ($ucl["uhw"]) {
                echo "<center>";
                echo "<input type=submit name=\"update_all\" value=\"Update all\" \>&nbsp;";
                echo "<input type=submit value=\"submit\" \>";
                echo "</center>\n";
            }
            echo "</form>";
	    if (!$show_pci) {
		if ($gfxnum) {
		    $messtr="Found $gfxnum different ".get_plural("graphiccard",$gfxnum);
		    if ($num_hl) $messtr.=" and $num_hl headless ".get_plural("node",$messtr);
		    message($messtr,$type=1);
		    echo "<table class=\"normal\">\n";
		    echo "<tr><th class=\"load\">GfxType</th>";
		    echo "<th class=\"mem\">Count</th>";
		    echo "<th class=\"gfx\">Gfx Info</th>\n";
		    foreach (array_keys($gfxlist) as $gfxc) {
			echo "<tr><td class=\"load\">( {$gfxlist[$gfxc]} )</td><td class=\"mem\">{$gfxcount[$gfxc]}</td><td class=\"gfx\">$gfxc</td></tr>\n";
		    }
		    echo "</table>";
		} else {
		    $messtr="Found ".get_plural("headless node",$num_hl,1);
		    if ($num_hl > 1) $messtr.="s";
		    message ($messtr,$type=1);
		}
	    }
        } else {
            message ("No machines selected");
        }
    } else {
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
