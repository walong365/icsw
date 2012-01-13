<?php
//-*ics*- ,CAPG,name:'conf',descr:'Configuration',pri:-20
//-*ics*- ,CAP,name:'bc',descr:'Boot control',defvalue:0,enabled:1,scriptname:'/php/bootcontrol.php',left_string:'Boot control',right_string:'Boot control',pri:-100,capability_group_name:'conf'
//-*ics*- ,CAP,name:'bcp',descr:'Extra power-down control',defvalue:0,enabled:1,mother_capability:'bc'
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
function fileread($name) {
    if (file_exists($name)) {
        $rfile=file($name);
        return $rfile;
    } else {
        return array("???");
    }
}
class ipc {
    var $name,$newstate,$prod_link,$newimage,$actimage,$part,$recvstate,$reqstate,$actnet,$up,$imageversion;
    var $newkernel,$actkernel,$kernelversion,$group,$new_ts,$refresh_tk,$out_dev_ref;
    var $last_boot,$last_install,$last_kernel,$dhcp_mac,$macadr,$kernel_append,$comment,$idx,$dhcp_write,$dhcp_written,$bootserver;
    function ipc($name) {
        $this->name=$name;
        $this->newstate=0;
        $this->prod_link=0;
        $this->idx=0;
        $this->group="";
        $this->newimage="";
        $this->actimage="";
        $this->newkernel="";
        $this->actkernel="";
        $this->imageversion="";
        $this->kernelversion="";
        $this->part="";
        $this->recvstate="???";
        $this->reqstate="???";
        $this->actnet="???";
        $this->dhcp_mac=0;
        $this->dhcp_write=0;
        $this->dhcp_written=0;
        $this->macadr="";
        $this->up=0;
        $this->new_ts=0;
        $this->refresh_tk=0;
        $this->last_boot="unknown";
        $this->last_install="unknown";
        $this->last_kernel="unknown";
        $this->kernel_append="";
        $this->comment="";
        $this->bootserver=0;
        $this->out_dev_ref=0;
    }
    function get_actkernel() {
        if ($this->actkernel) {
            return "{$this->actkernel} [$this->kernelversion]";
        } else {
            return htmlentities("<NONE>");
        }
    }
    function get_actimage() {
        if ($this->actimage) {
            return "{$this->actimage} [$this->imageversion]";
        } else {
            return htmlentities("<NONE>");
        }
    }
    function set_actstate($asa) {
        $this->actstate=$asa;
        $this->laststate=trim($this->actstate[sizeof($this->actstate)-1]);
    }
    function get_actnetstr() {
        return $this->actnet;
    }
    function get_state($mcon,$prod_nets) {
        $mres=query("SELECT d.reqstate,d.recvstate FROM device d WHERE d.name='$this->name'",$mcon);
        $mfr=mysql_fetch_object($mres);
        //echo "$mfr->reqstate - $mfr->recvstate<br>";
        if (preg_match("/^ok \d+\.\d+\.\d+\.\d+ (.*) \((.+)\)$/",$mfr->reqstate,$what)) {
            $this->reqstate=$what[1];#." (".$what[2].")";
            $this->actnet=$what[2];
        } else if (preg_match("/^warn \d+\.\d+\.\d+\.\d+ (.*) \((.+)\)$/",$mfr->reqstate,$what)) {
            $this->reqstate=$what[1];
            $this->actnet=$what[2];
        } else {
            $this->reqstate=$mfr->reqstate;
        }
        if (preg_match("/^(.*) \((.+)\)$/",$mfr->recvstate,$what2)) {
            if ($what && ($what2[2] == $what[2])) {
                $this->recvstate=$what2[1];
            } else {
                $this->recvstate="{$what2[1]} ({$what2[2]})";
            }
        } else {
            $this->recvstate=$mfr->recvstate;
        }
    }
    function show_ping() {
        echo "<input type=radio name=\"$this->name.rb\" value=\"none\" checked />\n";
        echo "<input type=radio name=\"$this->name.rb\" value=\"reboot\" />\n";
        echo "<input type=radio name=\"$this->name.rb\" value=\"halt\" />\n";
        echo "<input type=radio name=\"$this->name.rb\" value=\"poweroff\" />\n";
    }
    function show_greedy_mode() {
        echo "greedy mode is";
        if ($this->dhcp_mac) {
            echo " enabled";
        } else {
            echo " disabled";
        }
        echo ", <select name=\"$this->name.dm\">";
        echo "<option value=\"none\">keep</option>\n";
        echo "<option value=\"set\">enable</option>\n";
        echo "<option value=\"del\">disable</option>\n";
        echo "</select>\n";
    }
    function new_log_entry() {
        echo "<input name=\"$this->name.lfe\" maxlength=\"127\" size=\"40\" />";
    }
    function show_kernel_parameter() {
        echo "<input name=\"$this->name.kpn\" maxlength=\"99\" size=\"100\" value=\"$this->kernel_append\" />";
    }
    function show_comment() {
        echo "<input name=\"$this->name.comment\" maxlength=\"32\" size=\"33\" value=\"".htmlspecialchars($this->comment)."\" />";
    }
    function show_macadr() {
        echo "MACaddr: <input name=\"$this->name.mac\" maxlength=\"17\" size=\"20\" value=\"$this->macadr\" />";
    }
    function new_macadr() {
        echo ", option: <select name=\"$this->name.newmac\" >";
        echo "<option value=\"0\">----</option>\n";
        echo "<option value=\"1\">alter</option>\n";
        echo "<option value=\"2\">write</option>\n";
        echo "<option value=\"3\">delete</option>\n";
        echo "</select>\n";
        echo ", write_flag is ";
        if (!$this->dhcp_write) echo "not ";
        echo "set, dhcp_entry is ";
        if (!$this->dhcp_written) echo "not ";
        echo "written\n";
    }
    function mark_machine() {
        echo "<input type=hidden name=\"{$this->name}.mark\" value=1 />\n";
    }
    function show_image($images) {
        if ($images) {
            echo "<select name=\"$this->name.im\">";
            $idx=0;
            $short_targim="???";
            $long_targim="???";
            foreach (array_keys($images) as $actt) {
                echo "<option value=$idx";
                $actim="$actt [{$images[$actt]['version']}], {$images[$actt]['size']}, builddate: {$images[$actt]['short_bdate']} on {$images[$actt]['build_machine']}";
                if ($this->newimage==$actt) {
                    echo " selected ";
                    $short_targim="$actt [{$images[$actt]['version']}]";
                    $long_targim=$actim;
                }
                $lock_str=(($images[$actt]["locked"]) ? "LOCKED: " : "");
                echo ">$lock_str$actim</option>";
                $idx++;
            }
            echo "</select>\n";
        } else {
            list($long_targim,$short_targim)=array("N/A","N/A");
            echo "N/A";
        }
        return array($long_targim,$short_targim);
    }
    function show_kernel($kernels) {
        if ($kernels) {
            $info_len=40;
            echo "<select name=\"$this->name.kn\">";
            $targkern="???";
            foreach ($kernels as $kname=>$act_kern) {
                echo "<option value=\"$kname\"";
                $k_id="{$act_kern['name']} [{$act_kern['version']}]";
                if ($this->newkernel==$kname) {
                    echo " selected ";
                    $targkern=$k_id;
                }
                echo ">$k_id, {$act_kern['builddate']}</option>\n";
                if (strlen($act_kern["comment"])) {
                    $comline=$act_kern["comment"];
                    while (strlen($comline)) {
                        echo "<option disabled> - ".substr($comline,0,$info_len)."</option>\n";
                        $comline=trim(substr($comline,$info_len));
                    }
                }
            }
            echo "</select>\n";
        } else {
            $targkern="N/A";
            echo "N/A";
        }
        return $targkern;
    }
    function show_machine_history($span) {
        echo "<td class=\"bctloghistt\" colspan=\"$span\">";
        $mres=query("SELECT l.text,l.date,l.user,l.log_source FROM devicelog l, device d WHERE l.device=d.device_idx AND d.name='$this->name' ORDER BY l.date ASC");
        $u_idx_list=array();
        $u_aarray=array();
        $log_sources=get_all_log_sources();
        echo "<div class=\"center\">\n";
        if (mysql_num_rows($mres)) {
            echo "Device history</div>\n";
            echo "<div class=\"center\">\n";
            $ok_state=array(1=>array(1,2,3,4),
                            2=>array(3,4),
                            3=>array(1,5),
                            4=>array(1,5),
                            5=>array(1,5));
            $reboot_states=array(3,4);
            $bl_okstr=str_repeat("-",30);
            $bl_crstr=substr("-- Crash $bl_okstr",0,30);
            $opt_f=array();
            $act_state=-1;
            echo "<select name=\"bootlog\" size=10 style=\"width:100%\">\n";
            while ($mfr=mysql_fetch_object($mres)) {
                if ($log_sources[$mfr->log_source]->identifier=="user") {
                    if (!in_array($mfr->user,$u_idx_list)) {
                        $mres3=query("SELECT l.login FROM user l WHERE l.user_idx=$mfr->user");
                        $u_idx_list[]=$mfr->user;
                        if (mysql_num_rows($mres3)) {
                            $mfr3=mysql_fetch_object($mres3);
                            $u_aarray[$mfr->user]=htmlspecialchars($mfr3->login);
                        } else {
                            $u_aarray[$mfr->user]=htmlspecialchars("<UNKNOWN [{$mfr->user}]>");
                        }
                    }
                    $opt_f[]=array("{$u_aarray[$mfr->user]}: $mfr->text",$mfr->date,$mfr->user);
                } else {
                    if ($log_sources[$mfr->log_source]->identifier=="node" && $mfr->user) {
                        $last_state=$act_state;
                        $act_state=$mfr->user;
                        if ($last_state != -1) {
                            if (! in_array($act_state,$ok_state[$last_state])) $opt_f[]=array($bl_crstr,0,$mfr->user);
                        }
                    }
                    $opt_f[]=array("*{$log_sources[$mfr->log_source]->identifier}: $mfr->text",$mfr->date,$mfr->user);
                }
                if (in_array($act_state,$reboot_states)) $opt_f[]=array($bl_okstr,0,$mfr->user);
            }
            $opt_f=array_reverse($opt_f);
            $idx=0;
            $last_day=-1;
            foreach ($opt_f as $opt_l) {
                //$last_day=-1;
                // we need $stuff only for debug purposes
                list($opt,$date,$stuff)=$opt_l;
                $class="ns";
                if ($date) {
                    $time=mktime(intval(substr($date,8,2)),intval(substr($date,10,2)),intval(substr($date,12,2)),
                                 intval(substr($date,4,2)),intval(substr($date,6,2)),intval(substr($date,0,4)));
                    $act_day=intval(date("z",$time));
                    if ($act_day != $last_day) {
                        echo "<option class=\"nd\">".substr("-- ".date("D, j. F Y",$time)." ".$bl_okstr,0,30)."</option>\n";
                        $last_day=$act_day;
                    }
                    $t_str=date("G:i:s",$time)." ";
                } else {
                    $class="cr";
                    $t_str="";
                }
                $o_str="<option ";
                if ($class) $o_str.=" class=\"$class\" ";
                $o_str.=">$t_str$opt</option>\n";
                echo $o_str;
            }
            echo "</select>\n";
        } else {
            echo "No device history found";
        }
        echo "</div>\n";
        echo "</td>";
    }
    function show_syslog($avn,$actlog,$span) {
        echo "<td class=\"bctlogmest\" colspan=\"$span\">";
        $logs=array();
        $mlogdir="/var/log/hosts/{$this->name}";
        if (is_dir($mlogdir)) {
            $mldir=dir($mlogdir);
            while ($ye=$mldir->read()) {
                if (preg_match("/^\d{4}$/",$ye)) {
                    $ydirn="$mlogdir/$ye";
                    $ydir=dir($ydirn);
                    while ($me=$ydir->read()) {
                        if (preg_match("/^\d{2}$/",$me)) {
                            $mdirn="$ydirn/$me";
                            $mdir=dir($mdirn);
                            while ($de=$mdir->read()) {
                                if (preg_match("/^\d{2}$/",$de)) {
                                    $fname="$mdirn/$de/log";
                                    if (is_file($fname)) {
                                        $log_time=mktime(1,1,1,intval($me),intval($de),intval($ye));
                                        $logs[$log_time]=array($fname,$log_time,filesize($fname));
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        krsort($logs);
        if ($actlog == "" && sizeof($logs)) {
            $actlog=array_keys($logs);
            $actlog=$actlog[0];
        }
        if ($actlog) {
            echo "<div class=\"center\">";
            $host_match="/^$this->name(.*)$/";
            $lname=$logs[$actlog][0];
            $out_array=array();
            $plist=array();
            $fcon=file($lname);
            $num_lines=sizeof($fcon);
            $num_disp_lines=500;
            $start_line=$num_lines-$num_disp_lines;
            $act_line=0;
            foreach ($fcon as $line) {
                $act_line++;
                if ($act_line > $start_line) {
                    $rline=htmlentities($line);
                    $ne=array("time"=>"UNKNOWN","host"=>$this->name,"prog"=>"syslogd","pid"=>0,"msg"=>"","pvers"=>"UNKNOWN");
                    if (preg_match("/\S+\s+\S+\s+(\S+)\s+(\S+)\s+(.*)$/",$rline,$linem)) {
                        $ne["time"]=$linem[1];
                        $host=$linem[2];
                        if (preg_match($host_match,$host,$hostm)) {
                            if (strlen($hostm[1])) {
                                $ne["host"]="{$hostm[1]}: ";
                            } else {
                                $ne["host"]="";
                            }
                        } else {
                            $ne["host"]=$linem[2]+": ";
                        }
                        if (preg_match("/^([^:]+):\s+(.*)$/",$linem[3],$linen)) {
                            if (preg_match("/^(.*)\[(\d+)\]$/",$linen[1],$pidp)) {
                                $ne["prog"]=$pidp[1];
                                $ne["pid"]=intval($pidp[2]);
                            } else {
                                $ne["prog"]=$linen[1];
                            }
                            $ne["msg"]=$linen[2];
                        } else {
                            $ne["msg"]=$linem[3];
                        }
                    } else {
                        $ne["msg"]=$linem;
                    }
                    if (preg_match("/^(\S+)\s+(\S+)$/",$ne["prog"],$progp)) {
                        $ne["prog"]=$progp[1];
                        $ne["pvers"]=$progp[2];
                    }
                    $prog=$ne["prog"];
                    $pid=$ne["pid"];
                    if (in_array($prog,array_keys($plist))) {
                        $plist[$prog][0]++;
                        if (! in_array($pid,$plist[$prog][1])) {
                            $plist[$prog][1][]=$pid;
                        }
                    } else {
                        $plist[$prog]=array(1,array($pid));
                    }
                    $out_array[]=$ne;
                }
            }
            echo "Log from <select name=\"$avn\">";
            $last_day=7;
            foreach (array_keys($logs) as $ak) {
                $act_day=intval(date("w",$logs[$ak][1]));
                if ($act_day > $last_day) echo "<option disabled>------------------</option>\n";
                $last_day=$act_day;
                echo "<option value=\"$ak\"";
                if ($ak == $actlog) echo " selected";
                echo ">".date("D, d. F Y",$logs[$ak][1])." ({$logs[$ak][2]} Bytes)</option>";
            }
            echo "</select>\n";
            echo " in $num_lines lines (showing the last $num_disp_lines)</div>";
            //foreach (array_keys($plist) as $prog) {
            //  echo $prog.":".strval($plist[$prog][0])."(".strval(sizeof($plist[$prog][1])).")<br>";
            //}
            echo "<textarea style=\"width=100%; font-family:monospace ; font-style:normal ; font-size:10pt ; \" cols=100 rows=10 readonly >";
            foreach ($out_array as $aline) {
                echo "{$aline['host']}{$aline['time']} {$aline['prog']}";
                if ($aline["pvers"] != "UNKNOWN") echo " {$aline['pvers']}";
                if ($aline["pid"] != 0) echo "[{$aline['pid']}]";
                echo ": {$aline['msg']}\n";
            }
            echo "</textarea>\n";
        } else {
            echo "Nothing to display";
        }
        echo "</td>\n";
    }
}
function show_part($parts,$name,$actp,$show_none=0) {
    if ($parts) {
        echo "<select name=\"$name\">";
        if ($show_none) echo "<option value=\"-1\" >keep actual</option>";
        foreach ($parts as $idx=>$stuff) {
            echo "<option value=\"$idx\" ";
            if ($actp==$idx) echo " selected";
            echo ">{$stuff['name']} ({$stuff['info']})</option>";
        }
        echo "</select>\n";
    } else {
        echo "<input type=hidden name=\"$name\" value=\"-1\" />None available\n";
    }
}
function show_t_state($tstates,$pnets,$name,$newstate,$prod_link) {
    if ($name) {
        echo "<select name=\"$name\">";
        $last_pl=-1;
        if ($newstate == -1) {
            echo "<option value=\"keep\" selected >----</option>";
        }
        foreach ($tstates as $idx=>$acttl) {
            list($actt,$p_link)=$acttl;
            if ($last_pl == -1) {
                $last_pl=$p_link;
            } elseif ($last_pl != $p_link) {
                $last_pl=$p_link;
            }
            if (!$p_link) {
                echo "<option value=\"$idx\"";
                if ($newstate==$idx) echo " selected ";
                echo ">$actt</option>\n";
            }
        }
        foreach ($pnets as $idx2=>$pnet_l) {
            list($id,$pname)=$pnet_l;
            echo "<option disabled>--- $id [ $pname ] ---</option>";
            foreach ($tstates as $idx=>$acttl) {
                list($actt,$p_link)=$acttl;
                if ($p_link) {
                    echo "<option value=\"{$idx}_{$idx2}\"";
                    if ($newstate==$idx && $prod_link==$idx2) echo " selected ";
                    echo ">$actt into $id</option>\n";
                }
            }
        }
        echo "</select>\n";
    } else {
        list($actt,$p_link)=$tstates[$newstate];
        echo $actt;
        if ($p_link) {
            echo " into {$pnets[$prod_link][0]}";
        }
    }
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
require_once "apctools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["bc_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);
    // check additional infos
    $add_infos=array("adia"=>array("APC Control",1),"adip"=>array("Partition",1),"adii"=>array("Image",1),"adik"=>array("Kernel",2),"adim"=>array("MACaddr",1),
                     "adic"=>array("Comment/Log",1),"adih"=>array("Device history",1),"adil"=>array("Syslog",1));
    if (in_array("addinfo",$varkeys)) {
        $add_info_set=$vars["addinfo"];
    } else {
        $add_info_set=array();
    }
    $hidden_add_info="";
    foreach ($add_info_set as $short) {
        $hidden_add_info.="<input type=hidden name=\"addinfo[]\" value=\"$short\"/>\n";
    }
    // check verbose mode
    $verbose=0;
    if (in_array("verbose",$varkeys)) $verbose=$vars["verbose"];
    // temporary verbose moe
    $t_verbose=0;
    $hiddenverbose="<input type=hidden name=\"verbose\" value=\"$verbose\" />";
    // log status
    $log_status=get_log_status();
    // mac-mapping mode
    $macmapping=0;
    if (in_array("macmapping",$varkeys)) $macmapping=$vars["macmapping"];
    $hiddenmacmapping="<input type=hidden name=\"macmapping\" value=\"$macmapping\" />";
    // check macbootlog-date
    $none_mbl_date="none";
    $last_mbl_date=date("Ymd");
    if (in_array("actmbldate",$varkeys)) {
        $act_mbl_date=$vars["actmbldate"];
    } else {
        $act_mbl_date=$none_mbl_date;
    }
    $hiddenmacbootlog="<input type=hidden name=\"actmbldate\" value=\"$act_mbl_date\" />";
    // global greedy 
    $global_greedy_flag="greedy_global";
    // parse the machine selection
    list($display_a,$machgroups,$hiddenmach,$actmach,$optsel)=get_display_list($vars,"AND d.bootserver > 0 AND d.bootnetdevice=n.netdevice_idx");
    htmlhead();
    clusterhead($sys_config,"Boot control page",$style="formate.css",
                array("th.mactype"=>array("background-color:#e0eefe"),
                      "td.mactype"=>array("background-color:#c0ccec","text-align:left"),
                      "th.macaddr"=>array("background-color:#eeeeff"),
                      "td.macaddr"=>array("background-color:#ddddff","text-align:center"),
                      "th.macname"=>array("background-color:#eeeeff"),
                      "td.macname"=>array("background-color:#ddddee","text-align:center"),
                      "th.macblidx"=>array("background-color:#ffcccc"),
                      "td.macblidx"=>array("background-color:#eebbbb","text-align:center"),
                      "th.mactime"=>array("background-color:#effeff"),
                      "td.mactime"=>array("background-color:#deedee","text-align:center"),
                      "th.macip"=>array("background-color:#feefff"),
                      "td.macip"=>array("background-color:#eddeee","text-align:center"),
                      "td.bctloghisth"=>array("background-color:#ffeedd","text-align:center"),
                      "td.bctloghistt"=>array("background-color:#ffeedd","text-align:center","vertical-align:top"),
                      "td.bctlogmesh"=>array("background-color:#ffddee","text-align:center"),
                      "td.bctlogmest"=>array("background-color:#ffddee","text-align:center","vertical-align:top"),
                      "th.bctstate"=>array("background-color:#eeeeff"),
                      "td.bctstateup"=>array("background-color:#ccccee","text-align:center"),
                      "td.bctstatewarn"=>array("color:#ffffff","background-color:#ffff55","text-align:center"),
                      "td.bctstatedown"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "th.bcinitstate"=>array("background-color:#ffeeff"),
                      "th.bcreboot"=>array("background-color:#eeffee"),
                      "td.bcrebootup"=>array("background-color:#d0d0f2","text-align:center"),
                      "td.bcrebootwarn"=>array("color:#ffffff","background-color:#ffff55","text-align:center"),
                      "td.bcrebootdown"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "td.bcinitstate0up"=>array("background-color:#d4d4f6","text-align:center"),
                      "td.bcinitstate0warn"=>array("background-color:#ffff55","text-align:center"),
                      "td.bcinitstate0down"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "td.bcinitstate1up"=>array("background-color:#d8d8fa","text-align:center"),
                      "td.bcinitstate1warn"=>array("background-color:#ffff55","text-align:center"),
                      "td.bcinitstate1down"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "td.bcinitstate2up"=>array("background-color:#dcdcfe","text-align:center"),
                      "td.bcinitstate2warn"=>array("background-color:#ffff55","text-align:center"),
                      "td.bcinitstate2down"=>array("color:#ffffff","background-color:#ff5555","text-align:center"),
                      "td.bcpartup"=>array("background-color:#e8ffff","text-align:left"),
                      "td.bcpartwarn"=>array("background-color:#ffff55","text-align:left"),
                      "td.bcpartdown"=>array("background-color:#ff5555","text-align:left"),
                      "td.bcimageup"=>array("background-color:#eefffa","text-align:left"),
                      "td.bcimagewarn"=>array("background-color:#ffff55","text-align:left"),
                      "td.bcimagedown"=>array("background-color:#ff5555","text-align:left"),
                      "td.bckernelup"=>array("background-color:#f4fff4","text-align:left"),
                      "td.bckernelwarn"=>array("background-color:#ffff55","text-align:left"),
                      "td.bckerneldown"=>array("background-color:#ff5555","text-align:left"),
                      "td.bcmacup"=>array("background-color:#faffee","text-align:left"),
                      "td.bcmacwarn"=>array("background-color:#ffff55","text-align:left"),
                      "td.bcmacdown"=>array("background-color:#ff5555","text-align:left"),
                      "td.bcinfoup"=>array("background-color:#ffffe8","text-align:left"),
                      "td.bcinfowarn"=>array("background-color:#ffff55","text-align:left"),
                      "td.bcinfodown"=>array("background-color:#ff5555","text-align:left"),
                      "option.bc"=>array("background-color:#ffffff","color:#000000"),
                      "option.bcgr"=>array("background-color:#777777","color:#ffffff"),
                      "option.bcgrnw"=>array("background-color:#ff8888","color:#000000"),
                      "option.bcnw"=>array("background-color:#44ff44","color:#000000")
                      )
                );
    clusterbody($sys_config,"Boot control",array("sc","apc","ch"),array("conf"));
  
    $ucl=&$sys_config["ucl"];
    if ($ucl["bc"]) {
        // simple protocol
        $hcproto=new messagelog();
        // clear change_possible flag
        $c_possible=0;

        $tftpdir="/tftpboot/";
        $images=array();
        $mres=query("SELECT i.name,i.version,i.release,i.date,i.build_machine,i.size_string,i.build_lock FROM image i");
        $act_year=date("Y ");
        $act_dm=date("d.m. ");
        while ($mfr=mysql_fetch_object($mres)) {
            $imname=$mfr->name;
            $imvers="{$mfr->version}.{$mfr->release}";
            $date=$mfr->date;
            $im_dm=substr($date,6,2).".".substr($date,4,2).". ";
            $im_year=substr($date,0,4)." ";
            $im_time=substr($date,8,2).":".substr($date,10,2).":".substr($date,12,2);
            $full_time="{$im_dm}{$im_year}{$im_time}";
            if ($im_dm == $act_dm) $im_dm="";
            if ($im_year == $act_year) $im_year="";
            $im_bh=$mfr->build_machine;
            if (! strlen($im_bh)) $im_bh="UNKNOWN";
            $size_string=$mfr->size_string;
            if (strlen($size_string)) {
                $size_p=explode(";",$size_string);
                $im_size=0;
                while (count($size_p)) {
                    $part_name=array_shift($size_p);
                    $part_size=array_shift($size_p);
                    if (strlen($part_name)) $im_size+=intval($part_size);
                }
                $im_size=sprintf("%.2f MB",(double)$im_size/1024.);
            } else {
                $im_size="unknown";
            }
            $images[$imname]=array("version"=>$imvers,"full_bdate"=>$full_time,"short_bdate"=>"{$im_dm}{$im_year}{$im_time}","build_machine"=>$im_bh,"size"=>$im_size,"locked"=>$mfr->build_lock);
        }
        $imnames=array_keys($images);
        if (count($imnames)) {
            $def_im_name=$imnames[0];
        } else {
            $def_im_name="No Images found";
        }
        $kernels=array();
        $kerndir="{$tftpdir}kernels";
        if (is_dir($kerndir)) {
            $d=dir($kerndir);
            while ($entry=$d->read()) {
                $kname="$kerndir/$entry";
                if (is_dir($kname) && ! preg_match("/^\.+.*$/",$entry)) {
                    $act_kern=array("name"=>$entry,
                                    "version"=>"?.?",
                                    "builddate"=>"unknown",
                                    "comment"=>"");
                    $versfile=$kname."/.version";
                    if (file_exists($versfile)) {
                        foreach (file($versfile) as $versl) {
                            if (preg_match("/^VERSION=(.*)$/",trim($versl),$vers)) {
                                $act_kern["version"]=$vers[1];
                            } elseif (preg_match("/^BUILDDATE=(.*)$/",trim($versl),$binfo)) {
                                $act_kern["builddate"]=$binfo[1];
                            }
                        }
                    }
                    $commentfile=$kname."/.comment";
                    if (file_exists($commentfile)) {
                        foreach (file($commentfile) as $comline) $act_kern["comment"].=$comline." ";
                    }
                    $kernels[$entry]=$act_kern;
                }
            }
            ksort($kernels);
            $d->close();
        }
        $parts=array();
        $mres=query("SELECT pt.partition_table_idx,pt.name,pd.disc,p.pnum,p.size FROM partition_table pt LEFT JOIN partition_disc pd ON pd.partition_table=pt.partition_table_idx LEFT JOIN partition p ON p.partition_disc=pd.partition_disc_idx");
        while ($mfr=mysql_fetch_object($mres)) {
            $pt_idx=$mfr->partition_table_idx;
            if (!in_array($pt_idx,array_keys($parts))) $parts[$pt_idx]=array("name"=>$mfr->name,"discs"=>array(),"parts"=>0,"size"=>0);
            if (!in_array($mfr->disc,array_keys($parts[$pt_idx]))) $parts[$pt_idx]["discs"][$mfr->disc]=0;
            if ($mfr->pnum) $parts[$pt_idx]["discs"][$mfr->disc]++;
            if ($mfr->pnum) $parts[$pt_idx]["parts"]++;
            if ($mfr->pnum) $parts[$pt_idx]["size"]+=$mfr->size;
        }
        foreach ($parts as $idx=>$p_stuff) {
            $size=$p_stuff['size'];
            if ($size > 1000) {
                $size_str=sprintf("%.3f GB",$size/1000);
            } else {
                $size_str="$size MB";
            }
            $parts[$idx]["info"]="$size_str needed ".get_plural("disc",count($p_stuff["discs"]),1).", ".get_plural("partition",$p_stuff["parts"],1);
        }
        $user_ls=get_log_source("user");
        if ($user_ls) {
            $uls_idx=$user_ls->log_source_idx;
        } else {
            $uls_idx=0;
        }
        $ipc=array();
        if (count($machgroups)) {
            
            $mres=query("SELECT s.status_idx,s.status,s.prod_link FROM status s ORDER BY prod_link,status");
            $tstates=array();
            $install_state=-1;
            $boot_state=-1;
            while ($mfr=mysql_fetch_object($mres)) {
                $tstates[$mfr->status_idx]=array($mfr->status,$mfr->prod_link);
                if ($mfr->status == "installation") $install_state=$mfr->status_idx;
                if ($mfr->status == "boot" && $mfr->prod_link) $boot_state=$mfr->status_idx;
            }
            $prod_nets=array();
            $mres=query("SELECT nw.network_idx,nw.identifier,nw.name FROM network nw, network_type nt WHERE nt.identifier='p' AND nw.network_type=nt.network_type_idx");
            while ($mfr=mysql_fetch_object($mres)) $prod_nets[$mfr->network_idx]=array($mfr->identifier,$mfr->name);
            $boot_server=array();
            $mres=query("SELECT d.device_idx,d.name FROM device d, deviceconfig dc, config c WHERE dc.device=d.device_idx AND dc.config=c.config_idx AND c.name='mother_server'");
            while ($mfr=mysql_fetch_object($mres)) $boot_server[$mfr->device_idx]=$mfr->name;
            $reboot_array=array();
            $halt_array=array();
            $power_off_array=array();
            $node_bs_array=array();
            $refresh_tk_array=array();
            $apc_com_array=array();
            $do_list=array();
            foreach($boot_server as $idx=>$name) {
                $reboot_array[$name]=array();
                $power_off_array[$name]=array();
                $halt_array[$name]=array();
                $node_bs_array[$name]=array();
                $refresh_tk_array[$name]=array();
                $apc_com_array[$name]=array();
                $do_list[$name]=array();
            }
            // build apc-list
            $apcs=array();
            $mres=query("SELECT d.device_idx,d.name,i.ip,d.bootserver FROM device d, device_type dt, netip i, netdevice n WHERE dt.device_type_idx=d.device_type AND dt.identifier='AM' AND i.netdevice=n.netdevice_idx AND n.device=d.device_idx AND d.bootserver > 0 ORDER BY d.name");
            while ($mfr=mysql_fetch_object($mres)) {
                $apcs[$mfr->device_idx]=new apc($mfr->ip,$mfr->name,$mfr->device_idx,$mfr->bootserver);
                $sellist[$mfr->name]="APC $mfr->name (bs={$boot_server[$mfr->bootserver]})";
            }
            // empty apc resolve-dict
            $apc_resolve_dict=array();
                
            // get outlet-device references
            $out_dev_ref=array();
            $mres=query("SELECT m.outlet,m.slave_info,d.device_idx,m.device FROM device d, msoutlet m WHERE m.slave_device=d.device_idx $optsel");
            while ($mfr=mysql_fetch_object($mres)) {
                $dev_idx=$mfr->device_idx;
                if (!in_array($dev_idx,array_keys($out_dev_ref))) $out_dev_ref[$dev_idx]=array();
                $out_dev_ref[$dev_idx][]=$mfr;
            }
            $mres=query("SELECT d.device_idx,d.comment,d.bootnetdevice,d.dhcp_mac,d.dhcp_write,d.dhcp_written,d.prod_link,d.bootserver,d.etherboot_valid,d.name,d.newimage,d.partition_table,d.act_partition_table,d.newkernel,d.newstate,d.last_boot,d.last_install,d.last_kernel,n.macadr,d.kernel_append,dg.name AS dgname FROM device_group dg, device d, netdevice n, device_type dt WHERE n.device=d.device_idx AND dg.device_group_idx=d.device_group AND d.bootnetdevice=n.netdevice_idx AND (dt.identifier='H' OR dt.identifier='S') AND d.device_type=dt.device_type_idx AND d.bootserver > 0 $optsel ORDER BY d.name");
            while ($mfr=mysql_fetch_object($mres)) {
                $name=$mfr->name;
                $ipc[$name]=new ipc($name);
                $actdev=&$ipc[$name];
                $actdev->idx=$mfr->device_idx;
                $actdev->kernel_append=$mfr->kernel_append;
                $actdev->dhcp_mac=$mfr->dhcp_mac;
                $actdev->dhcp_write=$mfr->dhcp_write;
                $actdev->dhcp_written=$mfr->dhcp_written;
                $actdev->macadr=strtolower($mfr->macadr);
                $actdev->group=$mfr->dgname;
                $actdev->newstate=$mfr->newstate;
                $actdev->prod_link=$mfr->prod_link;
                $actdev->bootserver=$mfr->bootserver;
                $actdev->etherboot_valid=$mfr->etherboot_valid;
                $node_bs_array[$boot_server[$actdev->bootserver]][]=$name;
                if (!$mfr->prod_link) $mfr->prod_link=1;
                if ($mfr->last_boot) $actdev->last_boot=$mfr->last_boot;
                if ($mfr->last_install) $actdev->last_install=$mfr->last_install;
                if ($mfr->last_kernel) $actdev->last_kernel=$mfr->last_kernel;
                // comment
                $avn="{$name}_comment";
                if (isset($vars[$avn])) {
                    $newcomment=un_quote($vars[$avn]);
                    if ($newcomment != $mfr->comment) {
                        $actdev->comment=$newcomment;
                        update_table("device","comment='".mysql_escape_string($newcomment)."' WHERE name='$name'");
                        if (strlen($newcomment)) {
                            $info_str="altered comment to \"".mysql_escape_string($newcomment)."\"";
                        } else {
                            $info_str="cleared comment";
                        }
                        insert_table("devicelog","0,$actdev->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'$info_str',null");
                    } else {
                        $actdev->comment=$mfr->comment;
                    }
                } else {
                    $actdev->comment=$mfr->comment;
                }
                // log entry
                $avn="{$name}_lfe";
                if (isset($vars[$avn]) && strlen(trim($vars[$avn]))) {
                    insert_table("devicelog","0,$actdev->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'".mysql_escape_string(trim($vars[$avn]))."',null");
                }
                // apc-connection
                if (in_array($actdev->idx,array_keys($out_dev_ref))) {
                    $actdev->out_dev_ref=$out_dev_ref[$actdev->idx];
                    foreach ($out_dev_ref[$actdev->idx] as $odf) {
                        $apcs[$odf->device]->set_outlet_info($odf->outlet,"$name ($odf->slave_info)",$actdev->group,$actdev->idx,$actdev->comment);
                        if (!in_array($apcs[$odf->device]->ip,$apc_resolve_dict)) {
                            $act_apc=&$apcs[$odf->device];
                            $apc_resolve_dict[$act_apc->ip]=&$apcs[$odf->device];
                            if (!in_array($act_apc->ip,$do_list[$boot_server[$act_apc->bootserver]])) $do_list[$boot_server[$act_apc->bootserver]][]=$act_apc->ip;
                        }
                    }
                }
                // image 
                $newimage=$mfr->newimage;
                if ($newimage=="") {
                    $set=1;
                    if (isset($sys_config["DEFAULT_IMAGE"])) {
                        $actdev->newimage=trim($sys_config["DEFAULT_IMAGE"]);
                    } else {
                        $actdev->newimage=$def_im_name;
                    }
                } else {
                    $set=0;
                    $actdev->newimage=$newimage;
                }
                $avn=$name."_im";
                if (isset($vars["newimage"]) && intval($vars["newimage"]) >= 0) $vars[$avn]=$vars["newimage"];
                if (isset($vars[$avn])) {
                    $av=$vars[$avn];
                    if ($actdev->newimage != $imnames[intval($av)]) {
                        $actdev->newimage=$imnames[intval($av)];
                        $set=1;
                    }
                }
                if ($set) {
                    update_table("device","newimage='$actdev->newimage' WHERE name='$name'");
                    insert_table("devicelog","0,$actdev->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'changed image to {$actdev->newimage}',null");
                }
                // partition type
                $partition_table=$mfr->partition_table;
                if ($partition_table) {
                    $set=0;
                    $actdev->part=$partition_table;
                } else {
                    $set=1;
                    if ($parts) {
                        $actdev->part=array_keys($parts);
                        $actdev->part=$actdev->part[0];
                    } else {
                        $actdev->part=0;
                    }
                }
                $avn="{$name}_pt";
                if (isset($vars["newpartition"]) && intval($vars["newpartition"]) >= 0) $vars[$avn]=$vars["newpartition"];
                if (isset($vars[$avn])) {
                    $av=$vars[$avn];
                    if ($actdev->part != $av) {
                        $actdev->part=$av;
                        $set=1;
                    }
                }
                if ($set) {
                    if ($actdev->part > 0) {
                        update_table("device","partition_table='$actdev->part' WHERE name='$name'");
                        insert_table("devicelog","0,$actdev->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'changed partition-table to {$parts[$actdev->part]['name']}',null");
                    }
                }
                // kernel
                $newkernel=$mfr->newkernel;
                if ($newkernel=="") {
                    $set=1;
                    if (isset($sys_config["DEFAULT_KERNEL"])) {
                        $actdev->newkernel=trim($sys_config["DEFAULT_KERNEL"]);
                    } else {
                        if ($kernels) {
                            $first_kern_name=array_keys($kernels);
                            $actdev->newkernel=$kernels[$first_kern_name[0]];
                        } else {
                            $actdev->newkernel="N/A";
                        }
                    }
                } else {
                    $set=0;
                    $actdev->newkernel=$newkernel;
                }
                $avn="{$name}_kn";
                //echo "***$avn***{$vars["newkernel"]}***{$vars[$avn]}***<br>";
                if (isset($vars["newkernel"]) && $vars["newkernel"] != "keep actual") $vars[$avn]=$vars["newkernel"];
                if (isset($vars[$avn])) {
                    $av=$vars[$avn];
                    //echo "***$avn***$av***$actdev->newkernel***<br>";
                    if ($actdev->newkernel != $av) {
                        $actdev->newkernel=$av;
                        $set=1;
                    }
                }
                $avn="{$name}_kpn";
                if (isset($vars["allkpars"]) && strlen(trim($vars["allkpars"]))) $avn="allkpars";
                if (isset($vars[$avn]) || is_set("allkpclear",&$vars)) {
                    $newkpn=$vars[$avn];
                    if (is_set("allkpclear",&$vars)) {
                        $newkpn="";
                    } else if ($avn == "allkpars" && $newkpn=="-") {
                        $newkpn="";
                    }
                    if ($newkpn != $actdev->kernel_append) {
                        $actdev->kernel_append=$newkpn;
                        update_table("device","kernel_append='$actdev->kernel_append' WHERE name='$name'");
                        if (strlen($newkpn)) {
                            $info_str="altered kernel_parameter to \"".mysql_escape_string($newkpn)."\"";
                        } else {
                            $info_str="cleared kernel_parameter";
                        }
                        insert_table("devicelog","0,$actdev->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'$info_str',null");
                        $set=1;
                    }
                }
                if ($set) {
                    update_table("device","newkernel='$actdev->newkernel' WHERE name='$name'");
                    insert_table("devicelog","0,$actdev->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'changed kernel to {$actdev->newkernel}',null");
                    $actdev->refresh_tk=1;
                }
            }
            $ping_array=array();
            foreach($boot_server as $idx=>$name) $ping_array[$name]=array();
            // get the state(s)
            foreach (array_keys($ipc) as $mn) {
                $myipc=&$ipc[$mn];
                $myipc->get_state($sys_db_con,$prod_nets);
                $name=$myipc->name;
                // target state stuff
                $new_ts=0;
                // new target state (?)
                if ($myipc->newstate==0) {
                    $new_ts=1;
                    // set newstate to installation
                    $myipc->newstate=$install_state;
                    $myipc->prod_link=1;
                }
                $avn=$name."_ts";
                if (isset($vars["set_all"]) && $vars["set_all"] != "keep") $vars[$avn]=$vars["set_all"];
                if (isset($vars[$avn])) {
                    $av=$vars[$avn];
                    if (preg_match("/^(\d+)_(\d+)$/",$av,$avp)) {
                        $newstate=intval($avp[1]);
                        $newplink=intval($avp[2]);
                    } else {
                        $newstate=intval($av);
                        $newplink=$myipc->prod_link;
                    }
                    if ($myipc->newstate != $newstate || $myipc->prod_link != $newplink) {
                        $myipc->newstate=$newstate;
                        $myipc->prod_link=$newplink;
                        $new_ts=1;
                    }
                }
                // mac-address handling (including dhcp-stuff)
                $avn=$name."_dm";
                $ggreedy="none";
                if (isset($vars[$global_greedy_flag])) $ggreedy=$vars[$global_greedy_flag];
                if ((isset($vars[$avn]) && $vars[$avn]) or $ggreedy != "none") {
                    $avv=$vars[$avn];
                    if ($ggreedy != "none") $avv=$ggreedy;
                    if ($avv == "set") {
                        $myipc->dhcp_mac=1;
                        update_table("device","dhcp_mac=1 WHERE name='$name'");
                        insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'enabled greedy mode',null");
                    } else if ($avv == "del") {
                        $myipc->dhcp_mac=0;
                        update_table("device","dhcp_mac=0 WHERE name='$name'");
                        insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'disabled greedy mode',null");
                    }
                }
                $avn=$name."_mac";
                if (isset($vars[$avn]) && $vars[$avn]) {
                    $newmac=strtolower($vars[$avn]);
                    // 0 ... keep, 1 ... alter, 2 ... write, 3 ... delete
                    $mac_com=$vars[$name."_newmac"];
                    if ($mac_com > 0) {
                        $alter_mac=0;
                        if ($myipc->macadr != $newmac and preg_match("/^([a-f0-9]{2}:){5}[a-f0-9]{2}$/",$newmac)) $alter_mac=1;
                        // determine command for mother
                        $mac_com_array=array(1=>array(0=>"NONE",1=>"update_macadr"),
                                             2=>array(0=>"write_macadr",1=>"write_macadr"),
                                             3=>array(0=>"delete_macadr",1=>"delete_macadr"));
                        $mac_com=$mac_com_array[$mac_com][$alter_mac];
                        //echo "mc: $mac_com ; am: $alter_mac<br>";
                        $mr2=query("SELECT n.netdevice_idx FROM netdevice n, device d WHERE d.name='$name' AND d.bootnetdevice=n.netdevice_idx AND d.device_idx=n.device");
                        if (mysql_num_rows($mr2)) {
                            $mfr=mysql_fetch_object($mr2);
                            if ($alter_mac) {
                                $oldmac=$myipc->macadr;
                                $myipc->macadr=$newmac;
                                update_table("netdevice","macadr='$myipc->macadr' WHERE netdevice_idx=$mfr->netdevice_idx");
                                insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'altered macadr from $oldmac to $newmac',null");
                            }
                            if ($mac_com != "NONE") {
                                $ret=contact_server($sys_config,"mother_server",8001,"$mac_com $name",$timeout=0,$hostname=$boot_server[$myipc->bootserver]);
                                process_ret(&$hcproto,"mother_server",8001,"$mac_com",$ret,array($name));
                                insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'$ret',null");
                                $mr2=query("SELECT d.dhcp_write,d.dhcp_written FROM device d WHERE d.name='$name'");
                                $mfr=mysql_fetch_object($mr2);
                                $myipc->dhcp_write=$mfr->dhcp_write;
                                $myipc->dhcp_written=$mfr->dhcp_written;
                            }
                        }
                    }
                }
                if ((isset($vars[$name."_rb"]) && $vars[$name."_rb"]=="reboot") || (isset($vars["all_op"]) && $vars["all_op"]=="reboot")) {
                    $reboot_array[$boot_server[$myipc->bootserver]][]=$name;
                    insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'reboot via bootcontrol',null");
                } else if ((isset($vars[$name."_rb"]) && $vars[$name."_rb"]=="poweroff") || (isset($vars["all_op"]) && $vars["all_op"]=="poweroff")) {
                    $power_off_array[$boot_server[$myipc->bootserver]][]=$name;
                    insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'power-off via bootcontrol',null");
                } else if ((isset($vars[$name."_rb"]) && $vars[$name."_rb"]=="halt") || (isset($vars["all_op"]) && $vars["all_op"]=="halt")) {
                    $halt_array[$boot_server[$myipc->bootserver]][]=$name;
                    insert_table("devicelog","0,$myipc->idx,$uls_idx,{$sys_config['user_idx']},{$log_status['i']->log_status_idx},'halt via bootcontrol',null");
                } else {
                    $ping_array[$boot_server[$myipc->bootserver]][]=$name;
                }
                $myipc->new_ts=$new_ts;
            }
            foreach ($reboot_array as $server=>$nodes) {
                if (count($nodes)) {
                    $ret=contact_server($sys_config,"mother_server",8001,"reboot ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    $rets=preg_split("/#/",$ret);
                    if (count($rets) > 1) {
                        $idx=0;
                        foreach ($nodes as $name) {
                            $idx++;
                            $myipc=&$ipc[$name];
                            $infstr="Rebooting host $name on $server";
                            $ret=$rets[$idx];
#echo $infstr."<br>";
                            $hcproto->add_message($infstr,$ret,preg_match("/^ok.*rebooting.*$/",$ret));
                        }
                    } else {
                        $t_verbose=1;
                        $hcproto->add_message($ret,"error",0);
                    }
                }
            }
            foreach ($halt_array as $server=>$nodes) {
                if (count($nodes)) {
                    $ret=contact_server($sys_config,"mother_server",8001,"halt ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    $rets=preg_split("/#/",$ret);
                    if (count($rets) > 1) {
                        $idx=0;
                        foreach ($nodes as $name) {
                            $idx++;
                            $myipc=&$ipc[$name];
                            $infstr="Halting host $name on $server";
                            $ret=$rets[$idx];
                            $hcproto->add_message($infstr,$ret,preg_match("/^ok.*halting.*$/",$ret));
                        }
                    } else {
                        $t_verbose=1;
                        $hcproto->add_message($ret,"error",0);
                    }
                } 
            }
            foreach ($power_off_array as $server=>$nodes) {
                if (count($nodes)) {
                    $ret=contact_server($sys_config,"mother_server",8001,"poweroff ".implode(":",$nodes),$timeout=0,$hostname=$server);
                    $rets=preg_split("/#/",$ret);
                    if (count($rets) > 1) {
                        $idx=0;
                        foreach ($nodes as $name) {
                            $idx++;
                            $myipc=&$ipc[$name];
                            $infstr="Power-off host $name on $server";
                            $ret=$rets[$idx];
                            $hcproto->add_message($infstr,$ret,preg_match("/^ok.*poweroff.*$/",$ret));
                        }
                    } else {
                        $t_verbose=1;
                        $hcproto->add_message($ret,"error",0);
                    }
                }
            }
            foreach ($ping_array as $server=>$nodes) {
                if (count($nodes)) {
                    // clear reqstate-field
                    $node_f=array();
                    foreach ($nodes as $name) $node_f[]="name='$name'";
                    update_table("device","reqstate='no server-response' WHERE ".implode(" OR ",$node_f));
                    // calculate timeout
                    $act_to=10+intval(count($nodes)/10);
                    $ret=contact_server($sys_config,"mother_server",8001,"status ".implode(":",$nodes),$timeout=$act_to,$hostname=$server);
                    $rets=preg_split("/#/",$ret);
                    $head_string=array_shift($rets);
                    $head_error=(preg_match("/^error.*$/",$head_string));
                    $idx=0;
                    foreach ($nodes as $name) {
                        $myipc=&$ipc[$name];
                        $infstr="Pinging host $name on bs $server";
                        if ($head_error) {
                            $myipc->up=0;
                            $myipc->actnet="???";
                        } else {
                            $ret=$rets[$idx];
#echo $name." - ".$ret."<br>\n";
                            if (preg_match("/^warn.*$/",$ret)) {
                                $myipc->up=2;
                                if (preg_match("/^warn.*\((.+)\).*$/",$ret,$what)) {
                                    $myipc->actnet=$what[1];
                                } else {
                                    $myipc->actnet="???";
                                }
                            } else if (preg_match("/^\s*error.*$/",$ret)) {
                                $myipc->up=0;
                                $myipc->actnet="???";
                            } else {
                                $myipc->up=1;
                                if (preg_match("/^ok.*\((.+)\).*$/",$ret,$what)) {
                                    $myipc->actnet=$what[1];
                                } else {
                                    $myipc->actnet="???";
                                }
                            }
                        }
                        $hcproto->add_message($infstr,$ret,$myipc->up);
                        $idx++;
                    }
                }
            }
            foreach (array_keys($ipc) as $mn) {
                $myipc=&$ipc[$mn];
                $myipc->get_state($sys_db_con,$prod_nets);
            }
            // read the dotfiles
            foreach ($node_bs_array as $server=>$nodes) {
                if (count($nodes)) {
                    $rets=contact_server($sys_config,"mother_server",8001,"readdots ".implode(":",$nodes),$timeout=0,$hostname=$server);
                }
            }
            foreach (array_keys($ipc) as $mn) {
                $myipc=&$ipc[$mn];
                $mres_t=query("SELECT d.imageversion,d.actimage,d.actkernel,d.kernelversion,d.act_partition_table FROM device d WHERE d.name='$myipc->name'");
                $mfr_t=mysql_fetch_object($mres_t);
                $myipc->imageversion=$mfr_t->imageversion;
                $myipc->actimage=$mfr_t->actimage;
                $myipc->actkernel=$mfr_t->actkernel;
                $myipc->kernelversion=$mfr_t->kernelversion;
                $myipc->act_partition_table=$mfr_t->act_partition_table;
            }
            // apc control
            if (in_array("adia",$add_info_set)) {
                update_apc_info($sys_config,$do_list,$apc_resolve_dict);
                foreach ($apcs as $apcnum=>$apc) {
                    $sstr=$apc->create_apc_string($sys_config,$vars,$apc_outlet_states,$apc_master_states,$apc_p_delays,$apc_r_delays,$log_status);
                    if (strlen($sstr) && $apc->up) {
                        $rets=contact_server($sys_config,"mother_server",8001,"apc_com $apc->ip $sstr",$timeout=20,$hostname=$boot_server[$apc->bootserver]);
                        $apc->ping($sys_config,$boot_server);
                        $apc->rescan();
                        //echo "*$sstr<br>";
                    }
                }
            }
            // maybe we have to change the target_state
            foreach (array_keys($ipc) as $mn) {
                $myipc=&$ipc[$mn];
                $name=$myipc->name;
                $new_ts=$myipc->new_ts;
                if ($myipc->up==1) {
                    $net_ok=0;
                    foreach ($prod_nets as $n_idx=>$net_l) {
                        list($net_id,$net_name)=$net_l;
                        if ($net_id == $myipc->actnet) $net_ok=1;
                    }
                    //echo "$myipc->recvstate $myipc->reqstate : $myipc->newstate ; $install_state , $myipc->newimage - $myipc->actimage <br>";
                    //echo "$net_ok *$myipc->actnet* $myipc->imageversion : ".$images[$myipc->actimage]["version"]."<br>";
                    if ( $net_ok
                         && preg_match("/^up to.*$/",$myipc->recvstate)
                         && preg_match("/^up to.*/",$myipc->reqstate)
                         && $myipc->newstate==$install_state
                         && $myipc->newimage==$myipc->actimage
                         && $myipc->imageversion==$images[$myipc->actimage]["version"] ) {
                        //echo "************";
                        if (isset($vars["cint"])) {
                            $myipc->newstate=$boot_state;
                            $new_ts=1;
                        } else {
                            $c_possible=1;
                        }
                    }
                }
                if ($new_ts) {
                    update_table("device","newstate=$myipc->newstate, prod_link=$myipc->prod_link WHERE name='$name'");
                    $myipc->refresh_tk=1;
                }
                if ($myipc->refresh_tk) {
                    $refresh_tk_array[$boot_server[$myipc->bootserver]][]=$name;
                }
            }
            // refresh-it
            foreach ($refresh_tk_array as $server=>$nodes) {
                if (count($nodes)) {
                    $rets=contact_server($sys_config,"mother_server",8001,"refresh_tk ".implode(":",$nodes),$timeout=0,$hostname=$server);
                }
            }
            $messtr="Please select devicegroup or device(s) by their name";
            if ($macmapping) $messtr.=" or MAC address";
            $messtr.=":";
            message ($messtr);
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\"><tr>";
            $numlines=1;
            echo "<td><select name=\"addinfo[]\" multiple size=5 >";
            foreach ($add_infos as $short=>$stuff) {
                echo "<option value=\"$short\" ";
                if (in_array($short,$add_info_set)) {
                    echo " selected ";
                    $numlines+=$stuff[1];
                }
                echo ">$stuff[0]</option>\n";
            }
            echo "</select></td>";
            //             echo "<td><table class=\"blind\">";
            //             foreach ($add_infos as $short=>$stuff) {
            //                 echo "<tr><td class=\"right\">";
            //                 echo "<input type=checkbox name=\"addinfo_$short\" ";
            //                 if (in_array($short,$add_info_set)) echo " checked ";
            //                 echo "/>$stuff[0]</td></tr>\n";
            //             }
            //             echo "</table></td>\n";
            if (in_array("adih",$add_info_set) && in_array("adil",$add_info_set)) $numlines--;
            echo "<td>&nbsp;&nbsp;</td>";
            echo "<td><select name=\"selgroup[]\" multiple size=5>";
            foreach ($machgroups as $mg=>$mgv) {
                echo "<option value=\"$mg\"";
                if ($mgv["selected"]) echo " selected";
                echo ">$mg";
                if ($mgv["num"]) echo " (".get_plural("device",$mgv["num"],1).")";
                echo "</option>\n";
            }
            echo "</select>";
            hidden_sid();
            echo "</td>\n";
            echo "<td>&nbsp;&nbsp;</td>";
            echo "<td><select name=\"selmach[]\" size=5 multiple>";
            $num_greedy=0;
            $num_nodhcp=0;
            $num_etherboot_invalid=0;
            //if (!$actdev->etherboot_valid) $num_etherboot_invalid++;
            foreach ($machgroups as $act_group=>$display_g) {
                //list($n1,$n2,$sel,$mach_list)=$display_g;
                $num_mach=sizeof($display_g["list"]);
                echo "<option value=d disabled>$act_group [ ".get_plural("machine",$num_mach,1)." ]</option>\n";
                $mres=query("SELECT d.name,d.device_idx,d.comment,d.dhcp_mac,d.dhcp_written,d.bootserver,d.etherboot_valid FROM device d WHERE ( d.name='".implode("' OR d.name='",$display_g["list"])."') ORDER by d.name");
                while ($mfr=mysql_fetch_object($mres)) {
                    $name=$mfr->name;
                    $act_c="bc";
                    $dhcp_str_f=array();
                    if ($mfr->dhcp_mac) {
                        $act_c.="gr";
                        $num_greedy++;
                        $dhcp_str_f[]="gr";
                    }
                    if (!$mfr->dhcp_written) {
                        $act_c.="nw";
                        $num_nodhcp++;
                        $dhcp_str_f[]="dw";
                    }
                    if (!$mfr->etherboot_valid) {
                        $num_etherboot_invalid++;
                        $dhcp_str_f[]="ed";
                    }
                    if ($dhcp_str_f) $dhcp_str_f[]="";
                    echo "<option class=\"$act_c\" value=\"$name\"";
                    if (in_array($name,$actmach)) echo " selected ";
                    echo ">".implode(",",$dhcp_str_f)."$name ";
                    if ($mfr->comment) echo " ($mfr->comment)";
                    echo ", bs={$boot_server[$mfr->bootserver]}</option>\n";
                }
            }
            echo "</select></td>";
            if ($macmapping) {
                echo "<td>&nbsp;&nbsp;</td>";
                $mres=query("SELECT n.macadr,d.name,d.comment FROM device d,netdevice n WHERE d.device_idx=n.device AND d.bootnetdevice=n.netdevice_idx");
                if (mysql_num_rows($mres)) {
                    echo "<td><select name=\"selmachmac[]\" size=5 multiple>";
                    $macadr=array();
                    while ($mfr=mysql_fetch_object($mres)) {
                        $macadr[$mfr->macadr][]=array($mfr->name,$mfr->comment);
                    }
                    ksort($macadr);
                    foreach (array_keys($macadr) as $mnpr) {
                        $d_array=&$macadr[$mnpr];
                        $nlist="";
                        foreach ($d_array as $d_entry) {
                            list($mnp,$mna)=$d_entry;
                            $nlist.=$mnp." ";
                            if ($mna) $nlist.=" [$mna] ";
                        }
                        echo "<option value=\"$mnp\"";
                        if (in_array($mnp,$actmach)) echo " selected";
                        echo ">$mnpr ( $nlist )</option>\n";
                    }
                    echo "</select>";
                    echo "</td>\n";
                }
            }
            echo "</tr></table></div>\n";
            if ($num_greedy || $num_nodhcp || $num_etherboot_invalid) {
                $att_f=array();
                if ($num_greedy) $att_f[]=get_plural("greedy machine",$num_greedy,1);
                if ($num_nodhcp) $att_f[]=get_plural("machine",$num_nodhcp,1)." without a valid DHCP-entry";
                if ($num_etherboot_invalid) $att_f[]=get_plural("machine",$num_etherboot_invalid,1)." without a valid etherboot-dir";
                $mess_str="Attention ! Found ".implode(" and ",$att_f)." !";
                message($mess_str,$type=1);
            }
            echo "<div class=\"center\">";
            echo "<h3>Verbose: ";
            echo "<input type=checkbox name=\"verbose\" ";
            if ($verbose) echo " checked ";
            echo "/>, show MAC-mapping: <input type=checkbox name=\"macmapping\" ";
            if ($macmapping) echo " checked ";
            echo "/>, showing MAC-bootlog from ";
            echo "<select name=\"actmbldate\">";
            $mres=query("SELECT date FROM macbootlog LIMIT 1");
            if ($mfr=mysql_fetch_object($mres)) {
                $first_mbl_date=substr($mfr->date,0,8);
            } else {
                $first_mbl_date=$act_mbl_date;
            }
            $first_mbl_year =intval(substr($first_mbl_date,0,4));
            $first_mbl_month=intval(substr($first_mbl_date,4,2));
            $first_mbl_day  =intval(substr($first_mbl_date,6,2));
            $last_mbl_year =intval(substr($last_mbl_date,0,4));
            $last_mbl_month=intval(substr($last_mbl_date,4,2));
            $last_mbl_day  =intval(substr($last_mbl_date,6,2));
            $act_mbl_year=$last_mbl_year;
            $act_mbl_month=$last_mbl_month;
            $act_mbl_day=$last_mbl_day;
            $max_dt_entries=100;
            $last_wday="-1";
            while (true) {
                $act_tstruct=mktime(0,0,0,$act_mbl_month,$act_mbl_day,$act_mbl_year);
                $act_wday=strftime("%u",$act_tstruct);
                if ($last_wday == "-1") echo "<option value=\"$none_mbl_date\">show nothing</option>\n";
                if ($act_wday == "7" || $last_wday == "-1") echo "<option disabled>--------------------</option>\n";
                $last_wday=$act_wday;
                $act_dstr=sprintf("%04d%02d%02d",$act_mbl_year,$act_mbl_month,$act_mbl_day);
                echo "<option value=\"$act_dstr\"";
                if ($act_mbl_date == $act_dstr) echo " selected";
                echo ">".strftime("%A, %e. %b %Y",$act_tstruct)."</option>\n";
                if ($act_dstr == $first_mbl_date) break;
                if (!--$act_mbl_day) {
                    if (--$act_mbl_month) {
                        $act_mbl_day=31;
                        while (!checkdate($act_mbl_month,$act_mbl_day,$act_mbl_year)) $act_mbl_day--;
                    } else {
                        $act_mbl_year--;
                        $act_mbl_month=12;
                        $act_mbl_day=31;
                    }
                }
                if (!$max_dt_entries--) break;
            }
            echo "</select>\n";
            //echo ", showing $first_mbl_date - $act_mbl_date";
            echo "<input type=submit value=\"select\" /></h3>";
            echo "</div>";
            echo "</form>\n";
        }
        $mres=query("SELECT b.device,b.macadr,b.date,b.type,b.ip,DATE_FORMAT(b.date,'%H:%i:%s') as fdate,b.log_source FROM macbootlog b WHERE b.date > '{$act_mbl_date}000000' AND b.date < '{$act_mbl_date}235959' ORDER BY date");
        $mac_list=array();
        if (mysql_num_rows($mres)) {
            $macbootlog_str="; showing ".strval(mysql_num_rows($mres))." MAC-bootlog entries";
            $mac_list=array();
            $mac_device_list=array();
            while ($mfr=mysql_fetch_object($mres)) {
                $mac_list[]=$mfr;
                if (!in_array($mfr->device,$mac_device_list) && $mfr->device) $mac_device_list[]=$mfr->device;
            }
            if (count($mac_device_list)) {
                $mres=query("SELECT d.name,d.device_idx FROM device d WHERE d.device_idx=".implode(" OR d.device_idx=",$mac_device_list));
                $mac_device_list=array();
                while ($mfr=mysql_fetch_object($mres)) $mac_device_list[$mfr->device_idx]=$mfr->name;
            }
        } else {
            if ($act_mbl_date == $none_mbl_date) {
                $macbootlog_str="";
            } else {
                $macbootlog_str="; found no MAC-bootlog entries";
            }
        }
        if ($verbose || $t_verbose) $hcproto->print_messages("");
        if (sizeof($ipc) > 0) {
            if (sizeof($display_a) > 1) {
                $tot_mach=0;
                $tot_grp=0;
                foreach ($display_a as $lk=>$lv) {
                    $tot_grp+=1;
                    list($n1)=$lv;
                    $tot_mach+=$n1;
                }
                $mes_str="Found $tot_mach devices in $tot_grp devicegroups";
            } else {
                reset($display_a);
                list($n1,$n2,$mach_list)=current($display_a);
                if ($n1 == 1) {
                    $mes_str="Found device {$mach_list[0]} in devicegroup ".key($display_a);
                } else {
                    $mes_str="Found $n1 devices in machinegroup ".key($display_a);
                }
            }
            message($mes_str.$macbootlog_str);
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
            if (in_array("adia",$add_info_set)) echo "<input type=hidden name=\"apc_all_control\" value=\"6\" />\n";
            echo "<table class=\"normal\">\n";
            echo "<tr>";
            echo "<th class=\"name\">Node</th>";
            echo "<th class=\"bctstate\">target state</th>";
            echo "<th class=\"bcreboot\">none/reboot/halt/poweroff</th>";
            echo "<th class=\"bcinitstate\">recv</th>";
            echo "<th class=\"bcinitstate\">req</th>";
            echo "<th class=\"bcinitstate\">network</th>";
            echo "</tr>";
            $lastmg="none";
            foreach ($display_a as $act_group=>$display_g) {
                list($n1,$n2,$mach_list)=$display_g;
                if (sizeof($display_a) > 1) echo "<tr><td colspan=\"6\" class=\"machinegroup\">devicegroup: $act_group , selected $n1 of $n2 devices</td></tr>\n";
                foreach ($mach_list as $mach_name) {
                    $ip=&$ipc[$mach_name];
                    if ($ip->up == 1 && $ip->etherboot_valid && !preg_match("/rror/",$ip->reqstate)) {
                        $uds="up";
                    } else if ($ip->up == 2 || ($ip->up == 1 && !$ip->etherboot_valid) || ($ip->up == 1 && preg_match("/rror/",$ip->reqstate))) {
                        $uds="warn";
                    } else {
                        $uds="down";
                    }
                    echo "<tr>";
                    echo "<td class=\"name$uds\" rowspan=\"$numlines\" >$ip->name";
                    $ip->mark_machine();
                    echo "</td>";
                    // always show t_state and some basic info
                    echo "<td class=\"bctstate$uds\">";
                    show_t_state($tstates,$prod_nets,"$ip->name.ts",$ip->newstate,$ip->prod_link);
                    echo "</td>";
                    echo "<td class=\"bcreboot$uds\">";
                    $ip->show_ping();
                    echo "</td>";
                    echo "<td class=\"bcinitstate0$uds\">{$ip->recvstate}</td>\n";
                    echo "<td class=\"bcinitstate1$uds\">{$ip->reqstate}</td>\n";
                    echo "<td class=\"bcinitstate2$uds\">".$ip->get_actnetstr()."</td>\n";
                    echo "</tr>\n";
                    if (in_array("adia",$add_info_set)) {
                        echo "<tr>";
                        echo "<td class=\"bcpart$uds\" colspan=\"5\">APC Info: ";
                        if ($ip->out_dev_ref) {
                            echo "connected to ".strval(count($ip->out_dev_ref))." outlets: ";
                            foreach ($ip->out_dev_ref as $odf) {
                                $act_apc=&$apcs[$odf->device];
                                echo "$act_apc->name/$odf->outlet (state is {$act_apc->states[$odf->outlet]['state']}), ";
                                echo "<select name=\"apc.{$odf->device}.o{$odf->outlet}\" >";
                                foreach ($apc_outlet_states as $acti=>$acts) {
                                    echo "<option value=\"$acti\" ";
                                    if ($acti==0) echo " selected ";
                                    echo ">$acts</option>\n";
                                }
                                echo "</select>";
                            }
                        } else {
                            echo "not connected to an APC";
                        }
                        echo "</td>";
                        echo "</tr>\n";
                    }
                    if (in_array("adip",$add_info_set)) {
                        echo "<tr>";
                        echo "<td class=\"bcpart$uds\" colspan=\"5\">New partition: ";
                        show_part($parts,"{$ip->name}.pt",$ip->part);
                        echo ", actual: ";
                        if ($ip->act_partition_table) {
                            echo $parts[$ip->act_partition_table]["name"]." (".$parts[$ip->act_partition_table]["info"].")";
                        } else {
                            echo "not set";
                        }
                        echo "</td>";
                        echo "</tr>\n";
                    }
                    if (in_array("adii",$add_info_set)) {
                        echo "<tr>";
                        echo "<td class=\"bcimage$uds\" colspan=\"5\">New image: ";
                        list($targim,$short_ti)=$ip->show_image($images);
                        $instim=$ip->get_actimage();
                        echo ", actual: ";
                        if ($instim == $short_ti) {
                            echo "same at $ip->last_install";
                        } else {
                            echo "$instim at $ip->last_install";
                        }
                        echo "</td>";
                        echo "</tr>\n";
                    }
                    if (in_array("adik",$add_info_set)) {
                        echo "<tr><td class=\"bckernel$uds\" colspan=\"5\">New kernel: ";
                        $targkern=$ip->show_kernel($kernels);
                        $instkern=$ip->get_actkernel();
                        echo ", actual: ";
                        if ($instkern == $targkern) {
                            echo "same at $ip->last_kernel";
                        } else {
                            echo "$instkern at $ip->last_kernel";
                        }
                        echo "</td></tr>\n";
                        echo "<tr><td colspan=\"5\"class=\"bckernel$uds\">Kernelparameter: ";
                        $ip->show_kernel_parameter();
                        echo "</td></tr>\n";
                    }
                    if (in_array("adim",$add_info_set)) {
                        echo "<tr>";
                        echo "<td class=\"bcmac$uds\" colspan=\"3\" >";
                        $ip->show_macadr();
                        echo $ip->new_macadr();
                        echo "</td>";
                        echo "<td class=\"bcmac$uds\" colspan=\"2\" >";
                        $ip->show_greedy_mode();
                        echo "</td>";
                        echo "</tr>\n";
                    }
                    if (in_array("adic",$add_info_set)) {
                        echo "<tr>";
                        echo "<td class=\"bcinfo$uds\" colspan=\"2\">Comment: ";
                        $ip->show_comment();
                        echo "</td>";
                        echo "<td class=\"bcinfo$uds\" colspan=\"3\">New log entry: ";
                        $ip->new_log_entry();
                        echo "</td>";
                        echo "</tr>\n";
                    }
                    if (in_array("adil",$add_info_set) || in_array("adih",$add_info_set)) {
                        echo "<tr>";
                        echo "<td class=\"blind\" colspan=\"5\" >";
                        echo "<table class=\"blind\">";
                        echo "<tr>";
                        if (in_array("adih",$add_info_set)) {
                            $ip->show_machine_history(1);
                        }
                        if (in_array("adil",$add_info_set)) {
                            $avn=$ip->name."logf";
                            if (in_array($avn,$varkeys)) {
                                $actlog=$vars[$avn];
                            } else {
                                $actlog="";
                            }
                            $ip->show_syslog($avn,$actlog,1);
                        }
                        echo "</tr></table></td>";
                        echo "</tr>\n";
                    }
                }
            }
            echo "</table>";
            echo "<table class=\"normalnf\">\n";
            echo "<tr>";
            echo "<td class=\"nameup\" rowspan=\"$numlines\" >all devices";
            $ip->mark_machine();
            echo "</td>";
            // always show t_state and some basic info
            echo "<td class=\"bctstateup\">";
            show_t_state($tstates,$prod_nets,"set_all",-1,1);
            echo "</td>";
            echo "<td class=\"bcrebootup\">";
            echo "<input type=radio name=\"all_op\" value=\"none\" checked />&nbsp;";
            echo "<input type=radio name=\"all_op\" value=\"reboot\" />&nbsp;";
            echo "<input type=radio name=\"all_op\" value=\"halt\" />&nbsp;";
            echo "<input type=radio name=\"all_op\" value=\"poweroff\" />&nbsp;";
            echo "</td>";
            echo "</tr>\n";
            if (in_array("adip",$add_info_set)) {
                echo "<tr>";
                echo "<td class=\"bcpartup\" colspan=\"2\">New partition: ";
                show_part($parts,"newpartition",-1,1);
                echo "</td>";
                echo "</tr>\n";
            }
            if (in_array("adii",$add_info_set)) {
                echo "<tr>";
                echo "<td class=\"bcimageup\" colspan=\"2\">New image: ";
                echo "<select name=\"newimage\">";
                echo "<option value=-1>keep actual</option>\n";
                $idx=0;
                foreach (array_keys($images) as $actt) {
                    $lock_str=(($images[$actt]["locked"]) ? "LOCKED: " : "");
                    echo "<option value=\"$idx\" >$lock_str$actt [{$images[$actt]['version']}], {$images[$actt]['size']}, builddate: {$images[$actt]['short_bdate']} on {$images[$actt]['build_machine']}</option>\n";
                    $idx++;
                }
                echo "</select>\n";
                echo "</td>";
                echo "</tr>\n";
            }
            if (in_array("adik",$add_info_set)) {
                echo "<tr><td class=\"bckernelup\" colspan=\"2\">New kernel: ";
                echo "<select name=\"newkernel\">";
                echo "<option value=\"keep actual\">keep actual</option>\n";
                foreach ($kernels as $actn=>$kstuff) echo "<option value=\"$actn\">$actn [ {$kstuff['version']} ]</option>\n";
                echo "</select>";
                echo "</td></tr>\n";
                echo "<tr><td colspan=\"2\"class=\"bckernelup\">Kernelparameter: ";
                echo "all kparams: <input name=\"allkpars\" maxlength=\"64\" size=\"40\" value=\"\" />, clear all: <input type=checkbox name=\"allkpclear\"/>";
                echo "</td></tr>\n";
            }
            if (in_array("adim",$add_info_set)) {
                echo "<tr>";
                echo "<td class=\"bcmacup\" colspan=\"2\" >";
                echo "all greedy modes: ";
                echo "<select name=\"$global_greedy_flag\">";
                echo "<option value=\"none\">keep</option>\n";
                echo "<option value=\"set\">enable</option>\n";
                echo "<option value=\"del\">disable</option>\n";
                echo "</select></td>\n";
                echo "</tr>\n";
            }
            echo "</table>\n";
            echo "<div class=\"center\">";
            if ($c_possible) {
                echo "fix installed: <input type=checkbox name=\"cint\" value=\"fix installed\" />&nbsp&nbsp\n";
            }
            echo "</div>\n";
            echo "<div class=\"center\"><input type=submit value=\"submit\"></div>\n";
            echo "{$hiddenmach}{$hiddenverbose}{$hiddenmacmapping}{$hiddenmacbootlog}{$hidden_add_info}";
            hidden_sid();
            echo "</div>\n";
            echo "</form>\n";
        } else {
            message ("No devices found $macbootlog_str");
        }
        if ($mac_list) {
            $num_max_rows=min(2,sizeof($mac_list));
            $extra_rows=$num_max_rows-sizeof($mac_list)%$num_max_rows;
            if ($extra_rows==$num_max_rows) $extra_rows=0;
            while ($extra_rows--) $mac_list[]="";
            $num_macs=sizeof($mac_list);
            $num_lines=$num_macs/$num_max_rows;
            echo "<table class=\"normal\">";
            echo "<tr>";
            for ($idx=0;$idx<$num_max_rows;$idx++) {
                echo "<th class=\"macblidx\">Idx</th><th class=\"mactype\">Type</th><th class=\"macaddr\">MAC-Address</th>";
                echo "<th class=\"macname\">Device</th><th class=\"macname\">BDev</th><th class=\"macip\">IP/option</th><th class=\"mactime\">time</th>";
            }
            echo "</tr>\n";
            $log_sources=get_all_log_sources();
            $num_rows=0;
            $act_idx=0;
            for ($idx=0;$idx<$num_macs;$idx++) {
                if (!$num_rows) echo "<tr>";
                $mac_entry=$mac_list[$act_idx];
                if ($mac_entry) {
                    echo "<td class=\"macblidx\">$act_idx</td>";
                    echo "<td class=\"mactype\">DHCP$mac_entry->type</td>";
                    echo "<td class=\"macaddr\">$mac_entry->macadr</td>";
                    echo "<td class=\"macname\">";
                    if (in_array($mac_entry->device,array_keys($mac_device_list))) {
                        echo $mac_device_list[$mac_entry->device];
                    } else {
                        echo "---";
                    }
                    echo "</td>";
                    echo "<td class=\"macname\">";
                    if ($mac_entry->log_source && in_array($mac_entry->log_source,array_keys($log_sources))) {
                        echo $log_sources[$mac_entry->log_source]->devname;
                    } else {
                        echo "---";
                    }
                    echo "</td>\n";
                    echo "<td class=\"macip\">$mac_entry->ip</td>";
                    echo "<td class=\"mactime\">$mac_entry->fdate</td>";
                } else {
                    foreach (array("blidx","type","addr","name","name","ip","time") as $ctype) echo "<td class=\"mac$ctype\">&nbsp;</td>\n";
                }
                $act_idx+=$num_lines;
                if ($act_idx >= $num_macs) $act_idx+=1-$num_max_rows*$num_lines;
                $num_rows++;
                if ($num_rows == $num_max_rows) {
                    echo "</tr>";
                    $num_rows=0;
                }
            }
            echo "</table>\n";
        }
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
