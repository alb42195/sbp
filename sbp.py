#!/usr/bin/python3

#####################################################################################
#
# sbp - split brain prodection library for usage of sbpd.
# Copyright (C) 2014 Albert Hayr <albert@hayr.at>
#
#   one line to give the library's name and an idea of what it does.
#   Copyright (C) year  name of author
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, write to the Free Software
#   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
#####################################################################################


import socket, sys, os, time, struct, threading

class sbp(threading.Thread):
  def __init__(self,sock_file,cb_func):

    self.cb_func = cb_func

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    while True:
      try:
        sock.connect(sock_file)
        break
      except ConnectionRefusedError:
        time.sleep(5)
    tosend  = struct.pack('H', 1000)
    sock.send(tosend)
    while True:
      try:
        data_raw = sock.recv(1024)
        if not data_raw:
          sock.close()
          break
      
        length, = struct.unpack('H', data_raw[:2])
        if length != len(data_raw):
          start=2
          end=length
          while end > start:
            self.unpack(data_raw[start:end])
            if end == len(data_raw):
              break
            length, = struct.unpack('H', data_raw[end:end+2])
            start = end + 2
            end = end + length

        else:
          self.unpack(data_raw[2:])

      except KeyboardInterrupt:
         sock.close() 
         sys.exit(1)

  def unpack(self,data):
    pkt = {}
    pkt['msg_type'], = struct.unpack('H', data[:2])
    pkt['state'], = struct.unpack('H', data[2:4])
    pkt['ClusterID'], = struct.unpack('H', data[4:6])
    pkt['NodeID'], = struct.unpack('H', data[6:8])
    pkt['linktype'], = struct.unpack('H', data[8:10])
    if pkt['msg_type'] > 300:
      pkt['lID'], = struct.unpack('H', data[10:12])
    self.cb_func(pkt)

