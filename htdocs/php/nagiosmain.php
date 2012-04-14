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
  clusterbody($sys_config,"Nagios",array(),array(),1);
  echo "<div class=\"center\">";
  echo "<img src=\"/nagios/images/logofullsize.jpg\" border=\"0\" alt=\"Nagios\"><br>";
  echo "Copyright (c) 1999-2004 Ethan Galstad";
  echo "</div>";

  echo "<div class=\"center\">Nagios {$sys_config['NAGIOS_VERSION']}</div>";

  writesimplefooter($sys_config);
}
?>
