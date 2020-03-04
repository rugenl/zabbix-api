#!/usr/bin/python3
"""
 add_host_if.py Add host interfaces for vhost web tests

 Parms 1) target host name
       2) interface dns name
       3) port
"""

import json
import sys
import socket
from pyzabbix import ZabbixAPI
from os import environ

# activate these lines for tracing
#import logging
#logging.basicConfig(filename='pyzabbix_debug.log',level=logging.DEBUG)

# The hostname at which the Zabbix web interface is available
ZABBIX_SERVER = 'https://'+environ['Zhost']+'/zabbix'

zapi = ZabbixAPI(ZABBIX_SERVER)

# Login to the Zabbix API
zapi.login(environ['Zuser'], environ['Zpass'])

# Command line arg is the host to process
target_host = str(sys.argv[1])
dns = str(sys.argv[2])
port = str(sys.argv[3])

# get the target host
host = zapi.host.get(filter={"host":target_host}, output="extend", selectInterfaces="extend")
#print json.dumps(host, indent=4, sort_keys=True)

if len(host) > 0:
    host = host[0]
    hostId = host['hostid']

for interface in host['interfaces']:
    if dns == interface["dns"]:
        print(interface["dns"])
        sys.exit('Interface exists, update in GUI')

ip = socket.gethostbyname(dns)

print('Adding to', target_host, dns, ip, port)
zapi.hostinterface.create(hostid=hostId, dns=dns, ip=ip, main='0', port=port, type='1', useip='0')
