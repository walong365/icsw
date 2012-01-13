<?php
//-*ics*- ,CAP,name:'jsi',descr:'Jobsystem info',defvalue:1,enabled:1,scriptname:'/php/jobsysinfo.php',left_string:'Jobsysteminfo',right_string:'Information about the batchsystem'
function my_job_cmp($a,$b) {
    if ($a->pri < $b->pri) {
        return 1; 
    } else if ($a->pri > $b->pri) {
        return -1;
    } else {
        return 0;
    }
}
function my_job_cmp_2($j1,$j2) {
    //(echo "$j1->sort_crit , $j1->id, $j2->id<br>";
    $swap=0;
    switch ($j1->sort_crit) {
    case "jobid":
        if ($j1->id < $j2->id) $swap=1;
        break;
    case "user":
        if ($j1->user < $j2->user) $swap=1;
        break;
    case "numnodes":
        if ($j1->nodenum < $j2->nodenum) $swap=1;
        break;
    case "jobname":
        if ($j1->name < $j2->name) $swap=1;
        break;
    case "t0":
        if ($j1->time_run < $j2->time_run) $swap=1;
        break;
    case "t1":
        if ($j1->time_left < $j2->time_left) $swap=1;
        break;
    case "l1":
        if ($j1->load_avg < $j2->load_avg) $swap=1;
        break;
    }
    return $swap;
}

class node {
    var $name,$down,$jobs,$alarm;
    function node($name) {
        $this->name=$name;
        $this->down=0;
        $this->alarm=1;
        $this->jobs=array();
    }
}
class sres {
    var $name,$clist,$hlist,$ohlist;
    function sres($name) {
        $this->name=$name;
        $this->classes=array();
        $this->nodes=array();
        $this->ohlist="";
    }
    function set_classes($clist) {
        $this->classes=$clist;
    }
    function set_nodes($clist) {
        $this->nodes=$clist;
        $this->optimize_hostlist();
    }
    function get_free_nodes($all_nodes) {
        $free_nodes=0;
        $problem_nodes=0;
        foreach ($this->nodes as $host) {
            if ($all_nodes[$host]["down"]) {
                $problem_nodes++;
            } else if ($all_nodes[$host]["used"]==0) {
                $free_nodes++;
            }
        }
        return array($free_nodes,$problem_nodes);
    }
    function optimize_hostlist() {
        $this->ohlist=optimize_hostlist($this->nodes);
    }
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
        if ($act || count($time_o)) {
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
    var $id,$ehost,$nodenum,$user,$name,$time,$c_list,$wall,$vmem;
    var $pri,$qtime,$depend,$reqnodes,$load_avg;
    var $pri_cred_class,$pri_fs_user,$pri_serv_qtime,$pri_serv_xfctr,$pri_serv_bypass;
    function job($id,$ehost,$nodenum,$user,$name,$time,$c_list,$load_avg,$time_r,$time_l) {
        $this->id=$id;
        $this->host=$ehost;
        $this->nodenum=$nodenum;
        $this->user=$user;
        $this->name=$name;
        $this->time=$time;
        $this->c_list=$c_list;
        $this->wall=$wall;
        $this->vmem=$vmem;
        $this->pri=0;
        $this->time_run=str_to_sec($time_r);
        $this->time_left=str_to_sec($time_l);
        $this->load_avg=(float)$load_avg;
        $this->qtime=$qtime;
        $this->depend="";
        $this->reqnodes=0;
        $this->pri_cred_class=0.;
        $this->pri_fs_user=0.;
        $this->pri_serv_qtime=0.;
        $this->pri_serv_xfctr=0.;
        $this->pri_serv_bypass=0.;
        $this->sort_crit="";
        //echo strval($this->user->fair_share)."<br>";
    }
    function set_depend($dep) {
        $dlist=preg_split("/,/",$dep);
        $this->depend=$dlist;
    }
    function get_name() { return "<td class=\"jobs\">$this->name</td>"; }
    function get_mean_load() { return "<td class=\"meanload\">".sprintf("%.2f",$this->load_avg)."</td>"; }
    function get_user() { return "<td class=\"user\">".$this->user."</td>"; }
    function get_host() { return "<td class=\"exhost\">".implode(" , ",$this->host)."</td>"; }
    function get_nodenum() { return "<td class=\"excpu\">$this->nodenum</td>"; }
    function get_id() { return "<td class=\"id\">$this->id</td>"; }
    function get_pri() { 
        $ret_str="";
        $show_percent=0;
        $tot_pri=$this->pri;
        foreach (array($this->pri,$this->pri_cred_class,$this->pri_fs_user,$this->pri_serv_qtime,$this->pri_serv_xfctr,$this->pri_serv_bypass) as $act_pri) {
            $ret_str.="<td class=\"pri\">".strval($act_pri);
            if ($show_percent) {
                $ret_str.=" (";
                if ($tot_pri == 0) {
                    $ret_str.="100 %";
                } else {
                    $ret_str.=sprintf("%.1f %%",doubleval(100*$act_pri/$tot_pri));
                }
                $ret_str.=")";
            }
            $ret_str.="</td>\n";
            $show_percent=1;
        }
        return $ret_str;
    }
    function get_time() { return "<td class=\"time\">$this->time</td>";}
    function get_time_run() { return "<td class=\"time\">".sec_to_str($this->time_run)."</td>"; }
    function get_time_left() { return "<td class=\"time\">".sec_to_str($this->time_left)."</td>"; }
    function get_queue() { return "<td class=\"qu\">".implode(",",$this->c_list)."</td>"; }
    function get_wall() { return "<td class=\"wall\">".sec_to_str($this->wall)."</td>"; }
    function get_vmem() { return "<td class=\"vmem\">".strval($this->vmem)." MB</td>"; }
    function get_reqnodes() { return "<td class=\"wall\">".strval($this->reqnodes)."</td>"; }
    function get_qtime() { return "<td class=\"vmem\">".$this->qtime."</td>"; }
    function get_depend($jl) {
        $rstr="<td class=\"pri\">";
        $rstr.="<table width=100% align=center>";
        foreach ($this->depend as $sd) {
            $sds=preg_split("/:/",$sd);
            $jid=preg_split("/\./",$sds[1]);
            $jid=$jid[0];
            $addinfo="";
            foreach ($jl as $ajob) {
                if ($ajob->id==$jid) $addinfo=" ; ".$ajob->name." ( ".$ajob->user->name." )";
            }
            $rstr.="<tr><td align=right width=30%>".$sds[0]."</td>";
            $rstr.="<td align=center>:</td>";
            $rstr.="<td align=left>$jid$addinfo</td></tr>";
        }
        $rstr.="</table>";
        $rstr.="</td>";
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
    // init mysql statistics
    init_mysql_stats();
    // maximum number of jobs to display
    $MAX_JOBS=10000;
    htmlhead();
    clusterhead($sys_config,"Batch system information page",$style="formate.css",
                array("th.vmem"=>array("background-color:#efffbe","text-align:center"),
                      "td.vmem"=>array("background-color:#deeead","text-align:center"),
                      "th.wall"=>array("background-color:#dffeff","text-align:center"),
                      "td.wall"=>array("background-color:#ceedee","text-align:center"),
                      "th.qu"=>array("background-color:#fff0f0","text-align:center"),
                      "td.qu"=>array("background-color:#eedddd","text-align:center"),
                      "th.pri"=>array("background-color:#ffeeee","text-align:center"),
                      "td.pri"=>array("background-color:#eedeee","text-align:center"),
                      "th.meanload"=>array("background-color:#99eeee","text-align:center"),
                      "td.meanload"=>array("background-color:#88deee","text-align:center"),
                      "th.time"=>array("background-color:#effeff","text-align:center"),
                      "td.time"=>array("background-color:#deedee","text-align:right"),
                      "th.excpu"=>array("background-color:#eeeeff","text-align:center"),
                      "td.excpu"=>array("background-color:#ccccee","text-align:center"),
                      "th.exhost"=>array("background-color:#eeeeff","text-align:center"),
                      "td.exhost"=>array("background-color:#ccccee","text-align:center"),
                      "th.jobh"=>array("background-color:#ffeeff","text-align:center"),
                      "td.jobn"=>array("background-color:#eeddee","text-align:center"),
                      "td.jobs"=>array("background-color:#eeccee","text-align:center"),
                      "th.qnum"=>array("background-color:#eeeeff","text-align:center"),
                      "td.qnum"=>array("background-color:#ccccee","text-align:center"),
                      "th.qtot"=>array("background-color:#f0f0f8","text-align:center"),
                      "td.qtot"=>array("background-color:#e0e0f7","text-align:center"),
                      "th.qucs"=>array("background-color:#ddddff","text-align:center"),
                      "td.qucs"=>array("background-color:#ccccee","text-align:center"),
                      "th.quwt"=>array("background-color:#eeeeee","text-align:center"),
                      "td.quwt"=>array("background-color:#cccccc","text-align:center"),
                      "th.qummc"=>array("background-color:#ddffff","text-align:center"),
                      "td.qummc"=>array("background-color:#bbdddd","text-align:center"),
                      "th.id"=>array("color:#000000","background-color:#ffffff","text-align:center"),
                      "td.id"=>array("color:#000000","background-color:#eeeeee","text-align:center")
                      ));
    clusterbody($sys_config,"Batch system info");
    $ucl=usercaps($sys_db_con);
    if ($ucl["jsi"]) {
        $rslist=array("JobID"=>array("JobID","jobid"),
                      "User"=>array("UserName","user"),
                      "Nodes"=>array("number of nodes","numnodes"),
                      "JobName"=>array("JobName","jobname"),
                      "Time el."=>array("Time elapsed","t0"),
                      "Time left"=>array("Time left","t1"),
                      "Load"=>array("Load Average","l1"));
        if (isset($vars["stype"])) {
            $rstype=$vars["stype"];
        } else {
            $rstype="JobID";
        }
        if ($vars["asc_sort"] == $rstype) {
            $sort_dir="ascending";
            $hidden_sort_dir="<input type=hidden name=\"desc_sort\" value=\"{$rstype}\" />\n";
        } else {
            $sort_dir="descending";
            $hidden_sort_dir="<input type=hidden name=\"asc_sort\" value=\"{$rstype}\" />\n";
        }
        //print_r($vars);
        //echo "*$rstype*$sort_dir*<br>";
        $rsstr=$rslist[$rstype][0].", $sort_dir";
        $short_sort=$rslist[$rstype][1];
        # get all nodes
        $mrs=query("SELECT d.name FROM device d, config c, deviceconfig dc WHERE dc.device=d.device_idx AND dc.config=c.config_idx AND (c.name='openpbs_mom' OR c.name='sge_client')");
        $node_list=array();
        while ($mfr=mysql_fetch_object($mrs)) {
            $node_list[$mfr->name]=new node($mfr->name);//array("name"=>$mfr->name,"down"=>0,"res"=>array(),"used"=>0,"jobs"=>array());
        }
//         foreach ($node_list as $node=>$stuff) {
//             echo "$node - ";
//             print_r($stuff["jobs"]);
//             echo "<br>";
//         }
        //print_r($node_list);
        $sge_stuff=call_pure_external("export SGE_CELL=srocell ; export SGE_ROOT=/opt/sge ; export PATH=$PATH:/opt/sge/bin/glinux ; /opt/sge/bin/glinux/sgestat -r -R cnj -n -s");
        //print_r($sge_stuff);
        $act_mode="?";
        $act_line_num=0;
        $complexes=array();
        $jobs_r=array();
        $jobs_q=array();
        $num_down=0;
        $num_alarm=0;
        $num_used=0;
        foreach ($sge_stuff as $sge_line) {
            if ($sge_line[0] == ":") {
                preg_match("/^:run-mode\s+(.)\s+.*$/",$sge_line,$sge_p);
                $act_mode=$sge_p[1];
                $act_line_num=0;
            } else {
                $act_line_num++;
                $sge_split=explode(";",$sge_line);
                if ($act_line_num > 1) {
                    if ($act_mode == "c") {
                        $c_name=$sge_split[0];
                        $complexes[$c_name]=new complex($c_name);
                        $new_c=&$complexes[$c_name];
                        $new_c->pe_list=explode(",",$sge_split[1]);
                        $new_c->max_nodes=$sge_split[2];
                        $new_c->max_walltime=$sge_split[3];
                        $new_c->max_n_walltime=$sge_split[4];
                        $new_c->waiting=(int)$sge_split[5];
                        $new_c->running=(int)$sge_split[6];
                        $new_c->nodes_total=(int)$sge_split[7];
                        $new_c->nodes_up=(int)$sge_split[8];
                        $new_c->nodes_available=(int)$sge_split[9];
                        $new_c->nodes_error=(int)$sge_split[12];
                        $new_c->node_list=$sge_split[13];
                    } else if ($act_mode == "j") {
                        $job_id=$sge_split[0];
                        $job_name=$sge_split[2];
                        $num_nodes=$sge_split[3];
                        $user=$sge_split[4];
                        $job_stat=$sge_split[5];
                        $c_list=explode(",",$sge_split[6]);
                        $qr_time=$sge_split[7];
                        if ($job_stat == "r") {
                            $num_used+=$num_nodes;
                            $jobs_r[$job_id]=new job($job_id,explode(",",$sge_split[11]),$num_nodes,$user,$job_name,$qr_time,$c_list,$sge_split[10],$sge_split[8],$sge_split[9]);
                            $jobs_r[$job_id]->sort_crit=$short_sort;

                        } else if (preg_match("/q/",$job_stat)) {
                            $jobs_w[$job_id]=new job($job_id,array(),$num_nodes,$user,$job_name,$qr_time,$c_list,0.,"0","0");
                        }
                    } else if ($act_mode == "n") {
                        preg_match("/^(\D+\d+).*$/",$sge_split[0],$nn_p);
                        $node_name=$nn_p[1];
                        if (in_array($node_name,array_keys($node_list))) {
                            $node_stat=$sge_split[1];
                            if (preg_match("/d/",$node_stat) || preg_match("/u/",$node_stat)) {
                                $node_list[$node_name]->down=1;
                                $num_down++;
                            } else if (preg_match("/a/",$node_stat)) {
                                $node_list[$node_name]->alarm=1;
                                $num_alarm++;
                            }
                        } else {
                            echo "Error: node $node_name is not known to the underlying database<br>";
                        }
                    }
                }
            }
        }
        $jobrn=count($jobs_r);
        $jobwn=count($jobs_w);
        $all_nodes=sizeof(array_keys($node_list));
        $jobhn=0;
        $users=array();
        if (count($jobs_w)) usort($jobs_w,"my_job_cmp");
        // sort running jobs according to $rstype
        uasort($jobs_r,"my_job_cmp_2");
        $act_rjl=array_keys($jobs_r);
        if ($sort_dir == "ascending") $act_rjl=array_reverse($act_rjl,FALSE);
        $out_a=array();
        foreach (array(array($jobrn,"running"),array($jobwn,"waiting"),array($jobhn,"held")) as $jota) {
            list($val,$what)=$jota;
            $act_str="$val ".get_plural("job",$val)." $what";
            if ($what == "running") {
                $act_str.=sprintf(" on %d of %d (%d down, %d alarm) nodes",$num_used,$all_nodes,$num_down,$num_alarm);
            }
            $out_a[]=$act_str;
        }
        message(implode(", ",$out_a));
        if (sizeof($jobs_r)==0) {
            message("No jobs running");
        } else {
            message("Table of running jobs (sorted by ".$rsstr.")");
            echo "<form action=\"/php/jobsysinfo.php?".write_sid()."\" method=post>";
            echo $hidden_sort_dir;
            echo "<table class=\"normal\">\n";
            echo "<tr>";
            foreach (array(array(1,"user","User"),array(1,"id","JobID"),array(0,"exhost","Queue(s)"),
                           array(1,"excpu","Nodes"),array(1,"jobh","JobName"),array(1,"time","Time el."),
                           array(1,"wall","Time left"),array(0,"vmem","Complex"),array(1,"meanload","Load")) as $stuff) {
                list($is_button,$class,$but_name)=$stuff;
                echo "<th class=\"$class\">";
                if ($is_button) {
                    echo "<input type=submit name=\"stype\" value=\"$but_name\" />";
                } else {
                    echo "$but_name";
                }
                echo "</th>\n";
            }
            echo "</tr>\n";
            foreach ($act_rjl as $jid) {
                echo "<tr>";
                $jr=&$jobs_r[$jid];
                echo $jr->get_user(),$jr->get_id(),$jr->get_host(),$jr->get_nodenum(),$jr->get_name();
                echo $jr->get_time_run(),$jr->get_time_left(),$jr->get_queue(),$jr->get_mean_load();
                echo "</tr>\n";
            } 
            echo "</table></form>";
        }
        if (sizeof($jobs_w)==0) {
            message ("No jobs waiting");
        } else {
            message ("Table of waiting jobs");
            echo "<table class=\"normal\">\n";
            echo "<tr><th class=\"user\">User</th><th class=\"id\">ID</th>\n";
            //foreach (array("Pri","Cred","FS","QTime","XFctr","Bypass") as $header) {
            //    echo "<th class=\"pri\">$header</th>\n";
            //}
            echo "<th class=\"jobh\">Jobname</th><th class=\"wall\">req. nodes</th><th class=\"qu\">Complex</th>\n";
            echo "<th class=\"vmem\">qtime</th></tr>\n";
            foreach ($jobs_w as $jq) {
                echo "<tr>";
                echo $jq->get_user(),$jq->get_id(),$jq->get_name();
                echo $jq->get_nodenum(),$jq->get_queue(),$jq->get_time();//$jq->get_vmem();
                echo "</tr>\n";
            } 
            echo "</table>";
        }
        if (sizeof($myjobsh)) {
            message ("Table of held jobs");
            echo "<table class=\"normal\">\n";
            echo "<tr><th class=\"user\">User</th><th class=\"id\">ID</th><th class=\"pri\">Depends on</th>\n";
            echo "<th class=\"jobh\">Jobname</th><th class=\"wall\">req. nodes</th><th class=\"qu\">Complex</th></tr>\n";
            foreach ($myjobsh as $jq) {
                echo "<tr>";
                echo $jq->get_user(),$jq->get_id(),$jq->get_depend($myjobst),$jq->get_name();
                echo $jq->get_wall(),$jq->get_queue();
                echo "</tr>\n";
            } 
            echo "</table>";
        } else {
            message ("No jobs held");
        }
        message("Complex configuration");
        echo "<table class=\"normal\">\n";
        echo "<tr>";
        echo "<th class=\"qu\">Name</th>";
        echo "<th class=\"id\">PE-List</th>";
        echo "<th class=\"qummc\">Max. cpus</th>";
        echo "<th class=\"quwt\">Max. walltime</th>";
        echo "<th class=\"quwt\">Max. walltime/n</th>";
        echo "<th class=\"qucs\">W</th>";
        echo "<th class=\"id\">R</th>";
        echo "<th class=\"qu\"># of nodes</th>";
        echo "<th class=\"qu\">Nodes up</th>";
        echo "<th class=\"qu\">Free nodes</th>";
        echo "<th class=\"qu\">Error nodes</th>";
        echo "<th class=\"qu\">Machines</th>";
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
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
