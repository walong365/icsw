<?php
// Auto-config of frontend-capabilities: start with //-*ics*-<spaces> ;
// then: delimeter (for example +); then type which can be one of CAP
// then: list of key/value pairs
// for example:
// 
//-*ics*- ,CAP,name:'na',defvalue:1,enabled:1,descr:'Access Nagios',scriptname:'/php/nagiosindex.php',left_string:'Nagios',right_string:'Nagios',capability_group_name:'info',pri:-40
//-*ics*- ,CAP,name:'nap',defvalue:0,enabled:1,descr:'Access Nagios problems',mother_capability_name:'na'
//-*ics*- ,CAP,name:'nai',defvalue:0,enabled:1,descr:'Access Nagios internas',mother_capability_name:'na'
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
require_once "mysql.php";
require_once "config.php";
$vars=readgets();
if ($sys_config["ERROR"] == 1) {
  errorpage("No configfile.");
} else if (! $sys_config["na_en"] == 1) {
  errorpage("You are not allowed to view this page.");
} else if (! $sys_config["SESSION"]) {
  errorpage("You are currently not logged in.");
} else {
  if (isset($sys_config["AUTO_RELOAD"])) unset($sys_config["AUTO_RELOAD"]);
  htmlhead();
  clusterhead($sys_config,"Nagios Network Monitor",$style="formate.css");
  echo "<frameset border=\"0\" frameborder=\"0\" framespacing=\"0\" cols=\"180,*\">";
  echo "<frame src=\"nagiosside.php?".write_sid()."\" name=\"side\" target=\"main\">";
  echo "<frame src=\"nagiosmain.php?".write_sid()."\" name=\"main\">";
  echo "</frameset>";
  writesimplefooter($sys_config);
}
?>
