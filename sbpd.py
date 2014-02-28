#!/usr/bin/python3

import struct, time, socket, queue, threading, json, sys, os, logging, logging.handlers

CRITICAL=50
ERROR=40
WARNING=30
NOTICE=25
INFO=20
DEBUG=10

if os.path.isfile('/etc/sbpd.conf'):
  conf_file_location = '/etc/sbpd.conf'
elif os.path.isfile('/usr/local/etc/sbpd.conf'):
  conf_file_location = '/usr/local/etc/sbpd.conf'
elif os.path.isfile('sbpd.conf'):
  conf_file_location = 'sbpd.conf'
else:
  print("ERROR: No config file found")
  sys.exit(1)
with open('sbpd.conf') as f:
  config = json.load(f)

if "Logging" in config:
  print(config['Logging'])
else:
  log_path = '/var/log/'
  log_filename = 'sbpd.log'
  log_serverity = INFO

FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
#logging.basicConfig(filename=log_path + "/" + log_filename ,format=FORMAT)
logging.getLogger('').setLevel(INFO)
handler = logging.handlers.RotatingFileHandler(log_path + "/" + log_filename, maxBytes=10000000, backupCount=5)
handler.setFormatter(logging.Formatter(FORMAT))
logging.addLevelName(25, "NOTICE")
logging.getLogger("").addHandler(handler)
logger = logging.getLogger("system")


logger.log (INFO, "sbpd started")

class heartbeat():
  def __init__(self):
    pass

  def pack_hb(self, src_nID, des_nID, lID, seqnum, acknum, ClusterID, NodeID):
    data_pack = struct.pack('HHHHIId', ClusterID, NodeID, des_nID, lID, seqnum, acknum, time.time()) 
    return data_pack

  def unpack_hb(self, data_pack):
    #print(len(data_pack))
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


class hb_rx_udp(heartbeat,threading.Thread):
  def __init__(self,system):
    threading.Thread.__init__(self)
    self.daemon = True
    self.system = system
    self.sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock_udp.bind(('',system.udp_port))

    self.logger = logging.getLogger("RX UDP")

  def run(self):
    self.rx_udp()

  def rx_udp(self):
    while True:
      raw_pkt = self.sock_udp.recvfrom(4096)
      data = self.unpack_hb(raw_pkt[0]) 
      if not data[0]:
        continue
      data_pkt = data[1]
      ip_header = self.unpack_ip_addr(raw_pkt[0][:20])
      if data_pkt['dst_nID'] != self.system.cluster[data_pkt['ClusterID']].NodeID:
        logger.log(INFO, "packet received with wrong dest node ID (" + data_pkt['dst_nID'] + ")")
        continue
      try:
        self.system.cluster[data_pkt['ClusterID']].Nodes[data_pkt['src_nID']].udp_links[data_pkt['lID']].rxq.put(data_pkt)
      except:
        self.logger.log(WARNING, "packet can't be dispatched to link")
        print("EEEERRRROROO")
 

class hb_rx_icmp(heartbeat,threading.Thread):
  def __init__(self,system):
    threading.Thread.__init__(self)
    self.daemon = True
    self.system = system
    self.sock_icmp = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    #self.sock_icmp.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
    self.sock_icmp.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

    self.logger = logging.getLogger("RX ICMP")

  def run(self):
    self.rx_icmp()
   
  def rx_icmp(self):
    while True:
      raw_pkt = self.sock_icmp.recvfrom(4096)
      icmp_type = struct.unpack('b', raw_pkt[0][20:21])
      if icmp_type[0] != 0:
        continue
      data = self.unpack_hb(raw_pkt[0][28:]) 
      if not data[0]:
        continue
      data_pkt = data[1]
      ip_header = self.unpack_ip_addr(raw_pkt[0][:20])
      if data_pkt['dst_nID'] != self.system.cluster[data_pkt['ClusterID']].NodeID:
        logger.log(INFO, "packet received with wrong dest node ID (" + str(data_pkt['dst_nID']) + ")")
        continue
      try:
        self.system.cluster[data_pkt['ClusterID']].Nodes[data_pkt['src_nID']].icmp_links[data_pkt['lID']].rxq.put(data_pkt)
      except:
        self.logger.log(WARNING, "packet can't be dispatched to link")
        print("EEEERRRROROO")
      #self.rxq[data_pkt['lID']].rxq.put(data_pkt) 
      #print(data_pkt)
      

class hb_tx(heartbeat,threading.Thread):
  def __init__(self,txq,system):
    threading.Thread.__init__(self)
    self.daemon = True
    self.sock_icmp = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    self.sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.txq = txq
    self.logger = logging.getLogger("TX")
    self.logger.setLevel( log_serverity )
    self.system = system

  def run(self):
    while True:
      x = self.txq.get()
      if x[0] == 0:
        self.tx_icmp(x[1],x[2],x[3],x[4],x[5],x[6],x[7],x[8])
      elif x[0] == 1:
        self.tx_udp(x[1],x[2],x[3],x[4],x[5],x[6],x[7],x[8])
      self.txq.task_done()

  def tx_udp(self,src_ip,host,dst_nID,lID,seq,ack,ClusterID,NodeID):
    dst_ip = socket.gethostbyname(host)
    data = self.pack_hb(NodeID,dst_nID,lID,seq,ack, ClusterID, NodeID)
    try:
      self.sock_udp.sendto(data, (dst_ip, self.system.udp_port))
    except:
      self.logger.log(DEBUG, "sending of udp packet prohibited")

  def tx_icmp(self,src_ip,host,dst_nID,lID,seq,ack,ClusterID,NodeID):
    dst_ip = socket.gethostbyname(host)
    ip_header = self.pack_ip(src_ip,dst_ip)
    cksum = 0
    icmp_header = struct.pack("bbHHh", 8, 0, cksum, ClusterID, 1)
    data = self.pack_hb(NodeID,dst_nID,lID,seq,ack, ClusterID, NodeID)
    cksum = socket.htons(self.checksum(icmp_header + data))
    icmp_header = struct.pack("bbHHh", 8, 0, cksum, ClusterID, 1)
    pkt = ip_header + icmp_header + data
    self.sock_icmp.sendto(pkt, (dst_ip, 1))


class send_msg(threading.Thread):
  def __init__(self,link):
    threading.Thread.__init__(self)
    self.daemon = True
    self.link = link

  def run(self):
    while True:
      time.sleep(self.link.time)
      self.link.seqnum += 1
      self.link.cluster.txq.put([self.link.type,self.link.src_ip, self.link.dst_ip,self.link.dst_nID,self.link.lID,self.link.seqnum,self.link.acknum,self.link.cluster.ID,self.link.cluster.NodeID])
      

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
          self.link.logger.log(NOTICE, "in-service") 
          self.cnode.check_split()
      except queue.Empty:
        if self.link.status:
          self.link.logger.log(WARNING, "out-of-service") 
          self.link.status = False
          self.link.cnode.check_split()

class link():
  def __init__(self,cnode,cluster,time,src_ip,dst_ip,dst_nID,lID,maxloss,ltype):
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
    self.cluster = cluster
    self.type = ltype
    if self.type == 0:
      self.typename = "ICMP"
    elif self.type == 1:
      self.typename = "UDP"

    self.logger = logging.getLogger("ClusterID:" + str(cluster.ID) + " NodeID:" + str(self.cnode.ID) + " " + self.typename + " LinkID:" + str(self.lID) )

    self.tx = send_msg(self)
    self.rxq = queue.Queue() 
    self.rx = get_msg(self, self.cnode)

  def start(self):
    self.tx.start()
    self.rx.start()   

class cluster():
  #def __init__(self,config,rxq,txq):
  def __init__(self,config,txq):
    self.config = config
    #self.rxq = rxq
    self.txq = txq
    self.ID = self.config["ID"]
    self.hostname = socket.gethostname()
    self.NodeID = ""
    self.Nodes = {}
    self.logger = logging.getLogger("ClusterID:" + str(self.ID))

  def create_nodes(self):
    for i in self.config["Members"]:
      if i['Hostname'] == self.hostname:
        self.NodeID = i['ID']
      else:
        self.Nodes[i['ID']] = cnodes(self,i['ID'],i['Hostname'])

  def create_all_links(self):
    for x,z in self.Nodes.items():
      z.create_links()

class cnodes():
  def __init__(self,cluster,dst_nID,hostname):
    self.cluster = cluster
    self.ID = dst_nID
    self.hostname = hostname
    self.icmp_links = {}
    self.udp_links = {}
    self.status = {'icmp': True, 'udp': True}

    self.logger = logging.getLogger("ClusterID:" + str(cluster.ID) + " NodeID:" + str(self.ID))

  def create_links(self):
    for i in self.cluster.config["links"]:
      if len(i['Nodes']) != 2:
          print("ERROR")
      if i['type'] == "icmp":
        own_link = False
        for x in i['Nodes']:
          if x['NodeID'] == self.cluster.NodeID:
            own_link = True
          else:
            dst_nID = x['NodeID']
            ip = x['IP']
        if own_link:
          self.icmp_links[i['ID']] = link(self,self.cluster,i['interval'],ip,i['ICMPIP'],dst_nID,i['ID'],i['maxloss'], 0) 
      elif i['type'] == "udp":
        own_link = False
        for x in i['Nodes']:
          if x['NodeID'] == self.cluster.NodeID:
            own_link = True
            src_ip = x['IP']
          else:
            dst_nID = x['NodeID']
            dst_ip = x['IP']
        if own_link:
          self.udp_links[i['ID']] = link(self,self.cluster,i['interval'],src_ip,dst_ip,dst_nID,i['ID'],i['maxloss'], 1)

  def start_all_links(self):
    for i in self.icmp_links:
      self.icmp_links[i].start()
    for i in self.udp_links:
      self.udp_links[i].start()


  def check_split(self):
    status = False
    for i in self.icmp_links:
      if self.icmp_links[i].status:
        status = True
    if self.status['icmp'] != status:
      if status:
        self.logger.log (NOTICE, "ICMP path in-service")
      else:
        self.logger.log (CRITICAL, "ICMP path out-of-service")
    self.status['icmp'] = status
    status = False
    for i in self.udp_links:
      if self.udp_links[i].status:
        status = True
    if self.status['udp'] != status:
      if status:
        self.logger.log (NOTICE, "UDP path in-service")
      else:
        self.logger.log (CRITICAL, "UDP path out-of-service")
    self.status['udp'] = status
    

class system():
  def __init__(self,config):
    self.config = config
    self.udp_port = 7878
    self.txq = queue.Queue()
    #self.rxq = queue.Queue()
    self.tx = hb_tx(self.txq,self)  
    self.rx_icmp = hb_rx_icmp(self) 
    self.rx_udp = hb_rx_udp(self) 
    self.start_queues()
    self.cluster = {}
      

  def start_queues(self):
    self.tx.start()
    self.rx_icmp.start()
    self.rx_udp.start()
    
  def create(self):
    if 'Cluster' not in  self.config:
      print("Section 'Cluster' missing in config file")
      sys.exit(1)
    for i in self.config['Cluster']:
      #self.cluster[i['ID']] = cluster(i,self.rxq,self.txq)
      self.cluster[i['ID']] = cluster(i,self.txq)
      self.cluster[i['ID']].create_nodes()
      self.cluster[i['ID']].create_all_links()

  def start(self):
    for i in self.cluster:
      for x in self.cluster[i].Nodes:
        self.cluster[i].Nodes[x].start_all_links()
    self.monitor()  

  def monitor(self):
    while True:
      try:
        if not self.rx_icmp.isAlive:
          self.rx.start()
        if not self.tx.isAlive:
          self.tx.start()
        time.sleep(1)
      except KeyboardInterrupt:
        logger.log(INFO, "sbpd stop on keyboard interrupt") 
        sys.exit(0)

x = system(config)
x.create()
x.start()

