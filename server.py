import errno
import socket
import threading
import logging
from typing import Dict


class ClientAgent(threading.Thread):            
    client_id_count = 0
    id: int

    def __init__(self, conn: socket.socket, server: 'Server'):
        super().__init__()
        ClientAgent.client_id_count += 1
        self.conn = conn
        self.server = server
        self.id = ClientAgent.client_id_count
        self.logger = logging.getLogger('agent')
        self.logger.debug(f"Agent {self.id} created")
        #print("new agent")

    def exec(self, inp: str) -> bool:
        self.logger.debug(f"got: '{inp}'")
        r = inp.strip().split()
        if len(r)==0:
            self.conn.sendall("\n".encode('utf-8'))
            return
        cmd = r[0]
        args = r[1:]
        if cmd == "Close" or cmd == "DummyClose":
            self.conn.close()
            return False
        if cmd.lower() == "stop":
            self.conn.close()
            self.server.stop_server()
            if 'stop' in self.server.commands:
                self.server.commands['stop']()
            return False
        
        self.logger.debug(f"got command:{cmd}({args})")
        if cmd in self.server.commands:
            try:
                res = str(self.server.commands[cmd](args))
                if res:
                    res += "\n"
                else:
                    res = "\n"
            except Exception as e:
                res = f"Error: {e}\n"
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
                
            #print("Agent done...")

        except EOFError:
            self.logger.warning(f"Client {self.id} misbehaved and did not close nicely")
        
        self.conn.close()
        if self.id in self.server.agents:
            del self.server.agents[self.id]
        return

HOST = '0.0.0.0'  
PORT = 5555    

class Client(socket.socket):
    def __init__(self, host = HOST, port=PORT) -> None:
        super().__init__(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((host, port))


class Server:
    agents:  Dict[int, ClientAgent]
    
    def __init__(self, commands) -> None:                
        self.stop = False
        self.logger = logging.getLogger('server')
        self.commands = commands
        self.agents = {}
        
    def wait_for_clients(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen()
            while not self.stop:
                #print("waiting for new clients...")
                try:
                    conn, _ = s.accept()
                    agent = ClientAgent(conn, self)
                    agent.start()
                    self.agents[agent.id] = agent
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
        with Client(HOST, PORT) as conn:
            # just wake the accept to catch the stop
            conn.send('DummyClose'.encode('utf-8'))
        for agent in list(self.agents.values()):
            agent.stop = True
            agent.conn.close()
            #agent.join()