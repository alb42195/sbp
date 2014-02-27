#!/usr/bin/python3

import struct, time, socket, queue, threading, json

class heartbeat():
  def __init__(self):
    pass

  def pack_hb(self, src_nID, des_nID, lID, seqnum, acknum, ClusterID, NodeID):
    data_pack = struct.pack('HHHHIId', ClusterID, NodeID, des_nID, lID, seqnum, acknum, time.time()) 
    return data_pack

  def unpack_hb(self, data_pack):
    try:
      upacked = struct.unpack('HHHHIId', data_pack)
      pkt = {}
      pkt['ClusterID'] = upacked[0]
      pkt['src_nID'] = upacked[1]
      pkt['dst_nID'] = upacked[2]
      pkt['lID'] = upacked[3]
      pkt['seqnum'] = upacked[4]
      pkt['acknum'] = upacked[5]
      pkt['time'] = upacked[6]
      return [True, pkt]
    except:
      return [False]

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
  #def __init__(self,rxq,ip,port,ClusterID,NodeID):
  def __init__(self,system):
    threading.Thread.__init__(self)
    self.daemon = True
    #self.rxq = rxq
    #self.ip = ip
    #self.port = port
    #self.ClusterID = ClusterID
    #self.NodeID = NodeID
    self.system = system
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    #self.sock.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
    self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

  def run(self):
    self.rx()
    
  def rx(self):
    while True:
      raw_pkt = self.sock.recvfrom(4096)
      
      data = self.unpack_hb(raw_pkt[0][28:]) 
      if not data[0]:
        continue
      data_pkt = data[1]
      ip_header = self.unpack_ip_addr(raw_pkt[0][:20])
      if data_pkt['dst_nID'] != self.system.cluster[data_pkt['ClusterID']].NodeID:
        print("SSS")
        continue
      try:
        self.system.cluster[data_pkt['ClusterID']].Nodes[data_pkt['src_nID']].icmp_links[data_pkt['lID']].rxq.put(data_pkt)
      except:
        print("EEEERRRROROO")
      #self.rxq[data_pkt['lID']].rxq.put(data_pkt) 
      #print(data_pkt)
      

class hb_tx(heartbeat,threading.Thread):
  def __init__(self,txq):
    threading.Thread.__init__(self)
    self.daemon = True
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    self.txq = txq

  def run(self):
    while True:
      x = self.txq.get()
      self.tx(x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7])
      self.txq.task_done()

  def tx(self,src_ip,host,dst_nID,lID,seq,ack,ClusterID,NodeID):
    dst_ip = socket.gethostbyname(host)
    ip_header = self.pack_ip(src_ip,dst_ip)
    cksum = 0
    icmp_header = struct.pack("bbHHh", 8, 0, cksum, ClusterID, 1)
    data = self.pack_hb(NodeID,dst_nID,lID,seq,ack, ClusterID, NodeID)
    cksum = socket.htons(self.checksum(icmp_header + data))
    icmp_header = struct.pack("bbHHh", 8, 0, cksum, ClusterID, 1)
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
      self.link.cluster.txq.put([self.link.src_ip, self.link.dst_ip,self.link.dst_nID,self.link.lID,self.link.seqnum,self.link.acknum,self.link.cluster.ID,self.link.cluster.NodeID])
      

class get_msg(threading.Thread):
  def __init__(self,link,cnode):
    threading.Thread.__init__(self)
    self.daemon = True
    self.link = link
    self.cnode = cnode

  def run(self):
    while True:
      try:
        pkt = self.link.rxq.get(timeout=self.link.time*self.link.maxloss) 
        self.link.acknum = pkt['seqnum']
        self.link.rxq.task_done()
        if not self.link.status:
          self.link.status = True
          print("link " + str(self.link.lID) + " ok")
          self.cnode.check_split()
      except queue.Empty:
        if self.link.status:
          print("link " + str(self.link.lID) + " failed")
          self.link.status = False
          self.link.cnode.check_split()

class ICMP_link():
  def __init__(self,cnode,cluster,time,src_ip,dst_ip,dst_nID,lID,maxloss):
    self.status = True
    self.time = time
    self.cnode = cnode
    self.maxloss = maxloss
    self.src_ip = src_ip
    self.dst_ip = dst_ip
    self.dst_nID = dst_nID
    self.seqnum = 0
    self.acknum = 0
    self.lID = lID
    self.tx = send_msg(self)
    self.rxq = queue.Queue() 
    self.rx = get_msg(self, self.cnode)
    self.cluster = cluster

  def start(self):
    self.tx.start()
    self.rx.start()   

class cluster():
  def __init__(self,config,rxq,txq):
    self.config = config
    self.rxq = rxq
    self.txq = txq
    self.ID = self.config["ID"]
    self.hostname = socket.gethostname()
    self.NodeID = ""
    self.Nodes = {}

  def create_nodes(self):
    for i in self.config["Members"]:
      if i['Hostname'] == self.hostname:
        self.NodeID = i['ID']
      else:
        self.Nodes[i['ID']] = cnodes(self,i['ID'],i['Hostname'])

  def create_all_icmp_links(self):
    for x,z in self.Nodes.items():
      z.create_links()

class cnodes():
  def __init__(self,cluster,dst_nID,hostname):
    self.cluster = cluster
    self.ID = dst_nID
    self.hostname = hostname
    self.icmp_links = {}
    self.status = True
  
  def create_links(self):
    for i in self.cluster.config["ICMP_links"]:
      own_link = False
      if len(i['Nodes']) != 2:
        print("ERROR")
      for x in i['Nodes']:
        if x['NodeID'] == self.cluster.NodeID:
          own_link = True
        else:
          dst_nID = x['NodeID']
          ip = x['IP']
      if own_link:
        self.icmp_links[i['ID']] = ICMP_link(self,self.cluster,i['interval'],ip,i['ICMPIP'],dst_nID,i['ID'],i['maxloss'],)

  def start_all_links(self):
    for i in self.icmp_links:
      self.icmp_links[i].start()


  def check_split(self):
    status = False
    for i in self.icmp_links:
      if self.icmp_links[i].status:
        status = True
    if self.status != status:
      if status:
        print("node " + str(self.ID) + " ok")
      else:
        print("split " + str(self.ID) + "brain")

    self.status = status
    

class system():
  def __init__(self):
    with open('sbp.conf') as f:
      self.config = json.load(f)
    self.txq = queue.Queue()
    self.rxq = queue.Queue()
    self.tx = hb_tx(self.txq)  
    self.rx = hb_rx(self) 
    self.start()
    self.cluster = {}

  def start(self):
    self.tx.start()
    self.rx.start()

  def create_cluster(self):
    for i in self.config['Cluster']:
      self.cluster[i['ID']] = cluster(i,self.rxq,self.txq)
      self.cluster[i['ID']].create_nodes()
      self.cluster[i['ID']].create_all_icmp_links()


