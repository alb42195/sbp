#!/usr/bin/python3

import struct, time, socket, queue, threading, json, sys, os, logging, logging.handlers


def run_as_daemon():
  if __name__ == "__main__":
    try:
      pid = os.fork()
      if pid > 0:
        sys.exit(0)
    except OSError:
      sys.exit(1)

    os.chdir("/")
    os.setsid()
    os.umask(0)

    try:
      pid = os.fork()
      if pid > 0:
        sys.exit(0)
    except OSError:
      sys.exit(1)

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

daemon = True
if "System" in config:
  if "forground" in config['System']:
    if config['System']['forground']:
      daemon = False

if daemon:      
  run_as_daemon()

log_file = '/var/log/sbpd.log'
log_serverity = DEBUG
log_file_size = 1000000000 
log_file_no = 5
if "Logging" in config:
  if "level" in config['Logging']:
    log_serverity = config['Logging']['level']
    log_serverity = log_serverity.upper()
  if "logfile" in config['Logging']:
    log_file = config['Logging']['logfile']
  if "no_of_files" in config['Logging']:
    log_file_no = config['Logging']['no_of_files']
  if "max_file_size" in config['Logging']:
    log_file_no = config['Logging']['max_file_size'] * 1000 * 1000


FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
#logging.basicConfig(filename=log_path + "/" + log_filename ,format=FORMAT)
logging.getLogger('').setLevel(log_serverity)
handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10000000, backupCount=5)
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
    time.sleep(0.1)
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
    time.sleep(0.1)
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
        print(data_pkt) 
        continue
      if data_pkt['src_nID'] == data_pkt['dst_nID']:
        try:
          dispatch_nodeID = self.system.cluster[data_pkt['ClusterID']].all_links[data_pkt['lID']]
          self.system.cluster[data_pkt['ClusterID']].Nodes[self.system.cluster[data_pkt['ClusterID']].all_links[data_pkt['lID']]].icmp_links[data_pkt['lID']].icmp_hop.rxq.put(data_pkt)
        except:
         self.logger.log(WARNING, "ICMP hop packet received, which can't be distributed") 
      else:
        try:
          self.system.cluster[data_pkt['ClusterID']].Nodes[data_pkt['src_nID']].icmp_links[data_pkt['lID']].rxq.put(data_pkt)
        except:
          self.logger.log(WARNING, "packet can't be dispactched to any link ClusterID:" + str(data_pkt['ClusterID']) + " NodeID:" + str(data_pkt['src_nID']) + " LinkID:" + str(data_pkt['lID']))  
      

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
      if x[0] == 0 or x[0] == 2:
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
    self.active = threading.Event()

  def run(self):
    while True:
      self.link.cluster.txq.put([self.link.type,self.link.src_ip, self.link.dst_ip,self.link.dst_nID,self.link.lID,self.link.seqnum,self.link.acknum,self.link.cluster.ID,self.link.cluster.NodeID])
      self.link.seqnum += 1
      if self.active.wait(self.link.time):
        self.link.logger.log (DEBUG, "stopping icmp tx thread")
        return
      

class get_msg(threading.Thread):
  def __init__(self,link,cnode):
    threading.Thread.__init__(self)
    self.daemon = True
    self.link = link
    self.cnode = cnode
    self.alarmq = self.cnode.alarmq

  def run(self):
    self.do_work()
 
  def do_work(self):
    self.link.logger.log (DEBUG, "starting get_msg thread")
    while True:
      try:
        pkt = self.link.rxq.get(timeout=self.link.time*self.link.maxloss)
        if not pkt:
          self.link.logger.log (DEBUG, "stopping get_msg thread")
          return
        self.link.acknum = pkt['seqnum']
        
        if pkt['acknum'] < self.link.seqnum - self.link.maxloss and self.link.get_ack and  pkt['seqnum'] != 0:
          self.link.logger.log (NOTICE, "tx out-of-service")
          self.alarmq.put(self.link.alarm_txo)
          self.link.get_ack = False
        elif pkt['acknum'] > self.link.seqnum - self.link.maxloss and not self.link.get_ack:
          self.link.logger.log (NOTICE, "tx in-service")
          self.alarmq.put(self.link.alarm_txi)
          self.link.get_ack = True 
        self.link.rxq.task_done()
        if not self.link.status:
          if self.link.type == 0: 
            self.link.icmp_hop_stop()
          self.link.status = True
          self.link.logger.log(NOTICE, "in-service")
          self.alarmq.put(self.link.alarm_ins)
          if self.link.type != 2:
            self.cnode.check_split()
      except queue.Empty:
        if self.link.status:
          if self.link.type == 0: 
            self.link.icmp_hop_start()
          self.link.logger.log(WARNING, "out-of-service")
          self.alarmq.put(self.link.alarm_oos)
          self.link.status = False
          if self.link.type != 2:
            self.link.cnode.check_split()
 
class link():
  def __init__(self,cnode,cluster,time,src_ip,dst_ip,dst_nID,lID,maxloss,ltype,own_ip=None):
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
    self.hb_loss = 0
    self.cluster = cluster
    self.own_ip= own_ip
    self.get_ack = True
    self.type = ltype
    self.alarm_oos = {"clusterID": self.cluster.ID, "cnodeID": self.cnode.ID, "linktype": self.type, "lID": self.lID, "state": 0, "msgid": 301}
    self.alarm_ins = {"clusterID": self.cluster.ID, "cnodeID": self.cnode.ID, "linktype": self.type, "lID": self.lID, "state": 1, "msgid": 301}
    self.alarm_txo = {"clusterID": self.cluster.ID, "cnodeID": self.cnode.ID, "linktype": self.type, "lID": self.lID, "state": 0, "msgid": 302}
    self.alarm_txi = {"clusterID": self.cluster.ID, "cnodeID": self.cnode.ID, "linktype": self.type, "lID": self.lID, "state": 1, "msgid": 302}
    if self.type == 0:
      self.typename = "ICMP"
    elif self.type == 1:
      self.typename = "UDP"
    elif self.type == 2:
      self.typename = "ICMP_HOP"
      self.status = False 
      self.alarm_oos = {"clusterID": self.cluster.ID, "cnodeID": self.cnode.ID, "linktype": self.type, "lID": self.lID, "state": 0, "msgid": 303}
      self.alarm_ins = {"clusterID": self.cluster.ID, "cnodeID": self.cnode.ID, "linktype": self.type, "lID": self.lID, "state": 1, "msgid": 303}
    self.alarmq = self.cnode.alarmq 
    

    self.logger = logging.getLogger("ClusterID:" + str(self.cluster.ID) + " NodeID:" + str(self.cnode.ID) + " LinkID:" + str(self.lID) + " " + self.typename  )

    self.tx = send_msg(self)
    self.rxq = queue.Queue() 
    self.rx = get_msg(self, self.cnode)

  def start(self):
    self.tx.start()
    self.rx.start()   

  def icmp_hop_start(self):
    if self.type != 0:
      self.logger.log(DEBUG, "icmp_hop link only by icmp links available")
      return
    self.icmp_hop = link(self.cnode,self.cluster,self.time,self.own_ip,self.dst_ip,self.cluster.NodeID,self.lID,self.maxloss,2)
    self.icmp_hop.tx.start()
    self.icmp_hop.rx.start()   
    self.logger.log (INFO, "starting ICMP hop verification")

  def icmp_hop_stop(self):
    if self.type != 0:
      self.logger.log(DEBUG, "icmp_hop link only by icmp links available")
      return
    self.icmp_hop.rxq.put(False)   
    self.icmp_hop.tx.active.set()
    del self.icmp_hop.tx
    del self.icmp_hop.rx
    self.logger.log (INFO, "stopping ICMP hop verification")
    

class cluster():
  def __init__(self,config,system):
    self.system = system
    self.config = config
    self.txq = self.system.txq
    self.ID = self.config["ID"]
    self.hostname = socket.gethostname()
    self.NodeID = ""
    self.Nodes = {}
    self.all_links = {}
    self.logger = logging.getLogger("ClusterID:" + str(self.ID))
    #self.apiq = queue.Queue()
    self.alarmq = self.system.sock_api.alarmq


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
    self.alarmq = self.cluster.alarmq
    self.logger = logging.getLogger("ClusterID:" + str(cluster.ID) + " NodeID:" + str(self.ID))
    #self.alarm_oos = {"clusterID": self.cluster.ID, "cnodeID": self.ID, "state": 0, "msgid": 201}
    #self.alarm_ins = {"clusterID": self.cluster.ID, "cnodeID": self.ID, "state": 1, "msgid": 201}

  def create_links(self):
    for i in self.cluster.config["links"]:
      if len(i['Nodes']) != 2:
          print("ERROR")
      if i['type'] == "icmp":
        own_link = False
        for x in i['Nodes']:
          if x['NodeID'] == self.cluster.NodeID:
            own_link = True
            src_ip = x['IP']
          else:
            dst_nID = x['NodeID']
            ip = x['IP']
        if own_link:
          self.icmp_links[i['ID']] = link(self,self.cluster,i['interval'],ip,i['ICMPIP'],dst_nID,i['ID'],i['maxloss'],0,src_ip)
          self.cluster.all_links[i['ID']] = self.ID
      elif i['type'] == "udp":
        own_link = False
        for x in i['Nodes']:
          if x['NodeID'] == self.cluster.NodeID:
            if not self.cluster.system.udp:
              self.logger.log ( ERROR, "no udp port configured, can't setup udp links")
              continue
            own_link = True
            src_ip = x['IP']
          else:
            dst_nID = x['NodeID']
            dst_ip = x['IP']
        if own_link:
          self.udp_links[i['ID']] = link(self,self.cluster,i['interval'],src_ip,dst_ip,dst_nID,i['ID'],i['maxloss'],1)
          self.cluster.all_links[i['ID']] = self.ID

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
        self.alarmq.put({"clusterID": self.cluster.ID, "cnodeID": self.ID, "state": 1, "linktype": 0, "msgid": 201})
      else:
        self.logger.log (CRITICAL, "ICMP path out-of-service")
        self.alarmq.put({"clusterID": self.cluster.ID, "cnodeID": self.ID, "state": 0, "linktype": 0, "msgid": 201})
    self.status['icmp'] = status
    status = False
    for i in self.udp_links:
      if self.udp_links[i].status:
        status = True
    if self.status['udp'] != status:
      if status:
        self.logger.log (NOTICE, "UDP path in-service")
        self.alarmq.put({"clusterID": self.cluster.ID, "cnodeID": self.ID, "state": 1, "linktype": 1, "msgid": 202})
      else:
        self.logger.log (CRITICAL, "UDP path out-of-service")
        self.alarmq.put({"clusterID": self.cluster.ID, "cnodeID": self.ID, "state": 0, "linktype": 1, "msgid": 202})
    self.status['udp'] = status
    

class system():
  def __init__(self,config):
    self.config = config
    if "System" not in self.config:
      self.udp = False
      #self.logger.log( INFO, "System section missing in config file")
    else:
      if "udp_port" in self.config["System"]:
        self.udp_port = self.config["System"]['udp_port']
        self.udp = True
      else:
        self.udp = False
    self.txq = queue.Queue()
    self.tx = hb_tx(self.txq,self)  
    self.rx_icmp = hb_rx_icmp(self) 
    if self.udp:
      self.rx_udp = hb_rx_udp(self) 
    self.start_queues()
    self.cluster = {}
     

  def start_queues(self):
    self.tx.start()
    self.rx_icmp.start()
    if self.udp:
      self.rx_udp.start()
    
  def create(self):
    if 'Cluster' not in  self.config:
      print("Section 'Cluster' missing in config file")
      sys.exit(1)
    self.sock_api = sock_api(self)
    for i in self.config['Cluster']:
      self.cluster[i['ID']] = cluster(i,self)
      self.cluster[i['ID']].create_nodes()
      self.cluster[i['ID']].create_all_links()
      self.sock_api.conn[i['ID']] = {}
      self.sock_api.alarmbuffer[i['ID']] = {}
  
  def start(self):
    for i in self.cluster:
      for x in self.cluster[i].Nodes:
        self.cluster[i].Nodes[x].start_all_links()
    self.sock_api.start()
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

class api_new_conn(threading.Thread):
  def __init__(self,sock_api):
    threading.Thread.__init__(self)
    self.daemon = True
    self.conn_no = 0
    self.sock_api = sock_api
    self.start()

  def run(self):
    while True:
      conn, addr = self.sock_api.sock.accept()
      try:
        raw_data = conn.recv(1024) 
        data = struct.unpack('H', raw_data) 
        clusterID = data[0]
        if clusterID not in self.sock_api.conn:
          self.sock_api.logger.log(INFO, "registered with wrong cluster ID")
          conn.close()
        else:
          self.conn_no += 1
          self.sock_api.conn[clusterID][self.conn_no] = api_conn(conn,self.sock_api,clusterID)
      except:
        self.sock_api.logger.log(ERROR, "unexpected error")
        conn.close()
 

class api_conn(threading.Thread):
  def __init__(self,conn,sock_api,ClusterID):
    threading.Thread.__init__(self)
    self.daemon = True
    self.sock_api = sock_api
    self.conn = conn
    self.ClusterID = ClusterID
    self.txq = queue.Queue()
    self.start()

  def msg(self,alarm):
    if "lID" in alarm:
      return struct.pack('HHHHHHH', 14, alarm['msgid'], alarm['state'], alarm['clusterID'], alarm['cnodeID'], alarm['linktype'], alarm['lID'])
    elif "cnodeID" in alarm:
      return struct.pack('HHHHHH', 12, alarm['msgid'], alarm['state'], alarm['clusterID'], alarm['cnodeID'], alarm['linktype'])

  def run(self):
    self.send_buf()
    while True:
      alarm = self.txq.get()
      try:
        self.conn.send(self.msg(alarm))
        #time.sleep(0.001)
      except:
        self.conn.close()
        return

  def send_buf(self):
    for i in self.sock_api.alarmbuffer[self.ClusterID]:
      for x in self.sock_api.alarmbuffer[self.ClusterID][i].values():
        self.txq.put(x) 

class sock_api(threading.Thread):
  def __init__ (self,system):
    threading.Thread.__init__(self)
    self.daemon = True
    self.conn = {}
    self.logger = logging.getLogger("sock api")
    self.system = system
    self.sockfile = "sbpd.sock"
    if "api" in self.system.config:
      self.sockfile = self.system.config['api']['socket']
    self.alarmq = queue.Queue()
    self.alarmbuffer = {}  

  def run(self):
    self.new_conn = self.listen()
    self.do_work()


  def buffer(self,alarm):
    if alarm['state'] != 0:
      try:
        if alarm['msgid'] > 300:
          del self.alarmbuffer[alarm['clusterID']][alarm['msgid']][alarm['lID']]
        elif alarm['msgid'] > 200: 
          del self.alarmbuffer[alarm['clusterID']][alarm['msgid']][alarm['linktype']]
      except KeyError:
        self.logger.log( DEBUG, "alarm not buffered " + str(alarm) )
    else:
      if alarm['msgid'] > 300:
        if alarm['msgid'] in self.alarmbuffer[alarm['clusterID']]:
          self.alarmbuffer[alarm['clusterID']][alarm['msgid']][alarm['lID']] = alarm
        else:
          self.alarmbuffer[alarm['clusterID']][alarm['msgid']] = {alarm['lID']: alarm }
        return
      elif alarm['msgid'] > 200:
        if alarm['msgid'] in self.alarmbuffer[alarm['clusterID']]:
          self.alarmbuffer[alarm['clusterID']][alarm['msgid']][alarm['linktype']] = alarm
        else:
          self.alarmbuffer[alarm['clusterID']][alarm['msgid']] = {alarm['linktype']: alarm } 
        return
      


  def do_work(self):
    while True:
      alarm = self.alarmq.get()
      dead_thread = {}
      for k,v in self.conn[alarm['clusterID']].items():
        if v.is_alive():
          v.txq.put(alarm)
        else:
          dead_thread[alarm['clusterID']] = k  
      self.buffer(alarm)
      self.alarmq.task_done()
      for k,v in dead_thread.items():
        del self.conn[k][v]
      del dead_thread

  def listen(self):
    if os.path.exists(self.sockfile):
      os.remove(self.sockfile)
    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.sock.bind(self.sockfile)
    self.sock.listen(5)
    self.new_conn = api_new_conn(self)
   
 



x = system(config)
x.create()
x.start()

