
<html>
<head>
        <title>Garden Control Center</title>
</head>
<body style="width:100%">
<pre>
<?php
$pipe = fopen("/home/pi/pipe","w");
fwrite($pipe,"hello\n");
fclose($pipe);
$pipe = fopen("/home/pi/pipe","r");
echo("I got: ".fgets($pipe));
fclose($pipe);
?>
</pre>
</body>
</html>

