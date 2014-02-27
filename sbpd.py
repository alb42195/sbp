#!/usr/bin/python3

import sbp, time

x = sbp.system()
x.create()
#x.cluster[1000].Nodes[2].start_all_links()
x.start()



time.sleep(100)
