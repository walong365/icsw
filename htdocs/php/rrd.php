<?php
//
// Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
//
// Send feedback to: <lang@init.at>
// 
// This file belongs to the webfrontend package
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
//-*ics*- ,CAP,name:'ch',descr:'Cluster history',scriptname:'/php/rrd.php',left_string:'Cluster history',right_string:'Time-tracked machine parameters',defvalue:0,enabled:1,capability_group_name:'info',pri:-50
class machine {
    var $name,$dev_type,$alias,$descr,$info,$index,$mgname,$filename,$num_rrd,$device_idx,$rrd_class;
    function machine($name,$idx) {
        $this->name=$name;
        $this->dev_type="";
        $this->device_idx=$idx;
        $this->alias="";
        $this->rrd_class=0;
        $this->descr=array();
        $this->info=array();
        $this->index=array();
        $this->from_snmp=array();
        $this->mgname="UNSET";
        $this->filename="UNSET";
        $this->num_rrd=0;
    }
    function get_name() {
        if ($this->dev_type == "MD") {
            if (preg_match("/^METADEV_.*$/",$this->name)) {
                return "MetaDevice for devicegroup ".substr($this->name,8);
            } else {
                return "MetaDevice $this->name";
            }
        } else {
            return $this->name;
        }
    }
}
function leg_f_sort($v0,$v1) {
    if ($v0["val"] < $v1["val"]) {
        return -1;
    } else if ($v0["val"] > $v1["val"]) {
        return 1;
    } else {
        return 0;
    }
}
function color($col) {
    if ($col == "000000") {
        return "000001";
    } else {
        return $col;
    }
}
function shorten_info_string($is) {
    if (preg_match("/^percentage of (.*)$/",$is,$is_p)) $is="% ".$is_p[1];
    if (preg_match("/^bytes per second (.*)$/",$is,$is_p)) $is="bps ".$is_p[1];
    return $is;
}
function get_rrd_classes() {
    $all_classes=array();
    $mres=query("SELECT * FROM rrd_class rc LEFT JOIN rrd_rra ra ON ra.rrd_class=rc.rrd_class_idx ORDER BY rc.name,ra.steps,ra.rows");
    while ($mfr=mysql_fetch_object($mres)) {
        if (!in_array($mfr->rrd_class_idx,array_keys($all_classes))) {
            $all_classes[$mfr->rrd_class_idx]=$mfr;
            $all_classes[$mfr->rrd_class_idx]->struct=array();
        }
        if ($mfr->rrd_rra_idx) {
            $all_classes[$mfr->rrd_class_idx]->struct[$mfr->rrd_rra_idx]=$mfr;
        }
    }
    return $all_classes;
}
function get_size_str($sz) {
    $out_str="";
    foreach (array("T"=>1024*1024*1024*1024,
                   "G"=>1024*1024*1024,
                   "M"=>1024*1024,
                   "k"=>1024) as $sp=>$sl) {
        if ($sz > $sl) {
            $div=intval($sz/$sl);
            $sz-=$div*$sl;
            if ($out_str) $out_str.=", ";
            $out_str.="$div {$sp}Byte";
        }
    }
    $out_str.=" $sz Byte";
    return $out_str;
}
function get_time_str($secs) {
    $out_str="";
    if ($secs > 3600) {
        if ($secs > 3600*24) {
            if ($secs > 3600*24*31) {
                if ($secs > 3600*24*31*12) {
                    $years=intval($secs/(24*3600*31*12));
                    $secs-=$years*3600*24*31;
                    $out_str.=get_plural("year",$years,1).", ";
                }
                $months=intval($secs/(24*3600*31));
                $secs-=$months*3600*24*31;
                $out_str.=get_plural("month",$months,1).", ";
            }
            $days=intval($secs/(24*3600));
            $secs-=$days*3600*24;
            $out_str.=get_plural("day",$days,1)." ";
        }
        $hours=intval($secs/3600);
        $secs-=$hours*3600;
        $out_str.=sprintf("%d:",$hours);
    }
    $mins=intval($secs/60);
    $secs-=$mins*60;
    $out_str.=sprintf("%02d:%02d",$mins,$secs);
    return $out_str;
}
function get_last_update($when,$diff_time) {
    $rd_time=$diff_time;
    $outstr="";
    $abs_str=date("l, j. F Y; G:i:s",$when);
    if ($diff_time < 60) {
        $rel_str=sprintf("%d",$diff_time)." seconds";
    } else {
        if ($diff_time > 3600) {
            if ($diff_time > 3600*24) {
                $days=intval($diff_time/(24*3600));
                $diff_time-=$days*3600*24;
                $outstr=get_plural("day",$days,1)." ";
            }
            $hours=intval($diff_time/3600);
            $diff_time-=$hours*3600;
            $mins=intval($diff_time/60);
            $diff_time-=$mins*60;
            $rel_str=sprintf("%s%d:%02d:%02d",$outstr,$hours,$mins,$diff_time);
        } else {
            $mins=intval($diff_time/60);
            $diff_time-=$mins*60;
            $rel_str=sprintf("%s%d:%02d",$outstr,$mins,$diff_time);
        }
    }
    return array($abs_str,$rel_str,$rd_time);
}
class rrd_data {
    var $descr,$descr_field,$virtual,$type,$color,$db_entry,$max,$average,$min,$last,$info,$p_mach_list,$mach_list,$invalid_machs,$valid_machs,$show,$priority;
    function rrd_data($descr) {
        $this->descr=$descr;
        $this->info="";
        $this->p_mach_list=array();
        $this->mach_list=array();
        $this->invalid_machs=array();
        $this->valid_machs=0;
        $this->descr_field=preg_split("/\./",$this->descr);
        $this->virtual=0;
        $this->show=0;
        $this->events=array();
        $this->draw_type="LINE2";
        $this->color="00ff88";
        $this->db_entry=0;
        $this->maximum=0.;
        $this->average=0.;
        $this->minimum=0.;
        $this->last=0.;
        // datasource buttons (left side)
        $this->rrd_max=0;
        $this->rrd_average=0;
        $this->rrd_min=0;
        // draw min/average/maximum rulers (right side)
        $this->draw_maximum=0;
        $this->draw_average=0;
        $this->draw_minimum=0;
        $this->draw_last=0;
        $this->priority=0;
        // extra legends
        $this->legends=array();
    }
    function set_parameters($obj) {
        $this->info=$obj->info;
        $this->base=$obj->base;
        $this->factor=$obj->factor;
        $this->unit=$obj->unit;
        $this->var_type=$obj->var_type;
        $this->from_snmp=$obj->from_snmp;
    }
    function get_descr_fields() {
        $d1=$this->descr_field[0];
        list($d2,$d3,$d4)=array("","","");
        if (isset($this->descr_field[1])) {
            $d2=$this->descr_field[1];
            if (isset($this->descr_field[2])) {
                $d3=$this->descr_field[2];
                if (isset($this->descr_field[3])) {
                    $d4=$this->descr_field[3];
                }
            }
        }
        return array($d1,$d2,$d3,$d4);
    }
    function get_base() {
        return $this->base;
    }
    function get_val_str($value) {
        $pflist=array("","k","M","G","T");
        $prefix=array_shift($pflist);
        $value*=$this->factor;
        if (strval($value) == "NAN") {
            $ret_str="NaN";
        } else {
            if ($this->base != 1) {
                while (abs($value) > $this->base) {
                    $prefix=array_shift($pflist);
                    $value/=$this->base;
                }
            }
            if ($this->var_type=="f" || $prefix) {
                $ret_str=sprintf("%.2f",$value);
            } else {
                $ret_str=sprintf("%d",$value);
            }
        }
        if ($this->unit == "1") {
            $unit="";
        } else {
            $unit=$this->unit;
        }
        if ($unit == "s" && !$prefix) {
            $ret_str="";
            $value=intval($value);
            foreach (array("d"=>60*60*24,"h"=>60*60,"m"=>60) as $t_str=>$fac) {
                if ($value > $fac) {
                    $ret_str.=sprintf("%d%s ",intval($value/$fac),$t_str);
                    $value-=$fac*intval($value/$fac);
                }
            }
            $ret_str.="$value";
        }
        return "$ret_str $prefix$unit";
    }
}
function get_cluster_events() {
    $cl=array();
    $mres=query("SELECT * FROM cluster_event");
    while ($mfr=mysql_fetch_object($mres)) $cl[$mfr->cluster_event_idx]=$mfr;
    foreach ($cl as $idx=>$stuff) $cl[$idx]->legend_used=0;
    return $cl;
}
function var_compare($v1,$v2,$vv1,$vv2) {
    if (($v1 == $vv1 && $v2 == $vv2) || ($v1 == $vv2 && $v2 == $vv1)) {
        return 1;
    } else {
        return 0;
    }
}
function fit_in_list($list,$d_field) {
    $ok=1;
    if (sizeof($list)) {
        $d1n=$d_field[0];
        foreach ($list as $le=>$stuff) {
            $d1o=$stuff->descr_field[0];
            if ($d1o != $d1n) {
                $ok=0;
                break;
            }
        }
    }
    return $ok;
}
function my_encode($str) {
    return str_replace(".","_",$str);
}
function col_change($col,$fac) {
    $c_a=sscanf($col,"%02x%02x%02x");
    $n_c=array();
    foreach ($c_a as $c_v) {
        $n_c[]=max(min($c_v+$fac,255),0);
    }
    return sprintf("%02x%02x%02x",$n_c[0],$n_c[1],$n_c[2]);
}
function get_device_groups() {
    // parse device locations
    $mres=query("SELECT g.* FROM device_group g");
    $device_groups=array();
    while ($mfr=mysql_fetch_object($mres)) {
        // make a copy for clusterconfig-page
        $device_groups[$mfr->device_group_idx]=$mfr;
    }
    return $device_groups;
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["ch_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {

    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);

    htmlhead();
    $clustername=$sys_config["CLUSTERNAME"];
    $sys_config["EXPIRES"]=1;
    clusterhead($sys_config,"Cluster history page",$style="formate.css",
                array("th.dds"=>array("background-color:#eeeeff"),
                      "td.dds"=>array("background-color:#ccccff","text-align:center"),
                      "th.group"=>array("background-color:#eeffee"),
                      "th.maximum"=>array("background-color:#eeffee"),
                      "td.maximum"=>array("background-color:#ccffcc","text-align:center"),
                      "th.average"=>array("background-color:#e2f2e2"),
                      "td.average"=>array("background-color:#c1f2c1","text-align:center"),
                      "td.steps"=>array("background-color:#ccffcc","text-align:left"),
                      "td.rows"=>array("background-color:#c1f2c1","text-align:left"),
                      "td.cf"=>array("background-color:#e0e0b0","text-align:left"),
                      "th.minimum"=>array("background-color:#d4e4d4"),
                      "td.minimum"=>array("background-color:#b0e0b0","text-align:center"),
                      "th.pri"=>array("background-color:#e4e4d4"),
                      "td.pri"=>array("background-color:#e0e0b0","text-align:center"),
                      "th.last"=>array("background-color:#f2e2e2"),
                      "td.last"=>array("background-color:#f2c1c1","text-align:center"),
                      "td.rrdinfo"=>array("background-color:#f2c1c1","text-align:right"),
                      "th.ndev"=>array("background-color:#f2f9f9"),
                      "td.ndev"=>array("background-color:#f2f1f1","text-align:center"),
                      "th.reld"=>array("background-color:#f2f9f9","text-align:right"),
                      "td.relmdrok"=>array("background-color:#c2f1f1","text-align:right"),
                      "td.relmdcok"=>array("background-color:#c2f1f1","text-align:center","width:1%"),
                      "td.relmdlok"=>array("background-color:#c2f1f1","text-align:left","width:1%"),
                      "td.reldrok"=>array("background-color:#c2f1c1","text-align:right"),
                      "td.reldcok"=>array("background-color:#c2f1c1","text-align:center","width:1%"),
                      "td.reldlok"=>array("background-color:#c2f1c1","text-align:left",),
                      "td.reldrwarn"=>array("background-color:#ffff44","text-align:right"),
                      "td.reldcwarn"=>array("background-color:#ffff44","text-align:center"),
                      "td.reldlwarn"=>array("background-color:#ffff44","text-align:left"),
                      "td.reldrerror"=>array("background-color:#ff8888","text-align:right"),
                      "td.reldcerror"=>array("background-color:#ff8888","text-align:center"),
                      "td.reldlerror"=>array("background-color:#ff8888","text-align:left"),
                      "th.del"=>array("background-color:#f2e1e1"),
                      "td.del"=>array("background-color:#f2b1b1","text-align:center"),
                      "th.dellog"=>array("background-color:#dee0e0"),
                      "td.dellog"=>array("background-color:#e2fbfb","text-align:center"),
                      "th.delse"=>array("background-color:#eeeeff"),
                      "td.delse"=>array("background-color:#ddddee","text-align:center"),
                      "th.type"=>array("background-color:#ddddff"),
                      "td.type"=>array("background-color:#bbbbdd","text-align:center"),
                      "th.color"=>array("background-color:#ddffff"),
                      "td.color"=>array("background-color:#bbdddd","text-align:center"),
                      "th.class"=>array("background-color:#eeeeee"),
                      "td.class"=>array("background-color:#dddddd","text-align:center"),
                      "th.threshold"=>array("background-color:#e6e6e6"),
                      "td.threshold"=>array("background-color:#d6d6d6","text-align:center"),
                      "th.hysteresis"=>array("background-color:#dddddd"),
                      "td.hysteresis"=>array("background-color:#cccccc","text-align:center"),
                      "th.action"=>array("background-color:#ffe6e6"),
                      "td.action"=>array("background-color:#eed6d6","text-align:center"),
                      "th.classes"=>array("background-color:#eedddd"),
                      "td.classes"=>array("background-color:#ddcccc","text-align:center"),
                      "th.location"=>array("background-color:#e6ffe6"),
                      "td.location"=>array("background-color:#d6eed6","text-align:center"),
                      "th.mail"=>array("background-color:#ddeedd"),
                      "td.mail"=>array("background-color:#ccddcc","text-align:center"),
                      "td.hostlist"=>array("background-color:#ddd0d0","text-align:left"),
                      "input.deverror"=>array("background-color:#ff8888","font-size:normal"),
                      "input.devwarn"=>array("background-color:#ffff44","font-size:normal"),
                      "input.devok"=>array("background-color:#88ff88","font-size:normal"),
                      "x"=>array()
                      )
                );
    clusterbody($sys_config,"Cluster history",array("bc","sc"),array("info"));

    $ucl=usercaps($sys_db_con);
    if ($ucl["ch"]) {
    
        $allm_name="Overview";
        $crrd_name="Configure RRD-Classes";
        $priority_list=range(10,-10);
        // define some static values
        // list of colors
        $colors=array("black"=>"000000","gray"=>"808080","maroon"=>"800000","red"=>"FF0000",
                      "green"=>"008000","lime"=>"00FF00","olive"=>"808000","yellow"=>"FFFF00",
                      "navy"=>"000080","blue"=>"0000FF","purple"=>"800080","fuchsia"=>"FF00FF",
                      "teal"=>"008080","aqua"=>"00FFFF","silver"=>"C0C0C0","white"=>"FFFFFF");
        ksort($colors);
        // description-array
        $descr_f=array("blks"=>"Block I/O","df"=>"Disk info","fan"=>"Fan","load"=>"Load info","mem"=>"Memory",
                       "temp"=>"Temperature","vms"=>"System info","net"=>"Network info","num"=>"Context/Interrupts",
                       "aflw"=>"Airflow","humi"=>"Humidity","swap"=>"Swapping");
        // possible endtimes
        $endtimes=array(0 =>array("name"=>"now"     ,"timelen"=>0            ),
                        1 =>array("name"=>"1 hour"  ,"timelen"=>60*60        ),
                        2 =>array("name"=>"2 hours" ,"timelen"=>2*60*60      ),
                        3 =>array("name"=>"3 hours" ,"timelen"=>3*60*60      ),
                        4 =>array("name"=>"4 hours" ,"timelen"=>4*60*60      ),
                        5 =>array("name"=>"6 hours" ,"timelen"=>6*60*60      ),
                        6 =>array("name"=>"12 hours","timelen"=>12*60*60     ),
                        7 =>array("name"=>"1 day"   ,"timelen"=>24*60*60     ),
                        8 =>array("name"=>"2 days"  ,"timelen"=>2*24*60*60   ),
                        9 =>array("name"=>"1 week"  ,"timelen"=>7*24*60*60   ),
                        10=>array("name"=>"2 weeks" ,"timelen"=>2*7*24*60*60 ),
                        11=>array("name"=>"1 month" ,"timelen"=>31*24*60*60  ),
                        12=>array("name"=>"2 months","timelen"=>31*2*24*60*60));
        // possible timeframes
        $timeframes=array(0=>array("name"=>"1 hour"  ,"timelen"=>60*60        ,"slice"=>60*15     ),
                          1=>array("name"=>"2 hours" ,"timelen"=>2*60*60      ,"slice"=>60*60     ),
                          2=>array("name"=>"6 hours" ,"timelen"=>6*60*60      ,"slice"=>60*60     ),
                          3=>array("name"=>"12 hours","timelen"=>12*60*60     ,"slice"=>60*60*2   ),
                          4=>array("name"=>"1 day"   ,"timelen"=>24*60*60     ,"slice"=>60*60*12  ),
                          5=>array("name"=>"2 days"  ,"timelen"=>2*24*60*60   ,"slice"=>60*60*24  ),
                          6=>array("name"=>"1 week"  ,"timelen"=>7*24*60*60   ,"slice"=>60*60*24  ),
                          7=>array("name"=>"2 weeks" ,"timelen"=>2*7*24*60*60 ,"slice"=>60*60*24*7),
                          8=>array("name"=>"1 month" ,"timelen"=>31*24*60*60  ,"slice"=>60*60*24*7),
                          9=>array("name"=>"2 months","timelen"=>31*2*24*60*60,"slice"=>60*60*24*7));
        // possible x-sizes
        $x_sizes=array(0=>array("name"=>"small" ,"x"=>320 ),
                       1=>array("name"=>"medium","x"=>640 ),
                       2=>array("name"=>"wide"  ,"x"=>800 ),
                       3=>array("name"=>"big"   ,"x"=>1024),
                       4=>array("name"=>"x-wide","x"=>1400));
        // possible y_sizes
        $y_sizes=array(0=>array("name"=>"small" ,"y"=>200 ),
                       1=>array("name"=>"medium","y"=>400 ),
                       2=>array("name"=>"wide"  ,"y"=>600 ),
                       3=>array("name"=>"big"   ,"y"=>768 ),
                       4=>array("name"=>"x-wide","y"=>1000));
        // possible compositions for total values
        $compose_opts=array(0=>array("name"=>"Add" ,"op"=>"+"  ),
                            1=>array("name"=>"Max" ,"op"=>"MAX"),
                            2=>array("name"=>"Min" ,"op"=>"MIN"),
                            3=>array("name"=>"Mean","op"=>"+"  ));
        // hidden list of machines (or $allm_name)
        $hiddenmach="";
        // hidden show_total flag
        $hiddentot="";
        // hidden list of machines for totals
        $hidden_tot_mach="";
        $hiddenrrd="";
        // hidden graph parameters
        $hiddengp="";
        // hidden y-start/end parameters
        $hiddenyas="";
        $act_timeframe_idx=0;
        $act_endtime_idx=0;
        $act_x_size_idx=0;
        $act_y_size_idx=0;
        $act_compose_idx=0;
        // 0 ... normal (no total showing)
        // 1 ... show total overview
        $show_total=0;
        $actmach=array();
        $actrrd_dec=array();
        $delrrd_dec=array();
        $rrd_list=array();
        // different rrd diagrams
        $rrd_diagrams=array();
        $var_keys=array_keys($vars);
        $y_start=0.;
        $y_end=0.;
        // del_flag
        $del_something=0;
        //print_r($vars);
        if (sizeof($vars)) {
            foreach (array("yzero","rigid","altscale","yzrule","altygrid","reltoaverage","drawtmarks","dboots","dccevents","noxgrid","noygrid","noyas","meanvalue","ignorenan","cccevents","cdrawing") as $hgpp) {
                if (in_array($hgpp,$var_keys)) $hiddengp.="<input type=hidden name=\"$hgpp\" value=1 />\n";
            }
            if (in_array("ystart",$var_keys)) {
                $y_start=(double)$vars["ystart"];
            }
            if (in_array("yend",$var_keys)) {
                $y_end=(double)$vars["yend"];
            }
            if ($y_start > $y_end) {
                $y_sw=$y_end;
                $y_end=$y_start;
                $y_start=$y_sw;
            }
            $hiddenyas.="<input type=hidden name=\"ystart\" value=\"$y_start\" />\n";
            $hiddenyas.="<input type=hidden name=\"yend\" value=\"$y_end\" />\n";
            if (in_array("endtimeidx",$var_keys)) {
                $act_endtime_idx=intval($vars["endtimeidx"]);
            }
            if (in_array("timeframeidx",$var_keys)) {
                $act_timeframe_idx=intval($vars["timeframeidx"]);
            }
            if (in_array("x_sizeidx",$var_keys)) {
                $act_x_size_idx=intval($vars["x_sizeidx"]);
            }
            if (in_array("y_sizeidx",$var_keys)) {
                $act_y_size_idx=intval($vars["y_sizeidx"]);
            }
            if (in_array("composeidx",$var_keys)) {
                $act_compose_idx=intval($vars["composeidx"]);
            }
            // showtotal is set if a summary report is requested
            // actmach is subset of {"Overview","Config RRD-classes",[all_machines]}
            // totmach is only set if actmach is "Overview" (summary report)
            if (in_array("showtotal",$var_keys)) {
                $show_total=$vars["showtotal"];
                $actmach=array($allm_name);
                if (in_array("tot_mach",$var_keys)) {
                    $tot_mach=$vars["tot_mach"];
                    foreach ($tot_mach as $mach) $hidden_tot_mach.="<input type=hidden name=\"tot_mach[]\" value=\"$mach\" />\n";
                } else {
                    unset($tot_mach);
                }
            } else {
                if (in_array("selmach",$var_keys)) {
                    $actmach=array_unique($vars["selmach"]);
                } else {
                    $actmach=array($allm_name);
                }
            }
            foreach ($actmach as $mach) $hiddenmach.="<input type=hidden name=\"selmach[]\" value=\"$mach\" />\n";
            // show something, zero means start page
            $show_sthg="ov";
            if (sizeof($actmach)) {
                // "seq" means plots of a given subset of all rrd_datas for the selected machines
                if ($actmach[0] == $allm_name) {
                    $show_sthg="ov";
                } else if ($actmach[0] == $crrd_name) {
                    $show_sthg="conf";
                } else {
                    $show_sthg="seq";
                }
                // "tot" means one plot where a given subset of all rrd_datas for the selected machines are shown
                if ($show_total == 1) $show_sthg="tot";
            }
            if (in_array("selrrd",$var_keys)) {
                $actrrd=array_unique($vars["selrrd"]);
                // actrrd is now the list of all selected data-sources
                $col_idx=0;
                reset($colors);
                $hiddenrrd="";
                foreach ($actrrd as $rrd) {
                    if (!in_array(my_encode("{$rrd}.rem"),$var_keys)) {
                        $urldec=urldecode($rrd);
                        //echo $rrd," ",$urldec,"<br>";
                        $d_field=preg_split("/\./",$urldec);
                        if (!in_array($d_field[0],array_keys($rrd_diagrams))) $rrd_diagrams[$d_field[0]]=array();
                        $new_rrd=new rrd_data($urldec);
                        $list_ok=each($colors);
                        if ($list_ok) {
                            list($key,$val)=$list_ok;
                        } else {
                            reset($colors);
                            list($key,$val)=each($colors);
                        }
                        $new_rrd->color=$val;
                        $actrrd_dec[]=$urldec;
                        // anything to delete?
                        if (in_array(my_encode("{$urldec}.del"),$var_keys)) $del_something=1;
                        $hiddenrrd.="<input type=hidden name=\"selrrd[]\" value=\"$rrd\" />\n";
                        $rrd_list[$urldec]=$new_rrd;
                        $rrd_diagrams[$d_field[0]][$urldec]=$new_rrd;
                        unset($new_rrd);
                    }
                }
            }
            if (in_array("delrrd",$var_keys)) {
                foreach ($vars["delrrd"] as $rrd) {
                    $delrrd_dec[]=urldecode($rrd);
                }
            }
        }
        $hiddentime="<input type=hidden name=\"timeframeidx\" value=\"$act_timeframe_idx\" /><input type=hidden name=\"endtimeidx\" value=\"$act_endtime_idx\" />\n";
        $hiddensize="<input type=hidden name=\"x_sizeidx\" value=\"$act_x_size_idx\" /><input type=hidden name=\"y_sizeidx\" value=\"$act_y_size_idx)\" />\n";
        $hiddencompose="<input type=hidden name=\"composeidx\" value=\"$act_compose_idx\" />\n";
        $hiddentot="<input type=hidden name=\"showtotal\" value=\"$show_total\" />\n";
    
        $machine_list=array();
        $disp_array=array();
        $disp_type=array();
        $num_disp=0;
        $mres=query("SELECT d.name, d.rrd_class,d.alias, dg.name as mgname, d.comment,d.device_idx as idx,dt.identifier, rs.filename, COUNT(rd.info) AS rdcount FROM device d INNER JOIN device_group dg INNER JOIN device_type dt LEFT JOIN rrd_set rs ON rs.device=d.device_IDX LEFT JOIN rrd_data rd ON rd.rrd_set=rs.rrd_set_idx WHERE d.device_type=dt.device_type_idx AND (dt.identifier='H' OR dt.identifier='NB' OR dt.identifier='AM' OR dt.identifier='MD') AND d.device_group=dg.device_group_idx GROUP BY mgname,d.name");
        while($mfr=mysql_fetch_object($mres)) {
            // just a check
            $newmach=new machine($mfr->name,$mfr->idx);
            $newmach->dev_type=$mfr->identifier;
            $newmach->mgname=$mfr->mgname;
            $newmach->comment=$mfr->comment;
            $newmach->rrd_class=$mfr->rrd_class;
            $newmach->alias=$mfr->alias;
            $newmach->filename=$mfr->filename;
            if (!in_array($mfr->mgname,array_keys($disp_array))) {
                $disp_array[$mfr->mgname]=array();
                $disp_type[$mfr->mgname]="D";
                $num_disp++;
            }
            $disp_array[$mfr->mgname][]=$mfr->name;
            $newmach->num_rrd=$mfr->rdcount;
            $machine_list[$newmach->name]=$newmach;
            $num_disp++;
            unset($newmach);
        }
        if (sizeof(array_keys($machine_list))) {
            message ("Please select a device and some datasets:");
            $disp_array[$allm_name]=$allm_name;
            $disp_array[$crrd_name]=$crrd_name;
            $disp_type[$allm_name]="S";
            $disp_type[$crrd_name]="S";
            $num_disp+=3;
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\"><tr>";
            echo "<td class=\"top\"><form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
            echo "<select name=\"selmach[]\" size=".strval(min($num_disp,8)).">\n";
            foreach (array("S","T","D") as $dtype) {
                foreach (array_keys($disp_array) as $gname) {
                    if ($disp_type[$gname] == $dtype) {
                        if (in_array($dtype,array("S","T"))) {
                            echo "<option value=\"$gname\"";
                            if (in_array($gname,$actmach)) echo " selected";
                            echo ">$gname</option>";
                        } else {
                            $num_mach=count($disp_array[$gname]);
                            echo "<option disabled>--- $gname [ ".get_plural("device",$num_mach,1)." ] ------</option>\n";
                            foreach (array("MD","x") as $dst) {
                                foreach ($disp_array[$gname] as $key=>$mname) {
                                    $mach=&$machine_list[$mname];
                                    if ($mach->dev_type == $dst || ($dst == "x" && $mach->dev_type != "MD")) {
                                        echo "<option value=\"$mach->name\" ".(in_array($mach->name,$actmach) ? "selected" : "" ).">".($dst=="MD" ? " - MetaDevice" : $mach->name);
                                        $com_field=array();
                                        if ($mach->alias) $com_field[]=$mach->alias;
                                        if ($mach->comment) $com_field[]=$mach->comment;
                                        if (count($com_field)) echo " (".implode(", ",$com_field).")";
                                        echo " : $mach->num_rrd parameters</option>\n";
                                    }
                                }
                            }
                        }
                    }
                }
            }
            echo "</select><br>";
            hidden_sid();
            echo $hiddenrrd;
            echo $hiddentime;
            echo $hiddensize;
            echo $hiddencompose;
            echo $hiddengp;
            echo $hiddenyas;
            echo "<input type=submit value=\"select\" />";
            echo "</form></td>";
            if (count($actrrd_dec)) {
                $sql_q_array=array();
                foreach ($actrrd_dec as $descr) $sql_q_array[]="TRIM('.' FROM CONCAT_WS('.',rud.descr1,rud.descr2,rud.descr3,rud.descr4))='$descr'";
                $mr=query("SELECT rud.*,TRIM('.' FROM CONCAT_WS('.',rud.descr1,rud.descr2,rud.descr3,rud.descr4)) AS descr FROM rrd_user_data rud WHERE rud.user={$sys_config['user_idx']} AND (".implode(" OR ",$sql_q_array).")");
                while ($mres=mysql_fetch_object($mr)) {
                    $act_rrd=&$rrd_list[$mres->descr];
                    $act_rrd->db_entry=1;
                    foreach (array("draw_type","color","priority","draw_maximum","draw_average","draw_minimum","draw_last","rrd_min","rrd_average","rrd_max") as $v_name) $act_rrd->$v_name=$mres->$v_name;
                    if (!$act_rrd->color) {
                        $list_ok=each($colors);
                        if ($list_ok) {
                            list($key,$val)=$list_ok;
                        } else {
                            reset($colors);
                            list($key,$val)=each($colors);
                        }
                        $act_rrd->color=$val;
                    }
                }
            }
            //print_r($actmach);
            $log_stack=new messagelog();
            if (in_array($show_sthg,array("tot","seq"))) {
                if ($show_sthg == "tot") {
                    // Total view mode
                    $sel_f=array();
                    foreach ($actrrd_dec as $act_st) $sel_f[]=" (TRIM('.' FROM CONCAT_WS('.',rd.descr1,rd.descr2,rd.descr3,rd.descr4))='$act_st')";
                    $mach_list=array();
                    $mr2=query("SELECT rd.info,rd.rrd_index,rs.device,d.name,rd.base,rd.from_snmp,rd.factor,rd.unit,rd.var_type,dg.name as dgname,TRIM('.' FROM CONCAT_WS('.',rd.descr1,rd.descr2,rd.descr3,rd.descr4)) AS descr,rs.filename FROM rrd_data rd, rrd_set rs, device d, device_group dg, device_type dt WHERE dt.device_type_idx=d.device_type AND rd.rrd_set=rs.rrd_set_idx AND rs.device=d.device_idx AND d.device_group=dg.device_group_idx AND (".implode("OR",$sel_f).") ORDER BY dgname, d.name,rd.descr1,rd.descr2,rd.descr3,rd.descr4");
                    $mg_list=array();
                    while ($mfr2=mysql_fetch_object($mr2)) {
                        $mname=$mfr2->name;
                        $dgname=$mfr2->dgname;
                        if (in_array($dgname,array_keys($mg_list))) {
                            if (!in_array($mname,$mg_list[$dgname])) $mg_list[$dgname][]=$mname;
                        } else {
                            $mg_list[$dgname]=array($mname);
                        }
                        if (!in_array($mname,array_keys($mach_list))) $mach_list[$mname]=array();
                        $rrd_n=$mfr2->descr;
                        //$rrd_list[$rrd_n]->info=$mfr2->info;
                        $rrd_list[$rrd_n]->set_parameters($mfr2);
                        $rrd_list[$rrd_n]->p_mach_list[$mname]=array($mfr2->rrd_index,$mfr2->filename);
                        $mach_list[$mname][]=$rrd_n;
                    }
                    // if tot_mach is not set, set it to all valid machines
                    echo "<td class=\"top\"><table class=\"simplesmall\"><tr>\n";
                    if (!isset($tot_mach)) $tot_mach=array_keys($mach_list);
                    echo "<td class=\"top\"><form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
                    echo $hiddentot;
                    echo $hiddenrrd;
                    echo "<select name=\"tot_mach[]\" size=".strval(min(count($mg_list)+count($mach_list),8))." multiple>";
                    foreach($mg_list as $dgname=>$mlist) {
                        $num_mach=count($mlist);
                        echo "<option disabled>--- $dgname [ $num_mach ] ---</option>\n";
                        foreach (array("MD","x") as $dst) {
                            foreach ($mlist as $mname) {
                                $mach=&$machine_list[$mname];
                                if ($mach->dev_type == $dst || ($dst == "x" && $mach->dev_type != "MD")) {
                                    echo "<option value=\"$mname\" ";
                                    $com_field=array();
                                    if ($mach->alias) $com_field[]=$mach->alias;
                                    if ($mach->comment) $com_field[]=$mach->comment;
                                    if (in_array($mname,$tot_mach)) {
                                        echo " selected ";
                                        foreach ($mach_list[$mname] as $act_st) {
                                            $rrd_list[$act_st]->show=1;
                                            $rrd_list[$act_st]->mach_list[$mname]=&$rrd_list[$act_st]->p_mach_list[$mname];
                                        }
                                    }
                                    echo ">".($dst=="MD" ? " - MetaDevice" : $mname).sprintf(" (%d of %d)",count($mach_list[$mname]),count($actrrd_dec));
                                    if (count($com_field)) echo " (".implode(", ",$com_field).")";
                                    echo "</option>";
                                }
                            }
                        }
                    }
                    echo "</select>";
                    echo "</td>\n";
                    unset($mach);
                } else {
                    // Sequential View mode
                    $mach=&$machine_list[$actmach[0]];
                    // read event-info if necessary
                    $mr2=query("SELECT rd.info,rd.base,rd.factor,rd.unit,rd.from_snmp,rd.var_type,rd.descr1,TRIM('.' FROM CONCAT_WS('.',rd.descr1,rd.descr2,rd.descr3,rd.descr4)) AS descr,rd.rrd_index FROM rrd_data rd, rrd_set rs WHERE rd.rrd_set=rs.rrd_set_idx AND rs.device=$mach->device_idx ORDER BY rd.descr1,rd.descr2,rd.descr3,rd.descr4");
                    $dlist=array();
                    if (mysql_num_rows($mr2)) {
                        $type_list=array();
                        while ($mfr2=mysql_fetch_object($mr2)) {
                            $type_list[]=$mfr2->descr1;
                            $descr_list=array($mfr2->descr=>$mfr2->rrd_index);
                            foreach ($descr_list as $descr=>$rrd_index) {
                                //echo $descr,",";
                                $dlist[]=$descr;
                                $mach->info[$descr]=$mfr2->info;//set
                                $mach->index[$descr]=$rrd_index;
                                $mach->from_snmp[$descr]=$mfr2->from_snmp;
                                if (in_array($descr,$actrrd_dec)) $rrd_list[$descr]->set_parameters($mfr2);
                            }
                        }
                        $num_types=count(array_unique($type_list));
                        //print_r(array_keys($mach->info));
                        //echo "<br>";
                        ksort($mach->info);
                    }
                    // deselect descriptions not present in the actual machine
                    //print_r($actrrd_dec);
                    foreach ($actrrd_dec as $descr) {
                        if (!in_array($descr,$dlist)) {
                            echo $descr;
                            unset($actrrd_dec[array_search($descr,$actrrd_dec,FALSE)],$rrd_list[$descr]);
                        }
                    }
                    if (in_array("cccevents",$var_keys) || in_array("dccevents",$var_keys)) {
                        $all_threshold_classes=array(1=>"ascending",-1=>"descending");
                        $all_device_classes=get_device_classes();
                        $all_device_locations=get_device_locations();
                        $all_device_groups=get_device_groups();
                        $all_cluster_events=get_cluster_events();

                        if (count($actrrd_dec)) {
                            $sel_f=array();
                            foreach ($actrrd_dec as $descr) $sel_f[]="TRIM('.' FROM CONCAT_WS('.',rd.descr1,rd.descr2,rd.descr3,rd.descr4))='$descr'";
                            $mres=query("SELECT rd.*,TRIM('.' FROM CONCAT_WS('.',rd.descr1,rd.descr2,rd.descr3,rd.descr4)) AS descr,ccl.*,cu.user,cc.device_location,cc.ccl_dloc_con_idx,cg.device_group,cg.ccl_dgroup_con_idx FROM rrd_data rd INNER JOIN rrd_set rs LEFT JOIN ccl_event ccl ON ccl.rrd_data=rd.rrd_data_idx LEFT JOIN ccl_user_con cu ON cu.ccl_event=ccl.ccl_event_idx LEFT JOIN ccl_dloc_con cc ON cc.ccl_event=ccl.ccl_event_idx LEFT JOIN ccl_dgroup_con cg ON cg.ccl_event=ccl.ccl_event_idx WHERE rd.rrd_set=rs.rrd_set_idx AND rs.device=$mach->device_idx AND (".implode(" OR ",$sel_f).")");
                            //print_r($sel_f);
                            while ($mfr=mysql_fetch_object($mres)) {
                                $act_rrd=&$rrd_list[$mfr->descr];
                                $act_rrd->rrd_data_idx=$mfr->rrd_data_idx;
                                if ($mfr->ccl_event_idx) {
                                    if (!in_array($mfr->ccl_event_idx,array_keys($act_rrd->events))) {
                                        $mfr->mail_users=array();
                                        $mfr->device_locations=array();
                                        $mfr->device_groups=array();
                                        $act_rrd->events[$mfr->ccl_event_idx]=$mfr;
                                    }
                                    if ($mfr->user) {
                                        if (!in_array($mfr->user,array_values($act_rrd->events[$mfr->ccl_event_idx]->mail_users))) $act_rrd->events[$mfr->ccl_event_idx]->mail_users[]=$mfr->user;
                                    }
                                    if ($mfr->device_location) {
                                        if (!in_array($mfr->ccl_dloc_con_idx,array_keys($act_rrd->events[$mfr->ccl_event_idx]->device_locations))) $act_rrd->events[$mfr->ccl_event_idx]->device_locations[]=$mfr->device_location;
                                    }
                                    if ($mfr->device_group) {
                                        if (!in_array($mfr->ccl_dgroup_con_idx,array_keys($act_rrd->events[$mfr->ccl_event_idx]->device_groups))) $act_rrd->events[$mfr->ccl_event_idx]->device_groups[]=$mfr->device_group;
                                    }
                                }
                                unset($act_rrd);
                            }
                        }
                        // get user-list
                        $mres=query("SELECT u.login,u.useremail,u.user_idx,count(*) AS mailcount, cu.user FROM user u LEFT JOIN ccl_user_con cu ON cu.user=u.user_idx WHERE u.useremail != '' GROUP BY u.user_idx ORDER BY mailcount DESC");
                        $mail_users=array();
                        while ($mfr=mysql_fetch_object($mres)) {
                            if (!$mfr->user) $mfr->mailcount=0;
                            $mail_users[$mfr->user_idx]=$mfr;
                        }
                        $machmod_list=array();
                        foreach ($rrd_list as $descr=>$act_rrd) {
                            $idx=$act_rrd->rrd_data_idx;
                            foreach ($act_rrd->events as $ev_idx => $ev_stuff) {
                                $eidx="{$idx}_{$ev_idx}";
                                if (is_set("ncc_del_$eidx",&$vars)) {
                                    $log_stack->add_message("Deleted cc_event for {$act_rrd->info}","ok",1);
                                    foreach ($rrd_list[$descr]->events[$ev_idx]->mail_users as $mail_user) $mail_users[$mail_user]->mailcount--;
                                    query("DELETE FROM ccl_dgroup_con WHERE ccl_event=$ev_idx");
                                    query("DELETE FROM ccl_dloc_con WHERE ccl_event=$ev_idx");
                                    query("DELETE FROM ccl_user_con WHERE ccl_event=$ev_idx");
                                    query("DELETE FROM ccl_event WHERE ccl_event_idx=$ev_idx");
                                    unset($rrd_list[$descr]->events[$ev_idx]);
                                    if (!in_array($mach->name,$machmod_list)) $machmod_list[]=$mach->name;
                                } else if (is_set("ncc_set_$eidx",&$vars)) {
                                    $change_f=array();
                                    $threshold=trim($vars["ncc_th_$eidx"]);
                                    if ($threshold == strval(floatval($threshold)) && $threshold != $ev_stuff->threshold) {
                                        $change_f[]="threshold=$threshold";
                                        $rrd_list[$descr]->events[$ev_idx]->threshold=$threshold;
                                    }
                                    $hysteresis=trim($vars["ncc_hys_$eidx"]);
                                    if ($hysteresis == strval(floatval($hysteresis)) && $hysteresis != $ev_stuff->hysteresis) {
                                        $hysteresis=abs($hysteresis);
                                        $change_f[]="hysteresis=$hysteresis";
                                        $rrd_list[$descr]->events[$ev_idx]->hysteresis=$hysteresis;
                                    }
                                    foreach (array(array("thc","threshold_class"),
                                                   array("ce","cluster_event"),
                                                   array("dc","device_class")) as $stuff) {
                                        list($s_varn,$l_varn)=$stuff;
                                        $var=$vars["ncc_{$s_varn}_$eidx"];
                                        if ($var != $ev_stuff->$l_varn) {
                                            $change_f[]="{$l_varn}=$var";
                                            $rrd_list[$descr]->events[$ev_idx]->$l_varn=$var;
                                        }
                                    }
                                    // check device-location correlation
                                    if (is_set("ncc_dg_$eidx",&$vars)) {
                                        $new_list=$vars["ncc_dg_$eidx"];
                                    } else {
                                        $new_list=array();
                                    }
                                    $old_list=$ev_stuff->device_groups;
                                    foreach ($old_list as $old_v) {
                                        if (!in_array($old_v,$new_list)) query("DELETE FROM ccl_dgroup_con WHERE ccl_event=$ev_idx AND device_group=$old_v");
                                    }
                                    foreach ($new_list as $new_v) {
                                        if (!in_array($new_v,$old_list)) insert_table("ccl_dgroup_con","0,$ev_idx,$new_v,null");
                                    }
                                    $rrd_list[$descr]->events[$ev_idx]->device_groups=$new_list;
                                    // check device-device_group correlation
                                    if (is_set("ncc_dl_$eidx",&$vars)) {
                                        $new_list=$vars["ncc_dl_$eidx"];
                                    } else {
                                        $new_list=array();
                                    }
                                    $old_list=$ev_stuff->device_locations;
                                    foreach ($old_list as $old_v) {
                                        if (!in_array($old_v,$new_list)) query("DELETE FROM ccl_dloc_con WHERE ccl_event=$ev_idx AND device_location=$old_v");
                                    }
                                    foreach ($new_list as $new_v) {
                                        if (!in_array($new_v,$old_list)) insert_table("ccl_dloc_con","0,$ev_idx,$new_v,null");
                                    }
                                    $rrd_list[$descr]->events[$ev_idx]->device_locations=$new_list;
                                    // check mailuser-settings
                                    if (is_set("ncc_mail_$eidx",&$vars)) {
                                        $new_list=$vars["ncc_mail_$eidx"];
                                    } else {
                                        $new_list=array();
                                    }
                                    $old_list=$ev_stuff->mail_users;
                                    foreach ($old_list as $old_v) {
                                        if (!in_array($old_v,$new_list)) query("DELETE FROM ccl_user_con WHERE ccl_event=$ev_idx AND user=$old_v");
                                    }
                                    foreach ($new_list as $new_v) {
                                        if (!in_array($new_v,$old_list)) insert_table("ccl_user_con","0,$ev_idx,$new_v,null");
                                    }
                                    $rrd_list[$descr]->events[$ev_idx]->mail_users=$new_list;
                                    if (count($change_f)) {
                                        query("UPDATE ccl_event SET ".implode(",",$change_f)." WHERE ccl_event_idx=$ev_idx");
                                        if (!in_array($mach->name,$machmod_list)) $machmod_list[]=$mach->name;
                                    }
                                }
                            }
                            if (is_set("ncc_new_$idx",&$vars)) {
                                $threshold=trim($vars["ncc_th_$idx"]);
                                $hysteresis=trim($vars["ncc_hys_$idx"]);
                                if ($threshold != strval(floatval($threshold))) {
                                    $log_stack->add_message("Cannot add cc_event to {$act_rrd->info}","parse error for threshold",0);
                                    unset($threshold);
                                }
                                if ($hysteresis != strval(floatval($hysteresis))) {
                                    $log_stack->add_message("Cannot add cc_event to {$act_rrd->info}","parse error for hysteresis",0);
                                    unset($hysteresis);
                                }
                                if (isset($threshold) && isset($hysteresis)) {
                                    $th_class=$vars["ncc_thc_$idx"];
                                    $cc_event=$vars["ncc_ce_$idx"];
                                    $dclass=$vars["ncc_dc_$idx"];
                                    $ins_idx=insert_table("ccl_event","0,$mach->device_idx,$idx,$dclass,$threshold,$th_class,$cc_event,$hysteresis,0,null");
                                    if ($ins_idx) {
                                        $log_stack->add_message("Added cc_event to {$act_rrd->info} (threshold $threshold)","OK",1);
                                        $mres=query("SELECT ccl.* FROM ccl_event ccl WHERE ccl.ccl_event_idx=$ins_idx");
                                        $mfr=mysql_fetch_object($mres);
                                        $rrd_list[$descr]->events[$mfr->ccl_event_idx]=$mfr;
                                        if (is_set("ncc_mail_$idx",&$vars)) {
                                            $new_mail_users=$vars["ncc_mail_$idx"];
                                        } else {
                                            $new_mail_users=array();
                                        }
                                        foreach ($new_mail_users as $mail_user) {
                                            $ui_idx=insert_table("ccl_user_con","0,$ins_idx,$mail_user,null");
                                            $mail_users[$mail_user]->mailcount++;
                                        }
                                        $rrd_list[$descr]->events[$mfr->ccl_event_idx]->mail_users=$new_mail_users;
                                        $rrd_list[$descr]->events[$mfr->ccl_event_idx]->device_locations=array();
                                        foreach ($vars["ncc_dl_$idx"] as $device_loc) {
                                            $di_idx=insert_table("ccl_dloc_con","0,$ins_idx,$device_loc,null");
                                            $rrd_list[$descr]->events[$mfr->ccl_event_idx]->device_locations[]=$device_loc;
                                        }
                                        foreach ($vars["ncc_dg_$idx"] as $device_grp) {
                                            $di_idx=insert_table("ccl_dgroup_con","0,$ins_idx,$device_grp,null");
                                            $rrd_list[$descr]->events[$mfr->ccl_event_idx]->device_groups[]=$device_grp;
                                        }
                                        if (!in_array($mach->name,$machmod_list)) $machmod_list[]=$mach->name;
                                    } else {
                                        $log_stack->add_message("Cannot add cc_event to {$act_rrd->info}","SQL error",0);
                                    }
                                }
                            }
                        }
                        if (count($machmod_list)) {
                            $rets=contact_server($sys_config,"rrd_server",8003,"-c refresh ".implode(":",$machmod_list));
                            $log_stack->add_message("Refreshed devices ","ok",1);
                        }
                    }
                    if (!$del_something) {
                        echo "<td class=\"top\"><table class=\"simplesmall\"><tr>\n";
                        echo "<td class=\"top\" rowspan=\"2\"><form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
                        if ($mach->info) {
                            echo "<select name=\"selrrd[]\" size=".strval(min($num_types+count($mach->info),8))." multiple>";
                            $mach=&$machine_list[$actmach[0]];
                            $act_descr="";
                            foreach (array_keys($mach->info) as $descr) {
                                $d1=preg_split("/\./",$descr);
                                $d1=$d1[0];
                                if ($act_descr != $d1) {
                                    if (in_array($d1,array_keys($descr_f))) {
                                        $hline=$descr_f[$d1];
                                    } else {
                                        $hline=$d1;
                                    }
                                    echo "<option disabled>--- $hline ---</option>\n";
                                    $act_descr=$d1;
                                }
                                echo "<option value=\"$descr\"".(in_array($descr,$actrrd_dec) ? " selected " : "").">";
                                if ($mach->from_snmp[$descr]) echo "[SNMP] ";
                                echo "{$mach->info[$descr]}</option>\n";
                            }
                            echo "</select></td>";
                        } else {
                            echo "No datasets found";
                        }
                    }
                }
                hidden_sid();
                echo $hiddenmach;
                if (!$del_something) {
                    echo "<td class=\"top\"><table class=\"simplesmall\">";
                    $show_array=array(array("End time","endtime",$endtimes),array("Time Frame","timeframe",$timeframes),array("X-Size","x_size",$x_sizes),array("Y-Size","y_size",$y_sizes));
                    if (!isset($mach)) $show_array[]=array("Compose","compose",$compose_opts);
                    foreach ($show_array as $act_a) {
                        list($out_str,$var_name,$var_list)=$act_a;
                        echo "<tr><td class=\"right\">$out_str:</td><td class=\"left\">";
                        $idx_name="act_{$var_name}_idx";
                        echo "<select name=\"{$var_name}idx\" >\n";
                        foreach ($var_list as $idx=>$var_stuff) {
                            echo "<option value=\"$idx\"";
                            if ($$idx_name==$idx) echo " selected";
                            echo ">{$var_stuff['name']}";
                            if ($var_name=="x_size") echo " ({$var_stuff['x']} pix)";
                            if ($var_name=="y_size") echo " ({$var_stuff['y']} pix)";
                            echo "</option>\n";
                        }
                        echo "</select></td></tr>\n";
                    }
                    echo "</table></td>";
                    $opt_array=array(array("c","no x-grid" ,"noxgrid"   ,""      ),array("c","no y-grid"      ,"noygrid"     ,""    ),
                                     array("c","alt y-grid","altygrid"  ,""      ),array("c","alt y-scale"    ,"altscale"    ,""    ),
                                     array("c","from y=0"  ,"yzero"     ,""      ),array("c","rule at y=0"    ,"yzrule"      ,""    ),
                                     array("r","y-start"   ,"ystart"    ,$y_start),array("r","y-end"          ,"yend"        ,$y_end),
                                     array("c","rigid mode","rigid"     ,""      ),array("c","rel. to average","reltoaverage",""    ),
                                     array("c","time-marks","drawtmarks",""      ),array("c","no y-autoscale" ,"noyas"       ,""    ));
                    if (isset($mach)) {
                        $opt_array[]=array("c","boot events"      ,"dboots"   ,"");
                        $opt_array[]=array("c","cluster events"   ,"dccevents","");
                        $opt_array[]=array("c","configure drawing","cdrawing" ,"");
                        $opt_array[]=array("c","configure events" ,"cccevents","");
                    } else {
                        $opt_array[]=array("c","mean value"       ,"meanvalue","");
                        $opt_array[]=array("c","ignore NANs"      ,"ignorenan","");
                        $opt_array[]=array("c","configure drawing","cdrawing" ,"");
                    }
                    $num_max_rows=4;
                    $act_row=0;
                    echo "<td class=\"top\">";
                    echo "<table class=\"simplesmall\">\n";
                    foreach ($opt_array as $act_array) {
                        list($v_type,$str,$varname,$def_v)=$act_array;
                        if (!$act_row++) echo "<tr>";
                        echo "<td class=\"right\">$str:</td><td class=\"left\">";
                        if ($v_type == "c") {
                            echo "<input type=checkbox name=\"$varname\" ";
                            if (in_array($varname,$var_keys)) echo " checked ";
                            echo "/>";
                        } else {
                            echo "<input name=\"$varname\" value=\"$def_v\" maxlength=10 size=4 />";
                        }
                        echo "</td>\n";
                        if ($act_row==$num_max_rows) {
                            $act_row=0;
                            echo "</tr>";
                        }
                    }
                    echo "</table>";
                    echo "</td></tr>\n";
                    echo "<tr><td colspan=\"4\">";
                    echo "<input type=submit value=\"select\" />";
                    echo "</td></tr>";
                    echo "</table></form></td>\n";
                }
                if ($log_stack->get_num_messages()) $log_stack->print_messages();
            }
            echo "</tr></table></div>";
            if (sizeof($actmach)) {
                $mres=query("SELECT cs.value FROM config_str cs, config c WHERE cs.config=c.config_idx AND c.name='rrd_server' AND cs.name='rrd_dir'");
                if (mysql_num_rows($mres)) {
                    $mfr=mysql_fetch_object($mres);
                    $rrddir=$mfr->value;
                } else {
                    $rrddir="/var/lib/rrd-server/rrds";
                }
                if ($show_sthg == "ov") {
                    // get rrd-classes
                    $all_rrd_classes=get_rrd_classes();
                    // logging stack
                    $log_stack=new messagelog();
                    //if ($actmach[0] == $allm_name && !$show_total) {
                    //echo $show_sthg;
                    $ignore_list=array("df");
                    $sel_str="SELECT rd.info,rd.descr1,TRIM('.' FROM CONCAT_WS('.',rd.descr1,rd.descr2,rd.descr3,rd.descr4)) AS descr,rd.rrd_index,rs.device,dt.identifier FROM rrd_data rd, rrd_set rs, device d, device_type dt WHERE rs.device=d.device_idx AND d.device_type=dt.device_type_idx AND dt.identifier != 'MD' AND rs.device > 0 AND rd.rrd_set=rs.rrd_set_idx";
                    if (count($ignore_list)) $sel_str.=" AND NOT (rd.descr1='".implode("' OR rd.descr1='",$ignore_list)."')";
                    $mr2=query($sel_str);
                    $diff_descrs=array();
                    $diff_info=array();
                    $diff_d1s=array();
                    while ($mfr2=mysql_fetch_object($mr2)) {
                        $ddarray=array();
                        $descr=$mfr2->descr;
                        if (in_array($descr,array_keys($diff_descrs))) {
                            $diff_descrs[$descr]++;
                        } else {
                            $diff_descrs[$descr]=1;
                            $diff_infos[$descr]=$mfr2->info;
                            if (!in_array($mfr2->descr1,array_keys($diff_d1s))) $diff_d1s[$mfr2->descr1]=array();
                            $diff_d1s[$mfr2->descr1][]=$descr;
                        }
                    }
                    $machmod_list=array();
                    foreach (array_keys($disp_array) as $gname) {
                        if ($disp_type[$gname] != "S") {
                            foreach ($disp_array[$gname] as $key=>$mname) {
                                $mach=&$machine_list[$mname];
                                if (is_set("{$mach->name}_rrdc",&$vars)) {
                                    $new_rrdc=$vars["{$mach->name}_rrdc"];
                                    if ($new_rrdc != $mach->rrd_class) {
                                        $log_stack->add_message("Changed rrd-class of device $mach->name to {$all_rrd_classes[$new_rrdc]->name}","ok",1);
                                        $mach->rrd_class=$new_rrdc;
                                        query("UPDATE device SET rrd_class=$new_rrdc WHERE name='$mach->name'");
                                    }
                                }
                                if (is_set("{$mach->name}_rrdr",&$vars)) {
                                    $machmod_list[]=$mach->name;
                                }
                                unset($mach);
                            }
                        }
                    }
                    if (count($machmod_list)) {
                        $rets=contact_server($sys_config,"rrd_server",8003,"-c rebuild ".implode(":",$machmod_list));
                        //echo $rets;
                        $log_stack->add_message("Refreshed devices ","ok",1);
                    }
                    if ($log_stack->get_num_messages()) $log_stack->print_messages();
                    message("Overview of all ".strval(sizeof(array_keys($machine_list)))." machines with an associated RRD and all ".count($diff_descrs)." parameters");
                    $max_m_width=0;
                    foreach (array_keys($disp_array) as $gname) {
                        if ($disp_type[$gname] != "S") $max_m_width=max($max_m_width,count($disp_array[$gname]));
                    }
                    $max_m_width=min(3,$max_m_width);
                    echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                    echo "<table class=\"normal\">\n";
                    echo "<tr><th class=\"group\">Devicegroup</td><th class=\"last\" colspan=\"".strval(4*$max_m_width+$max_m_width-1)."\">Devices</th></tr>\n";
                    $machname_list=array_keys($machine_list);
                    $rets=contact_server($sys_config,"rrd_server",8003,"-c flush ".implode(":",$machname_list));
                    $rets_p=explode("#",$rets);
                    $header=array_shift($rets_p);
                    $con_error=((preg_match("/^error.*$/",$header)) ? 1 : 0);
                    foreach ($machname_list as $mach) $machname_list[$mach]=explode(":",array_shift($rets_p));
                    //print_r($machname_list);
                    foreach (array_keys($disp_array) as $gname) {
                        $first=0;
                        $has_md=0;
                        if ($disp_type[$gname] != "S") {
                            $mach_count=0;
                            foreach ($disp_array[$gname] as $key=>$mname) {
                                $mach=&$machine_list[$mname];
                                if ($mach->dev_type == "MD") {
                                    $has_md=1;
                                } else {
                                    $mach_count++;
                                }
                            }
                            $max_height=intval(($mach_count+$max_m_width-1)/$max_m_width);
                            $act_row=0;
                            $act_line=0;
                            if ($has_md) {
                                $max_height++;
                            }
                            echo "<tr><td class=\"dds\" rowspan=\"$max_height\" >$gname</td>";
                            foreach (array("MD","x") as $dst) {
                                foreach ($disp_array[$gname] as $key=>$mname) {
                                    $mach=&$machine_list[$mname];
                                    if ($mach->dev_type == $dst || ($dst == "x" && $mach->dev_type != "MD")) {
                                        if (!$act_row++ && $act_line) echo "<tr>";
                                        if ($con_error) {
                                            $rel_c="error";
                                            list($rel_date,$diff_seconds)=array("unknown (server error)",0);
                                        } else {
                                            list($ret,$ret_type)=$machname_list[$mname];
                                            if ($ret == -1) {
                                                $rel_c="error";
                                                list($rel_date,$diff_seconds)=array("never (no file)",0);
                                            } else {
                                                $act_time=intval(time());
                                                list($abs_date,$rel_date,$diff_seconds)=get_last_update($ret,time()-$ret);
                                                $rel_date="[$ret_type] $rel_date ago";
                                                if ($diff_seconds > 300) {
                                                    $rel_c="error";
                                                } else if ($diff_seconds > 200) {
                                                    $rel_c="warn";
                                                } else {
                                                    $rel_c="ok";
                                                }
                                            }
                                        }
                                        if ($dst=="MD") {
                                            $tdc="md";
                                        } else {
                                            $tdc="d";
                                        }
                                        echo "<td nowrap=\"nowrap\" class=\"rel${tdc}rok\">";
                                        echo "<a class=\"rrd$tdc\" href=\"rrd.php?".write_sid()."&selmach[]=$mach->name\" >".($dst=="MD" ? "MetaDevice" : $mach->name)."</a>, </td>\n";
                                        echo "<td nowrap=\"nowrap\" class=\"rel${tdc}cok\"><select name=\"{$mach->name}_rrdc\" >";
                                        echo "<option value=\"0\" selected>";
                                        if ($mach->rrd_class) {
                                            if (in_array($mach->rrd_class,array_keys($all_rrd_classes))) {
                                                echo "{$all_rrd_classes[$mach->rrd_class]->name}";
                                            } else {
                                                echo "(idx $mach->rrd_class)";
                                            }
                                        } else {
                                            echo "(not set)";
                                        }
                                        echo ", keep</option>\n";
                                        foreach ($all_rrd_classes as $idx=>$stuff) {
                                            if ($mach->rrd_class != $idx) echo "<option value=\"$idx\">$stuff->name</option>";
                                        }
                                        echo "</select></td>\n";
                                        echo "<td nowrap=\"nowrap\" class=\"rel${tdc}cok\"><input type=checkbox name=\"{$mach->name}_rrdr\" /></td>\n";
                                        echo "<td nowrap=\"nowrap\" class=\"rel".($rel_c=="ok" ? $tdc : "d")."l$rel_c\">, $rel_date</td>\n";
                                        if ($mach->dev_type == "MD") {
                                            if (!$first) echo "<td rowspan=\"$max_height\" class=\"dds\">&nbsp;&nbsp;</td>\n";
                                            while ($act_row < $max_m_width) {
                                                $act_row++;
                                                echo "<td colspan=\"4\" class =\"group\">&nbsp;</td>\n";
                                                if (!$first && $act_row < $max_m_width) echo  "<td rowspan=\"$max_height\" class=\"dds\">&nbsp;&nbsp;</td>\n";
                                            }
                                        }
                                        if ($act_row == $max_m_width) {
                                            $act_row=0;
                                            echo "</tr>\n";
                                            $act_line++;
                                            $first++;
                                        }
                                        if (!$first) echo "<td rowspan=\"$max_height\" class=\"dds\">&nbsp;&nbsp;</td>\n";
                                    }
                                }
                            }
                            if ($act_row) {
                                while ($act_row < $max_m_width) {
                                    $act_row++;
                                    echo "<td colspan=\"4\" class =\"group\">&nbsp;</td>\n";
                                    if (!$first && $act_row < $max_m_width) echo  "<td rowspan=\"$max_height\" class=\"dds\">&nbsp;&nbsp;</td>\n";
                                }
                                echo "</tr>\n";
                            }
                            $first++;
                        }
                    }
                    echo "</table><div class=\"center\"><input type=submit value=\"submit\"/></div></form>\n";
                    function diff_d1_sort($v0,$v1) {
                        if (count($v0) < count($v1)) {
                            return -1;
                        } else if (count($v0) > count($v1)) {
                            return 1;
                        } else {
                            return 0;
                        }
                    }
                    uasort($diff_d1s,"diff_d1_sort");
                    $max_width=4;
                    $diff_d1s_keys=array_keys($diff_d1s);
                    echo "<table class=\"normal\">\n";
                    echo "<tr><th class=\"group\">Group</th><th class=\"dds\">Show</th>";
                    echo "<th class=\"dds\" colspan=\"".strval($max_width*3)."\">RRD data</th></tr>\n";
                    foreach ($diff_d1s as $d1=>$d1f) {
                        $len=count($d1f);
                        $max_height=intval((count($d1f)+$max_width-1)/$max_width);
                        echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                        echo "<tr><td rowspan=\"$max_height\" class=\"group\" >";
                        if (in_array($d1,array_keys($descr_f))) {
                            echo $descr_f[$d1];
                        } else {
                            echo $d1;
                        }
                        echo "</td>\n";
                        echo "<td class=\"dds\" rowspan=\"$max_height\" >";
                        echo "<input type=submit name=\"submit\" value=\"Show\" />";
                        echo "<input type=hidden name=\"showtotal\" value=\"1\" />";
                        echo "<input type=hidden name=\"selmach[]\" value=\"$allm_name\" />";
                        echo "<input type=hidden name=\"ignorenan\" value=\"1\" />";
                        echo "<input type=hidden name=\"cdrawing\" value=\"1\" />";
                        echo "</td>";
                        $act_row=0;
                        $act_line=0;
                        foreach ($d1f as $d1l) {
                            if (!$act_row++ && $act_line) echo "<tr>";
                            echo "<td class=\"rrdinfo\">".shorten_info_string($diff_infos[$d1l])."</td>";
                            echo "<td class=\"dds\">";
                            echo "<input type=checkbox name=\"selrrd[]\" value=\"$d1l\" checked />";
                            echo "</td>";
                            echo "<td class=\"ndev\">{$diff_descrs[$d1l]}</td>";
                            if ($act_row == $max_width) {
                                $act_row=0;
                                echo "</tr>\n";
                                $act_line++;
                            }
                        }
                        if ($act_row < $max_width && $act_row) echo "<td colspan=\"".strval(3*($max_width-$act_row))."\" class =\"group\">&nbsp</td></tr>\n";
                        echo "</form>";
                    }
                    echo "</table>";
                    //</div>";
                } else if ($show_sthg == "conf") {
                    $log_stack=new messagelog();
                    $all_rrd_classes=get_rrd_classes();
                    $all_rrd_names=array();
                    foreach ($all_rrd_classes as $idx=>$stuff) $all_rrd_names[]=$stuff->name;
                    $all_heartbeats=array(30,60,90,120,150,180);
                    $all_steps=array(30,60,90,120,150,180);
                    $all_cf_functions=array("--please select--"=>0,
                                            "MIN"=>1,"AVERAGE"=>1,"MAX"=>2);
                    foreach ($all_rrd_classes as $idx=>$stuff) {
                        $pfix="rrd$idx";
                        if (is_set("{$pfix}del",&$vars)) {
                            $log_stack->add_message("Deleted rrd_class named '$stuff->name'","OK",1);
                            unset($all_rrd_classes[$idx]);
                            query("DELETE FROM rrd_rra WHERE rrd_class=$idx");
                            query("DELETE FROM rrd_class WHERE rrd_class_idx=$idx");
                        } else {
                            if (is_set("{$pfix}name",&$vars)) {
                                $new_name=$vars["{$pfix}name"];
                                $sql_f=array();
                                if ($stuff->name != $new_name) {
                                    if (!in_array($new_name,$all_rrd_names)) {
                                        $log_stack->add_message("Changed name of rrd_class from '$stuff->name' to '$new_name'","ok",1);
                                        $sql_f[]="name='".mysql_escape_string($new_name)."'";
                                        unset($all_rrd_names[array_search($stuff->name,$all_rrd_names,FALSE)]);
                                        $all_rrd_names[]=$new_name;
                                        $all_rrd_classes[$idx]->name=$new_name;
                                    } else {
                                        $log_stack->add_message("Cannot rename rrd_class from '$stuff->name' to '$new_name'","Name '$new_name' already used",0);
                                    }
                                }
                                $new_rrd_num=trim($vars["{$pfix}numds"]);
                                if ($new_rrd_num != $stuff->num_rrd) {
                                    if (!is_positive_integer($new_rrd_num)) {
                                        $log_stack->add_message("Cannot change num_ds of rrd_class named '$stuff->name' from '$stuff->num_rrd' to '$new_rrd_num'","DS_num is not a positive integer");
                                    } else {
                                        $new_rrd_num=(int)$new_rrd_num;
                                        $log_stack->add_message("Changed change num_ds of rrd_class named '$stuff->name' from '$stuff->num_rrd' to '$new_rrd_num'","ok",1);
                                        $sql_f[]="num_rrd=$new_rrd_num";
                                        $all_rrd_classes[$idx]->num_rrd=$new_rrd_num;
                                    }
                                }
                                $new_hb=$vars["{$pfix}hb"];
                                if ($new_hb != $stuff->heartbeat) {
                                    $sql_f[]="heartbeat=$new_hb";
                                    $log_stack->add_message("Changed HeartBeat of rrd_class named '$stuff->name' from '$stuff->heartbeat' to '$new_hb'","ok",1);
                                    $all_rrd_classes[$idx]->heartbeat=$new_hb;
                                }
                                $new_step=$vars["{$pfix}step"];
                                if ($new_step != $stuff->step) {
                                    $sql_f[]="step=$new_step";
                                    $log_stack->add_message("Changed Step of rrd_class named '$stuff->name' from '$stuff->step' to '$new_step'","ok",1);
                                    $all_rrd_classes[$idx]->step=$new_step;
                                }
                                if ($sql_f) {
                                    query("UPDATE rrd_class SET ".implode(",",$sql_f)." WHERE rrd_class_idx=$idx");
                                }
                                // check for altering of rras
                                foreach ($stuff->struct as $ridx=>$rstuff) {
                                    $rpfix="rrd{$idx}rra{$ridx}";
                                    if (is_set("{$rpfix}cf",&$vars)) {
                                        $rracf=$vars["{$rpfix}cf"];
                                        $new_steps=$vars["{$rpfix}steps"];
                                        $new_rows=$vars["{$rpfix}rows"];
                                        $new_xff=$vars["{$rpfix}xff"];
                                        if ($rracf=="delete") {
                                            query ("DELETE FROM rrd_rra WHERE rrd_rra_idx=$ridx");
                                            $log_stack->add_message("Delete rrd_rra from rrd_set named '$stuff->name'","OK",1);
                                            unset($all_rrd_classes[$idx]->struct[$ridx]);
                                        } else {
                                            $sql_f=array();
                                            if ($rracf != $rstuff->cf) {
                                                $sql_f[]="cf='$rracf'";
                                                $log_stack->add_message("Changed CF for rrd_rra from '$rstuff->cf' to '$rracf'","ok",1);
                                                $all_rrd_classes[$idx]->struct[$ridx]->cf=$rracf;
                                            }
                                            if (is_positive_integer($new_steps)) {
                                                $new_steps=(int)$new_steps;
                                                if ($new_steps != $rstuff->steps) {
                                                    $sql_f[]="steps=$new_steps";
                                                    $all_rrd_classes[$idx]->struct[$ridx]->steps=$new_steps;
                                                    $log_stack->add_message("Changed Steps for RRD_rra from $rstuff->steps to $new_steps","OK",1);
                                                }
                                            } else {
                                                $log_stack->add_message("Cannot change Steps for RRD_rra from $rstuff->steps to $new_steps","not a positive integer",0);
                                            }
                                            if (is_positive_integer($new_rows)) {
                                                $new_rows=(int)$new_rows;
                                                if ($new_rows != $rstuff->rows) {
                                                    $sql_f[]="rows=$new_rows";
                                                    $all_rrd_classes[$idx]->struct[$ridx]->rows=$new_rows;
                                                    $log_stack->add_message("Changed Rows for RRD_rra from $rstuff->rows to $new_rows","OK",1);
                                                }
                                            } else {
                                                $log_stack->add_message("Cannot change Rows for RRD_rra from $rstuff->rows to $new_rows","not a positive integer",0);
                                            }
                                            if (is_positive_float($new_xff)) {
                                                $new_xff=(float)$new_xff;
                                                if ($new_xff != $rstuff->xff) {
                                                    $sql_f[]="xff=$new_xff";
                                                    $all_rrd_classes[$idx]->struct[$ridx]->xff=$new_xff;
                                                    $log_stack->add_message("Changed XFF for RRD_rra from $rstuff->xff to $new_xff","OK",1);
                                                }
                                            } else {
                                                $log_stack->add_message("Cannot change XFF for RRD_rra from $rstuff->xff to $new_xff","not a positive float",0);
                                            }
                                            if ($sql_f) {
                                                query("UPDATE rrd_rra SET ".implode(",",$sql_f)." WHERE rrd_rra_idx=$ridx");
                                            }
                                        }
                                    }
                                }
                                // check for new rras
                                $rpfix="rrd{$idx}nrra";
                                if (is_set("{$rpfix}cf",&$vars)) {
                                    $new_cf=$vars["{$rpfix}cf"];
                                    $new_steps=$vars["{$rpfix}steps"];
                                    $new_rows=$vars["{$rpfix}rows"];
                                    $new_xff=$vars["{$rpfix}xff"];
                                    if (is_positive_integer($new_steps) && is_positive_integer($new_rows) && is_positive_float($new_xff)) {
                                        $ins_idx=insert_table("rrd_rra","0,$idx,'$new_cf',$new_steps,$new_rows,$new_xff,null");
                                        if ($ins_idx) {
                                            $log_stack->add_message("Added new rrd_RRA to rrd_set '$stuff->name'","ok",1);
                                            $all_rrd_classes[$idx]->struct[$ins_idx]=new stdclass();
                                            $all_rrd_classes[$idx]->struct[$ins_idx]->rrd_class=$idx;
                                            $all_rrd_classes[$idx]->struct[$ins_idx]->cf=$new_cf;
                                            $all_rrd_classes[$idx]->struct[$ins_idx]->steps=$new_steps;
                                            $all_rrd_classes[$idx]->struct[$ins_idx]->rows=$new_rows;
                                            $all_rrd_classes[$idx]->struct[$ins_idx]->xff=$new_xff;
                                        } else {
                                            $log_stack->add_message("Cannot add new rrd_RRA to rrd_set '$stuff->name'","SQL Error",0);
                                        }
                                    } else {
                                        if (!is_positive_integer($new_steps)) $log_stack->add_message("Steps for new RRA of rrd_set '$stuff->name' is not a positive integer","error",0);
                                        if (!is_positive_integer($new_rows)) $log_stack->add_message("Rows for new RRA of rrd_set '$stuff->name' is not a positive integer","error",0);
                                        if (!is_positive_float($new_xff)) $log_stack->add_message("XFF for new RRA of rrd_set '$stuff->name' is not a positive float","error",0);
                                    }
                                }
                            }
                        }
                    }
		    if (is_set("newrrdname",&$vars)) {
			$new_name=$vars["newrrdname"];
			if (in_array($new_name,$all_rrd_names)) {
			    $log_stack->add_message("Cannot add new rrd_class named '$new_name'","Name '$new_name' already used",0);
			} else {
			    $new_rrd_num=trim($vars["newrrdnumds"]);
			    if (!is_positive_integer($new_rrd_num)) {
				$log_stack->add_message("Cannot add add new rrd_class named '$new_name'","DS_num is not a positive integer",0);
			    } else {
				$new_rrd_num=(int)$new_rrd_num;
				$newstep=$vars["newrrdhb"];
				$newhb=$vars["newrrdhb"];
				$ins_idx=insert_table("rrd_class","0,'".mysql_escape_string($new_name)."',$new_rrd_num,$newstep,$newhb,null");
				if ($ins_idx) {
				    $log_stack->add_message("Added new rrd_class named '$new_name'","ok",1);
				    $all_rrd_classes[$ins_idx]=new stdclass();
				    $all_rrd_classes[$ins_idx]->name=$new_name;
				    $all_rrd_classes[$ins_idx]->num_rrd=$new_rrd_num;
				    $all_rrd_classes[$ins_idx]->step=$newstep;
				    $all_rrd_classes[$ins_idx]->heartbeat=$newhb;
				    $all_rrd_classes[$ins_idx]->struct=array();
				    if (is_set("newrrdcpy",&$vars)) {
					$rrd_src=$vars["newrrdcpy"];
					if (in_array($rrd_src,array_keys($all_rrd_classes))) {
					    $src_rrd=&$all_rrd_classes[$rrd_src];
					    foreach ($src_rrd->struct as $ridx=>$rstuff) {
						$i2_idx=insert_table("rrd_rra","0,$ins_idx,'".mysql_escape_string($rstuff->cf)."',$rstuff->steps,$rstuff->rows,$rstuff->xff,null");
						$all_rrd_classes[$ins_idx]->struct[$i2_idx]=new stdclass();
						$all_rrd_classes[$ins_idx]->struct[$i2_idx]->rrd_class=$i2_idx;
						$all_rrd_classes[$ins_idx]->struct[$i2_idx]->cf=$rstuff->cf;
						$all_rrd_classes[$ins_idx]->struct[$i2_idx]->steps=$rstuff->steps;
						$all_rrd_classes[$ins_idx]->struct[$i2_idx]->rows=$rstuff->rows;
						$all_rrd_classes[$ins_idx]->struct[$i2_idx]->xff=$rstuff->xff;
					    }
					    $log_stack->add_message("Copied ".get_plural("RRA",count($all_rrd_classes[$ins_idx]->struct),1)." from '$src_rrd->name' to new rrd_class '$new_name'","ok",1);
					}
				    }
				} else {
				    $log_stack->add_message("Cannot add add new rrd_class named '$new_name'","SQL Error",0);
				}
			    }
			}
                    }
                    if ($log_stack->get_num_messages()) $log_stack->print_messages();
                    echo "<div class=\"center\"><form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                    echo $hiddentime;
                    echo $hiddensize;
                    echo $hiddencompose;
                    echo $hiddenmach;
                    echo $hiddenrrd;
                    echo $hiddengp;
                    echo $hiddenyas;
                    $num_rrd_classes=count($all_rrd_classes);
                    if ($num_rrd_classes) {
                        if ($num_rrd_classes== 1) {
                            message("Found 1 RRD class");
                        } else {
                            message("Found $num_rrd_classes RRD classes");
                        }
                    } else {
                        message("Found no RRD classes");
                    }
                    echo "<table class=\"normal\">";
                    foreach ($all_rrd_classes as $idx=>$stuff) {
                        $pfix="rrd$idx";
                        $num_rras=count($stuff->struct);
                        $num_rras_2=$num_rras;
                        if (!$num_rras) $num_rras_2++;
                        $num_rras_2+=3;
                        echo "<tr><td class=\"name\" colspan=\"4\">Name:<input name=\"{$pfix}name\" value=\"$stuff->name\" size=\"20\" maxlength=\"40\" />, delete:<input type=checkbox name=\"{$pfix}del\" />, \n";
			
                        echo "Number of Datasources:<input name=\"{$pfix}numds\" size=\"20\" maxlength=\"10\" value=\"$stuff->num_rrd\" />, \n";
                        echo "Step:<select name=\"{$pfix}step\" >";
                        foreach ($all_steps as $num) {
                            echo "<option value=\"$num\" ";
                            if ($num == $stuff->step) echo " selected ";
                            echo " >$num</option>\n";
                        }
                        echo "</select> seconds, \n";
                        echo "Hearbeat:<select name=\"{$pfix}hb\" >";
                        foreach ($all_heartbeats as $num) {
                            echo "<option value=\"$num\" ";
                            if ($num == $stuff->heartbeat) echo " selected ";
                            echo " >$num</option>\n";
                        }
                        echo "</select> seconds</td>\n";
                        echo "</tr>\n";
                        if (!$num_rras) {
                            echo "<tr><td colspan=\"4\" class=\"average\" >No RRAs defined</td></tr>\n";
                        } else {
                            foreach ($stuff->struct as $ridx=>$rstuff) {
                            }
                        }
                        $tot_size=540;
                        foreach ($stuff->struct as $ridx=>$rstuff) {
                            $pfix="rrd{$idx}rra{$ridx}";
                            echo "<tr><td class=\"pri\">CF:<select name=\"{$pfix}cf\" >";
                            foreach ($all_cf_functions as $act_cf=>$didx){
                                if ($didx) {
                                    echo "<option value=\"$act_cf\" ";
                                    if ($rstuff->cf == $act_cf) echo " selected ";
                                    echo ">$act_cf</option>\n";
                                } else {
                                    echo "<option value=\"delete\" >--delete this rra--</option>\n";
                                }
                            }
                            echo "</select></td>\n";
                            echo "<td class=\"steps\">steps:<input name=\"{$pfix}steps\" size=\"20\" maxlength=\"20\" value=\"$rstuff->steps\"/>, PDP length: ".get_time_str($rstuff->steps*$stuff->step)."</td>\n";
                            echo "<td class=\"rows\">rows:<input name=\"{$pfix}rows\" size=\"20\" maxlength=\"20\" value=\"$rstuff->rows\"/>, total length: ".get_time_str($rstuff->steps*$stuff->step*$rstuff->rows)."</td>\n";
                            echo "<td class=\"minimum\">xff:<input name=\"{$pfix}xff\" size=\"20\" maxlength=\"20\" value=\"$rstuff->xff\"/></td>\n";
                            $tot_size+=$rstuff->rows*8*$stuff->num_rrd;
                            echo "</tr>\n";
                        }
                        $pfix="rrd{$idx}nrra";
                        echo "<tr><td class=\"pri\">CF:<select name=\"{$pfix}cf\" >";
                        foreach ($all_cf_functions as $act_cf=>$idx){
                            echo "<option ";
                            if ($idx) { 
                                echo " value=\"$act_cf\" ";
                            } else {
                                echo " value=\"$idx\" ";
                            }
                            echo ">$act_cf</option>\n";
                        }
                        echo "</select></td>\n";
                        echo "<td class=\"steps\">steps:<input name=\"{$pfix}steps\" size=\"20\" maxlength=\"20\" value=\"2\"/></td>\n";
                        echo "<td class=\"rows\">rows:<input name=\"{$pfix}rows\" size=\"20\" maxlength=\"20\" value=\"2000\"/></td>\n";
                        echo "<td class=\"minimum\">xff:<input name=\"{$pfix}xff\" size=\"20\" maxlength=\"20\" value=\"0.1\"/></td>\n";
                        echo "</tr>\n";
                        echo "<tr><td class=\"cf\" colspan=\"4\">Needed size per RRD-Database: ".get_size_str($tot_size)."</td></tr>\n";
                    }
                    echo "<tr><td class=\"name\" colspan=\"4\">NewName:<input name=\"newrrdname\" size=\"20\" maxlength=\"40\" value=\"\" />, \n";
                    echo "Number of Datasources:<input name=\"newrrdnumds\" size=\"20\" maxlength=\"10\" value=\"128\" />, \n";
                    echo "Step:<select name=\"newrrdstep\" >";
                    foreach ($all_steps as $num) echo "<option value=\"$num\">$num</option>\n";
                    echo "</select> seconds, \n";
                    echo "Hearbeat:<select name=\"newrrdhb\" >";
                    foreach ($all_heartbeats as $num) echo "<option value=\"$num\">$num</option>\n";
                    echo "</select> seconds, \n";
                    echo "Copy from:<select name=\"newrrdcpy\" >";
                    echo "<option value=\"0\">no copy</option>\n";
                    foreach ($all_rrd_classes as $idx=>$stuff) {
                        echo "<option value=\"$idx\">$stuff->name</option>\n";
                    }
                    echo "</select></td>\n";
                    echo "</tr></table>\n";
                    echo "<input type=submit value=\"submit\"/></form></div>\n";
                } else {
                    if ($del_something) {
                        $mach=&$machine_list[$actmach[0]];
                        if (count($delrrd_dec)) {
                            $del_log=new messagelog();
	      
                            $hiddenrrd="";
                            foreach($actrrd_dec as $rrd_dec) {
                                $keep=1;
                                if (in_array($rrd_dec,$delrrd_dec)) {
                                    $rets=contact_server($sys_config,"rrd_server",8003,"-c del_rrd_data ".$mach->name." $rrd_dec");
                                    if (preg_match("/^(\S+)\s+(.*)$/",$rets,$what)) {
                                        if ($what[1] == "ok") $keep=0;
                                        $del_log->add_message("Delete {$mach->info[$rrd_dec]} on $mach->name",$what[2],($what[1]=="ok"));
                                    } else {
                                        $del_log->add_message("Delete {$mach->info[$rrd_dec]} on $mach->name",$rets,0);
                                    }
                                }
                                if ($keep) $hiddenrrd.="<input type=hidden name=\"selrrd[]\" value=\"$rrd_dec\" />\n";
                            }
                            $del_log->print_messages("Delete Log on machine $mach->name (".get_plural("dataset",count($delrrd_dec),1)."):");
                            echo "<div class=\"center\"><form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                            hidden_sid();
                            echo $hiddenrrd;
                            echo $hiddentime;
                            echo $hiddensize;
                            echo $hiddencompose;
                            echo $hiddenmach;
                            echo $hiddengp;
                            echo $hiddenyas;
                            echo "<input type=submit value=\"OK\" />";
                            echo "</form></div>\n";
                        } else {
                            $del_list=array();
                            foreach($actrrd_dec as $rrd_dec) {
                                $act_rrd=&$rrd_list[$rrd_dec];
                                if (in_array(my_encode("{$act_rrd->descr}.del"),$var_keys)) $del_list[]=array($rrd_dec,$act_rrd->descr,$mach->info[$rrd_dec]);
                            }
                            message("Please confirm the deletion of ".get_plural("dataset",count($del_list),1)." on machine $mach->name :",$type=1);
                            echo "<div class=\"center\">";
                            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>\n";
                            echo "<table class=\"normalnf\">\n";
                            echo "<tr><th class=\"dds\">Name</th><th class=\"dellog\">Key</th></tr>\n";
                            foreach($del_list as $del_stuff) {
                                list($rrd_dec,$descr,$info)=$del_stuff;
                                echo "<tr><td class=\"dds\">$info</td><td class=\"dellog\">$rrd_dec</td></tr>\n";
                                echo "<input type=hidden name=\"{$descr}.del\" value=1 />\n";
                                echo "<input type=hidden name=\"delrrd[]\" value=\"$rrd_dec\" />\n";
                            }
                            echo "</table>\n";
                            hidden_sid();
                            echo $hiddentime;
                            echo $hiddensize;
                            echo $hiddencompose;
                            echo $hiddenmach;
                            echo $hiddenrrd;
                            echo $hiddengp;
                            echo $hiddenyas;
                            echo "<input type=submit value=\"delete\" />";
                            echo "</form></div>\n";
                        }
                    } else {
                        $act_time=intval(time());
                        $num_rrd=sizeof($actrrd_dec);
                        if ($show_sthg == "tot") {
                            //echo date("l, j. F Y; G:i:s",time())."<br>";
                            $ret=contact_server($sys_config,"rrd_server",8003,"-c flush ".implode(":",$tot_mach));
                            $num_machs=sizeof($tot_mach);
                            $new_dec=array();
                            foreach ($actrrd_dec as $rrd_dec) {
                                $act_rrd=&$rrd_list[$rrd_dec];
                                if ($act_rrd->show) {
                                    $new_dec[]=$rrd_dec;
                                    $act_rrd->valid_machs=count($act_rrd->mach_list);
                                } else {
                                    $num_rrd--;
                                }
                            }
                            //echo date("l, j. F Y; G:i:s",time())."<br>";
                            $actrrd_dec=$new_dec;
                            $h4_str="Showing $num_rrd ".get_plural("dataset",$num_rrd)." of $num_machs ".get_plural("machine",$num_machs);
                        } else {
                            $mach=&$machine_list[$actmach[0]];
                            //get last update
                            $ret=contact_server($sys_config,"rrd_server",8003,"-c flush {$actmach[0]}");
                            $ret=explode("#",$ret);
                            $ret=intval($ret[1]);
                            list($abs_date,$rel_date,$diff_seconds)=get_last_update($ret,$act_time-$ret);
                            $h4_str="RRD of ".$mach->get_name()." last updated: $abs_date ($rel_date ago)";
                            if ($num_rrd) {
                                $h4_str.=", selected $num_rrd of ".get_plural("dataset",$mach->num_rrd,1)." organized in ".get_plural("diagram",count(array_keys($rrd_diagrams)),1);
                            }
                        }
                        message($h4_str,$type=2);
                        $pos_types=array("AREA","STACK","LINE3","LINE2","LINE1");
                        // check for the configuration of ccevents
                        $configure_cevents=(($show_sthg == "seq" && in_array("cccevents",$var_keys)) ? 1 : 0);
                        $process_str=(in_array("ignorenan",$var_keys) ? ",DUP,UN,EXC,0,EXC,IF" : "");
                        $compose_str=$compose_opts[$act_compose_idx]["op"];
                        $do_mean_value=(($compose_opts[$act_compose_idx]["name"]=="Mean") ? 1 : 0);
                        $timeslice=$timeframes[$act_timeframe_idx]["timelen"];
                        $time_end=$act_time-$endtimes[$act_endtime_idx]["timelen"];
                        $time_start=$time_end-$timeslice;
                        // get max/average/min/last-values
                        $comp_str="";
                        $comp_idx=0;
                        $idx=0;
                        $maml_f=array();
                        foreach ($rrd_diagrams as $a=>$b) {
                            $actrrd_dec=array_keys($b);
                            // deselect descriptions not present in the actual machine
                            if ($show_sthg != "tot") {
                                foreach ($actrrd_dec as $descr) {
                                    if (!in_array($descr,$dlist)) {
                                        unset($actrrd_dec[array_search($descr,$actrrd_dec,FALSE)],$rrd_list[$descr]);
                                    }
                                }
                            }
                            if ($num_rrd) {
                                foreach ($actrrd_dec as $rrd_dec) {
                                    $maml_f[$rrd_dec]=array();
                                    $act_rrd=&$rrd_list[$rrd_dec];
                                    foreach (array("MAX","AVERAGE","MIN","LAST") as $dsa) {
                                        $maml_f[$rrd_dec][$dsa]=0.;
                                        $comp_idx++;
                                        $r_dsa=(($dsa == "LAST") ? "AVERAGE" : $dsa);
                                        if ($show_sthg == "tot") {
                                            $idx_start=$idx;
                                            foreach ($act_rrd->mach_list as $mname=>$rrd_stuff) {
                                                if (!in_array($mname,$act_rrd->invalid_machs)) {
                                                    list($rrd_index,$rrd_fname)=$rrd_stuff;
                                                    $comp_str.="DEF:ds$idx={$rrddir}/{$machine_list[$mname]->filename}:v$rrd_index:$r_dsa ";
                                                    $idx++;
                                                }
                                            }
                                            $num_found=$idx-$idx_start;
                                            if ($num_found) {
                                                $comp_str.=" CDEF:vs$comp_idx=ds".implode("$process_str,ds",range($idx_start,$idx-1)).$process_str;
                                                if ($num_found > 1) $comp_str.=str_repeat(",$compose_str",$num_found-1);
                                                if ($do_mean_value) $comp_str.=",$num_found,/";
                                            } else {
                                                $comp_str.=" CDEF:vs$comp_idx=0";
                                            }
                                        } else {
                                            $comp_str.=" DEF:vs$comp_idx={$rrddir}/{$mach->filename}:v{$mach->index[$rrd_dec]}:$r_dsa";
                                        }
                                        $comp_str.=" PRINT:vs$comp_idx:$dsa:$rrd_dec\\\:$dsa\\\:%lf ";
                                    }
                                }
                            }
                        }
                        $actstr="/usr/bin/rrdtool 2>&1 graph /dev/null -s $time_start -e $time_end $comp_str ";
                        $ret_array=array();
                        exec($actstr,$ret_array);
                        $pic_size=array_shift($ret_array);
                        foreach ($ret_array as $ret_line) {
                            preg_match("/^([^:]+):([^:]+):(.*)$/",$ret_line,$ret_stuff);
                            list($bla,$rrd_dec,$dsa,$ret)=$ret_stuff;
                            $maml_f[$rrd_dec][$dsa]=$ret;
                        }
                        if (in_array("cdrawing",$var_keys)) echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post>";
                        $image_idx=0;
			$write_hidden=1;
                        foreach ($rrd_diagrams as $a=>$b) {
                            $image_idx++;
                            $actrrd_dec=array_keys($b);
                            if ($show_sthg != "tot") {
                                // deselect descriptions not present in the actual machine
                                foreach ($actrrd_dec as $descr) {
                                    if (!in_array($descr,$dlist)) {
                                        unset($actrrd_dec[array_search($descr,$actrrd_dec,FALSE)],$rrd_list[$descr]);
                                    }
                                }
                            }
                            if ($num_rrd) {
                                //echo "$timeslice : $time_start - $time_end <br>";
                                echo "<div class=\"center\" >";
                                if (in_array("cdrawing",$var_keys)) {
                                    echo "<input type=hidden name=\"lowsubmit\" value=1 />";
                                    if ($show_sthg == "tot") echo "<input type=hidden name=\"showtotal\" value=\"1\" />";
                                    echo "<table class=\"normal\">\n";
                                    echo "<tr><th class=\"dds\">Dataset</th>";
                                    echo "<th class=\"color\">Min/Aver/Max</th>";
                                    if ($show_sthg == "tot") {
                                        echo "<th class=\"del\">Remove</th>";
                                    } else {
                                        echo "<th class=\"del\">Delete</th>";
                                    }
                                    echo "<th class=\"maximum\">Max</th><th class=\"average\">Average</th><th class=\"minimum\">Min</th>\n";
                                    echo "<th class=\"last\">Last</th><th class=\"type\">Type</th><th class=\"pri\">Priority</th>\n";
                                    echo "<th colspan=\"3\" class=\"color\">Color</th></tr>\n";
                                }
                                $vert_label=array();
                                foreach ($actrrd_dec as $rrd_dec) {
                                    $act_rrd=&$rrd_list[$rrd_dec];
                                    $change=0;
                                    if (in_array("cdrawing",$var_keys)) {
                                        $dt_name=my_encode($rrd_dec.".dt");
                                        $pri_name=my_encode($rrd_dec.".pri");
                                        $col_name=my_encode($rrd_dec.".col");
                                        $colp_name=my_encode($rrd_dec.".colp");
                                        if (in_array("lowsubmit",$var_keys)) {
                                            foreach (array("max","average","min") as $dtype) {
                                                $var_name=my_encode("{$rrd_dec}.rrd.{$dtype}");
                                                $vt_name="rrd_$dtype";
                                                $act_val=(in_array($var_name,$var_keys) ? 1 : 0 );
                                                if ($act_rrd->$vt_name != $act_val) {
                                                    $act_rrd->$vt_name=$act_val;
                                                    $change=1;
                                                }
                                            }
                                            foreach (array("maximum","average","minimum","last") as $dtype) {
                                                $var_name=my_encode("{$rrd_dec}.d{$dtype}");
                                                $vt_name="draw_$dtype";
                                                $act_val=(in_array($var_name,$var_keys) ? 1 : 0 );
                                                if ($act_val != $act_rrd->$vt_name) {
                                                    $act_rrd->$vt_name=$act_val;
                                                    $change=1;
                                                }
                                            }
                                            if (in_array($dt_name,$var_keys)) {
                                                if ($act_rrd->draw_type != $vars[$dt_name]) {
                                                    $change=1;
                                                    $act_rrd->draw_type=$vars[$dt_name];
                                                }
                                            }
                                            if (in_array($pri_name,$var_keys)) {
                                                if ($act_rrd->priority != $vars[$pri_name]) {
                                                    $change=1;
                                                    $act_rrd->priority=$vars[$pri_name];
                                                }
                                            }
                                            if (in_array($colp_name,$var_keys)) {
                                                if ($vars[$colp_name] != "keep") {
                                                    if ($act_rrd->color != $colors[$vars[$colp_name]]) {
                                                        $change=1;
                                                        $act_rrd->color=$colors[$vars[$colp_name]];
                                                    }
                                                } else {
                                                    if (in_array($col_name,$var_keys)) {
                                                        $new_col=strtoupper($vars[$col_name]);
                                                        if (preg_match("/^[A-F0-9]{6}$/",$new_col)) {
                                                            if ($act_rrd->color != $new_col) {
                                                                $change=1;
                                                                $act_rrd->color=$new_col;
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    if (!($act_rrd->rrd_max+$act_rrd->rrd_average+$act_rrd->rrd_min)) {
                                        $act_rrd->rrd_average=1;
                                        $change=1;
                                    }
                                    if ($change or ! $act_rrd->db_entry) {
                                        $d_fields=$act_rrd->get_descr_fields();
                                        ///print_r($d_fields);
                                        if (!$act_rrd->db_entry) {
                                            $act_rrd->db_entry=1;
                                            $mr=query("INSERT INTO rrd_user_data VALUES(0,{$sys_config['user_idx']},'".implode("','",$d_fields)."','$act_rrd->draw_type','$act_rrd->color',".
                                                      "$act_rrd->priority,$act_rrd->rrd_max,$act_rrd->rrd_average,$act_rrd->rrd_min,$act_rrd->draw_maximum,$act_rrd->draw_average,$act_rrd->draw_minimum,$act_rrd->draw_last,null)");
                                        } else {
                                            $mr=query("UPDATE rrd_user_data SET draw_type='$act_rrd->draw_type',color='$act_rrd->color',draw_maximum=$act_rrd->draw_maximum".
                                                      ",draw_average=$act_rrd->draw_average,draw_minimum=$act_rrd->draw_minimum,draw_last=$act_rrd->draw_last,priority=$act_rrd->priority".
                                                      ",rrd_max=$act_rrd->rrd_max,rrd_average=$act_rrd->rrd_average,rrd_min=$act_rrd->rrd_min WHERE user={$sys_config['user_idx']}".
                                                      " AND descr1='{$d_fields[0]}' AND descr2='{$d_fields[1]}' AND descr3='{$d_fields[2]}' AND descr4='{$d_fields[3]}'");
                                        }
                                    }
                                    
                                    if (in_array("cdrawing",$var_keys)) {
                                        echo "<tr><td class=\"dds\" >";
                                        if ($show_sthg == "tot") {
                                            echo $act_rrd->info;
                                        } else {
                                            echo $mach->info[$rrd_dec];
                                        }
                                        echo "</td>";
                                        echo "<td class=\"color\">";
                                        foreach (array("min","average","max") as $dtype) {
                                            $var_name=str_replace(".","_","{$act_rrd->descr}.rrd.{$dtype}");
                                            $vt="rrd_{$dtype}";
                                            echo "<input type=\"checkbox\" name=\"$var_name\" ";
                                            if ($act_rrd->$vt) echo " checked ";
                                            echo " />\n";
                                        }
                                        echo "</td>";
                                        if ($show_sthg == "tot") {
                                            echo "<td class=\"del\"><input type=checkbox name=\"{$act_rrd->descr}.rem\" /></td>\n";
                                        } else {
                                            echo "<td class=\"del\"><input type=checkbox name=\"{$act_rrd->descr}.del\" /></td>\n";
                                        }
                                    }
                                    $act_rrd->maximum=doubleval($maml_f[$rrd_dec]["MAX"]);
                                    $act_rrd->average=doubleval($maml_f[$rrd_dec]["AVERAGE"]);
                                    $act_rrd->minimum=doubleval($maml_f[$rrd_dec]["MIN"]);
                                    $act_rrd->last=doubleval($maml_f[$rrd_dec]["LAST"]);
                                    if (in_array("cdrawing",$var_keys)) {
                                        foreach (array("maximum","average","minimum","last") as $var_name) {
                                            $val=$act_rrd->$var_name;
                                            $vt_name="draw_{$var_name}";
                                            // shift to average
                                            if (in_array("reltoaverage",$var_keys) && $var_name != "average") $val-=$act_rrd->average;
                                            $outval=$act_rrd->get_val_str($val);
                                            echo "<td class=\"$var_name\">$outval <input type=checkbox name=\"".my_encode("{$rrd_dec}.d{$var_name}")."\" ";
                                            if ($act_rrd->$vt_name) echo " checked ";
                                            echo "/></td>\n";
                                        }
                                        $act_type=$act_rrd->unit;
                                        if ($act_type && !in_array($act_type,$vert_label)) $vert_label[]=$act_type;
                                        show_opt_list_simple($dt_name,$pos_types,$act_rrd->draw_type,"type");
                                        show_opt_list_simple($pri_name,$priority_list,$act_rrd->priority,"pri");
                                        echo "<td class=\"color\">#<input name=\"$col_name\" type=\"text\" size=\"8\" maxlength=\"6\" value=\"$act_rrd->color\"></td>";
                                        echo "<td class=\"color\">";
                                        echo "<select name=\"$colp_name\">";
                                        echo "<option value=\"keep\">keep</option>\n";
                                        foreach ($colors as $pd_col=>$col_val) echo "<option value=\"$pd_col\" >$pd_col</option>\n";
                                        echo "</select></td>\n";
                                        echo "<td style=\"background-color:#$act_rrd->color ; color:#000000 ; \">&nbsp;&nbsp;&nbsp;</td>\n";
                                        echo "</tr>\n";
                                        if ($configure_cevents) {
                                            echo "<tr><td class=\"blind\" colspan=\"12\"><table class=\"blind\">\n";
                                            echo "<tr><th class=\"ndev\">N/D</th>\n";
                                            echo "<th class=\"class\">Class</th>\n";
                                            echo "<th class=\"threshold\">Threshold</th>\n";
                                            echo "<th class=\"hysteresis\">Hysteresis</th>\n";
                                            echo "<th class=\"action\">Action</th>\n";
                                            echo "<th class=\"classes\">Classes</th>\n";
                                            echo "<th class=\"location\">Location</th>\n";
                                            echo "<th class=\"location\">Group</th>\n";
                                            echo "<th class=\"mail\">Mail</th>\n";
                                            echo "</tr>\n";
                                            foreach ($act_rrd->events as $ev_idx=>$ev_stuff) {
                                                $eidx="{$act_rrd->rrd_data_idx}_${ev_idx}";
                                                echo "<tr>";
                                                echo "<td class=\"del\" rowspan=\"2\"><input type=hidden name=\"ncc_set_$eidx\" value=\"set\"/><input type=checkbox name=\"ncc_del_$eidx\"/></td>\n";
                                                show_opt_list2("ncc_thc_$eidx",$all_threshold_classes,$ev_stuff->threshold_class,"class");
                                                echo "<td class=\"threshold\"><input name=\"ncc_th_$eidx\" size=\"10\" maxlength=\"15\" value=\"$ev_stuff->threshold\" /></td>\n";
                                                echo "<td class=\"hysteresis\"><input name=\"ncc_hys_$eidx\" size=\"10\" maxlength=\"15\" value=\"$ev_stuff->hysteresis\" /></td>\n";
                                                echo "<td class=\"action\"><select name=\"ncc_ce_$eidx\">";
                                                foreach ($all_cluster_events as $idx=>$stuff) {
                                                    echo "<option value=\"$idx\" ";
                                                    if ($ev_stuff->cluster_event==$idx) echo " selected ";
                                                    echo ">$stuff->name</option>\n";
                                                }
                                                echo "</select></td>\n";
                                                echo "<td class=\"classes\"><select name=\"ncc_dc_$eidx\" >";
                                                foreach ($all_device_classes as $idx=>$stuff) {
                                                    if ($idx) {
                                                        echo "<option value=\"$idx\" ";
                                                        if ($ev_stuff->device_class == $idx) echo " selected ";
                                                        echo ">$stuff->classname ($stuff->priority)</option>\n";
                                                    }
                                                }
                                                echo "</td>\n";
                                                echo "<td class=\"location\" rowspan=\"2\"><select name=\"ncc_dl_{$eidx}[]\" multiple size=\"3\" >";
                                                foreach ($all_device_locations as $idx=>$stuff) {
                                                    if ($idx) {
                                                        echo "<option value=\"$idx\" ";
                                                        if (in_array($idx,$ev_stuff->device_locations)) echo " selected ";
                                                        echo ">$stuff->location</option>\n";
                                                    }
                                                }
                                                echo "</select></td>\n";
                                                echo "<td class=\"location\" rowspan=\"2\"><select name=\"ncc_dg_{$eidx}[]\" multiple size=\"3\" >";
                                                foreach ($all_device_groups as $idx=>$stuff) {
                                                    if ($idx) {
                                                        echo "<option value=\"$idx\" ";
                                                        if (in_array($idx,$ev_stuff->device_groups)) echo " selected ";
                                                        echo ">$stuff->name</option>\n";
                                                    }
                                                }
                                                echo "</select></td>\n";
                                                echo "<td class=\"mail\" rowspan=\"2\">";
                                                if ($mail_users) {
                                                    echo "<select name=\"ncc_mail_{$eidx}[]\" multiple size=\"3\">";
                                                    foreach ($mail_users as $u_idx=>$u_stuff) {
                                                        echo "<option value=\"$u_idx\" ";
                                                        if (in_array($u_idx,$ev_stuff->mail_users)) echo " selected ";
                                                        echo ">$u_stuff->login (";
                                                        if ($u_stuff->mailcount) {
                                                            echo $u_stuff->mailcount;
                                                        } else {
                                                            echo "-";
                                                        }
                                                        echo ") $u_stuff->useremail</option>\n";
                                                    }
                                                    echo "</select>";
                                                } else {
                                                    echo "no valid users found";
                                                }
                                                echo "</td>\n";
                                                echo "</tr>\n";
                                                // get affected machines (class/location-basesd)
                                                $mres=query("SELECT d.name FROM device d, ccl_dloc_con dc, device_class cl, ccl_dgroup_con dg WHERE d.device_location=dc.device_location AND d.device_group=dg.device_group AND dc.ccl_event=$ev_idx AND dg.ccl_event=$ev_idx AND d.device_class=cl.device_class_idx AND cl.priority <= {$all_device_classes[$ev_stuff->device_class]->priority}");
                                                $h_list=array();
                                                while ($mfr=mysql_fetch_object($mres)) $h_list[]=$mfr->name;
                                                echo "<tr><td class=\"hostlist\" colspan=\"5\" >";
                                                if (count($h_list)) {
                                                    echo "Devicelist: ".optimize_hostlist($h_list);
                                                } else {
                                                    echo "No Devices affected";
                                                }
                                                echo "</td></tr>\n";
                                            }
                                            echo "<tr>";
                                            $rrd_idx=$act_rrd->rrd_data_idx;
                                            echo "<td class=\"ndev\"><input type=checkbox name=\"ncc_new_$rrd_idx\"/></td>\n";
                                            echo "<td class=\"class\"><select name=\"ncc_thc_$rrd_idx\">";
                                            foreach ($all_threshold_classes as $idx=>$stuff) {
                                                echo "<option value=\"$idx\">$stuff</option>\n";
                                            }
                                            echo "</select></td>\n";
                                            echo "<td class=\"threshold\"><input name=\"ncc_th_$rrd_idx\" size=\"10\" maxlength=\"15\" value=\"2.0\" /></td>\n";
                                            echo "<td class=\"hysteresis\"><input name=\"ncc_hys_$rrd_idx\" size=\"10\" maxlength=\"15\" value=\"0.5\" /></td>\n";
                                            echo "<td class=\"action\"><select name=\"ncc_ce_$rrd_idx\">";
                                            foreach ($all_cluster_events as $idx=>$stuff) {
                                                echo "<option value=\"$idx\">$stuff->name</option>\n";
                                            }
                                            echo "</select></td>\n";
                                            echo "<td class=\"classes\"><select name=\"ncc_dc_$rrd_idx\" >";
                                            foreach ($all_device_classes as $idx=>$stuff) {
                                                if ($idx) echo "<option value=\"$idx\">$stuff->classname ($stuff->priority)</option>\n";
                                            }
                                            echo "</td>\n";
                                            echo "<td class=\"location\"><select name=\"ncc_dl_{$rrd_idx}[]\" multiple size=\"3\" >";
                                            foreach ($all_device_locations as $idx=>$stuff) {
                                                if ($idx) echo "<option value=\"$idx\">$stuff->location</option>\n";
                                            }
                                            echo "</select></td>\n";
                                            echo "<td class=\"location\"><select name=\"ncc_dg_{$rrd_idx}[]\" multiple size=\"3\" >";
                                            foreach ($all_device_groups as $idx=>$stuff) {
                                                if ($idx) echo "<option value=\"$idx\">$stuff->name</option>\n";
                                            }
                                            echo "</select></td>\n";
                                            echo "<td class=\"mail\">";
                                            if ($mail_users) {
                                                echo "<select name=\"ncc_mail_{$rrd_idx}[]\" multiple size=\"3\">";
                                                foreach ($mail_users as $u_idx=>$u_stuff) {
                                                    echo "<option value=\"$u_idx\">$u_stuff->login (";
                                                    if ($u_stuff->mailcount) {
                                                        echo $u_stuff->mailcount;
                                                    } else {
                                                        echo "-";
                                                    }
                                                    echo ") $u_stuff->useremail</option>\n";
                                                }
                                                echo "</select>";
                                            } else {
                                                echo "no valid users found";
                                            }
                                            echo "</td></tr>\n";
                                            //>Device_Class</td><td>Threshold</td><td>Class</td></tr>\n";
                                            echo "</table></td></tr>\n";
                                        }
                                    }
                                }
                                echo "</table></div>\n";
                                if ($write_hidden) {
                                    $write_hidden=0;
                                    hidden_sid();
                                    echo $hiddentime;
                                    echo $hiddensize;
                                    echo $hiddencompose;
                                    echo $hiddenmach;
                                    echo $hiddenrrd;
                                    echo $hiddengp;
                                    echo $hiddenyas;
                                    echo $hidden_tot_mach;
                                }
                                echo "<div class=\"center\">";
                                $pngdir=get_root_dir()."/rrd-pngs";
                                $validx=0;
                                $tot_show=0;
                                $pri_list=array();
                                foreach ($actrrd_dec as $rrd_dec) {
                                    $act_rrd=&$rrd_list[$rrd_dec];
                                    $base=$act_rrd->get_base();
                                    if (!in_array($act_rrd->priority,$pri_list)) $pri_list[]=$act_rrd->priority;
                                }
                                sort ($pri_list);
                                // generate drawing order
                                $rrd_draw_order=array();
                                foreach ($pri_list as $draw_pri) {
                                    foreach ($pos_types as $act_type) {
                                        foreach ($actrrd_dec as $rrd_dec) {
                                            $act_rrd=&$rrd_list[$rrd_dec];
                                            if ($act_rrd->draw_type==$act_type && $act_rrd->priority==$draw_pri) {
                                                $rrd_draw_order[]=$rrd_dec;
                                            }
                                        }
                                    }
                                }
                                // 
                                $cce_str="";
                                $act_h_col="cccccc";
                                if (in_array("dccevents",$var_keys)) {
                                    $ev_idx_list=array();
                                    $leg_f=array();
                                    foreach ($rrd_draw_order as $rrd_dec) {
                                        $act_rrd=&$rrd_list[$rrd_dec];
                                        foreach ($act_rrd->events as $ev_idx=>$ev_stuff) {
                                            $ev_idx_list[]="cel.ccl_event=$ev_idx";
                                            $leg_f[]=array("val"=>$ev_stuff->threshold-($ev_stuff->hysteresis/2.),"color"=>"ffffff");
                                            $leg_f[]=array("val"=>$ev_stuff->threshold+($ev_stuff->hysteresis/2.),"color"=>$act_h_col);
                                        }
                                    }
                                    if (!count($ev_idx_list)) $ev_idx_list=array("1");
                                    $mres=query("SELECT cel.*,UNIX_TIMESTAMP(cel.date) AS ts FROM ccl_event_log cel WHERE (".implode(" OR ",$ev_idx_list).") OR cel.device=$mach->device_idx");
                                    while ($mfr=mysql_fetch_object($mres)) {
                                        $leg_str="VRULE:{$mfr->ts}#{$all_cluster_events[$mfr->cluster_event]->color}";
                                        $ld_written = 0;
                                        if (!$all_cluster_events[$mfr->cluster_event]->legend_used) {
                                            $all_cluster_events[$mfr->cluster_event]->legend_used=1;
                                            $leg_str.=":{$all_cluster_events[$mfr->cluster_event]->description}";
                                            $ld_written = 1;
                                        }
                                        if ($ld_written) $act_rrd->legends[]=" '$leg_str\\\j' ";
                                    }
                                    usort($leg_f,"leg_f_sort");
                                    $legidx=0;
                                    foreach ($leg_f as $stuff) {
                                        $val=$stuff["val"];
                                        $col=$stuff["color"];
                                        if (!$legidx++) {
                                            $cce_str.=" CDEF:vl$legidx=v0,UN,0,*,$val,+ AREA:vl$legidx#".color($col);
                                        } else {
                                            $cce_str.=" CDEF:vl$legidx=v0,UN,0,*,".strval($val-$last_y).",+ STACK:vl$legidx#".color($col);
                                        }
                                        $last_y=$val;
                                    }
                                    foreach ($rrd_draw_order as $rrd_dec) {
                                        $act_rrd=&$rrd_list[$rrd_dec];
                                        foreach ($act_rrd->events as $ev_idx=>$ev_stuff) {
                                            $act_rrd->legends[]=" HRULE:{$ev_stuff->threshold}#".color($act_rrd->color).":'  CCEvent at $ev_stuff->threshold ($ev_stuff->hysteresis)'\\\j";
                                        }
                                    }
                                }
                                // draw loop
                                $varstr="";
                                $defstr="";
                                $last_draw_type="NONE";
                                foreach ($rrd_draw_order as $rrd_dec) {
                                    $act_rrd=&$rrd_list[$rrd_dec];
                                    $show_mam=1;
                                    foreach (array(array("MAX","maximum",1),array("AVERAGE","average",0),array("MIN","minimum",-1)) as $act_type_f) {
                                        list($rrd_type,$show_type,$col_dif)=$act_type_f;
                                        $vt="rrd_".strtolower($rrd_type);
                                        if ($act_rrd->$vt) {
                                            if ($show_sthg == "tot") {
                                                $idx=0;
                                                foreach ($act_rrd->mach_list as $mname=>$rrd_stuff) {
                                                    if (!in_array($mname,$act_rrd->invalid_machs)) {
                                                        list($rrd_index,$rrd_fname)=$rrd_stuff;
                                                        $varstr.=" DEF:ds{$validx}_$idx={$rrddir}/{$machine_list[$mname]->filename}:v$rrd_index:$rrd_type ";
                                                        $idx++;
                                                    }
                                                }
                                                if ($idx) {
                                                    $tot_show+=$idx;
                                                    $varstr.=" CDEF:v$validx=ds{$validx}_".implode("$process_str,ds${validx}_",range(0,$idx-1)).$process_str;
                                                    if ($idx > 1) $varstr.=str_repeat(",$compose_str",$idx-1);
                                                    if ($do_mean_value) $varstr.=",$idx,/";
                                                    $vname="v";
                                                } else {
                                                    $vname="-";
                                                }
                                            } else {
                                                $tot_show+=1;
                                                $varstr.=" DEF:v$validx={$rrddir}/{$mach->filename}:v{$mach->index[$rrd_dec]}:$rrd_type";
                                                $vname="v";
                                            }
                                            if ($vname != "-") {
                                            if (in_array("reltoaverage",$var_keys)) {
                                                $mean_val=$act_rrd->average;
                                                $defstr.=" CDEF:vc$validx=$vname$validx,{$act_rrd->average},-";
                                                $vname="vc";
                                            } else {
                                                $mean_val=0;
                                            }
                                            if ($act_rrd->factor != 1) {
                                                $defstr.=" CDEF:vs$validx=$vname$validx,{$act_rrd->factor},*";
                                                $vname="vs";
                                            }
                                            $mam_f=array();
                                            if ($show_mam) {
                                                if ($act_rrd->draw_maximum) {
                                                    $defstr.=" HRULE:".strval(($act_rrd->maximum-$mean_val)*$act_rrd->factor)."#".color($act_rrd->color);
                                                    $mam_f[]="max";
                                                }
                                                if ($act_rrd->draw_average) {
                                                    $defstr.=" HRULE:".strval(($act_rrd->average-$mean_val)*$act_rrd->factor)."#".color($act_rrd->color);
                                                    $mam_f[]="average";
                                                }
                                                if ($act_rrd->draw_minimum) {
                                                    $defstr.=" HRULE:".strval(($act_rrd->minimum-$mean_val)*$act_rrd->factor)."#".color($act_rrd->color);
                                                    $mam_f[]="min";
                                                }
                                                if ($act_rrd->draw_last) {
                                                    $defstr.=" HRULE:".strval(($act_rrd->last-$mean_val)*$act_rrd->factor)."#".color($act_rrd->color);
                                                    $mam_f[]="last";
                                                }
                                            }
                                            $act_col=col_change($act_rrd->color,$col_dif*64);
                                            if ($act_col == $act_rrd->color) $act_col=col_change($act_rrd->color,-128*$col_dif);
                                            $draw_type=$act_rrd->draw_type;
                                            //echo $last_draw_type,$draw_type,$act_rrd->descr,"<br>";
                                            if ($last_draw_type == "NONE" && $act_rrd->draw_type == "STACK") $draw_type="AREA";
                                            $defstr.=" $draw_type:$vname$validx#".color($act_col).":'$show_type of ";
                                            $last_draw_type=$draw_type;
                                            if ($show_sthg == "tot") {
                                                $defstr.=$act_rrd->info;
                                            } else {
                                                $defstr.=$mach->info[$rrd_dec];
                                            }
                                            if (sizeof($mam_f)) $defstr.=" (with ".implode("/",$mam_f).")";
                                            $defstr.="'\\\j";
                                            if ($act_rrd->legends) {
                                                $defstr.=" ".implode(" ",$act_rrd->legends);
                                                unset($act_rrd->legends);
                                            }
                                            $show_mam=0;
                                            $validx++;
                                            }
                                        }
                                    }
                                }
                                $defstr="$varstr $cce_str $defstr";
                                $png_name="rrd_{$sys_config['session_user']}_$image_idx.png";
				$sec="/usr/bin/rrdtool 2>&1 graph $pngdir/$png_name -E -w {$x_sizes[$act_x_size_idx]['x']} -h {$y_sizes[$act_y_size_idx]['y']} -s $time_start -e $time_end --step 1 ";
                                if (in_array("noyas",$var_keys)) {
                                    $sec.=" -l $y_start -u $y_end -r ";
                                }
                                $title="Showing ".strval(sizeof($actrrd_dec))." ".get_plural("dataset",$num_rrd);
                                if ($show_sthg == "tot") {
                                    $title.=" of $num_machs ".get_plural("machine",$num_machs);
                                } else {
                                    $title.=" for ".$mach->get_name();
                                }
                                $title.=" ({$timeframes[$act_timeframe_idx]['name']}, size {$x_sizes[$act_x_size_idx]['x']} x {$y_sizes[$act_y_size_idx]['y']})";
                                $sec.="-t '$title' ";
                                if (sizeof($vert_label)) $sec.="-v '".implode(", ",$vert_label)."' ";
                                if (in_array("yzero",$var_keys)) $sec.="-l 0 ";
                                if (in_array("rigid",$var_keys)) $sec.="-r ";
                                if (in_array("altscale",$var_keys)) $sec.="--alt-autoscale ";
                                if (in_array("altygrid",$var_keys)) $sec.="--alt-y-grid ";
                                if (isset($base)) {
                                    if ($base != 1) $sec.="-b $base ";
                                }
                                if (in_array("yzrule",$var_keys)) $sec.="HRULE:0#".color("000000");
                                if (in_array("drawtmarks",$var_keys)) {
                                    // calculate the ruler positions
                                    // act_time is still valid from above
                                    $ruler_str="";
                                    $difftime=$timeframes[$act_timeframe_idx]["slice"];
                                    $ruler_type=$act_timeframe_idx+1;
                                    if ($ruler_type) {
                                        $act_ta=getdate($time_end);
                                        switch ($ruler_type) {
                                        case 1:
                                            $act_ta["minutes"]=intval(15*intval($act_ta["minutes"]/15));
                                            $vrule_time=mktime($act_ta["hours"],$act_ta["minutes"],0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 2:
                                            $vrule_time=mktime($act_ta["hours"],0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 3:
                                            $vrule_time=mktime($act_ta["hours"],0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 4:
                                            $act_ta["hours"]=intval(2*intval($act_ta["hours"]/2));
                                            $vrule_time=mktime($act_ta["hours"],0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 5:
                                            $act_ta["hours"]=intval(12*intval($act_ta["hours"]/12));
                                            $vrule_time=mktime($act_ta["hours"],0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 6:
                                            $vrule_time=mktime(0,0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 7:
                                            $vrule_time=mktime(0,0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"]);
                                            break;
                                        case 8:
                                            $vrule_time=mktime(0,0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"])-60*60*24*$act_ta["wday"];
                                            break;
                                        case 9:
                                            $vrule_time=mktime(0,0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"])-60*60*24*$act_ta["wday"];
                                            break;
                                        case 10:
                                            $vrule_time=mktime(0,0,0,$act_ta["mon"],$act_ta["mday"],$act_ta["year"])-60*60*24*$act_ta["wday"];
                                            break;
                                        }
                                        if ($difftime) {
                                            while ($vrule_time >= $time_start && $vrule_time <= $time_end) {
                                                $ruler_str.=" VRULE:$vrule_time#ff0000";
                                                $vrule_time-=$difftime;
                                            }
                                        } else {
                                            $ruler_str=" VRULE:$vrule_time#ff0000";
                                        }
                                    }
                                    $sec.=$ruler_str;
                                }
                                $sec.=$defstr;
                                if (in_array("dboots",$var_keys)) {
                                    $node_log_source=get_log_source("node");
                                    $node_log_source=$node_log_source->log_source_idx;
                                    $mres=query("SELECT dl.user,UNIX_TIMESTAMP(dl.date) AS ts FROM devicelog dl, device d WHERE d.name='$mach->name' AND d.device_idx=dl.device AND dl.user AND dl.log_source=$node_log_source AND dl.date > ".date("YmdHis",$time_start));
                                    if (mysql_num_rows($mres)) {
                                        $tu_array=array(1=>array("00fff0","boot maintenance",array()),2=>array("0f0ff0","boot other",array()),3=>array("ff00f0","reset",array()),4=>array("0ff080","halt",array()),5=>array("ff8080","got ip address",array()));
                                        while ($mfr=mysql_fetch_object($mres)) $tu_array[$mfr->user][2][]=$mfr->ts;
                                        foreach ($tu_array as $idx=>$stuff) {
                                            if (count($stuff[2])) {
                                                $first=0;
                                                foreach ($stuff[2] as $time) {
                                                    $sec.=" VRULE:$time#{$stuff[0]}";
                                                    if (!$first++) $sec.=":'{$stuff[1]} (".get_plural("event",count($stuff[2]),1).")'";
                                                }
                                            }
                                        }
                                    }
                                }
                                if (in_array("noxgrid",$var_keys)) $sec.=" -x none";
                                if (in_array("noygrid",$var_keys)) $sec.=" -y none";
                                if ($tot_show) {
                                    $ret_array=array();
                                    $ret=exec($sec,$ret_array);
                                    if (preg_match("/^\d+x\d+$/",$ret)) {
                                        echo "<img alt=\"Graph\" src=\"/rrd-pngs/$png_name\">";
                                    } else {
                                        message("Cannot create graph: $ret_array[0] (possibly invalid RRD-Class ?)",$type=1);
                                    }
                                } else {
                                    message("No valid data found!");
                                }
                                echo "</div>";
                            }
                        }
                        if (in_array("cdrawing",$var_keys)) {
                            echo "<div class=\"center\"><input type=submit value=\"submit\" /></div>\n";
                            echo "</form>";
                        }
                    }
                }
            }
        } else {
            message ("No devices with associated RRDs found");
        }
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
