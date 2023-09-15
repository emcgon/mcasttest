from time import time
import socket
import struct
import argparse

IS_ALL_GROUPS = True

def pretty(n):
    suffixes = ("b/s", "Kb/s", "Mb/s", "Gb/s")
    i = 0
    while (n > 1000):
        i += 1
        n /= 1000.0
    return(f"{round(n*100)/100}{suffixes[i]}")

parser = argparse.ArgumentParser(description='Join a multicast ground and listen for traffic')
parser.add_argument("group", action="store", help="Multicast group to join")
parser.add_argument("--source", action="store", help="Joint a particular source (SSM)")
parser.add_argument("port", action="store", help="UDP port to listen on")
args = parser.parse_args()

# Hack in support for SSM (see https://bugs.python.org/issue45252 and https://github.com/alexcraig/GroupFlow/blob/master/groupflow_scripts/ss_multicast_receiver.py)
if not hasattr(socket, "IP_UNBLOCK_SOURCE"):
    setattr(socket, "IP_UNBLOCK_SOURCE", 37)
if not hasattr(socket, "IP_BLOCK_SOURCE"):
    setattr(socket, "IP_BLOCK_SOURCE", 38)
if not hasattr(socket, "IP_ADD_SOURCE_MEMBERSHIP"):
    setattr(socket, "IP_ADD_SOURCE_MEMBERSHIP", 39)
if not hasattr(socket, "IP_DROP_SOURCE_MEMBERSHIP"):
    setattr(socket, "IP_DROP_SOURCE_MEMBERSHIP", 40)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
if IS_ALL_GROUPS:
    # on this port, receives ALL multicast groups
    sock.bind(('', int(args.port)))
else:
    # on this port, listen ONLY to MCAST_GRP
    sock.bind((args.group, args.port))

if (args.source):
    # SSM join
    mreq = struct.pack("=4sl4s", socket.inet_aton(args.group), socket.INADDR_ANY, socket.inet_aton(args.source))
    sock.setsockopt(socket.SOL_IP, socket.IP_ADD_SOURCE_MEMBERSHIP, mreq)
else:
    mreq = struct.pack("4sl", socket.inet_aton(args.group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

count=0
bytes=0
lasttime=time()
pkts_since_last_time=0
bytes_since_last_time=0
pps=0.0
sources = []

try:
    while True:
      if (time() - lasttime > 1.0):
          pps = pkts_since_last_time / (time() - lasttime)
          pkts_since_last_time = 0
          bytes_since_last_time = 0
          lasttime = time()
      (data, sender) = sock.recvfrom(10240)
      if (sender not in sources):
          sources.append(sender)
          print(f"\nFound new source: {sender[0]}:{sender[1]} ({len(sources)} unique sources so far)")
      n = len(data)
      bytes += n
      bytes_since_last_time += n
      count += 1
      pkts_since_last_time += 1
      print(f"\rcount={count} bytes={bytes} avg_pkt={int(bytes/count)} pps={round(pps)} bitrate={pretty(bytes_since_last_time*8.0/(time()-lasttime))}", end="    ")
except KeyboardInterrupt:
    print("")
    
