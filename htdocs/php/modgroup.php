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
function group_mask(&$sys_config,$min_gid,$max_gid,$group_act,$gname="",$vars=array()) {
    // get export entries
    $home_exps=get_exports(1);
    $scratch_exps=get_exports(2);
    $def_array=array("ggroupname"=>"newgroup",
                     "homestart"=>"/home",
                     "scratchstart"=>"/p_scratch",
                     "groupcom"=>"New Group",
                     "respvname"=>"",
                     "respnname"=>"",
                     "resptitan"=>"",
                     "resptel"=>"",
                     "respemail"=>"",
                     "respcom"=>"",
                     "active"=>1);
    // group list
    list($gl,$gln)=getgroups();
    if ($group_act == "ng") {
        // new group
        $group=new StdClass();
        foreach ($def_array as $var_n=>$var_k) {
            $group->$var_n=$var_k;
        }
        $group->gid=0;
    } else if ($group_act == "eg") {
        // alter an existing group ?
        $mres=query("SELECT * FROM ggroup g WHERE g.ggroupname='$gname'");
        $group=mysql_fetch_object($mres);
    } else if ($group_act == "cng") {
        // reedit new group
        $group=new StdClass();
        foreach ($def_array as $var_n=>$var_k) {
            $group->$var_n=$vars[$var_n];
        }
        $group->active=is_set("active",&$vars);
        $group->gid=$vars["gid"];
        if (is_set("ggroup_idx",&$vars)) $group->ggroup_idx=$vars["ggroup_idx"];
    } else {
        // reedit altering an existing group
        $group=new StdClass();
        foreach ($def_array as $var_n=>$var_k) {
            $group->$var_n=$vars[$var_n];
        }
        $group->active=is_set("active",&$vars);
        $group->gid=$vars["gid"];
        if (is_set("ggroup_idx",&$vars)) $group->ggroup_idx=$vars["ggroup_idx"];
    }
    if ($group->gid == "field")  $group->gid=0;
    $gids_used=array();
    $mres=query("SELECT g.gid FROM ggroup g");
    foreach ($gl as $g_idx=>$g_stuff) {
        if ($group_act=="ng" || $g_stuff->gid != $group->gid) $gids_used[]=$g_stuff->gid;
    }
    // general stuff
    echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
    hidden_sid();
    if ($group_act=="eg") {
        message("Modify the general properties of group $gname",$type=2);
    } else if ($group_act=="ng") {
        message("Set the general properties of the new group",$type=2);
    } else if ($group_act=="cng") {
        message("Please check the settings of the new group",$type=2);
    } else {
        message("Please check the settings of the changed group",$type=2);
    }
    echo "<table class=\"user\">\n";
    foreach (array("Groupname"   =>array("ggroupname",16),
                   "Homestart"   =>array("homestart",250),
                   "Scratchstart"=>array("scratchstart",250)) as $lname=>$vstuff) {
        list($vname,$vsize)=$vstuff;
        echo "<tr><td>$lname:</td><td><input name=\"$vname\" value=\"{$group->$vname}\" maxlength=$vsize size=40 /></td></tr>\n";
    }
    echo "<tr><td>Group ID:</td><td>";
    echo "<select name=\"gid\">";
    echo "<option value=\"field\" ";
    if ($group_act=="ng") echo " selected ";
    echo ">enter value:";
    $num_out=0;
    $max_num_out=20;
    $idx=max($min_gid,$group->gid-$max_num_out/2);
    $first_idx=$group->gid;
    while ($num_out < $max_num_out) {
        if (!in_array($idx,$gids_used)) {
            if (!$first_idx) $first_idx=$idx;
            echo "<option value=\"$idx\" ";
            if ($group_act != "ng" && $group->gid == $idx) echo " selected";
            echo ">$idx";
            $num_out++;
        }
        $idx++;
    }
    echo "</select>&nbsp;&nbsp;";
    echo "$min_gid <= <input name=\"gidfield\" value=\"$first_idx\" maxlength=10 size=10 /> <= $max_gid";
    echo "</td></tr>\n";
    echo "<tr><td>Active:</td><td><input type=checkbox name=\"active\" value=\"on\" ";
    if ($group->active) echo " checked  ";
    echo "/></td></tr>\n";
    echo "<tr><td colspan=2 align=\"center\">Comment and responsible Person</td></tr>\n";
    foreach (array("Group comments"=>"groupcom",
                   "First name"    =>"respvname",
                   "Last name"     =>"respnname",
                   "Title"         =>"resptitan",
                   "Tel."          =>"resptel",
                   "e-mail Address"=>"respemail",
                   "Comment"       =>"respcom") as $lname=>$vname) {
        echo "<tr><td>$lname:</td><td><input name=\"$vname\" value=\"{$group->$vname}\" maxlength=40 size=40 /></td></tr>\n";
    }
    echo "</table>\n";
    // capabilities
    $caps=get_group_caps_struct();
    message("Please select the capabilities of this group",$type=2);
    if ($group_act=="ng") {
        printcapabilities($caps,1);
    } else if ($group_act=="ceg" || $group_act=="cng") {
        printcapabilities($caps,1,0,&$vars);
    } else {
        printcapabilities($caps,1,get_group_caps_struct($gname));
    }
    echo "<table class=\"simplesmall\"><tr>";
    echo "<td><input type=reset value=\"Reset\" name=\"rest\" /></td>\n";
    if ($group_act=="ceg") {
        echo "<td><input type=submit value=\"Modify\" ></input></td>\n";
        echo "<input type=hidden name=\"oldidx\" value=\"$group->ggroup_idx\" />";
        echo "<input type=hidden name=\"oldname\" value=\"$gname\"/>";
        echo "<input type=hidden name=\"action\" value=\"modify\" ></input>";
    } else if ($group_act=="eg") {
        if (isset($group->ggroup_idx)) echo "<input type=hidden name=\"oldidx\" value=\"$group->ggroup_idx\" />";
        echo "<input type=hidden name=\"action\" value=\"modify\" />";
        echo "<input type=hidden name=\"oldname\" value=\"$gname\"/>";
        echo "<td><input type=submit value=\"Check and create\" ></input></td>\n";
    } else {
        echo "<input type=hidden name=\"action\" value=\"create\" />";
        echo "<td><input type=submit value=\"Check and Create\" /></td>\n";
    }
    echo "</tr></table>\n";
    echo "</form>";
}
function group_sanity_check($sys_config,$min_gid,$max_gid,$vars,$mstack,$modify=0) {
    if ($modify) {
        $oldidx=$vars["oldidx"];
        $oldname=$vars["oldname"];
    }
    // create / modify group
    $cnew=1;
    // check if group or homestart is already used
    $homestart=$vars["homestart"];
    $scratchstart=$vars["scratchstart"];
    $ggroupname=$vars["ggroupname"];
    $ngid=$vars["gid"];
    if ($ngid == "field") $ngid=$vars["gidfield"];
    if ($modify) {
        $mret=query("SELECT * FROM ggroup g, user u WHERE g.ggroup_idx=u.ggroup AND u.login='{$sys_config['session_user']}' AND g.ggroupname='$oldname'");
        if (mysql_num_rows($mret)) {
            if (!$vars["active"]) {
                $mstack->add_message("You can't set your own group inactive.","error",0);
                $cnew=0;
            }
            if (!$vars["mg"]) {
                $mstack->add_message("You can't remove the modify_group capability from your own group.","error",0);
                $cnew=0;
            }
        }
        $mret=query("SELECT * FROM ggroup g WHERE g.ggroup_idx=$oldidx");
        //         $ogroup=mysql_fetch_object($mret);
        //         if ($ggroupname != $ogroup->ggroupname || $ngid != $ogroup->gid) {
        //             $mret=query("SELECT g.ggroup_idx FROM ggroup g WHERE (g.ggroupname='$ggroupgname' OR g.gid=$ngid) AND g.ggroup_idx!=$oldidx");
        //             if (mysql_num_rows($mret)) {
        //                 $mstack->add_message("The groupname '$ngname' and/or group idx ($gid) is already used for another group","error",0);
        //                 $cnew=0;
        //             }
        //         }
    }
    if (!preg_match("/^\/.*$/",$homestart)) $homestart="/$homestart";
    if (!preg_match("/^.*\/$/",$homestart)) $homestart="$homestart/";
    if (!preg_match("/^\/.*$/",$scratchstart)) $scratchstart="/$scratchstart";
    if (!preg_match("/^.*\/$/",$scratchstart)) $scratchstart="$scratchstart/";
    if (strlen($homestart) < 3) {
        $mstack->add_message("Homestart is to short ($homestart)","warning",2);
    }
    if (strlen($scratchstart) < 3) {
        $mstack->add_message("Scratchstart is to short ($scratchstart)","warning",2);
    }
    if (strlen($ggroupname) < 2) {
        $mstack->add_message("Groupname is to short ($ggroupname)","error",0);
        $cnew=0;
    }
    if (!string_ok($ggroupname)) {
        $mstack->add_message("Some non-allowed characters deteced in groupname $ggroupname","error",0);
        $cnew=0;
    }
    if (!path_ok($homestart)) {
        $mstack->add_message("Some non-allowed characters deteced in homestart $homestart","error",0);
        $cnew=0;
    }
    if (!path_ok($scratchstart)) {
        $mstack->add_message("Some non-allowed characters deteced in scratchstart $scratchstart","error",0);
        $cnew=0;
    }
    if (!preg_match("/^\d+$/",$ngid)) {
        $mstack->add_message("Found garbage '$ngid' for gid","error",0);
        $cnew=0;
    } else {
        if ($ngid >= $min_gid && $ngid <= $max_gid) {
            if ($modify) {
                $mres=query("SELECT g.ggroup_idx,g.ggroupname,g.homestart,g.scratchstart,g.gid FROM ggroup g WHERE (g.ggroupname='$ggroupname' OR g.gid=$ngid) AND g.ggroup_idx!=$oldidx");
            } else {
                $mres=query("SELECT g.ggroup_idx,g.ggroupname,g.homestart,g.scratchstart,g.gid FROM ggroup g WHERE g.ggroupname='$ggroupname' OR g.gid=$ngid");
            }
            if ($mret=mysql_fetch_object($mres)) {
                $mstack->add_message("Groupname ($ggroupname) and/or groupid ($ngid) already used for group ".
                                     $mret->ggroupname." (gid=$mret->gid), homestart = $mret->homestart, scratchstart = $mret->scratchstart","error",0);
                $cnew=0;
            }
        } else {
            $mstack->add_message("Group id $ngid is out of bounds (< $min_gid or > $max_gid)","error",0);
            $cnew=0;
        }
    }
    if ($cnew) {
        if ($modify) {
            $insstr="ggroupname='".
                mysql_escape_string($ggroupname)."', gid=$ngid, homestart='".
                mysql_escape_string($homestart)."',  scratchstart='".
                mysql_escape_string($scratchstart)."', respvname='".
                mysql_escape_string($vars["respvname"])."',respnname='".
                mysql_escape_string($vars["respnname"])."', resptitan='".
                mysql_escape_string($vars["resptitan"])."', respemail='".
                mysql_escape_string($vars["respemail"])."', resptel='".
                mysql_escape_string($vars["resptel"])."', respcom='".
                mysql_escape_string($vars["respcom"])."', groupcom='".
                mysql_escape_string($vars["groupcom"])."' WHERE ggroup_idx=$oldidx";
        } else {
            $active=0;
            if ($vars["active"]) $active=1;
            $insstr="null,$active,'".
                mysql_escape_string($ggroupname)."',$ngid,'".
                mysql_escape_string($homestart)."','".
                mysql_escape_string($scratchstart)."','".
                mysql_escape_string($vars["respvname"])."','".
                mysql_escape_string($vars["respnname"])."','".
                mysql_escape_string($vars["resptitan"])."','".
                mysql_escape_string($vars["respemail"])."','".
                mysql_escape_string($vars["resptel"])."','".
                mysql_escape_string($vars["respcom"])."',0,0,0,0,0,'".
                mysql_escape_string($vars["groupcom"])."',null";
        }
    } else {
        $insstr="";
    }
    return array($ggroupname,$cnew,$insstr);
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "capability.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    $min_gid=100;
    $max_gid=65000;
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    htmlhead();
    $mglist=array("mg"=>array("editgroup"=>"edit existing group",
                              "modify"=>"modify existing group",
                              "inactgroup"=>"set group inactive",
                              "actgroup"=>"set group active",
                              "newgroup"=>"create new group",
                              "delgroup"=>"delete group",
                              "killgroup"=>"delete group",
                              "create"=>"create new group",
                              "browseall"=>"browse all groups"),
                  "bg"=>array("bgroup"=>"browse group")
                  );
    $ucl=usercaps();
    $action="";
    if (is_set("action",&$vars)) {
        foreach ($mglist as $cap=>$cap_stuff) {
            if (in_array($vars["action"],array_keys($cap_stuff))) {
                $action=$vars["action"];
                if ($ucl[$cap]) {
                    $title=$cap_stuff[$action];
                    $mes_str="";
                } else {
                    $title="error";
                    $mes_str="You are not allowed to {$cap_stuff[$action]}";
                }
            }
        }
    } else {
        $title="error";
        $mes_str="No action given";
    }
    clusterhead($sys_config,$title." page","formate.css");
    clusterbody($sys_config,$title);
    if ($mes_str) {
        message($mes_str);
    } else {
        $allcaps=getcapabilities();
        $mstack=new messagelog();
        if ($action == "inactgroup" || $action=="actgroup") {
            $gname=$vars["bgname"];
            // check if the active user is not in this group
            list($gl,$gln)=getgroups();
            $ul=getusers();
            if ($gl[$ul[$sys_config["session_user"]]->ggroup]->ggroupname == $gname) {
                $mstack->add_message("You can't set your own primary group active or inactive","error",0);
            } else {
                if ($action=="inactgroup") {
                    if ($gl[$gln[$gname]]->active) {
                        update_table("ggroup","active=0 WHERE ggroupname='$gname'");
                        list($gl,$gln)=getgroups();
                        message("Set group '$gname' inactive:");
                        printggroup($gl[$gln[$gname]]);
                    } else {
                        $mstack->add_message("Group '$gname' is already set inactive","ok",1);
                    }
                } else {
                    if (!$gl[$gln[$gname]]->active) {
                        update_table("ggroup","active=1 WHERE ggroupname='$gname'");
                        list($gl,$gln)=getgroups();
                        message("Set group '$gname' active:");
                        printggroup($gl[$gln[$gname]]);
                    } else {
                        $mstack->add_message("Group '$gname' is already set active","warning",0);
                    }
                }
            }
            // Create and check newgroup
        } else if ($action=="newgroup") {
            group_mask($sys_config,$min_gid,$max_gid,"ng","");
        } else if ($action =="create") {
            list($ggroupname,$cnew,$insstr)=group_sanity_check(&$sys_config,$min_gid,$max_gid,$vars,&$mstack);
            if ($cnew) {
                $ng_idx=insert_table("ggroup",$insstr);
                $mres=query("SELECT * FROM ggroup g WHERE g.ggroup_idx=$ng_idx");
                $ng=mysql_fetch_object($mres);
                foreach ($allcaps as $cap=>$capstuff) {
                    if (is_set($cap,&$vars)) {
                        $insstr="null,$ng_idx,$capstuff->capability_idx,null";
                        insert_table("ggroupcap",$insstr);
                    }
                }
                message("Created new Group:");
                printggroup($ng);
                $ret_str=update_yp($sys_config);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
            } else {
                // flush messagestack
                $mstack->print_messages();
                $mstack=new messagelog();
                group_mask($sys_config,$min_gid,$max_gid,"cng","",&$vars);
            }
            // Edit and check newgroup
        } else if ($action=="editgroup") {
            group_mask($sys_config,$min_gid,$max_gid,"eg",$vars["bgname"]);
        } else if ($action=="modify") {
            $oldcaps=getgroupcaps($vars["oldname"]);
            list($ggroupname,$cnew,$ustr)=group_sanity_check(&$sys_config,$min_gid,$max_gid,$vars,&$mstack,1);
            if ($cnew) {
                update_table("ggroup",$ustr);
                $mret=query("SELECT * FROM ggroup g WHERE g.ggroupname='$ggroupname'");
                $ng=mysql_fetch_object($mret);
                foreach ($allcaps as $cap=>$capstuff) {
                    if (is_set($cap,&$vars) && ! isset($oldcaps[$cap])) {
                        $insstr="null,$ng->ggroup_idx,$capstuff->capability_idx,null";
                        insert_table("ggroupcap",$insstr);
                    }
                    if (! is_set($cap,&$vars) && isset($oldcaps[$cap])) {
                        $mret=query("DELETE FROM ggroupcap WHERE ggroupcap_idx=$capstuff->capability_idx");
                    }
                }
                message("Modified Group:");
                printggroup($ng);
                $ret_str=update_yp($sys_config);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
            } else {
                // flush messagestack
                $mstack->print_messages();
                $mstack=new messagelog();
                group_mask($sys_config,$min_gid,$max_gid,"ceg","",&$vars);
            }
        } else if ($action=="browseall") {
            $mret=query("SELECT * FROM ggroup g");
            $num_g=mysql_num_rows($mret);
            if ($num_g) {
                message("Found ".get_plural("group",$num_g,1));
                $idx=0;
                while ($bg=mysql_fetch_object($mret)) {
                    printggroup($bg);
                }
            } else {
                message("No groups found (very strange...)");
            }
        } else if ($action=="delgroup") {
            list($gl,$gln)=getgroups();
            $ul=getusers();
            $gname=$vars["bgname"];
            $ggroup_idx=$gl[$gln[$gname]]->ggroup_idx;
            if (($gname == $gl[$ul[$sys_config["session_user"]]->ggroup]->ggroupname) || in_array($gl[$gln[$gname]]->ggroup_idx,$ul[$sys_config["session_user"]]->sgroup_idx)) {
                $mstack->add_message("You can't delete a group you are a member of","error",0);
            } else {
                $p_users=array();
                $s_users=array();
                foreach ($ul as $uname=>$u_stuff) {
                    if ($u_stuff->ggroup == $ggroup_idx) $p_users[]=$uname;
                    if (in_array($ggroup_idx,$u_stuff->sgroup_idx)) $s_users[]=$uname;
                }
                if (count($p_users) || count($s_users)) {
                    if (count($p_users)) {
                        $mstack->add_message("Primary users still defined: ".implode(", ",$p_users),"error",0);
                    }
                    if (count($s_users)) {
                        $mstack->add_message("Secondary users still defined: ".implode(", ",$s_users),"error",0);
                    }
                } else {
                    echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
                    message("Deleting group '$gname'");
                    echo "<center>";
                    echo "<input type=hidden name=\"bgname\" value=\"$gname\"/>\n";
                    echo "<input type=hidden name=\"action\" value=\"killgroup\" />\n";
                    echo "<input type=submit value=\"Delete group\" />\n";
                    echo "</center>";
                    echo "</form>";
                }
            }
            //if 
        } else if ($action=="killgroup") {
            $gname=$vars["bgname"];
            $mret=query("DELETE FROM ggroup WHERE ggroupname='$gname'");
            $mstack->add_message("Deleted group '$gname' from Database.","ok",1);
            $ret_str=update_yp($sys_config);
            if (preg_match("/^error.*$/",$ret_str)) {
                $mstack->add_message($ret_str,"error",0);
            } else {
                $mstack->add_message($ret_str,"ok",1);
            }
        } else if ($action=="bgroup") {
            $mret=query("SELECT * FROM ggroup g WHERE g.ggroupname='{$vars['bgname']}'");
            printggroup(mysql_fetch_object($mret));
        }
        $mstack->print_messages();
    }
    echo "<center><a href=\"logininfo.php?".write_sid()."\">return to LoginInfo</a></center>";
    writefooter($sys_config);
}
?>
