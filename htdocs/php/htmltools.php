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
class messagelog {
    var $mes;
    function messagelog() {
        $this->mes=array();
    }
    // state is 1 for OK and 0 for error, 2 for warning
    function add_message($command,$result,$state) {
        $this->mes[]=array($command,$result,$state);
    }
    function get_num_errors() {
        $num=0;
        foreach ($this->mes as $mstuff) {
            if (!$state) $num++;
        }
        return $num;
    }
    function get_num_messages() {
        return count($this->mes);
    }
    function print_messages($title="Messages") {
        if ($this->get_num_messages()) {
            if ($title) message($title,$type=1);
            echo "<table class=\"normalnf\">\n";
            echo "<tr>";
            echo "<th class=\"name\">Info</th>";
            echo "<th class=\"return\">return</th>";
            echo "<th class=\"success\">Success</th>";
            echo "</tr>";
	    $state_f=array(0=>array("succerr","Error"),
			   1=>array("succok","OK"),
			   2=>array("succwarn","Warning"));
            foreach ($this->mes as $mstuff) {
                list($command,$result,$state)=$mstuff;
                echo "<tr>";
                echo "<td class=\"name\">$command</td>";
                echo "<td class=\"return\">$result</td>";
		echo "<td class=\"{$state_f[$state][0]}\">{$state_f[$state][1]}</td>";
                echo "</tr>\n";
            }
            echo "</table>";
        }
    }
}
class messagestack {
    var $strs,$num_lines,$num_errors;
    function messagestack() {
        $this->strs=array();
        $this->num_lines=0;
        $this->num_errors=0;
    }
    function get_num_errors() {
        return $this->num_errors;
    }
    function addstr($str,$error=1) {
        $this->num_lines++;
        if (substr($str,0,1)=="@") {
            $this->strs[]=array(substr($str,1),0);
        } else {
            $this->strs[]=array($str,$error);
            if ($error) $this->num_errors++;
        }
    }
    function savestack($file) {
        if ($this->get_num_errors()) {
            $tf=fopen($file,"a+");
            $outstr=sprintf("%d Errors from %s :",$this->get_num_errors(),date("D j. M Y, G:i:s"));
            fwrite($tf,$outstr."\n");
            fwrite($tf,str_repeat("-",strlen($outstr))."\n");
            $idx=0;
            foreach ($this->strs as $str) {
                list($out_str,$error)=$str;
                fwrite($tf,sprintf("%2d %s\n",++$idx,$out_str));
            }
            fclose($tf);
        }
    }
    function printstack($title="Messages") {
        if (sizeof($this->strs)) {
            message($title,$type=1);
            echo "<table class=\"user\">\n";
            $idx=0;
            foreach ($this->strs as $str) {
                list($out_str,$error)=$str;
                echo "<tr><td class=\"left\">";
                if ($error) {
                    $idx++;
                    echo $idx;
                    $pf_str="";
                } else {
                    echo "&nbsp;";
                    $pf_str="- ";
                }
                echo "</td><td class=\"left\">$pf_str$out_str</td></tr>\n";
            }
            echo "</table>\n";
        }
    }
}
function message($str,$type=0) {
    if ($type==0) {
        echo "<h2>$str</h2>";
    } else if ($type==1) {
        echo "<h3>$str</h3>";
    } else if ($type==2) {
        echo "<h4>$str</h4>";
    } else {
        echo "<h2>Wrong type</h2>";
    }
    echo "\n";
}
function get_plural($str,$num,$show_num=0) {
    if ($show_num) {
        $rstr="$num $str";
    } else {
        $rstr=$str;
    }
    if ($num != 1) $rstr.="s";
    return $rstr;
}
function get_rand_str() {
    mt_srand ((double) microtime() * 1000000);
    $r_seed="";
    for ($i=0;$i<7;$i++) $r_seed.=chr(mt_rand(65,65+24));
    return $r_seed;
}
function un_quote($str) {
    return strtr(trim($str),array('\"'=>'"',"\\\\"=>"\\","\'"=>"'"));
}
function is_positive_integer($val) {
    if (is_numeric($val) && intval($val) > 0) {
        return 1;
    } else {
        return 0;
    }
}
function is_positive_float($val) {
    if (is_numeric($val) && floatval($val) > 0) {
        return 1;
    } else {
        return 0;
    }
}
function show_opt_list_simple($var_name,$var_list,$var_sel,$td_class="") {
    if ($td_class) echo "<td class=\"$td_class\">";
    // display a select-table named '$var_name' from var_list [a] as (a)->a
    echo "<select name=\"$var_name\">";
    foreach ($var_list as $var_line) {
	echo "<option value=\"$var_line\" ";
	if ($var_line == $var_sel) echo " selected ";
	echo ">$var_line</option>\n";
    }
    echo "</select>\n";
    if ($td_class) echo "</td>\n";
}
function show_opt_list($var_name,$var_list,$short_sel,$td_class="") {
    if ($td_class) echo "<td class=\"$td_class\">";
    // display a select-table named '$var_name' from var_list [a]->b as (value b)->a
    // select if b==$short_sel
    echo "<select name=\"$var_name\">";
    foreach ($var_list as $long=>$short) {
        echo "<option value=\"$short\" ";
        if ($short == $short_sel) echo " selected ";
        echo ">$long</option>\n";
    }
    echo "</select>\n";
    if ($td_class) echo "</td>\n";
}
function show_opt_list2($var_name,$var_list,$short_sel,$td_class="") {
    if ($td_class) echo "<td class=\"$td_class\">";
    // display a select-table named '$var_name' from var_list [a]->b as (value b)->a
    // select if a==$short_sel
    echo "<select name=\"$var_name\">";
    foreach ($var_list as $short=>$long) {
        echo "<option value=\"$short\" ";
        if ($short == $short_sel) echo " selected ";
        echo ">$long</option>\n";
    }
    echo "</select>\n";
    if ($td_class) echo "</td>\n";
}
function my_html_encode($str) {
    return htmlentities($str,ENT_QUOTES);
}
function my_html_decode($str) {
    if (version_compare(phpversion(),"4.3.0") == -1) {
        // pre-PHP 4.3.0 Code
        $trans_tbl=get_html_translation_table(HTML_ENTITIES);
        $trans_tbl=array_flip($trans_tbl);
        return un_quote(strtr($str,$trans_tbl));
    } else {
        // PHP 4.3.0 Code (and above)
        return un_quote(html_entity_decode($str,ENT_NOQUOTES));
    }
}
?>
