<?php
header("Location: /");

$vlv = @$_GET["valve"];
$off = @$_GET["off"];
$on  = @$_GET["on"];
echo "<pre>$vlv / $off / $on</pre>";

if (!$vlv)
{
  if ($on != null) {
    $cmd = "on $on\n";
  } elseif ($off != null) {
    $cmd = "off $off\n";
  } else {
    echo "No valve\n";
    http_response_code(401);
    return;
  }
} else {
  if ($off)
  {
     $dur = 'off';   
  } else {
     $dur=@$_GET["d"];
     if (!$dur) {
       echo "Specify duration of 'off'\n";
       http_response_code(401);
       return;
     }
  }
  $cmd = "override $vlv $dur\n";
}

$srvr = "127.0.0.1";
$port = 5555;

$sock=socket_create(AF_INET,SOCK_STREAM,0) or die("Cannot create a socket");
socket_connect($sock,$srvr,$port) or die("Could not connect to the socket");

socket_write($sock, $cmd);
$json_txt=socket_read($sock,1024, PHP_NORMAL_READ);
socket_close($sock);
echo "Got from server: $json_txt";
?>
