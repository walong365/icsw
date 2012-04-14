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
$apc_outlet_states=array(0=>"---",1=>"Immediate on",2=>"Immediate off",3=>"Immediate reboot",5=>"Delayed on",6=>"Delayed off",7=>"Delayed reboot");
$apc_master_states=array(-1=>"Update",6=>"Nothing",1=>"Immediate on",3=>"Immediate off",4=>"Immediate reboot",2=>"Sequenced on",7=>"Sequenced off",5=>"Sequenced reboot");
$apc_p_delays=array(-1=>array("Never",8),0=>array("Immediate",1),15=>array("15 Seconds",2),30=>array("30 Seconds",3),
                    45=>array("45 Seconds",4),60=>array("1 Minute",5),120=>array("2 Minutes",6),300=>array("5 Minutes",7));
$apc_r_delays=array(5=>array("5 Seconds",1),10=>array("10 Seconds",2),15=>array("15 Seconds",3),20=>array("20 Seconds",4),
                    30=>array("30 Seconds",5),45=>array("45 Seconds",6),60=>array("1 Minute",7));
class apc {
    var $ip,$states,$idx,$pod,$rd,$pod,$name,$up,$groups,$state,$bootserver;
    function apc($ip,$name,$idx,$bootserver) {
        $this->ip=$ip;
        $this->idx=$idx;
        $this->bootserver=$bootserver;
        $this->up=0;
        $this->pod=0;
        $this->rd=0;
        $this->state="ok";
        $this->groups="";
        $this->name=$name;
        $this->states=array();
        foreach (range(1,8) as $r) $this->states[$r]=array("type"=>"-");
    }
    function set_down() {
        $this->up=0;
        $this->state="down";
    }
    function set_up() {
        $this->up=1;
        $this->state="ok";
    }
    function ping($config,$bs) {
        $ret=contact_server($config,"mother_server",8001,"ping $this->ip",$timeout=0,$hostname=$bs[$this->bootserver]);
        $rets=preg_split("/#/",$ret);
        if (preg_match("/^ok/",$rets[1])) {
            $this->up=1;
            $this->state="ok";
        } else {
            $this->up=0;
            $this->state="down";
        }
    }
    function rescan() {
        if ($this->up) {
            $mres=query("SELECT d.power_on_delay,d.reboot_delay FROM device d WHERE d.device_idx=$this->idx");
            $mfr=mysql_fetch_object($mres);
            $this->pod=$mfr->power_on_delay;
            $this->rd=$mfr->reboot_delay;
            $mres=query("SELECT o.outlet,o.state,o.power_on_delay,o.power_off_delay,o.reboot_delay FROM msoutlet o WHERE o.device=$this->idx ORDER BY o.outlet");
            while ($mfr=mysql_fetch_object($mres)) {
                $onum=strval($mfr->outlet);
                $this->states[$onum]["state"]=$mfr->state;
                $this->states[$onum]["pond"]=$mfr->power_on_delay;
                $this->states[$onum]["poffd"]=$mfr->power_off_delay;
                $this->states[$onum]["rebd"]=$mfr->reboot_delay;
            }
        } else {
            foreach (range(1,8) as $r) {
                $this->states[$r]["state"]="unknown";
                $this->states[$r]["pond"]=0;
                $this->states[$r]["poffd"]=0;
                $this->states[$r]["rebd"]=0;
            }
        }
    }
    function getoutname($num) {
        if (isset($this->states[$num]["nodename"])) {
            $msc=$this->states[$num]["nodename"];
            if ($this->states[$num]["dev_info"]) $msc.=", ".$this->states[$num]["dev_info"];
            if ($this->states[$num]["comment"]) $msc.=" (".$this->states[$num]["comment"].")";
            return "$num : $msc";
        } else {
            return "$num";
        }
    }
    function set_outlet_info($num,$name,$group,$idx,$comment,$dev_info="",$out_type="C") {
        $this->states[$num]["type"]=$out_type;
        $this->states[$num]["nodename"]=$name;
        $this->states[$num]["machinegroup"]=$group;
        $this->states[$num]["machineidx"]=$idx;
        $this->states[$num]["comment"]=$comment;
        $this->states[$num]["dev_info"]=$dev_info;
    }
    function create_apc_string($config,$vars,$apc_o_states,$apc_m_states,$apc_p_delays,$apc_r_delays,$log_status) {
        $user_ls=get_log_source("user");
        if ($user_ls) {
            $uls_idx=$user_ls->log_source_idx;
        } else {
            $uls_idx=0;
        }
        $var_keys=array_keys($vars);
        $sstr=array();
        if (in_array("apc_all_control",$var_keys)) {
            $act_outlet="x";
            $all_what=$vars["apc_all_control"];
            if ($all_what != "6") {
                if ($all_what > 0) {
                    $sstr[]="gc=$all_what";
                    foreach (range(1,8) as $r) {
                        $sr=strval($r);
                        if ($this->states[$sr]["type"] == "C") {
                            insert_table("devicelog","0,{$this->states[$sr]['machineidx']},$uls_idx,{$config['user_idx']},{$log_status['i']->log_status_idx},'apc command \"".mysql_escape_string($apc_m_states[$all_what])."\"',null");
                        }
                    }
                } else {
                    $sstr[]="update";
                }
            } else {
                $match_str="/^apc_{$this->idx}_([a-zA-Z])([\d]*)$/";
                foreach ($var_keys as $pv) {
                    if (preg_match($match_str,$pv,$ipp)) {
                        //echo "*** $pv *** {$vars[$pv]} ***<br>";
                        $pvv=intval(trim($vars[$pv]));
                        $type=$ipp[1];
                        $outnum=$ipp[2];
                        if ($type == "o" && $pvv) {
                            $sstr[]="c$outnum=$pvv";
                            if ($this->states[$outnum]["type"] == "C") {
                                insert_table("devicelog","0,{$this->states[$outnum]['machineidx']},$uls_idx,{$config['user_idx']},{$log_status['i']->log_status_idx},'apc command \"".mysql_escape_string($apc_o_states[$pvv])."\"',null");
                            }
                        } else if ($type == "p") {
                            if ($this->states[$outnum]["pond"] != $pvv) $sstr[]="pond$outnum=$pvv";
                        } else if ($type == "P") {
                            if ($this->states[$outnum]["poffd"] != $pvv) $sstr[]="poffd$outnum=$pvv";
                        } else if ($type == "r") {
                            if ($this->states[$outnum]["rebd"] != $pvv) $sstr[]="rebd$outnum=$pvv";
                        } else if ($type == "m") {
                            if ($this->pod != $pvv) {
                                $this->pod=$pvv;
                                $sstr[]="gpond=$pvv";
                            }
                        }
                    }
                }
            }
        }
        //echo implode(":",$sstr)."<br>";
        return implode(":",$sstr);
    }
}
function pod_add($t1,$t2) {
    if ($t1==-1 | $t2==-1) {
        return -1;
    } else {
        return $t1+$t2;
    }
}
function get_podtstr($t) {
    if ($t == -1) {
        return "never";
    } else if ($t == 0) {
        return "immediatly";
    } else {
        if ($t >= 60) {
            $m=(int)($t/60);
            $r=$t-$m*60;
            if ($r) {
                return "$m:$r";
            } else {
                return "$m min";
            }
        } else {
            return "$t sec";
        }
    }
}
function update_apc_info(&$sys_config,$do_list,&$apc_resolve_dict) {
    foreach ($do_list as $server=>$nodes) {
        if (count($nodes)) {
            $com_list=implode(":",$nodes);
            $rets=preg_split("/#/",contact_server($sys_config,"mother_server",8001,"ping $com_list",$timeout=0,$hostname=$server));
            $header=array_shift($rets);
            foreach ($nodes as $t_ip) {
                $apc=&$apc_resolve_dict[$t_ip];
                $apc->set_down();
            }
            $rescan_list=array();
            if (!preg_match("/^error.*$/",$header)) {
                foreach ($rets as $ret) {
                    if (preg_match("/^ok (\S+) .*$/",$ret,$ret_p)) {
                        $apc=&$apc_resolve_dict[$ret_p[1]];
                        $apc->set_up();
                        $rescan_list[]=$ret_p[1];
                    }
                }
                if (count($rescan_list)) {
                    $rets=preg_split("/#/",contact_server($sys_config,"mother_server",8001,"apc_com ".implode(":",$rescan_list)." refresh",$timeout=30,$hostname=$server));
                }
            }
            foreach ($nodes as $t_ip) {
                $apc=&$apc_resolve_dict[$t_ip];
                $apc->rescan();
            }
        }
    }
}
?>
