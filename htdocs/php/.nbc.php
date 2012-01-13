<?php
//-*ics*- ,CAP,name:'nbc',descr:'Netbotz configuration',enabled:1,defvalue:0,scriptname:'/php/netbotzconfig.php',left_string:'Netbotz config',right_string:'Configuration of the Netbotzes ;-)',capability_group_name:'conf',pri:-40
class netbotz{
    var $name,$idx,$ip,$locations,$events;
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
} else if (! $sys_config["nbc_en"] == 1) {
    errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
    errorpage("You are currently not logged in.");
} else {
    if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
    $varkeys=array_keys($vars);

    // check dtype
#$dtypes=array("config");
#$dtype=$dtypes[0];
#if (in_array("dtype",$varkeys)) $dtype=$vars["dtype"];
#$hiddendtype="<input type=hidden name=\"dtype\" value=\"$dtype\" />";

    // parse the machine selection
    htmlhead();
    clusterhead($sys_config,"Netbotz config page",$style="formate.css",
                array("th.nbdelnbc"=>array("background-color:#f2bbaa","text-align:center"),
                      "th.nbclass"=>array("background-color:#f2eeff","text-align:center"),
                      "th.nblubound"=>array("background-color:#f2ffee","text-align:center"),
                      "td.nbdelnbc"=>array("background-color:#e2d2d2","text-align:center"),
                      "td.nbclass"=>array("background-color:#eefff2","text-align:center"),
                      "td.nbclassl"=>array("background-color:#eefff2","text-align:left"),
                      "td.nbclassr"=>array("background-color:#eefff2","text-align:right"),
                      "td.nbeventl"=>array("background-color:#ddddff","text-align:left"),
                      "td.nbeventr"=>array("background-color:#ddddff","text-align:right"),
                      "td.nbhostl"=>array("background-color:#eeeef2","text-align:left")
                      )
                );
    clusterbody($sys_config,"Netbotz config");
  
    $ucl=usercaps($sys_db_con);
    if ($ucl["nbc"]) {
        // simple protocol
        $hcproto=array();
        if (isset($vars["selnb"])) {
            $selnb=$vars["selnb"];
            $hiddennbsel="<input type=\"hidden\" name=\"selnb\" value=$selnb />";
        } else {
            $selnb=0;
            $hiddennbsel="";
        }
        // parse host_classes, host_locations and events
        $mres=query("SELECT h.classname,h.device_class_idx,h.priority FROM device_class h ORDER BY priority");
        $device_classes=array(0=>array("unset",0));
        while ($mfr=mysql_fetch_object($mres)) $device_classes[$mfr->device_class_idx]=array($mfr->classname,$mfr->priority);
        $mres=query("SELECT h.location,h.device_location_idx FROM device_location h");
        $host_locations=array(0=>array("unset"));
        while ($mfr=mysql_fetch_object($mres)) $host_locations[$mfr->device_location_idx]=array($mfr->location);
        $cluster_events=array();
        $mres=query("SELECT c.cluster_event_idx,c.name,c.description FROM cluster_event c");
        while ($mfr=mysql_fetch_object($mres)) $cluster_events[$mfr->cluster_event_idx]=array($mfr->name,$mfr->description);
        $netbotzes=array();
        $mres=query("SELECT d.name,d.device_idx,i.ip FROM device d, netdevice nd, netip i, device_type dt WHERE nd.device=d.device_idx AND d.device_type=dt.device_type_idx AND dt.identifier='NB' AND i.netdevice=nd.netdevice_idx AND nd.device=d.device_idx");
        while ($mfr=mysql_fetch_object($mres)) {
            $netbotzes[$mfr->device_idx]=new netbotz($mfr->name,$mfr->device_idx);
            $actnb=&$netbotzes[$mfr->device_idx];
            $actnb->ip=$mfr->ip;
            $actnb->locations=array();
            $mr2=query("SELECT nb.device_location FROM nb_hloc_con nb WHERE nb.device=$actnb->idx");
            while ($mfr2=mysql_fetch_object($mr2)) $actnb->locations[]=$mfr2->device_location;      
        }
        if (sizeof($netbotzes)) {
            message ("Please select Netbotz:");
            echo "<form action=\"/php/netbotzconfig.php?".write_sid()."\" method=post>";
            echo "<div class=\"center\">";
            echo "<table class=\"simplesmall\"><tr>\n";
            echo "<td><select name=\"selnb\">";
            foreach ($netbotzes as $netbotz) {
                echo "<option value=$netbotz->idx";
                if ($netbotz->idx == $selnb) echo " selected";
                echo ">$netbotz->name ($netbotz->ip)\n";
            }
            echo "</select>";
            echo "</td>";
            echo "<td><input type=submit value=\"select\" /></td>";
            echo "</tr></table>\n";
            echo "</div></form>";
            if ($selnb) {
                $actnb=$netbotzes[$selnb];
# check for new event
                if ($vars["newevent"]) {
                    $noadd_str="";
                    $lower_str=$vars["new_lowerbound"];
                    $upper_str=$vars["new_upperbound"];
                    $lower_temp=doubleval($lower_str);
                    $upper_temp=doubleval($upper_str);
                    if ($lower_str != strval($lower_temp) or $upper_str != strval($upper_temp)) {
                        $noadd_str="error parsing lower- and/or upperbound";
                    } else {
                        if ($vars["new_class"]) {
                            $nclass=$vars["new_class"];
                        } else {
                            $noadd_str="default class given";
                        }
                    }
                    if ($noadd_str) {
                        message("Cannot add new event because: $noadd_str");
                    } else {
                        $levent=$vars["lower_event"];
                        $uevent=$vars["upper_event"];
                        $mysql_str="INSERT INTO nb_event VALUES(0,$selnb,$nclass,$lower_temp,$levent,1,$upper_temp,$uevent,1,0,0,null)";
                        query($mysql_str);
                    }
                }
                $actnb->events=array();
                $mr2=query("SELECT nb.device_class,nb.nb_event_idx,nb.lower_bound,nb.lower_event,nb.upper_bound,nb.upper_event,nb.lower_mail,nb.upper_mail,nb.last_triggered,nb.disabled FROM nb_event nb WHERE nb.device=$actnb->idx");
                while ($mfr2=mysql_fetch_object($mr2)) {
                    $nb_idx=$mfr2->nb_event_idx;
                    if ($vars["del_$nb_idx"]=="on") {
                        $sql_str="DELETE FROM nb_event WHERE nb_event_idx=$nb_idx";
                        query($sql_str);
                    } else {
                        $actnb->events[$nb_idx]=array($mfr2->device_class,$mfr2->lower_bound,$mfr2->lower_event,$mfr2->lower_mail,$mfr2->upper_bound,$mfr2->upper_event,$mfr2->upper_mail,$mfr2->last_triggered,$mfr2->disabled);
                    }
                }
                message("Selected netbotz is $actnb->name (IP $actnb->ip)");
                echo "<form action=\"/php/netbotzconfig.php?".write_sid()."\" method=post>";
                echo "<input type=\"hidden\" name=\"lowerpart\" value=1 />\n";
                echo $hiddennbsel;
                echo "<h4>This Netbotz is responsible for the following locations:</h4>\n";
                foreach ($host_locations as $idx=>$loc_array) {
                    echo "<div class=\"center\">";
                    if ($idx) {
                        if ($vars["lowerpart"]) {
                            $avn=$selnb."_".$idx."_loc";
                            if ($vars[$avn] == "on" && !in_array($idx,$actnb->locations)) {
                                $sql_str="INSERT INTO nb_hloc_con VALUES (0,$selnb,$idx,null)";
                                query($sql_str);
                                $actnb->locations[]=$idx;
                            } elseif ($vars[$avn] != "on" && in_array($idx,$actnb->locations)) {
                                $sql_str="DELETE FROM nb_hloc_con WHERE device=$selnb AND device_location=$idx";
                                query($sql_str);
                                array_splice($actnb->locations,array_search($idx,$actnb->locations),1);
                            }
                        }
                        list($loc)=$loc_array;
                        echo "$loc <input type=\"checkbox\" name=\"$selnb.$idx.loc\" value=\"on\"";
                        if (in_array($idx,$actnb->locations)) echo " checked ";
                        echo "/>";
                    }
                    echo "</div>";
                }
                if (sizeof($actnb->events)) {
                    echo "<h4>".count($actnb->events)." events configured for this netbotz</h4>\n";
                    echo "<table class=\"normal\">\n";
                    echo "<tr><th class=\"nbdelnbc\">Delete</th><th colspan=2 class=\"nbclass\">Class/Hosts/Event selection</th><th colspan=2 class=\"nblubound\">Send mail</th><th colspan=2 class=\"nblubound\">Lower/Upper-bound</th><th class=\"blue2c\">Test</th></tr>\n";
                    $trigger_t=array(0=>"None/Unknown",1=>"Descending (lower)",2=>"Ascending (upper)");
                    foreach ($actnb->events as $nbe_idx=>$event) {
                        list($dclass,$lbound,$levent,$lmail,$ubound,$uevent,$umail,$last_t,$disabled)=$event;
                        if ($vars["levent_$nbe_idx"]) {
                            $new_hclass=$vars["class_$nbe_idx"];
                            $new_levent=$vars["levent_$nbe_idx"];
                            $new_lbound=$vars["lowerbound_$nbe_idx"];
                            if ($vars["lowermail_$nbe_idx"] == "on") {
                                $new_lmail=1;
                            } else {
                                $new_lmail=0;
                            }
                            $new_uevent=$vars["uevent_$nbe_idx"];
                            $new_ubound=$vars["upperbound_$nbe_idx"];
                            if ($vars["uppermail_$nbe_idx"] == "on") {
                                $new_umail=1;
                            } else {
                                $new_umail=0;
                            }
                            if ($vars["disable_$nbe_idx"] == "on") {
                                $s_disabled=1;
                            } else {
                                $s_disabled=0;
                            }
                            $lower_temp=doubleval($new_lbound);
                            $upper_temp=doubleval($new_ubound);
                            //echo "$new_lmail,$new_umail <br>";
                            //echo "New ($nbe_idx) : $new_hclass : $new_levent : $new_lbound : $new_uevent : $new_ubound <br>";
                            if ($new_lbound != strval($lower_temp) or $new_ubound != strval($upper_temp) or $device_classes[$new_hclass][1] == 0) {
                                echo "Can´t change... $new_lbound".strval($lower_temp)."<br>";
                            } else {
                                $sql_change=array();
                                if ($new_hclass != $dclass) {
                                    $sql_change[]="device_class=$new_hclass";
                                    $dclass=$new_hclass;
                                }
                                if ($lower_temp != $lbound) {
                                    $sql_change[]="lower_bound=$lower_temp";
                                    $lbound=$lower_temp;
                                }
                                if ($new_levent != $levent) {
                                    $sql_change[]="lower_event=$new_levent";
                                    $levent=$new_levent;
                                }
                                if ($new_lmail != $lmail) {
                                    $sql_change[]="lower_mail=$new_lmail";
                                    $lmail=$new_lmail;
                                }
                                if ($upper_temp != $ubound) {
                                    $sql_change[]="upper_bound=$upper_temp";
                                    $ubound=$upper_temp;
                                }
                                if ($new_uevent != $uevent) {
                                    $sql_change[]="upper_event=$new_uevent";
                                    $uevent=$new_uevent;
                                }
                                if ($new_umail != $umail) {
                                    $sql_change[]="upper_mail=$new_umail";
                                    $umail=$new_umail;
                                }
                                if ($disabled != $s_disabled) {
                                    $sql_change[]="disabled=$s_disabled";
                                    $disabled=$s_disabled;
                                }
                                if (count($sql_change)) {
                                    $sql_str="UPDATE nb_event SET ".implode(",",$sql_change)." WHERE nb_event_idx=$nbe_idx";
                                    //echo $sql_str."<br>";
                                    query($sql_str);
                                }
                            }
                            $ret=array();
                            if ($vars["lowertest_$nbe_idx"] == "on") {
                                $ret=contact_server($sys_config,"rrd_server",8003,"test_cet $actnb->idx $nbe_idx 1");
                            }
                            if ($vars["uppertest_$nbe_idx"] == "on") {
                                $ret=contact_server($sys_config,"rrd_server",8003,"test_cet $actnb->idx $nbe_idx 2");
                            }
                        }
                        $mr2=query("SELECT d.name FROM device d, device_location dl, device_class dc WHERE d.device_location=dl.device_location_idx AND d.device_class=dc.device_class_idx AND (dl.device_location_idx=".implode($actnb->locations," OR dl.device_location_idx=").") AND dc.priority <= ".strval($device_classes[$dclass][1]));
                        $hosts=array();
                        while ($mfr2=mysql_fetch_object($mr2)) $hosts[]=$mfr2->name;
                        echo "<tr><td rowspan=4 class=\"nbdelnbc\"><input type=\"checkbox\" name=\"del_$nbe_idx\" /></td>";
                        echo "<td class=\"nbclassr\">Highest Class (classes with lower priority are also affected):</td>";
                        echo "<td class=\"nbclassl\"><select name=\"class_$nbe_idx\">";
                        foreach ($device_classes as $idx=>$hc_array) {
                            list($class,$pri)=$hc_array;
                            echo "<option value=$idx";
                            if ($dclass==$idx) echo " selected";
                            echo ">$class ($pri)";
                        }
                        echo "</select></td>";
                        echo "<td colspan=2 class=\"nbclassl\">Last triggered: $trigger_t[$last_t] </td>";
                        echo "<td class=\"nbclassr\">Disabled:</td>";
                        echo "<td colspan=2 class=\"nbclassl\"><input type=\"checkbox\" name=\"disable_$nbe_idx\"";
                        if ($disabled) echo " checked ";
                        echo "/></td>";
                        echo "</tr>\n<tr>";
                        echo "<td class=\"nbhostl\" colspan=7>".implode($hosts,", ")."</td></tr>\n<tr>";
                        echo "<td class=\"nbeventr\">Lower event (triggered when traversing from higher to lower temperatures):</td>";
                        echo "<td class=\"nbeventl\"><select name=\"levent_$nbe_idx\">";
                        foreach ($cluster_events as $idx=>$lfield) {
                            list($name,$descr)=$lfield;
                            echo "<option value=\"$idx\"";
                            if ($idx == $levent) echo " selected";
                            echo ">$name ($descr)";
                        }
                        echo "</select></td>";
                        echo "<td class=\"nbeventr\">Send mail:</td>";
                        echo "<td class=\"nbeventl\"><input type=\"checkbox\" name=\"lowermail_$nbe_idx\" value=\"on\"";
                        if ($lmail) echo " checked ";
                        echo "/></td>\n";
                        echo "<td class=\"nbeventr\">Lower Bound:</td>";
                        echo "<td class=\"nbeventl\"><input name=\"lowerbound_$nbe_idx\" type=\"text\" size=\"10\" maxlength=\"8\" value=\"$lbound\" /> °C</td>";
                        echo "<td class=\"blue2c\"><input name=\"lowertest_$nbe_idx\" type=\"checkbox\" /></td>";
                        echo "</tr>\n<tr>";
                        echo "<td class=\"nbeventr\">Upper event (triggered when traversing from lower to higher temperatures):</td>";
                        echo "<td class=\"nbeventl\"><select name=\"uevent_$nbe_idx\">";
                        foreach ($cluster_events as $idx=>$lfield) {
                            list($name,$descr)=$lfield;
                            echo "<option value=\"$idx\"";
                            if ($idx == $uevent) echo " selected";
                            echo ">$name ($descr)";
                        }
                        echo "</select></td>";
                        echo "<td class=\"nbeventr\">Send mail:</td>";
                        echo "<td class=\"nbeventl\"><input type=\"checkbox\" name=\"uppermail_$nbe_idx\" value=\"on\"";
                        if ($umail) echo " checked ";
                        echo "/></td>\n";
                        echo "<td class=\"nbeventr\">Upper Bound:</td>";
                        echo "<td class=\"nbeventl\"><input name=\"upperbound_$nbe_idx\" type=\"text\" size=\"10\" maxlength=\"8\" value=\"$ubound\" /> °C</td>";
                        echo "<td class=\"blue2c\"><input name=\"uppertest_$nbe_idx\" type=\"checkbox\" /></td>";
                        echo "</tr>";
                    }
                    echo "</table>\n";
                } else {
                    echo "<h4>No events configured for this netbotz</h4>\n";
                }
                echo "<h4>Define a new netbotz event<input type=\"checkbox\" name=\"newevent\" value=\"new\" />:</h4>";
                echo "<table class=\"normal\">\n";
                echo "<tr><th colspan=2 class=\"nbclass\">Class/Event selection</th><th colspan=2 class=\"nblubound\">Send mail</th><th colspan=2 class=\"nblubound\">Lower/Upper-bound</th></tr>\n";
                echo "<tr><td class=\"nbclassr\">Highest Class (classes with lower priority are also affected):</td>";
                echo "<td class=\"nbclassl\" colspan=5><select name=\"new_class\">";
                foreach ($device_classes as $idx=>$hc_array) {
                    list($class,$pri)=$hc_array;
                    echo "<option value=$idx";
                    echo ">$class ($pri)";
                }
                echo "</select></td></tr>\n<tr>";
                echo "<td class=\"nbeventr\">Lower event (triggered when traversing from higher to lower temperatures):</td>";
                echo "<td class=\"nbeventl\"><select name=\"lower_event\">";
                foreach ($cluster_events as $idx=>$lfield) {
                    list($name,$descr)=$lfield;
                    echo "<option value=\"$idx\">$name ($descr)";
                }
                echo "</select></td>";
                echo "<td class=\"nbeventr\">Send mail:</td>";
                echo "<td class=\"nbeventl\"><input type=\"checkbox\" name=\"new_lowermail\" value=\"on\" checked /></td>\n";
                echo "<td class=\"nbeventr\">Lower Bound:</td>";
                echo "<td class=\"nbeventl\"><input name=\"new_lowerbound\" type=\"text\" size=\"10\" maxlength=\"8\" value=\"20.0\" /> °C</td>";
                echo "</tr>\n<tr>";
                echo "<td class=\"nbeventr\">Upper event (triggered when traversing from lower to higher temperatures):</td>";
                echo "<td class=\"nbeventl\"><select name=\"upper_event\">";
                foreach ($cluster_events as $idx=>$lfield) {
                    list($name,$descr)=$lfield;
                    echo "<option value=\"$idx\">$name ($descr)";
                }
                echo "</select></td>";
                echo "<td class=\"nbeventr\">Send mail:</td>";
                echo "<td class=\"nbeventl\"><input type=\"checkbox\" name=\"new_uppermail\" value=\"on\" checked /></td>\n";
                echo "<td class=\"nbeventr\">Upper Bound:</td>";
                echo "<td class=\"nbeventl\"><input name=\"new_upperbound\" type=\"text\" size=\"10\" maxlength=\"8\" value=\"25.0\" /> °C</td>";
                echo "</tr></table>\n";
                echo "<div class=\"center\"><input type=\"submit\" value=\"submit\" /></div>\n";
                echo "</form>";
            } else {
                message("No netbotz selected.");
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
