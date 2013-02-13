#!/usr/bin/python2

"""
Common class for evaluating anonymity over a data set
Event structure:
  (time, "join", uid)
  (time, "quit", uid)
  (time, "msg", (uid, msg))
"""

import logging

class AnonymitySimulator:
  """ Processes a data set to calculate both the clients' and their
  respective message slots' anonymity over time. """
  class Client:
    """ Represents a single client """
    def __init__(self, uid, total):
      self.uid = uid
      self.slots = {num: True for num in range(total)}
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
      count = len(self.slots)
      if idx in self.slots:
        count -= 1
      return count

    def remove_slot(self, idx):
      """ Remove a slot from the client's anonymity set """
      if idx in self.slots:
        del self.slots[idx]

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

  def __init__(self, total, events, min_anon = 0, slots_per_client = 1,
      clients_per_client = 1, round_time_span = 2.0):

    self.event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "msg" : self.on_msg,
        }

    total_clients = total * clients_per_client
    total_slots = total * slots_per_client

    self.clients = [AnonymitySimulator.Client(uid, total_slots) \
        for uid in range(total_clients)]
    self.slots = [AnonymitySimulator.Slot(uid, total_clients) \
        for uid in range(total_slots)]

    self.clients_per_client = clients_per_client
    self.slots_per_client = slots_per_client
    self.min_anon = min_anon
    self.round_time_span = round_time_span
    self.total = total
    self.lost_messages = 0
    self.delayed_events = []

    self.process_events(events)

  def process_events(self, events):
    next_time = self.round_time_span
    events.reverse()

    while len(events) > 0 or len(self.delayed_events) > 0:
      delayed_events = self.delayed_events
      self.delayed_events = []

      while len(delayed_events) > 0:
        event = delayed_events.pop()
        self.process_event(event)

      # No more join / quit events and there are still message posting events
      # add these to lost messages and break
      if len(events) == 0:
        self.lost_messages += len(self.delayed_events)
        break

      while len(events) > 0 and events[0][0] < next_time:
        event = events.pop()
        self.process_event(event)

      next_time += self.round_time_span

  def process_event(self, event):
    callback = self.event_actions.get(event[1], None)
    try:
      result = callback and callback(event[0], event[2])
    except:
      print event
      raise

    if not result:
      self.delayed_events.append(event)

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    for idx in range(self.clients_per_client):
      self.clients[uid + (idx * self.total)].set_online()

    return True

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    for idx in range(self.clients_per_client):
      self.clients[uid + (idx * self.total)].set_offline()

    return True

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """

    assert self.clients[uid].get_online()
    for client in self.clients:
      if not client.get_online():
        if client.remove_if(uid) <= self.min_anon or \
            self.slots[uid].remove_if(client.uid) <= self.min_anon:
          return False

    for client in self.clients:
      if not client.get_online():
        client.remove_slot(uid)
        self.slots[uid].remove_client(client.uid)

    return True
