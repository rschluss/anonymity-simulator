#!/usr/bin/python2

"""
Common class for evaluating anonymity over a data set
Event structure:
  (time, "join", uid)
  (time, "quit", uid)
  (time, "msg", (uid, msg))

A join within a round, happens at the beginning of each round
A msg happens afterward
A quit delays until the beginning of the following round
A user may delay exiting in order to transmit a message
"""

import argparse
import codecs
import logging
import pickle
import sys

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

def main():
  parser = argparse.ArgumentParser(description="The AnonymitySimulator")
  parser.add_argument("-i", "--input", default="data",
      help="input dataset")
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

  msg_parser = DefaultParse(filename=args.input)
  total = len(msg_parser.users)
  anon_sim = AnonymitySimulator(total, msg_parser.events, \
      min_anon = args.min_anon, \
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

class AnonymitySimulator:
  """ Processes a data set to calculate both the clients' and their
  respective message pseudonyms' anonymity over time. """
  class Client:
    """ Represents a single client """
    def __init__(self, uid, total):
      self.uid = uid
      self.pseudonyms = {num: True for num in range(total)}
      self.online = False

    def set_online(self):
      """ Set the client as online """
      self.online = True

    def set_offline(self):
      """ Set the client as offline """
      self.online = False

    def get_online(self):
      """ Return the client's online state """
      return self.online

    def remove_if(self, idx):
      """ Returns the count if the slot was removed """
      count = len(self.pseudonyms)
      if idx in self.pseudonyms:
        count -= 1
      return count

    def remove_slot(self, idx):
      """ Remove a slot from the client's anonymity set """
      if idx in self.pseudonyms:
        del self.pseudonyms[idx]

  class Slot:
    """ Represents a single message session """
    def __init__(self, uid, total):
      self.uid = uid
      self.clients = {num: True for num in range(total)}

    def remove_if(self, idx):
      """ Returns the count if the client was removed """
      count = len(self.clients)
      if idx in self.clients:
        count -= 1
      return count

    def remove_client(self, idx):
      """ Remove a client from the slot's anonymity set """
      if idx in self.clients:
        del self.clients[idx]

  def __init__(self, total, events, min_anon = 0, pseudonyms_per_client = 1,
      clients_per_client = 1, round_time_span = 2.0):

    self.event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "msg" : self.on_msg,
        }

    total_clients = total * clients_per_client
    total_pseudonyms = total * pseudonyms_per_client

    self.clients = [AnonymitySimulator.Client(uid, total_pseudonyms) \
        for uid in range(total_clients)]
    self.pseudonyms = [AnonymitySimulator.Slot(uid, total_clients) \
        for uid in range(total_pseudonyms)]

    self.clients_per_client = clients_per_client
    self.pseudonyms_per_client = pseudonyms_per_client
    self.min_anon = min_anon
    self.round_time_span = round_time_span
    self.total = total
    self.lost_messages = 0

    self.process_events(events)

  def process_events(self, events):
    events.reverse()
    delayed_msgs = []

    while len(events) > 0:
      to_quit = []
      msgs = delayed_msgs
      delayed_msgs = []

      # Move us to the period during the next event
      next_time = events[-1][0] + 2.0 - (events[-1][0] % self.round_time_span)

      while len(events) > 0 and events[-1][0] < next_time:
        event = events.pop()
        if event[1] == "join":
          self.on_join(event[0], event[2])
        elif event[1] == "msg":
          msgs.append(event)
        elif event[1] == "quit":
          to_quit.append(event)
        else:
          assert(False)

      for event in msgs:
        if not self.on_msg(event[0], event[2]):
          delayed_msgs.append(event)

      for event in to_quit:
        self.on_quit(event[0], event[2])

    # No more join / quit events and there are still message posting events
    # add these to lost messages and break
    self.lost_messages += len(delayed_msgs)


  def on_join(self, etime, uid):
    """ Handler for the client join event """
    for idx in range(self.clients_per_client):
      self.clients[uid + (idx * self.total)].set_online()

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    for idx in range(self.clients_per_client):
      self.clients[uid + (idx * self.total)].set_offline()

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """
    if not self.clients[uid].get_online():
      # Should be a delayed event!
      return False

    for client in self.clients:
      if not client.get_online():
        if client.remove_if(uid) <= self.min_anon or \
            self.pseudonyms[uid].remove_if(client.uid) <= self.min_anon:
          return False

    for client in self.clients:
      if not client.get_online():
        client.remove_slot(uid)
        self.pseudonyms[uid].remove_client(client.uid)

    return True

if __name__ == "__main__":
  main()
