<?php
//-*ics*- ,CAP,name:'jsi',descr:'Jobsystem info',defvalue:1,enabled:1,scriptname:'/php/jobsysinfo.php',left_string:'Jobsysteminfo',right_string:'Information about the batchsystem',capability_group_name:'job',pri:-40
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
function my_job_cmp($j1,$j2) {
    //echo "$j1->sort_crit , $j1->id, $j2->id<br>";
    $swap=0;
    $sf=$j1->sort_crit;
    if ($j1->$sf < $j2->$sf) {
        $swap=1;
    } else if ($j1->$sf >$j2->$sf) {
        $swap=-1;
    } else {
        $swap=0;
    }
    if ($j1->sort_dir == "d" && $swap) $swap=-$swap;
    return $swap;
}
function my_job_pri_cmp($j1,$j2) {
    if ($j1->pri < $j2->pri) {
        $swap=1;
    } else if ($j1->pri > $j2->pri) {
        $swap=-1;
    } else {
        $swap=0;
    }
    return $swap;
}
function my_job_id_cmp($j1,$j2) {
    if ($j1->id < $j2->id) {
        $swap=-1;
    } else if ($j1->id > $j2->id) {
        $swap=1;
    } else {
        $swap=0;
    }
    return $swap;
}

class node {
    var $name,$queues;
    function node($name) {
        $this->name=$name;
        $this->queues=array();
    }
}
class queue {
    var $name,$state,$jobs,$host,$userlists_access,$projects_access;
    function queue($name,&$host,$state) {
        $this->name=$name;
        $this->host=&$host;
        $this->state=$state;
        $this->logs=array();
        $this->jobs=array();
        $this->userlists_access=array();
        $this->projects_access=array();
    }
    function set_userlists_access($ula) {
        $this->userlists_access=$ula;
    }
    function set_projects_access($ula) {
        $this->projects_access=$ula;
    }
    function set_slot_info($used,$total) {
        $this->slots_total=$total;
        $this->slots_used=$used;
    }
    function add_log($when,$what) {
        $this->logs[]=array($when,$what);
    }
    function show() {
        echo $this->name,$this->host->name,"X<br>";
    }
    function show_log_lines($cspan) {
        if (count($this->logs)) {
            echo "<tr><td class=\"log2\" colspan=\"$cspan\">\n";
            $num_lines=min(6,max(2,count($this->logs)+1));
            echo "<textarea cols=120 rows=$num_lines wrap=\"off\" class=\"log\" readonly>";
            foreach ($this->logs as $lline) {
                list($when,$what)=$lline;
                echo "$when :: $what\n";
            }
            echo "</textarea>\n";
            echo "</td></tr>\n";
        }
    }
    function add_job($job) {
        $this->jobs[]=$job;
    }
    function is_unknown() { return preg_match("/u/",$this->state); }
    function is_load_alarm() { return preg_match("/a/",$this->state); }
    function is_suspend_alarm() { return preg_match("/A/",$this->state); }
    function is_disabled() { return preg_match("/d/",$this->state); }
    function is_suspended() { return preg_match("/s/",$this->state); }
    function is_calendar_disabled() { return preg_match("/D/",$this->state); }
    function is_calendar_suspended() { return preg_match("/C/",$this->state); }
    function is_subordinate() { return preg_match("/S/",$this->state); }
    function is_error() { return preg_match("/E/",$this->state); }
}
class complex {
    var $name,$pe_list,$max_walltime,$max_n_walltime,$max_nodes;
    var $waiting,$running,$nodes_total,$nodes_up,$nodes_available,$nodes_error,$node_list;
    function complex($name) {
        $this->name=$name;
        $this->pe_list=array();
        $this->max_walltime="00:00:00";
        $this->max_n_walltime="00:00:00";
        $this->max_nodes=0;
        $this->waiting=0;
        $this->running=0;
        $this->nodes_total=0;
        $this->nodes_up=0;
        $this->nodes_available=0;
        $this->nodes_error=0;
        $this->node_list="";
    }
}
function sec_to_str($sec) {
    $rsec=$sec;
    $time_o=array();
    foreach (array(3600*24,3600,60,1) as $div) {
        $act=(int)($rsec/$div);
        $rsec-=$act*$div;
        if ($act || !count($time_o)) {
            if (count($time_o)) {
                $time_o[]=sprintf("%02d",$act);
            } else {
                $time_o[]=sprintf("%d",$act);
            }
        }
    }
    return implode(":",$time_o);
}
function str_to_sec($str) {
    $str_parts=array_reverse(explode(":",$str));
    $mults=array(1,60,3600,3600*24);
    $secs=0;
    for ($idx=0;$idx<count($str_parts);$idx++) $secs+=(int)$str_parts[$idx]*$mults[$idx];
    return $secs;
}

class user {
    var $name,$fair_share;
    function user($name) {
        $this->name=$name;
        $this->fair_share=0.0;
    }
}

class job {
    var $id,$state,$ehost,$pe_info,$slots,$user,$name,$time,$c_list,$q_list;
    var $pri,$qtime,$depend,$load_avg;
    var $pri_cred_class,$pri_fs_user,$pri_serv_qtime,$pri_serv_xfctr,$pri_serv_bypass;
    var $logs;
    function job($id,$state,$ehost,$pe_info,$user,$name,$time,$c_list,$q_list) {
        $this->id=$id;
        $this->state=$state;
        $this->host=$ehost;
        $this->pe_info=$pe_info;
        preg_match("/^\S+\((\d+)\)$/",$this->pe_info,$pe_match) ;
        if ($pe_match) {
            $this->slots=(int)$pe_match[1];
        } else {
            $this->slots=(int)$this->pe_info;
        }
        $this->user=$user;
        $this->name=$name;
        $this->time=$time;
        if ($c_list) {
            $this->c_list=explode(",",$c_list);
        } else {
            $this->c_list=array("---");
        }
        if ($q_list) {
            $this->q_list=explode(",",$q_list);
        } else {
            $this->q_list=array("---");
        }
        $this->pri=0;
        $this->depend=array();
        $this->pri_cred_class=0.;
        $this->time_run=0.;
        $this->time_left=0.;
        $this->pri_fs_user=0.;
        $this->pri_serv_qtime=0.;
        $this->pri_serv_xfctr=0.;
        $this->pri_serv_bypass=0.;
        $this->sort_crit="";
        $this->sort_dir="";
        $this->logs=array();
        //echo strval($this->user->fair_share)."<br>";
    }
    function add_log($when,$what) {
        $this->logs[]=array($when,$what);
    }
    function get_log_lines() {
        return "<td class=\"log\">".count($this->logs)."</td>\n";
    }
    function show_log_lines($cspan) {
        if (count($this->logs)) {
            echo "<tr><td class=\"log2\" colspan=\"$cspan\">\n";
            $num_lines=min(6,max(2,count($this->logs)+1));
            echo "<textarea cols=120 rows=$num_lines wrap=\"off\" class=\"log\" readonly>";
            foreach ($this->logs as $lline) {
                list($when,$what)=$lline;
                echo "$when :: $what\n";
            }
            echo "</textarea>\n";
            echo "</td></tr>\n";
        }
    }
    function set_pri($pri) {
        $this->pri=$pri;
    }
    function get_pri() {
        return "<td class=\"pri\">$this->pri</td>\n";
    }
    function set_load_avg($load_avg) {
        $this->load_avg=$load_avg;
    }
    function set_times($time_r,$time_el) {
        $this->time_run=str_to_sec($time_r);
        $this->time_left=str_to_sec($time_el);
    }
    function is_running() { return preg_match("/r/",$this->state) ;}
    function is_waiting() { return preg_match("/w/",$this->state) ;}
    function is_deleted() { return preg_match("/d/",$this->state) ;}
    function is_hold() { return preg_match("/h/",$this->state) ;}
    function is_restarted() { return preg_match("/R/",$this->state) ;}
    function is_transfering() { return preg_match("/t/",$this->state) ;}
    function is_suspended() { return preg_match("/s/",$this->state) ;}
    function is_queue_suspended() { return preg_match("/S/",$this->state) ;}
    function is_threshold_suspended() { return preg_match("/T/",$this->state) ;}
    function is_error() { return preg_match("/E/",$this->state);}
    function get_name() { return "<td class=\"jobs\">$this->name</td>"; }
    function get_mean_load() { return "<td class=\"meanload\">$this->load_avg</td>"; }
    function get_user() { return "<td class=\"user\">$this->user</td>"; }
    function get_host() { return "<td class=\"exhost\">".implode(", ",$this->host)."</td>"; }
    function get_pe_info() { return "<td class=\"excpu\">$this->pe_info</td>"; }
    function get_id() { return "<td class=\"id\">$this->id</td>"; }
    function get_left_img() {
        echo "<td class=\"time\">";
        if ($this->time_run+$this->time_left) {
            $prec=sprintf("%.2f",$this->time_run/($this->time_run+$this->time_left)*100);
            $diff_len=5-strlen($prec);
            for ($i=0;$i<$diff_len;$i++) {
                $prec="&nbsp;$prec";
            }
        } else {
            $prec=0;
        }
        echo "$prec %";
        if ($GLOBALS["ENABLE_TGRAPH"]) {
            echo " <img src=\"jsi_png.php?x=140&y=16&perc=$prec\" />";
        }
        echo "</td>\n";
    }
    function get_state() {
        echo "<td class=\"state\">$this->state</td>\n";
    }
    function get_time() { return "<td class=\"qtime\">$this->time</td>";}
    function get_time_run() { return "<td class=\"time\">".sec_to_str($this->time_run)."</td>"; }
    function get_time_left() { return "<td class=\"time\">".sec_to_str($this->time_left)."</td>"; }
    function get_complex() { return "<td class=\"complex\">".implode(",",$this->c_list)."</td>"; }
    function get_queue() { return "<td class=\"queue\">".implode(",",$this->q_list)."</td>"; }
    function get_qtime() { return "<td class=\"qtime\">$this->qtime</td>"; }
    function get_depend($jl) {
        $rstr="<td class=\"pri\">";
        if ($this->depend) {
            $rstr.="<table class=\"blind2\">";
            foreach ($this->depend as $dip) {
                $rstr.="<tr><td class=\"center\">$dip";
                $ajob=$jl[$dip];
                if ($ajob->id==$dip) $rstr.=" ; $ajob->name ( user $ajob->user )";
                $rstr.="</td></tr>";
            }
            $rstr.="</table>\n";
        } else {
            $rstr.="---";
        }
        $rstr.="</td>\n";
        return $rstr;
    }
}
require_once "config.php";
require_once "mysql.php";
require_once "tools.php";
require_once "htmltools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["jsi_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    // maximum number of jobs to display
    $MAX_JOBS=10000;
    $ENABLE_TGRAPH=1;
    htmlhead();
    clusterhead($sys_config,"Batch system information page",$style="formate.css",
                array("th.slots"=>array("background-color:#dffeff","text-align:center"),
                      "td.slots"=>array("background-color:#ceedee","text-align:center"),
                      "th.qu"=>array("background-color:#fff0f0","text-align:center"),
                      "td.qu"=>array("background-color:#eedddd","text-align:center"),
                      "th.info"=>array("background-color:#f0fff0","text-align:center"),
                      "td.info"=>array("background-color:#ddeedd","text-align:left"),
                      "th.problem"=>array("background-color:#ffcccc","text-align:center"),
                      "td.problemok"=>array("background-color:#99ff99","text-align:center"),
                      "td.problemwarn"=>array("background-color:#ffff00","text-align:left"),
                      "td.problemerror"=>array("background-color:#ff8888","text-align:left"),
                      "th.pri"=>array("background-color:#ffeeee","text-align:center"),
                      "td.pri"=>array("background-color:#eedeee","text-align:center"),
                      "th.time"=>array("background-color:#effeff","text-align:center"),
                      "td.time"=>array("background-color:#deedee","text-align:center","font-family:monospace","char:'%'"),
                      "th.qtime"=>array("background-color:#effeff","text-align:center"),
                      "td.qtime"=>array("background-color:#deedee","text-align:center","font-family:monospace"),
                      "th.excpu"=>array("background-color:#eeeeff","text-align:center"),
                      "td.excpu"=>array("background-color:#ccccee","text-align:center"),
                      "th.exhost"=>array("background-color:#eeeeff","text-align:center"),
                      "td.exhost"=>array("background-color:#ccccee","text-align:center"),
                      "th.jobh"=>array("background-color:#ffeeff","text-align:center"),
                      "td.jobn"=>array("background-color:#eeddee","text-align:center"),
                      "td.jobs"=>array("background-color:#eeccee","text-align:center"),
                      "th.qnum"=>array("background-color:#eeeeff","text-align:center"),
                      "td.qnum"=>array("background-color:#ccccee","text-align:center"),
                      "th.usera"=>array("background-color:#eef4f4","text-align:center"),
                      "td.usera"=>array("background-color:#ddeeee","text-align:center"),
                      "th.projecta"=>array("background-color:#f4eef4","text-align:center"),
                      "td.projecta"=>array("background-color:#eeddee","text-align:center"),
                      "th.state"=>array("background-color:#eeeeff","text-align:center"),
                      "td.state"=>array("background-color:#ccccee","text-align:center"),
                      "th.qtot"=>array("background-color:#f0f0f8","text-align:center"),
                      "td.qtot"=>array("background-color:#e0e0f7","text-align:center"),
                      "th.qucs"=>array("background-color:#ddddff","text-align:center"),
                      "td.qucs"=>array("background-color:#ccccee","text-align:center"),
                      "th.quwt"=>array("background-color:#eeeeee","text-align:center"),
                      "td.quwt"=>array("background-color:#cccccc","text-align:center"),
                      "th.qummc"=>array("background-color:#ddffff","text-align:center"),
                      "td.qummc"=>array("background-color:#bbdddd","text-align:center"),
                      "th.complex"=>array("background-color:#ddffdd","text-align:center"),
                      "td.complex"=>array("background-color:#ccddcc","text-align:center"),
                      "th.queue"=>array("background-color:#eeffbb","text-align:center"),
                      "td.queue"=>array("background-color:#ddddaa","text-align:center"),
                      "th.meanload"=>array("background-color:#eeffee","text-align:center"),
                      "td.meanload"=>array("background-color:#cceecc","text-align:center"),
                      "th.id"=>array("color:#000000","background-color:#ffffff","text-align:center"),
                      "td.id"=>array("color:#000000","background-color:#eeeeee","text-align:center"),
                      "th.log"=>array("color:#000000","background-color:#fddf8f","text-align:center"),
                      "td.log"=>array("color:#000000","background-color:#ecce6e","text-align:center"),
                      "td.log2"=>array("color:#000000","background-color:#fcde9e","text-align:left"),
                      "th.user"=>array("color:#000000","background-color:#ffffff","text-align:center"),
                      "td.user"=>array("color:#000000","background-color:#eeffee","text-align:left"),
                      "textarea.log"=>array("color:#000000","background-color:#ffffff","font-family:sans-serif")
                      ));
    clusterbody($sys_config,"Batch system info",array(),array("job"));
    $ucl=usercaps($sys_db_con);
    if ($ucl["jsi"]) {
        $rslist=array("ji"=>array("JobID"          ,"id"       ),
                      "un"=>array("UserName"       ,"user"     ),
                      "sl"=>array("number of nodes","slots"    ),
                      "jn"=>array("JobName"        ,"name"     ),
                      "te"=>array("Time elapsed"   ,"time_run" ),
                      "tl"=>array("Time left"      ,"time_left"),
                      "pr"=>array("Priority"       ,"pri"  ));
        $sup_array=array("eaj"=>array("expand Array-jobs"  ,0),
                         "sjl"=>array("show logs"          ,0),
                         "sql"=>array("show queuelist"     ,0),
                         "sal"=>array("show accesslists"   ,0),
                         "sdp"=>array("show problemdetails",0));
        if (isset($vars["sal"])) $vars["sql"]=1;
        $sup_ref_str="";
        foreach ($sup_array as $short=>$stuff) {
            list($long,$set)=$stuff;
            if (isset($vars["$short"])) {
                $sup_ref_str.="&$short=on";
            }
        }
        if (is_set("sa",&$vars)) {
            $rstype=$vars["sa"];
        } else {
            $rstype="ji";
        }
        $hidden_sort_par="<input type=hidden name=\"sa\" value=\"$rstype\"/>\n";
        if (is_set("desc_sort",&$vars)) {
            $sort_dir="descending";
        } else {
            $sort_dir="ascending";
        }
        if ($sort_dir=="ascending") {
            $hidden_sort_dir="<input type=hidden name=\"asc_sort\" value=\"{$rstype}\" />\n";
        } else {
            $hidden_sort_dir="<input type=hidden name=\"desc_sort\" value=\"{$rstype}\" />\n";
        }
        //print_r($vars);
        //echo "*$rstype*$sort_dir*<br>";
        $rsstr="{$rslist[$rstype][0]}, $sort_dir";
        $sort_field=$rslist[$rstype][1];
# get all nodes
        $mrs=query("SELECT d.name FROM device d INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device_group dg INNER JOIN device_type dt LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE dg.device_group_idx=d.device_group AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND dc.new_config=c.new_config_idx AND c.name LIKE('sge_client%') AND dt.identifier='H' AND dt.device_type_idx=d.device_type");
        $node_list=array();
        $queue_list=array();
        while ($mfr=mysql_fetch_object($mrs)) {
            $node_list[$mfr->name]=new node($mfr->name);
        }
        $sge_root=file("/etc/sge_root");
        $sge_root=trim($sge_root[0]);
        $sge_arch=call_pure_external("$sge_root/util/arch");
        if (isset($vars["sal"])) {
            $stat_com="$sge_root/bin/noarch/sgestat.py -r -R cnj -a";
        } else {
            $stat_com="$sge_root/bin/noarch/sgestat.py -r -R cnj";
        }
        $sge_stuff=call_pure_external($stat_com);
        //foreach ($sge_stuff as $line) echo ":: $line<br>";
        $act_mode="?";
        $act_line_num=0;
        $complexes=array();
        $jobs=array();
        $host_info_f=array();
        $queue_info_f=array();
        $job_info_f=array();
        $all_job_nums=array();
        $job_ref_array=array();
        foreach ($sge_stuff as $sge_line) {
            if ($sge_line[0] == ":") {
                preg_match("/^:run-mode\s+(.)\s+.*$/",$sge_line,$sge_p);
                $act_mode=$sge_p[1];
                $act_line_num=0;
            } else {
                $sge_split=explode(";",$sge_line);
                if ($act_line_num) {
                    if ($act_mode == "c") {
                        $c_name=$sge_split[0];
                        $complexes[$c_name]=new complex($c_name);
                        $new_c=&$complexes[$c_name];
                        $new_c->pe_list=explode(",",$sge_split[1]);
                        $new_c->max_nodes=$sge_split[3];
                        $new_c->max_walltime=$sge_split[4];
                        $new_c->max_n_walltime=$sge_split[5];
                        $new_c->waiting=(int)$sge_split[6];
                        $new_c->running=(int)$sge_split[7];
                        $new_c->nodes_total=(int)$sge_split[8];
                        $new_c->nodes_up=(int)$sge_split[9];
                        $new_c->nodes_available=(int)$sge_split[10];
                        $new_c->nodes_error=(int)$sge_split[12];
                        $new_c->node_list=$sge_split[13];
                    } else if ($act_mode == "j") {
                        if ($sge_split[0] != "Id") {
                            $job_num=$sge_split[0];
                            $all_job_nums[]=$job_num;
                            if ($sge_split[1]) {
                                if (preg_match("/^\d+$/",$sge_split[1])) {
                                    $r_job_ids=array("{$job_num}.{$sge_split[1]}");
                                } else if (preg_match("/^(\d+),(\d+)$/",$sge_split[1],$ajis)) {
                                    $r_job_ids=array("{$job_num}.{$ajis[1]}","{$job_num}.{$ajis[2]}");
                                } else if (preg_match("/^(\d+)-(\d+):(\d+)$/",$sge_split[1],$ajis)) {
                                    $r_job_ids=array();
                                    for ($idx=$ajis[1];$idx<=$ajis[2];$idx+=$ajis[3]) {
                                        $r_job_ids[]="{$job_num}.$idx";
                                    }
                                }
                                if (isset($vars["eaj"])) {
                                    $job_ids=$r_job_ids;
                                    foreach ($r_job_ids as $rji) $job_ref_array[$rji]=$rji;
                                } else {
                                    $job_ids=array("{$job_num}.{$sge_split[1]}");
                                    //echo "*";
                                    //print_r($r_job_ids);
                                    //foreach ($r_job_ids as $rji) $job_ref_array[$rji]="{$job_num}.{$sge_split[1]}";
                                }
                            } else {
                                $job_ids=array($job_num);
                                $job_ref_array[$job_num]=$job_num;
                            }
                            foreach ($job_ids as $job_id) {
                                $job_name=$sge_split[2];
                                $num_slots=$sge_split[3];
                                $user=$sge_split[4];
                                $job_stat=$sge_split[5];
                                $qr_time=$sge_split[8];
                                $new_job=new job($job_id,$job_stat,explode(",",$sge_split[12]),$num_slots,$user,$job_name,$qr_time,$sge_split[6],$sge_split[7]);
                                $new_job->sort_crit=$sort_field;
                                $new_job->sort_dir=substr($sort_dir,0,1);
                                if ($new_job->is_running()) {
                                    $new_job->set_load_avg($sge_split[11]);
                                    $new_job->set_times($sge_split[9],$sge_split[10]);
                                } else if ($new_job->is_waiting()) {
                                    if ($sge_split[12]) $new_job->depend=explode(",",$sge_split[12]);
                                    $new_job->set_pri((float)$sge_split[11]);
                                }
                                $jobs[$job_id]=$new_job;
                                unset($new_job);
                            }
                        }
                    } else if ($act_mode == "n") {
                        //preg_match("/^(.*)$/",$sge_split[1],$nn_p);
                        $queue_name=$sge_split[0];
                        $node_name=$sge_split[1];
                        if (in_array($node_name,array_keys($node_list))) {
                            $new_queue=new queue($queue_name,$node_list[$node_name],$sge_split[2]);
                            $new_queue->set_slot_info((int)$sge_split[4],(int)$sge_split[5]);
                            if (isset($vars["sal"])) {
                                foreach (explode(",",$sge_split[9]) as $njob) $new_queue->add_job($njob);
                                $new_queue->set_userlists_access($sge_split[7]);
                                $new_queue->set_projects_access($sge_split[8]);
                            } else {
                                foreach (explode(",",$sge_split[7]) as $njob) $new_queue->add_job($njob);
                            }
                            $queue_list[$queue_name]=$new_queue;
                        } else {
                            $host_info_f[]="host $node_name is unknown";
                            $queue_info_f[]="queue $queue_name (on host $node_name) is unknown";
                        }
                    }
                }
                $act_line_num++;
            }
        }
        $sel_str_a=array();
        foreach (array_keys($job_ref_array) as $jra) $sel_str_a[]="j.job_uid='$jra'";
        if (count($sel_str_a)) {
            $mres=query("SELECT j.*,jl.*,DATE_FORMAT(jl.date,'%e. %b %Y, %H:%i:%s') AS twhen FROM sge_job j, sge_job_log jl WHERE jl.sge_job=j.sge_job_idx AND (".implode(" OR ",$sel_str_a).") ORDER BY jl.date DESC, jl.sge_job_log_idx DESC");
            while ($mfr=mysql_fetch_object($mres)) {
                $r_job_id=$job_ref_array[$mfr->job_uid];
                $jobs[$r_job_id]->add_log($mfr->twhen,$mfr->log_str);
            }
        }
        function get_total_slots($ts,$qo) { return $ts+$qo->slots_total; }
        function get_used_slots($ts,$qo) { return $ts+$qo->slots_used; }
        function get_free_slots($ts,$qo) { return $ts+$qo->slots_total-$qo->slots_used; }
        uasort($jobs,"my_job_cmp");
        message("RMS Overview:");
        echo "<table class=\"normalnf\">";
        echo "<tr><th class=\"name\">Type</th><th class=\"qu\">total</th><th class=\"qu\">used/run</th><th class=\"qu\">free/wait</th>";
        echo "<th class=\"problem\">Problems</th><th class=\"info\">Info</th>\n";
        echo "</tr>\n";
        echo "<tr><td class=\"name\">Hosts</td>\n";
        echo "<td class=\"qu\">".count(array_keys($node_list))."</td>\n";
        echo "<td class=\"qu\">-</td>\n";
        echo "<td class=\"qu\">-</td>\n";
        echo "<td class=\"problemok\">-</td>\n";
        echo "<td class=\"info\">";
        if (count($host_info_f)) {
            echo implode(", ",$host_info_f);
        } else {
            echo "---";
        }
        echo "</td>\n";
        echo "</tr>\n";
        echo "<tr><td class=\"name\">Queues</td>";
        echo "<td class=\"qu\">".sprintf("%d (%s)",count(array_keys($queue_list)),get_plural("slot",array_reduce($queue_list,"get_total_slots",0),1))."</td>";
        echo "<td class=\"qu\">".get_plural("slot",array_reduce($queue_list,"get_used_slots",0),1)."</td>";
        echo "<td class=\"qu\">".get_plural("slot",array_reduce($queue_list,"get_free_slots",0),1)."</td>";
        // generate problem-string
        $act_p_level=0;
        $out_f=array();
        $n_prob_f=array();
        $q_prob_f=array();
        $q_prob_f2=array();
        $lev_str_dict=array(0=>"ok",
                            1=>"warn",
                            2=>"error");
        foreach (array(array("unknown"           ,"is_unknown"           ,2),
                       array("load_alarm"        ,"is_load_alarm"        ,1),
                       array("suspend_alarm"     ,"is_suspend_alarm"     ,1),
                       array("disabled"          ,"is_disabled"          ,1),
                       array("suspended"         ,"is_suspended"         ,1),
                       array("calendar_disabled" ,"is_calendar_disabled" ,1),
                       array("calendar_suspended","is_calendar_suspended",1),
                       array("subordinate"       ,"is_subordinate"       ,1),
                       array("error"             ,"is_error"             ,2)) as $c_stuff) {
            list($out_str,$c_func,$p_level)=$c_stuff;
            $act_q_f=array();
            $act_h_f=array();
            $act_num=0;
            foreach ($queue_list as $q_name=>$q_obj) {
                $h_name=$q_obj->host->name;
                if ($q_obj->$c_func()) {
                    $act_num+=$q_obj->slots_total;
                    $act_q_f[]=$q_name;
                    if (!in_array($q_name,array_keys($q_prob_f2))) $q_prob_f2[$q_name]=array("probs"=>array(),"level"=>0);
                    $q_prob_f2[$q_name]["probs"][]=$out_str;
                    $q_prob_f2[$q_name]["level"]=max($p_level,$q_prob_f2[$q_name]["level"]);
                    if (!in_array($h_name,$act_h_f)) $act_h_f[]=$h_name;
                }
            }
            if ($act_num) {
                $out_f[]="$out_str: $act_num";
                $q_prob_f[$out_str]=$act_q_f;
                $n_prob_f[$out_str]=$act_h_f;
                $act_p_level=max($act_p_level,$p_level);
            }
        }
        if (!count($out_f)) $out_f[]="-";
        echo "<td class=\"problem{$lev_str_dict[$act_p_level]}\">".implode(", ",$out_f)."</td>\n";
        echo "<td class=\"info\">";
        if (count($queue_info_f)) {
            echo implode(", ",$queue_info_f);
        } else {
            echo "---";
        }
        echo "</td>\n";
        echo "</tr>\n";
        echo "<tr><td class=\"name\">Jobs</td>\n";
        echo "<td class=\"qu\">".strval(count($jobs))."</td>\n";
        $num_jobs_running=0;
        $num_slots_running=0;
        $num_jobs_waiting=0;
        $num_slots_waiting=0;
        $num_jobs_hold=0;
        $num_slots_hold=0;
        foreach ($jobs as $job_id=>$j_obj) {
            if ($j_obj->is_running() || $j_obj->is_transfering()) {
                $num_jobs_running++;
                $num_slots_running+=$j_obj->slots;
            }
            if ($j_obj->is_waiting() && !$j_obj->is_hold()) {
                $num_jobs_waiting++;
                $num_slots_waiting+=$j_obj->slots;
            }
            if ($j_obj->is_hold()) {
                $num_jobs_hold++;
                $num_slots_hold+=$j_obj->slots;
            }
        }
        if ($num_jobs_hold) {
            $job_info_f[]="$num_jobs_hold ($num_slots_hold slots) hold";
        }
        echo "<td class=\"qu\">$num_jobs_running ($num_slots_running slots)</td>\n";
        echo "<td class=\"qu\">$num_jobs_waiting ($num_slots_waiting slots)";
        echo "</td>\n";
        $j_prob_f=array();
        $j_prob_f2=array();
        $out_f=array();
        $act_p_level=0;
        foreach (array(array("error  "            ,"is_error"              ,2),
                       array("deleted"            ,"is_deleted"            ,1),
                       array("restarted"          ,"is_restarted"          ,1),
                       array("transfering"        ,"is_transfering"        ,1),
                       array("suspended"          ,"is_suspended"          ,1),
                       array("queue_suspended"    ,"is_queue_suspended"    ,1),
                       array("threshold_suspended","is_threshold_suspended",1)) as $c_stuff) {
            list($out_str,$c_func,$p_level)=$c_stuff;
            $act_num=0;
            $act_j_f=array();
            foreach ($jobs as $j_id=>$j_obj) {
                if ($j_obj->$c_func()) {
                    $act_num++;
                    $act_j_f[]=$j_id;
                    if (!in_array($j_id,array_keys($j_prob_f2))) $j_prob_f2[$j_id]=array("probs"=>array(),"level"=>0);
                    $j_prob_f2[$j_id]["probs"][]=$out_str;
                    $j_prob_f2[$j_id]["level"]=max($p_level,$j_prob_f2[$j_id]["level"]);
                }
            }
            if ($act_num) {
                $out_f[]="$out_str: $act_num";
                $q_prob_f[$out_str]=$act_j_f;
                $act_p_level=max($act_p_level,$p_level);
            }
        }
        if (!count($out_f)) $out_f[]="-";
        echo "<td class=\"problem{$lev_str_dict[$act_p_level]}\">".implode(", ",$out_f)."</td>\n";
        echo "<td class=\"info\">";
        if ($job_info_f) {
            echo implode(", ",$job_info_f);
        } else {
            echo "---";
        } 
        echo "</td>\n";
        echo "</tr>\n";
        echo "</table>\n";
        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
        echo $hidden_sort_dir;
        echo $hidden_sort_par;
        echo "<table class=\"simplesmall\" >";
        echo "<tr><td>Options:</td>";
        foreach ($sup_array as $short=>$stuff) {
            list($long,$set)=$stuff;
            echo "<td>$long <input type=checkbox name=\"$short\" ".(isset($vars[$short]) ? " checked " : "")." />,</td>\n";
        }
        echo "<td><input type=submit value=\"select\"/></td></tr>";
        echo "</table>\n";
        echo "</form>\n";

        $prob_queues=count($q_prob_f2);
        $prob_jobs=count($j_prob_f2);
        if ($prob_queues+$prob_jobs) {
            if (isset($vars["sdp"])) {
                $prob_f=array();
                if ($prob_queues) $prob_f[]=get_plural("Problem queue",$prob_queues,1);
                if ($prob_jobs) $prob_f[]=get_plural("Problem job",$prob_jobs,1);
                message(implode(" and ",$prob_f).":");
                echo "<table class=\"normalnf\">";
                echo "<tr><th class=\"info\">Objecttype</th><th class=\"name\">Objectname</th><th class=\"qu\">&nbsp;#&nbsp;</th><th class=\"problem\">Problems</th></tr>\n";
                foreach ($q_prob_f2 as $q_name=>$q_probs) {
                    echo "<tr><td class=\"info\">Queue</td><td class=\"name\">$q_name (".get_plural("slot",$queue_list[$q_name]->slots_total,1).")</td>\n";
                    echo "<td class=\"qu\">".strval(count($q_probs["probs"]))."</td>\n";
                    echo "<td class=\"problem{$lev_str_dict[$q_probs['level']]}\">".implode(", ",$q_probs["probs"])."</td>\n";
                    echo "</tr>\n";
                }
                foreach ($j_prob_f2 as $j_id=>$j_probs) {
                    echo "<tr><td class=\"info\">Job</td><td class=\"name\">$j_id</td>\n";
                    echo "<td class=\"qu\">".strval(count($j_probs["probs"]))."</td>\n";
                    echo "<td class=\"problem{$lev_str_dict[$j_probs['level']]}\">".implode(", ",$j_probs["probs"])."</td>\n";
                    echo "</tr>\n";
                }
                echo "</table>\n";
            }
        }
        $no_f=array();
        if ($num_jobs_running) {
            message("Table of running jobs (sorted by $rsstr)");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."$sup_ref_str\" method=post>";
            echo $hidden_sort_dir;
            echo "<table class=\"normal\">\n";
            echo "<tr>";
            foreach (array(array(1,"user","User","un",1),array(1,"id","JobID","ji",1),array(0,"state","State","",1),array(0,"log","Log","",1),array(1,"jobh","JobName","jn",1),array(0,"exhost","Queue(s)","",1),
                           array(1,"excpu","Slots","sl",1),array(1,"time","Time el.","te",1),array(1,"time","Time left","tl",1),
                           array(0,"time","tgraph","",1),array(0,"complex","Complex","",1),array(0,"queue","Queue","",1),array(0,"meanload","mean Load (efficiency)","",1)) as $stuff) {
                list($is_button,$class,$but_name,$sort,$cspan)=$stuff;
                echo "<th class=\"$class\" colspan=\"$cspan\">";
                if ($is_button) {
                    echo "<a href=\"{$sys_config['script_name']}?".write_sid()."&sa=$sort$sup_ref_str";
                    if ($rstype == $sort && $sort_dir=="ascending") echo "&desc_sort=1";
                    echo "\">$but_name</a>";
                } else {
                    echo "$but_name";
                }
                echo "</th>\n";
            }
            echo "</tr>\n";
            foreach ($jobs as $j_id=>$jr) {
                if ($jr->is_running() || $jr->is_transfering()) {
                    echo "<tr>";
                    echo $jr->get_user(),$jr->get_id(),$jr->get_state(),$jr->get_log_lines(),$jr->get_name(),$jr->get_host(),$jr->get_pe_info();
                    echo $jr->get_time_run(),$jr->get_time_left();
                    echo $jr->get_left_img();
                    echo $jr->get_complex(),$jr->get_queue(),$jr->get_mean_load();
                    echo "</tr>\n";
                    if (isset($vars["sjl"])) {
                        $jr->show_log_lines(13);
                    }
                }
            } 
            echo "</table></form>\n";
        } else {
            $no_f[]="jobs running";
        }
        uasort($jobs,"my_job_pri_cmp");
        if ($num_jobs_waiting) {
            message ("Table of waiting jobs");
            echo "<table class=\"normal\">\n";
            echo "<tr><th class=\"user\">User</th><th class=\"id\">ID</th><th class=\"log\">Log</th>\n";
            //foreach (array("Pri","Cred","FS","QTime","XFctr","Bypass") as $header) {
            //    echo "<th class=\"pri\">$header</th>\n";
            //}
            echo "<th class=\"jobh\">Jobname</th><th class=\"state\">State</th><th class=\"pri\">Priority</th><th class=\"slots\">req. slots</th><th class=\"complex\">Complex</th><th class=\"queue\">Queue</th>\n";
            echo "<th class=\"qtime\">qtime</th></tr>\n";
            foreach ($jobs as $j_id=>$jr) {
                if ($jr->is_waiting() && !$jr->is_hold()) {
                    echo "<tr>";
                    echo $jr->get_user(),$jr->get_id(),$jr->get_log_lines(),$jr->get_name(),$jr->get_state(),$jr->get_pri();
                    echo $jr->get_pe_info(),$jr->get_complex(),$jr->get_queue(),$jr->get_time();
                    echo "</tr>\n";
                    if (isset($vars["sjl"])) {
                        $jr->show_log_lines(10);
                    }
                }
            } 
            echo "</table>\n";
        } else {
            $no_f[]="jobs waiting";
        }
        if ($num_jobs_hold) {
            message ("Table of hold jobs");
            echo "<table class=\"normal\">\n";
            echo "<tr><th class=\"user\">User</th><th class=\"id\">ID</th><th class=\"log\">Log</th><th class=\"jobh\">Jobname</th>\n";
            echo "<th class=\"slots\">req. slots</th><th class=\"qu\">Complex</th><th class=\"qu\">Queue</th><th class=\"pri\">Depends on</th></tr>\n";
            foreach ($jobs as $j_id=>$jr) {
                if ($jr->is_hold()) {
                    echo "<tr>";
                    echo $jr->get_user(),$jr->get_id(),$jr->get_log_lines(),$jr->get_name();
                    echo $jr->get_pe_info(),$jr->get_complex(),$jr->get_queue(),$jr->get_depend($jobs);
                    echo "</tr>\n";
                    if (isset($vars["sjl"])) {
                        $jr->show_log_lines(8);
                    }
                }
            } 
            echo "</table>\n";
        } else {
            $no_f[]="jobs held";
        }
        if ($complexes) {
            message("Complex configuration");
            echo "<table class=\"normal\">\n";
            echo "<tr>";
            echo "<th class=\"qu\">Name</th>";
            echo "<th class=\"id\">PE-List</th>";
            echo "<th class=\"qummc\">Max. cpus</th>";
            echo "<th class=\"quwt\">Max. walltime</th>";
            echo "<th class=\"quwt\">Max. walltime/node</th>";
            echo "<th class=\"qucs\">W</th>";
            echo "<th class=\"id\">R</th>";
            echo "<th class=\"qu\"># of nodes</th>";
            echo "<th class=\"qu\">Nodes up</th>";
            echo "<th class=\"qu\">Free nodes</th>";
            echo "<th class=\"qu\">Error nodes</th>";
            echo "<th class=\"qu\">Queues</th>";
            echo "</tr>\n";
            foreach (array_keys($complexes) as $cn) {
                $cu=&$complexes[$cn];
                echo "<tr>";
                echo "<td class=\"qu\">$cn</td>";
                echo "<td class=\"id\">".implode(", ",$cu->pe_list)."</td>";
                echo "<td class=\"qummc\">$cu->max_nodes</td>";
                echo "<td class=\"quwt\">$cu->max_walltime</td>";
                echo "<td class=\"quwt\">$cu->max_n_walltime</td>";
                echo "<td class=\"qucs\">".strval($cu->waiting)."</td>";
                echo "<td class=\"id\">".strval($cu->running)."</td>";
                echo "<td class=\"qu\">$cu->nodes_total</td>\n";
                echo "<td class=\"qu\">$cu->nodes_up</td>\n";
                echo "<td class=\"qu\">$cu->nodes_available</td>\n";
                echo "<td class=\"qu\">$cu->nodes_error</td>\n";
                echo "<td class=\"qu\">$cu->node_list</td>\n";
                echo "</tr>\n";
            }
            echo "</table>\n";
        } else {
            $no_f[]="complexes found";
        }
        if (isset($vars["sql"])) {
            if (count($queue_list)) {
                message(get_plural("Queue",count($queue_list),1)." defined");
                $q_names=array_keys($queue_list);
                sort($q_names);
                $sql_f=array();
                foreach ($q_names as $q_name) $sql_f[]="s.queue_name='$q_name'";
                $mres=query("SELECT s.*,sl.*,DATE_FORMAT(sl.date,'%e. %b %Y, %H:%i:%s') AS twhen FROM sge_queue s LEFT JOIN sge_queue_log sl ON sl.sge_queue=s.sge_queue_idx WHERE (".implode(" OR ",$sql_f).") ORDER BY sl.date DESC, sl.sge_queue_log_idx DESC");
                while ($mfr=mysql_fetch_object($mres)) {
                    if ($mfr->log_str) {
                        $queue_list[$mfr->queue_name]->add_log($mfr->twhen,$mfr->log_str);
                    }
                }
                echo "<table class=\"normal\">\n";
                echo "<tr>";
                echo "<th class=\"user\">Name</th><th class=\"log\">Log</th><th class=\"state\">State</th>";
                if (isset($vars["sal"])) {
                    echo "<th class=\"usera\">UserLists</th><th class=\"projecta\">Projects</th>";
                }
                echo "</tr>\n";
                foreach ($q_names as $q_name) {
                    $act_q=$queue_list[$q_name];
                    echo "<tr><td class=\"user\">$q_name (on host {$act_q->host->name})</td>\n";
                    echo "<td class=\"log\">".strval(count($act_q->logs))."</td>\n";
                    echo "<td class=\"state\">$act_q->state</td>";
                    if (isset($vars["sal"])) {
                        echo "<td class=\"usera\">$act_q->userlists_access</td><td class=\"projecta\">$act_q->projects_access</td>";
                    }
                    echo "</tr>\n";
                    if (isset($vars["sjl"])) {
                        $act_q->show_log_lines(4);
                    }
                }
                echo "</table>\n";
            } else {
                $no_f[]="no queues found";
            }
        }
        if ($no_f) message("No ".implode(", ",$no_f));
    } else {
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
