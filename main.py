#!/usr/bin/python2

"""Reads the output from a data set, extracts the necessary data that
can then be run through the AnonymitySimulator."""

import codecs
import getopt
import logging
import pickle
import sys

from anon_sim import AnonymitySimulator
from irc_parse import IrcParse
from twitter_parse import TwitterParse

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

optlist, args = getopt.getopt(sys.argv[1:], "", ["type=", "input=", \
    "min_anon=", "clients_per_client=", "slots_per_client=", "debug"])
optdict = {}
for k,v in optlist:
  optdict[k] = v

datain = optdict.get("--input", "data")
dataset_type = optdict.get("--type", "irc")
clients_per_client = int(optdict.get("--clients_per_client", 1))
slots_per_client = int(optdict.get("--slots_per_client", 1))
min_anon = int(optdict.get("--min_anon", 0))
round_time_span = float(optdict.get("--round_time_span", 2.0))

if "--debug" in optdict:
  logging.basicConfig(level=logging.INFO)

if dataset_type == "irc":
  parser = IrcParse(filename=datain)
elif dataset_type == "twitter":
  parser = TwitterParse(filename=datain)
else:
  print "Invalid dataset type: %s" % (dataset_type, )
  sys.exit(-1)

total = len(parser.users)
anon_sim = AnonymitySimulator(total, parser.events, min_anon = min_anon, \
    slots_per_client = slots_per_client, \
    clients_per_client = clients_per_client, \
    round_time_span = round_time_span)

total_clients = total * clients_per_client
total_slots = total * slots_per_client

print "Total clients: %s" % (total_clients, )
print "Total slots: %s" % (total_slots, )
print "Lost messages: %s" % (anon_sim.lost_messages)

print "Clients:"
for client in anon_sim.clients:
  if(total_slots == len(client.slots)):
    continue
  print len(client.slots)

print "Slots:"
for slot in anon_sim.slots:
  if(total_clients == len(slot.clients)):
    continue
  print len(slot.clients)
