import logging
import os
import errno
import socket
from telnetlib import SE
import threading

path = "/home/pi/pipe"
gpio_map=(18,27,22,23,24,25,4,2)

def setup(gpio:int):
    if os.name == 'nt':
        print("setting gpio")
        return
    gpiofile = f"/sys/class/gpio/export"
    with open(gpiofile, "w") as f:
        f.write(str(gpio_map[gpio]))
    gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/direction"
    with open(gpiofile, "w") as f:
        f.write("out")


def turn(gpio:int, is_on: bool):
    gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/value"
    if os.name == 'nt':
        print("setting gpio:", gpiofile, is_on)
        return
    if not os.path.exists(gpiofile):
        print("setting gpio", gpio_map[gpio])
        setup(gpio)
    with open(gpiofile, "w") as f:
        f.write('0' if is_on else '1')


COMMANDS = {
    'on': lambda args : turn(0, True),
    'off': lambda args: turn(0, False),
    'get': lambda args: ','.join(args)
}

class ClientAgent(threading.Thread):            
    client_id_count = 0
    def __init__(self, conn: socket.socket, server: 'Server'):
        super().__init__()
        ClientAgent.client_id_count += 1
        self.conn = conn
        self.server = server
        self.id = ClientAgent.client_id_count
        self.logger = logging.getLogger('agent')
        self.logger.debug(f"Agent {self.id} created")
        print("new agent")

    def exec(self, inp: str) -> bool:
        print(f"got: '{inp}'")
        r = str(inp).split()
        if len(r)==0:
            self.conn.sendall("\n".encode('utf-8'))
            return
        cmd = r[0]
        args = r[1:]
        if cmd == "Close" or cmd == "DummyClose":
            self.conn.close()
            return False
        if cmd == "StopServer":
            self.conn.close()
            self.server.stop_server()
            return False
        
        print("got command:", cmd, args)
        if cmd in COMMANDS:
            res = COMMANDS[cmd](args)
            if res:
                res += "\n"
            else:
                res = "\n"
            self.conn.sendall(res.encode('utf-8'))
        else:
            self.conn.sendall(f"Command {cmd} is not supported.".encode('utf-8'))
        return True

    def run(self):
        self.logger.info(f"Proccesing requests from: {self.id}")
        try:
            inp=""
            stop = False
            while not stop:
                data = self.conn.recv(4096)
                if len(data)==0:
                    break
                try:
                    recv = data.decode("utf-8")
                except UnicodeDecodeError:
                    print("not a unicode:", data)
                    continue
                
                bar = recv.find('\n')
                while bar>=0:                    
                    cmd = inp+recv[:bar]                    
                    if not self.exec(cmd):
                        stop = True
                        break
                    inp = ""
                    recv = recv[bar+1:]
                    bar = recv.find('\n')
                inp = inp + recv
                
            print("Agent done...")

        except EOFError:
            self.logger.warning(f"Client {self.id} misbehaved and did not close nicely")
            self.conn.close()
            return

HOST = '127.0.0.1'  
PORT = 5555    

class Client(socket.socket):
    def __init__(self) -> None:
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((HOST, PORT))

class Server:
    def __init__(self) -> None:                
        self.stop = False
        self.logger = logging.getLogger('server')
        
    def wait_for_clients(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            while not self.stop:
                print("waiting for new clients...")
                try:
                    conn, addr = s.accept()
                    ClientAgent(conn, self).start()
                except OSError:
                    break
                except KeyboardInterrupt:
                    print("Got Ctrl-C")
                    self.stop = True
                    break
            print("Server is closing...")

    def stop_server(self):
        self.logger.info("Request to stop server...")
        self.stop = True        
        # this is a hack, it works but ugly
        # self.listener._listener._socket.shutdown(SHUT_RDWR)
        with Client() as conn:
            # just wake the accept to catch the stop
            conn.send('DummyClose'.encode('utf-8'))

if __name__ == "__main__":
    setup(0)
    srv = Server()
    srv.wait_for_clients()
    

