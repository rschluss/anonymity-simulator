#!/usr/bin/python2

"""
Common class for evaluating anonymity over a data set
Event structure:
  (time, "join", uid)
  (time, "quit", uid)
  (time, "msg", (uid, msg))
"""

import argparse
import math
import pickle

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
  parser.add_argument("--sort", default="online_time",
      help="sort analysis output: uid, online_time, interval, messages")
  parser.add_argument("-o", "--output", default="data.out",
      help="output dataset")
  parser.add_argument("-p", "--percent", default=0, type=float,
      help="Filter percent bounds (default: 0)")
  parser.add_argument("-b", "--bound", default=0, type=int,
      help="Filter fixed bounds (default: 0)")
  parser.add_argument("-s", "--start", default=0, type=float,
      help="Filter starting time (default: 0)")
  parser.add_argument("-e", "--end", default=-1, type=float,
      help="Filter end time (default: end)")
  parser.add_argument("-n", "--interval", default=86400, type=int,
      help="Filter time interval in seconds (default:86400 -- 1 day)")
  parser.add_argument("-f", "--filter", default=None,
      help="Filter type: interval, time_range, online_time")
  args = parser.parse_args()

  msg_parser = DefaultParse(filename=args.input)
  data_analyzer = DataAnalyzer(msg_parser.events, args.interval, args.end)

  if args.filter == None:
    clients = list(data_analyzer.clients.values())
    if args.sort == "uid":
      clients.sort(key=lambda client: client.uid)
    elif args.sort == "interval":
      clients.sort(key=lambda client: client.intervals)
    elif args.sort == "online_time":
      clients.sort(key=lambda client: client.online_time)
    elif args.sort == "messages":
      clients.sort(key=lambda client: len(client.msg_times))
    for client in clients:
      print client
    return

  to_remove = []
  if args.filter == "interval":
    intervals = math.ceil(msg_parser.events[-1][0] / args.interval)
    if args.percent != 0:
      desired_intervals = math.floor(intervals * args.percent)
    else:
      desired_intervals = args.bound
    print "Have %s intervals, removing clients with less than %s intervals" % \
        (intervals, desired_intervals)
    for client in data_analyzer.clients.values():
      if client.intervals < desired_intervals:
        to_remove.append(client.uid)
  elif args.filter == "time_range":
    for client in data_analyzer.clients.values():
      found = False
      for online_times in client.online_times:
        if online_times[0] <= args.start:
          found = True
          break
      if found:
        break
      to_remove.append(client.uid)
  elif args.filter == "online_time":
    percent = args.percent * msg_parser.events[-1][0]
    for client in data_analyzer.clients.values():
      if client.online_time < perent:
        to_remove.append(client.uid)

  print "Filtering will remove %s clients" % (len(to_remove))
  data_filter = DataFilter(msg_parser.events, len(msg_parser.users), to_remove)
  if args.start != 0 or args.end != 0:
    pass
#    data_filter.set_range(args.start, args.end)
  output = file(args.output, "w+")
  for event in data_filter.filtered_events:
    output.write(pickle.dumps(event))
  output.close()

class DataAnalyzer:
  """ Processes a data set to calculate both the clients' and their
  respective message pseudonyms' anonymity over time. """
  class Client:
    """ Represents a single client """
    def __init__(self, uid):
      self.uid = uid
      self.msg_times = []
      self.online_times = []
      self.online_time = 0
      self.intervals = 0

    def set_online(self, ctime):
      """ Set the client as online """
      self.online_times.append((ctime, 0))

    def set_offline(self, ctime):
      """ Set the client as offline """
      self.online_times[-1] = (self.online_times[-1][0], ctime)
      self.online_time += ctime - self.online_times[-1][0]

    def finished(self, ctime):
      """ Sets a final offline if necessary """
      if self.online_times[-1][1] == 0:
        self.set_offline(ctime)

    def set_msg(self, ctime):
      self.msg_times.append(ctime)

    def __repr__(self):
      return self.__str__()

    def __str__(self):
      return "uid: %s, online time: %s, intervals: %s, msgs: %s" % \
          (self.uid, self.online_time, self.intervals, len(self.msg_times))

  def __init__(self, events, interval, end):
    self.event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "msg" : self.on_msg,
        }

    self.clients = {}

    if end == -1:
      self.end = events[-1][0] + 1
    else:
      self.end = end

    self.process_events(events)

    if interval > 0:
      for client in self.clients.values():
        ctime = 0
        ntime = interval
        for online_times in client.online_times:
          while ntime < online_times[0]:
            ctime = ntime
            ntime += interval
          while online_times[0] <= ntime and ctime < online_times[1]:
            client.intervals += 1
            ctime = ntime
            ntime += interval

  def process_events(self, events):
    for event in events:
      if self.end < event[0]:
        break

      callback = self.event_actions.get(event[1], None)
      try:
        result = callback and callback(event[0], event[2])
      except:
        print event
        raise

    for client in self.clients.values():
      client.finished(self.end)

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    if uid not in self.clients:
      self.clients[uid] = DataAnalyzer.Client(uid)
    self.clients[uid].set_online(etime)

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    self.clients[uid].set_offline(etime)

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """
    assert(self.clients[uid].online_times[-1][1] == 0)
    self.clients[uid].set_msg(etime)

class DataFilter:
  """ Filters undesirable features from a data set. """
  def __init__(self, events, total, to_remove):
    if to_remove == []:
      self.filtered_events = events
      return

    self.event_actions = {
        "join" : self.on_join,
        "quit" : self.on_quit,
        "msg" : self.on_msg,
        }

    to_remove.sort()
    self.uid_map = []
    cidx = 0
    for idx in range(total):
      if idx in to_remove:
        self.uid_map.append(-1)
      else:
        self.uid_map.append(cidx)
        cidx += 1

    self.filtered_events = []
    self.process_events(events)

  def process_events(self, events):
    for event in events:
      callback = self.event_actions.get(event[1], None)
      try:
        result = callback and callback(event[0], event[2])
      except:
        print event
        raise

  def on_join(self, etime, uid):
    """ Handler for the client join event """
    nuid = self.uid_map[uid]
    if nuid == -1:
      return

    self.filtered_events.append((etime, "join", nuid))

  def on_quit(self, etime, uid):
    """ Handler for the client quit event """
    nuid = self.uid_map[uid]
    if nuid == -1:
      return

    self.filtered_events.append((etime, "quit", nuid))

  def on_msg(self, etime, (uid, msg)):
    """ Handler for the client message post event """
    nuid = self.uid_map[uid]
    if nuid == -1:
      return

    self.filtered_events.append((etime, "msg", (nuid, msg)))

if __name__ == "__main__":
  main()
