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
      "min_anon, split (default: min_anon)")
  parser.add_argument("-z", "--split_size", type=int, default=1,
      help="defines the buddy sizes for the splitting algorithm")
  parser.add_argument("--percent", type=float, default=1.0,
      help="models the adversaries guess that a pseudonym would be active"
      "if the member were online")
  args = parser.parse_args()

  logging.basicConfig(level=args.log_level)

  msg_parser = DefaultParse(filename=args.input)
  total = len(msg_parser.users)

  if args.policy == "min_anon":
    anon_sim = AnonymitySimulator(total, msg_parser.events,
        min_anon = args.min_anon,
        pseudonyms_per_client = args.pseudonyms_per_client,
        round_time_span = args.round_time_span,
        start_time = args.start,
        end_time = args.end)
  elif args.policy == "dynamic_split":
    anon_sim = DynamicSplitting(total, msg_parser.events,
        min_anon = args.min_anon,
        pseudonyms_per_client = args.pseudonyms_per_client,
        round_time_span = args.round_time_span,
        start_time = args.start,
        end_time = args.end,
        trainer = args.trainer,
        split_size = args.split_size)
  elif args.policy == "static_split":
    anon_sim = StaticSplitting(total, msg_parser.events,
        min_anon = args.min_anon,
        pseudonyms_per_client = args.pseudonyms_per_client,
        round_time_span = args.round_time_span,
        start_time = args.start,
        end_time = args.end,
        trainer = args.trainer,
        split_size = args.split_size)

  anon_sim.run()

  total_clients = total 
  total_pseudonyms = total * args.pseudonyms_per_client

  print "Total clients: %s" % (total_clients, )
  print "Total pseudonyms: %s" % (total_pseudonyms, )
  print "Delivered messages: %s" % (anon_sim.on_time, )
  print "Delayed messages: %s" % (len(anon_sim.delayed_times), )
  print "Lost messages: %s" % (len(anon_sim.lost_messages), )
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

  to_print = []
  result = {}
  for pseudonym in anon_sim.pseudonyms:
    if(total_clients == len(pseudonym.clients)):
      continue
    max_idx = -1
    max_value = 0
    own_rank = 0
    accumulated = 0
    same = 0
    near = 0
    own_value = pseudonym.client_rank[pseudonym.uid]
    up_own = own_value * 1.1
    down_own = own_value * 0.9
    for cuid in pseudonym.client_rank.keys():
      cvalue = pseudonym.client_rank[cuid]
      accumulated += cvalue
      if cvalue > max_value:
        max_value = cvalue
        max_idx = cuid
      if cvalue > own_value:
        own_rank += 1
      if cvalue == own_value:
        same += 1
      if cvalue > down_own and cvalue < up_own:
        near += 1
    result[pseudonym.uid] = max_idx
    prob = float(own_value) / float(accumulated)
    to_print.append((pseudonym.uid, max_idx, max_value, own_rank, own_value, same, near, prob))

  change = True
  kdx = 0
  while change:
    jdx = 0
    change = False
    kdx += 1
    for item0 in result.keys():
      jdx += 1
      for item1 in result.keys():
        if item0 == item1:
          continue
        if result[item0] != result[item1]:
          continue
        idx = result[item0]
        val0 = anon_sim.pseudonyms[item0].client_rank[idx]
        val1 = anon_sim.pseudonyms[item1].client_rank[idx]
        to_swap = item0
        val_swap = val0
        if val1 < val0:
          to_swap = item1
          val_swap = val1
        else:
          continue

        next_val = 0
        next_idx = -1
        for uid in anon_sim.pseudonyms[to_swap].client_rank.keys():
          if uid == idx:
            continue
          rank =  anon_sim.pseudonyms[to_swap].client_rank[uid]
          if rank >= val_swap or rank <= next_val:
            continue
          next_val = rank
          next_idx = uid

        if next_idx == -1:
          continue
        print "%s %s %s" % (to_swap, result[to_swap], next_idx)
        result[to_swap] = next_idx
        change = True

  print "Pseudonyms' Ranks: "
  found0 = 0
  found1 = 0
  for top in to_print:
    found0_0 = top[0] == top[1]
    found1_0 = result[top[0]] == top[0]
    print "\t%s -- %s -- %s -- %s" % (found0_0, found1_0, top, result[top[0]])
    if found1_0:
      found1 += 1
    if found0_0:
      found0 += 1
  print "Found: %s -- %s" % (found0, found1)


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
      """ Returns the count if the nym was removed """
      count = len(self.pseudonyms)
      if idx in self.pseudonyms:
        count -= 1
      return count

    def remove_nym(self, idx):
      """ Remove a nym from the client's anonymity set """
      if idx in self.pseudonyms:
        del self.pseudonyms[idx]

    def flip_coins(self, uids, prob = .1):
      for uid in uids:
        if self.coins[uid] != -1:
          continue
        self.coins[uid] = self.rand.random() < prob

  class Pseudonym:
    """ Represents a single message session """
    def __init__(self, uid, total):
      self.uid = uid
      self.clients = {num: True for num in range(total)}
      self.client_rank = {num: 1.0 for num in range(total)}

    def remove_if(self, idx):
      """ Returns the count if the client was removed """
      count = len(self.clients)
      if idx in self.clients:
        count -= 1
      return count

    def remove_client(self, idx):
      """ Remove a client from the nym's anonymity set """
      if idx in self.clients:
        del self.clients[idx]
        del self.client_rank[idx]

  def __init__(self, total, events, min_anon = 0,
      pseudonyms_per_client = 1, round_time_span = 2.0,
      start_time=0, end_time=-1):

    self.event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "msg" : self.on_msg,
        }

    total_clients = total
    total_pseudonyms = total * pseudonyms_per_client

    self.clients = [AnonymitySimulator.Client(uid, total_pseudonyms) \
        for uid in range(total_clients)]
    self.pseudonyms = [AnonymitySimulator.Pseudonym(uid, total_clients) \
        for uid in range(total_pseudonyms)]

    self.pseudonyms_per_client = pseudonyms_per_client
    self.min_anon = min_anon
    self.round_time_span = round_time_span
    self.total = total
    self.start_time = start_time
    self.on_time = 0
    self.delayed_times = []
    self.end_time = end_time
    self.percent = .01

    self.events = self.bootstrap(events)

  def bootstrap(self, events):
    start_time = self.start_time if self.start_time != 0 else self.round_time_span

    to_prepend = []
    idx = 0
    while idx < len(events) and events[idx][0] < start_time:
      event = events[idx]
      idx += 1

      if event[1] == "join":
        AnonymitySimulator.on_join(self, event[0], event[2])
      elif event[1] == "quit":
        AnonymitySimulator.on_quit(self, event[0], event[2])
      elif event[1] == "msg":
        if start_time == self.round_time_span:
          to_prepend.append(event)
      else:
        assert(False)

    if len(to_prepend) > 0:
      to_prepend.extend(events[idx:])
      return to_prepend
    return events[idx:]

  def run(self):
    self.process_events(self.events)

  def process_events(self, events):
    events.reverse()
    delayed_msgs = []
    msgs = []
    
    end_time = self.end_time if self.end_time != -1 else events[0][0] + 1.0
    next_time = self.round_time_span

    while len(events) > 0 and events[-1][0] < end_time:
      for msg in delayed_msgs:
        if msg not in msgs:
          msg_time = msg[0] + self.round_time_span - (msg[0] % self.round_time_span)
          self.delayed_times.append(next_time - msg_time)

      delayed_msgs = list(msgs)

      # Move us to the period during the next event
#      next_time = min(events[-1][0] + self.round_time_span - (events[-1][0] % self.round_time_span), end_time)
      next_time += self.round_time_span
      quit = {}

      while len(events) > 0 and events[-1][0] < next_time:
        event = events.pop()
        if event[1] == "join":
          if event[2] in quit:
            del quit[event[2]]
            continue
          self.on_join(event[0], event[2])
        elif event[1] == "msg":
          msgs.append(event)
        elif event[1] == "quit":
          quit[event[2]] = event[0]
        else:
          assert(False)

      to_delay = []
      delivered = {}
      for event in msgs:
        if not self.on_msg(event[0], event[2]):
          to_delay.append(event)
        else:
          delivered[event[2][0]] = True
          if event not in delayed_msgs:
            self.on_time += 1
      msgs = to_delay

      for nym in self.pseudonyms:
        if nym.uid in delivered:
          continue
        for cuid in nym.client_rank.keys():
          if self.is_member_online(cuid):
            nym.client_rank[cuid] *= (1 - self.percent)

      for uid, etime in quit.items():
        self.on_quit(etime, uid)

    # No more join / quit events and there are still message posting events
    # add these to lost messages and break
    self.lost_messages = msgs
#    if self.policy == self.splitting:
#      for msg in msgs:
#        self.splitting(msg[0],msg[2][0], msg[2][1], True)

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    self.clients[uid].set_online(etime)

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    self.clients[uid].set_offline(etime)

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """
    if not self.is_member_online(uid):
      # Should be a delayed event!
      return False

    if not self.check_min_anon(uid):
      return False

    for client in self.clients:
      if not self.is_member_online(client.uid):
        client.remove_nym(uid)
        self.pseudonyms[uid].remove_client(client.uid)
    return True

  def is_member_online(self, uid):
    return self.clients[uid].get_online()

  def check_min_anon(self, uid):
    clients_offline = 0
    for client in self.clients:
      if not self.is_member_online(client.uid):
        if client.remove_if(uid) < self.min_anon:
          return False
        if client.uid in self.pseudonyms[uid].clients:
          clients_offline += 1
          if len(self.pseudonyms[uid].clients) - clients_offline < self.min_anon:
            return False
    return True

class DynamicSplitting(AnonymitySimulator):
  def __init__(self, total, events, min_anon = 0,
      pseudonyms_per_client = 1, round_time_span = 2.0,
      start_time = 0, end_time = -1, trainer = None, split_size = 1):
    AnonymitySimulator.__init__(self, total, events, min_anon,
        pseudonyms_per_client, round_time_span, start_time, end_time)

    self.group_online = []
    self.split_group = []
    self.splits = {}
    self.join_queue = []
    self.offline_clients = []
    self.split_size = split_size

  def run(self):
    for client in self.clients:
      if not client.get_online():
        self.offline_clients.append(client.uid)

    AnonymitySimulator.run(self)

  def is_member_online(self, uid):
    if not self.clients[uid].get_online():
      return False

    if uid not in self.splits:
      if uid in self.join_queue:
        return False
      return True
    return self.group_online[self.splits[uid]]

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    self.clients[uid].set_online(etime)

    if uid not in self.splits:
      if uid not in self.join_queue:
        assert(uid in self.offline_clients)
        self.join_queue.append(uid)
      if len(self.join_queue) >= self.split_size:
        group_idx = len(self.split_group)
        group = []
        for g_uid in self.join_queue:
          self.offline_clients.remove(g_uid)
          self.splits[g_uid] = group_idx
          group.append(g_uid)
        self.split_group.append(group)
        self.group_online.append(True)
        self.join_queue = []
    else:
      group_idx = self.splits[uid]
      self.group_online[group_idx] = True
      for g_uid in self.split_group[group_idx]:
        if not self.clients[g_uid].get_online():
          self.group_online[group_idx] = False

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    self.clients[uid].set_offline(etime)

    if uid not in self.splits:
      # Dynamic splitting bootstrapping code
      if uid in self.join_queue:
        self.join_queue.remove(uid)
      else:
        clients = []
        for client in self.clients:
          if client.get_online() and \
              client.uid not in self.splits and \
              client.uid not in self.join_queue:
            clients.append(client)

        clients.sort(key=lambda client: client.get_online_time(etime))

        group_idx = len(self.split_group)
        self.splits[uid] = group_idx
        group = [uid]
        count = self.split_size - 1 if (2 * self.split_size - 1 < len(clients)) \
            else len(clients)
        for idx in range(count):
          self.splits[clients[idx].uid] = group_idx
          group.append(clients[idx].uid)
        self.split_group.append(group)
        self.group_online.append(False)

        for idx in group:
          for jdx in group:
            assert(idx in self.pseudonyms[jdx].clients)
    else:
      # Terminal splitting code
      group_idx = self.splits[uid]
      self.group_online[group_idx] = False

  def on_msg(self, etime, (uid, msg), tprint = False):
    """ Handler for the client message post event """
    if not self.is_member_online(uid):
      # Should be a delayed event!
      return False

    if not self.check_min_anon(uid):
      return False

    before = len(self.pseudonyms[uid].clients)
    before_group = self.pseudonyms[uid].clients
    group_idx = 0

    # Remove offline groups
    for online in self.group_online:
      if not online:
        for g_uid in self.split_group[group_idx]:
          self.clients[g_uid].remove_nym(uid)
          self.pseudonyms[uid].remove_client(g_uid)
      group_idx += 1

    # Remove non-bootstrapped clients
    for client in self.offline_clients:
      self.clients[client].remove_nym(uid)
      self.pseudonyms[uid].remove_client(client)

    if uid not in self.splits:
      return True

    after = len(self.pseudonyms[uid].clients)
    group_idx = self.splits[uid]

    for client in self.split_group[group_idx]:
      assert(client in self.pseudonyms[uid].clients)

    if before != after:
      logging.debug("Next: %s %s %s %s %s" % (before, after, uid, group_idx, len(self.split_group[group_idx])))
      logging.debug("Before: %s" % (before_group))
      logging.debug("After: %s" % (self.pseudonyms[uid].clients))
      logging.debug("Group: %s" % (self.split_group[group_idx]))

    return True

class StaticSplitting(DynamicSplitting):
  def __init__(self, total, events, min_anon = 0,
      pseudonyms_per_client = 1, round_time_span = 2.0,
      start_time = 0, end_time = -1, trainer = None,
      split_size = 1):

    DynamicSplitting.__init__(self, total, events, min_anon,
        pseudonyms_per_client, round_time_span,
        start_time, end_time, None, split_size)

    self.trainer = trainer

  def run(self):
    if self.trainer == "rank":
      splitting_order = self.rank_trainer()
    elif self.trainer == "join":
      splitting_order = self.join_trainer()
    else:
      splitting_order = self.random_trainer()

    groups = len(splitting_order) / self.split_size
    remaining = len(splitting_order) % self.split_size
    split_size = self.split_size + remaining / groups
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
      if count >= split_size:
        if count == split_size and remaining > 0:
          remaining -= 1
        else:
          self.split_group.append(group)
          self.group_online.append(online)
          group_idx += 1
          count = 0
          group = []
          online = True

    AnonymitySimulator.run(self)

  def rank_trainer(self):
    clients = list(self.clients)
    clients.sort(key=lambda client: client.get_online_time(self.start_time))

    splitting_order = []
    for client in clients:
      splitting_order.append(client.uid)
    return splitting_order

  def join_trainer(self):
    splitting_order = []
    for client in self.clients:
      splitting_order.append(client.uid)
    return splitting_order

  def random_trainer(self):
    splitting_order = range(len(self.clients))
    rand = random.Random()
    rand.shuffle(splitting_order)
    return splitting_order

class CoinFlip(AnonymitySimulator):
  def __init__(self, total, events, min_anon = 0,
      pseudonyms_per_client = 1, round_time_span = 2.0,
      start_time = 0, end_time = -1):
    AnonymitySimulator.__init__(total, events, min_anon,
        pseudonyms_per_client, round_time_span, start_time, end_time)

  def run(self):
    uids = []
    for client in self.clients:
      if not client.get_online():
        uids.append(client.uid)

    for client in self.clients:
      if client.get_online():
        client.flip_coins(uids, 1.0 / float(len(self.clients)))

    AnonymitySimulator.run(self)

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    self.clients[uid].set_online(etime)

    if self.policy == self.coin_flip:
      for client in self.clients:
        if not client.get_online():
          self.clients[uid].flip_coins( \
              [client.uid], math.log(len(self.clients)) / \
              (len(self.clients) * len(self.clients)))

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    self.clients[uid].set_offline(etime)

    if self.policy == self.coin_flip:
      for client in self.clients:
        if client.get_online():
          client.flip_coins([uid])

  def coin_flip(self, etime, uid, msg):
    pclient = self.clients[uid]
    for client in self.clients:
      if client.get_online():
        continue
      assert(pclient.coins[client.uid] != -1)
      if pclient.coins[client.uid]:
        return False
    return self.maintain_min_anon(etime, uid, msg)

if __name__ == "__main__":
  main()
