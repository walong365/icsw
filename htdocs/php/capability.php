<?php
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
require_once "tools.php";
function find_user_export($name,$type) {
    $sc_name="{$type}export";
    $match_col=array("homeexport"=>"export","scratchexport"=>"export_scr");
    $match_col=$match_col[$sc_name];
    $eq=query("SELECT d.name,sc.value FROM device d, device_config dc, new_config c, config_str sc, user u WHERE u.login='$name' ".
              "AND dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND u.$match_col=dc.device_config_idx ".
              "AND sc.new_config=c.new_config_idx AND sc.name='$sc_name'");
    return mysql_fetch_object($eq);
}
function printggroup($gob) {
    if ($gob->active) {
        $actstr="active";
    } else {
        $actstr="inactive";
    }
    message("Info about $actstr group $gob->ggroupname",$type=1);
    echo "<table class=\"user\">";
    echo "<tr>";
    echo "<td class=\"fronthlr\">Var</td><td class=\"fronthll\">Value</td>";
    echo "<td class=\"fronthlr\">Var</td><td class=\"fronthll\">Value</td>";
    echo "</tr>\n";
    echo "<tr>";
    echo "<td class=\"right\">Groupname:</td><td class=\"left\">$gob->ggroupname</td>\n";
    echo "<td class=\"right\">Gid:</td><td class=\"left\">$gob->gid</td>\n";
    echo "</tr>\n<tr>";
    echo "<td class=\"right\">Homestart:</td><td class=\"left\">$gob->homestart</td>\n";
    echo "<td class=\"right\">Telefon:</td><td class=\"left\">".btf_string($gob->resptel)."</td>";
    echo "</tr>\n<tr>";
    echo "<td class=\"right\">Responsible Persion:</td><td class=\"left\">".btf_string(trim($gob->resptitan." ".$gob->respvname." ".$gob->respnname))."</td>\n";
    echo "<td class=\"right\">e-mail:</td><td class=\"left\">".btf_string($gob->respemail)."</td>\n";
    echo "</tr>\n<tr>";
    echo "<td class=\"right\">Comment:</td><td class=\"left\">".btf_string($gob->respcom)."</td>\n";
    echo "<td class=\"right\">Group Comment:</td><td class=\"left\">".btf_string($gob->groupcom)."</td>\n";
    echo "</tr></table>\n";
    printcapabilities(get_group_caps_struct($gob->ggroupname));
    $mret=query("SELECT u.login,u.uid,u.home FROM user u, ggroup g WHERE u.ggroup=g.ggroup_idx AND g.ggroupname='$gob->ggroupname'");
    if (mysql_num_rows($mret)) {
        $num_u=mysql_num_rows($mret);
        $mes_str="$num_u ".get_plural("user",$num_u)." defined";
        message($mes_str,$type=1);
        echo "<table class=\"user\">\n";
        while ($user=mysql_fetch_object($mret)) {
            echo "<tr><td class=\"right\">$user->login</td><td class=\"left\">(uid = $user->uid)</td><td class=\"left\">homedir = $gob->homestart"."$user->home</td></tr>\n";
        }
        echo "</table>";
    } else {
        message("No Users defined for this group",$type=1);
    }
}
function printuser($us,$gst,$capabilities=1) {
    $gs=$gst[$us->ggroup];
    if ($us->active) {
        $actstr="active";
    } else {
        $actstr="inactive";
    }
    $mes_str="$us->usertitan $us->uservname $us->usernname";
    if (trim($mes_str)) {
        $mes_str.=" (login: $us->login)";
    } else {
        $mes_str="$us->login";
    }
    message("Info about $actstr user $mes_str");
    $max_row=2;
    $act_row=0;
    $sgroup_c=count($us->sgroup_idx);
    if ($sgroup_c) {
        $sgroup_a=array();
        foreach ($us->sgroup_idx as $idx) {
            $sgroup_a[]="{$gst[$idx]->ggroupname} ({$gst[$idx]->gid})";
        }
        $sgroup_v=implode(", ",$sgroup_a);
    } else {
        $sgroup_v="None";
    }
    $hexp=find_user_export($us->login,"home");
    if ($hexp) {
        $hex_val="$gs->homestart$us->home ($hexp->value/$us->home on $hexp->name)";
    } else {
        $hex_val="None";
    }
    $sexp=find_user_export($us->login,"scratch");
    if ($sexp) {
        $sex_val="$gs->scratchstart$us->scratch ($sexp->value/$us->scratch on $sexp->name)";
    } else {
        $sex_val="None";
    }
    
    echo "<table class=\"user\">";
    foreach (array(array("Login",$us->login),
                   array("userid",$us->uid),
                   array("Primary group","$gs->ggroupname ($gs->gid)"),
                   array(get_plural("Secondary group",$sgroup_c),$sgroup_v),
                   array("Home dir",$hex_val),
                   array("Scratch dir",$sex_val),
                   array("Responsible persion",btf_string(trim("$us->usertitan $us->uservname $us->usernname"))),
                   array("Telefon",btf_string($us->usertel)),
                   array("e-mail",btf_string($us->useremail)),
                   array("Pager",btf_string($us->userpager)),
                   array("Comment",btf_string($us->usercom))) as $stuff) {
        list($info,$val)=$stuff;
        if (!$act_row++) echo "<tr>";
        echo "<td class=\"right\">$info:</td><td class=\"left\">$val</td>";
        if ($act_row == $max_row) {
            echo "</tr>\n";
            $act_row=0;
        }
    }
    if ($act_row) {
        while ($act_row++ < $max_row) echo "<td>&nbsp;</td>";
        echo "</tr>\n";
    }
    echo "</table>";
    if ($capabilities) printcapabilities(get_group_caps_struct($gs->ggroupname));
}
function printcapabilities($caps,$modify=0,$g_caps=0,$vars=array()) {
    if ($caps["total"]) {
        message(strval($caps["total"])." capabilities defined",$type=1);
        echo "<table class=\"user\">\n";
        $maxr=3;
        $idx=0;
        foreach ($caps as $group=>$cap_l) {
            if (!in_array($group,array("total")) && $cap_l["num"]) {
                echo "<tr><td colspan=\"".strval($maxr*2)."\" class=\"fronthl\">$group</td></tr>\n";
                $numr=0;
                foreach ($cap_l["caps"] as $capname=>$cap_stuff) {
                    $sub_cap_str="";
                    foreach ($cap_stuff as $capn=>$cap) {
                        $idx++;
                        if (!$numr++) echo "<tr>";
                        if ($modify) {
                            $left_string="<input type=checkbox name=\"$capn\" value=\"on\" ";
                            if ($g_caps) {
                                if (in_array($group,array_keys($g_caps))) {
                                    if (in_array($capname,array_keys($g_caps[$group]["caps"]))) {
                                        if (in_array($capn,array_keys($g_caps[$group]["caps"][$capname]))) $left_string.=" checked ";
                                    }
                                }
                            } else if ($vars) {
                                if (is_set($capn,&$vars)) $left_string.=" checked ";
                            } else {
                                if ($cap["def"]) $left_string.=" checked ";
                            }
                            $left_string.=">";
                        } else {
                            $left_string="$idx.";
                        }
                        echo "<td class=\"right\">$left_string</td><td class=\"left\">$sub_cap_str{$cap['descr']}</td>\n";
                        if ($numr == $maxr) {
                            echo "</tr>\n";
                            $numr=0;
                        }
                        $sub_cap_str="(*) ";
                    }
                }
                if ($numr) {
                    echo "<td colspan=\"".strval(($maxr-$numr)*2)."\" >&nbsp;</td></tr>\n";
                }
            }
        }
        echo "</table>\n";
    } else {
        message("No capabilities defined",$type=1);
    }
}
?>
