#!/usr/bin/python3

#
# web_vhost_gen.py
#
# Parms 1) target host name
#
# Generate ZBX-Vhost application if it doesn't exist
#          delete existing ZBX-Vhost web tests
#          delete existing ZBX-Vhost items (cert checks)
#          http and https web tests for each non-default host interface
#          cert expiration test 
#          appropriate triggers for these tests

from pyzabbix import ZabbixAPI

import json
import sys
from operator import itemgetter
from os import environ

# activate these lines for tracing
import logging
logging.basicConfig(filename='pyzabbix_debug.log',level=logging.DEBUG)

# The hostname at which the Zabbix web interface is available
ZABBIX_SERVER = 'https://'+environ['Zhost']+'/zabbix'

zapi = ZabbixAPI(ZABBIX_SERVER)

# Login to the Zabbix API
zapi.login(environ['Zuser'], environ['Zpass'])

# Command line arg is the host to process
target_host = str(sys.argv[1])

# get the target host, applications, interfaces and HttpTests
host = zapi.host.get(filter={"host":target_host}, output="extend", 
	selectApplications="extend", selectInterfaces="extend")
#print json.dumps(host, indent=4, sort_keys=True)

# prettyHostName = name as in Zabbix, could be mIxEd case.....  

if len(host) > 0:
    host = host[0]
    hostId = host['hostid']
    prettyHostName = host['host']

applications = host['applications']
#print json.dumps(applications, indent=4, sort_keys=True)

# See if application ZBX-Vhost exists, get appid if it does, create it if it doesn't
appexists = 0
for application in applications:
   if application['name'] == "ZBX_Vhost":
      appexists = 1
      appid = application['applicationid']

if not appexists:
   print("Creating new application for", hostId)	
   create_result = zapi.application.create(hostid=hostId,name="ZBX_Vhost")
#  print json.dumps(create_result, indent=4, sort_keys=True)
   appid = create_result['applicationids'][0]

appArray = []
appArray.append(appid)

# Delete existing web tests
web_tests = zapi.httptest.get(hostid=hostId,applicationids=appid,output="extend")

#print json.dumps(web_tests, indent=4, sort_keys=True)
for test in web_tests:
   zapi.httptest.delete(test['httptestid'])

# Delete existing items
items = zapi.item.get(hostid=hostId,applicationids=appid,output="extend",selectTriggers="extend")

#print json.dumps(items, indent=4, sort_keys=True)

for item in items:
   zapi.item.delete(parms=item['itemid'])

# Create new items, web tests and triggers
for interface in sorted(host['interfaces'], key=itemgetter('main'), reverse=True):
   
   if interface['type'] != '1':
      continue 

   if interface['main'] == '1':
      baseInterface = interface['interfaceid']
      continue
   
   if interface['port'] != '80':
	   print('Creating cert check item for', interface['dns'])
	   this_key = 'cert_days_left.sh['+interface['dns']+','+interface['port']+']'
	   item_resp = zapi.item.create({ 'name' : '$1 SSL Certificate days till expiration', 
	      'key_' : this_key,
	      'type' : '10',
	      'hostid' : hostId,
	      'value_type' : '0',
	      'delay' : '43200',
	      'interfaceid' : baseInterface,
	      'applications' : appArray,
	      }) 

	#  print 'Creating < 3 day disaster trigger' 
	   trigger_resp = zapi.trigger.create({ 'description' : interface['dns']+' Certificate expires within 3 days',
	      'expression' : '{'+prettyHostName+':'+this_key+'.last()}<4', 
	      'priority' : '5',
              'status' : '0',
	      })

	#  print 'Creating < 10 day high trigger' 
	   trigger_resp = zapi.trigger.create({ 'description' : interface['dns']+' Certificate expires within 10 days', 
	      'expression' : '{'+prettyHostName+':'+this_key+'.last()}<10', 
	      'priority' : '4',
              'status' : '0',
	      'dependencies' : [ {"triggerid" : trigger_resp['triggerids'][0]} ],
	      })

	#  print 'Creating < 15 day average trigger' 
	   trigger_resp = zapi.trigger.create({ 'description' : interface['dns']+' Certificate expires within 15 days',
	      'expression' : '{'+prettyHostName+':'+this_key+'.last()}<15',
	      'dependencies' : [ {"triggerid" : trigger_resp['triggerids'][0]} ],
	      'priority' : '3',
              'status' : '0',
	      })

	#  print 'Creating < 30 day warning trigger' 
	   trigger_resp = zapi.trigger.create({ 'description' : interface['dns']+' Certificate expires within 30 days',
	      'expression' : '{'+prettyHostName+':'+this_key+'.last()}<30',
	      'priority' : '2',
	      'dependencies' : [{"triggerid" : trigger_resp['triggerids'][0]} ],
	      })

	#  print ' '

   print('Creating http web test for ', interface['dns'])
   web_resp = zapi.httptest.create({ 'name' : interface['dns']+' http test',
        'hostid' : hostId,
        'applicationid' : appid,
        'delay' : '240',
        'steps' : [ { 'name' : 's1',
                      'url' : 'http://'+interface['dns'],
                      'status_codes' : '200',
                      'no' : '1',
                      } ],
         })

   trigger_resp = zapi.trigger.create({ 'description' : interface['dns']+' http web site problem',
      'expression' : '{'+prettyHostName+':web.test.fail['+interface['dns']+' http test].min(#2)}>0',
      'priority' : '4',
      'status' : '1',
       }) 

   if interface['port'] != '80':
	   print('Creating https web test')
	   web_resp = zapi.httptest.create({ 'name' : interface['dns']+' https test',
		'hostid' : hostId,
		'applicationid' : appid,
		'delay' : '240',
		'verify_host' : '1',
		'verify_peer' : '1',
		'steps' : [ { 'name' : 's1',
			      'url' : 'https://'+interface['dns'], 
			      'status_codes' : '200',  
			      'no' : '1',  
			      } ],
		 })

	   trigger_resp = zapi.trigger.create({ 'description' : interface['dns']+' https web site problem',
	      'expression' : '{'+prettyHostName+':web.test.fail['+interface['dns']+' https test].min(#2)}>0',
	      'priority' : '4',
	      'status' : '1',
	       })

