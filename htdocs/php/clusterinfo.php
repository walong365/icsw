<?php
//-*ics*- ,CAPG,name:'info',descr:'Information',pri:10
//-*ics*- +CAP+name:'sc'+defvalue:0+enabled:1+descr:'Show Clusterinfo'+scriptname:'/php/clusterinfo.php'+left_string:'Overview'+right_string:'Short Cluster Summary'+capability_group_name:'info'+pri:-100
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
function fill_hosts_ji($machlist,$mcon) {
    $mres=query("SELECT m.name FROM machine m, config c, deviceconfig mc WHERE mc.machine=m.machine_idx AND mc.config=c.config_idx AND c.name='pbs_server'",$mcon);
    $hosts=&$GLOBALS["hosts"];
    $jobsfound=0;
    if (mysql_affected_rows()) {
        $mr=mysql_fetch_object($mres);
        $qsplit=call_pure_external("/usr/local/cluster/sbin/qstat ".$mr->name." -n");
        for ($i=5;$i < sizeof($qsplit)-1;$i++) {
            $line=$qsplit[$i];
            if (preg_match("/^\d+.*$/",$line)) {
                $lspl=preg_split("/\s+/",trim($line));
                preg_match("/^(\d+)\..*$/",$lspl[0],$jns);
                $jnum=$jns[1];
                $name=$lspl[1];
                $queue=$lspl[2];
                $jname=$lspl[3];
                $state=$lspl[9];
                $nline="";
                while (preg_match("/^   .*$/",$qsplit[$i+1])) {
                    $i++;
                    $nline.=trim($qsplit[$i]);
                }
                if ($state == "R") {
                    $nodes=preg_split("/\+/",$nline);
                    $j=0;
                    foreach ($nodes as $node) {
                        $j++;
                        $nnodes=sizeof($nodes);
                        preg_match("/^([^\/]+)\/(.*)$/",$node,$nns);
                        if (in_array($nns[1],$machlist)) {
                            $jobsfound=1;
                            if ($nnodes > 1) {
                                $hosts[$nns[1]]->jobs[]=$name." (".$jnum.") [".$jname."(".strval($j)."/".strval($nnodes).")]";
                            } else {
                                $hosts[$nns[1]]->jobs[]=$name." (".$jnum.") [".$jname."]";
                            }
                        }
                    }
                }
            }
        }
    }
    return $jobsfound;
}
class host {
    var $state,$load_1,$load_5,$load_15,$name,$alias,$cpu,$mb,$upt,$jobs,$mem,$memtot,$machinegroup,$pbs,$comment,$in_tot,$out_tot,$temps,$fans,$net_state,$disk_state,$disk_array;
    var $batch_clients,$load_state,$checks,$checks_ok,$checks_warning;
    function host($name,$alias,$mg,$comment) {
        $this->name=$name;
        $this->alias=$alias;
        $this->machinegroup=$mg;
        $this->comment=$comment;
        $this->state="NOTSET";
        $this->mem_state="UNKNOWN";
        $this->checks=0;
        $this->checks_ok=0;
        $this->num_checks_warning=0;
        $this->checks_warning=array();
        $this->num_checks_error=0;
        $this->checks_error=array();
        $this->mem=-1;
        $this->memtot=-1;
        $this->load_state="UNKNOWN";
        $this->load_1=-1;
        $this->load_5=-1;
        $this->load_15=-1;
        $this->cpu=-1;
        $this->cpus="OK";
        $this->mb=-1;
        $this->mbs="OK";
        $this->upt=array("-","-","-");
        $this->jobs=array();
        $this->pbs=0;
        $this->in_tot=0.;
        $this->out_tot=0.;
        $this->net_state="UNKNOWN";
        $this->disk_state="UNKNOWN";
        $this->disk_array=array();
        $this->temps=array();
        $this->fans=array();
        $this->batch_clients=array();
    }
    function set_state($state) {
        if ($this->state == "NOTSET") {
            $this->state=$state;
            $this->checks++;
            if ($this->state =="UP") {
                $this->checks_ok++;
            } else {
                $this->num_checks_error++;
                $this->checks_error[]="S";
            }
        }
    }
    function set_batch_type($btype) {
        $client_a=array("sge_client"=>array("sge","s"),"openpbs_mom"=>array("openpbs","o"),"pbspro_mom"=>array("pbspro","p"));
        $this->batch_clients[]=$client_a[$btype];
    }
    function get_batch_types() {
        $str="<td class=\"batchclient\">";
        if (count($this->batch_clients)) {
            $bc=array();
            foreach ($this->batch_clients as $act_c) {
                list($long,$short)=$act_c;
                $bc[]=$short;
            }
            $str.=implode("/",$bc);
        } else {
            $str.="---";
        }
        $str.="</td>\n";
        return $str;
    }
    function add_check($stat,$sc) {
        //echo "***$stat<br>";
        $this->checks++;
        if ($stat == "OK" || $stat == "RECOVERY") {
            $this->checks_ok++;
        } else if ($stat == "WARNING") {
            if (!in_array($sc,$this->checks_warning)) $this->checks_warning[]=$sc;
            $this->num_checks_warning++;
        } else {
            if (!in_array($sc,$this->checks_error)) $this->checks_error[]=$sc;
            $this->num_checks_error++;
        }
    }
    function add_temp($stat,$out) {
        $this->add_check($stat,"T");
        if (preg_match("/^.* (.+)-[T|t]emp has (\S+).*$/",$out,$out_m)) {
            if ($stat == "OK" || $stat== "RECOVERY") $tname=$out_m[1];
            $tval=(double)$out_m[2];
            $this->temps[$tname]=array($stat,$tval);
        }
    }
    function get_temp($tname) {
        $r_str="";
        if (in_array($tname,array_keys($this->temps))) {
            $r_str.="<td class=\"temp";
            list($tstat,$tval)=$this->temps[$tname];
            if ($tstat == "OK") {
                $r_str.="n";
            } elseif ($tstat == "WARNING") {
                $r_str.="w";
            } else {
                $r_str.="c";
            }
            $r_str.="\">$tval °C</td>\n";
        } else {
            $r_str.="<td class=\"tempn\">---</td>\n";
        }
        return $r_str;
    }
    function get_fan($fname) {
        $r_str="";
        if (in_array($fname,array_keys($this->fans))) {
            $r_str.="<td class=\"fan";
            list($fstat,$fval)=$this->fans[$fname];
            if ($fstat == "OK") {
                $r_str.="n";
            } elseif ($fstat == "WARNING") {
                $r_str.="w";
            } else {
                $r_str.="c";
            }
            $r_str.="\">$fval RPM</td>\n";
        } else {
            $r_str.="<td class=\"fann\">---</td>\n";
        }
        return $r_str;
    }
    function add_fan($stat,$out) {
        $this->add_check($stat,"F");
        if (preg_match("/^.* (.+)-[F|f]an has (\S+).*$/",$out,$out_m)) {
            $fname=$out_m[1];
            $fval=(double)$out_m[2];
            $this->fans[$fname]=array($stat,$fval);
#echo "<br>".$out_m[1]." - ".$out_m[2]."<br>";
        }
    }
    function add_net($stat,$out) {
        $this->add_check($stat,"N");
        if (preg_match("/^.*:\s+([\d\.]+) (.*)B\/s in. ([\d\.]+) (.*)B\/s out.*$/",$out,$out_m)) {
            $in_val=(double)$out_m[1];
            $out_val=(double)$out_m[3];
            $in_pfix=$out_m[2];
            $out_pfix=$out_m[4];
            if ($in_pfix == "K") $in_val*=1024.;
            if ($in_pfix == "M") $in_val*=1024.*1024.;
            if ($in_pfix == "G") $in_val*=1024.*1024.*1024.;
            if ($out_pfix == "K") $out_val*=1024.;
            if ($out_pfix == "M") $out_val*=1024.*1024.;
            if ($out_pfix == "G") $out_val*=1024.*1024.*1024.;
            $this->net_state=$stat;
            $this->in_tot+=$in_val;
            $this->out_tot+=$out_val;
        }
    }
    function get_net() {
        $r_str="<td class=\"";
        if ($this->state == "UP" && $this->net_state!="UNKNOWN") {
            $s_array=array();
            foreach (array($this->in_tot,$this->out_tot) as $val) $s_array[]=net_to_str($val);
            $r_str.="netn\">".implode(", ",$s_array);
        } else {
            $r_str.="netc\">no data";
        }
        $r_str.="</td>\n";
        return $r_str;
    }
    function add_disk($stat,$out) {
        $this->add_check($stat,"D");
        if (preg_match("/^.*-\s+([\d\.]+) .*$/",$out,$out_m)) {
            $perc_full=(double)$out_m[1];
            $this->disk_state=$stat;
            $this->disk_array[]=$perc_full;
        }
    }
    function get_disk() {
        $r_str="<td class=\"";
        if ($this->state == "UP" && $this->disk_state != "UNKNOWN") {
            $r_str.="diskn\">".strval(min($this->disk_array))." % / ".strval(max($this->disk_array))." %";
        } else {
            $r_str.="diskc\">no data";
        }
        $r_str.="</td>\n";
        return $r_str;
    }
    function get_name() {
        $str="<td class=\"name\">$this->name";
        if (strlen($this->alias)) {
            $str.=", $this->alias";
        }
        $str.="</td>";
        return $str;
    }
    function get_uptime() {
        if ($this->state == "UP") {
            if ($this->upt[0] == "-") {
                $str="no data";
            } else {
                $str="up since";
                if ($this->upt[0]) {
                    $str.=" ".$this->upt[0]." day";
                    if ($this->upt[0] > 1) $str.="s";
                }
                $str.=sprintf(" %02d:%02d",$this->upt[1],$this->upt[2]);
            }
        }
        return $str;
    }
    function get_loads($load) {
        if ($this->state != "UP" || $this->load_state=="UNKNOWN") {
            $str="<td class=\"loadc\">no data</td>";
        } else {
            $str="<td class=\"";
            if ($this->load_state == "OK") {
                $str.="loadn";
            } elseif ($this->load_state =="WARNING") {
                $str.="loadw";
#} elseif ($load < 3.5) {
#	$str.="loade";
} else {
	$str.="loadc";
}
 $str.="\">".sprintf("%2.2f",$load)."</td>";
        }
        return $str;
    }
    function set_memory($stat,$out) {
        $this->add_check($stat,"M");
        if (preg_match("/.*(\d+) % of .*, (\d+) % of .*$/",$out,$split)) {
            $this->mem_state=$stat;
            $this->mem=$split[1];
            $this->memtot=$split[2];
        }
    }
    function get_memory() {
        if ($this->mem == -1) {
            $str="<td class=\"memc\">no data</td>";
        } else {
            $str="<td class=\"";
            if ($this->mem_state == "OK") {
                $str.="memn";
            } elseif ($this->mem == "WARNING") {
                $str.="memw";
            } else {
                $str.="memc";
            }
            $str.="\">$this->mem / $this->memtot</td>";
        }
        return $str;
    }
    function set_loads($stat,$out) {
        $this->add_check($stat,"L");
        if (preg_match("/.*: (\S+) (\S+) (\S+)/",$out,$split)) {
            $this->load_state=$stat;
            $this->load_1=(float)$split[1];
            $this->load_5=(float)$split[2];
            $this->load_15=(float)$split[3];
        }
    }
    function get_load1()  { return $this->get_loads($this->load_1); }
    function get_load5()  { return $this->get_loads($this->load_5); }
    function get_load15() { return $this->get_loads($this->load_15); }
    function set_uptime($stat,$out) {
        $this->add_check($stat,"U");
        if (preg_match("/^.*Up for (\d+) days, (\d+) hours and (\d+) mins$/",$out,$split)) {
            $this->upt=array($split[1],$split[2],$split[3]);
        }
    }
    function get_cpu_temp() { return $this->get_temp($this->cpu,$this->cpus); }
    function get_mb_temp()  { return $this->get_temp($this->mb ,$this->mbs ); }
    function get_num_jobs() {
        $num=sizeof($this->jobs);
        return $num;
    }
    function get_jobs() {
        $cls="jobn";
        $str="none";
        for ($i=0;$i < sizeof($this->jobs);$i++) {
            if ($i == 0) {
                $str=$this->jobs[$i];
                $cls="jobs";
            } else {
                $str.="<br>".$this->jobs[$i];
            }
        }
        return "<td class=\"$cls\">$str</td>";
    }
}
function net_to_str($val) {
    if ($val < 500.) {
        $f_str="%.0f ";
    } else {
        $val/=1024.;
        if ($val < 500.) {
            $f_str="%.2f K";
        } else {
            $val/=1024.;
            if ($val < 500.) {
                $f_str="%.2f M";
            } else {
                $val/=1024.;
                $f_str="%.2f G";
            }
        }
    }
    return sprintf($f_str."B/s",$val);
}
function show_data_line($res,$sup_array,$addt) {
    if (!$sup_array["load"][1]) {
        foreach (array(0=>"load_1",1=>"load_5",2=>"load_15") as $idx=>$str) {
            if ($addt == "c" || !$res[$str]["set"]) {
                echo "<td class=\"load$addt\">no data</td>\n";
            } else {
                echo "<td class=\"load$addt\">".sprintf("%.2f / %.2f",$res[$str]["min"],$res[$str]["max"])."</td>\n";
            }
        }
    }
    if (!$sup_array["mem"][1]) {
        if ($addt == "c" || !$res["mem_p"]["set"]) {
            echo "<td class=\"mem$addt\">no data</td>\n";
            echo "<td class=\"mem$addt\">no data</td>\n";
        } else {
            echo "<td class=\"mem$addt\">".$res["mem_p"]["min"]." / ".$res["mem_p"]["max"]."</td>\n";
            echo "<td class=\"mem$addt\">".$res["mem_t"]["min"]." / ".$res["mem_t"]["max"]."</td>\n";
        }
    }
    if (!$sup_array["net"][1]) {
        if ($addt == "c" || !$res["net_in"]["set"]) {
            echo "<td class=\"net$addt\">no data</td>\n";
            echo "<td class=\"net$addt\">no data</td>\n";
        } else {
            foreach (array("net_in","net_out") as $net_array) {
                $s_array=array(net_to_str($res[$net_array]["min"]),net_to_str($res[$net_array]["max"]));
                echo "<td class=\"net$addt\">".implode(", ",$s_array)."</td>\n";
            }
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
} else if (! $sys_config["sc_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    // get list of machinegroups
    list($display_a,$machgroups,$hiddenmach,$actmach,$optsel)=get_display_list($vars,"");
    htmlhead();
    clusterhead($sys_config,"Cluster info page",$style="formate.css",
                array("th.load"=>array("background-color:#ffffff"),
                      "td.loadn"=>array("background-color:#eeffee","text-align:center"),
                      "td.loadw"=>array("background-color:#ccffcc","text-align:center"),
                      "td.loade"=>array("background-color:#aaffaa","text-align:center"),
                      "td.loadc"=>array("background-color:#88ff88","text-align:center"),
                      "th.mem"=>array("background-color:#f4f4ff"),
                      "td.mem"=>array("background-color:#fff4e4","text-align:center"),
                      "th.memn"=>array("background-color:#f4f4ff"),
                      "td.memn"=>array("background-color:#fff4e4","text-align:center"),
                      "td.memw"=>array("background-color:#fff4c4","text-align:center"),
                      "td.memc"=>array("background-color:#fff484","text-align:center"),
                      "th.temp"=>array("background-color:#ffffff"),
                      "th.tempn"=>array("background-color:#ffffff"),
                      "td.temp"=>array("background-color:#ffeeee","text-align:center"),
                      "td.tempn"=>array("background-color:#fff4e4","text-align:center"),
                      "td.tempw"=>array("background-color:#fff4c4","text-align:center"),
                      "td.tempc"=>array("background-color:#fff484","text-align:center"),
                      "th.gfx"=>array("background-color:#ffeeff"),
                      "td.gfx"=>array("background-color:#eeddee","text-align:center"),
                      "th.diskn"=>array("background-color:#e4f4e4"),
                      "td.diskn"=>array("background-color:#d4f4ef","text-align:center"),
                      "td.diskc"=>array("background-color:#64fff4","text-align:center"),
                      "th.netn"=>array("background-color:#f4f4f4"),
                      "td.netn"=>array("background-color:#e4f4ff","text-align:center"),
                      "td.netc"=>array("background-color:#84fff4","text-align:center"),
                      "th.fann"=>array("color:#000000","background-color:#ffffff","text-align:center"),
                      "td.fann"=>array("color:#000000","background-color:#ffeeff","text-align:center"),
                      "td.fanw"=>array("color:#000000","background-color:#ffccff","text-align:center"),
                      "td.fanc"=>array("color:#000000","background-color:#ff88ff","text-align:center"),
                      "a:link.cinfodd"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#ff5540"),
                      "a:visited.cinfodd"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#ff5540"),
                      "a:hover.cinfodd"=>array("font-weight:normal","color:#e0e0e0","text-decoration:none","background-color:#ff5540"),
                      "a:active.cinfodd"=>array("font-weight:normal","color:#ffffff","text-decoration:underline","background-color:#ff5540"),
                      "a:link.cinfodw"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#d0d030"),
                      "a:visited.cinfodw"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#d0d030"),
                      "a:hover.cinfodw"=>array("font-weight:normal","color:#0000e0","text-decoration:none","background-color:#d0d030"),
                      "a:active.cinfodw"=>array("font-weight:normal","color:#ffffff","text-decoration:underline","background-color:#d0d030"),
                      "a:link.cinfodu"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#ccffcc"),
                      "a:visited.cinfodu"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#ccffcc"),
                      "a:hover.cinfodu"=>array("font-weight:normal","color:#0000e0","text-decoration:none","background-color:#ccffcc"),
                      "a:active.cinfodu"=>array("font-weight:normal","color:#ffffff","text-decoration:underline","background-color:#ccffcc"),
                      "a:link.cinfodu2"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#cccce0"),
                      "a:visited.cinfodu2"=>array("font-weight:normal","color:#000000","text-decoration:none","background-color:#cccce0"),
                      "a:hover.cinfodu2"=>array("font-weight:normal","color:#0000e0","text-decoration:none","background-color:#cccce0"),
                      "a:active.cinfodu2"=>array("font-weight:normal","color:#ffffff","text-decoration:underline","background-color:#cccce0"),
                      "th.batchclient"=>array("background-color:#eeeeff","text-align:center"),
                      "td.batchclient"=>array("background-color:#aaaacc","text-align:center")
                      )
                );
    clusterbody($sys_config,"Cluster info",array("ch","bc"),array("info"));
    $ucl=usercaps($sys_db_con);
    if ($ucl["sc"]) {
        // Overview types
        $ov_types=array("List","Detailed");
        if (in_array("hidesel",array_keys($vars))) {
            $hide_selector=1;
        } else {
            $hide_selector=0;
        }
        if (in_array("ovtype",array_keys($vars))) {
            $act_ov_type=$vars["ovtype"];
        } else {
            $act_ov_type=$ov_types[0];
        }
        $act_ov_str="&ovtype=$act_ov_type";
        $sup_array=array("cmt"=>array("Comment",0),"upt"=>array("uptime",0),"mem"=>array("Memory",0),"load"=>array("Load",0),"net"=>array("Net",0),
                         "temp"=>array("Temperatures",0),"fan"=>array("Fans",0),"batch"=>array("BatchSys",0),"disk"=>array("Disk",0));
        if (count($machgroups)) {
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=get>";
            hidden_sid();
            if ($hide_selector) {
            } else {
                message ("Please select machinegroup or machine(s) by their name:");
                echo "<div class=\"center\">";
                echo "<table class=\"simplesmall\"><tr><td>";
                echo "<select name=\"selgroup[]\" multiple size=5>";
                foreach ($machgroups as $mg=>$mgv) {
                    echo "<option value=\"$mg\"";
                    if ($mgv["selected"]) echo " selected";
                    echo ">$mg";
                    if ($mgv["num"]) echo " ({$mgv['num']} ".get_plural("device",$mgv["num"]).")";
                    echo "\n";
                }
                echo "</select>";
                echo "</td>\n";
                echo "<td>&nbsp;&nbsp;</td>";
                echo "<td><select name=\"selmach[]\" size=5 multiple>";
                foreach ($machgroups as $act_group=>$display_g) {
                    if ($display_g["num"]) {
                        $num_mach=sizeof($display_g["list"]);
                        $mach_str=get_plural("machine",$num_mach);
                        echo "<option value=d disabled>$act_group [ $num_mach $mach_str ]\n";
                        $mres=query("SELECT d.name,d.comment FROM device d WHERE ( d.name='".implode("' OR d.name='",$display_g["list"])."')");
                        while ($mfr=mysql_fetch_object($mres)) {
                            echo "<option value=\"$mfr->name\"";
                            $name=$mfr->name;
                            if (in_array($name,$actmach)) echo " selected";
                            echo ">$name";
                            if ($mfr->comment) echo " ($mfr->comment)";
                            echo "\n";
                        }
                    }
                }
                echo "</select></td>";
                echo "</tr></table></div>\n";
            }
            echo "<table class=\"simplesmall\">\n";
            echo "<tr><td>Suppress display of</td>";
            $sup_ref_str="";
            foreach ($sup_array as $short=>$dlist) {
                list($long,$set)=$dlist;
                echo "<td>$long</td><td><input type=\"checkbox\" name=\"$short\" ";
                if (isset($vars[$short])) {
                    echo " checked ";
                    $sup_array[$short][1]=1;
                    $sup_ref_str.="&$short=on";
                }
                echo "/>, </td>";
            }
            echo "</tr></table>\n";
        } else {
            message("No machines found",$type=2);
        }
        $ref_str="{$act_ov_str}{$sup_ref_str}";
        if (count($display_a)) {
            if (sizeof($display_a) > 1) {
                $tot_mach=0;
                $tot_grp=0;
                foreach ($display_a as $lk=>$lv) {
                    $tot_grp+=1;
                    list($n1)=$lv;
                    $tot_mach+=$n1;
                }
                $mes_str="Found $tot_mach machines in $tot_grp machinegroups";
            } else {
                reset($display_a);
                list($n1,$n2,$mach_list)=current($display_a);
                if ($n1 == 1) {
                    $mes_str="Found machine ".$mach_list[0]." in machinegroup ".key($display_a);
                } else {
                    $mes_str="Found $n1 machines in machinegroup ".key($display_a);
                }
            }
            $mes_str.=", <input type=\"hidden\" name=\"ovtype\" value=\"$act_ov_type\" /><input type=submit value=\"select\" />";
            $mes_str.=", <a href=\"clusterinfo.php?".write_sid()."$ref_str\">Overview</a>";
            message($mes_str);
        } else {
            if (count($machgroups)) {
                $mes_str="Overview, mode is <select name=\"ovtype\">";
                foreach ($ov_types as $ov_type) {
                    $mes_str.="<option value=\"$ov_type\"";
                    if ($act_ov_type==$ov_type) $mes_str.=" selected ";
                    $mes_str.=">$ov_type";
                }
                $mes_str.="</select>, hide selector: <input type=checkbox name=\"hidesel\" ".($hide_selector ? " checked " : "")."/>, <input type=submit value=\"select\" />\n";
                message($mes_str);
            }
        }
        echo "</form>";
        if (!count($display_a)) {
            $mr2=query("SELECT d.name FROM device d, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier!='R'");
            $actmach=array();
            while ($mfr=mysql_fetch_object($mr2)) $actmach[]=$mfr->name;
        }
        $hname_selstr="( h.host_name='".implode("' OR h.host_name='",$actmach)."')";
        $mname_selstr="( d.name='".implode("' OR d.name='",$actmach)."')";
        // build host-array
        $hosts=array();
        $mr2=query("SELECT d.name,d.alias,dg.name AS mgname, d.comment FROM device d, device_group dg, device_type dt WHERE dt.device_type_idx=d.device_type AND $mname_selstr AND dg.device_group_idx=d.device_group AND dt.identifier != 'R'");
        while ($mfr=mysql_fetch_object($mr2)) {
            $name=$mfr->name;
            $hosts[$name]=new host($name,$mfr->alias,$mfr->mgname,$mfr->comment);
        }
        // check for batchsys-connectivity
        
        $mr2=query("SELECT d.name,c.name AS cname FROM device d, deviceconfig mc, config c WHERE d.device_idx=mc.device AND c.config_idx=mc.config AND (c.name='sge_client' OR c.name='openpbs_mom' OR c.name='pbspro_mom') AND $mname_selstr");
        if (mysql_num_rows($mr2)) {
            $batch_clients_found=1;
            while ($mfr=mysql_fetch_object($mr2)) $hosts[$mfr->name]->set_batch_type($mfr->cname);
        } else {
            $batch_clients_found=0;
        }
        // open connection to nagios db
        $mres=query("SELECT h.host_name,h.host_status,s.service_description AS descr, s.service_status AS status, s.plugin_output AS output FROM nagiosdb.servicestatus s, nagiosdb.hoststatus h WHERE s.host_name=h.host_name AND $hname_selstr ORDER BY h.host_name");
        if ($mres) {
            while ($mfr=mysql_fetch_object($mres)) {
                $name=$mfr->host_name;
                $acthost=&$hosts[$name];
                $acthost->set_state($mfr->host_status);
                $descr=$mfr->descr;
                if ($descr == "Memory" && !$sup_array["mem"][1]) {
                    $acthost->set_memory($mfr->status,$mfr->output);
                } elseif ($descr == "LoadLevel" && !$sup_array["load"][1]) {
                    $acthost->set_loads($mfr->status,$mfr->output);
                } elseif ($descr == "Uptime" && !$sup_array["upt"][1]) {
                    $acthost->set_uptime($mfr->status,$mfr->output);
                } elseif (preg_match("/^eth|lo.*$/",$descr) && !$sup_array["net"][1]) {
                    $acthost->add_net($mfr->status,$mfr->output);
                } elseif (preg_match("/^.*Temp.*$/",$descr) && !$sup_array["temp"][1]) {
                    $acthost->add_temp($mfr->status,$mfr->output);
                } elseif (preg_match("/^.*Fan.*$/",$descr) && !$sup_array["fan"][1]) {
                    $acthost->add_fan($mfr->status,$mfr->output);
                } elseif (preg_match("/\/.*$/",$descr) && !$sup_array["disk"][1]) {
                    $acthost->add_disk($mfr->status,$mfr->output);
                }
            }
        } else {
            message("No nagios database found",$type=2);
        }
        // determine configinfo command
        if (sizeof($display_a)) {
            $avail_temps=array();
            $avail_fans=array();
            foreach ($hosts as $host) {
                foreach ($host->temps as $tname=>$tval) {
                    if (!in_array($tname,$avail_temps)) $avail_temps[]=$tname;
                }
                foreach ($host->fans as $fname=>$fval) {
                    if (!in_array($fname,$avail_fans)) $avail_fans[]=$fname;
                }
            }
            echo "<table class=\"normal\">\n";
            $num_rows=1;
            echo "<tr><th class=\"name\">Hostname [alias]";
            if (!$sup_array["upt"][1]) echo " (uptime)";
            echo "</th>";
            if (!$sup_array["load"][1]) {
                $num_rows+=3;
                echo "<th class=\"load\">Load 1</th><th class=\"load\">Load 5</th><th class=\"load\">Load 15</th>\n";
            }
            if (!$sup_array["mem"][1]) {
                $num_rows++;
                echo "<th class=\"load\">Memory %</th>\n"; 
            }
            if (!$sup_array["net"][1]) {
                $num_rows++;
                echo "<th class=\"netn\">Net in, out</th>\n";
            }
            if (!$sup_array["disk"][1]) {
                $num_rows++;
                echo "<th class=\"diskn\">Disk usage</th>\n";
            }
            if (!$sup_array["temp"][1] && count($avail_temps)) {
                foreach ($avail_temps as $avail_temp) {
                    echo "<th class=\"tempn\">$avail_temp T</th>\n";
                    $num_rows++;
                }
            }
            if (!$sup_array["fan"][1] && count($avail_fans)) {
                foreach ($avail_fans as $avail_fan) {
                    echo "<th class=\"fann\">$avail_fan F</th>\n";
                    $num_rows++;
                }
            }
            if (!$sup_array["batch"][1] && $batch_clients_found) {
                echo "<th class=\"batchclient\">BatchSys</th>\n";
                $num_rows++;
            }
            echo "</tr>\n";
            $lastmg="none";
            foreach ($display_a as $act_group=>$display_g) {
                list($n1,$n2,$mach_list)=$display_g;
                if (sizeof($display_a) > 1) {
                    echo "<tr><td colspan=$num_rows class=\"machinegroup\">machinegroup: $act_group, selected ";
                    if ($n1 == $n2) {
                        echo "all $n1";
                    } else {
                        echo "$n1 of $n2";
                    }
                    echo " machines</td></tr>\n";
                }
                foreach ($mach_list as $mach_name) {
                    $mach=&$hosts[$mach_name];
                    echo "<tr>";
                    if ($mach->state == "UP") {
                        $uds="up";
                    } else {
                        $uds="down";
                    }
                    echo "<td class=\"name$uds\">$mach_name";
                    if ($mach->comment && !$sup_array["cmt"][1]) {
                        echo " [$mach->comment]";
                    }
                    $p_str=$mach->alias;
                    if ($uds == "up" && ! $sup_array["upt"][1]) {
                        if ($p_str) $p_str.=", ";
                        $p_str.=$mach->get_uptime()."";
                    }
                    if ($p_str) echo " ($p_str)";
                    echo "</td>";
                    if (!$sup_array["load"][1]) {
                        echo $mach->get_load1();
                        echo $mach->get_load5();
                        echo $mach->get_load15();
                    }
                    if (!$sup_array["mem"][1]) echo $mach->get_memory();
                    if (!$sup_array["net"][1]) echo $mach->get_net();
                    if (!$sup_array["disk"][1]) echo $mach->get_disk();
                    if (!$sup_array["temp"][1]) {
                        foreach ($avail_temps as $avail_temp) {
                            echo $mach->get_temp($avail_temp);
                        }
                    }
                    if (!$sup_array["fan"][1]) {
                        foreach ($avail_fans as $avail_fan) {
                            echo $mach->get_fan($avail_fan);
                        }
                    }
                    if (!$sup_array["batch"][1] && $batch_clients_found) echo $mach->get_batch_types();
                    echo "</tr>\n";
                }
            }
            echo "</table>";
        } else {
            if ($act_ov_type == "List") {
                $mr2=query("SELECT DISTINCT dg.name,dg.device_group_idx FROM device_group dg ORDER BY dg.name");
                if (mysql_num_rows($mr2)) {
                echo "<table class=\"normal\">";
                echo "<tr>";
                echo "<th class=\"name\">Groupname</th>";
                echo "<th class=\"type\">Devices</th>";
                echo "<th class=\"down\">Down</th>";
                if (!$sup_array["load"][1]) {
                    foreach (array("1","5","15") as $loads) {
                        echo "<th class=\"load\">Load $loads</th>";
                    }
                }
                if (!$sup_array["mem"][1]) {
                    echo "<th class=\"load\">p.m %</th>\n"; 
                    echo "<th class=\"load\">t.m %</th>\n"; 
                }
                if (!$sup_array["net"][1]) {
                    echo "<th class=\"netn\">Net in</th>\n"; 
                    echo "<th class=\"netn\">Net out</th>\n"; 
                }
                echo "</tr>\n";
                $tot_up=0;
                $tot_down=0;
                $id_t_array=array();
                // total and group-local checks
                $states_array=array("t","g");
                // possible checks
                $check_array=array("mem_p"=>array("mem_state","mem"),
                                   "mem_t"=>array("mem_state","memtot"),
                                   "net_in"=>array("net_state","in_tot"),
                                   "net_out"=>array("net_state","out_tot"),
                                   "load_1"=>array("load_state","load_1"),
                                   "load_5"=>array("load_state","load_5"),
                                   "load_15"=>array("load_state","load_15")
                                   );
                $check_res=array();
                foreach ($states_array as $act_state) {
                    $check_res[$act_state]=array();
                    foreach ($check_array as $act_check=>$state_vars) {
                        list($state_var,$read_var)=$state_vars;
                        $check_res[$act_state][$act_check]=array("sv"=>$state_var,"rv"=>$read_var,"min"=>-1,"max"=>-1,"set"=>0);
                    }
                }
                while ($mfr=mysql_fetch_object($mr2)) {
                    $mr3=query("SELECT d.name,dt.identifier,dt.description FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type AND d.device_group=$mfr->device_group_idx AND dt.identifier != 'R' AND dt.identifier != 'MD' ORDER BY d.name");
                    if (mysql_num_rows($mr3)) {
                        $act_res=&$check_res["g"];
                        foreach ($act_res as $act_check=>$check_vars) $act_res[$act_check]["set"]=0;
                        $num_down=0;
                        $num_up=0;
                        $id_array=array();
                        while ($mfr2=mysql_fetch_object($mr3)) {
                            $host=&$hosts[$mfr2->name];
                            if (in_array($mfr2->description,array_keys($id_array))) {
                                $id_array[$mfr2->description]++;
                            } else {
                                $id_array[$mfr2->description]=1;
                            }
                            if (in_array($mfr2->identifier,array_keys($id_t_array))) {
                                $id_t_array[$mfr2->identifier]++;
                            } else {
                                $id_t_array[$mfr2->identifier]=1;
                            }
                            if ($host->state == "UP") {
                                $num_up++;
                                foreach ($states_array as $act_state) {
                                    $act_res=&$check_res[$act_state];
                                    foreach ($act_res as $act_check=>$check_vars) {
                                        if ($host->$check_vars["sv"] != "UNKNOWN") {
                                            $host_var=$host->$check_vars["rv"];
                                            if ($check_vars["set"]) {
                                                $act_res[$act_check]["max"]=max($host_var,$act_res[$act_check]["max"]);
                                                $act_res[$act_check]["min"]=min($host_var,$act_res[$act_check]["min"]);
                                            } else {
                                                $act_res[$act_check]["max"]=$host_var;
                                                $act_res[$act_check]["min"]=$host_var;
                                                $act_res[$act_check]["set"]=1;
                                            }
                                        }
                                    }
                                }
                            } else {
                                $num_down++;
                            }
                        }
                        $tot_up+=$num_up;
                        $tot_down+=$num_down;
                        $num_hosts=$num_up+$num_down;
                        if ($num_down) {
                            $uds2="down";
                            if ($num_down == $num_hosts) {
                                if ($num_down == 1) {
                                    echo "all down";
                                } else {
                                    $out_ud="all $num_down down";
                                }
                            } else {
                                $out_ud="$num_down of $num_hosts";
                            }
                        } else {
                            $uds2="up";
                            if ($num_hosts > 1) {
                                $out_ud="all $num_hosts up";
                            } else {
                                $out_ud="is up";
                            }
                        }
                        if ($num_up) {
                            $uds="up";
                            $uds3="du2";
                            $addt="n";
                        } else {
                            $uds="down";
                            $uds3="dd";
                            $addt="c";
                        }
                        echo "<tr>";
                        echo "<td class=\"name$uds\"><a class=\"cinfo$uds3\" href=\"clusterinfo.php?".write_sid()."&selgroup[]=$mfr->name$ref_str\">$mfr->name</a></td>";
                        $id_outa=array();
                        foreach ($id_array as $id=>$num) $id_outa[]="$num ".get_plural($id,$num);
                        echo "<td class=\"type$uds\">".implode("/",$id_outa)."</td>\n";
                        echo "<td class=\"downov$uds2\">$out_ud</td>";
                        show_data_line($check_res["g"],$sup_array,$addt);
                        echo "</tr>\n";
                    }
                }
                $tot_hosts=$tot_up+$tot_down;
                if ($tot_down) {
                    $uds2="down";
                    if ($tot_down == $tot_hosts) {
                        $out_ud="all $tot_down down";
                    } else {
                        $out_ud="$tot_down of $tot_hosts";
                    }
                } else {
                    $uds2="up";
                    if ($tot_hosts > 1) {
                        $out_ud="all $tot_hosts up";
                    } else {
                        $out_ud="is up";
                    }
                }
                if ($tot_up) {
                    $uds="up";
                    $addt="n";
                } else {
                    $uds="down";
                    $addt="c";
                }
                echo "<tr>";
                echo "<td class=\"name$uds\" >Total</td>";
                $id_outa=array();
                foreach ($id_t_array as $id=>$num) $id_outa[]="$num $id";
                echo "<td class=\"type$uds\">".implode("/",$id_outa)."</td>\n";
                echo "<td class=\"down$uds2\">$out_ud</td>";
                show_data_line($check_res["t"],$sup_array,$addt);
                echo "</tr>\n";
                echo "</table>\n";
                }
            } else if ($act_ov_type == "Detailed") {
                $num_columns=8;
                echo "<table class=\"normal\">";
                echo "<tr>";
                echo "<th class=\"name\">Groupname</th><th class=\"type\" colspan=\"$num_columns\">Devices</th>";
                echo "</tr>";
                $mr2=query("SELECT DISTINCT dg.name,dg.device_group_idx FROM device_group dg ORDER BY dg.name");#, device_type dt, device d WHERE d.device_type=dt.device_type_idx AND d.device_group=dg.device_group_idx ORDER BY dt.identifier,dg.name");
                while ($mfr=mysql_fetch_object($mr2)) {
                    $mr3=query("SELECT d.name,dt.identifier,dt.description FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type AND dt.identifier != 'R' AND dt.identifier != 'MD' AND d.device_group=$mfr->device_group_idx ORDER BY d.name");
                    if (mysql_num_rows($mr3)) {
                        echo "<tr>";
                        $num_machs=mysql_num_rows($mr3);
                        $num_d_rows=intval($num_machs/$num_columns);
                        if ($num_d_rows*$num_columns < $num_machs) $num_d_rows++;
                        echo "<td class=\"name\" rowspan=\"$num_d_rows\"><a class=\"cinfodu2\" href=\"clusterinfo.php?".write_sid()."&selgroup[]=$mfr->name$ref_str\">$mfr->name</a></td>";
                        $act_col=0;
                        $act_row=0;
                        while ($mfr3=mysql_fetch_object($mr3)) {
                            if ($act_row && !$act_col) echo "<tr>";
                            $dname=$mfr3->name;
                            $device=&$hosts[$dname];
                            $checks_tot=$device->checks;
                            $checks_ok=$device->checks_ok;
                            $checks_warning=$device->checks_warning;
                            $checks_error=$device->checks_error;
                            $num_checks_warning=$device->num_checks_warning;
                            $num_checks_error=$device->num_checks_error;
                            if ($num_checks_error) {
                                $tdc="downdown";
                                $tdc2="dd";
                            } else if ($num_checks_warning) {
                                $tdc="downwarn";
                                $tdc2="dw";
                            } else {
                                $tdc="downup";
                                $tdc2="du";
                            }
                            echo "<td class=\"$tdc\" ><a class=\"cinfo$tdc2\" href=\"clusterinfo.php?".write_sid()."&selmach[]=$dname$ref_str\" >$dname (";
                            $out_array=array();
                            foreach (array($checks_ok,implode("",$checks_warning),implode("",$checks_error)) as $check_out) {
                                if ($check_out) {
                                    $out_array[]=$check_out;
                                } else {
                                    $out_array[]="-";
                                }
                            }
                            echo implode(",",$out_array).")</a></td>";
                            if (++$act_col==$num_columns) {
                                echo "</tr>";
                                $act_col=0;
                                $act_row++;
                            }
                        }
                        if ($act_col) echo "<td class=\"downnone\" colspan=\"".strval($num_columns-$act_col)."\">&nbsp;</td></tr>";
                    }
                }
                echo "</table>";
            } else {
                message("Unknown Overview-type $act_ov_type");
            }
        }
    } else {
        message ("You are not allowed to access this page");
    }
    writefooter($sys_config);
}
?>
