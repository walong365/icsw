<?php
//-*ics*- ,CAP,name:'csc',descr:'Server configuration',enabled:1,defvalue:0,scriptname:'/php/servercontrol.php',left_string:'Servercontrol',right_string:'Control the Clusterserver',capability_group_name:'conf',pri:-60
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
} else if (! $sys_config["csc_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    // disable auto-reload
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    // get list of machinegroups
    htmlhead();
    clusterhead($sys_config,"Server control page",$style="formate.css",
                array("th.csname"=>array("background-color:#e2d2d2"),
                      "td.csname"=>array("background-color:#e2d2d2","text-align:center"),
                      "td.csnamedown"=>array("background-color:#ff8080","text-align:center"),
                      "th.csnum"=>array("background-color:#aabbbb"),
                      "td.csnum"=>array("background-color:#bbcccc","text-align:center"),
                      "td.csnumdown"=>array("background-color:#ff8080","text-align:center"),
                      "th.cstasks"=>array("background-color:#ffddee"),
                      "td.cstasks"=>array("background-color:#ddddbb","text-align:left"),
                      "td.cstaskidx"=>array("background-color:#e4e4d9","text-align:right"),
                      "td.cstasksdown"=>array("background-color:#ff8080","text-align:center"),
                      "th.cslog"=>array("background-color:#eeddff"),
                      "td.cslog"=>array("background-color:#bbdddd","text-align:left"),
                      "option.csnd"=>array("background-color:#777777","color:#ffffff"),
                      "option.cscr"=>array("background-color:#ffffff","color:#ff6666"),
                      "option.csns"=>array("background-color:#ffffff","color:#000000")
                      )
                );
    clusterbody($sys_config,"Server control",array(),array("conf"));
    $ucl=usercaps($sys_db_con);
    $logstack=new messagelog();
    if ($ucl["csc"]) {
        $hostlist=array();
        //print_r($vars);
        //echo "<br>";
        if (is_set("action",$vars)) {
            $action=$vars["action"];
            if (is_set("{$action}h",&$vars)) $hostlist=$vars["{$action}h"];
        } else {
            $action="none";
        }
        $com_dict=array("none"=>array("str"=>"none","selected"=>1),
                        "hosts"=>array("str"=>"renew /etc/hosts","selected"=>0,"config"=>array("auto_etc_hosts"),"com"=>"write_etc_hosts"),
                        "named"=>array("str"=>"renew the Nameserver configuration","selected"=>0,"config"=>array("name_server","name_slave"),"com"=>"write_nameserver_config"),
                        "dhcpd"=>array("str"=>"renew the dhcp-server configuration","selected"=>0,"config"=>array("dhcp_server"),"com"=>"write_dhcpd_config"),
                        "ypserv"=>array("str"=>"renew the YP-server configuration","selected"=>0,"config"=>array("yp_server"),"com"=>"write_yp_config"),
			"hopcount"=>array("str"=>"rebuild the Hopcount-table","selected"=>0,"config"=>array("rebuild_hopcount"),"com"=>"rebuild_hopcount")
                        );
        if ($action != "none") {
            if (isset($com_dict[$action]["com"])) {
                $command=$com_dict[$action]["com"];
                foreach ($hostlist as $host) {
                    $serv_result=contact_server($sys_config,"server",8004,$command,$timeout=10,$hostname=$host);
                    $logstack->add_message("$action on $host",$serv_result,preg_match("/^ok.*$/",$serv_result));
                }
            } else {
                $logstack->add_message("$action on selected hosts ".implode(", ",$hostlist),"No command defined for $action",0);
            }
        }
        //print_r($hostlist);
        if ($logstack->get_num_messages()) $logstack->print_messages();
        $mres=query("SELECT DISTINCT d.name,d.device_idx FROM device d, deviceconfig mc, config c, config_type ct WHERE mc.device=d.device_idx AND mc.config=c.config_idx AND c.config_type=ct.config_type_idx AND ct.identifier='s' ORDER BY d.name");
        $servers=array();
        while ($mfr=mysql_fetch_object($mres)) {
            $servers[$mfr->name]=$mfr;
        }
        $num_servers=count($servers);
        if ($num_servers) {
            message("Found $num_servers ".get_plural("Clusterserver",$num_servers));
            echo "<table class=\"normal\"><tr>\n";
            echo "<th class=\"csname\">Servername</th>";
            echo "<th class=\"cstasks\">Task info/Log</th>";
            echo "</tr>\n";
            $mres=query("SELECT c.name,c.descr FROM config c, config_type ct WHERE ct.identifier='s' AND ct.config_type_idx=c.config_type");
            $server_configs=array();
            while ($mfr=mysql_fetch_object($mres)) $server_configs[$mfr->name]=$mfr->descr;
            foreach ($servers as $sname=>$server) {
                $serv_result=contact_server($sys_config,"server",8004,"info",$timeout=10,$hostname=$sname);
                if (preg_match("/^ok\s*(\S+).*$/",$serv_result,$serv_str)) {
                    if (preg_match("/^:.*$/",$serv_str[1])) {
                        $props=explode(":",substr($serv_str[1],1));
                    } else {
                        $props=explode(":",$serv_str[1]);
                    }
                    $version=array_shift($props);
                    $num_props=count($props);
                    $sstate="";
                } else {
                    $num_props=-1;
                    $sstate="down";
                    $version="?.?";
                }
                $mres=query("SELECT d.text,d.date FROM devicelog d, log_source l WHERE d.log_source=l.log_source_idx AND l.device=$server->device_idx AND l.identifier='cluster-server' ORDER BY d.date DESC");
                $slog=array();
                while ($mfr=mysql_fetch_object($mres)) $slog[]=$mfr;
                echo "<tr>";
                echo "<td class=\"csname$sstate\" rowspan=\"2\">$sname ($version)</td>";
                if ($num_props > 0) {
                    echo "<td class=\"cstasks$sstate\"><table class=\"blind\">";
                    echo "<tr><th class=\"csnum\" colspan=\"3\">$num_props ".get_plural("task",$num_props)." found</th></tr>\n";
                    $idx=0;
                    foreach ($props as $prop) {
                        $idx++;
                        echo "<tr><td class=\"cstaskidx\">$idx </td><td class=\"cstasks$sstate\"> $prop</td><td class=\"cstasks$sstate\">{$server_configs[$prop]}</td></tr>\n";
                    }
                    echo "</table></td>";
                } else if ($num_props == 0) {
                    echo "<td class=\"cstasks$sstate\">";
                    echo "no tasks defined";
                    echo "</td>";
                } else {
                    echo "<td class=\"cstasks$sstate\">";
                    echo "error (no connection)";
                    echo "</td>";
                }
                echo "</tr>\n";
                echo "<tr><td class=\"cslog\">";
                if (count($slog)) {
                    $last_day=-1;
                    echo "<select size=\"10\">\n";
                    $first=0;
                    foreach ($slog as $entry) {
                        $date=$entry->date;
                        $time=mktime(intval(substr($date,8,2)),intval(substr($date,10,2)),intval(substr($date,12,2)),
                                     intval(substr($date,4,2)),intval(substr($date,6,2)),intval(substr($date,0,4)));
                        $act_day=intval(date("z",$time));
                        if ($act_day != $last_day) {
                            echo "<option class=\"csnd\">".substr("-- ".date("D, j. F Y",$time)." $bl_okstr",0,30)."</option>\n";
                            $last_day=$act_day;
                        }
                        $t_str=date("G:i:s",$time)." ";
                        echo "<option ";
                        if (!$first++) echo " selected ";
                        echo ">$t_str: $entry->text</option>\n";
                    }
                    echo "</select>\n";
                } else {
                    echo "No log found";
                }
                echo "</td></tr>\n";
            }
            echo "</table>\n";
            message("Please choose an action:");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            echo "<table class=\"blind\">";
            foreach ($com_dict as $a_name=>$a_stuff) {
                echo "<tr>";
                echo "<td class=\"right\">{$a_stuff['str']}:</td><td><input type=radio name=\"action\" value=\"$a_name\" ";
                if ($a_stuff["selected"]) echo " \"checked\" ";
                echo "></td>\n";
                echo "<td class=\"left\">";
                if (isset($a_stuff["config"])) {
                    $mres=query("SELECT d.name,c.name AS cname,c.descr FROM device d, deviceconfig mc, config c, config_type ct WHERE mc.device=d.device_idx AND mc.config=c.config_idx AND c.config_type=ct.config_type_idx AND ct.identifier='s' AND (c.name='".implode("' OR c.name='",$a_stuff["config"])."') ORDER BY d.name");
                    if (mysql_num_rows($mres)) {
                        echo "<select name=\"".$a_name."h[]\" multiple>";
                        while ($mfr=mysql_fetch_object($mres)) {
                            echo "<option value=\"$mfr->name\" selected >$mfr->name ($mfr->cname, $mfr->descr)</option>\n";
                        }
                        echo "</select>\n";
                    } else {
                        echo "No hosts found";
                    }
                } else {
                    echo "---";
                }
                echo "</td>\n";
                echo "</tr>\n";
            }
            echo "</table>\n";
            message("<input type=submit value=\"submit\" />",$type=2);
            echo "</form>";
        } else {
            message("No Clusterservers found");
        }
    } else {
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
