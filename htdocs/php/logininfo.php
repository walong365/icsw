<?php
//-*ics*- ,CAPG,name:'user',descr:'User configuration',pri:20
//-*ics*- ,CAP,name:'li',defvalue:1,enabled:1,descr:'Login information',scriptname:'/php/logininfo.php',left_string:'Login info',right_string:'Information about your account',capability_group_name:'user',pri:-20
//-*ics*- ,CAP,name:'mg',defvalue:0,enabled:1,descr:'Modify Groups',mother_capability_name:'li'
//-*ics*- ,CAP,name:'bg',defvalue:0,enabled:1,descr:'Browse Groups',mother_capability_name:'li'
//-*ics*- ,CAP,name:'mu',defvalue:0,enabled:1,descr:'Modify Users',mother_capability_name:'li'
//-*ics*- ,CAP,name:'bu',defvalue:0,enabled:1,descr:'Browse Users',mother_capability_name:'li'
//-*ics*- ,CAP,name:'mp',defvalue:1,enabled:1,descr:'Modify personal info',mother_capability_name:'li'
//-*ics*- ,CAP,name:'sql',defvalue:0,enabled:1,descr:'Display SQL statistics',mother_capability_name:'li'
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
function show_jump_target($what,$action,$left_string,$right_string,$rb=0) {
    echo "<tr><td class=\"right\">";
    if ($rb) {
        echo "$left_string <input type=radio name=\"action\" value=\"$action\" ";
        if ($rb == 2) echo " checked ";
        echo " />";
    } else {
        echo "<a class=\"front\" href=\"mod{$what}.php?".write_sid()."&action=$action\">$left_string</a>";
    }
    echo "</td>\n";
    echo "<td class=\"left\">$right_string</td></tr>\n";
}
function fill_user_table($max,$act) {
    while($act++ < $max) echo "<td>&nbsp</td>\n";
}
require_once "mysql.php";
require_once "config.php";
require_once "htmltools.php";
require_once "tools.php";
require_once "capability.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["hwi_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    htmlhead();
    $clustername=$sys_config["CLUSTERNAME"];
    clusterhead($sys_config,"Login information page","formate.css");
    clusterbody($sys_config,"Login information page",array(),array("info"));
    list($gl,$gln)=getgroups($sys_db_con);
    $ul=getusers($sys_db_con);
    // get user info
    $suser=$ul[$sys_config["session_user"]];
    $sgroup=$gl[$suser->ggroup];
    printuser($suser,$gl);
    // show capabilities
    $ucl=usercaps($sys_db_con);
    if (count(array_keys($ucl))) {
        if (isset($ucl["bg"]) || isset($ucl["mg"])) {
            message("Group options:",$type=2);
            echo "<form action=\"modgroup.php?".write_sid()."\" method=post>";
            echo "<table class=\"front1\" ><tr><td><table class=\"front2\" >\n";
            if ($ucl["mg"]) {
                echo "<tr><td class=\"fronthl\" colspan=\"2\">Global group options:</td></tr>\n";
                show_jump_target("group","newgroup","Create group","Create a new group");
                show_jump_target("group","browseall","Browse all","Show all groups");
            }
            $num_g=count($gl);
            $fc_array=array();
            foreach ($gl as $g=>$gstuff) {
                $nfkey=substr($gstuff->ggroupname,0,1);
                if (!in_array($nfkey,array_keys($fc_array))) $fc_array[$nfkey]=0;
                $fc_array[$nfkey]++;
            }
            echo "<tr><td class=\"fronthl\" colspan=\"2\">Option on selected group ";
            echo "<select name=\"bgname\" >";
            $fkey="-";
            foreach ($gl as $g=>$gstuff) {
                $num_p=0;
                $num_s=0;
                foreach ($ul as $uname=>$u_stuff) {
                    if ($u_stuff->ggroup == $gstuff->ggroup_idx) $num_p++;
                    if (in_array($gstuff->ggroup_idx,$u_stuff->sgroup_idx)) $num_s++;
                }
                $nfkey=substr($gstuff->ggroupname,0,1);
                if ($nfkey != $fkey) {
                    $num_nfk=$fc_array[$nfkey];
                    echo "<option disabled >-- $nfkey ($num_nfk ".get_plural("group",$num_nfk).") ------</option>\n";
                    $fkey=$nfkey;
                }
                echo "<option value=\"{$gstuff->ggroupname}\" >";
                if (!$gstuff->active) echo "(*)";
                echo "$gstuff->ggroupname [$gstuff->gid], $num_p ".get_plural("primary user",$num_p)." found";
                if ($num_s) echo", $num_s ".get_plural("secondary user",$num_s)." found";
                echo "</option>\n";
            }
            echo "</select> (".get_plural("group",$num_g,1)." defined):</td></tr>";
            $rb_flag=2;
            if ($ucl["bg"]) {
                show_jump_target("group","bgroup","Browse","Show information about selected group",$rb_flag);
                $rb_flag--;
            }
            if ($ucl["mg"]) {
                show_jump_target("group","editgroup","Edit Group","Edit information about selected group",$rb_flag);
                if ($rb_flag == 2) $rb_flag--;
                show_jump_target("group","inactgroup","Disable Group","The selected group is set inactive",$rb_flag);
                show_jump_target("group","actgroup","Enable Group","The selected group is set active",$rb_flag);
            }
            if ($ucl["mg"]) {
                show_jump_target("group","delgroup","Delete Group","The selected group is deleted",$rb_flag);
            }
            echo "<tr><td class=\"center\" colspan=\"2\"><input type=submit value=\"select\" /></td></tr>\n";
            echo "</table></td></tr></table></form>\n";
        }
        //echo "</table>\n";
        //echo "<table class=\"user\" >";
        if (isset($ucl["mu"]) || isset($ucl["bu"]) || isset($ucl["mp"])) {
            message("User options:",$type=2);
            echo "<form action=\"moduser.php?".write_sid()."\" method=post >";
            echo "<table class=\"front1\" ><tr><td><table class=\"front2\" >";
            if (isset($ucl["mu"]) || isset($ucl["mp"])) {
                if (isset($ucl["mu"])) {
                    echo "<tr><td class=\"fronthl\" colspan=\"2\">Global user options:</td></tr>\n";
                    show_jump_target("user","newuser","Create user","Create a new user");
                    show_jump_target("user","browseall","Browse all","Show all users");
                }
                if (isset($ucl["mp"])) {
                    echo "<tr><td class=\"fronthl\" colspan=\"2\">Local user options:</td></tr>\n";
                    show_jump_target("user","editpers","Edit personal data","Edit your personal information");
                }
            }
            if (isset($ucl["mu"]) || isset($ucl["bu"])) {
                $num_u=count($ul);
                $fc_array=array();
                foreach ($ul as $u=>$u_stuff) {
                    $nfkey=substr($u_stuff->login,0,1);
                    if (!in_array($nfkey,array_keys($fc_array))) $fc_array[$nfkey]=0;
                    $fc_array[$nfkey]++;
                }
                echo "<tr><td class=\"fronthl\" colspan=\"2\" >Option on selected user <select name=\"buname\" >";
                $fkey="-";
                foreach ($ul as $u=>$u_stuff) {
                    $nfkey=substr($u_stuff->login,0,1);
                    if ($nfkey != $fkey) {
                        $num_nfk=$fc_array[$nfkey];
                        echo "<option disabled >-- $nfkey ($num_nfk ".get_plural("user",$num_nfk).") ------</option>\n";
                        $fkey=$nfkey;
                    }
                    echo "<option value=\"{$u_stuff->login}\" >{$u_stuff->login} [{$u_stuff->uid}], pgroup {$gl[$u_stuff->ggroup]->ggroupname} [{$gl[$u_stuff->ggroup]->gid}]";
                    if (count($u_stuff->sgroup_idx)) {
                        $sgroup_list=array();
                        foreach ($u_stuff->sgroup_idx as $sg_idx) {
                            $sgroup_list[]="{$gl[$sg_idx]->ggroupname} [{$gl[$sg_idx]->gid}]";
                        }
                        echo ", ".get_plural("sgroup",count($u_stuff->sgroup_idx))." ".implode(", ",$sgroup_list);
                    }
                    echo "</option>\n";
                }
                echo "</select> (".get_plural("user",$num_u,1)." defined):</td></tr>\n";
                $rb_flag=2;
                if ($ucl["bu"]) {
                    show_jump_target("user","buser","Browse","Show information about selected user",$rb_flag);
                    $rb_flag--;
                }
                if ($ucl["mu"]) {
                    show_jump_target("user","edituser","Edit User","Edit information about selected user",$rb_flag);
                    if ($rb_flag == 2) $rb_flag--;
                    show_jump_target("user","inactuser","Disable User","The selected user is set inactive",$rb_flag);
                    show_jump_target("user","actuser","Enable User","The selected user is set active",$rb_flag);
                }
                if ($ucl["mu"]) {
                    show_jump_target("user","deluser","Delete User","The selected user is deleted",$rb_flag);
                }
                echo "<tr><td class=\"center\" colspan=\"2\"><input type=submit value=\"select\" /></td></tr>\n";
            }
        }
        echo "</table></td></tr></table></form>\n";
    } else {
        message("No capabilities defined",$type=2);
    }
    writefooter($sys_config);
}
?>
