#!/usr/bin/python3

import sbp, time

x = sbp.system()
x.create_cluster()
x.cluster[1000].Nodes[2].start_all_links()




time.sleep(100)
