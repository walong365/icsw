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
function user_mask(&$sys_config,$min_uid,$max_uid,$user_act,$uname="",$vars=array()) {
    $mres=query("SELECT u.ggroup,u.export,u.export_scr FROM user u ORDER BY u.user_idx DESC LIMIT 1");
    $old_set=mysql_fetch_object($mres);
    list($gdef,$gndef)=getgroups();
    $udef=getusers();
    $def_array=array("login"          =>"newuser",
                     "uservname"      =>"",
                     "usernname"      =>"",
                     "usertitan"      =>"",
                     "usertel"        =>"",
                     "useremail"      =>"",
                     "userpager"      =>"",
                     "usercom"        =>"",
                     "sgroup_idx"     =>array(),
                     "home"           =>"",
                     "scratch"        =>"",
                     "ggroup"         =>$old_set->ggroup,
                     "active"         =>1,
                     "uid"            =>0,
                     "export"         =>$old_set->export,
                     "export_scr"     =>$old_set->export_scr,
                     "sgeee_user"     =>1,
                     "cluster_contact"=>0,
                     "password"       =>"init4u",
                     "shell"          =>"/bin/bash",
                     "user_idx"       =>0);
    if ($user_act=="nu") {
        $user=new StdClass();
        foreach ($def_array as $var_n=>$var_k) {
            $user->$var_n=$var_k;
        }
	$user->passwd1=$def_array["password"];
	$user->passwd2=$def_array["password"];
    } else if ($user_act=="eu" || $user_act=="ep") {
        $user=$udef[$uname];
	$user->passwd1="";
	$user->passwd2="";
    } else if ($user_act == "ceu" || $user_act=="cep" || $user_act=="cnu") {
        $user=new StdClass();
        foreach ($def_array as $var_n=>$var_k) {
            if (is_set($var_n,&$vars)) {
                $user->$var_n=$vars[$var_n];
            } else {
                $user->$var_n=$var_k;
            }
        }
	
	// handle passwd-field
	if ($vars["passwd1"]) {
	    $user->passwd1=$vars["passwd1"];
	} else {
	    $user->passwd1="";
	}
	if ($vars["passwd2"]) {
	    $user->passwd2=$vars["passwd2"];
	} else {
	    $user->passwd2="";
	}
    }
    if ($user->uid == "field") {
        if (is_set("uidfield",&$vars)) {
            $user->uid=intval($vars["uidfield"]);
        } else {
            $user->uid=0;
        }
    }
    $home_exports=get_exports("home");
    $scratch_exports=get_exports("scratch");
    $u_idx_rf=array();
    $check_idx=0;
    $lastgid=0;
    foreach ($udef as $act_uname=>$ustuff) {
        if ($ustuff->user_idx > $check_idx) {
            $check_idx=$ustuff->user_idx;
            $lastgid=$ustuff->ggroup;
        }
        if (!$user || $act_uname != $uname) $u_idx_rf[$ustuff->uid]=1;
    }
    $shells=readshells();
    // general stuff
    echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
    if ($user_act=="eu") {
        message("Modify the general properties of user $uname",$type=2);
    } else if ($user_act == "ep") {
        message("Modify the personal information of user $uname",$type=2);
    } else if ($user_act == "cep") {
        message("Please check the personal information of user $uname",$type=2);
    } else if ($user_act=="nu") {
        message("Set the general properties of the new user",$type=2);
    } else if ($user_act=="cnu") {
        message("Pease check the settings of the new user",$type=2);
    } else if ($user_act=="ceu") {
        message("Pease check the settings of the existing user",$type=2);
    }
    echo "<table class=\"user\">";
    if ($user_act != "ep" && $user_act != "cep") {
        echo "<tr><td>Login:</td><td><input name=\"login\" value=\"{$user->login}\" maxlength=40 size=40 /></td></tr>\n";
        echo "<tr><td>User ID:</td><td>";
        echo "<select name=\"uid\">";
        echo "<option value=\"field\" ";
        if (!$user->uid) echo "  selected ";
        echo ">enter value:";
        $num_out=0;
        $max_num_out=30;
        if (in_array($user_act,array("cnu","eu","ceu"))) {
            $idx=max($min_uid,$user->uid-$max_num_out/2);
            $first_idx=$user->uid;
        } else {
            $idx=$min_uid;
            $first_idx=0;
        }
        while ($num_out < $max_num_out) {
            if (!isset($u_idx_rf[$idx])) {
                if (!$first_idx) $first_idx=$idx;
                echo "<option value=\"$idx\" ";
                if ($user_act != "nu" && $user->uid == $idx) echo " selected ";
                echo ">$idx";
                $num_out++;
            }
            $idx++;
        }
        echo "</select>&nbsp;&nbsp;";
        echo "<input name=\"uidfield\" value=\"$first_idx\" maxlength=10 size=10 />";
        echo "</td></tr>\n";
        echo "<tr><td>Export entry:</td><td>";
        echo "<select name=\"export\">";
        echo "<option value=\"0\" ";
        if (!count($home_exports)) echo " selected ";
        echo ">none";
        $quota_ok=array();
        $sel=0;
        foreach ($home_exports as $idx=>$he_stuff) {
            echo "<option value=\"$idx\" ";
            if (!$sel) {
                if ($user) {
                    if ($user->export==$idx) $sel=1;
                } else {
                    $sel=1;
                }
                if ($sel) echo " selected ";
            }
            echo ">{$he_stuff->value} on {$he_stuff->name}";
            if ($he_stuff->quota) {
                echo " (*)";
                if (!in_array($he_stuff->name,$quota_ok)) $quota_ok[]=$he_stuff->name;
            }
        }
        echo "</select></td></tr>\n";
        if (count($scratch_exports)) {
            echo "<tr><td>Scratch entry:</td><td>";
            echo "<select name=\"export_scr\">";
            echo "<option value=\"0\">none";
            $sel=0;
            foreach ($scratch_exports as $idx=>$se_stuff) {
                echo "<option value=\"$idx\" ";
                if (!$sel) {
                    if ($user) {
                        if ($user->export_scr==$idx) $sel=1;
                    } else {
                        $sel=1;
                    }
                    if ($sel) echo " selected ";
                }
                echo ">{$se_stuff->value} on {$se_stuff->name}";
                if ($se_stuff->quota) {
                    echo " (*)";
                    if (!in_array($se_stuff->name,$quota_ok)) $quota_ok[]=$se_stuff->name;
                }
            }
            echo "</select></td></tr>\n";
        } else {
            echo "<input type=hidden name=\"export_scr\" value=\"0\" />\n";
        }
        if (!$user->uid && count($quota_ok)) {
            echo "<tr><td>Use quota if possible:</td>";
            echo "<td><input type=checkbox name=\"usequota\" checked /> (possible on ".implode(", ",$quota_ok).")</td>";
            echo "</tr>\n";
        }
        echo "<tr><td>Primary Group:</td><td>";
        echo "<select name=\"ggroup\">";
        foreach ($gdef as $gd=>$gstuff) {
            echo "<option value=\"$gd\"" ;
            if ($user->ggroup==$gstuff->ggroup_idx) echo " selected ";
            echo ">$gstuff->ggroupname [ gid=$gstuff->gid ] ($gstuff->homestart - $gstuff->scratchstart)";
        }
        echo "</select>";
        echo "</td></tr>\n";
        echo "<tr><td>Secondary Groups:</td><td>";
        echo "<select name=\"sgroup_idx[]\" multiple>";
        foreach ($gdef as $gd=>$gstuff) {
            echo "<option value=\"$gd\" ";
            if (in_array($gstuff->ggroup_idx,$user->sgroup_idx)) echo " selected ";
            echo ">$gstuff->ggroupname [ gid=$gstuff->gid ]";
        }
        echo "</select>";
        echo "</td></tr>\n";
        if ($user_act=="nu" || $user_act=="cnu") {
            echo "<tr><td>Home (is appended to {HOMESTART from primary group}, leave empty for login-name):</td>\n";
        } else {
            echo "<tr><td>Home:</td>\n";
        }
        echo "<td><input name=\"home\" maxlength=255 size=40 value=\"$user->home\" /></td></tr>\n";
        $sgeee_server=get_sgeee_server();
        if ($sgeee_server) {
            echo "<tr><td>Create SGEEE-user:</td><td><input type=checkbox name=\"sgeee_user\" value=\"1\" ";
            if ($user->sgeee_user) echo " checked ";
            echo "/> (on server $sgeee_server)</td></tr>\n";
        }
        echo "<tr><td>Cluster Contact:</td><td><input type=checkbox name=\"cluster_contact\" value=\"1\" ";
        if ($user->cluster_contact) echo " checked ";
        echo "/></td></tr>\n";
    }
    echo "<tr><td>Shell:</td><td>";
    echo "<select name=\"shell\">";
    foreach (array_keys($shells) as $gd) {
        echo "<option value=\"$gd\"";
        if ($gd==$user->shell) echo " selected";
        echo ">$gd\n";
    }
    echo "</select>";
    echo "</td></tr>\n";
    echo "<tr><td>Password:</td><td><input type=password name=\"passwd1\" maxlength=24 size=24 value=\"$user->passwd1\" /></td></tr>\n";
    echo "<tr><td>Check:</td><td><input type=password name=\"passwd2\" maxlength=24 size=24 value=\"$user->passwd2\" /></td></tr>\n";
    echo "<tr><td>Active:</td><td><input type=checkbox name=\"active\" value=\"on\" ";
    if ($user->active) echo " checked ";
    echo "/></td></tr>\n";
    echo "<tr><td colspan=2 align=\"center\">Personal information</td></tr>\n";
    foreach (array(array("First name","uservname","","uservname"),
                   array("Last name","usernname","","usernname"),
                   array("Title","usertitan","","usertitan"),
                   array("Tel.","usertel","","usertel"),
                   array("e-mail Address","useremail","","useremail"),
                   array("Pager Address","userpager","","userpager"),
                   array("User comments","usercom","","usercom")) as $d_array) {
        list($lname,$vname,$ngdef,$gdef)=$d_array;
        if ($user) {
            $def_value=$user->$gdef;
        } else {
            $def_value=$ngdef;
        }
        echo "<tr><td>$lname:</td><td><input name=\"$vname\" value=\"$def_value\" maxlength=40 size=40 /></td></tr>\n";
    }
    echo "</table>\n";
    echo "<center><table><tr>";
    echo "<td align=left><input type=reset value=\"Reset\" name=\"rest\"/></td>\n";
    echo "<td align=right>";
    // we send the old login for eu and ceu
    if (in_array($user_act,array("eu","ceu"))) echo "<input type=hidden name=\"oldlogin\" value=\"$user->login\"/>\n";
    // we send the old idx for eu, ceu, ep and cep
    if (in_array($user_act,array("eu","ceu","ep","cep"))) {
	echo "<input type=hidden name=\"oldidx\" value=\"$user->user_idx\"/>\n";
	echo "<input type=hidden name=\"oldpasswd\" value=\"$user->password\"/>\n";
    }
    $act_array=array("nu" =>"create",
                     "cnu"=>"create",
                     "eu" =>"modify",
                     "ceu"=>"modify",
                     "ep" =>"modpers",
                     "cep"=>"modpers");
    echo "<input type=hidden name=\"action\" value=\"{$act_array[$user_act]}\" />\n";
    if ($user_act=="cnu" || $user_act=="ceu") {
        echo "<input type=submit value=\"Check and modify\" />\n";
    } else if ($user_act=="ep" || $user_act=="cep") {
        echo "<input type=hidden name=\"login\" value=\"$user->login\"/>\n";
        echo "<input type=submit value=\"Check personal\" />\n";
    } else {
        echo "<input type=submit value=\"Check and Create\" />\n";
    }
    echo "</td>\n";
    echo "</tr></table></center>\n";
    echo "</form>\n";
}
function user_sanity_check($sys_config,$ct,$min_uid,$max_uid,$vars,$mstack) {
    $udef=getusers();
    if ($ct=="eu") {
        $oldlogin=$vars["oldlogin"];
    }
    if ($ct == "eu" || $ct=="ep") {
        $oldidx=$vars["oldidx"];
        $user=$udef[$vars["login"]];
        //print_r($user);
    }
    $login=$vars["login"];
    $cnew=1;
    // group/user definitions
    list($gdef,$gndef)=getgroups();
    // new secondary groups
    $nsec_gids=array();
    $udef=getusers();
    $add_flags=array();
    if ($ct == "nu" || $ct == "eu") {
        // export entries
        $home_exports=get_exports("home");
        $scratch_exports=get_exports("scratch");
        // check if group or homestart is already used
        $home=$vars["home"];
        if (!strlen($home)) $home=$login;
        if (is_set("scratch",&$vars)) {
            $scratch=$vars["scratch"];
        } else {
            $scratch="";
        }
        if (!strlen($scratch)) $scratch=$login;
        $ngid=$vars["ggroup"];
        if (is_set("sgroup_idx",&$vars)) {
            $nsec_gids=$vars["sgroup_idx"];
        }
        $uid=$vars["uid"];
        if ($uid == "field") $uid=$vars["uidfield"];
        $export=$vars["export"];
        $export_scr=$vars["export_scr"];
        //echo "EX:$export<br>";
        $group=$gdef[$ngid];
        $homestart=$group->homestart;
        if ($ct == "eu") {
            $login=$oldlogin;
        }
    }
    $password=$vars["passwd1"];
    $password2=$vars["passwd2"];
    $passwd_crypted=0;
    if ((!$password || !$password2) && is_set("oldpasswd",&$vars)) {
	$password=$vars["oldpasswd"];
	$password2=$vars["oldpasswd"];
	$passwd_crypted=1;
    }
    //echo "*$password*$password2$passwd_crypted<br>";
    if ($ct != "ep") {
        if ($ct=="eu") {
            if ($oldlogin == $sys_config["session_user"]) {
                // check for changes of yourself
                if ($login != $user->login) {
                    $mstack->add_message("You can't modify the loginname of yourself!","error",0);
                    $cnew=0;
                }
                if ($uid != $user->uid) {
                    $mstack->add_message("You can't modify the user-ID of yourself!","error",0);
                    $cnew=0;
                }
                if ($home != $user->home) {
                    $mstack->add_message("You can't modify the homedirectory of yourself!","error",0);
                    $cnew=0;
                }
                if ($ngid != $user->ggroup) {
                    $mstack->add_message("You can't modify the Primary group-ID of yourself!","error",0);
                    $cnew=0;
                }
                if (!$vars["active"]) {
                    $mstack->add_message("You can't deactivate yourself!","error",0);
                    $cnew=0;
                }
            }
        }
        if (!preg_match("/^\d+$/",$uid)) {
            $mstack->add_message("Found garbage '$uid' for uid","error",0);
            $cnew=0;
        } else {
            if ($uid >= $min_uid && $uid <= $max_uid) {
                if ($ct=="eu") {
                    $mres=query("SELECT u.user_idx,u.login,u.uid FROM user u WHERE (u.login='$login' AND u.login != '$oldlogin') OR (u.uid=$uid AND u.user_idx != $oldidx)");
                } else {
                    $mres=query("SELECT u.user_idx,u.login,u.uid FROM user u WHERE u.login='$login' OR u.uid=$uid");
                }
                if ($mret=mysql_fetch_object($mres)) {
                    if ($login==$mret->login && $uid==$mret->uid) {
                        $mstack->add_message("Loginname $login and userid ($uid) already used for user $mret->login (uid=$mret->uid)","error",0);
                    } else if ($login==$mret->login) {
                        $mstack->add_message("Loginname ($login) already used for user $mret->login","error",0);
                    } else {
                        $mstack->add_message("Userid ($uid) already used for $mret->login","error",0);
                    }
                    $cnew=0;
                }
            } else {
                $mstack->add_message("Userid $uid is out of bounds (< $min_uid or > $max_uid)","error",0);
                $cnew=0;
            }
        }
    }
    if ($password != $password2) {
        $mstack->add_message("You entered two different passwords","error",0);
        $cnew=0;
    }
    if (strlen($password) < 5) {// && ($ct=="nu" || ($ct=="eu" && strlen($password)))) {
        $mstack->add_message("Your password is too short","error",0);
        $cnew=0;
    }
    if ($ct != "ep") {
        if (strlen($home) < 1) {
            $mstack->add_message("Home is too short ($home)","error",0);
            $cnew=0;
        }
        if (strlen($scratch) < 1) {
            $mstack->add_message("Scratch is too short ($scratch)","error",0);
            $cnew=0;
        }
        if (strlen($login) < 2) {
            $mstack->add_message("Login is too short ($login)","error",0);
            $cnew=0;
        }
        if (!string_ok($login)) {
            $mstack->add_message("Some non-allowed characters deteced in login-string","error",0);
            $cnew=0;
        }
        if (!string_ok($home) && (!$user || ($user && strlen($home)))) {
            $mstack->add_message("Some non-allowed characters deteced in home string","error",0);
            $cnew=0;
        }
        if (!string_ok($scratch)) {
            $mstack->add_message("Some non-allowed characters deteced in scratch string","error",0);
            $cnew=0;
        }
        $active=is_set("active",&$vars);
    }
    if ($cnew) {
	if (!$passwd_crypted) $password=crypt($password,get_rand_str());
        if ($ct == "eu" || $ct=="ep") {
            $ins_array=array();
            if ($ct != "ep") {
                $sgeee_user=is_set("sgeee_user",&$vars);
                $cluster_contact=is_set("cluster_contact",&$vars);
                if ($active != $user->active) $ins_array[]="active=$active";
                if ($login != $oldlogin) $ins_array[]="login='$login'";
                if ($uid != $user->uid) $ins_array[]="uid=$uid";
                if ($ngid != $user->ggroup) $ins_array[]="ggroup=$ngid";
                if ($export != $user->export) $ins_array[]="export=$export";
                if ($export_scr != $user->export_scr) $ins_array[]="export_scr=$export_scr";
                if ($home != $user->home) $ins_array[]="home='".mysql_escape_string($home)."'";
                if ($scratch != $user->scratch) $ins_array[]="scratch='".mysql_escape_string($scratch)."'";
                if ($sgeee_user != $user->sgeee_user) {
                    $ins_array[]="sgeee_user=$sgeee_user";
                    if ($sgeee_user) {
                        $add_flags[]="csu";
                    } else {
                        $add_flags[]="dsu";
                    }
                }
                if ($cluster_contact != $user->cluster_contact) $ins_array[]="cluster_contact=$cluster_contact";
            }
            if ($vars["shell"] != $user->shell) $ins_array[]="shell='".mysql_escape_string($vars["shell"])."'";
            if (strlen($password)) $ins_array[]="password='".mysql_escape_string($password)."'";
            foreach (array("uservname","usernname","usertitan","useremail","userpager","usertel","usercom") as $u_s) {
                if ($vars[$u_s] != $user->$u_s) $ins_array[]="$u_s='".mysql_escape_string($vars[$u_s])."'";
            }
            if (!count($ins_array)) $ins_array[]="login='$login'";
            $insstr=implode(",",$ins_array)." WHERE user_idx=$oldidx";
        } else {
            $sgeee_user=is_set("sgeee_user",&$vars);
	    if ($sgeee_user) $add_flags[]="csu";
            $cluster_contact=is_set("cluster_contact",&$vars);
            $insstr="0,$active,'$login',$uid,$ngid,$export,$export_scr,'".
                mysql_escape_string($home)."','".
                mysql_escape_string($scratch)."','".
                mysql_escape_string($vars["shell"])."','".
                mysql_escape_string($password)."',$sgeee_user,$cluster_contact,'".
                mysql_escape_string($vars["uservname"])."','".
                mysql_escape_string($vars["usernname"])."','".
                mysql_escape_string($vars["usertitan"])."','".
                mysql_escape_string($vars["useremail"])."','".
                mysql_escape_string($vars["userpager"])."','".
                mysql_escape_string($vars["usertel"])."',0,0,0,0,0,'','".
                mysql_escape_string($vars["usercom"])."',null";
        }
    } else {
        $cnew=0;
        $insstr="";
    }
    return array($login,$cnew,$insstr,$nsec_gids,$add_flags);
}
require_once "config.php";
require_once "mysql.php";
require_once "capability.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    $min_uid=500;
    $max_uid=65000;
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    htmlhead();
    $clustername=$sys_config["CLUSTERNAME"];
    $mulist=array("mu"=>array("create"   =>"create new user",
                              "actuser"  =>"edit existing user",
                              "inactuser"=>"set user inactive",
                              "edituser" =>"edit existing user",
                              "modify"   =>"modify existing user",
                              "newuser"  =>"create new user",
                              "deluser"  =>"delete user",
                              "killuser" =>"delete user",
                              "browseall"=>"browse all users"),
                  "mp"=>array("editpers" =>"edit personal information",
                              "modpers"  =>"modify personal information"),
                  "bu"=>array("buser"    =>"browse users")
                  );
    $ucl=usercaps($sys_db_con);
    $action="";
    if (is_set("action",&$vars)) {
        foreach ($mulist as $cap=>$cap_stuff) {
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
    clusterhead($sys_config,$title,"formate.css");
    clusterbody($sys_config,$title);
    if ($mes_str) {
        message($mes_str);
    } else {
        $allcaps=getcapabilities($sys_db_con);
        $mstack=new messagelog();
        if ($action=="inactuser" || $action=="actuser") {
            $uname=$vars["buname"];
            if ($uname==$sys_config["session_user"]) {
                $mstack->add_message("You can't set your own user active/inactive","error",0);
            } else {
                if ($action=="inactuser") {
                    $mret=query("SELECT u.user_idx FROM user u WHERE u.active AND u.login='$uname'");
                    if (mysql_num_rows($mret)) {
                        update_table("user","active=0 WHERE login='$uname'");
                        $mstack->add_message("Set user '$uname' inactive:","ok",1);
                        $u_list=getusers();
                        list($g_list,$gn_list)=getgroups();
                        printuser($u_list[$uname],$g_list);
                        $ret_str=update_yp($sys_config);
                        if (preg_match("/^error.*$/",$ret_str)) {
                            $mstack->add_message($ret_str,"error",0);
                        } else {
                            $mstack->add_message($ret_str,"ok",1);
                        }
                    } else {
                        $mstack->add_message ("User '$uname' is already set inactive","error",0);
                    }
                } else {
                    $mret=query("SELECT u.user_idx FROM user u WHERE NOT u.active AND u.login='$uname'");
                    if (mysql_num_rows($mret)) {
                        update_table("user","active=1 WHERE login='$uname'");
                        $mstack->add_message("Set user '$uname' active:","ok",1);
                        $u_list=getusers();
                        list($g_list,$gn_list)=getgroups();
                        printuser($u_list[$uname],$g_list);
                        $ret_str=update_yp($sys_config);
                        if (preg_match("/^error.*$/",$ret_str)) {
                            $mstack->add_message($ret_str,"error",0);
                        } else {
                            $mstack->add_message($ret_str,"ok",1);
                        }
                    } else {
                        $mstack->add_message ("User '$uname' is already set active","error",0);
                    }
                }
            }
        } else if ($action=="killuser") {
            $uname=$vars["buname"];
            list($gl,$gln)=getgroups();
            $ul=getusers();
            $ku=$ul[$uname];
            $kg=$gl[$ku->ggroup];
            $home=$kg["homestart"].$ku["home"];
            $scratch=$kg["scratchstart"].$ku["scratch"];
            // get export-entry for fileserver 
            $fse=find_user_export($uname,"home");
            if (is_set("delhome",$vars["delhome"]) && $fse) {
                $ret_str=delete_user_home($sys_config,$fse->name,$uname);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
            }
            $fss=find_user_export($uname,"scratch");
            if (is_set("delscratch",&$vars) && $fss) {
                $ret_str=delete_user_scratch($sys_config,$fss->name,$uname);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
            }
            // remove sgeee-user
            if ($ku->sgeee_user) {
                $ret_str=delete_sgeee_user($sys_config,get_sgeee_server(),$uname);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
            }
            // delete secondary groups
            $mret=query("DELETE FROM user_ggroup WHERE user=$ku->user_idx");
            // delete primary group
            $mret=query("DELETE FROM user WHERE login='$uname'");
            $mstack->add_message("Deleted user '$uname' from Database.","ok",1);
            $ret_str=update_yp($sys_config);
            if (preg_match("/^error.*$/",$ret_str)) {
                $mstack->add_message($ret_str,"error",0);
            } else {
                $mstack->add_message($ret_str,"ok",1);
            }
            // new user stuff
        } else if ($action=="newuser") {
            user_mask($sys_config,$min_uid,$max_uid,"nu");
        } else if ($action=="create") {
            list($login,$cnew,$insstr,$sec_gids,$add_flags)=user_sanity_check(&$sys_config,"nu",$min_uid,$max_uid,$vars,&$mstack);
            if ($cnew) {
                $new_uidx=insert_table("user",$insstr);
                $mres=query("SELECT * FROM user u WHERE u.login='$login'");
                $new_user=mysql_fetch_object($mres);
                $quota_machines=array();
                if ($new_user->export) {
                    $exps=get_exports("home");
                    $ret_str=create_user_home($sys_config,$exps[$new_user->export]->name,$login);
                    if (preg_match("/^error.*$/",$ret_str)) {
                        $mstack->add_message("Create_user_home: $ret_str","error",0);
                    } else {
                        $mstack->add_message("Create_user_home: $ret_str","ok",1);
                    }
                    if (is_set("usequota",&$vars) && $exps[$new_user->export]->quota) {
                        if (!in_array($exps[$new_user->export]->name,$quota_machines)) $quota_machines[]=$exps[$new_user->export]->name;
                    }
                } else {
                    $mstack->add_message("No export entry found, hence no homedirectory is created.","warning",0);
                }
                if ($new_user->export_scr) {
                    $exps=get_exports("scratch");
                    $ret_str=create_user_scratch($sys_config,$exps[$new_user->export_scr]->name,$login);
                    if (preg_match("/^error.*$/",$ret_str)) {
                        $mstack->add_message("Create_user_scratch: $ret_str","error",0);
                    } else {
                        $mstack->add_message("Create_user_scratch: $ret_str","ok",1);
                    }
                    if (is_set("usequota",&$vars) && $exps[$new_user->export_scr]->quota) {
                        if (!in_array($exps[$new_user->export_scr]->name,$quota_machines)) $quota_machines[]=$exps[$new_user->export_scr]->name; 
                    }
                } else {
                    $num_scratch=count(get_exports("scratch"));
                    // only print a warning if there are valid scratchexport machines
                    if ($num_scratch) $mstack->add_message("No scratchexport entry found, hence no scratchdirectory is created.","warning",0);
                }
                foreach ($sec_gids as $sec_gid) {
                    if ($sec_gid != $new_user->ggroup) insert_table("user_ggroup","0,$sec_gid,$new_uidx,null");
                }
                $new_users=getusers();
                list($g_list,$gn_list)=getgroups();
                message("Created new User:");
                printuser($new_users[$login],$g_list);
                $ret_str=update_yp($sys_config);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message("Update YP-Maps: $ret_str","error",0);
                } else {
                    $mstack->add_message("Update YP-Maps: $ret_str","ok",1);
                }
                if (in_array("csu",$add_flags)) {
                    $ret_str=create_sgeee_user($sys_config,get_sgeee_server(),$login);
                    if (preg_match("/^error.*$/",$ret_str)) {
                        $mstack->add_message("Create SGEEE-user: $ret_str","error",0);
                    } else {
                        $mstack->add_message("Create SGEEE-user: $ret_str","ok",1);
                    }
                }
                if (count($quota_machines)) {
                    foreach ($quota_machines as $quota_machine) {
                        $ret_str=create_user_quota($sys_config,$quota_machine,$login);
                        if (preg_match("/^error.*$/",$ret_str)) {
                            $mstack->add_message("Set Quota: $ret_str","error",0);
                        } else {
                            $mstack->add_message("Set Quota: $ret_str","ok",1);
                        }
                    }
                }
            } else {
                user_mask($sys_config,$min_uid,$max_uid,"cnu","",&$vars);
            }
            // edit existing user
        } else if ($action=="edituser") {
            user_mask($sys_config,$min_uid,$max_uid,"eu",$vars["buname"]);
        } else if ($action=="modify") {
            list($login,$cnew,$insstr,$sec_gids,$add_flags)=user_sanity_check(&$sys_config,"eu",$min_uid,$max_uid,$vars,&$mstack);
            if ($cnew) {
                //echo "*** $insstr ***<br>";
                update_table("user",$insstr);
                $u_list=getusers();
                list($g_list,$gn_list)=getgroups();
                foreach ($sec_gids as $sec_gid) {
                    if (!in_array($sec_gid,$u_list[$login]->sgroup_idx)) {
                        insert_table("user_ggroup","0,$sec_gid,{$u_list[$login]->user_idx},null");
                        $u_list[$login]->sgroup_idx[]=$sec_gid;
                    }
                }
                foreach ($u_list[$login]->sgroup_idx as $sec_gid) {
                    if (!in_array($sec_gid,$sec_gids)) query("DELETE FROM user_ggroup WHERE user={$u_list[$login]->user_idx} AND ggroup=$sec_gid");
                    unset($u_list[$login]->sgroup_idx[array_search($sec_gid,$u_list[$login]->sgroup_idx)]);
                }
                message("Modified User:");
                printuser($u_list[$login],$g_list);
                $ret_str=update_yp($sys_config);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
                if (in_array("csu",$add_flags)) {
                    $ret_str=create_sgeee_user($sys_config,get_sgeee_server(),$login);
                    if (preg_match("/^error.*$/",$ret_str)) {
                        $mstack->add_message("Create SGEEE-user: $ret_str","error",0);
                    } else {
                        $mstack->add_message("Create SGEEE-user: $ret_str","ok",1);
                    }
                }
                if (in_array("dsu",$add_flags)) {
                    $ret_str=delete_sgeee_user($sys_config,get_sgeee_server(),$login);
                    if (preg_match("/^error.*$/",$ret_str)) {
                        $mstack->add_message("Deleted SGEEE-user: $ret_str","error",0);
                    } else {
                        $mstack->add_message("Deleted SGEEE-user: $ret_str","ok",1);
                    }
                }
            } else {
                user_mask($sys_config,$min_uid,$max_uid,"ceu","",&$vars);
            }
        } else if ($action=="deluser") {
            $uname=$vars["buname"];
            if ($uname == $sys_config["session_user"]) {
                $mstack->add_message("You can't delete yourself","error",0);
            } else {
                $mret=query("SELECT u.home,u.scratch, g.homestart,g.scratchstart FROM user u, ggroup g WHERE u.login='$uname' AND u.ggroup=g.ggroup_idx");
                $ku=mysql_fetch_object($mret);
                $fse=find_user_export($uname,"home");
                $fss=find_user_export($uname,"scratch");
                echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
                message("Deleting user '$uname'");
                if ($fse || $fss) {
                    message("Please select:");
                    echo "<table class=\"user\">";
                    if ($fse) {
                        echo "<tr><td>Delete Home-directory (".$ku->homestart.$ku->home." [".$fse->value."/".$ku->home."] on $fse->name".
                            "):</td><td><input type=checkbox name=\"delhome\" value=\"on\"></td></tr>\n";
                    }
                    if ($fss) {
                        echo "<tr><td>Delete Scratch-directory (".$ku->scratchstart.$ku->scratch." [".$fss->value."/".$ku->scratch."] on $fss->name".
                            "):</td><td><input type=checkbox name=\"delscratch\" value=\"on\"></td></tr>\n";
                    }
                    echo "</table>\n";
                }
                echo "<center>";
                echo "<input type=hidden name=\"buname\" value=\"$uname\"/>\n";
                echo "<input type=hidden name=\"action\" value=\"killuser\"/>";
                echo "<input type=submit value=\"Delete user\" />\n";
                echo "</center>";
                echo "</form>";
            }
        } else if ($action=="browseall") {
	    $all_users=getusers();
            $num_u=count($all_users);
            if ($num_u) {
                message("Found ".get_plural("user",$num_u,1));
                $lastgid=-1;
                list($g_list,$gn_list)=getgroups();
		foreach ($all_users as $login=>$bu) {
                    if ($bu->ggroup == $lastgid) {
                        printuser($bu,$g_list,$capabilities=0);
                    } else {
                        //if ($lastgid > 0) echo "<hr noshade>";
                        $lastgid=$bu->ggroup;
                        printuser($bu,$g_list,$capabilities=1);
                    }
                }
            } else {
                message("No users found (?)");
            }
        } else if ($action=="modpers") {
            list($login,$cnew,$insstr,$sec_gids,$add_flags)=user_sanity_check(&$sys_config,"ep",$min_uid,$max_uid,$vars,&$mstack);
            if ($cnew) {
                update_table("user",$insstr);
		$all_users=getusers();
		$nu=$all_users[$login];
                message("Modified User:");
                list($g_list,$gn_list)=getgroups();
                printuser($nu,$g_list);
                $ret_str=update_yp($sys_config);
                if (preg_match("/^error.*$/",$ret_str)) {
                    $mstack->add_message($ret_str,"error",0);
                } else {
                    $mstack->add_message($ret_str,"ok",1);
                }
            } else {
                user_mask($sys_config,$min_uid,$max_uid,"cep",$login,&$vars);
            }
        } else if ($action=="editpers") {
            user_mask($sys_config,$min_uid,$max_uid,"ep",$sys_config["session_user"]);
        } else if ($action=="buser") {
            $u_list=getusers();
            list($g_list,$gn_list)=getgroups();
            printuser($u_list[$vars["buname"]],$g_list);
        }
        $mstack->print_messages();
    }
    echo "<center><a href=\"logininfo.php?".write_sid()."\">return to LoginInfo</a></center>";
    writefooter($sys_config);
}
?>
