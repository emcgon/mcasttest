# mcasttest
A simple Python script for subscribing to an IP multicast group and displaying statistics about the packets received (if any).

    $ python3 mcasttest.py -h
    usage: mcasttest.py [-h] [--source SOURCE] group port

    Join a multicast ground and listen for traffic

    positional arguments:
      group            Multicast group to join
      port             UDP port to listen on

    optional arguments:
      -h, --help       show this help message and exit
      --source SOURCE  Joint a particular source (SSM)

    $ python3 mcasttest.py 225.1.1.1 2001
    Found new source: 192.0.2.2:57284 (1 unique sources so far)
    count=1360 bytes=1789760 avg_pkt=1316 pps=291 bitrate=3.07Mb/s

Supports source-specific multicast (assuming underlying operating system support and a connection to a network with IGMPv3). 

    $ python3 mcasttest.py --source 192.0.2.2 225.1.1.1 2001
    Found new source: 192.0.2.2:57284 (1 unique sources so far)
    count=814 bytes=1071224 avg_pkt=1316 pps=291 bitrate=3.07Mb/s
    
    $ sudo tcpdump -vvni eth0 igmp
    [...]
    17:14:30.928635 IP (tos 0xc0, ttl 1, id 0, offset 0, flags [DF], proto IGMP (2), length 44, options (RA))
        10.10.10.10 > 224.0.0.22: igmp v3 report, 1 group record(s) [gaddr 225.1.1.1 allow { 192.0.2.2 }]
