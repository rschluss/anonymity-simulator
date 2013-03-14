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
import logging
import math
import pickle
import random

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
  parser.add_argument("-a", "--analyze", default=False, action="store_const",
      dest="analyze", const=True, help="Analyze not simulate")
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
  parser.add_argument("-s", "--start", type=float, default=0.0,
      help="specifies the region between bootstrapping and evaluation "
      "(default: 0)")
  parser.add_argument("-e", "--end", type=float, default=-1,
      help="specifies the end time for evaluation (default: all / -1)")
  parser.add_argument("-t", "--trainer", default=None,
      help="specifies a trainer for the anonymity data for static splitting "
      "groups: join, rank, or random (default: None)")
  parser.add_argument("-x", "--policy", default="min_anon",
      help="specifies the policy for the simulator: "
      "min_anon, static_split, dynamic_split (default: min_anon)")
  args = parser.parse_args()

  logging.basicConfig(level=args.log_level)

  msg_parser = DefaultParse(filename=args.input)
  total = len(msg_parser.users)
  trainer = None
  if args.trainer == "join":
    trainer = AnonymitySimulator.join_trainer
  elif args.trainer == "rank":
    trainer = AnonymitySimulator.rank_trainer
  elif args.trainer == "random":
    trainer = AnonymitySimulator.random_trainer

  anon_sim = AnonymitySimulator(total, msg_parser.events, \
      min_anon = args.min_anon, \
      pseudonyms_per_client = args.pseudonyms_per_client, \
      clients_per_client = args.clients_per_client, \
      round_time_span = args.round_time_span, \
      policy = args.policy, \
      trainer = trainer, \
      trainer_time = args.start,
      end_time = args.end)

  total_clients = total * args.clients_per_client
  total_pseudonyms = total * args.pseudonyms_per_client

  print "Total clients: %s" % (total_clients, )
  print "Total pseudonyms: %s" % (total_pseudonyms, )
  print "Delivered messages: %s" % (anon_sim.on_time, )
  print "Lost messages: %s" % (anon_sim.lost_messages)
  print "Delays: %s" % (anon_sim.delayed_times)

  to_print = []
  for client in anon_sim.clients:
    if(total_pseudonyms == len(client.pseudonyms)):
      continue
    to_print.append(len(client.pseudonyms))
  print "Clients: %s" % (to_print,)

  to_print = []
  for pseudonym in anon_sim.pseudonyms:
    if(total_clients == len(pseudonym.clients)):
      continue
    to_print.append(len(pseudonym.clients))
  print "Pseudonyms: %s" % (to_print,)

class AnonymitySimulator:
  """ Processes a data set to calculate both the clients' and their
  respective message pseudonyms' anonymity over time. """
  class Client:
    """ Represents a single client """
    def __init__(self, uid, total):
      self.uid = uid
      self.pseudonyms = {num: True for num in range(total)}
      self.coins = {num: -1 for num in range(total)}
      self.online = False

      self.online_time = 0
      self.last_time = -1 

      self.rand = random.Random()
      self.rand.seed(uid)

    def set_online(self, ctime):
      """ Set the client as online """
      self.online = True
      self.last_time = ctime

    def set_offline(self, ctime):
      """ Set the client as offline """
      self.online = False
      self.online_time += ctime - self.last_time
      self.last_time = -1

    def get_online_time(self, ctime = 0):
      if ctime == 0 or self.last_time == -1:
        return self.online_time
      return self.online_time + ctime - self.last_time

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

    def flip_coins(self, uids, prob = .1):
      for uid in uids:
        if self.coins[uid] != -1:
          continue
        self.coins[uid] = self.rand.random() < prob

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

  def __init__(self, total, events, min_anon = 0,
      pseudonyms_per_client = 1, clients_per_client = 1,
      round_time_span = 2.0, policy = "min_anon",
      trainer=None, trainer_time=0,
      end_time=-1):

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
    self.on_time = 0
    self.lost_messages = 0
    self.delayed_times = []
    self.end_time = end_time

    self.policy = None

    if trainer_time > 0:
      if trainer == None:
        events = self.bootstrap_trainer(events, trainer_time)
      else:
        events = trainer(self, events, trainer_time)

    self.policy = self.maintain_min_anon
    if policy == "static_split":
      self.policy = self.static_splitting
    elif policy == "dynamic_split":
      pass

    if self.policy == self.coin_flip:
      uids = []
      for client in self.clients:
        if not client.get_online():
          uids.append(client.uid)

      for client in self.clients:
        if client.get_online():
          client.flip_coins(uids, 1.0 / float(len(self.clients)))

    self.process_events(events)

  def bootstrap_trainer(self, events, trainer_time):
    if trainer_time == 0:
      trainer_time = self.round_time_span

    to_prepend = []
    idx = 0
    while idx < len(events) and events[idx][0] < trainer_time:
      event = events[idx]
      idx += 1

      if event[1] == "join":
        self.on_join(event[0], event[2])
      elif event[1] == "quit":
        self.on_quit(event[0], event[2])
      elif event[1] == "msg":
        if trainer_time == self.round_time_span:
          to_prepend.append(event)
      else:
        assert(False)

    if len(to_prepend) > 0:
      return to_prepend.extend(events[idx:])
    return events[idx:]

  def static_splitting_init(self, splitting_order):
    self.group_online = []
    self.split_group = []
    self.splits = {}

    groups = len(splitting_order) / self.min_anon
    remaining = len(splitting_order) % self.min_anon
    min_anon = self.min_anon + remaining / groups
    remaining = remaining % groups

    count = 0
    group = []
    group_idx = 0
    online = True

    for uid in splitting_order:
      self.splits[uid] = group_idx
      group.append(uid)
      online = online and self.clients[uid].get_online()

      count += 1
      if count >= min_anon:
        if count == min_anon and remaining > 0:
          remaining -= 1
        else:
          self.split_group.append(group)
          self.group_online.append(online)
          group_idx += 1
          count = 0
          group = []
          online = True

  def rank_trainer(self, events, trainer_time):
    events = self.bootstrap_trainer(events, trainer_time)

    clients = list(self.clients)
    clients.sort(key=lambda client: client.get_online_time(trainer_time))

    splitting_order = []
    for client in clients:
      splitting_order.append(client.uid)
    self.static_splitting_init(splitting_order)

    return events

  def join_trainer(self, events, trainer_time):
    events = self.bootstrap_trainer(events, trainer_time)

    splitting_order = []
    for client in self.clients:
      splitting_order.append(client.uid)
    self.static_splitting_init(splitting_order)

    return events

  def random_trainer(self, events, trainer_time):
    events = self.bootstrap_trainer(events, trainer_time)

    splitting_order = range(len(self.clients))
    rand = random.Random()
    rand.shuffle(splitting_order)
    self.static_splitting_init(splitting_order)

    return events

  def process_events(self, events):
    events.reverse()
    delayed_msgs = []
    msgs = []
    
    end_time = self.end_time if self.end_time != -1 else events[0][0] + 1.0

    while len(events) > 0 and events[-1][0] < end_time:
      for msg in delayed_msgs:
        if msg not in msgs:
          msg_time = msg[0] + self.round_time_span - (msg[0] % self.round_time_span)
          self.delayed_times.append(next_time - msg_time)

      to_quit = []
      delayed_msgs = list(msgs)

      # Move us to the period during the next event
      next_time = min(events[-1][0] + self.round_time_span - (events[-1][0] % self.round_time_span), end_time)
      joined = {}

      while len(events) > 0 and events[-1][0] < next_time:
        event = events.pop()
        if event[1] == "join":
          self.on_join(event[0], event[2])
          joined[event[2]] = True
        elif event[1] == "msg":
          msgs.append(event)
        elif event[1] == "quit":
          to_quit.append(event)
        else:
          assert(False)

      to_delay = []
      for event in msgs:
        if not self.on_msg(event[0], event[2]):
          to_delay.append(event)
        elif event not in delayed_msgs:
          self.on_time += 1
      msgs = to_delay

      for event in to_quit:
        if event[2] in joined:
          continue
        self.on_quit(event[0], event[2])

    # No more join / quit events and there are still message posting events
    # add these to lost messages and break
    self.lost_messages += len(msgs)
    for msg in msgs:
      self.static_splitting(msg[0],msg[2][0], msg[2][1], True)

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    for idx in range(self.clients_per_client):
      self.clients[uid + (idx * self.total)].set_online(etime)

    if self.policy == self.coin_flip:
      for client in self.clients:
        if not client.get_online():
          for idx in range(self.clients_per_client):
            self.clients[uid + (idx * self.total)].flip_coins([client.uid], math.log(len(self.clients)) / (len(self.clients) * len(self.clients)))
    elif self.policy == self.static_splitting:
      group_idx = self.splits[uid]
      good = True
      for g_uid in self.split_group[group_idx]:
        if not self.clients[g_uid].get_online():
          good = False
          break
      if good:
        self.group_online[group_idx] = True

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    for idx in range(self.clients_per_client):
      self.clients[uid + (idx * self.total)].set_offline(etime)

    if self.policy == self.coin_flip:
      for client in self.clients:
        if client.get_online():
          client.flip_coins([uid])
    elif self.policy == self.static_splitting:
      group_idx = self.splits[uid]
      self.group_online[group_idx] = False

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """
    if not self.clients[uid].get_online():
      # Should be a delayed event!
      return False

    if self.policy(etime, uid, msg):
      for client in self.clients:
        if not client.get_online():
          client.remove_slot(uid)
          self.pseudonyms[uid].remove_client(client.uid)
      return True
    return False

  def maintain_min_anon(self, etime, uid, msg):
    for client in self.clients:
      if not client.get_online():
        if client.remove_if(uid) <= self.min_anon or \
            self.pseudonyms[uid].remove_if(client.uid) <= self.min_anon:
          return False

    return True

  def always(self, etime, uid, msg):
    return True

  def coin_flip(self, etime, uid, msg):
    for idx in range(self.clients_per_client):
      pclient = self.clients[uid + (idx * self.total)]
      for client in self.clients:
        if client.get_online():
          continue
        assert(pclient.coins[client.uid] != -1)
        if pclient.coins[client.uid]:
          return False
    return self.maintain_min_anon(etime, uid, msg)

  def static_splitting(self, etime, uid, msg, tprint = False):
    group_idx = self.splits[uid]
    if not self.group_online[group_idx]:
      logging.info("%s %s %s %s" % (etime, uid, group_idx, self.split_group[group_idx]))
      return False

    group_idx = 0
    for online in self.group_online:
      if not online:
        for g_uid in self.split_group[group_idx]:
          self.pseudonyms[uid].remove_client(g_uid)
      group_idx += 1
    return True
    """
    # Old code
    group = self.splits[uid]
    count = 0
    for g_uid in self.split_group[group]:
      if not self.clients[g_uid].get_online():
        count += 1
    if count > 0:
      if tprint:
        print "%s %s %s %s %s" % (etime, count, uid, g_uid, self.split_group[group])
      return False

    return self.maintain_min_anon(etime, uid, msg)
    """

if __name__ == "__main__":
  main()
