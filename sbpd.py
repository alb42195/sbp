#!/usr/bin/python3

import threading, queue, sbp, time

rxq = queue.Queue()
txq = queue.Queue()


rx_t = sbp.hb_rx("aaa",'',1,1000,10)
rx_t.start()

tx_t = sbp.hb_tx(txq, 1000)
tx_t.start()

print("aaaa")

for i in range(10):
  txq.put(['192.168.122.12','192.168.122.13'])
  time.sleep(1)

print("dddd")

txq.join()

