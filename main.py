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

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

optlist, args = getopt.getopt(sys.argv[1:], "", ["type=", "input=", \
    "min_anon=", "debug"])
optdict = {}
for k,v in optlist:
  optdict[k] = v

datain = optdict.get("--input", "data")
dataset_type = optdict.get("--type", "irc")
min_anon = int(optdict.get("--min_anon", 0))

if "--debug" in optdict:
  logging.basicConfig(level=logging.INFO)

f = open(datain, "rb")
events = pickle.load(f)
f.close()

if dataset_type == "irc":
  irc = IrcParse(events)
  total = len(irc.users)
  events = irc.events
else:
  print "Invalid dataset type: %s" % (dataset_type, )
  sys.exit(-1)

anon_sim = AnonymitySimulator(total, events, min_anon)

print "Total: %s" % (total, )
print "Lost messages: %s" % (anon_sim.lost_messages)

print "Clients:"
for client in anon_sim.clients:
  if(total == len(client.slots)):
    continue
  print len(client.slots)

print "Slots:"
for slot in anon_sim.slots:
  if(total == len(slot.clients)):
    continue
  print len(slot.clients)
