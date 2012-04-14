<?php
//-*ics*- ,CAP,name:'ai',descr:'Application install',enabled:1,defvalue:0,scriptname:'/php/applicationinstall.php',left_string:'Application install',right_string:'Define and install applications without rebooting',capability_group_name:'conf',pri:30
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
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["ai_en"] == 1) {
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
    clusterhead($sys_config,"Application install page",$style="formate.css",
                array("td.pass"=>array("background-color:#eedd88","text-align:center"),
                      "th.pinfo"=>array("background-color:#e2f2d2","text-align:center"),
                      "th.pname"=>array("background-color:#e2f2d2","text-align:left"),
                      "td.pname"=>array("background-color:#d2e2c2","text-align:left"),
                      "td.pnameh"=>array("background-color:#e2f2d2","text-align:left"),
                      "td.pnameerr"=>array("background-color:#ff8888","text-align:left"),
                      "th.pgroup"=>array("background-color:#d2e2c2","text-align:left"),
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
    clusterbody($sys_config,"Application install",array(),array("conf"));
    if ($ucl["ai"]) {
        // read package-info
        $inst_p=array();
        $mres=query("SELECT p.*,ip.*,a.architecture as arch FROM package p, inst_package ip, architecture a WHERE a.architecture_idx=p.architecture AND ip.package=p.package_idx ORDER BY p.name, p.version,p.release");
        while ($mfr=mysql_fetch_object($mres)) {
            $mfr->displayed=0;
            $mfr->used=0;
            $mfr->idn_array=array("i"=>0,"d"=>0,"n"=>0);
            $inst_p[$mfr->inst_package_idx]=$mfr;
        }
        // sort types
        $so_types=array(-1=>"Show all, sort by Name",
                        -2=>"Show all, sort by Group (and Name)");
        // all groups
        $all_pgroups=array();
        $act_idx=0;
        // add all groups
        foreach ($inst_p as $ip_idx=>$ip_stuff) {
            if (!$ip_stuff->pgroup) $ip_stuff->pgroup="unknown";
            if (!in_array($ip_stuff->pgroup,array_keys($all_pgroups))) $all_pgroups[$ip_stuff->pgroup]=array("num"=>0,"idx"=>++$act_idx);
            $all_pgroups[$ip_stuff->pgroup]["num"]++;
        }
        foreach ($all_pgroups as $pg_name=>$pg_stuff) {
            $so_types[$pg_stuff["idx"]]="Group $pg_name ({$pg_stuff['num']} packages)";
        }
        //print_r($all_pgroups);
        // Display types
        $ov_types=array("Overview","Detailed");
        if (in_array("ovtype",array_keys($vars))) {
            $act_ov_type=$vars["ovtype"];
        } else {
            $act_ov_type=$ov_types[0];
        }
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
        foreach ($pg_selected as $pgs) $hidden_pg_sel="<input type=hidden name=\"pgs[]\" value=\"$pgs\"/>\n";
        $only_highest=0;
        $hidden_highest="";
        if (in_array("oh",&$varkeys)) {
            $only_highest=1;
            $hidden_highest="<input type=hidden name=\"oh\" value=\"$only_highest\" />\n";
        }
        // simple protocol
        $hcproto=new messagelog();
        $hidden_ov_type="<input type=hidden name=\"ovtype\" value=\"$act_ov_type\"/>";
        // simple protocol
        if (count($machgroups)) {
            message ("Please select devicegroup or device(s) by their name:");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
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
            hidden_sid();
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
            echo "</tr>\n<tr>";
            echo "<td colspan=\"5\">";
            echo "<select name=\"ovtype\">";
            foreach ($ov_types as $act_ovt) {
                echo "<option value=\"$act_ovt\" ";
                if ($act_ovt == $act_ov_type) echo " selected ";
                echo ">$act_ovt</option>";
            }
            echo "</select>, only highest version: <input type=checkbox name=\"oh\" ".($only_highest ? "checked" : "")."/>, ";
            echo "<input type=submit value=\"select\" /></td></tr></table>";
            echo "</form>\n";
        }
        echo "<div class=\"center\"><input type=submit value=\"submit\"></div>";
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
