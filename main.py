#!/usr/bin/python2

"""Reads the output from a data set, extracts the necessary data that
can then be run through the AnonymitySimulator."""

import argparse
import codecs
import logging
import pickle
import sys

from anon_sim import AnonymitySimulator
from irc_parse import IrcParse
from twitter_parse import TwitterParse

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

class DefaultParse:
  def __init__(self, filename):
    self.events = []
    self.users = {}
    f = open(filename, "rb")

    while True:
      try:
        event = pickle.load(f)
        self.events.append(event)
        if event[1] == "join" and event[2] not in  self.users:
          self.users[event[2]] = event[2]
      except EOFError:
        break

    f.close()

parser = argparse.ArgumentParser(description="The AnonymitySimulator")
parser.add_argument("-i", "--input", default="data",
    help="input dataset")
parser.add_argument("-t", "--type", default="parsed",
    help="twitter, irc, or parsed (default: parsed)")
parser.add_argument("-c", "--clients_per_client", type=int, default=1,
    help="number of (virtual) clients per a client (default: 1)")
parser.add_argument("-p", "--pseudonyms_per_client", type=int, default=1,
    help="the number of pseudonyms per client (default: 1)")
parser.add_argument("-d", "--debug", dest="log_level", action="store_const",
    const=logging.DEBUG, help="sets the logging level to 'debug'")
parser.add_argument("--info", dest="log_level", action="store_const",
    const=logging.INFO, help="sets the logging level to 'info'")
parser.add_argument("-m", "--min_anon", type=int, default=0,
    help="minimum value for the anonymity meter, (default: 0)")
parser.add_argument("-r", "--round_time_span", type=float, default=2.0,
    help="specifies the duration of a round in seconds (default: 2.0)")
args = parser.parse_args()

if hasattr(args, "log_level"):
  logging.basicConfig(level=args.log_level)


if args.type == "irc":
  parser = IrcParse(filename=args.input)
elif args.type == "twitter":
  parser = TwitterParse(filename=args.input)
elif args.type == "parsed":
  parser = DefaultParse(filename=args.input)
else:
  print "Invalid dataset type: %s" % (dataset_type, )
  sys.exit(-1)

total = len(parser.users)
anon_sim = AnonymitySimulator(total, parser.events, min_anon = args.min_anon, \
    pseudonyms_per_client = args.pseudonyms_per_client, \
    clients_per_client = args.clients_per_client, \
    round_time_span = args.round_time_span)

total_clients = total * args.clients_per_client
total_pseudonyms = total * args.pseudonyms_per_client

print "Total clients: %s" % (total_clients, )
print "Total pseudonyms: %s" % (total_pseudonyms, )
print "Lost messages: %s" % (anon_sim.lost_messages)

print "Clients:"
for client in anon_sim.clients:
  if(total_pseudonyms == len(client.pseudonyms)):
    continue
  print len(client.pseudonyms)

print "Pseudonyms:"
for pseudonym in anon_sim.pseudonyms:
  if(total_clients == len(pseudonym.clients)):
    continue
  print len(pseudonym.clients)
