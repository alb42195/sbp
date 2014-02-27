#!/usr/bin/python3

import threading, queue, sbp, time, json

#rxq = queue.Queue()
#txq = queue.Queue()

#with open('sbp.conf') as f:
#  config = json.load(f)

#tx_t = sbp.hb_tx(txq)
#tx_t.start()



#x = sbp.cluster(config['Cluster'][0],rxq,txq)
#x.create_nodes()
#x.create_all_icmp_links()
#x.Nodes[2].start_all_links()

x = sbp.system()
x.create_cluster()
x.cluster[1000].Nodes[2].start_all_links()

#l = {}
#l[1] = sbp.icmp_link(txq,2,'192.168.122.12','192.168.122.13',12,1)
#l[1].start()
#rx_t = sbp.hb_rx(l,'',1,1000,11)
#rx_t.start()



time.sleep(100)
