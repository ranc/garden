import sys
from multiprocessing.connection import Client
from garden_server import Client

with Client() as conn:
    # just wake the accept to catch the stop
    while True:
        inp = input(">")+"\n"
        conn.sendall(inp.encode('utf-8'))
        res = conn.recv(16384).decode('utf-8')
        if not res:
            break
        print(res)
