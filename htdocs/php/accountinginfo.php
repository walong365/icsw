<?php
//-*ics*- ,CAPG,name:'job',descr:'Jobsystem',pri:40
//-*ics*- ,CAP,name:'aci',descr:'Accounting info',enabled:1,defvalue:1,scriptname:'/php/accountinginfo.php',left_string:'Accountinginfo',right_string:'Accounting information',pri:-10,capability_group_name:'job'
//-*ics*- ,CAP,name:'aac',descr:'Accounting info for all accounts',enabled:1,defvalue:0,mother_capability_name:'aci'
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
function gettimestr($insecs) {
    $hours=(int) ($insecs/3600);
    $mins=(int)(($insecs-3600*$hours)/60);
    $secs=$insecs-60*$mins-3600*$hours;
    $rstr="";
    if ($hours > 50) {
        $days=(int) ($hours/24);
        $hours-=$days*24;
        if ($days > 50) {
            $weeks=(int) ($days/7);
            $days-=$weeks*7;
            if ($weeks > 51) {
                $years= (int) ($weeks/52);
                $weeks-=$years*52;
                $rstr.=sprintf("%d y, ",$years);
            }
            if ($weeks) $rstr.=sprintf("%d w, ",$weeks);
        }
        if ($days) $rstr.=sprintf("%d d ",$days);
    }
    $rstr.=sprintf("%2d:%02d:%02d",$hours,$mins,$secs);
    return $rstr;
}
function changedate($indate,$offset) {
    $actyear=(int) substr($indate,0,4);
    $actmonth=(int) substr($indate,4,2);
    $actday=(int) substr($indate,6,2);
    list($newyear,$newmonth,$newday)=changedate2($actyear,$actmonth,$actday,$offset);
    return sprintf("%04d%02d%02d",$newyear,$newmonth,$newday);
}
function changedate2($actyear,$actmonth,$actday,$offset) {
    $done="-";
#$num=0;
    do {
#$num++;
#echo strval($actyear).".".strval($actmonth).".".strval($actday)."<br>";
        switch ($done) {
        case "-":
            $done=$offset;
            switch ($offset) {
            case "pd":
                $actday++;
                break;
            case "pw":
                $actday+=7;
                break;
            case "pm":
                $actmonth++;
                break;
            case "py":
                $actyear++;
                $done="cmd";
                break;
            case "md":
                $actday--;
                break;
            case "mw":
                $actday-=7;
                break;
            case "mm":
                $actmonth--;
                break;
            case "my":
                $actyear--;
                $done="cmd";
                break;
            }
            break;
        case "pd":
            $actday=1;
            $actmonth+=1;
            $done="pm";
            break;
        case "pm":
            $actmonth=1;
            $actyear+=1;
            $done="cmd";
            break;
        case "md":
            $actday=31;
            $actmonth-=1;
            $done="mm";
            break;
        case "mm":
            if ($actmonth == 0) {
                $actmonth=12;
                $actyear-=1;
            } else {
                $done="cmd";
            }
            break;
        case "cmd":
            while (! checkdate($actmonth,$actday,$actyear)) { $actday-- ; }
            break;
        }
        if (checkdate($actmonth,$actday,$actyear) or ($done=="exit")) break;
#if ($num > 100) break;
    } while (1);
    return array($actyear,$actmonth,$actday);
}

class res{
    var $name;
    var $cpu,$walltime,$walltime_t,$num_jobs,$num_slots;
    var $walltime_p,$walltime_t_p;
    var $min_slots,$max_slots;
    function res($name) {
        $this->name=$name;
        $this->num_jobs=0;
        $this->num_slots=0;
        $this->min_slots=0;
        $this->max_slots=0;
        $this->cpu=0;
        $this->walltime=0;
        $this->walltime_t=0;
        $this->walltime_p=0;
        $this->walltime_t_p=0;
        $this->jobs=array();
    }
    function get_mean_slots() {
        if ($this->num_jobs) {
            return sprintf("%.2f",$this->num_slots/$this->num_jobs);
        } else {
            return sprintf("%.2f",0);
        }
    }
    function get_mean_walltime() {
        if ($this->num_jobs) {
            return $this->walltime_t/$this->num_jobs;
        } else {
            return 0;
        }
    }
    function add_job_run($job) {
        # get latest run
        $job_runs=array_keys($job->runs);
        $job_run=&$job->runs[$job_runs[count($job_runs)-1]];
        if (!in_array($job->job_uid,array_keys($this->jobs))) {
            $this->jobs[$job->job_uid]=$job->sge_job_idx;
            $this->num_jobs++;
            $this->num_slots+=$job_run->slots;
            if (!$this->min_slots) {
                $this->min_slots=$job_run->slots;
            } else {
                $this->min_slots=min($this->min_slots,$job_run->slots);
            }
            $this->max_slots=max($this->max_slots,$job_run->slots);
        }
        // run-local variables
        $this->cpu+=$job_run->sge_cpu;
        $this->walltime+=$job_run->sge_ru_wallclock;
        $this->walltime_t+=$job_run->slots*$job_run->sge_ru_wallclock;
    }
    function set_perc($res) {
        if ($res->walltime) {
            $this->walltime_p=sprintf("%3.2f",(100*$this->walltime/$res->walltime));
        } else {
            $this->walltime_p=sprintf("%3.2f",0);
        }
    }
}
class job_run {
    var $slots,$jobname,$granted_pe;
    var $sge_cpu,$sge_ru_wallclock,$failed,$failed_str,$exit_status,$masterq;
    function job_run($js) {
        foreach (array("jobname","slots","sge_cpu","sge_ru_wallclock","failed","failed_str","exit_status","masterq") as $name) {
            $this->$name=$js->$name;
        }
    }
}
        
class job {
    var $jobname;
    var $slots;
    var $num_logs,$logs,$num_runs,$runs;
    var $job_uid,$jobnum,$taskid,$sge_job_idx;
    var $jobowner,$jobgroup,$account,$suname,$sulname,$spname;
    function job($js) {
        $this->num_logs=0;
        $this->logs=array();
        $this->num_runs=0;
        $this->runs=array();
        foreach (array("job_uid","jobnum","taskid","sge_job_idx","jobowner","jobgroup","account","suname","sulname","spname") as $name) {
            $this->$name=$js->$name;
        }
    }
    function add_log($js) {
        if ($js->log_str) {
            $this->logs[]=array($js->logdate,$js->log_str);
            $this->num_logs++;
        }
    }
    function add_run($js) {
        if ($js->sge_job_run_idx) {
            $run_idx=$js->sge_job_run_idx;
        } else {
            $run_idx=0;
        }
        if (!in_array($run_idx,array_keys($this->runs))) {
            $this->runs[$run_idx]=new job_run($js);
            $this->num_runs++;
        }
    }
    function show_log_lines($cspan) {
        if ($this->num_logs) {
            echo "<tr><td class=\"log\" colspan=\"$cspan\">\n";
            $num_lines=min(6,max(2,count($this->logs)+1));
            echo "<textarea cols=120 rows=$num_lines wrap=\"off\" class=\"log\" readonly>";
            $idx=0;
            foreach ($this->logs as $lline) {
                $idx++;
                list($when,$what)=$lline;
                printf("%03d %s :: %s\n",$idx,$when,$what);
            }
            echo "</textarea>\n";
            echo "</td></tr>\n";
        }
    }
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["aci_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $actdate=getdate(time());
    $dtype="day";
    $term_date=sprintf("%04d%02d%02d",(int) $actdate["year"],$actdate["mon"],$actdate["mday"]);
    $sdate=changedate($term_date,"md");
    if (isset($vars["date"])) $sdate=$vars["date"];
    if (isset($vars["dtype"])) $dtype=$vars["dtype"];
    $r_types=array("user","group","project","department","account");
    //print_r($vars);
    htmlhead();
    clusterhead($sys_config,"Accounting information page","formate.css",
                array("table.acc_cal"=>array("border-color:#000000","background-color:#e0f4f4","border-width:1px","margin:2px","border-spacing:0px","border-style:none","padding:1px","width:25%","border-collapse:collapse","spacing:2px"),
                      "td.acc_top"=>array("vertical-align:top","padding:5px"),
                      ".acc_cal_cell_mn"  =>array("vertical-align:center","text-align:right","padding:4px","border-width:1px","border-spacing:0px","border-style:none","font-size:large","text-align:center","background-color:#ffffff"),
                      ".acc_cal_cell_wdn" =>array("vertical-align:center","text-align:right","padding:4px","border-width:1px","border-spacing:0px","border-style:none","font-size:large","text-align:center","background-color:#ffffff"),
                      ".acc_cal_cell_wn"  =>array("vertical-align:center","text-align:right","padding:4px","border-width:1px","border-spacing:0px","border-style:solid","padding:5px","background-color:#f4e0f4","font-size:large"),
                      ".acc_cal_cell_day" =>array("vertical-align:center","text-align:center","padding:4px","border-width:1px","border-spacing:0px","border-style:solid"),
                      ".acc_cal_cell_days"=>array("vertical-align:center","text-align:center","padding:4px","border-width:1px","border-spacing:0px","border-style:solid","background-color:#ff8888"),
                      ".acc_cal_cell_e"   =>array("vertical-align:center","text-align:right","padding:4px","border-width:1px","border-style:none","border-spacing:0px","background-color:#ffffff"),
                      "a:link.acc_cal_w"    =>array("font-weight:bold","color:#000000","text-decoration:none","background-color:#f4e0f4"),
                      "a:visited.acc_cal_w" =>array("font-weight:bold","color:#000000","text-decoration:none","background-color:#f4e0f4"),
                      "a:hover.acc_cal_w"   =>array("font-weight:bold","color:#444400","text-decoration:none","background-color:#f4e0f4"),
                      "a:active.acc_cal_w"  =>array("font-weight:bold","color:#ffffff","text-decoration:underline","background-color:#f4e0f4"),

                      "a:link.acc_cal_d"    =>array("font-weight:bold","color:#000000","text-decoration:none","background-color:#e0f4f4"),
                      "a:visited.acc_cal_d" =>array("font-weight:bold","color:#000000","text-decoration:none","background-color:#e0f4f4"),
                      "a:hover.acc_cal_d"   =>array("font-weight:bold","color:#444400","text-decoration:none","background-color:#e0f4f4"),
                      "a:active.acc_cal_d"  =>array("font-weight:bold","color:#ffffff","text-decoration:underline","background-color:#e0f4f4"),

                      "a:link.acc_cal_ds"   =>array("font-weight:bold","color:#000000","text-decoration:none","background-color:#ff8888"),
                      "a:visited.acc_cal_ds"=>array("font-weight:bold","color:#000000","text-decoration:none","background-color:#ff8888"),
                      "a:hover.acc_cal_ds"  =>array("font-weight:bold","color:#444400","text-decoration:none","background-color:#ff8888"),
                      "a:active.acc_cal_ds" =>array("font-weight:bold","color:#ffffff","text-decoration:underline","background-color:#ff8888"),
                      "th.accname"=>array("background-color:#eeeeff","text-align:center"),
                      "td.accnamen"=>array("background-color:#ccccee"),
                      "td.accnameu"=>array("background-color:#d8d8f0"),
                      "td.accnamet"=>array("background-color:#e7e7f7"),
                      "th.acccput"=>array("background-color:#fff0f0","text-align:center"),
                      "td.acccputn"=>array("background-color:#eedddd","text-align:center"),
                      "td.acccputu"=>array("background-color:#f0d8d8","text-align:center"),
                      "td.acccputt"=>array("background-color:#f7e7e7","text-align:center"),
                      "th.accwt"=>array("background-color:#eeeeff","text-align:center"),
                      "td.accwtn"=>array("background-color:#ccccee","text-align:center"),
                      "td.accwtu"=>array("background-color:#d8d8f0","text-align:center"),
                      "td.accwtt"=>array("background-color:#e7e7f7","text-align:center"),
                      "th.accpcput"=>array("background-color:#ffeeff","text-align:center"),
                      "td.accpcputn"=>array("background-color:#eeddee","text-align:center"),
                      "td.accpcputu"=>array("background-color:#f0d8f0","text-align:center"),
                      "td.accpcputt"=>array("background-color:#f7e7f7","text-align:center"),
                      "th.accpwt"=>array("background-color:#fefedd","text-align:center"),
                      "td.accpwtn"=>array("background-color:#ececbb","text-align:center"),
                      "td.accpwtu"=>array("background-color:#f0f0c0","text-align:center"),
                      "td.accpwtt"=>array("background-color:#f6f6c5","text-align:center"),
                      "th.jobnum"    =>array("background-color:#ddffcc"),
                      "th.job"       =>array("background-color:#e0f0e0"),
                      "th.jobtaskid" =>array("background-color:#e4ffdd"),
                      "td.job1num"   =>array("background-color:#cceecc","border-top:1px black solid","border-right:1px black solid"),
                      "td.job1taskid"=>array("background-color:#d4eecc","border-top:1px #888888 solid","border-right:1px #888888 solid"),
                      "td.job1"     =>array("background-color:#d4eed4"),
                      "td.job1c"     =>array("background-color:#d4eed4","text-align:center"),
                      "td.job1r"     =>array("background-color:#d4eed4","text-align:right"),
                      "td.job2num"   =>array("background-color:#ccccee","border-top:1px black solid","border-right:1px black solid"),
                      "td.job2taskid"=>array("background-color:#ccd4ee","border-top:1px #888888 solid","border-right:1px #888888 solid"),
                      "td.job2"     =>array("background-color:#d0d0e4"),
                      "td.job2c"     =>array("background-color:#d0d0e4","text-align:center"),
                      "td.job2r"     =>array("background-color:#d0d0e4","text-align:right"),
                      "td.log"       =>array("background-color:#e4e4e4")
                      
                      )
                );
    $all_del=1;
    foreach ($r_types as $r_type) {
        if (!is_set($r_type,&$vars)) $all_del=0;
    }
    if ($all_del) unset($vars["user"]);
    $sup_ref_str="";
    if (is_set("logs",&$vars)) {
        $with_logs=1;
        $vars["detail"]=1;
        $sup_ref_str.="&logs=1";
    } else {
        $with_logs=0;
    }
    if (is_set("detail",&$vars)) {
        $detail=1;
        $sup_ref_str.="&detail=1";
    } else {
        $detail=0;
    }
    foreach ($r_types as $r_type) {
        if (is_set($r_type,&$vars)) $sup_ref_str.="&$r_type=1";
    }
    // check suppress info
    clusterbody($sys_config,"Accounting information",array(),array("job"));

    $days=array("Sun","Mon","Tue","Wen","Thu","Fri","Sat");
    $months=array("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec");

    $term_year=(int) substr($term_date,0,4);
    $term_month=(int) substr($term_date,4,2);
    $term_day=(int) substr($term_date,6,2);

    $act_year=(int) substr($sdate,0,4);
    $act_month=(int) substr($sdate,4,2);
    $act_day=(int) substr($sdate,6,2);
    if (! checkdate($act_month,$act_day,$act_year) || strlen($sdate) != 8) {
        $sdate=changedate($term_date,"md");
        $act_year=(int) substr($sdate,0,4);
        $act_month=(int) substr($sdate,4,2);
        $act_day=(int) substr($sdate,6,2);
    }
    list($prev_year,$prev_month,$prev_day)=changedate2($act_year,$act_month,1,"mm");
    list($next_year,$next_month,$next_day)=changedate2($act_year,$act_month,1,"pm");
    $needed_months=array(array($prev_year,$prev_month),array($act_year,$act_month),array($next_year,$next_month));
    $check_dates=array();
    if ($dtype == "day") {
        $check_dates[]=sprintf("%04d%02d%02d",$act_year,$act_month,$act_day);
    } else if ($dtype == "week") {
        $d_array=getdate(mktime(12,0,0,1,1,$act_year));
        $day_offset=$d_array["wday"];
        $d_array=getdate(mktime(12,0,0,$act_month,$act_day,$act_year));
        $t_week=($d_array["yday"]-$d_array["wday"]+$day_offset)/7+1;
    }
    echo "<table class=\"simple\"><tr>";
    $w_add=0;
    foreach ($needed_months as $amonth) {
        echo "<td class=\"acc_top\">";
        list($a_year,$a_month)=$amonth;
# build the actual month array
        $act_month_a=array();
        $d_array=getdate(mktime(12,0,0,1,1,$a_year));
        $day_offset=$d_array["wday"];
        for ($day=0;$day<32;$day++) {
            if (checkdate($a_month,$day,$a_year)) {
                $d_array=getdate(mktime(12,0,0,$a_month,$day,$a_year));
                $wday=$d_array["wday"];
                $week=($d_array["yday"]-$wday+$day_offset)/7+1;
                $act_month_a[]=array($day,$week,$wday);
                if ($dtype == "month" && $a_month == $act_month) {
                    $check_dates[]=sprintf("%04d%02d%02d",$a_year,$a_month,$day);
                } else if ($dtype == "week") {
                    if ($week == $t_week || ($week == 1 && sizeof($check_dates < 7) && $w_add)) {
                        $check_dates[]=sprintf("%04d%02d%02d",$a_year,$a_month,$day);
                        $w_add=1;
                        $t_week=$week;
                    }
                }
            }
        }
        echo "<table class=\"acc_cal\">";
        echo "<tr><th class=\"acc_cal_cell_e\">&nbsp;</th><th colspan=7 class=\"acc_cal_cell_mn\"><a href=\"{$sys_config['script_name']}?date=".sprintf("%04d%02d%02d",$a_year,$a_month,1)."&dtype=month$sup_ref_str&".write_sid()."\">\n";
        echo $months[$a_month-1]." $a_year";
        echo "</a></th></tr>\n";
        echo "<tr><th class=\"acc_cal_cell_e\">&nbsp;</th>";
        foreach ($days as $wd) {
            echo "<th class=\"acc_cal_cell_wdn\">$wd</th>\n";
        }
        echo "</tr>\n";
        $last_week=0;
        foreach ($act_month_a as $act_month_p) {
            list($day,$week,$wday)=$act_month_p;
            if ($last_week != $week) {
                if ($last_week != 0) echo "</tr>\n";
                echo "<tr><td class=\"acc_cal_cell_wn\"><a class=\"acc_cal_w\" href=\"{$sys_config['script_name']}?date=".sprintf("%04d%02d%02d",$a_year,$a_month,$day)."&dtype=week$sup_ref_str&".write_sid()."\" >$week</a></td>\n";
                for ($i =0;$i<$wday;$i++) echo "<td class=\"acc_cal_cell_e\">&nbsp;</td>";
                //echo "</tr>\n<tr>";
                $last_week=$week;
            }
            $day_d=sprintf("%04d%02d%02d",$a_year,$a_month,$day);
            $ds_str=((in_array($day_d,$check_dates)) ? "s" : "");
            if ($day_d==$term_date) $day="&lt;$day&gt;";
            echo "<td class=\"acc_cal_cell_day{$ds_str}\"><a class=\"acc_cal_d{$ds_str}\"href=\"{$sys_config['script_name']}?date={$day_d}&dtype=day$sup_ref_str&".write_sid()."\">$day</a></td>\n";
        }
        for ($i=$wday;$i<6;$i++) echo "<td class=\"acc_cal_cell_e\">&nbsp;</td>";
        echo "</tr>\n";
        echo "</table>\n";
        echo "</td>";
    }
    echo "</tr></table>\n";
    echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
    echo "<div class=\"center\">";
    echo "<input type=hidden name=\"date\" value=\"$sdate\"/><input type=hidden name=\"dtype\" value=\"$dtype\" />\n";
    echo "Suppress ";
    foreach ($r_types as $r_type) {
        echo "$r_type <input type=checkbox name=\"$r_type\" value=\"sup\" ".(is_set($r_type,&$vars) ? "checked" : "")."/>, \n";
    }
    echo "detailed: <input type=checkbox name=\"detail\" value=\"1\" ".($detail ? "checked" : "")."/>, \n";
    echo "with logs: <input type=checkbox name=\"logs\" value=\"1\" ".($with_logs ? "checked" : "")."/>, \n";
    echo "<input type=submit value=\"select\"/>";
    echo "</div>\n";
    echo "</form>";
    //print_r($check_dates);
    $actstrdate=strftime("%e %B %Y\n",mktime(0,0,0,$act_month,$act_day,$act_year));
    $ucl=usercaps($sys_db_con);
    if ($ucl["aci"]) {
        $num_days=sizeof($check_dates);
    
        $messtr="Given date: $actstrdate, showing the per-$dtype statistics";
        if ($num_days > 1) $messtr.=" ($num_days days)";
        $mysql_s_str=$check_dates[0];
        $mysql_e_str=$check_dates[count($check_dates)-1];
        //$mysql_s_str=strftime("%Y%m%d",mktime(0,0,0,$act_month,$act_day,$act_year));
        $sel_str="j.job_uid,j.sge_job_idx,jr.sge_job_run_idx,j.jobname,j.jobnum,j.taskid,j.jobowner,j.jobgroup,j.queue_time,jr.slots,jr.account,jr.sge_cpu,jr.sge_ru_wallclock,jr.exit_status,jr.failed,jr.failed_str,jr.granted_pe,jr.masterq,su.name AS suname, sul.name AS sulname, sp.name AS spname ";
        $sql_query="sge_job j LEFT JOIN sge_job_run jr ON jr.sge_job=j.sge_job_idx LEFT JOIN sge_user su ON j.sge_user=su.sge_user_idx LEFT JOIN sge_userlist sul ON sul.sge_userlist_idx=jr.sge_userlist LEFT JOIN sge_project sp ON sp.sge_project_idx=jr.sge_project ";
        if ($with_logs) {
            $sel_str.=",sjl.log_str,DATE_FORMAT(sjl.date,'%e. %b %Y , %H:%i:%s') AS logdate ";
            $sql_query.=" LEFT JOIN sge_job_log sjl ON sjl.sge_job=j.sge_job_idx ";
        }
        $sql_query.=" WHERE jr.start_time < '{$mysql_e_str}235959' AND jr.end_time > '{$mysql_s_str}000000'";
        $mres=query("SELECT $sel_str FROM $sql_query");
        $num_jobs=0;
        $job_dict=array();
        if (mysql_num_rows($mres)) {
            $totname="zzzzzztotal";
            $unkname="zzzunknown";
            $r_dict=array();
            $r_types=array("user","group","project","department","account");
            foreach ($r_types as $r_type) {
                $r_dict[$r_type]=array($totname=>new res($totname),
                                       $unkname=>new res($unkname));
            }
            $runs_visited=array();
            while ($mfr=mysql_fetch_object($mres)) {
                if (!in_array($mfr->sge_job_idx,array_keys($job_dict))) {
                    $num_jobs++;
                    $act_job=new job($mfr);
                    $job_dict[$mfr->sge_job_idx]=&$act_job;
                } else {
                    $act_job=&$job_dict[$mfr->sge_job_idx];
                }
                $act_job->add_run($mfr);
                if ($with_logs) $job_dict[$mfr->sge_job_idx]->add_log($mfr);
                if (!in_array($mfr->sge_job_run_idx,$runs_visited)) {
                    $runs_visited[]=$mfr->sge_job_run_idx;
                    $ref_dict=array();
                    foreach($r_types as $r_type) {
                        $r_dict[$r_type][$totname]->add_job_run($act_job);
                        $ref_dict[$r_type]=$unkname;
                    }
                    if ($act_job->suname) {
                        $ref_dict["user"]=$act_job->suname;
                    } else if ($act_job->jobowner) {
                        $ref_dict["user"]=$act_job->jobowner;
                    }
                    if ($act_job->jobgroup) $ref_dict["group"]=$act_job->jobgroup;
                    if ($act_job->account) $ref_dict["account"]=$act_job->account;
                    if ($act_job->sulname) $ref_dict["department"]=$act_job->sulname;
                    if ($act_job->spname) $ref_dict["project"]=$act_job->spname;
                    foreach ($ref_dict as $rk=>$rv) {
                        if (!in_array($rv,array_keys($r_dict[$rk]))) $r_dict[$rk][$rv]=new res($rv);
                        $r_dict[$rk][$rv]->add_job_run($act_job);
                    }
                }
                unset($act_job);
            }
        }
        if ($num_jobs) {
            $messtr.=", found ".get_plural("job",$num_jobs,1);
        } else {
            $messtr.=", no accounting information found for the given timeframe.";
        }
        message($messtr);
        if ($num_jobs) {
            //message("Efficiency (nodes used): ".sprintf("%.1f",$ulist["TOTAL"]->res->wtused/($num_days*3600*24))." of 156");
            foreach ($r_dict as $r_type=>$r_stuff) {
                if (!is_set($r_type,&$vars)) {
                    // calculate percentages
                    $klist=array_keys($r_stuff);
                    sort($klist);
                    foreach ($klist as $k) {
                        $r_dict[$r_type][$k]->set_perc($r_dict[$r_type][$totname]);
                    }
                    message("Per-$r_type overview",$type=1);
                    echo "<table class=\"normal\">";
                    echo "<tr>";
                    echo "<th class=\"accname\">Name</th>\n";
                    echo "<th class=\"acccput\"># of jobs</th>\n";
                    echo "<th class=\"acccput\"># of slots</th>\n";
                    echo "<th class=\"acccput\" colspan=3>min/mean/max # of slots</th>\n";
                    echo "<th class=\"accwt\">time consumed</th><th class=\"accwt\">perc.</th>";
                    echo "<th class=\"accpwt\">time per job</th>\n";
                    echo "</tr>\n";
                    foreach ($klist as $k) {
                        $act_e=&$r_stuff[$k];
                        if ($act_e->num_jobs) {
                            if ($k == $totname) {
                                $k_o=substr($k,6);
                                $actt="t";
                            } else if ($k == $unkname) {
                                $k_o=substr($k,3);
                                $actt="u";
                            } else {
                                $k_o=$k;
                                $actt="n";
                            }
                            $show=1;
                            if ($show) {
                                echo "<tr>";
                                echo "<td class=\"accname$actt\">$k_o</td>";
                                echo "<td class=\"acccput$actt\">$act_e->num_jobs</td>";
                                echo "<td class=\"acccput$actt\">$act_e->num_slots</td>";
                                echo "<td class=\"acccput$actt\">$act_e->min_slots</td>";
                                echo "<td class=\"acccput$actt\">".$act_e->get_mean_slots()."</td>\n";
                                echo "<td class=\"acccput$actt\">$act_e->max_slots</td>";
                                echo "<td class=\"accwt$actt\">",gettimestr($act_e->walltime_t),"</td>";
                                echo "<td class=\"accwt$actt\">$act_e->walltime_p %</td>";
                                echo "<td class=\"accpwt$actt\">".gettimestr($act_e->get_mean_walltime())."</td>\n";
                                echo "</tr>\n";
                                if ($actt != "t" && $detail) {
                                    echo "<tr><td class=\"blind\" colspan=\"9\">";
                                    echo "<table class=\"simplefull2\">";
                                    echo "<tr><th class=\"jobnum\">JobNum</th>\n";
                                    echo "<th class=\"jobtaskid\">TaskID</th>\n";
                                    if ($with_logs) echo "<th class=\"jobtaskid\">#Logs</th>\n";
                                    foreach (array("Name","Wallclock","slots","PE","failed","failed_str","exit_status","MasterQ") as $name) {
                                        echo "<th class=\"job\">$name</th>\n";
                                    }
                                    echo "</tr>\n";
                                    // check array_jobs
                                    $aj_dict=array();
                                    //total number of runs per job
                                    $job_runs=array();
                                    foreach ($act_e->jobs as $job_uid=>$job_idx) {
                                        $job_stuff=&$job_dict[$job_idx];
                                        $jobnum=(int)$job_stuff->jobnum;
                                        if (!in_array($jobnum,array_keys($aj_dict))) {
                                            $aj_dict[$jobnum]=array();
                                            $job_runs[$jobnum]=0;
                                        }
                                        $aj_dict[$jobnum][(int)$job_stuff->taskid]=$job_stuff->num_runs;
                                        $job_runs[$jobnum]+=$job_stuff->num_runs+$with_logs;
                                    }
                                    $c_j=1;
                                    $c_t=1;
                                    $job_nums=array_keys($aj_dict);
                                    sort($job_nums);
                                    foreach ($job_nums as $job_num) {
                                        $task_ids=array_keys($aj_dict[$job_num]);
                                        sort($task_ids);
                                        $c_j=3-$c_j;
                                        echo "<tr>";
                                        echo "<td class=\"job{$c_j}num\" rowspan=\"{$job_runs[$job_num]}\">$job_num</td>\n";
                                        $first_taskid=0;
                                        foreach ($task_ids as $task_id) {
                                            $job_uid="$job_num";
                                            if ($task_id) $job_uid.=".$task_id";
                                            $job_stuff=&$job_dict[$act_e->jobs[$job_uid]];
                                            echo "<td class=\"job{$c_t}taskid\" rowspan=\"$job_stuff->num_runs\">$job_stuff->taskid</td>";
                                            if ($with_logs) {
                                                echo "<td class=\"job{$c_t}taskid\" rowspan=\"$job_stuff->num_runs\">$job_stuff->num_logs</td>\n";
                                            }
                                            $first_taskid=0;
                                            foreach ($job_stuff->runs as $job_run_idx=>$job_run) {
                                                $c_t=3-$c_t;
                                                if ($first_taskid++) echo "<tr>";
                                                echo "<td class=\"job{$c_t}\">$job_run->jobname</td>";
                                                echo "<td class=\"job{$c_t}c\">".gettimestr($job_run->sge_ru_wallclock)."</td>";
                                                echo "<td class=\"job{$c_t}c\">$job_run->slots</td>";
                                                echo "<td class=\"job{$c_t}c\">$job_run->granted_pe</td>\n";
                                                echo "<td class=\"job{$c_t}r\">$job_run->failed , </td>";
                                                echo "<td class=\"job{$c_t}\">$job_run->failed_str</td>";
                                                echo "<td class=\"job{$c_t}c\">$job_run->exit_status</td>";
                                                echo "<td class=\"job{$c_t}\">$job_run->masterq</td>\n";
                                                echo "</tr>\n";
                                            }
                                            if($with_logs) {
                                                $job_stuff->show_log_lines(10);
                                            }
                                        }
                                    }
                                    echo "</table></td></tr>\n";
                                }
                            }
                        }
                    }
                }
                echo "</table>\n";
            }
        }
    } else {
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
