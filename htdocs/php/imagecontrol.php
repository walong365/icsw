<?php
//-*ics*- ,CAP,name:'ic',descr:'Image control',enabled:1,defvalue:0,scriptname:'/php/imagecontrol.php',left_string:'Image control',right_string:'Modify the Cluster Images',capability_group_name:'conf',pri:30
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
function get_image_string($im_t,$what=0) {
    $ret_str="$im_t->name";
    if ($what > 0) $ret_str.=", version $im_t->version.$im_t->release";
    if ($what > 1) $ret_str.=", build $im_t->builds";
    if ($what > 2) $ret_str.=" (last build at $im_t->bdate on $im_t->build_machine)";
    #return ("$im_t->name, version $im_t->version.$im_t->release (build $im_t->builds, last build at $im_t->bdate on $im_t->build_machine [$im_t->source])");
    return $ret_str;
}
function add_hc(&$g_hc,$group) {
    //echo $group;
    if (!in_array($group,array_keys($g_hc))) $g_hc[$group]=array();
}
function show_size($sz) {
    if ($sz < 2048) {
        $str="Byte";
    } else if ($sz < 2048*1024) {
        $sz=intval($sz/1024);
        $str="kB";
    } else {
        $sz=intval($sz/(1024*1024));
        $str="MB";
    }
    $ret_str="$sz ".get_plural($str,$sz);
    return $ret_str;
}
require_once "config.php";
require_once "mysql.php";
require_once "htmltools.php";
require_once "tools.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
    errorpage("No configfile.");
} else if (! $sys_config["ic_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);

    // suppress array
    $sup_array=array("arch"=>array("Architecture",0),"ven"=>array("Vendor",0),"dist"=>array("Distribution",0),"size"=>array("Size",0),"group"=>array("Group",0),
                     "itime"=>array("Install time",0),"sum"=>array("Summary",0));
    // parse the image selection
    $act_image="";
    if (in_array("image",$varkeys)) {
        $act_image=$vars["image"];
    }
    $sort_type="n";
    if (in_array("sorttype",$varkeys)) {
        $sort_type=$vars["sorttype"];
    }
    htmlhead();
    clusterhead($sys_config,"Image control page",$style="formate.css",
                array("td.icspacer"=>array("background-color:#ccddff","text-align:center"),
                      "th.icname"=>array("background-color:#eeeeff","text-align:left"),
                      "td.icname"=>array("background-color:#ddddee","text-align:left"),
                      "th.icversion"=>array("background-color:#eeffee","text-align:right"),
                      "td.icversion"=>array("background-color:#ddeedd","text-align:right"),
                      "th.icrelease"=>array("background-color:#eeffe0","text-align:left"),
                      "td.icrelease"=>array("background-color:#ddeed0","text-align:left"),
                      "th.icarch"=>array("background-color:#ffffe0"),
                      "td.icarch"=>array("background-color:#eeeed0","text-align:center"),
                      "th.icvendor"=>array("background-color:#d0ffe0"),
                      "td.icvendor"=>array("background-color:#c0eed0","text-align:center"),
                      "th.icdistribution"=>array("background-color:#ffdde0"),
                      "td.icdistribution"=>array("background-color:#eeccd0","text-align:center"),
                      "th.icsize"=>array("background-color:#ffeef0","text-align:right"),
                      "td.icsize"=>array("background-color:#eedde0","text-align:right"),
                      "th.icitime"=>array("background-color:#ddeef0"),
                      "td.icitime"=>array("background-color:#ccdde0","text-align:right"),
                      "th.icgroup"=>array("background-color:#ddffe0","text-align:left"),
                      "td.icgroup"=>array("background-color:#cceed0","text-align:left"),
                      "th.icsummary"=>array("background-color:#dddde0","text-align:left"),
                      "td.icsummary"=>array("background-color:#ccccd0","text-align:left")
                      )
                );
    clusterbody($sys_config,"Image control",array(),array("conf"));
  
    $ucl=usercaps($sys_db_con);
    if ($ucl["ic"]) {
        // sort types
        $sort_types=array("n"=>"by Name","g"=>"by Group","t"=>"by install time","s"=>"by size","v"=>"by version","r"=>"by release");
        // simple protocol
        $mres=query("SELECT i.image_idx,i.name,i.version,i.release,i.builds,i.source,i.build_machine,i.size_string,DATE_FORMAT(i.date,'%e. %b %Y, %H:%i:%s') as bdate FROM image i");
        $images=array();
        while ($mfr=mysql_fetch_object($mres)) {
            $mr2=query("SELECT pi.pi_connection_idx FROM pi_connection pi WHERE pi.image=$mfr->image_idx");
            $mfr->num_packages=mysql_affected_rows();
            $images[$mfr->name]=$mfr;
        }
        if (count($images)) {
            message("Please select image:");
            echo "<form action=\"{$sys_config['script_name']}?".write_sid()."\" method=post >";
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\"><tr><td>";
            echo "<select name=\"image\" size=3>";
            foreach ($images as $name=>$image) {
                echo "<option value=\"$name\"";
                if ($name == $act_image) echo " selected ";
                echo ">".get_image_string($image,$what=1);
            }
            echo "</select>\n";
            echo "</td><td>";
            echo "<select name=\"sorttype\">";
            foreach ($sort_types as $sst=>$sstr) {
                echo "<option value=\"$sst\"";
                if ($sst == $sort_type) echo " selected ";
                echo ">$sstr";
            }
            echo "</select>";
            echo "</tr></table>\n";
            echo "<table class=\"simplesmall\"><tr><td>Suppress display of</td>";
            $sup_ref_str="";
            foreach ($sup_array as $short=>$dlist) {
                list($long,$set)=$dlist;
                echo "<td>$long</td><td><input type=\"checkbox\" name=\"$short\" ";
                if (isset($vars[$short])) {
                    echo " checked ";
                    $sup_array[$short][1]=1;
                }
                echo "/>, </td>\n";
            }
            echo "<td><input type=submit value=\"select\" /></td>";
            echo "</tr></table>\n";
            echo "</div>\n";
            echo "</form>\n";
            if ($act_image) {
                $image=&$images[$act_image];
                // calculate image size from size_string
                $rep_size=0;
                $size_parts=explode(";",$image->size_string);
                foreach ($size_parts as $size_p) {
                    if (preg_match("/^\d+$/",$size_p)) $rep_size+=intval($size_p);
                }
                message("Showing info about image ".get_image_string($image,$what=4),$type=1);
                // query architecture
                $mres=query("SELECT * FROM architecture");
                $architecture=array();
                while ($mfr=mysql_fetch_object($mres)) $architecture[$mfr->architecture_idx]=$mfr;
                // query distribution
                $mres=query("SELECT * FROM distribution");
                $distribution=array();
                while ($mfr=mysql_fetch_object($mres)) $distribution[$mfr->distribution_idx]=$mfr;
                // query vendor
                $mres=query("SELECT * FROM vendor");
                $vendor=array();
                while ($mfr=mysql_fetch_object($mres)) $vendor[$mfr->vendor_idx]=$mfr;
                $mres=query("SELECT p.distribution,p.vendor,DATE_FORMAT(FROM_UNIXTIME(pi.install_time),'%e. %b %Y, %H:%i:%s') AS install_date,pi.install_time,p.name,p.version,p.release,p.architecture,p.size,p.pgroup,p.summary FROM package p, pi_connection pi WHERE pi.package=p.package_idx AND pi.image=$image->image_idx");
                $g_types=array();
                $g_hierarchy=array();
                $packages=array();
                $sort_array=array();
                $act_architectures=array();
                $act_vendors=array();
                $tot_size=0;
                $p_idx=0;
                while ($mfr=mysql_fetch_object($mres)) {
                    $p_idx++;
                    if (in_array($mfr->pgroup,array_keys($g_types))) {
                        $g_types[$mfr->pgroup]++;
                    } else {
                        $g_types[$mfr->pgroup]=1;
                    }
                    if (!in_array($mfr->architecture,$act_architectures)) $act_architectures[]=$mfr->architecture;
                    if (!in_array($mfr->vendor,$act_vendors)) $act_vendors[]=$mfr->vendor;
                    $mfr->groups=explode("/",$mfr->pgroup);
                    $mfr->num_groups=count($mfr->groups);
                    $mfr->shown=1;
                    if (count($mfr->groups) > 0) add_hc($g_hierarchy,$mfr->groups[0]);
                    if (count($mfr->groups) > 1) add_hc($g_hierarchy[$mfr->groups[0]],$mfr->groups[1]);
                    if (count($mfr->groups) > 2) add_hc($g_hierarchy[$mfr->groups[0]][$mfr->groups[1]],$mfr->groups[2]);
                    if (count($mfr->groups) > 3) add_hc($g_hierarchy[$mfr->groups[0]][$mfr->groups[1]][$mfr->groups[2]],$mfr->groups[3]);
                    if (count($mfr->groups) > 4) add_hc($g_hierarchy[$mfr->groups[0]][$mfr->groups[1]][$mfr->groups[2]][$mfr->groups[3]],$mfr->groups[4]);
                    $tot_size+=$mfr->size;
                    $packages[$p_idx]=$mfr;
                    if ($sort_type == "t") {
                        $sort_array[$p_idx]=$mfr->install_time;
                    } else if ($sort_type == "s") {
                        $sort_array[$p_idx]=$mfr->size;
                    } else if ($sort_type == "v") {
                        $sort_array[$p_idx]=$mfr->version;
                    } else if ($sort_type == "r") {
                        $sort_array[$p_idx]=$mfr->release;
                    } else {
                        $sort_array[$p_idx]=$mfr->name;
                    }
                }
                $num_architectures=count($act_architectures);
                $num_vendors=count($act_vendors);
                message("Consists of $image->num_packages packages from $num_vendors ".get_plural("vendor",$num_vendors)." ( $num_architectures ".get_plural("architecture",$num_architectures)."), ".
                        "total size is ".show_size($tot_size)." vs. ".show_size($rep_size*1024),$type=2);
                if ($sort_type == "g") {
                    $gm_array=array();
                    foreach (array_keys($g_hierarchy) as $hl0) {
                        $gm_array[]=array($hl0,"/^$hl0$/");
                        foreach (array_keys($g_hierarchy[$hl0]) as $hl1) {
                            $gm_array[]=array("$hl0/$hl1","/^$hl0\/$hl1.*$/");
                        }
                    }
                    sort($gm_array);
                } else {
                    $gm_array=array(array("","/^.*$/"));
                }
                //$p_names=array_keys($packages);
                asort($sort_array);
                echo "<table class=\"normal\">";
                echo "<tr><th class=\"icname\">Name</th>";
                $num_cols=3;
                echo "<th class=\"icversion\">Version</th>";
                echo "<th class=\"icrelease\">Release</th>";
                if (!$sup_array["arch"][1]) {
                    echo "<th class=\"icarch\">Arch</th>";
                    $num_cols++;
                }
                if (!$sup_array["ven"][1]) {
                    echo "<th class=\"icvendor\">Vendor</th>";
                    $num_cols++;
                }
                if (!$sup_array["dist"][1]) {
                    echo "<th class=\"icdistribution\">Distribution</th>";
                    $num_cols++;
                }
                if (!$sup_array["size"][1]) {
                    echo "<th class=\"icsize\">Size</th>";
                    $num_cols++;
                }
                if (!$sup_array["group"][1]) {
                    echo "<th class=\"icgroup\">Group</th>";
                    $num_cols++;
                }
                if (!$sup_array["itime"][1]) {
                    echo "<th class=\"icitime\">Inst.Time</th>";
                    $num_cols++;
                }
                if (!$sup_array["sum"][1]) {
                    echo "<th class=\"icsummary\">Summary</th>";
                    $num_cols++;
                }
                echo "</tr>\n";
                $num_s=0;
                foreach ($gm_array as $tm) {
                    list($tm_str,$tm_re)=$tm;
                    $sm_line=1;
                    foreach ($sort_array as $idx=>$wurscht) {
                        $act_p=&$packages[$idx];
                        $show=$act_p->shown;
                        if (!preg_match($tm_re,$act_p->pgroup)) $show=0;
                        if ($show) {
                            if ($sm_line) {
                                if (strlen($tm_str)) echo "<tr><td colspan=\"$num_cols\" class=\"icspacer\">$tm_str</td></tr>\n";
                                $sm_line=0;
                            }
                            $act_p->shown=0;
                            $num_s++;
                            echo "<tr>";
                            echo "<td class=\"icname\">$act_p->name</td>";
                            echo "<td class=\"icversion\">$act_p->version</td>";
                            echo "<td class=\"icrelease\">$act_p->release</td>";
                            if (!$sup_array["arch"][1]) echo "<td class=\"icarch\">".$architecture[$act_p->architecture]->architecture."</td>";
                            if (!$sup_array["ven"][1]) echo "<td class=\"icvendor\">".$vendor[$act_p->vendor]->vendor."</td>";
                            if (!$sup_array["dist"][1]) echo "<td class=\"icdistribution\">".$distribution[$act_p->distribution]->distribution."</td>";
                            if (!$sup_array["size"][1]) echo "<td class=\"icsize\">".show_size($act_p->size)."</td>";
                            if (!$sup_array["group"][1]) echo "<td class=\"icgroup\">$act_p->pgroup</td>";
                            if (!$sup_array["itime"][1]) echo "<td class=\"icitime\">$act_p->install_date</td>";
                            if (!$sup_array["sum"][1]) echo "<td class=\"icsummary\">$act_p->summary</td>";
                            echo "</tr>\n";
                        }
                    }
                }
                echo "</table>\n";
                if ($image->num_packages != $num_s) message("Internal error");
            }
        } else {
            message("No images found");
        }
    } else {
        message ("You are not allowed to access this page.");
    }
    writefooter($sys_config);
}
?>
