#!/usr/bin/python3

import socket, sys, os, time, struct, threading


class sbp(threading.Thread):
  def __init__(self,cb_func):

    self.cb_func = cb_func
    sock_file= "sbpd.sock"

    #sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_file)
    tosend  = struct.pack('H', 1000)
    sock.send(tosend)
    while True:
      try:
        data = sock.recv(1024)
        if not data:
          sock.close()
          break
        try:
          pkt = {}
          pkt['msg_type'], = struct.unpack('H', data[:2])
          pkt['state'], = struct.unpack('H', data[2:4])
          pkt['ClusterID'], = struct.unpack('H', data[4:6])
          if pkt['msg_type'] > 200:
            pkt['NodeID'], = struct.unpack('H', data[6:8])
            pkt['linktype'], = struct.unpack('H', data[8:10])
          if pkt['msg_type'] > 300:
            pkt['lID'], = struct.unpack('H', data[10:12])
          self.cb_func(pkt)
        except:
          print(data)
      except KeyboardInterrupt:
        sock.close() 
        sys.exit(1)


def p(x):
  print(x)


z=sbp(p)
