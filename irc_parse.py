#!/usr/bin/python2

"""Parses a set of Irc events and converts it into a data set for the
AnonymitySimulator."""

import logging

class IrcParse:
  """ Parses the Irc log produced by irc_crawl.py creating
  a list of IrcParse.User and events that can then be plugged into
  the AnonymitySimulator """
  class User:
    """ Represents a single user's activity """
    def __init__(self, name, ctime, uid):
      self.name = name
      self.online_time = [ctime]
      self.msgs = []
      self.online = True
      self.host = ""
      self.uid = uid

    def join(self, ctime):
      """ User has joined """
      if self.online:
        return
      self.online_time.append(ctime)
      self.online = True

    def quit(self, ctime):
      """ User has quit """
      assert(self.online)
      self.online_time.append(ctime)
      self.online = False

    def add_msg(self, etime, msg):
      """ User posted a message """
      self.msgs.append((etime, msg))

    def set_host(self, host):
      """ Retrieved the user's host info """
      self.host = host

    def __repr__(self): 
      return self.__str__()

    def __str__(self):
      return "%s@%s: %s" % (self.name, self.host, len(self.msgs))

  def __init__(self, events):
    self.users = {}
    self.events = []

    event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "nick" : self.on_nick,
        "msg" : self.on_msg,
        "whois" : self.on_whois
        }

    for event in events:
      callback = event_actions.get(event[1], None)
      callback and callback(event[0], event[2])

  def on_join(self, etime, name):
    """ Handler for the client join event """
    if name in self.users:
      logging.info("Client rejoined: %s" % (name, ))
      self.users[name].join(etime)
    else:
      logging.info("Client joined: %s" % (name, ))
      self.users[name] = IrcParse.User(name, etime, len(self.users))
    self.events.append((etime, "join", self.users[name].uid, "join"))

  def on_nick(self, etime, (oldname, newname)):
    """ Handler for the client nick (name change) event """
    if oldname not in self.users:
      return

    logging.info("Nickname change: %s : %s" % (oldname, newname))
    self.users[newname] = self.users[oldname]
    self.users[newname].name = newname
    del self.users[oldname]

  def on_quit(self, etime, name):
    """ Handler for the client quit event """
    if name not in self.users:
      return

    logging.info("Client quit: %s" % (name, ))
    self.users[name].quit(etime)
    self.events.append((etime, "quit", self.users[name].uid))

  def on_msg(self, etime, (name, msg)):
    """ Handler for the client message post event """
    if name not in self.users:
      return

    logging.info("%s: %s" % (name, msg))
    self.users[name].add_msg(etime, msg)
    self.events.append((etime, "msg", (self.users[name].uid, msg)))

  def on_whois(self, etime, (name, host)):
    """ Handler for the client host inquiry event """
    if name not in self.users:
      return

    self.users[name].set_host(host)
