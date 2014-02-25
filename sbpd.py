#!/usr/bin/python3

import threading, queue, sbp, time

rxq = queue.Queue()
txq = queue.Queue()


l = {}
l[1] = sbp.icmp_link(txq,2,'192.168.122.12','192.168.122.13',12,1)
l[1].start()
tx_t = sbp.hb_tx(txq, 1000,11)
tx_t.start()
rx_t = sbp.hb_rx(l,'',1,1000,11)
rx_t.start()



time.sleep(100)
