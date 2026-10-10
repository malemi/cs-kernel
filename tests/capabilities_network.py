from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path


def restrict_network(log_path):
    log_path = Path(log_path)

    def check(host):
        allowed = host == 'localhost'
        try:
            allowed = allowed or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if not allowed:
            with log_path.open('a') as stream:
                stream.write(json.dumps({'attempt': 'nonloopback', 'host': str(host)}) + '\n')
            raise RuntimeError('CLI fixture refuses nonloopback network access')

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo
    original_gethostbyname = socket.gethostbyname
    original_gethostbyname_ex = socket.gethostbyname_ex
    original_gethostbyaddr = socket.gethostbyaddr

    def connect(sock, address):
        check(address[0] if isinstance(address, tuple) else address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address[0] if isinstance(address, tuple) else address)
        return original_connect_ex(sock, address)

    def sendto(sock, *args):
        address = args[-1]
        check(address[0] if isinstance(address, tuple) else address)
        return original_sendto(sock, *args)

    def getaddrinfo(host, *args, **kwargs):
        check(host)
        return original_getaddrinfo(host, *args, **kwargs)

    def gethostbyname(host):
        check(host)
        return original_gethostbyname(host)

    def gethostbyname_ex(host):
        check(host)
        return original_gethostbyname_ex(host)

    def gethostbyaddr(host):
        check(host)
        return original_gethostbyaddr(host)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.getaddrinfo = getaddrinfo
    socket.gethostbyname = gethostbyname
    socket.gethostbyname_ex = gethostbyname_ex
    socket.gethostbyaddr = gethostbyaddr
