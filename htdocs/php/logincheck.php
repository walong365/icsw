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
$PYTHON_COMPAT=1;

function mysql_check(&$item,$key) {
    if (is_string($item)) {
        $item="'".mysql_escape_string($item)."'";
    }
}

require_once "config.php";
require_once "mysql.php";
require_once "tools.php";
$vars=readgets();
if (! session_id()) {
    $loginname="";
    $loginpassword="";
    if (us_vars_defined()) {
        if (isset($_POST["name"])) $loginname=$_POST["name"];
        if (isset($_POST["password"])) $loginpassword=$_POST["password"];
    } else {
        if (isset($GLOBALS["HTTP_POST_VARS"]["name"])) $loginname=$GLOBALS["HTTP_POST_VARS"]["name"];
        if (isset($GLOBALS["HTTP_POST_VARS"]["password"])) $loginpassword=$_POST["password"];
    }
    $sys_config["AUTO_RELOAD"]=30;
    $search_str="/^\/\/\-\*ics\*\- (.*)$/";
    $ics_lines=array();
    $dir_c=dir(get_root_dir()."/php");
    while ($entry=$dir_c->read()) {
        if (preg_match("/^[^#]+\.php$/",$entry)) {
            $fname=get_root_dir()."/php/$entry";
            $fcont=file($fname);
            foreach ($fcont as $line) {
                if (preg_match($search_str,$line,$line_m)) $ics_lines[]=trim($line_m[1]);
            }
        }
    }
    //print_r($ics_lines);
    $new_stuff=0;
    foreach (array("CAPG","CAP") as $s_group) {
        foreach($ics_lines as $p_line) {
            $deli=$p_line[0];
            //echo "$deli , ".substr($p_line,1)." <br>";
            $parts=explode($deli,substr($p_line,1));
            $group=array_shift($parts);
            $kva=array();
            $kva2=array();
            foreach ($parts as $ps) {
                $psp=explode(":",$ps,2);
                $kva[$psp[0]]=$psp[1];
                $kva2[]=$psp[0]."=".$psp[1];
            }
            if ($group == $s_group && $s_group == "CAP") {
                $mres=query("SELECT * FROM capability c WHERE c.name=".$kva["name"],$sys_db_con);
                if (!mysql_affected_rows()) {
                    query("INSERT INTO capability SET php_enabled=1,".implode(", ",$kva2),$sys_db_con);
                    $new_stuff=1;
                }
            } else if ($group == $s_group && $s_group == "CAPG") {
                $mres=query("SELECT * FROM capability_group cg WHERE cg.name=".$kva["name"],$sys_db_con);
                if (!mysql_affected_rows()) {
                    query("INSERT INTO capability_group SET ".implode(", ",$kva2),$sys_db_con);
                    $new_stuff=1;
                }
            }
        }
    }
    if ($new_stuff || 1) {
        // recalculate the capability-capability_group linking
        $mres=query("SELECT cg.name,cg.capability_group_idx FROM capability_group cg");
        $cgs=array();
        while ($mfr=mysql_fetch_object($mres)) $cgs[$mfr->name]=$mfr->capability_group_idx;
        $mres=query("SELECT c.capability_idx,c.capability_group,c.capability_group_name FROM capability c");
        $new_cs=array();
        while ($mfr=mysql_fetch_object($mres)) {
            if ($mfr->capability_group_name) {
                if ($mfr->capability_group != $cgs[$mfr->capability_group_name]) $new_cs[$mfr->capability_idx]=$cgs[$mfr->capability_group_name];
            }
        }
        foreach ($new_cs as $idx=>$cg_idx) query("UPDATE capability SET capability_group=$cg_idx WHERE capability_idx=$idx");
        // recalculate the capability-mother_capability linking
        $mres=query("SELECT c.name,c.capability_idx FROM capability c WHERE c.php_enabled=1");
        $c_s=array();
        while ($mfr=mysql_fetch_object($mres)) $c_s[$mfr->name]=$mfr->capability_idx;
        $mres=query("SELECT c.capability_idx,c.mother_capability,c.mother_capability_name FROM capability c WHERE c.php_enabled=1");
        $new_cs=array();
        while ($mfr=mysql_fetch_object($mres)) {
            if ($mfr->mother_capability_name) {
                if ($mfr->mother_capability != $c_s[$mfr->mother_capability_name]) $new_cs[$mfr->capability_idx]=$c_s[$mfr->mother_capability_name];
            }
        }
        foreach ($new_cs as $idx=>$cg_idx) query("UPDATE capability SET mother_capability=$cg_idx WHERE capability_idx=$idx");
        // delete old ggroupcaps
        $mres=query("SELECT g.ggroupcap_idx FROM ggroupcap g LEFT JOIN capability c ON g.capability=c.capability_idx WHERE c.name IS NULL");
        while ($mfr=mysql_fetch_object($mres)) query("DELETE FROM ggroupcap WHERE ggroupcap_idx=$mfr->ggroupcap_idx");
    }
    // error object (field)
    unset($err_obj);
    //print_r($nf);
    $mres=query("SELECT u.user_idx,u.login,u.password,g.ggroup_idx FROM user u, ggroup g WHERE u.active AND g.active".
                " AND u.ggroup=g.ggroup_idx AND u.login='$loginname'",$sys_db_con);
    if (mysql_num_rows($mres)) {
        $mfr=mysql_fetch_object($mres);
        if (crypt($loginpassword,$mfr->password) == $mfr->password) {
            session_name("ICSID");
            session_start();
            init_session();
            $GLOBALS["HTTP_SESSION_VARS"]["session_user"]=$mfr->login;
            $GLOBALS["HTTP_SESSION_VARS"]["user_idx"]=$mfr->user_idx;
            $GLOBALS["HTTP_SESSION_VARS"]["ggroup_idx"]=$mfr->ggroup_idx;
            $GLOBALS["HTTP_SESSION_VARS"]["page_views"]="1";
            $sys_config["AUTO_RELOAD"]=0;
        } else {
            if ($loginname) {
                $err_obj=array("@Username '$loginname' not defined or wrong password");
            } else {
                $err_obj=array("@no Username given");
            }
        }
    } else {
        $mres=query("SELECT u.login FROM user u, ggroup g WHERE u.login='$loginname'",$sys_db_con);
        if (!mysql_num_rows($mres)) {
            $mres=query("SELECT * FROM user u",$sys_db_con);
            $num_u=mysql_num_rows($mres);
            $mres=query("SELECT * FROM ggroup g",$sys_db_con);
            $num_g=mysql_num_rows($mres);
            if ($num_u+$num_g) {
                if ($loginname) {
                    $err_obj=array("@Username '$loginname' not defined or wrong password");
                } else {
                    $err_obj=array("@no Username given");
                }
            } else {
                // seed for crypt
                $r_seed=get_rand_str();
                // error string
                $err_obj=array("@No users / groups defined","@Creating default group admin / user admin with all rights");
                // generate group
                $mres=query("INSERT INTO ggroup VALUES(0,1,'admin',666,'','','','','','','','',0,0,0,0,0,'',null)",$sys_db_con);
                // generate user
                $mres=query("INSERT INTO user VALUES(0,1,'admin',666,1,0,0,'NOHOME','NOSCRATCH','/bin/false','".crypt("init4u",$r_seed)."',0,1,'','','','','','',0,0,0,0,0,'','',null)",$sys_db_con);
                // generate ggroupcaps
                $mres=query("SELECT c.capability_idx FROM capability c",$sys_db_con);
                while ($mfr=mysql_fetch_object($mres)) $mr2=query("INSERT INTO ggroupcap VALUES(0,1,$mfr->capability_idx,null)",$sys_db_con);
                $err_obj[]="@Creating standard tables";
                // device_types
                foreach (array("H"=>"Host",
                               "AM"=>"APC Masterswitch",
                               "NB"=>"Netbotz",
                               "S"=>"Manageable Switch",
                               "R"=>"Raid box",
                               "P"=>"Printer",
                               "MD"=>"Meta device") as $id=>$str) query("INSERT INTO device_type VALUES(0,'$id','$str',null)");
                // config_types
                foreach (array("s"=>array("Server properties",""),
                               "n"=>array("Node properties",""),
                               "h"=>array("Hardware properties",""),
                               "e"=>array("Export entries","")) as $id=>$stuff) {
                    list($name,$descr)=$stuff;
                    query("INSERT INTO config_type VALUES(0,'$name','$id','$descr',null)");
                }
                // network_types
                foreach (array("b"=>"boot network",
                               "p"=>"production network",
                               "s"=>"slave network",
                               "o"=>"other network",
                               "l"=>"local network") as $id=>$descr) query("INSERT INTO network_type VALUES(0,'$id','$descr',null)");
                // standard network(s)
                $def_net_array=array("identifier"=>"notset",
                                     "network_type"=>2,
                                     "master_network"=>0,
                                     "short_names"=>1,
                                     "name"=>"not set",
                                     "penalty"=>1,
                                     "postfix"=>"",
                                     "info"=>"tralala",
                                     "network"=>"0.0.0.0",
                                     "netmask"=>"0.0.0.0",
                                     "broadcast"=>"0.0.0.0",
                                     "gateway"=>"0.0.0.0",
                                     "gw_pri"=>0);
                $net_array=array(array("identifier"=>"prod","network_type"=>2,"name"=>"init.prod","info"=>"Production network","network"=>"172.16.0.0","netmask"=>"255.255.0.0","broadcast"=>"172.16.255.255"),
                                 array("identifier"=>"boot","network_type"=>1,"name"=>"init.boot","postfix"=>"i","info"=>"Boot network","network"=>"172.17.0.0","netmask"=>"255.255.0.0","broadcast"=>"172.17.255.255"),
                                 array("identifier"=>"mpi","network_type"=>3,"master_network"=>1,"name"=>"init.mpi","postfix"=>"mp","info"=>"MPI Network","network"=>"10.0.0.0","netmask"=>"255.255.0.0","broadcast"=>"10.0.255.255"),
                                 array("identifier"=>"local","network_type"=>5,"name"=>"localdomain","info"=>"Loopback network","network"=>"127.0.0.0","netmask"=>"255.0.0.0","broadcast"=>"127.255.255.255"),
                                 array("identifier"=>"ext","network_type"=>6,"name"=>"init.ext","info"=>"External network","network"=>"192.168.1.0","netmask"=>"255.255.255.0","broadcast"=>"192.168.1.255"),
                                 array("identifier"=>"apc","network_type"=>4,"name"=>"init.apc","info"=>"APC network","network"=>"172.18.0.0","netmask"=>"255.255.0.0","broadcast"=>"172.18.255.255"));
                $if_array=array();
                exec("/sbin/ifconfig",$if_array);
                foreach ($if_array as $if_part) {
                    if (preg_match("/^.*(ddr:[\d\.]+).*(cast:[\d\.]+)*.*(ask:[\d\.]+)*.*$/",$if_part,$if_ps)) {
                        //echo "<br>";
                        //print_r($if_ps);
                    }
                }
                foreach ($net_array as $n_a) {
                    $set_v=$def_net_array;
                    foreach ($n_a as $a_k=>$a_v) $set_v[$a_k]=$a_v;
                    array_walk($set_v,"mysql_check");
                    $sql_str="INSERT INTO network VALUES(0,".implode(",",array_values($set_v)).",1,0,null)";
                    //echo "$sql_str<br>";
                    query($sql_str);
                }
                // log status
                foreach (array(array("c",200,"critical"),
                               array("e",100,"error"),
                               array("w",50,"warning"),
                               array("i",0,"info"),
                               array("n",-50,"notice")) as $ls_stuff) {
                    list($ls_id,$ls_ll,$ls_name)=$ls_stuff;
                    query("INSERT INTO log_status VALUES(0,'$ls_id',$ls_ll,'$ls_name',null)");
                }
                // status, assumes 1 to be the production network
                foreach (array("boot"=>1,
                               "boot_clean"=>1,
                               "installation"=>1,
                               "installation_clean"=>1,
                               "boot_local"=>0,
                               "memtest"=>0) as $status=>$p_link) query("INSERT INTO status VALUES(0,'$status',$p_link,null)");
                // hw_entry_types
                foreach (array(array("cpu","CPU","Speed in MHz","","Model Type",""),
                               array("mem","Memory","Phyiskal Memory","Virtual Memory","",""),
                               array("disks","Harddisks","Number of harddisks","total Size","",""),
                               array("cdroms","CDRoms","Number of CD-Roms","","",""),
                               array("gfx","Graphicscard","","","Type of Gfx","")) as $stuff) {
                    list($identifier,$description,$iarg0_descr,$iarg1_descr,$sarg0_descr,$sarg1_descr)=$stuff;
                    query("INSERT INTO hw_entry_type VALUES(0,'$identifier','$description','$iarg0_descr','$iarg1_descr','$sarg0_descr','$sarg1_descr',null)");
                }
                // snmp classes
                foreach (array(array("default_class","Standard class for SNMP-devices")) as $snmp_stuff) {
                    list($name,$descr)=$snmp_stuff;
                    query("INSERT INTO snmp_class SET name='$name',descr='$descr'");
                }
                // device classes
                query("INSERT INTO device_class VALUES(0,'normal',0,null)");
                // device location
                query("INSERT INTO device_location VALUES(0,'room0',null)");
                // user log_source
                query("INSERT INTO log_source VALUES(0,'user','Cluster user',0,'Clusteruser',null)");
                // filesystem types
                foreach (array(array("reiserfs","f","83","ReiserFS Filesystem"),
                               array("ext2","f","83","Extended 2 Filesystem"),
                               array("ext3","f","83","Extended 3 Filesystem"),
                               array("swap","s","82","SwapSpace"),
                               array("ext","e","f","Extended Partition"),
                               array("empty","d","0","Empty Partition")) as $fs_stuff) {
                    list($name,$id,$hextype,$descr)=$fs_stuff;
                    query("INSERT INTO partition_fs VALUES(0,'$name','$id','$descr','$hextype',null)");
                }
                // cluster event
                foreach (array(array("halt","Halts a machine","ff0000"),
                               array("poweroff","Power-offs a machine","00ff00"),
                               array("ping","Pings a machine","0000ff")) as $ins_stuff) {
                    list($name,$descr,$color)=$ins_stuff;
                    query("INSERT INTO cluster_event VALUES(0,'$name','$descr','$color',null)");
                }
                // default values
                $server_name=explode(".",$GLOBALS["HTTP_SERVER_VARS"]["SERVER_NAME"]);
                $server_name=ucfirst($server_name[0]);
                insert_table("genstuff","0,'CLUSTERNAME','Name of the Cluster','$server_name',null");
                insert_table("genstuff","0,'AUTO_RELOAD','Reload time of some Pages','60',null");
                insert_table("genstuff","0,'POLITICAL_CORRECT','FunStuff','1',null");
                // rrd-class (complicated stuff)
                $step=30;
                $ins_idx=insert_table("rrd_class","0,'standard_device',128,$step,60,null");
                if ($ins_idx) {
                    foreach (array("AVERAGE","MAX","MIN") as $rra) {
                        foreach (array(30      =>        24*60*60,
                                       5*60    =>      7*24*60*60,
                                       15*60   =>    4*7*24*60*60,
                                       4*60*60 => 12*4*7*24*60*60) as $act_step=>$act_slots) {
                            $st_r=$act_step/$step;
                            $st_s=$act_slots/($step*$st_r);
                            insert_table("rrd_rra","0,$ins_idx,'$rra',$st_r,$st_s,0.1,null");
                        }
                    }
                }
            }
        } else {
            $mres=query("SELECT u.login FROM user u WHERE u.login='$loginname' AND u.active",$sys_db_con);
            if (!mysql_num_rows($mres)) {
                $err_obj=array("@User '$loginname' is not active");
            }
            $mres=query("SELECT g.ggroupname FROM user u, ggroup g WHERE u.login='$loginname' AND g.active=0 AND g.ggroup_idx=u.ggroup",$sys_db_con);
            if (mysql_num_rows($mres)) {
                $mret=mysql_fetch_object($mres);
                $err_obj=array("@Your primary group '$mret->ggroupname' is not active");
            }
        }
    }
    if (!isset($err_obj)) $err_obj=array();
    if ($err_obj) array_unshift($err_obj,"You coldn't log in because:");
    $sys_config["RELOAD_TARGET"]="../old_index.php";
    # '0':48,'9':57,'a':97,'z':122
    if (strlen(session_id())) {
        $add_str=strftime("%H%M%S");
        $orig_sess_id=substr(session_id(),0,31);
        for ($i=16;$i<31;$i++) {
            $diff_i=ord($add_str[$i-16])-45;
            $orig_char=ord($orig_sess_id[$i]);
            $new_char=$orig_char+$diff_i;
            while ($new_char > 122) {
                $new_char-=10;
            }
            if ($new_char < 97) {
                while ($new_char > 57) $new_char-=10;
            }
            while ($new_char < 48) $new_char+=10;
            $orig_sess_id[$i]=chr($new_char);
        }
        $orig_sess_id=substr($orig_sess_id,0,31);
        session_id($orig_sess_id);
        $sys_config["SESSION"]=1;
    }
    errorpage($err_obj);
} else {
    session_destroy();
    if ($PYTHON_COMPAT) {
        echo "<meta http-equiv=\"refresh\" content=\"0; URL=../python/main.py\">";
    } else {
        echo "<meta http-equiv=\"refresh\" content=\"0; URL=../old_index.php\">";
    }
}
?>
