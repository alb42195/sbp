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


import socket, time, struct, threading

class sbp(threading.Thread):
  def __init__(self,clusterID,cb_func,sockfile="/run/sbpd.sock",thread=False):
    self.cb_func = cb_func
    self.sockfile = sockfile
    self.clusterID = clusterID
    self.thread = thread
    if self.thread:
      threading.Thread.__init__(self)
      self.daemon = True
    else:
      self.run() 


  def run(self):
    self.init()
    self.rx()
    self.stop()


  def stop(self):
    self.sock.close()
    return

  def init(self):
    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.sock.connect(self.sockfile)
    tosend  = struct.pack('H', self.clusterID)
    self.sock.send(tosend)

  def rx(self):
    while True:
        data_raw = self.sock.recv(1024)
        if not data_raw:
          raise BrokenPipeError("sbpd connection")
      
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

