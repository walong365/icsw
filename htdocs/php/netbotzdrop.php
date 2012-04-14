<?php
//
// Copyright (C) 2001,2002,2003,2004,2007 Andreas Lang, init.at
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

foreach ($_FILES as $key=>$value) {
    move_uploaded_file($_FILES[$key]["tmp_name"], "/tmp/.nbdrop_picture");
}
foreach ($_POST as $key=>$value) {
    file_put_contents("/tmp/.nbdrop_post_$key", $value);
}
exec("/usr/local/bin/netbotz_drop.py");
// require_once "config.php";
// $vars = readgets();
// if (isset($vars["BOTZIP"])) {
//     $bip = $vars["BOTZIP"];
//     $time = $vars["BOTZTIME"];
//     $sensors_needed = array("TEMP", "HUMI", "AFLW");
//     $subs_needed = array("VALUE", "VALUEUNITS", "LABEL", "TYPE");
//     $sens_part = "";
//     for ($idx=0 ; $idx < intval($vars["NUMSENSORS"]) ; $idx++) {
//         $stype = $vars["SENSORTYPE_$idx"];
//         if (in_array($stype, $sensors_needed)) {
//             foreach ($subs_needed as $sp1) {
//                 $varname = "SENSOR{$sp1}_$idx";
//                 $sens_part.=":$stype;$sp1;$vars[$varname]";
//             }
//         }
//     }
//     foreach ($HTTP_POST_FILES as $key=>$value) {
//         move_uploaded_file ($HTTP_POST_FILES[$key]["tmp_name"], "/srv/www/htdocs/nb-pics/$bip/actual");
//     }
//     $sc="/usr/local/sbin/send_command.py";
//     $ret=exec("$sc -c localhost 8002 \"NETBOTZ:$bip:{$time}{$sens_part}\"");
//     if (file_exists("/etc/ext_netbotz_hosts")) {
//         $ext_hosts=file("/etc/ext_netbotz_hosts");
//         foreach ($ext_hosts as $ext_host) {
//             $ret=exec("$sc -c ".trim($ext_host)." 8002 \"NETBOTZ:$bip:{$time}{$sens_part}\"");
//         }
//     }
// }
?>
