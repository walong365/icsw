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
function check_time($int) {
    if (preg_match("/^0(\d.*)$/",$int,$subint)) {
        return $subint[1];
    } else {
        return $int;
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
    $hours=(int)($sec/3600);
    $rsec=$sec-$hours*3600;
    $mins=(int)($rsec/60);
    $rsec=$rsec-$mins*60;
    return sprintf("%02.2d:%02.2d:%02.2d",$hours,$mins,$rsec);
}
function str_to_sec($str) {
    $str_parts=explode(":",$str);
    $secs=0;
    foreach ($str_parts as $act_s) {
        $secs*=60;
        $secs+=(int)$act_s;
    }
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
        $this->load_avg=$load_avg;
        $this->qtime=$qtime;
        $this->depend="";
        $this->reqnodes=0;
        $this->pri_cred_class=0.;
        $this->pri_fs_user=0.;
        $this->pri_serv_qtime=0.;
        $this->pri_serv_xfctr=0.;
        $this->pri_serv_bypass=0.;
        //echo strval($this->user->fair_share)."<br>";
    }
    function set_depend($dep) {
        $dlist=preg_split("/,/",$dep);
        $this->depend=$dlist;
    }
    function get_name() { return "<td class=\"jobs\">$this->name</td>"; }
    function get_user() { return "<td class=\"user\">".$this->user."</td>"; }
    function get_host() { return "<td class=\"exhost\">".implode(" + ",$this->host)."</td>"; }
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
    function get_time() { return "<td class=\"time\">".sec_to_str($this->time)."</td>"; }
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
    clusterhead($sys_config,"Batch system information page",$style="formate.css");
    clusterbody($sys_config,"Batch system info");
    $ucl=usercaps($sys_db_con);
    if ($ucl["jsi"]) {
        $rslist=array("id"=>"JobID","user"=>"UserName","nodes"=>"number of nodes","jobname"=>"JobName","rtime"=>"Time elapsed","ltime"=>"Time left");
        $rstype="id";
        $rsstr=$rslist[$rstype].", descending";
        foreach (array_keys($rslist) as $rspos) {
            if ($vars[$rspos]) {
                $rsstr=$rslist[$rspos].", descending";
                $rstype=$rspos;
            } elseif ($vars["N".$rspos]) {
                $rsstr=$rslist[$rspos].", ascending";
                $rstype="N$rspos";
            }
        }
        # get all nodes
        $mrs=query("SELECT d.name FROM device d, config c, deviceconfig dc WHERE dc.device=d.device_idx AND dc.config=c.config_idx AND c.name='openpbs_mom'");
        $node_list=array();
        while ($mfr=mysql_fetch_object($mrs)) {
            $node_list[$mfr->name]=array("name"=>$mfr->name,"down"=>0,"res"=>array(),"used"=>0,"jobs"=>array());
        }
//         foreach ($node_list as $node=>$stuff) {
//             echo "$node - ";
//             print_r($stuff["jobs"]);
//             echo "<br>";
//         }
        //print_r($node_list);
        $sge_stuff=call_pure_external("export SGE_CELL=srocell ; export SGE_ROOT=/opt/sge ; export PATH=$PATH:/opt/sge/bin/glinux ; /opt/sge/bin/glinux/sgestat -r -m cnj -n");
        //print_r($sge_stuff);
        $act_mode="?";
        $act_line_num=0;
        $complexes=array();
        $jobs_r=array();
        $jobs_q=array();
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
                            $jobs_r[$job_id]=new job($job_id,explode(",",$sge_split[11]),$num_nodes,$user,$job_name,$qr_time,$c_list,$sge_split[10],$sge_split[8],$sge_split[9]);
                        } else if ($job_stat == "q") {
                            $jobs_w[$job_id]=new job($job_id,array(),$num_nodes,$user,$job_name,$qr_time,$c_list,0.,"0","0");
                        }
                    }
                }
            }
        }
        $jobrn=count($jobs_r);
        $jobwn=count($jobs_w);
        $stand_res=call_pure_external("/opt/maui/bin/diagnose -r");
        $srlist=array();
        $sr_state="FLAG";
        foreach ($stand_res as $sr_line) {
            if ($sr_state=="FLAG" && preg_match("/STANDINGRES/",$sr_line)) {
                $sr_state="ACL";
            } else if ($sr_state=="ACL" && preg_match("/ACL:\s+RES==([^=]+)=\s+CLASS==(.*)\+$/",$sr_line,$sll)) {
                $sr_name=$sll[1];
                $sr_classes=(preg_split("/\+:==/",$sll[2]));
                $sr_state="NODES";
            } else if ($sr_state=="NODES" && preg_match("/Attributes\s+\(HostList='(.*)'\)/",$sr_line,$hlist)) {
                $hl_pregs=preg_split("/\s+/",$hlist[1]);
                $sr_state="FLAG";
                $sr_nl=array();
                foreach ($node_list as $act_node=>$node_stuff) {
                    foreach ($hl_pregs as $act_preg) {
                        if (preg_match("/$act_preg/",$act_node)) {
                            $sr_nl[]=$act_node;
                        }
                    }
                }
                $sr_list[$sr_name]=new sres($sr_name);
                $sr_list[$sr_name]->set_classes($sr_classes);
                $sr_list[$sr_name]->set_nodes($sr_nl);
            }
        }
        #print_r($sr_list);
//         $mcfgn=get_root_dir()."/php/maui/maui.cfg";
//         if (file_exists($mcfgn)) {
//             $mcfg=file($mcfgn);
//             foreach ($mcfg as $line) {
//                 if (preg_match("/^SRCFG\[(.*)\]\s+(.*)=(.*)$/",$line,$lss)) {
//                     $name=$lss[1];
//                     $what=$lss[2];
//                     $arg=$lss[3];
// #echo $idx." : ".$name."<br>";
//                     if (! $srlist[$name]) {
//                         $srlist[$name]=new sres();
//                     }
// #echo $idx,$name,$arg,"<br>";
//                     $srlist[$name]->set_arg($what,$arg);
//                 }
//             }
//         }
    
//         $nodes_used=0;
//         $node_list=array();
//         foreach ($srlist as $sr) {
//             foreach ($sr->hlist as $host) {
//                 if (! in_array($host,array_keys($node_list))) {
//                     $node_list[$host]=0;
//                 }
//             }
//         }
//         ksort($node_list);
        $all_nodes=sizeof(array_keys($node_list));
        $mres=query("SELECT d.name FROM device d, config c, deviceconfig mc WHERE mc.device=d.device_idx AND mc.config=c.config_idx AND c.name='openpbs_server'",$sys_db_con);
        if (mysql_affected_rows()) {
            $mr=mysql_fetch_object($mres);
            $pbs_server=$mr->name;
            $pbs_server="fs11";
            $num_down=0;
            $downlist=call_pure_external("/opt/openpbs/bin/pbsnodes -al -s $pbs_server");
            foreach ($downlist as $downline) {
                if (preg_match("/^(\S+)\s+(\S+)$/",$downline,$downpart)) {
                    $node_list[$downpart[1]]["down"]=1;
                    $num_down++;
                }
            }
            $queues=array();
            $queue_snames=array();
            //print_r($pbs_server); 
            $pbs_server="fs11";
//             $qsplit=call_pure_external("/opt/openpbs/bin/qstat -Qf @$pbs_server");
//             foreach ($qsplit as $qline) {
//                 $line=trim($qline);
//                 if (strlen($line)) {
//                     if (preg_match("/^Queue: (.*)$/",$line,$qns)) {
//                         $qname=$qns[1];
//                         $queues[$qname]=new queue($qname);
//                         $act_queue=&$queues[$qname];
//                         if (preg_match("/^(.*)_(\d+)$/",$qname,$rqname)) {
//                             $nqname=$rqname[1];
//                             $subname=intval($rqname[2]);
//                         } else {
//                             $nqname=$qname;
//                             $subname=0;
//                         }
//                         $act_queue->short_name=$nqname;
//                         if (!in_array($nqname,array_keys($queue_snames))) $queue_snames[$nqname]=array();
//                         if ($subname) $queue_snames[$nqname][]=$subname;
//                     } else if (preg_match("/^\s*(\S+) \= (.*)$/",$line,$lss)) {
//                         if ($lss[1]=="queue_type") {
//                             $act_queue->type=substr($lss[2],0,1);
//                         } else if ($lss[1]=="enabled") {
//                             if ($lss[2]=="True") $act_queue->enabled="yes";
//                         } else if ($lss[1]=="started") {
//                             if ($lss[2]=="True") $act_queue->started="yes";
//                         } else if ($lss[1]=="Priority") {
//                             $act_queue->pri=$lss[2];
//                         } else if (preg_match("/^resources_([^\.]+)\.(.*)$/",$lss[1],$rst)) {
//                             if ($rst[1]=="min") {
//                                 if ($rst[2]=="nodect") {
//                                     $act_queue->min_cpus=$lss[2];
//                                 }
//                             } else if ($rst[1]=="max") {
//                                 if ($rst[2]=="nodect") {
//                                     $act_queue->max_cpus=$lss[2];
//                                 } else if ($rst[2]=="walltime") {
//                                     $act_queue->max_walltime=check_time($lss[2]);
//                                 }
//                             }
//                         } else if ($lss[1] == "state_count") {
//                             preg_match("/^\S+:(\d+) \S+:(\d+) \S+:(\d+) \S+:(\d+) \S+:(\d+) \S+:(\d+)$/",$lss[2],$rst);
//                             $act_queue->transit=intval($rst[1]);
//                             $act_queue->queued=intval($rst[2]);
//                             $act_queue->held=intval($rst[3]);
//                             $act_queue->waiting=intval($rst[4]);
//                             $act_queue->running=intval($rst[5]);
//                             $act_queue->exiting=intval($rst[6]);
//                         }
//                     }
//                 }
//             }
            ksort($queues);
            $totname="total";
            $queue_snames[$totname]=array();
            $qsplit=call_pure_external("/opt/openpbs/bin/qstat -f @$pbs_server");
            //$jobrn=0;
            //$jobqn=0;
            $jobhn=0;
            $qsplit[]="";
            $oline="";
            $users=array();
//             $myjobsh=array();
//             $myjobst=array();
// # dirty hack against to early recognition of END-OF-RECORD
//             $vlfound=0;
//             for ($i=0;$i < sizeof($qsplit)-1;$i++) {
//                 $line=$oline.trim($qsplit[$i]);
//                 if (ord(substr($qsplit[$i+1],0,1)) == 9) {
//                     $oline=$line;
//                 } else {
//                     $oline="";
//                     if (preg_match("/^Job Id: (\d+).*$/",$line,$lls)) {
//                         $jobid=$lls[1];
//                         $jobtime=0;
//                         $jobwall=0;
//                         $depend="";
//                         $jobnodes=1;
//                         $comment="???";
//                         //echo ":: $jobid<br>";
//                     } elseif (strlen($line)==0 && $vlfound) {
//                         if (! in_array($jobuser,array_keys($users))) {
//                             $users[$jobuser]=new user($jobuser);
//                         }
//                         $newuser=&$users[$jobuser];
//                         $vlfound=0;
//                         if ($jobstate=="R") {
//                             $myjobl="";
//                             foreach ($jobhost as $host) {
//                                 preg_match("/^([^\/]+)\/(\d+)$/",$host,$qls);
//                                 if (strlen($myjobl)) $myjobl.=" + ";
//                                 $myjobl.=$qls[1].".$qls[2]";
//                             }
//                             $njob=new job($jobid,$myjobl,sizeof($jobhost),&$newuser,$jobname,$jobtime,$queues[$jobqu],$jobwall,$jobvmem,$qtime);
//                             $myjobsr[$jobid]=$njob;
//                             $myjobst[]=$njob;
//                             $jobrn++;
//                             $nodes_used+=sizeof($jobhost);
//                             foreach ($jobhost as $host) {
//                                 if (preg_match("/^([^\/]+)\/.*$/",$host,$host_m)) {
//                                     // check for down node
//                                     if (!$node_list[$host_m[1]]["down"]) {
//                                         $node_list[$host_m[1]]["used"]++;
//                                         $node_list[$host_m[1]]["jobs"]=array();
//                                     }
//                                 }
//                             }
//                         } elseif ($jobstate=="Q") {
//                             $njob=new job($jobid,"---","---",&$newuser,$jobname,"---",$queues[$jobqu],0,$comment,$qtime);
//                             $njob->reqnodes=$jobnodes;
//                             $myjobsq[]=$njob;
//                             $myjobst[]=$njob;
//                             $jobqn++;
//                         } elseif ($jobstate=="H") {
//                             $jobhn++;
//                             $njob=new job($jobid,"---","---",&$newuser,$jobname,"---",$queues[$jobqu],$jobnodes,$comment,$qtime);
//                             $njob->set_depend($depend);
//                             $myjobsh[]=$njob;
//                             $myjobst[]=$njob;
//                         }
//                         if (!$MAX_JOBS--) break;
//                     } elseif (preg_match("/^Variable_List = (.*)$/",$line)) {
//                         $vlfound=1;
//                     } elseif (preg_match("/^Job_Name = (.*)$/",$line,$qls)) {
//                         $jobname=$qls[1];
//                     } elseif (preg_match("/^Job_Owner = ([^\@]+).*$/",$line,$qls)) {
//                         $jobuser=$qls[1];
//                     } elseif (preg_match("/^job_state = (.*)$/",$line,$qls)) {
//                         $jobstate=$qls[1];
//                     } elseif (preg_match("/^resources_used\.cput = (\d+):(\d+):(\d+)$/",$line,$qls)) {
//                         $jobtime=(((int) $qls[1])*60+(int)$qls[2])*60+(int)$qls[3];
//                     } elseif (preg_match("/^resources_used\.vmem = (\d+).*$/",$line,$qls)) {
//                         $jobvmem=(int)(((int) $qls[1])/1024);
//                     } elseif (preg_match("/^resources_used\.walltime = (\d+):(\d+):(\d+)$/",$line,$qls)) {
//                         $jobwall=(((int) $qls[1])*60+(int)$qls[2])*60+(int)$qls[3];
//                     } elseif (preg_match("/^Resource_List.nodes = (\d+).*$/",$line,$qls)) {
//                         $jobnodes=$qls[1];
//                     } elseif (preg_match("/^queue = (.*)$/",$line,$qls)) {
//                         $jobqu=$qls[1];
//                     } elseif (preg_match("/^qtime = (.*)$/",$line,$qls)) {
//                         $qtime=$qls[1];
//                     } elseif (preg_match("/^depend = (.*)$/",$line,$qls)) {
//                         $depend=$qls[1];
//                     } elseif (preg_match("/^exec_host = (.*)$/",$line,$qls)) {
//                         $jobhostl=$qls[1];
//                         $jobhost=preg_split("/\+/",$jobhostl);
//                     } elseif (preg_match("/.*comment.*/",$line)) {
//                         $qls=preg_split("/\=/",$line);
//                         $comment=$qls[1];
//                     }
//                 }
//             }
// //            foreach ($node_list as $node=>$stuff) {
// //                if (count($stuff["jobs"])) {
// //                    echo "$node - ";
// //                    print_r($stuff["jobs"]);
// //                    echo "<br>";
// //                }
// //            }
//             // get prorities
//             $qs2=call_pure_external("/opt/maui/bin/diagnose -p");
//             foreach ($qs2 as $qsline) {
//                 if (preg_match("/^\s+Weights\s+--------\s+[^\(]+\(([^\)]+)\)\s+[^\(]+\(([^\)]+)\)[^\(]+\(([^:]+):([^:]+):([^:]+)\).*$/",$qsline,$qss)) {
//                     $w_cred_class=doubleval($qss[1]);
//                     $w_fs_user=doubleval($qss[2]);
//                     $w_serv_qtime=abs(doubleval($qss[3]));
//                     $w_serv_xfctr=abs(doubleval($qss[4]));
//                     $w_serv_bypass=abs(doubleval($qss[5]));
//                     //echo "$w_cred_class $w_fs_user $w_serv_qtime $w_serv_xfctr $w_serv_bypass<br>\n";
//                 } elseif (preg_match("/^(\d+)\s+(-*\d+)\s+[^\(]+\(([^\)]+)\)\s+[^\(]+\(([^\)]+)\)[^\(]+\(([^:]+):([^:]+):([^:]+)\).*$/",$qsline,$qss)) {
//                     foreach (array_keys($myjobsq) as $mjqk) {
//                         $mjq=&$myjobsq[$mjqk];
//                         if ($mjq->id == $qss[1]) {
//                             $mjq->pri=$qss[2];
//                             $mjq->pri_cred_class=doubleval($qss[3])*$w_cred_class;
//                             $mjq->pri_fs_user=doubleval($qss[4]);
//                             $mjq->pri_serv_qtime=abs(doubleval($qss[5]));
//                             $mjq->pri_serv_xfctr=abs(doubleval($qss[6]));
//                             $mjq->pri_serv_bypass=abs(doubleval($qss[7]));
// #echo $qss[1],$qss[2],"<br>";
//                         }
//                     }
//                 }
//             }
//             $user_list=array_keys($users);
//             $qs2=call_pure_external("/opt/maui/bin/diagnose -f");
//             foreach ($qs2 as $qsline) {
//                 if (preg_match("/^([^\*]+)\*\s+(\d+\.\d+)\s+.*$/",$qsline,$fsinfo)) {
//                     if (in_array($fsinfo[1],$user_list)) {
//                         $user=&$users[$fsinfo[1]];
//                         $user->fair_share=doubleval($fsinfo[2]);
//                     }
//                 }
//             }

            usort($jobs_q,"my_job_cmp");
            // sort running jobs according to $rstype
            $act_rjl=array_keys($jobs_r);
            if (substr($rstype,0,1) == "N") {
                $dir=1;
                $rrstype=substr($rstype,1);
            } else {
                $dir=0;
                $rrstype=$rstype;
            }
            $cont=1;
            while ($cont) {
                $cont=0;
                for ($i=0 ; $i < sizeof($act_rjl)-1 ; $i++) {
                    if ($dir) {
                        $j2=&$jobs_r[$act_rjl[$i]];
                        $j1=&$jobs_r[$act_rjl[$i+1]];
                    } else {
                        $j1=&$jobs_r[$act_rjl[$i]];
                        $j2=&$jobs_r[$act_rjl[$i+1]];
                    }
                    $swap=0;
                    switch ($rrstype) {
                    case "id":
                        if ($j1->id < $j2->id) {
                            $swap=1;
                        }
                        break;
                    case "user":
                        if ($j1->user->name < $j2->user->name) {
                            $swap=1;
                        }
                        break;
                    case "nodes":
                        if ($j1->nodenum < $j2->nodenum) {
                            $swap=1;
                        }
                        break;
                    case "jobname":
                        if ($j1->name < $j2->name) {
                            $swap=1;
                        }
                        break;
                    case "rtime":
                        if ($j1->time_run < $j2->time_run) {
                            $swap=1;
                        }
                        break;
                    case "ltime":
                        if ($j1->time_left < $j2->time_left) {
                            $swap=1;
                        }
                        break;
                    }
                    if ($swap) {
                        $cont=1;
                        $tempidx=$act_rjl[$i];
                        $act_rjl[$i]=$act_rjl[$i+1];
                        $act_rjl[$i+1]=$tempidx;
                    }
                }
            }

//             $c_class=array();
//             foreach (array_keys($queue_snames) as $qu) {
//                 if ($qu == $totname) {
//                     $c_class[$qu]["class"]="qtot";
//                 } else {
//                     $c_class[$qu]["class"]="qnum";
//                 }
//                 $qnum[$qu]["sepp"]=0;
//                 $nnum[$qu]["sepp"]=0;
//                 foreach ($user_list as $du) {
//                     $qnum[$qu][$du]=0;
//                     $nnum[$qu][$du]=0;
//                 }
//             }
//             foreach (array_keys($jobs_r) as $jid) {
//                 $nqname=$jobs_r[$jid]->qu->short_name;
//                 $qnum[$nqname][$jobs_r[$jid]->user->name]++;
//                 $nnum[$nqname][$jobs_r[$jid]->user->name]+=$jobs_r[$jid]->nodenum;
//                 $qnum[$totname][$jobs_r[$jid]->user->name]++;
//                 $nnum[$totname][$jobs_r[$jid]->user->name]+=$jobs_r[$jid]->nodenum;
//                 $qnum[$nqname]["sepp"]++;
//                 $nnum[$nqname]["sepp"]+=$jobs_r[$jid]->nodenum;
//                 $qnum[$totname]["sepp"]++;
//                 $nnum[$totname]["sepp"]+=$jobs_r[$jid]->nodenum;
//             }
            $out="Overview: ";
            $first=1;
            foreach (array(array($jobrn,"running"),array($jobqn,"waiting"),array($jobhn,"held")) as $jota) {
                if ($first) {
                    $first=0;
                } else {
                    $out.=", ";
                }
                list($val,$what)=$jota;
                $out.="$val ".get_plural("job",$val)." $what";
                if ($what == "running") {
                    $out.=sprintf(" on %d of %d (%d down) nodes",$nodes_used,$all_nodes,$num_down);
                }
            }
            message($out);
            if (sizeof($jobs_r)==0) {
                message("No jobs running");
            } else {
                message("Table of running jobs (sorted by ".$rsstr.")");
                echo "<form action=\"/php/jobsysinfo.php?".write_sid()."\" method=post>";
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"user\"><input type=submit name=\"";
                if ($rstype == "user") echo "N";
                echo "user\" value=\"User\"></input></th>";
                echo "<th class=\"id\"><input type=submit name=\"";
                if ($rstype == "id") echo "N";
                echo "id\" value=\"JobID\"></input></th>\n";
                echo "<th class=\"exhost\" width=32%>Hostname</th>\n";
                echo "<th class=\"excpu\"><input type=submit name=\"";
                if ($rstype == "nodes") echo "N";
                echo "nodes\" value=\"nodenum\"></input></th>\n";
                echo "<th class=\"jobh\"><input type=submit name=\"";
                if ($rstype == "jobname") echo "N";
                echo "jobname\" value=\"Jobname\"></input></th>";
                echo "<th class=\"time\"><input type=submit name=\"";
                if ($rstype == "time") echo "N";
                echo "rtime\" value=\"Time el.\"></input></th>\n";
                echo "<th class=\"wall\"><input type=submit name=\"";
                if ($rstype == "wall") echo "N";
                echo "ltime\" value=\"Time left\"></input></th>\n";
                echo "<th class=\"vmem\">Complex</th></tr>\n";
                //foreach (array_keys($jobs_r) as $jid) {
                foreach ($act_rjl as $jid) {
                    echo "<tr>";
                    $jr=&$jobs_r[$jid];
                    echo $jr->get_user(),$jr->get_id(),$jr->get_host(),$jr->get_nodenum(),$jr->get_name();
                    echo $jr->get_time_run(),$jr->get_time_left(),$jr->get_queue();
                    echo "</tr>\n";
                } 
                echo "</table></form>";
//                 message ("Table of running jobs / used nodes");
//                 echo "<table class=\"normal\">\n";
//                 echo "<tr><th class=\"user\">User</th>";
//                 foreach (array_keys($queue_snames) as $qu) {
//                     echo "<th class=\"".$c_class[$qu]["class"]."\">".$qu;
//                     if (sizeof($queue_snames[$qu])) {
//                         asort($queue_snames[$qu],SORT_NUMERIC);
//                         echo "(".implode(",",array_values($queue_snames[$qu])).")";
//                     }
//                     echo "</th>\n";
//                 }
//                 echo "</tr>\n";
      
//                 foreach ($user_list as $du) {
//                     $line_str="";
//                     $jobs_used=0;
//                     foreach (array_keys($queue_snames) as $qu) {
//                         $act_numq=$qnum[$qu][$du];
//                         $act_numn=$nnum[$qu][$du];
//                         if ($act_numq || $act_numn) {
//                             $out_str="$act_numq / $act_numn";
//                             $jobs_used=1;
//                         } else {
//                             $out_str="-";
//                         }
//                         $line_str.="<td class=\"".$c_class[$qu]["class"]."\">$out_str</td>";
//                     }
//                     if ($jobs_used) {
//                         echo "<tr>";
//                         echo "<td class=\"user\">".$du."</td>";
//                         echo $line_str;
//                         echo "</tr>\n";
//                     }
//                 } 
//                 echo "<tr>";
//                 echo "<td class=\"usert\">total</td>";
//                 foreach (array_keys($queue_snames) as $qu) {
//                     echo "<td class=\"qtot\">";
//                     if ($qnum[$qu]["sepp"]) {
//                         echo $qnum[$qu]["sepp"]." / ".$nnum[$qu]["sepp"];
//                     } else {
//                         echo "-";
//                     }
//                     echo "</td>";
//                 }
//                 echo "<tr>\n";
//                 echo "</table>";
            }
            if (sizeof($jobs_q)==0) {
                message ("No jobs waiting");
            } else {
                message ("Table of waiting jobs");
                echo "<table class=\"normal\">\n";
                echo "<tr><th class=\"user\">User</th><th class=\"id\">ID</th>\n";
                foreach (array("Pri","Cred","FS","QTime","XFctr","Bypass") as $header) {
                    echo "<th class=\"pri\">$header</th>\n";
                }
                echo "<th class=\"jobh\">Jobname</th><th class=\"wall\">req. nodes</th><th class=\"qu\">Complex</th>\n";
                echo "<th class=\"vmem\">qtime</th></tr>\n";
                foreach ($jobs_q as $jq) {
                    echo "<tr>";
                    echo $jq->get_user(),$jq->get_id(),$jq->get_pri(),$jq->get_name();
                    echo $jq->get_reqnodes(),$jq->get_queue(),$jq->get_qtime();//$jq->get_vmem();
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
            message("Can´t find a valid OpenPBS-Server.");
        }
    } else {
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
