<?php
 header("Location: /");

 if (@$_GET["clear"]!==null)
 {
   unlink("/tmp/override");
   return;
 }

 $min=@$_GET["min"];
 if (!$min) {
   $hour=@$_GET["hour"];
   if ($hour) $min=$hour*60;
 }
 if (!$min) {
   echo "No time paramter\n";
   return;
 }

$is_on = @$_GET["on"]!==null;
$is_off = @$_GET["off"]!==null;

$ctrl="/sys/class/gpio/gpio4/value";

if ($is_on) {
   $cmd = "$min on";
   file_put_contents($ctrl, "0");
} else if ($is_off) {
   $cmd = "$min off";
   file_put_contents($ctrl, "1");
} else {
   echo "Specify on or off";
}
file_put_contents("/tmp/override", $cmd);
?>
