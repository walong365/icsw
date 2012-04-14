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
function init_session() {
    session_register("session_user");
    session_register("user_idx");
    session_register("ggroup_idx");
    session_register("page_views");
    return;
}
function write_sid() {
    return "ICSID=".session_id();
}
function hidden_sid() {
    echo "<input type=\"hidden\" name=\"ICSID\" value=\"".session_id()."\" />";
}
function get_php_version() {
    $phpvers=phpversion();
    if (preg_match("/^(\d+)\.(\d+)\.(\d+)$/",$phpvers,$phpvrs)) {
        $php_vers=array((int)$phpvrs[1],(int)$phpvrs[2],(int)$phpvrs[3]);
    } else {
        $php_vers=array(0,0,0);
    }
    //echo "$phpvers - $us_vars $phpvrs[1] $phpvrs[2] <br>";
    return $php_vers;
}
function get_relative_dir($sys_config) {
    // returns pathname above /php
    preg_match("/^(.*)\/php\/.*$/",$sys_config['script_name'],$grdm);
    return $grdm[1];
}
function get_root_dir() {
    if (isset($GLOBALS["HTTP_SERVER_VARS"]["PATH_TRANSLATED"])) {
        $src_dir=dirname($GLOBALS["HTTP_SERVER_VARS"]["PATH_TRANSLATED"]);
    } else {
        $src_dir=dirname($GLOBALS["HTTP_SERVER_VARS"]["SCRIPT_FILENAME"]);
    }
    // strip trailing /php
    if (preg_match("/^(.*)\/php$/",$src_dir,$src_parts)) $src_dir=$src_parts[1];
    return $src_dir;
}
function us_vars_defined() {
    return ((version_compare(phpversion(),"4.2.0") == -1) ? 0 : 1);
}

function open_icss($save_path,$session_name) {
    return true;
}
function close_icss() {
    global $sys_db_con;
#mysql_close($sys_db_con);
    return true;
}
function read_icss($session_id) {
    global $sys_db_con;
    $result=mysql_query("SELECT s.value,DATE_FORMAT(s.logout_time,'%Y') AS logout_time FROM session_data s WHERE s.session_id='$session_id'",$sys_db_con);
    if ($result && mysql_num_rows($result)) {
        $mfr=mysql_fetch_object($result);
        //echo "+",$mfr->value,preg_match("/^\\(.*$/",$mfr->value),"+<br>";
        //if (preg_match("/^\(.*$/",$mfr->value)) {
        //    echo "***",$mfr->value,"<br>";
        //}
        if ((int)$mfr->logout_time) {
            return "";
        } else {
            return $mfr->value;
        }
    } else {
        return "";
    }
}
function parse_session_data($data) {
    $ret_field=array();
    foreach (preg_split("/;/",$data) as $act_dat) {
        if (preg_match("/^(.*)\|(.*)$/",$act_dat,$act_dp)) {
            $ret_field[$act_dp[1]]=unserialize($act_dp[2]);
        }
    }
    return $ret_field;
}
function write_icss($session_id,$data) {
    global $sys_db_con;
    $as_data=addslashes($data);
    $msq=mysql_query("SELECT * FROM session_data s WHERE s.session_id='$session_id'",$sys_db_con);
    $refresh=1;
    $add_new=1;
    if (mysql_num_rows($msq)) {
        $add_new=0;
        $mfr=mysql_fetch_object($msq);
        if ($mfr->value == $data) $refresh=0;
    }
    if ($refresh) {
        if ($add_new) {
            $new_u_idx=0;
            $f_data=parse_session_data($data);
            if (in_array("user_idx",array_keys($f_data))) $new_u_idx=(int)$f_data["user_idx"];
            $rip=$GLOBALS["HTTP_SERVER_VARS"]["REMOTE_ADDR"];
            $sql_str="INSERT INTO session_data SET session_id='$session_id',value='$as_data',user_idx=$new_u_idx,remote_addr='$rip',login_time=NOW() ";
        } else {
            $sql_str="UPDATE session_data SET value='$as_data' WHERE session_id='$session_id'";
        }
        $msq=mysql_query($sql_str,$sys_db_con) or
            error_log("write: ".mysql_error()."\n",3,"/tmp/errors.log");
    }
    return true;
}
function destroy_icss($session_id) {
    global $sys_db_con;
    $sql_str="UPDATE session_data SET logout_time=NOW() WHERE session_id='$session_id'";
    mysql_query($sql_str,$sys_db_con);
    return true;
}
function gc_icss($max_time) {
    global $sys_db_con;
    mysql_query("UPDATE session_data SET forced_logout=1,logout_time=NOW() WHERE UNIX_TIMESTAMP(date) < UNIX_TIMESTAMP()-$max_time",$sys_db_con);
    return true;
}
$cfname="/etc/sysconfig/cluster/mysql.cf";
if (is_readable($cfname)) {
    $sys_config=readconfig($cfname);
} else {
    die("Problem accesing $cfname <br>");
}
require_once "htmltools.php";
// uncomment the following line if you don´t want to use database-based sessionhandling
session_set_save_handler("open_icss","close_icss","read_icss","write_icss","destroy_icss","gc_icss");
function readgets() {
    global $sys_config;
    $gets=array();
    $us_vars=us_vars_defined();
    $mygets=array();
    if ($us_vars) {
        if (count($_SERVER["argv"]))$mygets=preg_split("/&|;/",$_SERVER["argv"][0]);
    } else {
        $mygets=preg_split("/&|;/",$GLOBALS["HTTP_SERVER_VARS"]["argv"][0]);
    }
    //echo $GLOBALS["HTTP_SERVER_VARS"]["HTTP_REFERER"];
    // parse get variables
    foreach ($mygets as $get_line) {
	if (preg_match("/^.*=.*$/",$get_line)) {
	    list($get_k,$get_v)=explode("=",$get_line,2);
	    $gets[$get_k]=$get_v;
	} else {
	    $gets[$get_line]=1;
	}
    }
    if ($us_vars) {
        // parse post-variables
        foreach($_POST as $avn => $avv) {
            //echo "$avn = ".print_r($avv)."<br>";
            $gets[$avn]=$avv;
        }
        foreach($_GET as $avn => $avv) {
            //echo "$avn = ".print_r($avv)."<br>";
            $gets[$avn]=$avv;
        }
    } else {
        // parse post-variables
        foreach($GLOBALS["HTTP_POST_VARS"] as $avn => $avv) {
            //echo "$avn = ".print_r($avv)."<br>";
            $gets[$avn]=$avv;
        }
        foreach($GLOBALS["HTTP_GET_VARS"] as $avn => $avv) {
            //echo "$avn = ".print_r($avv)."<br>";
            $gets[$avn]=$avv;
        }
    }
#foreach (array_keys($gets) as $avn) {
#  echo $avn." - ".$gets[$avn]."<br>";
#}
    if (isset($gets["ICSID"])) {
        session_name("ICSID");
        session_id($gets["ICSID"]);
        session_start();
        init_session();
        init_mysql_stats();
        if (strlen($GLOBALS["HTTP_SESSION_VARS"]["session_user"]) == 0) {
            session_destroy();
        } else {
            $sys_config["SESSION"]=1;
            $sys_config["session_user"]=$GLOBALS["HTTP_SESSION_VARS"]["session_user"];
            $sys_config["user_idx"]=$GLOBALS["HTTP_SESSION_VARS"]["user_idx"];
            $sys_config["ggroup_idx"]=$GLOBALS["HTTP_SESSION_VARS"]["ggroup_idx"];
            $sys_config["python_session_id"]=$GLOBALS["HTTP_SESSION_VARS"]["session_id"];
            $GLOBALS["HTTP_SESSION_VARS"]["page_views"]=strval(intval($GLOBALS["HTTP_SESSION_VARS"]["page_views"]) + 1);
            $sys_config["page_views"]=$GLOBALS["HTTP_SESSION_VARS"]["page_views"];
            // read user caps
            $sys_config["ucl"]=usercaps();
        }
    }
    return $gets;
}

function readshells() {
    $slist=array();
    $sfile=file("/etc/shells");
    for ($i=0;$i < sizeof($sfile);$i++) {
        $shell=trim($sfile[$i]);
        if (strlen($shell)) $slist[$shell]=1;
    }
    return $slist;
}

function readconfig($cfname) {
    require_once "htmltools.php";
    global $sys_db_con;
    $config=array("ERROR"        =>0,
                  "global_errors"=>new messagestack(),
                  "script_name"  =>$GLOBALS["HTTP_SERVER_VARS"]["SCRIPT_NAME"],
                  "start_time"   =>time());
    if (session_id()) {
        $config["SESSION"]=1;
    } else {
        $config["SESSION"]=0;
    }
    if (file_exists($cfname)) {
        $netsaintinfo=0;
        $clusterinfo=0;
        $jobsysteminfo=0;
        $hardwareinfo=0;
        $accountinginfo=0;
        $conffile=file($cfname);
        for ($i=0;$i < sizeof($conffile) ;$i++) {
            $line=$conffile[$i];
            if (! preg_match("/^#.*$/",$line)) {
                $split=preg_split("/=/",$line);
                if (count($split) == 2) {
                    $var=trim($split[0]);
                    $val=trim($split[1]);
                    $err=0;
                    switch ($var) {
                    case "MYSQL_HOST":
                    case "MYSQL_USER":
                    case "MYSQL_PASSWD":
                    case "MYSQL_DATABASE":
                    case "MYSQL_PORT":
                    case "NAGIOS_DATABASE":
                        break;
                    default:
                        $config["global_errors"]->addstr("Unknown key/value pair: $var / $val");
                        $err=1;
                        break;
                    }
                    if ($err == 0) $config[$var]=$val;
                }
            }
        }
        if ($config["MYSQL_HOST"] && $config["MYSQL_USER"] && $config["MYSQL_PASSWD"] && $config["MYSQL_DATABASE"]) {
            //echo "0 ",time(),"<br>";
            @$sys_db_con=mysql_connect($config["MYSQL_HOST"],$config["MYSQL_USER"],$config["MYSQL_PASSWD"]) or die("Cannot connect to SQL-Server, exiting ...");
            mysql_select_db($config["MYSQL_DATABASE"],$sys_db_con);
            $mret=mysql_query("SELECT g.name,g.value FROM genstuff g",$sys_db_con);
            while ($mds=mysql_fetch_object($mret)) $config[strtoupper($mds->name)]=$mds->value;
            $mret=mysql_query("SELECT c.name,c.enabled FROM capability c",$sys_db_con);
            while ($mds=mysql_fetch_object($mret)) $config[strtolower($mds->name)."_en"]=(int)$mds->enabled;
            $given_server_name=$GLOBALS["HTTP_SERVER_VARS"]["SERVER_NAME"];
            if (preg_match("/^\d+\.\d+\.\d+\.\d+$/",$given_server_name)) {
                $mres=mysql_query("SELECT d.name FROM netdevice n, device d, netip i WHERE i.netdevice=n.netdevice_idx AND n.device=d.device_idx AND i.ip='$given_server_name'",$sys_db_con);
                if (mysql_num_rows($mres)) {
                    $mfr=mysql_fetch_object($mres);
                    $server_name=$mfr->name;
                }
            } else {
                $server_name=explode(".",$given_server_name);
                $server_name=$server_name[0];
            }
            $mres=mysql_query("SELECT n.netdevice_idx,i.ip FROM network_type nt, netdevice n, device d, network nw, netip i WHERE nw.network_type=nt.network_type_idx AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx AND n.device=d.device_idx AND d.name='$server_name' AND nt.identifier != 'b'",$sys_db_con);
            //echo "1 ",time(),"<br>";
            if (mysql_num_rows($mres)) {
                $loc_ndevs=array();
                $ss_ndevs=array();
                $sd_ndevs=array();
                while ($mfr=mysql_fetch_object($mres)) {
                    $loc_ndevs[]=$mfr->netdevice_idx;
                    $ss_ndevs[]="h.s_netdevice=$mfr->netdevice_idx";
                    $sd_ndevs[]="h.d_netdevice=$mfr->netdevice_idx";
                }
                $ss_ndev_l=implode(" OR ",$ss_ndevs);
                $sd_ndev_l=implode(" OR ",$sd_ndevs);
                $mres=mysql_query("SELECT i.ip,n.netdevice_idx,c.name as cname,d.name as dname FROM network_type nt, device d, netdevice n, netip i, network nw, device_config dc, new_config c, new_config_type ct WHERE n.device=d.device_idx AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx AND dc.device=d.device_idx AND nw.network_type=nt.network_type_idx AND c.new_config_type=ct.new_config_type_idx AND nt.identifier != 'b' AND dc.new_config=c.new_config_idx AND (c.name='config_server' OR c.name='mother_server' OR c.name='rrd_server' OR c.name='server' OR c.name='yp_server' OR c.name='package_server' OR (d.name NOT LIKE('node%')) OR c.name LIKE('%export') OR c.name='sge_server' OR c.name='nagios_master' OR c.name='rebuild_hopcount')",$sys_db_con);
                $targ_dict=array();
                //echo "2 ",time(),"<br>";
                $lo_dict=array();
                $ndev_list=array();
                $max_pen=666666;
                $exp_list=array();
                while ($mfr=mysql_fetch_object($mres)) {
                    if (preg_match("/^.*export$/",$mfr->cname)) $exp_list[]=$mfr->cname;
                    $act_dname=$mfr->dname;
                    $act_conf=$mfr->cname;
                    $act_ndev=$mfr->netdevice_idx;
                    if (!in_array($act_conf,array_keys($targ_dict))) $targ_dict[$act_conf]=array();
                    if (!in_array($act_dname,array_keys($targ_dict[$act_conf]))) $targ_dict[$act_conf][$act_dname]=array();
                    $targ_dict[$act_conf][$act_dname][$act_ndev]=array("ip"=>$mfr->ip,"pen"=>$max_pen);
                    if (!in_array($act_ndev,array_keys($lo_dict))) $lo_dict[$act_ndev]=array();
                    if (!in_array($act_dname,array_keys($lo_dict[$act_ndev]))) $lo_dict[$act_ndev][$act_dname]=array();
                    $lo_dict[$act_ndev][$act_dname][]=$act_conf;
                    $ndev_list[]=$mfr->netdevice_idx;
                }
                //print_r($exp_list);
                $ndev_list=array_unique($ndev_list);
                $ds_ndevs=array();
                $dd_ndevs=array();
                foreach ($ndev_list as $nd) {
                    $ds_ndevs[]="h.s_netdevice=$nd";
                    $dd_ndevs[]="h.d_netdevice=$nd";
                }
                if (count($ds_ndevs) && count ($dd_ndevs)) {
                    //echo "3 ",time(),"<br>";
                    $ds_ndev_l=implode(" OR ",$ds_ndevs);
                    $dd_ndev_l=implode(" OR ",$dd_ndevs);
                    $mres=mysql_query("SELECT h.s_netdevice,h.d_netdevice,h.value FROM hopcount h WHERE (($ds_ndev_l) AND ($dd_ndev_l)) OR (($ss_ndev_l) AND ($dd_ndev_l)) ORDER BY h.value",$sys_db_con);
                    //echo "SELECT h.s_netdevice,h.d_netdevice,h.value FROM hopcount h WHERE (($ds_ndev_l) AND ($dd_ndev_l)) OR (($ss_ndev_l) AND ($dd_ndev_l)) ORDER BY h.value","<br>";
                    //echo "3a ",time(),"<br>";
                    while ($mfr=mysql_fetch_object($mres)) {
                        if (!in_array($mfr->s_netdevice,$loc_ndevs)) {
                            $src_dev=$mfr->d_netdevice;
                            $dest_dev=$mfr->s_netdevice;
                        } else {
                            $src_dev=$mfr->s_netdevice;
                            $dest_dev=$mfr->d_netdevice;
                        }
                        if (in_array($src_dev,$loc_ndevs)) {
                            if (in_array($dest_dev,array_keys($lo_dict))) {
                                foreach ($lo_dict[$dest_dev] as $t_dname=>$tdn_s) {
                                    foreach ($tdn_s as $t_conf) {
                                        $td_stuff=$targ_dict[$t_conf][$t_dname][$dest_dev];
                                        if ($td_stuff["pen"] >= $mfr->value) {
                                            $targ_dict[$t_conf][$t_dname][$dest_dev]["pen"]=$mfr->value;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                //echo "4 ",time(),"<br>";
                foreach ($targ_dict as $cname=>$s1) {
                    if (in_array($cname,$exp_list)) {
                        $r_name="export";
                    } else {
                        $r_name=$cname;
                    }
                    if (!in_array($r_name,array_keys($config))) $config[$r_name]=array();
                    foreach ($s1 as $dname=>$s2) {
                        $lm_pen=$max_pen;
                        $best_ip="*";
                        foreach ($s2 as $idx=>$s3) {
                            if ($s3["pen"] < $lm_pen) {
                                $best_ip=$s3["ip"];
                                $lm_pen=$s3["pen"];
                            }
                        }
                        if ($lm_pen < $max_pen) {
                            $config[$r_name][$dname]=$best_ip;
                        } else {
                            $config[$r_name]["localhost"]="127.0.0.1";
                        }
                    }
                }
                //print_r($config);
            } else {
                $mres=mysql_query("SELECT * FROM device");
                if (mysql_num_rows($mres)) $config["global_errors"]->addstr("Major config failure: cannot determine webfrontend-host (check /etc/httpd/httpd.conf, name found there is '$server_name', netdevice/ipaddress present ?)");

            }
            if (!isset($config["CLUSTERNAME"])) $config["CLUSTERNAME"]=htmlspecialchars("<name not set>");
            //echo "5 ",time(),"<br>";
        }
    } else {
        $config["ERROR"]=1;
    }
    return $config;
}
function clusterhead(&$config,$what,$style_file,$loc_style=array()) {
    // already set in readconfig
    //$config["start_time"]=time();
    if ($config["ERROR"] == 0) {
        echo "<head>\n";
        echo "<meta name=\"generator\" content=\"webfrontend php scripts\">\n";
        echo "<meta http-equiv=\"content-type\" content=\"text/html; charset=ISO-8859-1\">\n";
        if (isset($config["AUTO_RELOAD"])) {echo "<meta http-equiv=\"refresh\" content=\"{$config['AUTO_RELOAD']}";
            if (isset($config["RELOAD_TARGET"])) {
                echo "; URL={$config['RELOAD_TARGET']}"; 
                if ($config["SESSION"] == 1) echo "?".write_sid();
            }
            echo "\">";
            echo "<meta http-equiv=\"expires\" content=\"0\">\n";
        } else if (isset($config["EXPIRES"])) {
            echo "<meta http-equiv=\"expires\" content=\"0\">\n";
        }
        echo "<meta http-equiv=\"pragma\" content=\"no-cache\">\n";
        echo "<meta http-equiv=\"cache-control\" content=\"no-cache\">\n";
        echo "<title>{$config['CLUSTERNAME']} - $what</title>\n";
        echo "<link rel=stylesheet type=\"text/css\" href=\"$style_file\">\n";
        echo "<style type=\"text/css\">\n";
        foreach (array("th.thi"=>array("width:90px","color:#000000","background-color:#ffffff","border-width:0px","padding:0px","margin:0px"),
                       "th.thfl"=>array("text-align:center","font-size:x-large","color:#000000","background-color:#e8e8e8","padding:0px"),
                       "th.thrp"=>array("text-align:right","font-weight:normal","width:25%","color:#000000","background-color:#f4f4f4","vertical-align:middle","height:0%"),
                       "td.thrp"=>array("text-align:right","font-weight:normal","width:25%","color:#000000","background-color:#f4f4f4","vertical-align:middle","height:0%"),
                       "td.thrc"=>array("text-align:center","font-weight:normal","width:25%","color:#000000","background-color:#f4f4f4"),
                       "td.thrc2"=>array("text-align:center","font-weight:normal","color:#000000","background-color:#f0f0f0","font-size:small","padding:0px","margin:0px"),
                       "td.w3cvalid"=>array("text-align:right","width:88px","height:31px","color:#000000","backgroup-color:#ffffff"),
                       "img.w3cvalid"=>array("border-width:0px"),
                       ) as $what=>$stuff) echo "$what { ".implode("; ",$stuff)."; } \n";
        if (count($loc_style)) {
            foreach ($loc_style as $what=>$stuff) echo "$what { ".implode("; ",$stuff)."; } \n";
        }
        echo "</style>\n";
        echo "</head>\n";
    }
}
function clusterbody($config,$text,$ref=array(),$ref_g=array(),$small=0) {
    if ($config["ERROR"] == 0) {
        echo "<body class=\"blind\">\n";
        if ($small == 1) {
            if (isset($config["CLUSTERPICTURE"])) {
                echo "<div class=\"center\">";
                echo "<img alt=\"Clustername\" src=\"{$config['CLUSTERPICTURE']}\">";
                echo "</div>";
            }
            echo "<h1>{$config['CLUSTERNAME']} - $text</h1>\n";
        } else {
	    $act_ref=array();
            $logo_height=2;
            if ($config["SESSION"] && (count($ref) || count ($ref_g))) {
		$scr_name=$GLOBALS["HTTP_SERVER_VARS"]["SCRIPT_NAME"];
		$mres=query("SELECT c.name,c.capability_group_name FROM capability c WHERE c.scriptname='$scr_name'");
		if (mysql_num_rows($mres)) {
		    $mfr=mysql_fetch_object($mres);
		    $own_cap=$mfr->name;
		} else {
		    $own_cap="???";
		}
                $check_ref=array();
                foreach ($ref as $ar) {
		    if ($ar != $own_cap) $check_ref[]="(gc.capability=c.capability_idx AND c.name='$ar' AND c.enabled AND c.capability_group=cg.capability_group_idx)";
		}
                foreach ($ref_g as $ag) $check_ref[]="(gc.capability=c.capability_idx AND c.enabled AND c.capability_group=cg.capability_group_idx AND cg.name='$ag' AND c.name != '$own_cap')";
                if (count($check_ref)) {
                    $mres=query("SELECT c.* FROM capability c, ggroupcap gc, capability_group cg WHERE gc.ggroup={$config['ggroup_idx']} AND (".implode(" OR ",$check_ref).") ORDER BY c.name");
                    if (mysql_num_rows($mres)) {
                        while ($mfr=mysql_fetch_object($mres)) $act_ref[]=array($mfr->left_string,$mfr->scriptname);
                    }
                    if (count($act_ref)) $logo_height++;
                }
            }
            echo "<table class=\"blind\" summary=\"headtable\"><tr>\n";
            echo "<th class=\"thi\" rowspan=\"$logo_height\" >\n";
            echo "<a class=\"init\" href=\"http://www.init.at\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>";
            echo "</th>\n<th class=\"thfl\" rowspan=\"2\">";
            echo "{$config['CLUSTERNAME']} - $text";
            echo "</th>\n";
            echo "<th class=\"thrp\">";
            echo "<a class=\"header\" href=\"";
            if (isset($config["RELOAD_TARGET"]) && strlen($config["RELOAD_TARGET"])) {
                echo $config["RELOAD_TARGET"];
            } else {
                echo "../python/main.py";
            }
            if ($config["SESSION"]) echo "?SID=".$config["python_session_id"];
            //if ($config["SESSION"] == 1) echo "?".write_sid();
            echo "\">back to home</a></th></tr>\n";
            echo "<tr><td class=\"thrp\">";
            if ($config["SESSION"]) {
                echo "<form action=\"logincheck.php?".write_sid()."\" method=post>";
                echo "Logged in as {$GLOBALS['HTTP_SESSION_VARS']['session_user']} , ";
                echo "<input type=submit name=\"logout\" value=\"logout\" /></form>\n";
            } else {
                echo "Not logged in";
            }
            echo "</td></tr>\n";
            if (count($act_ref)) {
                $logo_height++;
                $num_ref=count($act_ref);
                $max_width=600;
                $rows=intval(($num_ref+$max_width-1)/$max_width);
                $per_row=intval($num_ref/$rows);
                echo "<tr><td colspan=\"2\" class=\"thrc2\"><table class=\"blind\" summary=\"navigation table\">";
                for ($r=0;$r<$rows;$r++) {
                    echo "<tr>\n";
                    $counter=$per_row;
                    while ($counter && $num_ref) {
                        $counter--;
                        $num_ref--;
                        list($string,$script)=array_shift($act_ref);
                        echo "<td class=\"thrc2\"><a class=\"header\" href=\"".get_relative_dir($config)."$script?".write_sid()."\" >".str_replace(" ","&nbsp;",$string)."</a></td>\n";
                    }
                    echo "</tr>\n";
                }
                echo "</table></td></tr>\n";
            }
            echo "</table>\n";
        }
    }
}
function errorpage($error_var,$style_file="formate.css") {
    htmlhead();
    global $sys_config;
    if (is_string($error_var)) {
        $sys_config["global_errors"]->addstr($error_var);
    } elseif (is_array($error_var)) {
        foreach ($error_var as $err_str) {
            $sys_config["global_errors"]->addstr(strval($err_str));
        }
    } elseif (is_null($error_var)) {
    } else {
        $sys_config["global_errors"]->addstr(strval($error_var));
    }
    clusterhead($sys_config,"Error",$style_file);
    if (!isset($sys_config["AUTO_RELOAD"])) $sys_config["AUTO_RELOAD"]=30;
    if ($sys_config["AUTO_RELOAD"] > 0 && count($sys_config["global_errors"])) clusterbody($sys_config,"Errorpage");
    write_error_footer($sys_config,$page_errors=0);
    writesimplefooter();
}
function htmlhead() {
    if (1) {
        echo "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\" \"http://www.w3.org/TR/html4/strict.dtd\" >\n";
        echo "<html>\n";
    } else {
        echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>";
        echo "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD XHTML 1.0//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd\" >\n" ;
        echo "<html xmlns=\"http://www.w3.org/1999/xhtml\" >\n";
    }
}
function writefooter($config) {
    $diff_time=time()-$config["start_time"];
    if (mysql_stats_used() && (isset($config["ucl"]["sql"]) && $config["ucl"]["sql"])) echo "<div class=\"center\">".get_mysql_stats()."</div>\n";
    echo "<hr>";
    write_error_footer($config);
    echo "<table class=\"blind\" summary=\"footertable\"><tr><td class=\"left\" >";
    if ($diff_time < 1) {
        $diff_str=" < 1 sec";
    } else {
        $diff_str=" $diff_time secs";
    }
    echo "Page generated : ".date("l, j. F Y; G:i:s",time()).",$diff_str";
    if (isset($config["AUTO_RELOAD"])) {
        echo " ; page is reloaded every ".$config["AUTO_RELOAD"]." seconds.";
    }
    echo "</td><td class=\"right\">";
    $mres=query("SELECT u.useremail,u.login FROM user u WHERE u.cluster_contact AND u.useremail != ''");
    if (mysql_num_rows($mres)) {
        $cname=((isset($config["CLUSTERNAME"])) ? $config["CLUSTERNAME"] : "Cluster");
	$tm_f=array();
	$tl_f=array();
	while ($mfr=mysql_fetch_object($mres)) {
	    $tm_f[]=$mfr->useremail;
	    $tl_f[]=$mfr->login;
	}
        echo "<a href=\"mailto:".implode(",%20",$tm_f)."?subject=Clusterrequest%20from%20$cname\">&lt;contact support (".implode(", ",$tl_f).")&gt;</a>";
    } else {
        echo "&nbsp;";
    }
    echo "</td>\n";
    if (isset($config["POLITICAL_CORRECT"]) && !$config["POLITICAL_CORRECT"]) {
        echo "<td class=\"w3cvalid\">";
        echo "<a href=\"http://wirrichtensuns.at\">";
        echo "<img class=\"w3cvalid\" src=\"/icons-init/banner_160.jpg\" alt=\"wirrichtensuns.at\" ></a></td>\n";
    }
    echo "<td class=\"w3cvalid\">";
    echo "<a href=\"http://validator.w3.org/check/referer\">";
    echo "<img class=\"w3cvalid\" src=\"/icons-init/valid-html401.png\" alt=\"Valid HTML 4.01!\" height=\"31\" width=\"88\"></a></td>\n";
    echo "<td class=\"w3cvalid\">";
    echo "<a href=\"http://jigsaw.w3.org/css-validator/\">";
    echo "<img class=\"w3cvalid\" src=\"/icons-init/valid-css.png\" alt=\"Valid CSS!\" height=\"31\" width=\"88\"></a></td>\n";
    echo "</tr></table>";
    writesimplefooter();
}
function write_error_footer($config,$page_errors=1) {
    $num_e=$config["global_errors"]->get_num_errors();
    if ($num_e) {
        $me_str=get_plural("error",$num_e,1)." occured";
        if ($page_errors) $me_str.=" during the processing of this page";
        $me_str.=":";
        $config["global_errors"]->printstack($me_str);
        $config["global_errors"]->savestack("/tmp/webfrontend.errors");
    }
}
function writesimplefooter() {
    echo "\n</body>\n</html>\n";
}
?>
