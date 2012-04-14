<?php
//-*ics*- ,CAP,name:'nbs',descr:'Netbotz show',enabled:1,defvalue:0,scriptname:'/php/netbotzshow.php',left_string:'Netbotz pictures',right_string:'Shows the actual images of the Netbotzes',capability_group_name:'info',pri:40
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
class netbotz{
    var $name,$idx,$ip,$picture,$pic_f;
    function netbotz($name,$idx) {
        $this->name=$name;
        $this->idx=$idx;
    }
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["nbs_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    $varkeys=array_keys($vars);

    // check dtype
#$dtypes=array("config");
#$dtype=$dtypes[0];
#if (in_array("dtype",$varkeys)) $dtype=$vars["dtype"];
#$hiddendtype="<input type=hidden name=\"dtype\" value=\"$dtype\" />";

    // parse the machine selection
    htmlhead();
    clusterhead($sys_config,"Netbotz picture page",$style="formate.css",
                array("td.nbpictd"=>array("color:#000000","background-color:#ddeeff","text-align:center")
                      )
                );
    clusterbody($sys_config,"Netbotz picture",array(),array("info"));
  
    $ucl=usercaps($sys_db_con);
    if ($ucl["nbs"]) {
        // simple protocol
        $hcproto=array();
        $netbotzes=array();
        if (isset($vars["selnb"])) {
            $selnb=$vars["selnb"];
        } else {
            $selnb=array();
        }
        if (isset($vars["stride"])) {
            $stride=$vars["stride"];
        } else {
            $stride=60;
        }
        $max_numpics=15;
        if (isset($vars["numpics"])) {
            $numpics=min($vars["numpics"],$max_numpics);
        } else {
            $numpics=3;
        }
        $pfix=get_root_dir();
        $act_time=time();
        $first_time=$act_time-$numpics*$stride;
        $num_pics=0;
        $mres=query("SELECT d.name,d.device_idx,i.ip FROM device d, netdevice nd, netip i, device_type dt WHERE dt.identifier='NB' AND dt.device_type_idx=d.device_type AND nd.device=d.device_idx AND i.netdevice=nd.netdevice_idx");
        while ($mfr=mysql_fetch_object($mres)) {
            $netbotzes[$mfr->device_idx]=new netbotz($mfr->name,$mfr->device_idx);
            $actnb=&$netbotzes[$mfr->device_idx];
            $actnb->ip=$mfr->ip;
            $pic_f=array();
            $fname="/nb-pics/$mfr->ip/actual";
            if (is_file($pfix.$fname)) {
                $pic_f[$act_time]=$fname;
                $actnb->picture=$fname;
                $picdir=get_root_dir()."/nb-pics/$mfr->ip";
                $pic_ldir="/nb-pics/$mfr->ip";
                if (is_dir($picdir)) {
                    $picd=dir($picdir);
                    while ($ye=$picd->read()) {
                        if (preg_match("/^\d{4}$/",$ye)) {
                            $year_int=intval($ye);
                            $year_ltime=mktime(23,59,59,12,31,$year_int);
                            if ($year_ltime > $first_time) {
                                $ydirn="$picdir/$ye";
                                $ydir=dir($ydirn);
                                while ($me=$ydir->read()) {
                                    if (preg_match("/^\d{2}$/",$me)) {
                                        $month_int=intval($me);
                                        $month_ltime=mktime(23,59,59,$month_int,31,$year_int);
                                        if ($month_ltime > $first_time) {
                                            $mdirn="$ydirn/$me";
                                            $mdir=dir($mdirn);
                                            while ($de=$mdir->read()) {
                                                if (preg_match("/^\d{2}$/",$de)) {
                                                    $day_int=intval($de);
                                                    $day_ltime=mktime(23,59,59,$month_int,$day_int,$year_int);
                                                    if ($day_ltime > $first_time) {
                                                        $ddirn="$mdirn/$de";
                                                        $ddir=dir($ddirn);
                                                        while ($he=$ddir->read()) {
                                                            if (preg_match("/^\d{2}$/",$he)) {
                                                                $hour_int=intval($he);
                                                                $hour_ltime=mktime($hour_int,59,59,$month_int,$day_int,$year_int);
                                                                if ($hour_ltime > $first_time) {
                                                                    $hdirn="$ddirn/$he";
                                                                    $hdir=dir($hdirn);
                                                                    while ($te=$hdir->read()) {
                                                                        if (preg_match("/^(\d+)_(\d+)\.jpg$/",$te,$what)) {
                                                                            $min_int=intval($what[1]);
                                                                            $sec_int=intval($what[2]);
                                                                            $ts=mktime($hour_int,$min_int,$sec_int,$month_int,$day_int,$year_int);
                                                                            $pic_f[$ts]="$pic_ldir/$ye/$me/$de/$he/$te";
                                                                            $num_pics++;
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                //echo $num_pics."<br>";
                krsort($pic_f);
            } else {
                $actnb->picture="NONE";
            }
            $actnb->pic_f=$pic_f;
        }
        if (sizeof($netbotzes)) {
            $stride_array=array(array("1 minute",60),array("2 minutes",120),array("5 minutes",5*60),array("10 minutes",60*10),array("15 minutes",60*15),
                                array("30 minutes",60*30),array("1 hour",60*60),array("2 hours",2*60*60),array("4 hours",4*60*60),
                                array("5 hours",5*60*60),array("6 hours",6*60*60),array("12 hours",12*60*60),array("1 day",24*60*60));
            message ("Please select Netbotz and display parameters:");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=get>";
            hidden_sid();
            echo "<div class=\"center\">";
            echo "<table class=\"simple\"><tr>\n";
            echo "<td>Netbotz:</td><td><select name=\"selnb[]\" multiple=5>";
            foreach ($netbotzes as $netbotz) {
                echo "<option value=$netbotz->idx";
                if (in_array($netbotz->idx,$selnb)) echo " selected";
                echo ">$netbotz->name ($netbotz->ip)\n";
            }
            echo "</select>";
            echo "</td>";
            echo "<td>Stride:</td><td><select name=\"stride\">";
            foreach ($stride_array as $act_s) {
                list($info,$off)=$act_s;
                echo "<option value=$off";
                if ($stride == $off) echo " selected";
                echo ">$info\n";
            }
            echo "</select>";
            echo "</td>";
            echo "<td># of pictures:</td><td><select name=\"numpics\">";
            for ($i=1;$i<=$max_numpics;$i++) {
                echo "<option value=$i";
                if ($i == $numpics) echo " selected";
                echo ">$i\n";
            }
            echo "</select>";
            echo "</td>";
            echo "<td><input type=submit value=\"select\" /></td>";
            echo "</tr></table>\n";
            echo "</div></form>";
            if ($selnb) {
                foreach ($selnb as $act_sel) {
                    $act_nb=&$netbotzes[$act_sel];
                    if ($act_nb->picture == "NONE") {
                        message ("No pictures found for netbotz $act_nb->name");
                    } else {
                        message ("Showing $numpics pictures of netbotz $act_nb->name (from ".strftime("%e. %b %Y, %T",$act_time-$stride*($numpics-1))." to ".strftime("%e. %b %Y, %T",$act_time).")");
                        $max_num_rows=min(3,$numpics);
                        echo "<div class=\"center\"><table class=\"simplesmall\"><tr><td><table class=\"normal\">";
                        $num_rows=0;
                        $search_time=$act_time;
                        $last_show_ts="???";
                        $last_double=0;
                        for ($i=0;$i<$numpics;$i++) {
                            $first=1;
                            $found=0;
                            foreach ($act_nb->pic_f as $act_ts=>$act_pic) {
                                $act_diff=$search_time-$act_ts;
                                if ($first) {
                                    $first=0;
                                    if (!$act_diff) {
                                        $found=1;
                                        break;
                                    }
                                } else {
                                    //echo "$act_diff, $last_diff ; ";
                                    if ($act_diff*$last_diff <=0 or ($act_diff > 0 && $last_diff > 0)) {
                                        //echo "$ts : $act_diff , $last_diff";
                                        if (abs($act_diff) > abs($last_diff) and $last_ts != $last_show_ts) {
                                            $act_diff=$last_diff;
                                            $act_ts=$last_ts;
                                            $act_pic=$last_pic;
                                        }
                                        $found=1;
                                        break;
                                    }
                                }
                                $last_diff=$act_diff;
                                $last_pic=$act_pic;
                                $last_ts=$act_ts;
                            }
                            if (!$found) $last_double++;
                            //echo " ld: $last_double , ";
                            $search_time-=$stride;
                            if ($last_double > 1 && !$num_rows) break;
                            if (!$num_rows) echo "<tr>";
                            if ($last_double <= 1) {
                                $last_show_ts=$act_ts;
                                //echo $act_pic;
                                echo "<td class=\"nbpictd\">";
                                echo strftime("%T, %e. %b %Y",$act_ts)." ($act_diff)<br>";
                                echo "<img alt=\"$act_nb->name\" src=\"$act_pic\" >";
                                echo "</td>";
                                $num_rows++;
                                if ($num_rows == $max_num_rows) {
                                    echo "</tr>";
                                    $num_rows=0;
                                }
                            }
                        }
                        if ($num_rows) {
                            while ($num_rows++ != $max_num_rows) echo "<td class=\"nbpictd\">&nbsp;</td>";
                            echo "</tr>";
                        }
                        echo "</table></td></tr></table></div>";
                    }
                }
            } else {
                message ("No netbotz selected.");
            }
        } else {
            message("No netbotzes found.");
        }
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
