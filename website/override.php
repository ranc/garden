<?php
 header("Location: /");

$vlv=@$_GET["valve"];
if ($vlv == null)
{
   echo "No valve\n";
   http_response_code(401);
   return;
}

 if (@$_GET["off"]!==null)
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

$srvr = "127.0.0.1";
$port = 5555;

$sock=socket_create(AF_INET,SOCK_STREAM,0) or die("Cannot create a socket");
socket_connect($sock,$srvr,$port) or die("Could not connect to the socket");

socket_write($sock,"override $vlv $dur\n");
$json_txt=socket_read($sock,1024, PHP_NORMAL_READ);
socket_close($sock);
echo "Got from server: $json_txt";
?>
