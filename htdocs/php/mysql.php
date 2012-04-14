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
function string_ok($str) {
    return (preg_match("/^[\da-zA-Z_]+$/",$str));
}

function path_ok($str) {
    return (preg_match("/^[\da-zA-Z_\/]+$/",$str));
}

function btf_string($str) {
    if (strlen($str) > 0) {
        return $str;
    } else {
        return "---";
    }
}

function get_server_host(&$config,$name) {
    $ret="";
    if (isset($config[$name])) {
        $ret=array_keys($config[$name]);
        $ret=$ret[0];
    }
    return $ret;
}

function contact_server(&$config,$name,$port,$comstr,$timeout=0,$hostname="") {
    if (isset($config[$name])) {
        $host=$config[$name];
        if ($hostname) {
            if (in_array($hostname,array_keys($host))) {
                $host=$host[$hostname];
            } else {
                $config["global_errors"]->addstr("No host named '$hostname' found in config named '$name' found");
                $ret="Host '$hostname' not found in config '$name'";
                $host="";
            }
        } else {
            $hkeys=array_keys($host);
            $host=$host[$hkeys[0]];
        }
        if ($host) {
            $sc="/usr/local/sbin/send_command.py";
            if (is_executable($sc)) {
                if ($timeout) $sc.=" -t $timeout";
                if (preg_match("/^-c .*$/",$comstr)) {
                    $ret=exec("$sc -c $host $port ".substr($comstr,3));
                } else {
                    $ret=exec("$sc $host $port $comstr");
                }
                if (preg_match("/^Got: (.*)$/",$ret,$ret_str)) $ret=$ret_str[1];
                if (preg_match("/^error:.*$/",$ret)) {
                    $config["global_errors"]->addstr("Error calling server name '$name' on host '$host' (port $port) via '$sc' (command '$comstr'): $ret");
                }
            } else {
                $config["global_errors"]->addstr("Cannot find tool '$sc'");
                $ret="";
            }
        }
    } else {
        $config["global_errors"]->addstr("No config named '$name' found");
        $ret="No config named '$name' found";
    }
    return $ret;
}
function call_pure_external($prog) {
    $rets=array();
    //exec("/usr/local/cluster/sbin/wrapper -s $prog",$rets);
    exec($prog,$rets);
    return $rets;
}

function create_sgeee_user(&$config,$fserver,$name) {
    $ret=contact_server($config,"sge_server",8004,"create_sgeee_user username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}

function delete_sgeee_user(&$config,$fserver,$name) {
    $ret=contact_server($config,"sge_server",8004,"delete_sgeee_user username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}

function create_user_home(&$config,$fserver,$name) {
    $ret=contact_server($config,"export",8004,"create_user_home username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}

function create_user_quota(&$config,$fserver,$name) {
    $ret=contact_server($config,"export",8004,"create_user_quota username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}

function create_user_scratch(&$config,$fserver,$name) {
    $ret=contact_server($config,"export",8004,"create_user_scratch username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}

function delete_user_home(&$config,$fserver,$name) {
    $ret=contact_server($config,"export",8004,"delete_user_home username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}
function delete_user_scratch(&$config,$fserver,$name) {
    $ret=contact_server($config,"export",8004,"delete_user_scratch username:$name",$timeout=20,$hostname=$fserver);
    return $ret;
}

function update_yp(&$config) {
    $ret=contact_server($config,"yp_server",8004,"write_yp_config",$timeout=20);
    return $ret;
}
function get_table_idx($tname) {
    global $sys_db_con;
    $mres=query("SELECT t.table_r_idx FROM table_r t WHERE t.name='$tname'",$sys_db_con);
    $tres=mysql_fetch_object($mres);
    return $tres->table_r_idx;
}

function get_user_idx($login) {
    global $sys_db_con;
    $mres=query("SELECT u.user_idx FROM user u WHERE u.login='$login'",$sys_db_con);
    $ures=mysql_fetch_object($mres);
    return $ures->user_idx;
}

function update_table($table,$str,$con="0") {
# generate wstr
    $wstr=str_replace("'","\'",$str);
    $mret=query("UPDATE $table SET $str",$con);
    return $mret;
}

function insert_table($table,$str,$con="0") {
# generate wstr
    $wstr=str_replace("'","\'",$str);
    $mret=query("INSERT INTO $table VALUES($str)",$con);
    return mysql_insert_id();
}

function insert_table_set($table,$str,$con="0") {
# generate wstr
    $wstr=str_replace("'","\'",$str);
    $mret=query("INSERT INTO $table SET $str",$con);
    return mysql_insert_id();
}

function delete_from_table($table,$str,$con="0") {
    $mret=query("DELETE FROM $table WHERE $str",$con);
    return mysql_affected_rows();
}

function init_mysql_stats() {
    $GLOBALS["mysql_queries"]=0;
    $GLOBALS["mysql_queries_error"]=0;
}

function mysql_stats_used() {
    return ($GLOBALS["mysql_queries"]+$GLOBALS["mysql_queries_error"] > 0);
}
function get_mysql_stats() {
    $rstr="SQL statistics: ".strval($GLOBALS["mysql_queries"])." queries submitted";
    if ($GLOBALS["mysql_queries_error"]) $rstr.=" (".strval($GLOBALS["mysql_queries_error"])." of them with error)";
    return $rstr;
}
  
function query($str,$con="0") {
    global $sys_db_con,$sys_config;
    if ($con == "0") $con=$sys_db_con;
    if (!isset($GLOBALS["mysql_queries"])) init_mysql_stats();
    $GLOBALS["mysql_queries"]++;
    $mres=mysql_query($str,$con);
    //echo "*<br>$str";
    if (! $mres) {
        $errstr=mysql_error($con);
        $sys_config["global_errors"]->addstr("Error sending SQL-Query '$str'");
        $sys_config["global_errors"]->addstr("@SQL-Errormessage is: '$errstr'");
        $GLOBALS["mysql_queries_error"]++;
    } 
    //$sys_config["global_errors"]->addstr("sending SQL-Query '$str'");
    //echo "SQL-Query :".$str."<br>";
    return $mres;
}

function getcapabilities() {
    global $sys_db_con;
    $mres=query("SELECT * FROM capability c WHERE c.php_enabled=1",$sys_db_con);
    $ucl=array();
    while ($cap=mysql_fetch_object($mres)) $ucl[$cap->name]=$cap;
    return $ucl;
}

function getgroups() {
    global $sys_db_con;
    $mres=query("SELECT * FROM ggroup g ORDER BY g.ggroupname",$sys_db_con);
    $gl=array();
    $gln=array();
    while ($g=mysql_fetch_object($mres)) {
        $gl[$g->ggroup_idx]=$g;
        $gln[$g->ggroupname]=$g->ggroup_idx;
    }
    return array($gl,$gln);
}

function getusers() {
    global $sys_db_con;
    $mres=query("SELECT * FROM user u ORDER BY u.login");
    $ul=array();
    while ($u=mysql_fetch_object($mres)) {
        $u->sgroup_idx=array();
        $ul[$u->login]=$u;
    }
    $mres=query("SELECT u.login,g.ggroup_idx FROM user u, ggroup g, user_ggroup ug WHERE ug.user=u.user_idx AND ug.ggroup=g.ggroup_idx",$sys_db_con);
    while ($ug=mysql_fetch_object($mres)) $ul[$ug->login]->sgroup_idx[]=$ug->ggroup_idx;
    return $ul;
}

function get_all_log_sources() {
    global $sys_db_con;
    $all_sources=array(0=>array("identifier"=>"???","name"=>"unknown","description"=>"not set"));
    $mres=query("SELECT l.*,d.name AS devname FROM log_source l LEFT JOIN device d ON l.device=d.device_idx ORDER BY l.identifier");
    while ($mfr=mysql_fetch_object($mres)) $all_sources[$mfr->log_source_idx]=$mfr;
    return $all_sources;
}
function get_all_log_users() {
    global $sys_db_con;
    $uls=get_log_source("user");
    $uls=$uls->log_source_idx;
    $mres=query("SELECT COUNT(DISTINCT d.devicelog_idx) AS logcount,u.* FROM user u, devicelog d WHERE (d.log_source=$uls AND d.user=u.user_idx) GROUP BY u.login");
    $all_ls=array();
    while ($mfr=mysql_fetch_object($mres)) $all_ls[$mfr->user_idx]=$mfr;
    return $all_ls;
}
function get_log_source($id) {
    global $sys_db_con;
    $mres=query("SELECT * FROM log_source l WHERE l.identifier='$id'");
    if (mysql_num_rows($mres)) {
        return mysql_fetch_object($mres);
    } else {
        return 0;
    }
}

function get_sgeee_server() {
    $eq=query("SELECT mc.device_config_idx,d.name FROM device d, device_config mc, new_config c WHERE mc.device=d.device_idx AND mc.new_config=c.new_config_idx AND c.name='sge_server'");
    if (mysql_num_rows($eq)) {
        $mret=mysql_fetch_object($eq);
        $sgeee_server=$mret->name;
    } else {
        $sgeee_server="";
    }
    return $sgeee_server;
}

function get_exports($type) {
    $eq=query("SELECT dc.device_config_idx,d.name,sc.value,d.device_idx FROM device d, device_config dc, new_config c,config_str sc WHERE dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND sc.new_config=c.new_config_idx AND sc.name='{$type}export' ORDER BY d.name");
    $dev_idx=array();
    $exps=array();
    while ($mfr=mysql_fetch_object($eq)) {
        $dev_idx[]="d.device_idx=$mfr->device_idx";
        $mfr->quota=0;
        $exps[$mfr->device_config_idx]=$mfr;
    }
    if (count($dev_idx)) {
        $eq=query("SELECT DISTINCT d.device_idx FROM device d, device_config dc, new_config c WHERE dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND c.name='quota' AND (".implode(" OR ",$dev_idx).")");
        while ($mfr=mysql_fetch_object($eq)) {
            foreach ($exps as $idx=>$stuff) {
                if ($stuff->device_idx == $mfr->device_idx) $exps[$idx]->quota=1;
            }
        }
    }
    return $exps;
}

function getgroupcaps($name) {
    global $sys_db_con;
    $gcl=array();
    $mres=query("SELECT c.name,c.descr,gc.ggroupcap_idx FROM capability c, ggroupcap gc, ggroup g WHERE ".
                "gc.capability=c.capability_idx AND gc.ggroup=g.ggroup_idx AND g.ggroupname='$name' AND c.php_enabled=1",$sys_db_con);
    while ($ucap=mysql_fetch_object($mres)) $gcl[$ucap->name]=array($ucap->descr,$ucap->ggroupcap_idx);
    return $gcl;
}

function get_group_caps_struct($name=0) {
    global $sys_db_con;
    $gcl=array("total"=>0);
    $mca=array();
    if ($name) {
        $mres=query("SELECT c.name,c.capability_idx,c.descr,c.defvalue,gc.ggroupcap_idx,c.capability_group,cg.descr as cg_descr FROM capability c, ggroupcap gc, ggroup g, capability_group cg WHERE ".
                    "gc.capability=c.capability_idx AND gc.ggroup=g.ggroup_idx AND g.ggroupname='$name' AND cg.capability_group_idx=c.capability_group AND c.php_enabled=1 ORDER BY cg.pri,c.pri",$sys_db_con);
    } else {
        $mres=query("SELECT c.name,c.capability_idx,c.descr,c.defvalue,c.capability_group,cg.descr as cg_descr,0 as ggroupcap_idx FROM capability c, capability_group cg WHERE ".
                    "cg.capability_group_idx=c.capability_group AND c.php_enabled ORDER BY cg.pri,c.pri",$sys_db_con);
    }
    while ($ucap=mysql_fetch_object($mres)) {
        if (!in_array($ucap->cg_descr,array_keys($gcl))) $gcl[$ucap->cg_descr]=array("caps"=>array(),"num"=>0);
        $gcl[$ucap->cg_descr]["caps"][$ucap->name]=array($ucap->name=>array("def"=>$ucap->defvalue,"descr"=>$ucap->descr,"idx"=>$ucap->ggroupcap_idx));
        $mca[$ucap->capability_idx]=array($ucap->cg_descr,$ucap->name);
        $gcl[$ucap->cg_descr]["num"]++;
        $gcl["total"]++;
    }
    if ($name) {
        $mres=query("SELECT c.name,c.descr,c.defvalue,gc.ggroupcap_idx,c.mother_capability FROM capability c, ggroupcap gc, ggroup g WHERE c.php_enabled AND ".
                    "gc.capability=c.capability_idx AND gc.ggroup=g.ggroup_idx AND g.ggroupname='$name' AND c.mother_capability ORDER BY c.pri",$sys_db_con);
    } else {
        $mres=query("SELECT c.name,c.descr,c.defvalue,c.mother_capability,0 as ggroupcap_idx FROM capability c WHERE c.php_enabled AND c.mother_capability ORDER BY c.pri",$sys_db_con);
    }
    while ($ucap=mysql_fetch_object($mres)) {
        if (isset($mca[$ucap->mother_capability])) {
            list($descr,$c_name)=$mca[$ucap->mother_capability];
            $gcl[$descr]["caps"][$c_name][$ucap->name]=array("def"=>$ucap->defvalue,"descr"=>$ucap->descr,"idx"=>$ucap->ggroupcap_idx);
            $gcl[$descr]["num"]++;
            $gcl["total"]++;
        }
    }
    if ($name) {
        $mres=query("SELECT c.name,c.descr,c.defvalue,gc.ggroupcap_idx FROM capability c, ggroupcap gc, ggroup g WHERE ".
                    "gc.capability=c.capability_idx AND gc.ggroup=g.ggroup_idx AND g.ggroupname='$name' AND c.mother_capability=0 AND c.capability_group=0 AND c.php_enabled ORDER BY c.pri",$sys_db_con);
    } else {
        $mres=query("SELECT c.name,c.descr,c.defvalue,0 as ggroupcap_idx FROM capability c WHERE c.php_enabled AND c.mother_capability=0 AND c.capability_group=0 ORDER BY c.pri",$sys_db_con);
    }
    while ($ucap=mysql_fetch_object($mres)) {
        if (!in_array("unsorted",array_keys($gcl))) $gcl["unsorted"]=array("caps"=>array(),"num"=>0);
        $gcl["unsorted"]["caps"][$ucap->name]=array($ucap->name=>array("def"=>$ucap->defvalue,"descr"=>$ucap->descr,"idx"=>$ucap->ggroupcap_idx));
        $gcl["unsorted"]["num"]++;
        $gcl["total"]++;
    }
    return $gcl;
}

function usercaps() {
    global $sys_db_con;
    $mres=query("SELECT u.ggroup,u.user_idx,c.name,c.descr FROM user u INNER JOIN ggroup g LEFT JOIN ggroupcap gc ON gc.ggroup=g.ggroup_idx LEFT JOIN capability c ON gc.capability=c.capability_idx WHERE u.login='{$GLOBALS['HTTP_SESSION_VARS']['session_user']}' AND u.ggroup=g.ggroup_idx",$sys_db_con);
    $ucl=array();
    while ($mfr=mysql_fetch_object($mres)) {
	if ($mfr->name) $ucl[$mfr->name]=array($mfr->descr);
    }
    return $ucl;
}
class config_variable {
    var $var_type,$name,$descr,$var_idx,$value,$multiline=0;
    function config_variable($var_type,$name,$descr,$value,$var_idx) {
        $this->var_type=$var_type;
        $this->name=$name;
        $this->descr=$descr;
        $this->value=$value;
        $this->var_idx=$var_idx;
        if ($this->var_type=="str" && substr_count($this->value,"\n")) $this->multiline=1;
    }
    function get_name() {
        return $this->name;
    }
    function compose_prefix($pfix) {
        return "{$pfix}_{$this->var_type}_{$this->var_idx}";
    }
    function print_html_mask($pfix,$config_vts=array()) {
        $my_pfix=$this->compose_prefix($pfix);
        echo "<td class=\"delnew\">Del:<input type=checkbox name=\"{$my_pfix}_del\" /><input type=hidden name=\"{$my_pfix}_set\" value=\"1\"/></td>\n";
        if ($config_vts) {
            echo "<td class=\"type\">{$config_vts[$this->var_type]} ";
            if ($this->var_type == "str") {
                echo "<input type=checkbox name=\"${my_pfix}_ml\" ";
                if ($this->multiline) echo " checked ";
                echo "/>";
            }
            echo "</td>\n";
            echo "<td class=\"netl\"><input name=\"{$my_pfix}_name\" value=\"$this->name\" maxlength=\"30\" size=\"30\" /></td>";
            if (!$this->multiline) {
                echo "<td class=\"netl\">";
                echo "<input name=\"{$my_pfix}_value\" value=\"".my_html_encode($this->value)."\" maxlength=\"120\" size=\"30\" /></td>";
            }
            echo "<td class=\"netl\" ><input name=\"{$my_pfix}_descr\" value=\"$this->descr\" maxlength=\"250\" size=\"50\" /></td>";
            if ($this->multiline) {
                $lines=max(1,substr_count($this->value,"\n")+1);
                $act_h=min($lines,10);
                echo "<td class=\"netl\">Lines: $lines</td></tr>\n";
                echo "<tr><td class=\"netl\" colspan=\"5\">\n";
                echo "<textarea name=\"{$my_pfix}_value\" wrap=\"off\" cols=\"80\" rows=\"$act_h\">".my_html_encode($this->value)."</textarea></td></tr>\n";
            }
        }
    }
    function check_for_change($pfix,&$vars,$log_stack,$add_str,&$all_names) {
        $my_pfix=$this->compose_prefix($pfix);
        if (is_set("{$my_pfix}_ml",&$vars) || substr_count($this->value,"\n")) {
            $this->multiline=1;
        } else {
            $this->multiline=0;
        }
        if (is_set("{$my_pfix}_set",&$vars)) {
            $vvar_descr="{$my_pfix}_descr";
            $old_descr=trim($this->descr);
            $new_descr=my_html_decode($vars[$vvar_descr]);
            if ($old_descr != $new_descr) {
                $log_stack->add_message("modify description of $this->name from '$old_descr' to '$new_descr' $add_str","ok",1);
                update_table("config_{$this->var_type}","descr='".mysql_escape_string($new_descr)."' WHERE config_{$this->var_type}_idx=$this->var_idx");
                $this->descr=$new_descr;
            }
            $vvar_value="{$my_pfix}_value";
            $old_value=$this->value;
            $new_value=my_html_decode($vars[$vvar_value]);
            if ($old_value != $new_value) {
                $parse_ok=0;
                if ($this->var_type=="int") {
                    if (preg_match("/^\d+$/",$new_value)) {
                        $parse_ok=1;
                        $new_val_str=$new_value;
                    }
                } else if ($this->var_type=="str") {
                    $parse_ok=1;
                    $new_val_str="'".mysql_escape_string($new_value)."'";
                } else if ($this->var_type=="blob") {
                    $parse_ok=1;
                    $new_val_str="'".mysql_escape_string($new_value)."'";
                }
                if ($parse_ok) {
                    $log_stack->add_message("modify value of $this->name from (".strval(strlen($old_value))." -> ".strval(strlen($new_value)).") '".str_replace("\n","<br>",$old_value)."' to '".str_replace("\n","<br>",$new_value)."' $add_str","ok",1);
                    update_table("config_{$this->var_type}","value=$new_val_str WHERE config_{$this->var_type}_idx=$this->var_idx");
                    $this->value=$new_value;
                } else {
                    $log_stack->add_message("cannot modify value of $this->name from '$old_value' to '$new_value' $add_str","parse error",0);
                }
            }
            $vvar_name="{$my_pfix}_name";
            $new_name=trim($vars[$vvar_name]);
            if ($new_name != $this->name && $new_name) {
                if (preg_match("/^\w+[\w\d]*$/",$new_name)) {
                    if (in_array($new_name,$all_names)) {
                        $log_stack->add_message("cannot change name from $this->name to '$new_name' $add_str","already in varlist",0);
                    } else {
                        $log_stack->add_message("changed name $this->name to '$new_name' $add_str","ok",1);
                        update_table("config_{$this->var_type}","name='$new_name' WHERE config_{$this->var_type}_idx={$this->var_idx}");
                        $this->name=$new_name;
                        $all_names[]=$new_name;
                    }
                } else {
                    $log_stack->add_message("cannot change name from $this->name to '$new_name' $add_str","parse error",0);
                }
            }
        }
    }
}
class config_nagios extends config_variable {
    var $template,$command_line;
    function config_nagios($name,$descr,$nag_idx,$template,$command_line) {
        $this->var_type="nagios";
        $this->name=$name;
        $this->descr=$descr;
        $this->var_idx=$nag_idx;
        $this->template=$template;
        if (!$this->template) $this->template=0;
        $this->command_line=$command_line;
    }
    function print_html_mask($pfix,$nag_service_templates) {
        parent::print_html_mask($pfix);
        $my_pfix=$this->compose_prefix($pfix);
        echo "<td class=\"type\"><input type=hidden name=\"{$my_pfix}_set\" value=\"1\"/><select name=\"{$my_pfix}_st\" >\n";
        foreach ($nag_service_templates as $n_idx=>$n_stuff) {
            if ($n_idx) {
                echo "<option value=\"$n_idx\" ";
                if ($n_idx == $this->template) echo " selected ";
                echo ">$n_stuff->name</option>\n";
            } else {
                echo "<option value=\"$n_idx\">$n_stuff</option>\n";
            }
        }
        echo "</select></td>\n";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}_name\" value=\"$this->name\" maxlength=\"20\" size=\"20\" /></td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}_descr\" value=\"$this->descr\" maxlength=\"64\" size=\"30\" /></td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}_comline\" value=\"$this->command_line\" maxlength=\"250\" size=\"50\" /></td>";
    }
    function check_for_change($pfix,&$vars,$log_stack,$add_str,$all_nag_names) {
        $my_pfix=$this->compose_prefix($pfix);
        if (is_set("{$my_pfix}_set",&$vars)) {
            $nc_name="{$my_pfix}_name";
            $nc_cline="{$my_pfix}_comline";
            $nc_descr="{$my_pfix}_descr";
            if (is_set($nc_name,&$vars) && is_set($nc_cline,&$vars)) {
                $nc_st=$vars["{$my_pfix}_st"];
                $nc_name=trim($vars[$nc_name]);
                $nc_cline=trim($vars[$nc_cline]);
                $nc_descr=trim($vars[$nc_descr]);
                if (($nc_name != $this->name) || ($nc_cline != $this->command_line) || ($nc_st != $this->template) || ($nc_descr != $this->descr)) {
                    if (($nc_name != $this->name) && in_array($nc_name,$all_nag_names)) {
                        $log_stack->add_message("cannot alter name of Nagios_check_command from {$this->name} to $nc_name $add_str","name already used",0);
                    } else {
                        update_table("ng_check_command","ng_service_templ=$nc_st,name='".mysql_escape_string($nc_name)."',command_line='".mysql_escape_string($nc_cline).
                                     "',description='".mysql_escape_string($nc_descr)."' WHERE ng_check_command_idx=$this->var_idx");
                        $log_stack->add_message("altered Nagios_check_command {$this->name} $add_str","ok",1);
                        $this->name=$nc_name;
                        $this->command_line=$nc_cline;
                        $this->template=$nc_st;
                        $this->descr=$nc_descr;
                        $all_nag_names[]=$nc_name;
                    }
                }
            } else {
                $log_stack->add_message("Need name and command line for nagios_variable $this->name $add_str","error",0);
            }
        }
    }
}
class config_snmp extends config_variable {
    function config_snmp($mib,$snmp_idx) {
        $this->var_type="snmp";
        $this->value=$mib;
        $this->var_idx=$snmp_idx;
    }
    function print_html_mask($pfix,$all_snmp_mibs) {
        parent::print_html_mask($pfix);
        $my_pfix=$this->compose_prefix($pfix);
        $snmp_st2=$all_snmp_mibs[$this->value];
        echo "<td class=\"netl\" colspan=\"4\" ><input type=hidden name=\"{$my_pfix}_set\" value=\"1\"/>$snmp_st2->name (MIB $snmp_st2->mib)</td>\n";
    }
    function check_for_change($pfix,&$vars,$log_stack,$add_str,&$all_snmp_mibs) {
        $my_pfix=$this->compose_prefix($pfix);
        if (is_set("{$my_pfix}_set",&$vars)) {
        }
    }
}
class config {
    var $name,$descr,$config_type,$config_idx,$dev_idx;
    var $str,$int,$blob,$nagios,$snmp,$all_names;
    var $prefix,$add_str;
    function config($name,$descr,$config_type,$priority,$config_idx,$device_idx=0) {
        $this->name=$name;
        $this->descr=$descr;
        $this->config_type=$config_type;
        $this->priority=$priority;
        $this->config_idx=$config_idx;
        $this->dev_idx=$device_idx;
        $this->all_names=array();
        $this->set_prefix("conf");
        $this->add_str="";
        foreach (array("str","int","blob","nagios","snmp") as $cn) {
            $this->$cn=array();
        }
    }
    function set_add_str($add_str) {
        $this->add_str=$add_str;
    }
    function set_prefix($pfix) {
        $this->prefix=$pfix;
    }
    function compose_prefix() {
        return "{$this->prefix}_{$this->config_idx}";
    }
    function check_priority_change(&$vars,$log_stack) {
        $my_pfix=$this->compose_prefix();
        $pri_name="{$my_pfix}_pri";
        $descr_name="{$my_pfix}_descr";
        if (!$this->dev_idx && isset($vars[$pri_name])) {
            $new_pri=trim($vars[$pri_name]);
            if (strval((int)$new_pri) != $new_pri) {
                $log_stack->add_message("change priority of $this->name from '{$this->priority}' to '$new_pri'","parse error",0);
            } else if ((int)$new_pri != (int)$this->priority) {
                $log_stack->add_message("changed priority of $this->name from '{$this->priority}' to '$new_pri'","ok",1);
                $this->priority=(int)$new_pri;
                update_table("config","priority=$new_pri WHERE config_idx=$this->config_idx");
            }
            $new_descr=my_html_decode($vars["{$my_pfix}_descr"]);
            if ($new_descr != $this->descr) {
                $log_stack->add_message("changed description of $this->name from '{$this->descr}' to '$new_descr'","ok",1);
                $this->descr=$new_descr;
                update_table("config","descr='".mysql_escape_string($new_descr)."' WHERE config_idx=$this->config_idx");
            }
        }
    }
    function add_new_variable($new_type,$new_name,$new_descr,$new_value,$log_stack) {
	$parse_ok=0;
	if ($new_type=="int") {
	    if (preg_match("/^\d+$/",$new_value)) {
		$parse_ok=1;
		$new_val_str=$new_value;
	    }
	} else if ($new_type=="str") {
	    $parse_ok=1;
	    $new_val_str="'".mysql_escape_string($new_value)."'";
	} else if ($new_type=="blob") {
	    $parse_ok=1;
	    $new_val_str="'".mysql_escape_string($new_value)."'";
	}
	if ($parse_ok) {
	    $ins=insert_table("config_$new_type","0,'$new_name','".mysql_escape_string($new_descr)."',{$this->config_idx},0,$new_val_str,$this->dev_idx,null");
	    if ($ins) {
		$log_stack->add_message("add new variable named '$new_name' to $this->name, type $new_type, value $new_value, description '$new_descr' $this->add_str","ok",1);
		$this->add_variable($new_type,$new_name,$new_descr,$new_value,$ins);
	    }  else {
		$log_stack->add_message("cannot add new variable named '$new_name' to $this->name $this->add_str","SQL Error",0);
	    }
	} else {
	    $log_stack->add_message("add new variable named '$new_name' to $this->name, type $new_type, value $new_value $this->add_str","parse error",0);
	}
    }
    function check_for_new_var(&$vars,$log_stack) {
        $my_pfix=$this->compose_prefix();
        if (is_set("{$my_pfix}v_new",&$vars)) {
            $new_type=$vars["{$my_pfix}v_newtype"];
            $new_name="{$my_pfix}v_newname";
            if (is_set($new_name,&$vars)) {
                $new_name=trim($vars[$new_name]);
                $new_value=my_html_decode($vars["{$my_pfix}v_newval"]);
                $new_descr=my_html_decode($vars["{$my_pfix}v_newdescr"]);
                if (in_array($new_name,$this->all_names)) {
                    $log_stack->add_message("add new variable to $this->name named '$new_name' $this->add_str","already in varlist",0);
                } else {
                    if (preg_match("/^\w+[\w\d]*$/",$new_name)) {
			$this->add_new_variable($new_type,$new_name,$new_descr,$new_value,&$log_stack);
                    } else {
                        $log_stack->add_message("add new variable named '$new_name' to $this->name $this->add_str","parse error for name",0);
                    }
                }
            }
        }
    }
    function check_for_new_nagios(&$vars,$log_stack,$all_nag_names) {
        $my_pfix=$this->compose_prefix();
        if (is_set("{$my_pfix}n_new",&$vars)) {
            $new_name="{$my_pfix}n_new_name";
            $new_cline="{$my_pfix}n_new_comline";
            if (is_set($new_name,&$vars) && is_set($new_cline,&$vars)) {
                $new_name=$vars[$new_name];
                // device idx to get a (hopefully) unique name
                if ($this->dev_idx) $new_name.="_$dev_idx";
                $new_cline=$vars[$new_cline];
                $new_descr=$vars["{$my_pfix}n_new_descr"];
                $new_st=$vars["{$my_pfix}n_new_templ"];
                if (in_array($new_name,$all_nag_names)) {
                    $log_stack->add_message("cannot add new Nagios_check_command named '$new_name' to config $this->name $this->add_str","name already used",0);
                } else {
                    $ins=insert_table("ng_check_command","0,{$this->config_idx},$new_st,'".mysql_escape_string($new_name)."','".mysql_escape_string($new_cline)."','".mysql_escape_string($new_descr)."',0,$this->dev_idx,null");
                    if ($ins) {
                        $log_stack->add_message("added new Nagios_check_command name '$new_name' to $this->name $this->add_str","ok",1);
                        $all_nag_names[]=$new_name;
                        $this->add_nagios($new_name,$new_descr,$ins,$new_st,$new_cline);
                    } else {
                        $log_stack->add_message("cannot add new Nagios_check_command name '$new_name' to $this->name $this->add_str","SQL-Error",0);
                    }
                }
            } else {
                $log_stack->add_message("cannot add new Nagios_check_command to $this->name $this->add_str","empty name/command line",0);
            }
        }
    }
    function check_for_new_snmp(&$vars,$log_stack,&$all_snmp_mibs) {
        $my_pfix=$this->compose_prefix();
        if (is_set("{$my_pfix}s_new",&$vars)) {
            $add_it=1;
            $new_snmp_mib=$vars["{$my_pfix}s_new"];
            foreach ($this->snmp as $idx=>$s2) {
                if ($s2->value == $new_snmp_mib) {
                    $add_it=0;
                    $log_stack->add_message("Cannot add SNMP-MIB '{$all_snmp_mibs[$new_snmp_mib]->descr}' to $this->name","already set",0);
                }
            }
            if ($add_it) {
                $ins=insert_table("snmp_config","0,$this->config_idx,$new_snmp_mib,$this->dev_idx,null");
                if ($ins) {
                    $log_stack->add_message("added new SNMP config to $this->name $this->add_str","ok",1);
                    $this->add_snmp($new_snmp_mib,$ins);
                } else {
                    $log_stack->add_message("cannot add new SNMP variable to $this->name $this->add_str","SQL-Error",0);
                }
            }
        }
    }
    function check_for_var_change(&$vars,$log_stack) {
        $my_pfix=$this->compose_prefix();
        foreach (array("int","str","blob") as $var_type) {
            foreach ($this->$var_type as $var_idx=>$var_stuff) {
                if (is_set($var_stuff->compose_prefix($my_pfix)."_del",&$vars)) {
                    $log_stack->add_message("deleted variable called $var_stuff->name from config '$this->name' $this->add_str","ok",1);
                    query("DELETE FROM config_$var_type WHERE config_{$var_type}_idx=$var_idx");
                    unset($this->{$var_type}[$var_idx]);
                } else {
                    $this->{$var_type}[$var_idx]->check_for_change($my_pfix,&$vars,&$log_stack,"(config $this->name) $this->add_str",&$this->all_names);
                }
            }
        }
    }
    function check_for_nagios_change(&$vars,$log_stack,$all_nag_names) {
        $my_pfix=$this->compose_prefix();
        foreach ($this->nagios as $nag_idx=>$nag_stuff) {
            if (is_set($nag_stuff->compose_prefix($my_pfix)."_del",&$vars)) {
                $log_stack->add_message("deleted Nagios_check_command called {$nag_stuff->name} from config '$this->name' $this->add_str","ok",1);
                query("DELETE FROM ng_check_command WHERE ng_check_command_idx=$nag_idx");
                unset($this->nagios[$nag_idx]);
            } else {
                $this->nagios[$nag_idx]->check_for_change($my_pfix,&$vars,&$log_stack,"(config $this->name) $this->add_str",&$all_nag_names);
            }
        }
    }
    function check_for_snmp_change(&$vars,$log_stack,&$all_snmp_mibs) {
        $my_pfix=$this->compose_prefix();
        foreach ($this->snmp as $snmp_idx=>$snmp_stuff) {
            if (is_set($snmp_stuff->compose_prefix($my_pfix)."_del",&$vars)) {
                $log_stack->add_message("deleted SNMP-MIB '{$all_snmp_mibs[$snmp_stuff->value]->descr}' from config '$this->name' $this->add_str","ok",1);
                query("DELETE FROM snmp_config WHERE snmp_config_idx=$snmp_idx");
                unset($this->snmp[$snmp_idx]);
            } else {
                $this->snmp[$snmp_idx]->check_for_change($my_pfix,&$vars,&$log_stack,"(config $this->name) $this->add_str",&$all_snmp_mibs);
            }
        }
    }
    function add_variable($var_type,$name,$descr,$value,$var_idx) {
        $this->all_names[]=$name;
        $this->{$var_type}[$var_idx]=new config_variable($var_type,$name,$descr,$value,$var_idx);
    }
    function add_nagios($name,$descr,$ng_check_command_idx,$ng_service_templ,$command_line) {
        $this->all_names[]=$name;
        $this->nagios[$ng_check_command_idx]=new config_nagios($name,$descr,$ng_check_command_idx,$ng_service_templ,$command_line);
        //pprint_r(get_object_vars($this->nagios[$ng_check_command_idx]));
    }
    function add_snmp($snmp_mib,$snmp_config_idx) {
        $this->snmp[$snmp_config_idx]=new config_snmp($snmp_mib,$snmp_config_idx);
    }
    function get_nagios_names() {
        $n_n=array();
        foreach ($this->nagios as $idx=>$stuff) $n_n[]=$stuff->get_name();
        return $n_n;
    }
    // outputs the html-mask
    function print_html_mask($global,$config_vts,$nag_service_templates,$all_snmp_mibs) {
        $r_size=$this->get_number_of_lines()+3;
        $my_pfix=$this->compose_prefix();
        echo "<tr><td class=\"name\" colspan=\"6\" >$this->name, ";
        if ($global) {
            echo "del: <input type=checkbox name=\"{$my_pfix}_del\" />, \n";
            echo "pri: <input name=\"{$my_pfix}_pri\" maxlength=\"7\" size=\"4\" value=\"$this->priority\" />, \n";
            echo "<input name=\"{$my_pfix}_descr\" maxlength=\"160\" size=\"40\" value=\"".my_html_encode($this->descr)."\" />";
        } else {
            echo $this->descr;
        }
        echo "</td></tr>\n";
        // variable stuff
        $num_vars=$this->get_number_of_vars();
        if ($num_vars) {
            echo "<td class=\"group\" rowspan=\"$num_vars\" >Vars</td>\n";
            $line_num=0;
            foreach (array("int","str","blob") as $cn) {
                foreach ($this->$cn as $var_idx=>$var_stuff) {
                    if ($line_num++) echo "<tr>";
                    $var_stuff->print_html_mask($my_pfix,$config_vts);
                    echo "</tr>\n";
                }
            }
        }
        if ($num_vars) echo "<tr>";
        echo "<td class=\"delnew\" colspan=\"2\" >NewVar:<input type=checkbox name=\"{$my_pfix}v_new\" /></td>\n";
        echo "<td class=\"type\">";
        echo "<select name=\"{$my_pfix}v_newtype\">";
        foreach ($config_vts as $short=>$long){
            echo "<option value=\"$short\">$long</option>\n";
        }
        echo "</select>";
        echo "</td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}v_newname\" maxlength=\"30\" size=\"30\" /></td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}v_newval\" maxlength=\"120\" size=\"30\" /></td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}v_newdescr\" maxlength=\"250\" size=\"50\" /></td>";
        echo "</tr>\n";
        // Nagios stuff
        $num_nags=$this->get_number_of_nagios();
        if ($num_nags) {
            echo "<td class=\"group\" rowspan=\"$num_nags\" >Nag</td>\n";
            $line_num=0;
            foreach ($this->nagios as $var_idx=>$var_stuff) {
                if ($line_num++) echo "<tr>";
                $var_stuff->print_html_mask($my_pfix,$nag_service_templates);
                echo "</tr>\n";
            }
        }
        if ($num_nags) echo "<tr>";
        echo "<td class=\"delnew\" colspan=\"2\">NewNag:<input type=checkbox name=\"{$my_pfix}n_new\" /></td>\n";
        echo "<td class=\"type\"><select name=\"{$my_pfix}n_new_templ\" >\n";
        foreach ($nag_service_templates as $n_idx=>$n_stuff) {
            if ($n_idx) {
                echo "<option value=\"$n_idx\">$n_stuff->name</option>\n";
            } else {
                echo "<option value=\"$n_idx\">$n_stuff</option>\n";
            }
        }
        echo "</select></td>\n";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}n_new_name\" maxlength=\"20\" size=\"20\" /></td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}n_new_descr\" maxlength=\"64\" size=\"30\" /></td>";
        echo "<td class=\"netl\"><input name=\"{$my_pfix}n_new_comline\" maxlength=\"255\" size=\"50\" /></td>";
        echo "</tr>\n";
        // SNMP stuff
        $num_snmps=$this->get_number_of_snmp();
        if ($num_snmps) {
            echo "<td class=\"group\" rowspan=\"$num_snmps\" >SNMP</td>\n";
            $line_num=0;
            foreach ($this->snmp as $var_idx=>$var_stuff) {
                if ($line_num++) echo "<tr>";
                $var_stuff->print_html_mask($my_pfix,$all_snmp_mibs);
                echo "</tr>\n";
            }
        }
        if ($num_snmps) echo "<tr>";
        echo "<td class=\"delnew\" colspan=\"2\">NewSNMP:</td>\n";
        echo "<td class=\"netl\" colspan=\"4\"><select name=\"{$my_pfix}s_new\" >";
        echo "<option select value=\"0\">None</option>\n";
        foreach ($all_snmp_mibs as $idx=>$snmp_stuff) {
            echo "<option value=\"$idx\">$snmp_stuff->name (MIB $snmp_stuff->mib)</option>\n";
        }
        echo "</select></td>\n";
        echo "</tr>\n";
    }
    function get_number_of_vars() {
        $num_vars=count($this->str)+count($this->int)+count($this->blob);
        foreach ($this->str as $key=>$value) {
            if ($value->multiline) $num_vars++;
        }
        return $num_vars;
    }
    function get_number_of_nagios() {
        return count($this->nagios);
    }
    function get_number_of_snmp() {
        return count($this->snmp);
    }
    // returns number of lines needed for the webinterface (vars/nagios/snmp)
    function get_number_of_lines() {
        return $this->get_number_of_vars()+$this->get_number_of_nagios()+$this->get_number_of_snmp();
    }
}
// get global configs
function get_glob_configs($conf_list=array(),$config_type="") {
    if (count($conf_list)) {
        $sel_str=" AND (c.name='".implode("' OR c.name='",$conf_list)."')";
    } else {
        $sel_str="";
    }
    if ($config_type) {
        $sel_str.=" AND ct.identifier='$config_type'";
    }
    // parse configs
    $configs=array();
    $mres=query("SELECT c.name,c.descr,c.config_type,c.priority,c.config_idx FROM config c, config_type ct WHERE c.config_type=ct.config_type_idx $sel_str ORDER BY c.config_type,c.priority DESC");
    while ($mfr=mysql_fetch_object($mres)) {
        $configs[$mfr->name]=new config($mfr->name,$mfr->descr,$mfr->config_type,$mfr->priority,$mfr->config_idx);
    }
    foreach (array(array("str","cs"),array("int","ci"),array("blob","cb")) as $stuff) {
        list($long,$short)=$stuff;
        $mres=query("SELECT {$short}.name,{$short}.descr,{$short}.value,{$short}.config,{$short}.config_{$long}_idx as idx, c.name as cname FROM config c,config_type ct, config_$long $short WHERE c.config_type=ct.config_type_idx AND {$short}.config=c.config_idx AND {$short}.device=0 $sel_str");
        while ($mfr=mysql_fetch_object($mres)) {
            $configs[$mfr->cname]->add_variable($long,$mfr->name,$mfr->descr,$mfr->value,$mfr->idx);
        }
    }
    // nagios stuff
    $mres=query("SELECT c.name as cname, n.* FROM ng_check_command n, config c, config_type ct WHERE ct.config_type_idx=c.config_type AND n.config=c.config_idx AND n.device=0 $sel_str");
    while ($mfr=mysql_fetch_object($mres)) {
        $configs[$mfr->cname]->add_nagios($mfr->name,$mfr->description,$mfr->ng_check_command_idx,$mfr->ng_service_templ,$mfr->command_line);
    }
    // snmp stuff
    $mres=query("SELECT c.name as cname, s.* FROM snmp_config s, config c, config_type ct WHERE ct.config_type_idx=c.config_type AND s.config=c.config_idx AND s.device=0 $sel_str");
    while ($mfr=mysql_fetch_object($mres)) {
        $configs[$mfr->cname]->add_snmp($mfr->snmp_mib,$mfr->snmp_config_idx);
    }
    //print_r($configs);
    return $configs;
}
function get_log_status() {
    $mres=query("SELECT * FROM log_status ORDER BY log_level DESC");
    $ls=array();
    while ($mfr=mysql_fetch_object($mres)) {
        $ls[$mfr->identifier]=$mfr;
    }
    return $ls;
}
function get_log_targets() {
    $mres=query("SELECT de.name,d.device,COUNT(DISTINCT d.date) AS logcount FROM devicelog d LEFT JOIN device de ON d.device=de.device_idx GROUP BY de.name");
    $lts=array();
    while ($mfr=mysql_fetch_object($mres)) {
        $lts[$mfr->device]=$mfr;
    }
    return $lts;
}
function get_device_classes() {
    // parse device_classes
    $mres=query("SELECT h.* FROM device_class h ORDER BY priority");
    $device_classes=array();
    $device_classes[0]->classname="unset";
    $device_classes[0]->name="unset";
    while ($mfr=mysql_fetch_object($mres)) {
	// make a copy for clusterconfig-page
	$mfr->name=$mfr->classname;
	$device_classes[$mfr->device_class_idx]=$mfr;
    }
    return $device_classes;
}
function get_device_locations() {
    // parse device locations
    $mres=query("SELECT h.* FROM device_location h");
    $device_locations=array();
    $device_locations[0]->location="unset";
    $device_locations[0]->name="unset";
    while ($mfr=mysql_fetch_object($mres)) {
	// make a copy for clusterconfig-page
	$mfr->name=$mfr->location;
	$device_locations[$mfr->device_location_idx]=$mfr;
    }
    return $device_locations;
}
?>
