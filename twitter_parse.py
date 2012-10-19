#!/usr/bin/python2

"""Parses a set of Twitter events and converts it into a data set for the
AnonymitySimulator."""

import logging
from datetime import datetime

pre_time = 60.0
post_time = 1200.0

class TwitterParse:
  """ Parses the Twitter log produced by twitter_crawl.py creating
  a list of TwitterParse.User and events that can then be plugged into
  the AnonymitySimulator """
  class User:
    """ Represents a single user's activity """
    def __init__(self, name, uid):
      self.name = name
      self.msgs = []
      self.uid = uid
      self.online = False
      self.online_time = []

    def add_msg(self, etime, msg):
      """ User posted a message """
      last_msg = 0.0
      if len(self.msgs) > 0:
        last_msg = self.msgs[-1][0]

      if self.online:
        if etime - last_msg > (post_time + pre_time):
          self.online_time.append(last_msg + post_time)
          self.online = False

      if not self.online:
        self.online_time.append(max(0.0, etime - pre_time))
        self.online = True

      self.msgs.append((etime, msg))

    def finished(self, etime):
      if not self.online or len(self.msgs) == 0:
        return

      last_msg = self.msgs[-1][0]
      if etime - last_msg > post_time + pre_time:
        self.online_time.append(last_msg + post_time)
        self.online = False

    def __repr__(self): 
      return self.__str__()

    def __str__(self):
      return "%s: %s" % (self.name, len(self.msgs))

  def __init__(self, events):
    userids = events["userids"]
    statuses = events["statuses"]

    self.users = {}
    for uid in userids:
      self.users[uid] = TwitterParse.User(uid, len(self.users))
    self.events = []

    if len(statuses) == 0:
      return

    start_time = self.parse_time(statuses[0].created_at)
    self.events = []

    for status in statuses:
      user_id = status.user.id
      if user_id not in self.users:
        continue
      ctime = (self.parse_time(status.created_at) - start_time).total_seconds()
      self.users[user_id].add_msg(ctime, status.text)
      self.events.append((ctime, "msg", (self.users[user_id].uid, status.text)))

    end_time = (self.parse_time(statuses[-1].created_at) - start_time).total_seconds()
    for user in self.users.values():
      user.finished(end_time)

      online = False
      for time in user.online_time:
        if online:
          self.events.append((time, "quit", user.uid))
        else:
          self.events.append((time, "join", user.uid))

        online = not online

    self.events.sort()

  def parse_time(self, time):
    return datetime.strptime(time, "%a %b %d %H:%M:%S +0000 %Y")
