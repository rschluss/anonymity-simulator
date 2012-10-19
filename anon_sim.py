#!/usr/bin/python2

"""Common class for evaluating anonymity over a data set"""

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

    def set_get_online(self):
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

  def __init__(self, total, events, min_anon = 0):
    event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "msg" : self.on_msg,
        }

    self.clients = [AnonymitySimulator.Client(uid, total) for uid in range(total)]
    self.slots = [AnonymitySimulator.Slot(uid, total) for uid in range(total)]
    self.min_anon = min_anon
    self.lost_messages = 0

    for event in events:
      callback = event_actions.get(event[1], None)
      callback and callback(event[0], event[2])

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    self.clients[uid].set_get_online()

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    self.clients[uid].set_offline()

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """
    for client in self.clients:
      if not client.get_online():
        if client.remove_if(uid) <= self.min_anon or \
            self.slots[uid].remove_if(uid) <= self.min_anon:
          self.lost_messages += 1
          return

    for client in self.clients:
      if not client.get_online():
        client.remove_slot(uid)
        self.slots[uid].remove_client(client.uid)
