<?php
header("Content-type: image/png");
$width =$_GET["x"];
$height=$_GET["y"];
$perc  =$_GET["perc"];
$red_val  =200*$perc/100;
$green_val=240*(100-$perc)/100.;
$im      =imagecreate($width,$height);
$grey    =imagecolorallocate($im,0,0,0);
$rect_col=imagecolorallocate($im,$red_val,$green_val,50);
$white  = imagecolorallocate($im, 250,250,250);
imagefilledrectangle($im,0,0,$width*$perc/100,$height,$rect_col);
$px     = (imagesx($im) - 7.5 * strlen($perc)) / 2;
//imagestring($im, 4, $px, $height/2-7, "$perc %", $white);
imagepng($im);
imagedestroy($im);
?>
