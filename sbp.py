#!/usr/bin/python3

import struct, time, socket, queue, threading

class heartbeat():
  def __init__(self, ClusterID, NodeID):
    self.ClusterID = ClusterID
    self.NodeID = NodeID

  def pack_hb(self, src_nID, des_nID, lID, seqnum, acknum):
    data_pack = struct.pack('HHHHIId', self.ClusterID, self.NodeID, des_nID, lID, seqnum, acknum, time.time()) 
    return data_pack

  def unpack_hb(self, data_pack):
    upacked = struct.unpack('HHHHIId', data_pack)
    pkt = {}
    pkt['ClusterID'] = upacked[0]
    pkt['src_nID'] = upacked[1]
    pkt['dst_nID'] = upacked[2]
    pkt['lID'] = upacked[3]
    pkt['seqnum'] = upacked[4]
    pkt['acknum'] = upacked[5]
    pkt['time'] = upacked[6]
    return pkt

  def pack_ip(self, srcip, dstip, proto=1, ident=54321):
    saddr = socket.inet_aton(srcip)
    daddr = socket.inet_aton(dstip)
    ihl_ver = (4 << 4) | 5
    return struct.pack('!BBHHHBBH4s4s', ihl_ver, 0, 0, ident, 0, 255, proto, 0, saddr, daddr)

  def unpack_ip_addr(self, data_pack):
    unpacked = struct.unpack('!BBHHHBBH4s4s', data_pack)
    dst_ip = struct.unpack('ssss', data_pack[16:20])

  def checksum(self,str):
    csum = 0
    countTo = (len(str) / 2) * 2
    count = 0
    while count < countTo:
      #thisVal = ord(str[count+1]) * 256 + ord(str[count])
      thisVal = str[count+1] * 256 + str[count]
      csum = csum + thisVal
      csum = csum & 0xffffffff
      count = count + 2

    if countTo < len(str):
      csum = csum + ord(str[len(str) - 1])
      csum = csum & 0xffffffff
    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer


class hb_rx(heartbeat,threading.Thread):
  def __init__(self,rxq,ip,port,ClusterID,NodeID):
    threading.Thread.__init__(self)
    self.daemon = True
    self.rxq = rxq
    self.ip = ip
    self.port = port
    self.ClusterID = ClusterID
    self.NodeID = NodeID
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    #self.sock.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
    self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

  def run(self):
    self.rx()
    
  def rx(self):
    while True:
      raw_pkt = self.sock.recvfrom(4096)
      data_pkt = self.unpack_hb(raw_pkt[0][28:]) 
      ip_header = self.unpack_ip_addr(raw_pkt[0][:20])
      if data_pkt['ClusterID'] != self.ClusterID or data_pkt['dst_nID'] != self.NodeID: 
        print("SSS") 
        print(data_pkt)
        continue
      self.rxq[data_pkt['lID']].rxq.put(data_pkt) 
      #print(data_pkt)
      

class hb_tx(heartbeat,threading.Thread):
  def __init__(self,txq,ClusterID,NodeID):
    threading.Thread.__init__(self)
    self.daemon = True
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    self.ClusterID = ClusterID
    self.NodeID = NodeID
    self.txq = txq

  def run(self):
    while True:
      x = self.txq.get()
      self.tx(x[0],x[1],x[2],x[3],x[4],x[5])
      self.txq.task_done()

  def tx(self,src_ip,host,dst_nID,lID,seq,ack):
    dst_ip = socket.gethostbyname(host)
    src_ip = src_ip
    ip_header = self.pack_ip(src_ip,dst_ip)
    cksum = 0
    icmp_header = struct.pack("bbHHh", 8, 0, cksum, self.ClusterID, 1)
    data = self.pack_hb(self.NodeID,dst_nID,lID,seq,ack)
    cksum = socket.htons(self.checksum(icmp_header + data))
    icmp_header = struct.pack("bbHHh", 8, 0, cksum, self.ClusterID, 1)
    pkt = ip_header + icmp_header + data
    self.sock.sendto(pkt, (dst_ip, 1))


class send_msg(threading.Thread):
  def __init__(self,link):
    threading.Thread.__init__(self)
    self.daemon = True
    self.link = link

  def run(self):
    while True:
      time.sleep(self.link.time)
      self.link.seqnum += 1
      self.link.txq.put([self.link.src_ip, self.link.dst_ip,self.link.dst_nID,self.link.lID,self.link.seqnum,self.link.acknum])
      

class get_msg(threading.Thread):
  def __init__(self,link):
    threading.Thread.__init__(self)
    self.daemon = True
    self.link = link

  def run(self):
    while True:
      pkt = self.link.rxq.get() 
      self.link.acknum = pkt['seqnum']
      print(pkt)
      self.link.rxq.task_done()

class icmp_link():
  def __init__(self,txq,time,src_ip,dst_ip,dst_nID,lID):
    self.txq = txq
    self.time = time
    self.src_ip = src_ip
    self.dst_ip = dst_ip
    self.dst_nID = dst_nID
    self.seqnum = 0
    self.acknum = 0
    self.lID = lID
    self.tx = send_msg(self)
    self.rxq = queue.Queue() 
    self.rx = get_msg(self)

  def start(self):
    self.tx.start()
    self.rx.start()   
  


