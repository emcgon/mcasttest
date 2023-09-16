import sys
from time import time
import socket
import struct
import argparse

# Lots of helpful hints from https://svn.python.org/projects/python/trunk/Demo/sockets/mcast.py


def pretty(n):
    suffixes = ("b/s", "Kb/s", "Mb/s", "Gb/s")
    i = 0
    while (n > 1000):
        i += 1
        n /= 1000.0
    return(f"{round(n*100)/100}{suffixes[i]}")

family = 0
parser = argparse.ArgumentParser(description='Join a multicast ground and listen for traffic')
parser.add_argument("group", action="store", help="Multicast group to join")
parser.add_argument("--source", "-s", action="store", help="Joint a particular source (SSM)")
parser.add_argument("--local", "-l", action="store", help="Local interface address (IPv4) or index (IPv6)")
#parser.add_argument("--4", "-4", action="store_true", help="IPv4 only")
#parser.add_argument("--6", "-6", action="store_true", help="IPv6 only")
parser.add_argument("port", action="store", help="UDP port to listen on")
args = parser.parse_args()

try:
    group_info = socket.getaddrinfo(args.group, args.port, family=family)[0]
    group_bin = socket.inet_pton(group_info[0], group_info[4][0])
    if (group_info[0] == socket.AF_INET):
        if ((group_bin[0] < 224) or (group_bin[0] > 239)):
            # IPv4 multicast addresses are in the range 224.0.0.0 to 239.255.255.255
            raise socket.gaierror
        elif (group_info[0] == socket.AF_INET6):
            # IPv6 multicast addresses are in the range ff00::/8
            if (group_bin[0] != 0xff):
                raise socket.gaierror
except socket.gaierror:
    print("ERROR: Invalid address specified for multicast group", file=sys.stderr)
    sys.exit(-1)

# If a multicast source is specified (SSM), parse that
if (args.source):
    try:
        source_info = socket.getaddrinfo(args.source, 0, family=family)[0]
        source_bin = socket.inet_pton(source_info[0], source_info[4][0])
    except socket.gaierror:
        print("ERROR: Invalid address specified for source address", file=sys.stderr)
        sys.exit(-1)
    if (group_info[0] != source_info[0]):
        print("ERROR: It makes no sense to specify different address-families for group and source", file=sys.stderr)
        sys.exit(-1)

# Determine the local interface address
if (group_info[0] == socket.AF_INET):
    local_bin = bytes([0,0,0,0])
else:
    local_bin = struct.pack("@L", 0)    # In the IPv6 world, this is an interface index number
    
if (args.local):
    if (group_info[0] == socket.AF_INET):
        # In the IPv4 world, specify the interface by IP address
        try:
            local_info = socket.getaddrinfo(args.local, 0, family=socket.AF_INET)[0]
            local_bin = socket.inet_pton(socket.AF_INET, local_info[4][0])
        except socket.gaierror:
            print("ERROR: Invalid address specified for local interface address", file=sys.stderr)
            sys.exit(-1)
    else:
        # In the IPv6 world, specify the interface as an (integer) index
        try:
            local_if = int(args.local)
            if (local_if < 0):
                raise ValueError
            local_bin = struct.pack("@L",  local_if)
        except ValueError:
            print("ERROR: Invalid interface index specified for local interface address", file=sys.stderr)
            sys.exit(-1)

# Hack in support for SSM (see https://bugs.python.org/issue45252 and https://github.com/alexcraig/GroupFlow/blob/master/groupflow_scripts/ss_multicast_receiver.py)
# See /usr/include/linux/in.h and /usr/include/linux/in6.h
extra_socket_attrs = {
    "IP_UNBLOCK_SOURCE": 37,
    "IP_BLOCK_SOURCE": 38,
    "IP_ADD_SOURCE_MEMBERSHIP": 39,
    "IP_DROP_SOURCE_MEMBERSHIP": 40,
    "MCAST_JOIN_GROUP": 42,
    "MCAST_BLOCK_SOURCE": 44,
    "MCAST_LEAVE_GROUP": 45,
    "MCAST_JOIN_SOURCE_GROUP": 46,
    "MCAST_LEAVE_SOURCE_GROUP": 47,
}
for (k, v) in extra_socket_attrs.items():
    if (not hasattr(socket, k)):
        setattr(socket, k, v)

sock = socket.socket(group_info[0], socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('', int(args.port)))

try:
    if (not args.source):
        # Not SSM
        if (group_info[0] == socket.AF_INET):
            # IPv4
            mreq = group_bin + local_bin
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        else:
            #IPv6
            ipv6_mreq = group_bin + local_bin 
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, ipv6_mreq)
    else:
        # SSM join
        if (group_info[0] == socket.AF_INET):
            # IPv4
            mreq = group_bin + local_bin + source_bin 
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_SOURCE_MEMBERSHIP, mreq)
        else:
            # IPv6
            ipv6_mreq = group_bin + local_bin + source_bin
            sock.setsockopt(socket.IPPROTO_IPV6, socket.MCAST_JOIN_SOURCE_GROUP, ipv6_mreq)    # TODO: Need a different structure for MCAST_JOIN_SOURCE_GROUP
except OSError as e:
    print("ERROR: Failed to join multicast group.  Possible reasons include:-", file=sys.stderr)
    if (args.source):
        print("- Operating system doesn't support source-spcific multicast (try again without \"-s\" argument)", file=sys.stderr)
    if (args.local):
        print("- The local address you specified doesn't exist on this host (check the address specified in the \"-l\" argument)", file=sys.stderr)
    print("- The multicast Gods have decided to smite you", file=sys.stderr)
    print(f"(actual error returned was {e})", file=sys.stderr)
    sys.exit(0)

print(f"Listening to group {group_info[4][0]}", end="")
if (args.source):
    print(f" for traffic from {source_info[4][0]}", end="")
print("")

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
    
