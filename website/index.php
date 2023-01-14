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
$srvr = "10.0.0.12";
$port = 5555;

$sock=socket_create(AF_INET,SOCK_STREAM,0) or die("Cannot create a socket");
socket_connect($sock,$srvr,$port) or die("Could not connect to the socket");
socket_write($sock,"get\n");

$json_txt=socket_read($sock,1024, PHP_NORMAL_READ);
$read=json_decode($json_txt);
socket_close($sock);
$arr = $read
?>
<pre>
<?php
 echo $json_txt
?>
 
</pre>
<h3>Daily schedule below:</h3>
<table border="1" style="border: 1px black;">
<tr><th>Valve</th><th>Day</th><th>Start Time</th><th>Duration</th></tr>
<?php
  $days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  foreach ($arr as $v) {    
    $vlv = $v->valve_no;
    $day = $days[$v->sched_day];
    $hour = intval($v->start_time/3600);
    $tsec = $v->start_time-3600*$hour;
    $min = intval($tsec/60);
    $sec = intval($tsec-$min*60);
    $duration = $v->duration;
    if ($duration<60)
    {
       $duration = $duration." sec";
    } else {
       $dmin = intval($duration/60);
       $dsec = $duration-$dmin*60;
       $duration = $dmin.":".sprintf("%'.02d",$dsec);
    }
    echo "<tr><td>$vlv</td><td>$day</td><td>".sprintf("%'.02d",$hour).":".sprintf("%'.02d",$min).":".sprintf("%'.02d",$sec)."</td><td>$duration</td></tr>";
  }
?>
</table>
<h3>For manuall on/off click the links below:</h3>
<table border="1">
<tr><th class='off'>Turn Off</th><th class='on'>Turn On</th></tr>
<tr>
   <td>
      <a href="/setup.php?hour=1&off">1 hour</a>
   </td><td>
      <a href="/setup.php?hour=1&on">1 hour</a>
   </td>
</tr>
<tr>
   <td>
      <a href="/setup.php?hour=2&off">2 hour</a>
   </td><td>
      <a href="/setup.php?hour=2&on">2 hour</a>
   </td>
</tr>
<tr>
   <td>
      <a href="/setup.php?hour=4&off">4 hour</a>
   </td><td>
      <a href="/setup.php?hour=4&on">4 hour</a>
   </td>
</tr>
<tr>
   <td>
      <a href="/setup.php?hour=8&off">8 hour</a>
   </td><td>
      <a href="/setup.php?hour=8&on">8 hour</a>
   </td>
</tr>
</table>
<br/>
<b><a href="/setup.php?clear">Clear manual override</b>
<br/>
<br/>
<br/>
