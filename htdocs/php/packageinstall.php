<?php
//-*ics*- ,CAP,name:'pi',descr:'Package install',enabled:1,defvalue:0,scriptname:'/php/packageinstall.php',left_string:'Package install',right_string:'Install packages without rebooting',capability_group_name:'conf',pri:40
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
class instp_device {
    var $inst_package_idx,$install,$upgrade,$del,$status,$nodeps,$install_time,$forceflag;
    function instp_device($ipi,$ins,$upg,$del,$nodeps,$forceflag,$install_time,$stat) {
        $this->inst_package_idx=$ipi;
        $this->install=$ins;
        $this->upgrade=$upg;
        $this->del=$del;
        $this->nodeps=$nodeps;
        $this->forceflag=$forceflag;
        $this->install_time=$install_time;
        $this->status=$stat;
    }
    function get_install_time() {
        if ($this->install_time) {
            return date("D, j. M Y H:i:s",$this->install_time);
        } else {
            return "---";
        }
    }
}
function get_size_str($bytes) {
    $out_f=array();
    foreach (array("T"=>1024*1024*1024*1024,"G"=>1024*1024*1024,
                   "M"=>1024*1024          ,"k"=>1024) as $pf=>$sf) {
        $act_f=(int)($bytes/$sf);
        if ($act_f) {
            $out_f[]=sprintf("%d %s",$act_f,$pf);
            $bytes-=$sf*$act_f;
        }
    }
    $out_f[]="$bytes B";
    return implode(" ",$out_f);
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["pi_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);
    // user capabilities
    $ucl=usercaps($sys_db_con);
    list($display_a,$machgroups,$hiddenmach,$actmach,$optsel)=get_display_list($vars,"AND dc.device=d.device_idx AND dc.config=c.config_idx AND c.name='package_client'",$tables=array("c"=>"config","dc"=>"deviceconfig"));
    htmlhead();
    clusterhead($sys_config,"Package install page",$style="formate.css",
                array("td.pass"=>array("background-color:#eedd88","text-align:center"),
                      "th.pinfo"=>array("background-color:#e2f2d2","text-align:center"),
                      "th.pnamer"=>array("background-color:#e2f2d2","text-align:right"),
                      "td.pnamer"=>array("background-color:#d2e2c2","text-align:right"),
                      "th.pname"=>array("background-color:#e2f2d2","text-align:left"),
                      "td.pname"=>array("background-color:#d2e2c2","text-align:left"),
                      "td.pnameh"=>array("background-color:#e2f2d2","text-align:left"),
                      "td.pnameerr"=>array("background-color:#ff8888","text-align:left"),
                      "th.pgroup"=>array("background-color:#d2e2c2","text-align:left"),
                      "th.pgroupc"=>array("background-color:#d2e2c2","text-align:center"),
                      "td.pgroup"=>array("background-color:#c2d2b2","text-align:left"),
                      "td.pgroupc"=>array("background-color:#c2d2e2","text-align:center"),
                      "td.pgrouph"=>array("background-color:#d2e2c2","text-align:left"),
                      "td.pgrouperr"=>array("background-color:#ff8888","text-align:left"),
                      "th.pversion"=>array("background-color:#e2d2f2","text-align:center"),
                      "td.pversion"=>array("background-color:#d2c2e2","text-align:center"),
                      "td.pversionh"=>array("background-color:#e2d2f2","text-align:center"),
                      "td.pversionerr"=>array("background-color:#ff8888","text-align:center"),
                      "th.pnoass"=>array("background-color:#f6d2e6","text-align:center"),
                      "td.pnoass"=>array("background-color:#e2c2d6","text-align:center"),
                      "th.prelease"=>array("background-color:#e2d2fa","text-align:center"),
                      "td.prelease"=>array("background-color:#d2c2ea","text-align:center"),
                      "td.preleaseh"=>array("background-color:#e2d2fa","text-align:center"),
                      "td.preleaseerr"=>array("background-color:#ff8888","text-align:center"),
                      "th.parch"=>array("background-color:#e2e2fa","text-align:center"),
                      "td.parch"=>array("background-color:#d2d2ea","text-align:center"),
                      "td.parchh"=>array("background-color:#e2e2fa","text-align:center"),
                      "td.parcherr"=>array("background-color:#ff8888","text-align:center"),
                      "th.none"=>array("background-color:#f4f4f4","text-align:center"),
                      "td.none"=>array("background-color:#e4e4e4","text-align:center"),
                      "td.noneh"=>array("background-color:#f4f4f4","text-align:center"),
                      "td.noneerr"=>array("background-color:#ff8888","text-align:center"),
                      "th.add"=>array("background-color:#e4e4e4","text-align:center"),
                      "td.add"=>array("background-color:#d4d4d4","text-align:center"),
                      "td.addh"=>array("background-color:#e4e4e4","text-align:center"),
                      "td.adderr"=>array("background-color:#ff8888","text-align:center"),
                      "th.del"=>array("background-color:#d4d4d4","text-align:center"),
                      "td.del"=>array("background-color:#c4c4c4","text-align:center"),
                      "td.delh"=>array("background-color:#d4d4d4","text-align:center"),
                      "td.delerr"=>array("background-color:#ff8888","text-align:center"),
                      "th.tstate"=>array("background-color:#ffffdd","text-align:center"),
                      "td.tstate"=>array("background-color:#eeeecc","text-align:center"),
                      "td.tstateh"=>array("background-color:#fefeec","text-align:center"),
                      "td.tstateerr"=>array("background-color:#ff8888","text-align:center"),
                      "th.astate"=>array("background-color:#eeeecc","text-align:center"),
                      "td.astate"=>array("background-color:#ddddbb","text-align:center"),
                      "th.remove"=>array("background-color:#ddddbb","text-align:center"),
                      "td.remove"=>array("background-color:#ccccaa","text-align:center"),
                      "th.status"=>array("background-color:#ffeeee","text-align:center"),
                      "td.statok"=>array("background-color:#eedddd","text-align:left"),
                      "td.staterror"=>array("background-color:#ee7777","text-align:left"),
                      "td.statns"=>array("background-color:#ddcccc","text-align:left"),
                      "td.statovok"=>array("background-color:#eedddd","text-align:center"),
                      "td.statoverror"=>array("background-color:#ee7777","text-align:center"),
                      "td.statovns"=>array("background-color:#ddcccc","text-align:center"),
                      "th.nkeep"=>array("background-color:#ddffdd","text-align:center"),
                      "td.nkeep"=>array("background-color:#cceecc","text-align:center"),
                      "td.nkeeph"=>array("background-color:#dcfedc","text-align:center"),
                      "td.nkeeperr"=>array("background-color:#ff8888","text-align:center"),
                      "th.nins"=>array("background-color:#cceecc","text-align:center"),
                      "td.nins"=>array("background-color:#bbddbb","text-align:center"),
                      "td.ninsh"=>array("background-color:#cbedcb","text-align:center"),
                      "td.ninserr"=>array("background-color:#ff8888","text-align:center"),
                      "th.ndel"=>array("background-color:#bbddbb","text-align:center"),
                      "td.ndel"=>array("background-color:#aaccaa","text-align:center"),
                      "td.ndelh"=>array("background-color:#badcba","text-align:center"),
                      "td.ndelerr"=>array("background-color:#ff8888","text-align:center")
                      )
                );
    clusterbody($sys_config,"Package install",array(),array("conf"));
    if ($ucl["pi"]) {
        // log
        $hcproto=new messagelog();
        // read package-info
        $archs=array(0=>array("name"=>"- ALL -","num"=>0));
        $inst_p=array();
        $mres=query("SELECT p.*,ip.*,a.architecture as arch,a.architecture_idx FROM package p, inst_package ip, architecture a WHERE a.architecture_idx=p.architecture AND ip.package=p.package_idx ORDER BY p.name, p.version,p.release");
        while ($mfr=mysql_fetch_object($mres)) {
            $mfr->displayed=0;
            $mfr->used=0;
            $mfr->idn_array=array("i"=>0,"u"=>0,"d"=>0,"n"=>0,"a"=>0);
            $inst_p[$mfr->inst_package_idx]=$mfr;
            if (!in_array($mfr->architecture_idx,array_keys($archs))) $archs[$mfr->architecture_idx]=array("name"=>$mfr->arch,"num"=>0);
            $archs[$mfr->architecture_idx]["num"]++;
            $archs[0]["num"]++;
        }
        // selected architectures
        if (in_array("archs",array_keys($vars))) {
            $act_archs=$vars["archs"];
        } else {
            $act_archs=array(0);
        }
        if (!$act_archs) $act_archs=array(0);
        $hidden_archs="";
        foreach ($act_archs as $act_arch) $hidden_archs.="<input type=hidden name=\"archs[]\" value=\"$act_arch\" />\n";
        // regexp for name
        if (in_array("namereg",array_keys($vars))) {
            $namereg=$vars["namereg"];
        } else {
            $namereg=".*";
        }
        if (!$namereg) $namereg=".*";
        $hidden_namereg="<input type=hidden name=\"namereg\" value=\"$namereg\" />\n";
        // all groups
        $all_pgroups=array();
        $all_pgroups_rev=array();
        $act_idx=0;
        foreach ($inst_p as $ip_idx=>$ip_stuff) {
            $act_pgroup=$ip_stuff->pgroup;
            if (!$act_pgroup) {
                $act_pgroup="unknown";
                $inst_p[$ip_idx]->pgroup=$act_pgroup;
            }
            if (!in_array($act_pgroup,array_keys($all_pgroups))) {
                $all_pgroups[$act_pgroup]=array("num"=>0,"idx"=>++$act_idx);
                $all_pgroups_rev[$act_idx]=$act_pgroup;
            }
        }
        // deselected non-matching packages
        foreach ($inst_p as $inst_p_idx=>$inst_p_stuff) {
            if (!in_array($inst_p_stuff->architecture_idx,$act_archs) && !in_array(0,$act_archs)) {
                // not in arch list
                unset($inst_p[$inst_p_idx]);
            } else if (!preg_match("/$namereg/",$inst_p_stuff->name)) {
                unset($inst_p[$inst_p_idx]);
            }
        }
        // Display types
        $ov_types=array("Overview","Detailed","Maintenance");
        if (in_array("ovtype",array_keys($vars))) {
            $act_ov_type=$vars["ovtype"];
        } else {
            $act_ov_type=$ov_types[0];
        }
        // sort types
        $so_types=array(-1=>"Show all, sort by Name",
                        -2=>"Show all, sort by Group (and Name)");
        // check for altering of packagegroup
        if ($act_ov_type=="Maintenance") {
            foreach ($inst_p as $ip_idx=>$ip_stuff) {
                if (in_array("delp_$ip_idx",array_keys($vars))) {
                    $hcproto->add_message("Deleting installable package $ip_stuff->name (Version $ip_stuff->version, Release $ip_stuff->release)","ok",1);
                    query("DELETE FROM inst_package WHERE inst_package_idx=$ip_idx");
                    unset($inst_p[$ip_idx]);
                } else if (in_array("ng_$ip_idx",array_keys($vars))) {
                    $ng=$all_pgroups_rev[$vars["ng_$ip_idx"]];
                    if ($ng != $ip_stuff->pgroup) {
                        $hcproto->add_message("Changing group of installable package $ip_stuff->name (Version $ip_stuff->version, Release $ip_stuff->release) from {$inst_p[$ip_idx]->pgroup} to $ng","ok",1);
                        $inst_p[$ip_idx]->pgroup=$ng;
                        query("UPDATE package SET pgroup='".mysql_escape_string($ng)."' WHERE package_idx=$ip_stuff->package_idx");
                    }
                }
            }
        }
        // add all groups
        foreach ($inst_p as $ip_idx=>$ip_stuff) {
            $all_pgroups[$ip_stuff->pgroup]["num"]++;
        }
        foreach ($all_pgroups as $pg_name=>$pg_stuff) {
            if ($pg_stuff["num"]) $so_types[$pg_stuff["idx"]]="Group $pg_name ({$pg_stuff['num']} packages)";
        }
        //print_r($all_pgroups);
        $pg_selected=array();
        $hidden_pg_sel="";
        if (is_set("pgs",&$vars)) {
            foreach ($vars["pgs"] as $pgs) {
                if (in_array($pgs,array_keys($so_types))) {
                    $pg_selected[]=$pgs;
                }
            }
        }
        if (in_array(-1,$pg_selected) && in_array(-2,$pg_selected)) unset($pg_selected[array_search(-1,$pg_selected,FALSE)]);
        if (!count($pg_selected)) $pg_selected[]=-2;
        if (max($pg_selected) > 0) {
            if (in_array(-1,$pg_selected)) unset($pg_selected[array_search(-1,$pg_selected,FALSE)]);
            if (in_array(-2,$pg_selected)) unset($pg_selected[array_search(-2,$pg_selected,FALSE)]);
        }
        foreach ($pg_selected as $pgs) $hidden_pg_sel.="<input type=hidden name=\"pgs[]\" value=\"$pgs\"/>\n";
        $only_highest=0;
        $hidden_highest="";
        if (in_array("oh",&$varkeys)) {
            $only_highest=1;
            $hidden_highest="<input type=hidden name=\"oh\" value=\"$only_highest\" />\n";
        }
        $hidden_ov_type="<input type=hidden name=\"ovtype\" value=\"$act_ov_type\"/>";
        $ins_states      =array("keep"=>"n","install"=>"i","upgrade"=>"u","remove"=>"d");
        $nodep_states    =array("keep"=>"n","with --nodeps"=>"1","normal"=>"0");
        $forceflag_states=array("keep"=>"n","with --force"=>"1","normal"=>"0");
        // simple protocol
        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
        hidden_sid();
        if (count($machgroups)) {
            message ("Please select devicegroup or device(s) by their name:");
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\"><tr>";
            echo "<td>";
            echo "<select name=\"selgroup[]\" multiple size=5>";
            foreach ($machgroups as $mg=>$mgv) {
                echo "<option value=\"$mg\" ".($mgv["selected"] ? " selected" : "").">$mg";
                if ($mgv["num"]) echo " (".get_plural("device",$mgv["num"],1).")";
                echo "</option>\n";
            }
            echo "</select>";
            echo "</td>\n";
            echo "<td>&nbsp;&nbsp;</td>";
            echo "<td><select name=\"selmach[]\" size=5 multiple>";
            $all_machs=array();
            foreach ($machgroups as $act_group=>$display_g) {
                if ($display_g["num"]) {
                    $num_mach=sizeof($display_g["list"]);
                    $mach_str=get_plural("device",$num_mach);
                    echo "<option value=d disabled>$act_group [ $num_mach $mach_str ]</option>\n";
                    $mres=query("SELECT d.name,d.comment FROM device d WHERE ( d.name='".implode("' OR d.name='",$display_g["list"])."')");
                    while ($mfr=mysql_fetch_object($mres)) {
                        $name=$mfr->name;
                        $all_machs[]="d.name='$name'";
                        echo "<option value=\"$name\"";
                        if (in_array($name,$actmach)) echo " selected";
                        echo ">$name";
                        if ($mfr->comment) echo " ($mfr->comment)";
                        echo "</option>\n";
                    }
                }
            }
            echo "</select></td>";
            echo "<td>&nbsp;&nbsp;</td>\n";
            echo "<td><select name=\"pgs[]\" multiple size=\"5\">";
            foreach ($so_types as $so_num=>$so_stuff) {
                echo "<option value=\"$so_num\" ".(in_array($so_num,$pg_selected) ? "selected" : "" ).">$so_stuff</option>\n";
            }
            echo "</select></td>\n";
            echo "</tr>";
        } else {
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\"><tr>";
        }
            echo "<tr><td colspan=\"5\">";
            echo "Show architectures: <select name=\"archs[]\" multiple size=\"2\">";
            foreach ($archs as $arch_idx=>$arch_stuff) {
                echo "<option value=\"$arch_idx\" ".(in_array($arch_idx,$act_archs) ? "selected" : "").">{$arch_stuff['name']} ({$arch_stuff['num']} packages)</option>\n";
            }
            echo "</select>, \n";
            echo "Name RegExp: <input name=\"namereg\" value=\"$namereg\" maxlenght=\"32\" size=\"16\"/>, \n";
            echo "Viewmode: <select name=\"ovtype\">";
            foreach ($ov_types as $act_ovt) {
                echo "<option value=\"$act_ovt\" ".($act_ovt == $act_ov_type ? " selected " : "").">$act_ovt</option>\n";
            }
            echo "</select>, only highest version: <input type=checkbox name=\"oh\" ".($only_highest ? "checked" : "")."/>, ";
            echo "<input type=submit value=\"select\" /></td></tr></table>";
            echo "</form>\n";
        //print_r($inst_p);
        //print_r($vars);
        //disassociation array
        if ($act_ov_type != "Maintenance") {
            $disass_array=array();
            $machs=array();
            $mach_change_array=array();
            $mres=query("SELECT d.name,d.device_idx,dt.identifier FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx $optsel",$sys_db_con);
            while ($dev_record=mysql_fetch_object($mres)) {
                $change=0;
                if (in_array("{$dev_record->name}_rf",array_keys($vars)) || in_array("global_rf",array_keys($vars))) $change=1;
                $name=$dev_record->name;
                $dev_record->inst_packages=array();
                $dev_record->ignore_packages=array();
                $machs[$dev_record->name]=&$dev_record;
                $mr2=query("SELECT i.inst_package_idx, id.instp_device_idx, id.install, id.upgrade, id.del, id.nodeps, id.forceflag, id.status, UNIX_TIMESTAMP(id.install_time) AS install_time FROM inst_package i, instp_device id, package p WHERE p.package_idx=i.package AND id.inst_package=i.inst_package_idx AND id.device=$dev_record->device_idx ORDER BY p.name,p.version,p.release");
                while ($p_rec=mysql_fetch_object($mr2)) {
                    if (!in_array($p_rec->inst_package_idx,array_keys($inst_p))) {
                        $dev_record->ignore_packages[]=$p_rec->inst_package_idx;
                    } else {
                        $pfix="{$dev_record->name}_{$p_rec->inst_package_idx}";
                        if ((is_set("{$p_rec->inst_package_idx}_global",&$vars) && $vars["{$p_rec->inst_package_idx}_global"] == "del") || (is_set("{$pfix}_dis",&$vars) && $vars["{$pfix}_dis"])) {
                            query("DELETE FROM instp_device WHERE inst_package=$p_rec->inst_package_idx AND device=$dev_record->device_idx");
                            $change=1;
                        } else {
                            if ($p_rec->install) {
                                $act_s="i";
                            } else if ($p_rec->upgrade) {
                                $act_s="u";
                            } else if ($p_rec->del) {
                                $act_s="d";
                            } else {
                                $act_s="n";
                            }
                            // flag for no change
                            $new_s="n";
                            // check for local setting
                            $c_idx="{$dev_record->name}_{$p_rec->inst_package_idx}";
                            if (isset($vars[$pfix])) $new_s=$vars[$pfix];
                            if ($new_s == "n") {
                                $c_idx="glob_{$p_rec->inst_package_idx}_ins";
                                if (isset($vars[$c_idx])) $new_s=$vars[$c_idx];
                                if ($new_s == "n") $new_s=$act_s;
                                //echo "glob: $new_s<br>";
                            }
                            $act_nodep=$p_rec->nodeps;
                            $act_forceflag=$p_rec->forceflag;
                            // flag for no change
                            $new_nodep="n";
                            $new_forceflag="n";
                            $c_idx="{$pfix}_nod";
                            if (isset($vars[$c_idx])) $new_nodep=$vars[$c_idx];
                            if ($new_nodep == "n") {
                                $c_idx="glob_{$p_rec->inst_package_idx}_nod";
                                if (isset($vars[$c_idx])) $new_nodep=$vars[$c_idx];
                            }
                            $c_idx="{$pfix}_ffl";
                            if (isset($vars[$c_idx])) $new_forceflag=$vars[$c_idx];
                            if ($new_forceflag == "n") {
                                $c_idx="glob_{$p_rec->inst_package_idx}_ffl";
                                if (isset($vars[$c_idx])) $new_forceflag=$vars[$c_idx];
                            }
                            if ($new_nodep == "n") $new_nodep=$act_nodep;
                            if ($new_forceflag == "n") $new_forceflag=$act_forceflag;
                            if ($new_s != $act_s || $new_nodep != $act_nodep || $new_forceflag != $act_forceflag) {
                                //echo "C $act_s $new_s $new_nodep : $act_nodep $new_forceflag : $act_forceflag <br>";
                                $p_rec->install=0;
                                $p_rec->upgrade=0;
                                $p_rec->del=0;
                                $p_rec->nodeps=0;
                                $p_rec->forceflag=0;
                                if ($new_s == "i") $p_rec->install=1;
                                if ($new_s == "u") $p_rec->upgrade=1;
                                if ($new_s == "d") $p_rec->del=1;
                                if ($new_nodep == "1") $p_rec->nodeps=1;
                                if ($new_forceflag == "1") $p_rec->forceflag=1;
                                $sql_str="UPDATE instp_device SET install=$p_rec->install, upgrade=$p_rec->upgrade, del=$p_rec->del, nodeps=$p_rec->nodeps, forceflag=$p_rec->forceflag WHERE instp_device_idx=$p_rec->instp_device_idx";
                                //echo "$sql_str<br>";
                                query($sql_str);
                                $change=1;
                                $act_s=$new_s;
                            }
                            $dev_record->inst_packages[$p_rec->inst_package_idx]=new instp_device($p_rec->inst_package_idx,$p_rec->install,$p_rec->upgrade,$p_rec->del,$p_rec->nodeps,$p_rec->forceflag,$p_rec->install_time,$p_rec->status);
                            $inst_p[$p_rec->inst_package_idx]->used++;
                            $inst_p[$p_rec->inst_package_idx]->idn_array[$act_s]++;
                            //echo $vars[$p_rec->inst_package_idx."_td"];
                        }
                    }
                }
                foreach ($inst_p as $idx=>$ip) {
                    if (is_set("{$idx}_global",&$vars) && $vars["{$idx}_global"] == "add" && !in_array($idx,array_keys($dev_record->inst_packages))) {
#print_r($dev_record->inst_packages);
#echo "<br>";
                        $change=1;
                        $new_s=$vars["glob_{$idx}_ins"];
                        $new_nodeps=$vars["glob_{$idx}_nod"];
                        $new_forceflag=$vars["glob_{$idx}_ffl"];
                        $i_flag=0;
                        $u_flag=0;
                        $d_flag=0;
                        $n_flag=0;
                        $f_flag=0;
                        if ($new_s == "i") $i_flag=1;
                        if ($new_s == "u") $u_flag=1;
                        if ($new_s == "d") $d_flag=1;
                        if ($new_nodeps == "1") $n_flag=1;
                        if ($new_forceflag == "1") $f_flag=1;
                        query("INSERT INTO instp_device VALUES(0,$idx,$dev_record->device_idx,$i_flag,$u_flag,$d_flag,$n_flag,$f_flag,0,'',null)");
                        $dev_record->inst_packages[$idx]=new instp_device($idx,$i_flag,$u_flag,$d_flag,$n_flag,$f_flag,0,'');
                        $inst_p[$idx]->idn_array[$new_s]++;
                        $inst_p[$idx]->used++;
                    }
                }
                unset($dev_record);
                if ($change) $mach_change_array[]=$name;
            }
            if (count($mach_change_array)) {
                $ret=contact_server($sys_config,"package_server",8007,"new_config ".implode(":",$mach_change_array));
                process_ret(&$hcproto,"package_server",8007,"new_config",$ret,$mach_change_array);
            }
            if ($hcproto->get_num_messages()) $hcproto->print_messages("");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
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
                        message("Found device ".$mach_list[0]." in devicegroup ".key($display_a));
                    } else {
                        message("Found $n1 devices in devicegroup ".key($display_a));
                    }
                }
                echo "<table class=\"normal\">\n";
                foreach ($display_a as $act_group=>$display_g) {
                    list($n1,$n2,$mach_list)=$display_g;
                    if (count($display_a) > 1) echo "<tr><td colspan=\"13\" class=\"machinegroup\">devicegroup: $act_group , selected $n1 of $n2 devices</td></tr>\n";
                    foreach ($mach_list as $mach_name) {
                        $ip=&$machs[$mach_name];
                        echo "<tr>";
                        $num_ip=count($ip->inst_packages);
                        if ($act_ov_type == "Overview") {
                            $show_info=1;
                            $row_span=1;
                        } else {
                            if ($num_ip) {
                                $show_info=1;
                                $row_span=$num_ip+2;
                            } else {
                                $show_info=0;
                                $row_span=1;
                            }
                        }
                        echo "<td class=\"nameup\" rowspan=\"$row_span\">$ip->name, <input type=checkbox name=\"$ip->name.rf\" value=\"refresh\"/></td>";
                        echo "<input type=\"hidden\" name=\"$mach_name.dummy\" />";
                        if ($ip->ignore_packages) {
                            $ignore_str=", ".get_plural("package",count($ip->ignore_packages),1)." ignored";
                        } else {
                            $ignore_str="";
                        }
                        if ($show_info) {
                            $num_inst_p=count($ip->inst_packages);
                            if ($act_ov_type == "Overview") {
                                $info_array=array("ok"=>array(0,array(),"OK"),
                                                  "error"=>array(0,array(),"Error"),
                                                  "ns"=>array(0,array(),"Not set"));
                                $num_ok=0;
                                $num_error=0;
                                $num_notset=0;
                                $num_inst=0;
                                $num_del=0;
                                $num_keep=0;
                                $num_r_inst=0;
                                $num_r_del=0;
                                foreach ($ip->inst_packages as $ip_idx=>$ins_p) {
                                    if ($ins_p->install || $ins_p->upgrade) {
                                        $num_inst++;
                                    } else if ($ins_p->del) {
                                        $num_del++;
                                    } else {
                                        $num_keep++;
                                    }
                                    $status=$ins_p->status;
                                    if (strlen($status)) {
                                        if (preg_match("/^ok.*$/",$status)) {
                                            if (preg_match("/installed/",$status)) {
                                                $num_r_inst++;
                                            } else if (preg_match("/deleted/",$status)) {
                                                $num_r_del++;
                                            }
                                            $info_array["ok"][0]++;
                                        } else {
                                            $info_array["error"][0]++;
                                            $info_array["error"][1][]=$inst_p[$ins_p->inst_package_idx]->name;
                                        }
                                    } else {
                                        $info_array["ns"][0]++;
                                    }
                                }
                                $out_str="$num_inst_p ".get_plural("installable package",$num_inst_p)." associated$ignore_str ($num_inst";
                                if ($num_r_inst != $num_inst) $out_str.=" (act: $num_r_inst)";
                                $out_str.=" inst, $num_del";
                                if ($num_r_del != $num_del) $out_str.=" (act: $num_r_del)";
                                $out_str.=" del, $num_keep keep)";
#$out_str.=" ($num_ok, $num_error, $num_notset)";
                                echo "<td colspan=\"4\" class=\"pass\">$out_str</td>";
                                foreach ($info_array as $pfix=>$act_stuff) {
                                    list($act_num,$act_list,$act_pf)=$act_stuff;
                                    if ($act_num) {
                                        $out_str="$act_pf : $act_num";
                                        if (count($act_list)) $out_str.=" (".implode(", ",$act_list).")";
                                    } else {
                                        $out_str="-";
                                    }
                                    echo "<td class=\"statov$pfix\">$out_str</td>";
                                }
                                echo "</tr>\n";
                            } else {
                                //echo "<td>";
                                //echo "<table class=\"blind\"><tr>";
                                echo "<td colspan=\"12\" class=\"pass\">";
                                echo "$num_inst_p ".get_plural("installable package",$num_inst_p)." associated$ignore_str";
                                echo "</td></tr>\n";
                                echo "<tr>";
                                foreach (array("Packagename"=>"pname","Arch"=>"parch","Version"=>"pversion","Release"=>"prelease",
                                               "TState"=>"tstate","Actstate"=>"astate","nodeps"=>"tstate","force"=>"tstate","Flags"=>"astate",
                                               "Disass."=>"remove","Install date"=>"pname","Status"=>"status") as $name=>$css) echo "<th class=\"$css\">$name</th>\n";
                                echo "</tr>";
                                foreach ($ip->inst_packages as $ip_idx=>$ins_p) {
                                    $pckg_info=&$inst_p[$ip_idx];
                                    echo "<tr>";
                                    echo "<td class=\"pname\">$pckg_info->name</td>";
                                    echo "<td class=\"parch\">$pckg_info->arch</td>";
                                    echo "<td class=\"pversion\">$pckg_info->version</td>";
                                    echo "<td class=\"prelease\">$pckg_info->release</td>";
                                    $act_stat="n";
                                    if ($ins_p->install) {
                                        $act_stat="i";
                                    } else if ($ins_p->upgrade) {
                                        $act_stat="u";
                                    } else if ($ins_p->del) {
                                        $act_stat="d";
                                    }
                                    $act_flags=array();
                                    if ($ins_p->nodeps) $act_flags[]="--nodeps";
                                    if ($ins_p->forceflag) $act_flags[]="--force";
                                    if (!count($act_flags)) $act_flags[]="no flags";
                                    echo "<td class=\"tstate\"><select name=\"$ip->name.$ip_idx\">";
                                    foreach ($ins_states as $long=>$short) {
                                        echo "<option value=\"$short\" ";
                                        if ($short == "n")echo " selected ";
                                        echo ">$long</option>\n";
                                        if ($act_stat == $short) $act_stat_long=$long;
                                    }
                                    echo "</select></td>\n";
                                    echo "<td class=\"astate\">$act_stat_long</td>";
                                    echo "<td class=\"tstate\"><select name=\"$ip->name.{$ip_idx}.nod\">";
                                    foreach ($nodep_states as $long=>$short) {
                                        echo "<option value=\"$short\" ";
                                        if ($short == "n") echo " selected ";
                                        echo ">$long</option>\n";
                                    }
                                    echo "</select></td>\n";
                                    echo "<td class=\"tstate\"><select name=\"$ip->name.{$ip_idx}.ffl\">";
                                    foreach ($forceflag_states as $long=>$short) {
                                        echo "<option value=\"$short\" ";
                                        if ($short == "n") echo " selected ";
                                        echo ">$long</option>\n";
                                    }
                                    echo "</select></td>\n";
                                    echo "<td class=\"astate\">".implode(", ",$act_flags)."</td>";
                                    echo "<td class=\"remove\"><input type=checkbox name=\"{$ip->name}.{$ip_idx}.dis\"  /></td>\n";
                                    echo "<td class=\"pname\">".$ins_p->get_install_time()."</td>\n";
                                    $status=$ins_p->status;
                                    if (strlen($status)) {
                                        if (preg_match("/^ok.*$/",$status)) {
                                            $css="statok";
                                        } else {
                                            $css="staterror";
                                        }
                                    } else {
                                        $css="statns";
                                        $status="Not set";
                                    }
                                    echo "<td class=\"$css\">$status</td>";
                                    echo "</tr>\n";
                                }
                            }
                            //echo "</table>\n";
                            //echo "</td>\n";
                        } else {
                            echo "<td colspan=\"12\" class=\"pnoass\">No packages associated$ignore_str</td>";
                        }
                        echo "</tr>\n";
                    }
                }
                echo "</table>\n";
                echo "<div class=\"center\">Refresh all:<input type=checkbox name=\"global.rf\" value=\"refresh\"/></div>\n";
            } else {
                message ("No devices found");
            }
            if ($inst_p) {
            message("Global Package actions",$type=2);
            echo "<table class=\"normalnf\">\n";
            echo "<tr>";
            echo "<th class=\"pinfo\" colspan=\"".(in_array(-1,$pg_selected) ? "5" : "4")."\">PackageInfo</th>\n";
            if (count($machs)) {
                echo "<th class=\"none\" colspan=\"3\">Associate</th>\n";
                echo "<th class=\"tstate\" colspan=\"3\">State / Flags</th>\n";
                echo "<th class=\"nkeep\" colspan=\"4\">Statistics</th>\n";
            }
            echo "</tr>\n";
            echo "<tr>";
            foreach (array("Packagename"=>"pname") as $name=>$css) echo "<th class=\"$css\">$name</th>\n";
            if (in_array(-1,$pg_selected)) echo "<th class=\"pgroup\">Group</th>\n";
            foreach (array("Arch"=>"parch","Version"=>"pversion","Release"=>"prelease") as $name=>$css) echo "<th class=\"$css\">$name</th>\n";
            if (count($machs)) {
                foreach (array("None"=>"none","Add"=>"add","Rem"=>"del","TState"=>"tstate","nodep"=>"tstate","force"=>"tstate",
                               "Keep"=>"nkeep","Install"=>"nins","upgrade"=>"nins","Delete"=>"ndel")
                         as $name=>$css) echo "<th class=\"$css\">$name</th>\n";
            }
            echo "</tr>\n";
            $last_idx=-1;
            $last_pre_name="";
            foreach ($inst_p as $idx=>$ip) {
                $inst_p[$idx]->highest_version=1;
                preg_match("/^(\D+).*$/",$ip->name,$ipp);
                $pre_name=$ipp[1];
                $inst_p[$idx]->pre_name=$pre_name;
                if ($last_idx >= 0 && $inst_p[$last_idx]->pre_name == $pre_name) {
                    $inst_p[$last_idx]->highest_version=0;
                }
                $last_idx=$idx;
            }
            $last_pgroup="";
            foreach ($all_pgroups as $pg_name=>$pg_stuff) {
                foreach ($inst_p as $idx=>$ip) {
                    if ((min($pg_selected) == -1 || (min($pg_selected) == -2 && $pg_name==$ip->pgroup) || (max($pg_selected) > 0 && $pg_name==$ip->pgroup && in_array($pg_stuff["idx"],$pg_selected))) && !$ip->displayed) {
                        if ($ip->highest_version) {
                            $pf="h";
                            $show=1;
                        } else {
                            $pf="";
                            if ($only_highest) {
                                $show=0;
                            } else {
                                $show=1;
                            }
                        }
                        if ($show) {
                            if ($ip->used && ($ip->idn_array["n"] || $ip->idn_array["d"])) $pf="err";
                            if ($pg_name != $last_pgroup && !in_array(-1,$pg_selected)) {
                                $last_pgroup=$pg_name;
                                echo "<tr><td class=\"pgroupc\" colspan=\"14\">$pg_name</td></tr>\n";
                            }
                            $inst_p[$idx]->displayed=1;
                            echo "<tr>";
                            echo "<td class=\"pname$pf\">$ip->name</td>";
                            if (in_array(-1,$pg_selected)) echo "<td class=\"pgroup$pf\">$ip->pgroup</td>\n";
                            echo "<td class=\"parch$pf\">$ip->arch</td>\n";
                            echo "<td class=\"pversion$pf\">$ip->version</td>\n";
#echo "<td class=\"prelease\">$ip->release, $ip->used, ".strval(count($actmach))."</td>\n";
                            echo "<td class=\"prelease$pf\">$ip->release</td>\n";
                            if (count($machs)) {
                                // global is short for global association level
                                echo "<td class=\"none$pf\"><input type=radio name=\"$idx.global\" value=\"none\" checked/>";
                                echo "ass. to $ip->used, unass. to ".strval(count($actmach)-$ip->used);
                                echo "</td>";
                                echo "<td class=\"add$pf\">";
                                if ($ip->used == count($actmach)) {
                                    echo "-";
                                } else {
                                    echo "<input type=radio name=\"$idx.global\" value=\"add\" />";
                                }
                                echo "</td><td class=\"del$pf\">";
                                if ($ip->used) {
                                    echo "<input type=radio name=\"$idx.global\" value=\"del\" />";
                                } else {
                                    echo "-";
                                }
                                echo "</td><td class=\"tstate$pf\">\n";
                                echo "<select name=\"glob.$idx.ins\">";
                                foreach ($ins_states as $long=>$short) echo "<option value=\"$short\" ".($short=="n" ? "selected" : "").">$long</option>\n";
                                echo "</select>\n";
                                echo "</td>\n";
                                echo "<td class=\"tstate$pf\">\n";
                                show_opt_list("glob.$idx.nod",$nodep_states,"n");
                                echo "</td>\n";
                                echo "<td class=\"tstate$pf\">\n";
                                echo "<select name=\"glob.$idx.ffl\">";
                                foreach ($forceflag_states as $long=>$short) echo "<option value=\"$short\" ".($short=="n" ? "selected" : "").">$long</option>\n";
                                echo "</select>\n";
                                echo "</td>\n";
                                $ref_a=array("n"=>"keep","i"=>"ins","u"=>"ins","d"=>"del");
                                foreach ($ref_a as $what=>$ttype) echo "<td class=\"n$ttype$pf\">".(!$ip->used ? "-" : $ip->idn_array[$what])."</td>\n";
                            }
                            echo "</tr>";
                        }
                    }
                }
            }
            echo "</table>\n";
            } else {
                message("No packages found");
            }
        } else {
            if ($hcproto->get_num_messages()) $hcproto->print_messages("");
            $mres=query("SELECT i.inst_package_idx, id.instp_device_idx FROM inst_package i, instp_device id WHERE id.inst_package=i.inst_package_idx");
            while ($mfr=mysql_fetch_object($mres)) {
                if (in_array($mfr->inst_package_idx,array_keys($inst_p))) {
                    $inst_p[$mfr->inst_package_idx]->idn_array["a"]++;
                }
            }
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            if ($inst_p) {
                message("Package maintenance",$type=1);
            echo "<table class=\"normalnf\">\n";
            echo "<tr>";
            foreach (array("PackageName"=>"pinfo","Architecture"=>"parch","Version"=>"pversion","Release"=>"prelease",
                           "Group"=>"pgroupc","Packager"=>"pnamer","BuildHost"=>"pname","Size"=>"tstate",
                           "Associations"=>"nins","Delete"=>"del") as $title=>$class) {
                echo "<th class=\"$class\" >$title</th>\n";
            }
            echo "</tr>\n";
            $last_pgroup="";
            $pg_names=array_keys($all_pgroups);
            foreach ($all_pgroups as $pg_name=>$pg_stuff) {
                foreach ($inst_p as $idx=>$ip) {
                    if ((min($pg_selected) == -1 || (min($pg_selected) == -2 && $pg_name==$ip->pgroup) || (max($pg_selected) > 0 && $pg_name==$ip->pgroup && in_array($pg_stuff["idx"],$pg_selected))) && !$ip->displayed) {
                        if ($pg_name != $last_pgroup && !in_array(-1,$pg_selected)) {
                            $last_pgroup=$pg_name;
                            echo "<tr><td class=\"pgroupc\" colspan=\"13\">$pg_name</td></tr>\n";
                        }
                        $inst_p[$idx]->displayed=1;
                        echo "<tr>";
                        echo "<td class=\"pname\">$ip->name</td>";
                        echo "<td class=\"parch\">$ip->arch</td>\n";
                        echo "<td class=\"pversion\">$ip->version</td>\n";
                        echo "<td class=\"prelease\">$ip->release</td>\n";
                        echo "<td class=\"pnoass\"><select name=\"ng_$idx\">";
                        foreach ($pg_names as $pgn) {
                            $pgs=$all_pgroups[$pgn];
                            echo "<option value=\"${pgs['idx']}\" ".($ip->pgroup == $pgn ? "selected" : "").">$pgn</option>\n";
                        }
                        echo "</select></td>\n";
                        $packager=$ip->packager;
                        //$build_host=$ip->build_host;
                        list($pack,$host)=explode("@",$packager,2);
                        $build_host=$host;
                        if ($host == $build_host) $packager="$pack@";
                        echo "<td class=\"pnamer\">$packager</td>\n";
                        echo "<td class=\"pname\">$host</td>\n";
                        echo "<td class=\"tstate\">".get_size_str($ip->size)."</td>\n";
                        echo "<td class=\"nins\">".($ip->idn_array["a"] ? $ip->idn_array['a'] : "-")."</td>\n";
                        echo "<td class=\"del\">";
                        if ($ip->idn_array["a"]) {
                            echo "&nbsp;";
                        } else {
                            echo "<input name=\"delp_$idx\" type=checkbox />";
                        }
                        echo "</td>\n";
                        echo "</tr>\n";
                    }
                }
            }
            echo "</table>\n";
            } else {
                message("No matching packages found in database",$type=1);
            }
        }
        hidden_sid();
        echo $hidden_archs;
        echo $hidden_namereg;
        echo $hiddenmach;
        echo $hidden_highest;
        echo $hidden_pg_sel;
        echo $hidden_ov_type;
        echo "<div class=\"center\"><input type=submit value=\"submit\"></div>";
        echo "</form>";
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
