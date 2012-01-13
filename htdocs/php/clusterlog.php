<?php
//-*ics*- ,CAP,name:'clo',descr:'Cluster log',enabled:1,defvalue:0,scriptname:'/php/clusterlog.php',left_string:'Cluster log',right_string:'Show and add entries to the Clusterlog',capability_group_name:'info',pri:20
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
class device {
    var $name,$dgname,$idx;
    function device($name,$dgname,$idx) {
        $this->name=$name;
        $this->dgname=$dgname;
        $this->idx=$idx;
    }
}
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["clo_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);

    // parse the machine selection
    htmlhead();
    clusterhead($sys_config,"Cluster log page",$style="formate.css",
                array("th.device"=>array("background-color:#e0eefe"),
                      "td.device"=>array("background-color:#c0ccec","text-align:left"),
                      "th.num"=>array("background-color:#fefefe"),
                      "td.num"=>array("background-color:#eeeeee","text-align:center"),
                      "th.del"=>array("background-color:#ffaaaa"),
                      "td.del"=>array("background-color:#ee9999","text-align:center"),
                      "th.logsource"=>array("background-color:#eefee0"),
                      "td.logsource"=>array("background-color:#ceeec0","text-align:center"),
                      "td.logsourceu"=>array("background-color:#ffff00","text-align:center"),
                      "th.loglev"=>array("background-color:#feeee0"),
                      "td.loglev"=>array("background-color:#ecccc0","text-align:center"),
                      "th.text"=>array("background-color:#eeeeee"),
                      "td.text"=>array("background-color:#cccccc","text-align:left"),
                      "th.time"=>array("background-color:#ffeeee"),
                      "td.time"=>array("background-color:#eecccc","text-align:center"),
                      "th.date"=>array("background-color:#eeffee"),
                      "td.date"=>array("background-color:#cceecc","text-align:center"),
                      "td.users"=>array("background-color:#ddeedd","text-align:left")
                      )
                );
    clusterbody($sys_config,"Cluster log",array(),array("info"));
  
    $ucl=usercaps($sys_db_con);
    if ($ucl["clo"]) {
        // log status
        $log_status=get_log_status();
        // log sources
        $log_sources=get_all_log_sources();
        $log_users=get_all_log_users();
        $log_targets=get_log_targets();
        $size_array=array(15,25,50,75,100,150);
        $hidden_stuff="";
        if (is_set("log_src_idx",&$vars)) {
            $log_src_idx=$vars["log_src_idx"];
            if (in_array("-1",$log_src_idx) && $log_src_idx != array(0=>"-1")) array_splice($log_src_idx,array_search("-1",$log_src_idx),1);
        } else {
            $log_src_idx=array();
        }
        foreach ($log_src_idx as $lsi) $hidden_stuff.="<input type=hidden name=\"log_src_idx[]\" value=\"$lsi\"/>\n";
        if (is_set("show_ext",&$vars)) {
            $show_ext=1;
            $hidden_stuff.="<input type=hidden name=\"show_ext\" value=\"1\"/>\n";
        } else {
            $show_ext=0;
        }
        if (is_set("log_stat_idx",&$vars)) {
            $log_stat_idx=$vars["log_stat_idx"];
        } else {
            $log_stat_idx=array_keys($log_status);
            $log_stat_idx=$log_stat_idx[0];
        }
        $hidden_stuff.="<input type=hidden name=\"log_stat_idx\" value=\"$log_stat_idx\"/>\n";
        if (is_set("log_dev_idx",&$vars)) {
            $log_dev_idx=$vars["log_dev_idx"];
            if (in_array("-1",$log_dev_idx) && $log_dev_idx != array(0=>"-1")) array_splice($log_dev_idx,array_search("-1",$log_dev_idx),1);
        } else {
            $log_dev_idx=array();
        }
        foreach ($log_dev_idx as $ldi) $hidden_stuff.="<input type=hidden name=\"log_dev_idx[]\" value=\"$ldi\"/>\n";
        if (is_set("disp_size",&$vars)) {
            $disp_size=$vars["disp_size"];
        } else {
            $disp_size=$size_array[0];
        }
        $hidden_stuff.="<input type=hidden name=\"disp_size\" value=\"$disp_size\"/>\n";
        if (is_set("disp_start",&$vars)) {
            $disp_start=$vars["disp_start"];
        } else {
            $disp_start=0;
        }
        $hidden_stuff.="<input type=hidden name=\"disp_start\" value=\"$disp_start\"/>\n";
        // check for new log-entry
        $user_log_idx=get_log_source("user");
        $user_log_idx=$user_log_idx->log_source_idx;
        $log_change=0;
        $log_stack=new messagelog();
        $ins_idx=0;
        if (is_set("dellog",&$vars)) {
            $del_list=$vars["dellog"];
            foreach ($del_list as $del_idx) {
                query("DELETE FROM extended_log WHERE devicelog=$del_idx");
                query("DELETE FROM devicelog WHERE devicelog_idx=$del_idx");
                $log_change=1;
            }
        }
        if (is_set("delextlog",&$vars)) {
            $del_list=$vars["delextlog"];
            foreach ($del_list as $del_idx) {
                query("DELETE FROM extended_log WHERE extended_log_idx=$del_idx");
                $log_change=1;
            }
        }
        $log_ins_idx=0;
        if (is_set("addlog",&$vars)) {
            $log_lev=$vars["loglevel"];
            $log_text=un_quote(trim($vars["logtext"]));
            if (strlen($log_text)) {
                $ins_idx=insert_table("devicelog","0,{$vars['logdevice']},$user_log_idx,{$sys_config['user_idx']},$log_lev,'".mysql_escape_string($log_text)."',null");
                $log_stack->add_message("added devicelog","ok",1);
                $log_ins_idx=$ins_idx;
                $log_change=1;
            } else {
                $log_stack->add_message("cannot add devicelog: empty log_text","error",0);
                $ins_idx=0;
                //echo "$log_lev***$log_text***<br>";
            }
        } else if (is_set("dlta",&$vars)) {
            $ins_idx=$vars["dlta"];
        }
        if (is_set("extlog",&$vars) && $ins_idx) {
            $act_log_users=$vars["logusers"];
            $descr_txt=$vars["descr"];
            $subj_txt=$vars["subject"];
            if ($act_log_users && $descr_txt && $subj_txt) {
                $log_users_f=explode(",",$act_log_users);
                insert_table("extended_log","0,$ins_idx,$user_log_idx,{$sys_config['user_idx']},'".mysql_escape_string(un_quote(implode(",",$log_users_f))).
                             "','".mysql_escape_string(un_quote($subj_txt)).
                             "','".mysql_escape_string(un_quote($descr_txt))."',null");
                $log_stack->add_message("added extended devicelog","ok",1);
                $log_change=1;
            } else {
                if (!$act_log_users) $log_stack->add_message("Cannot add extened log","no log_users given",0);
                if (!$descr_txt) $log_stack->add_message("Cannot add extened log","empty description",0);
                if (!$subj_txt) $log_stack->add_message("Cannot add extened log","empty subject",0);
                if ($log_ins_idx) {
                    query("DELETE FROM devicelog WHERE devicelog_idx=$log_ins_idx");
                    $log_stack->add_message("Removed LogEntry","warning",2);
                    $log_change=0;
                }
            }
        }
        if ($log_stack->get_num_messages()) $log_stack->print_messages();
        if ($log_change) $log_users=get_all_log_users();
        $log_targets=get_log_targets();
        //echo "** $log_src_idx ** $log_stat_idx ** $log_dev_idx<br>";
        if (count($log_targets)) {
            message("Please select which LogEntries you wish to see");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            echo "<div class=\"center\">";
            echo "<table class=\"simple\"><tr>";
            echo "<td><select name=\"log_src_idx[]\" size=\"5\" multiple >\n";
            echo "<option value=\"-1\" ";
            if (in_array("-1",$log_src_idx)) echo " selected ";
            echo ">all</option>\n";
            if (count($log_users)) {
                echo "<option disabled>".sprintf("--- %d log users found ------",count($log_users))."</option>\n";
                foreach ($log_users as $idx=>$stuff) {
                    echo "<option value=\"u_$idx\" ";
                    if (in_array("u_$idx",$log_src_idx)) echo " selected ";
                    echo ">$stuff->login ($stuff->logcount entries)</option>\n";
                }
            }
            echo "<option disabled>--- System logsources --------</option>\n";
            foreach ($log_sources as $idx=>$stuff) {
                if ($idx && $stuff->identifier != "user") {
                    echo "<option value=\"s_$idx\" ";
                    if (in_array("s_$idx",$log_src_idx)) echo " selected ";
                    echo ">$stuff->name ($stuff->description)</option>\n";
                }
            }
            echo "</select>\n";
            echo "</td>\n<td>";
            $log_status_a2=array();
            echo "<select name=\"log_stat_idx\" size=\"5\">\n";
            foreach ($log_status as $idx=>$stuff) {
                $log_status_a2[$stuff->log_status_idx]=$stuff;
                echo "<option value=\"$idx\" ";
                if ($log_stat_idx == $idx) echo " selected ";
                echo ">$stuff->name ($stuff->log_level)</option>\n";
            }
            echo "</select>\n";
            echo "</td>\n<td>";
            echo "<select name=\"log_dev_idx[]\" multiple size=\"5\">\n";
            echo "<option value=\"-1\" ";
            if (in_array("-1",$log_dev_idx)) echo " selected ";
            echo ">all</option>\n";
            foreach ($log_targets as $idx=>$stuff) {
                if ($stuff->name) {
                    $act_name=$stuff->name;
                } else {
                    $act_name="Cluster";
                }
                echo "<option value=\"$idx\" ";
                if (in_array($idx,$log_dev_idx)) echo " selected ";
                echo ">$act_name ($stuff->logcount entries)</option>\n";
            }
            echo "</select>\n";
            echo "</td></tr>\n";
            // generate sql-string for the log-request
            $sql_srcs=array("devicelog d","log_status ls");
            $log_source_f=array();
            $sql_add_f=array();
            $multi_log_source=0;
            if (count($log_src_idx)) {
                foreach ($log_src_idx as $ls_idx) {
                    if (preg_match("/^(.)_(\d+)$/",$ls_idx,$log_p)) {
                        if ($log_p[1]=="u") {
                            // user request
                            $sql_add_f[]=" (d.log_source=$user_log_idx AND d.user={$log_p[2]}) ";
                            $log_source_f[]="user {$log_users[$log_p[2]]->login}";
                        } else {
                            // system request
                            $sql_add_f[]=" (d.log_source={$log_p[2]}) ";
                            $log_source_f[]="system {$log_sources[$log_p[2]]->name}";
                        }
                    } else {
                        // all
                        $multi_log_source=1;
                        $sql_add_f[]=" 1 ";
                        $log_source_f[]="all log sources";
                    }
                }
            } else {
                $sql_add_f[]="0";
                $log_source_f[]="no log sources";
            }
            if (count($sql_add_f) > 1) $multi_log_source=1;
            $log_source_str=implode(", ",$log_source_f);
            $sql_add_str="AND (".implode(" OR ",$sql_add_f).") ";
            // log device
            $num_devs=count($log_dev_idx);
            if ($num_devs) {
                $log_devices=array(0=>"Cluster");
                if ($log_dev_idx[0]=="-1") {
                    $num_devs=2;
                    $mres=query("SELECT d.name,d.device_idx FROM device d WHERE (d.device_idx=".implode(" OR d.device_idx=",array_keys($log_targets)).")");
                    $sql_add_str.=" AND (d.device=".implode(" OR d.device=",array_keys($log_targets)).")";
                } else {
                    $mres=query("SELECT d.name,d.device_idx FROM device d WHERE (d.device_idx=".implode(" OR d.device_idx=",$log_dev_idx).")");
                    $sql_add_str.=" AND (d.device=".implode(" OR d.device=",$log_dev_idx).")";
                }
                while ($mfr=mysql_fetch_object($mres)) $log_devices[$mfr->device_idx]=$mfr->name;
                if ($log_dev_idx[0]=="-1") {
                    $dev_str="all devices";
                } else {
                    if ($num_devs == 1) {
                        $dev_str="single device {$log_devices[$log_dev_idx[0]]}";
                    } else {
                        $dev_str=strval(count($log_dev_idx))." devices";
                    }
                }
            } else {
                $sql_add_str.=" AND 0";
                $dev_str="no device";
            }
            $log_level_str="log-level {$log_status[$log_stat_idx]->log_level} and higher";
            $sql_str="SELECT d.*,DATE_FORMAT(d.date,'%e. %b %Y') as l_date, DATE_FORMAT(d.date,'%H:%i:%s') as l_time FROM devicelog d, log_status ls WHERE d.log_status=ls.log_status_idx AND ls.log_level >= {$log_status[$log_stat_idx]->log_level} $sql_add_str ORDER BY d.date DESC, d.devicelog_idx DESC";
            $mres=query($sql_str);
            $num_entries=mysql_num_rows($mres);
            $disp_off_array=array();
            echo "<tr><td colspan=\"3\">\n";
            if ($num_entries) {
                while ($disp_start >= $num_entries) $disp_start-=$disp_size;
                echo "showing <select name=\"disp_size\">\n";
                foreach ($size_array as $act_size) {
                    echo "<option value=\"$act_size\" ";
                    if ($disp_size == $act_size) echo " selected ";
                    echo ">$act_size lines</option>\n";
                }
                echo "</select> (with extended_log: <input type=checkbox name=\"show_ext\" ";
                if ($show_ext) echo " checked ";
                echo "/>), offset \n";
                echo "<select name=\"disp_start\">\n";
                $act_row=1;
                while ($act_row <= $num_entries) {
                    $last_row=$act_row-1;
                    mysql_data_seek($mres,$act_row-1);
                    $act_data_1=mysql_fetch_object($mres);
                    $old_time_str="$act_data_1->l_date, $act_data_1->l_time";
                    $act_row=min($act_row+$disp_size-1,$num_entries);
                    mysql_data_seek($mres,$act_row-1);
                    $act_data_2=mysql_fetch_object($mres);
                    $act_time_str="$act_data_2->l_date, $act_data_2->l_time";
                    echo "<option value=\"$last_row\" ";
                    if ($disp_start == $last_row) {
                        $start_idx=$act_data_1->devicelog_idx;
                        $end_idx=$act_data_2->devicelog_idx;
                        echo " selected ";
                    }
                    echo ">".sprintf("%4d",$last_row+1)." - ".sprintf("%4d",$act_row)." ; $old_time_str - $act_time_str</option>\n";
                    $act_row++;
                }
                echo "</select>\n";
            }
            echo "<input type=submit value=\"select\"/></td></tr>\n";
            echo "</table></div></form>";
        } else {
            message("No log-targets found");
            $num_entries=0;
        }
        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
        //echo "$sql_str : ",,"<br>";
        if ($num_entries) {
            $mres2=query("SELECT e.extended_log_idx,e.users,e.subject,e.devicelog,e.description,DATE_FORMAT(e.date,'%e. %b %Y') as el_date, DATE_FORMAT(e.date,'%H:%i:%s') as el_time FROM extended_log e, devicelog d, log_status ls WHERE (e.devicelog <= $start_idx AND e.devicelog >= $end_idx) AND e.devicelog=d.devicelog_idx AND d.log_status=ls.log_status_idx AND ls.log_level >= {$log_status[$log_stat_idx]->log_level} $sql_add_str ORDER BY e.date");
            $num_ext=mysql_num_rows($mres2);
            message("Found $num_entries Log-entries for your request ($dev_str, $log_source_str, $log_level_str), $num_ext extended_log entries",1);
            $ext_logs=array();
            while ($mfr=mysql_fetch_object($mres2)) {
                if (!in_array($mfr->devicelog,array_keys($ext_logs))) $ext_logs[$mfr->devicelog]=array();
                $ext_logs[$mfr->devicelog][]=$mfr;
            }
            $num_cols=5;
            if ($multi_log_source) $num_cols++;
            if ($num_devs > 1) $num_cols++;
            $last_l_date="???";
            echo "<table class=\"normal\">\n";
            echo "<tr>";
            echo "<th class=\"num\">#</th><th class=\"del\">Del</th><th class=\"time\">Time</th>\n";
            if ($num_devs > 1) echo "<th class=\"device\">Device</th>\n";
            if ($multi_log_source) echo "<th class=\"logsource\">LogSource</th>\n";
            echo "<th class=\"loglev\">Level</th><th class=\"text\">Text</th>\n";
            echo "</tr>\n";
            mysql_data_seek($mres,$disp_start);
            $act_idx=$disp_start;
            $ext_span=$num_cols-3;
            $first=0;
            while (($mfr=mysql_fetch_object($mres)) && $disp_size) {
                $act_idx++;
                $disp_size--;
                if ($last_l_date != $mfr->l_date) {
                    $last_l_date=$mfr->l_date;
                    echo "<tr><td colspan=\"$num_cols\" class=\"date\">$last_l_date</td></tr>\n";
                }
                echo "<tr>";
                $r_span=1;
                if (in_array($mfr->devicelog_idx,array_keys($ext_logs))) {
                    $ext_count=count($ext_logs[$mfr->devicelog_idx]);
                    if ($show_ext) $r_span+=$ext_count*2;
                } else {
                    $ext_count=0;
                }
                echo "<td class=\"num\" rowspan=\"$r_span\" >$act_idx";
                if ($ext_count) echo " + $ext_count";
                echo "</td>\n";
                echo "<td class=\"del\" ><input type=checkbox name=\"dellog[]\" value=\"$mfr->devicelog_idx\"/></td>";
                echo "<td class=\"time\"><input type=radio name=\"dlta\" value=\"$mfr->devicelog_idx\" ";
                if (!$first++) echo " checked ";
                echo "/>$mfr->l_time</td>";
                if ($num_devs > 1) echo "<td class=\"device\">{$log_devices[$mfr->device]}</td>\n";
                if ($multi_log_source) {
                    $td_c="logsource";
                    //echo $mfr->log_source;
                    if ($mfr->log_source==$user_log_idx) {
                        if (in_array($mfr->user,array_keys($log_users))) {
                            $log_str="{$log_users[$mfr->user]->login} (user)";
                        } else {
                            $log_str="unknown user";
                            $td_c.="u";
                        }
                    } else {
                        if (in_array($mfr->log_source,array_keys($log_sources))) {
                            $log_str=$log_sources[$mfr->log_source]->name;
                        } else {
                            $log_str="unknown";
                            $td_c.="u";
                        }
                    }
                    echo "<td class=\"$td_c\">$log_str</td>\n";
                }
                echo "<td class=\"loglev\">{$log_status_a2[$mfr->log_status]->name} ({$log_status_a2[$mfr->log_status]->log_level})</td>\n";
                echo "<td class=\"text\">$mfr->text</td>";
                //echo "<td>$mfr->l_date</td>";
                echo "</tr>\n";
                if ($show_ext && $ext_count) {
                    foreach ($ext_logs[$mfr->devicelog_idx] as $ext_log) {
                        echo "<tr>";
                        echo "<td class=\"del\" rowspan=\"2\"><input type=checkbox name=\"delextlog[]\" value=\"$ext_log->extended_log_idx\"/></td>";
                        echo "<td class=\"time\" rowspan=\"2\">";
                        if ($ext_log->el_date != $last_l_date) echo "$ext_log->el_date, ";
                        echo "$ext_log->el_time</td>";
                        echo "<td class=\"users\" colspan=\"".strval($ext_span-1)."\">";
                        echo "Users: $ext_log->users";
                        echo "</td>";
                        echo "<td class=\"device\" colspan=\"1\">";
                        echo "Subject: $ext_log->subject";
                        echo "</td>";
                        echo "</tr>\n";
                        echo "<tr><td class=\"text\" colspan=\"$ext_span\">";
                        echo "<textarea cols=\"100\" rows=\"".min(3,count(explode("\n",trim($ext_log->description))))."\" readonly>";
                        echo $ext_log->description;
                        echo "</textarea>";
                        echo "</td>";
                        echo "</tr>\n";
                    }
                }
            }
            echo "</table>\n";
        } else {
            if (count($log_targets)) {
                message("Found no Log-entries for your request ($dev_str, $log_source_str, $log_level_str)",1);
            }
        }
        $device_groups=array();
        $devices=array();
        $mres=query("SELECT d.device_idx,d.name,dg.name AS dgname FROM device d, device_group dg WHERE d.device_group=dg.device_group_idx");
        while ($mfr=mysql_fetch_object($mres)) {
            if (!in_array($mfr->dgname,array_keys($device_groups))) $device_groups[$mfr->dgname]=array();
            $device_groups[$mfr->dgname][$mfr->name]=$mfr->device_idx;
            $devices[$mfr->name]=new device($mfr->name,$mfr->dgname,$mfr->device_idx);
        }
        ksort($device_groups);
        //print_r($device_groups);
        message("Add a new Log-Entry:",1);
        echo "<table class=\"normal\">";
        echo "<tr>";
        echo "<td class=\"time\" >New Entry: <input type=checkbox name=\"addlog\"/></td>\n";
        echo "<td class=\"device\">Device: ";
        echo "<select name=\"logdevice\">";
        echo "<option value=\"0\" >Cluster</option>\n";
        foreach ($device_groups as $dg_name => $dg_stuff) {
            echo "<option disabled>--- $dg_name (".strval(count($dg_stuff)).") devices ----</option>\n";
            foreach ($dg_stuff as $name=>$idx) {
                echo "<option value=\"$idx\" ";
                if (is_set("logdevice",&$vars)) {
                    if ($vars["logdevice"]==$idx) echo " selected ";
                } else if (count($log_dev_idx)==1 && $log_dev_idx[0]==$idx) {
                    echo " selected ";
                }
                echo " >$name</option>\n";
            }
        }
        echo "</select>\n";
        echo "</td>\n";
        echo "<td class=\"text\">Text: <input name=\"logtext\" maxlength=\"254\" size=\"60\" ";
        if (is_set("logtext",&$vars)) echo "value=\"".htmlspecialchars(un_quote($vars['logtext']))."\" ";
        echo "/></td>\n";
        echo "<td class=\"loglev\">Log level: ";
        echo "<select name=\"loglevel\">";
        foreach ($log_status as $id=>$stuff) {
            echo "<option value=\"$stuff->log_status_idx\" ";
            if (is_set("loglevel",&$vars) && $vars["loglevel"] == $stuff->log_status_idx) echo " selected ";
            echo ">{$stuff->name} ({$stuff->log_level})</option>\n";
        }
        echo "</td>\n";
        echo "</tr>\n";
        echo "<tr>";
        echo "<td class=\"time\" rowspan=\"2\">Extended Entry: <input type=checkbox name=\"extlog\"/></td>\n";
        echo "<td class=\"device\" colspan=\"1\">User (s): <input name=\"logusers\" maxlength=\"254\" size=\"80\" ";
        if (is_set("logusers",&$vars)) echo "value=\"".htmlspecialchars(un_quote($vars['logusers']))." \" ";
        echo "/></td>\n";
        echo "<td class=\"text\" colspan=\"2\">Subject: <input name=\"subject\" maxlength=\"254\" size=\"80\" ";
        if (is_set("subject",&$vars)) echo "value=\"".htmlspecialchars(un_quote($vars['subject']))." \" ";
        echo "/></td>\n";
        echo "</tr>\n";
        echo "<tr>";
        echo "<td class=\"text\" colspan=\"3\"><textarea name=\"descr\" cols=\"100\" rows=\"10\" >";
        if (is_set("descr",&$vars)) echo htmlspecialchars(un_quote($vars["descr"]));
        echo "</textarea></td></tr>\n";
        echo "</table>\n";
        echo "<div class=\"center\">";
        echo "<input type=submit value=\"submit\" /></div>\n";
        echo $hidden_stuff;
        echo "</form>\n";
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
