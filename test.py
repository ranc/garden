import sys
from multiprocessing.connection import Client
from server import Client

with Client('10.0.0.12') as conn:
    # just wake the accept to catch the stop
    while True:
        inp = input(">")+"\n"
        conn.sendall(inp.encode('utf-8'))
        res = conn.recv(16384).decode('utf-8')
        if not res:
            break
        print(res)
