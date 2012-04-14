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
    clusterhead($sys_config,"Nagios",$style="formate.css");
    $ucl=usercaps();
    //echo "<body class=\"nagios\">";
    echo "<div class=\"center\">";
    echo "<a class=\"init\" href=\"http://www.init.at\" target=\"main\"><img alt=\"Init.at logo\" src=\"/icons-init/kopflogo.png\" border=0></a>";
    echo "</div>";

    echo "<table class=\"normal\">";
    echo "<tr><th class=\"nagios\">--General--</th></tr>\n";
    echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"nagiosmain.php?".write_sid()."\" target=\"main\">Nagios Home</a></td></tr>\n";
    echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"../old_index.php?".write_sid()."\" target=\"_top\">Back to main page</a></td></tr>\n";
    echo "</table>\n";
    if ($ucl["na"]) {
        echo "<table class=\"normal\">";
        echo "<tr><th class=\"nagios\">--Monitoring--</th></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/tac.cgi\" target=\"main\">Tactical Overview</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?host=all\" target=\"main\">Service detail</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?hostgroup=all&style=hostdetail\" target=\"main\">Host Detail</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?hostgroup=all\" target=\"main\">Status Overview</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?hostgroup=all&style=summary\" target=\"main\">Status Summary</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?hostgroup=all&style=grid\" target=\"main\">Status Grid</a></td></tr>\n";
        echo "</table>\n";
    }
    if ($ucl["nap"]) {
        echo "<table class=\"normal\">";
        echo "<tr><th class=\"nagios\">--Problems--</th></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?host=all&servicestatustypes=248\" target=\"main\">Service problems</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/status.cgi?hostgroup=all&style=hostdetail&hoststatustypes=12\" target=\"main\">Host problems</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/outages.cgi\" target=\"main\">Network outages</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/statusmap.cgi?host=all\" target=\"main\">Status map</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/extinfo.cgi?&type=3\" target=\"main\">Network health</a></td></tr>\n";
        echo "</table>\n";
    }
    if ($ucl["nai"]) {
        echo "<table class=\"normal\">";
        echo "<tr><th class=\"nagios\">--Other stuff--</th></tr>\n";
        if (is_dir("/usr/local/nagios/shared/docs")) {
            echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/docs/index.html\" target=\"main\">Documentation</a></td></tr>\n";
        }
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/trends.cgi\" target=\"main\">Trends</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/avail.cgi\" target=\"main\">AvailabilityTrends</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/histogram.cgi\" target=\"main\">Alert Histogram</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/history.cgi?host=all\" target=\"main\">Alert history</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/summary.cgi\" target=\"main\">Alert Summary</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/notifications.cgi?contact=all\" target=\"main\">Notifications</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/showlog.cgi\" target=\"main\">Event Log</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/config.cgi\" target=\"main\">View Config</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/extinfo.cgi?&type=3\" target=\"main\">Comments</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/extinfo.cgi?&type=6\" target=\"main\">Downtime</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/extinfo.cgi?&type=0\" target=\"main\">Process info</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/extinfo.cgi?&type=4\" target=\"main\">Performance Info</a></td></tr>\n";
        echo "<tr><td class=\"nagios\"><a class=\"nagios\" href=\"/nagios/cgi-bin/extinfo.cgi?&type=7\" target=\"main\">Scheduling Queue</a></td></tr>\n";
        echo "</table>";
    }
    writesimplefooter();
}
?>
