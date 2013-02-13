#!/usr/bin/python2

"""Parses a set of Irc events and converts it into a data set for the
AnonymitySimulator."""

import getopt
import logging
import os
import pickle
import sys

def main():
  if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
    print "Usage: %s crawl.data" % (sys.argv[0],)
    return

  logging.basicConfig(level=logging.INFO)
  fname = sys.argv[1]
  dname = fname + "_data"
  if os.path.exists(dname):
    if not os.path.isdir(dname):
      print "Unable to write output to " + dname
      return
  else:
    os.makedirs(dname)

  irc = IrcParse(filename = sys.argv[1])
  for channel in irc.channels:
    cname = channel[1:].replace("/", "_")
    output = file(dname + "/" + cname, "w+")
    for line in irc.channels[channel].events:
      output.write(pickle.dumps(line))
    output.close()

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

    def add_msg(self, ctime, msg):
      """ User posted a message """
      assert(self.online)
      self.msgs.append((ctime, msg))

    def merge(self, other):

      # Merge online times
      online_time = []
      offline_time = []
      for idx in range(len(self.online_time)):
        if idx % 2 == 0:
          online_time.append(self.online_time[idx])
        else:
          offline_time.append(self.online_time[idx])

      for idx in range(len(other.online_time)):
        if idx % 2 == 0:
          online_time.append(other.online_time[idx])
        else:
          offline_time.append(other.online_time[idx])

      
      online_time.sort()
      offline_time.sort()
      times = []

      cstate = False

      on_idx = 0
      off_idx = 0

      while on_idx < len(online_time) and off_idx < len(offline_time):
        if online_time[on_idx] <= offline_time[off_idx]:
          if cstate:
            off_idx += 1
          else:
            cstate = True
            times.append(online_time[on_idx])
          on_idx += 1
        else:
          if cstate:
            cstate = False
            times.append(offline_time[off_idx])
          else:
            logging.critical("We should never have two offlines in a row without two onlines")
          off_idx += 1

      if cstate and off_idx < len(offline_time):
        times.append(offline_time[-1])
      elif not cstate and on_idx < len(online_time):
        times.append(online_time[on_idx])

      self.online_time = times
      self.msgs.extend(other.msgs)
      self.online = self.online or other.online

    def __repr__(self): 
      return self.__str__()

    def __str__(self):
      return "%s: messages: %s, uid: %s" % (self.name, len(self.msgs), self.uid)

  """ The Irc log contains many channels """
  class Channel:
    def __init__(self, name):
      self.name = name
      self.users = {}
      self.events = []
      self.cuid = 0
      self.merged_uids = {}

    def join(self, ctime, username):
      """ Handler for clients joining """
      if username in self.users:
        self.users[username].join(ctime)
        logging.info("%s: %s - Client rejoined: %s/%s" % \
            (self.name, ctime, username, self.users[username].uid))
      else:
        self.users[username] = IrcParse.User(username, ctime, self.cuid)
        self.cuid += 1
        logging.info("%s: %s - Client joined: %s/%s" % \
            (self.name, ctime, username, self.users[username].uid))

    def quit(self, ctime, username, broadcast):
      if username not in self.users:
        return

      if broadcast and not self.users[username].online:
        return

      logging.info("%s: %s - Client quit: %s/%s" % \
          (self.name, ctime, username, self.users[username].uid))
      self.users[username].quit(ctime)

    def nick(self, oldname, newname):
      """ Handler for the client nick (name change) event """
      if oldname not in self.users:
        return

      logging.info("Nickname change: %s : %s" % (oldname, newname))

      if newname in self.users:
        self.users[newname].merge(self.users[oldname])
        self.merged_uids[self.users[oldname].uid] = self.users[newname].uid
      else:
        self.users[newname] = self.users[oldname]
        self.users[newname].name = newname

      del self.users[oldname]

    def add_msg(self, ctime, username, msg):
      """ Handler for the client message post event """
      if username not in self.users:
        return

      logging.info("%s: %s - %s/%s: %s" % \
          (self.name, ctime, username, self.users[username].uid, msg))
      self.users[username].add_msg(ctime, msg)

    def finished(self):
      self.events = []
      uidx = 0
      for user in self.users.values():
        for idx in range(len(user.online_time)):
          if idx % 2 == 0:
            action = "join"
          else:
            action = "quit"
          self.events.append((user.online_time[idx], action, uidx))

        for msg in user.msgs:
          self.events.append((msg[0], "msg", (uidx, msg[1])))
        uidx += 1

      self.events.sort(key=lambda t: t[0], reverse = False)

    def __str__(self):
      return "%s: users: %s, events: %s" % \
          (self.name, len(self.users), len(self.events))

  def __init__(self, events=[], filename=""):
    if len(filename) > 0:
      f = open(filename, "rb")
      while True:
        try:
          events.append(pickle.load(f))
        except EOFError:
          break
      f.close()

    self.channels = {}

    event_actions = {
        "join" : self.on_join,
        "part" : self.on_part,
        "quit" : self.on_quit,
        "nick" : self.on_nick,
        "msg" : self.on_msg,
        }

    idx = 0
    for event in events:
      # Get the callback
      callback = event_actions.get(event[1], None)
      # Process the data
      try:
        callback and callback(float(event[0]), tuple(event[2:]))
        idx += 1
      except:
        print "%s %s" % (idx, event)
        raise

    for channel in self.channels.values():
      channel.finished();

    if len(self.channels) > 0:
      self.events = self.channels[self.channels.keys()[0]].events
    else:
      self.events = []

  def on_join(self, etime, (channel, name)):
    """ Handler for the client join event """
    channel = channel.lower()
    name = name.lstrip("+@~")
    if channel not in self.channels:
      self.channels[channel] = IrcParse.Channel(channel)
    self.channels[channel].join(etime, name)

  def on_nick(self, etime, (oldname, newname)):
    oldname = oldname.lstrip("+@~")
    newname = newname.lstrip("+@~")
    for channel in self.channels.values():
      channel.nick(oldname, newname)

  def on_quit(self, etime, (name, )):
    """ Handler for the client quit event """
    name = name.lstrip("+@~")
    for channel in self.channels.values():
      channel.quit(etime, name, True)

  def on_part(self, etime, (channel, name)):
    """ Handler for the client to leave a chatroom event """
    channel = channel.lower()
    name = name.lstrip("+@~")
    self.channels[channel].quit(etime, name, False)

  def on_msg(self, etime, (channel, name, msg)):
    """ Handler for the client message post event """
    channel = channel.lower()
    if channel not in self.channels:
      # Private message
      return
    name = name.lstrip("+@~")
    self.channels[channel].add_msg(etime, name, msg)

if __name__ == "__main__":
  main()
