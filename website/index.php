<html>
<head>
	<title>Garden Control Center</title>
</head>
<body style="width:100%">
<style>
h1 {
width:100%;
font-size: 48px;
}
.on {
background: orange;
}
.off {
background: blue;
}
td {
  padding: 5px;
}

</style>
<h1>Welcome to the Garden Control Center</h1>
<?php
echo "Local time is now:".strftime("%T");
$srvr = "127.0.0.1";
$port = 5555;

$sock=socket_create(AF_INET,SOCK_STREAM,0) or die("Cannot create a socket");
socket_connect($sock,$srvr,$port) or die("Could not connect to the socket");

socket_write($sock,"get\n");
$json_txt=socket_read($sock,1024, PHP_NORMAL_READ);
$read=json_decode($json_txt);

socket_write($sock,"ovl\n");
$ovl=json_decode(socket_read($sock,1024, PHP_NORMAL_READ));
socket_close($sock);
$arr = $read

?>
<h3>Daily schedule below:</h3>
<table border="1" style="border: 1px black;">
<tr><th>Valve</th><th>Day</th><th>Start Time</th><th>Duration</th></tr>
<?php

  function time2clock($time) {
    $hour = intval($time/3600);
    $tsec = $time-3600*$hour;
    $min = intval($tsec/60);
    $sec = intval($tsec-$min*60);
    return [$hour, $min, $sec];
  }
  function clock2str($clk)
  {
    return sprintf("%'.02d",$clk[0]).":".sprintf("%'.02d",$clk[1]).":".sprintf("%'.02d",$clk[2]);
  }

  $days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  foreach ($arr as $v) {    
    $vlv = $v->valve_no;
    $day = $days[$v->sched_day];
    $clk = time2clock($v->start_time);
    $duration = $v->duration;
    if ($duration<60)
    {
       $duration = $duration." sec";
    } else {
       $dmin = intval($duration/60);
       $dsec = $duration-$dmin*60;
       $duration = $dmin.":".sprintf("%'.02d",$dsec);
    }
    echo "<tr><td>$vlv</td><td>$day</td><td>".clock2str($clk)."</td><td>$duration</td></tr>";
  }
?>
</table>

<h3>Override list:</h3>
<table border="1" style="border: 1px black;">
<tr>
  <th>Valve</th>
  <th>Start Time</th>
  <th>End Time</th>
  <th>Duration</th>
  <th>Left to finish</th>
</tr>
<?php
  foreach ($ovl as $v) {
    $vlv = $v->valve_no;
    $duration = $v->duration;
    $start_clk = time2clock($v->start_time);
    $end_clk = time2clock($v->start_time+$duration);
    $left = $v->left;
?>
<tr>
  <td><?=$vlv?></td>
  <td><?=clock2str($start_clk)?></td>
  <td><?=clock2str($end_clk)?></td>
  <td><?=$duration?></td>
  <td><?=$left?></td>
  <td><a href="/override.php?valve=<?=$vlv?>&off">X</a></td>
</tr>
<?php
  }
?>
</table>


<h3>For manuall on/off click the links below:</h3>
<table border="1">
<?php
  for ($i = 1; $i < 8; $i++) {
?>
<tr>
   <td><?=$i?></td>
   <?php foreach ([3, 10, 60, 120, 600] as $d) { ?>
     <td>
        <a href="/override.php?valve=<?=$i?>&d=<?=$d?>"><?=$d?> sec</a>
     </td>
   <?php } ?>
</tr>
<?php } ?>
</table>
<br/><br/>

<a href="/override.php?on=0">ON 0</a>
<a href="/override.php?off=0">OFF 0</a>
<br/><br/>

<a href="/override.php?on=1">ON 1</a>
<a href="/override.php?off=1">OFF 1</a>
