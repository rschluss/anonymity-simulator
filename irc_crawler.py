#!/usr/bin/python2

"""
Monitors one or more IRC Channels including joins, leaves, messages, and nick
changes as well as a slow way for obtaining hostnames that
does not result in 'peer disconnections' from the server.

Outputs the following data formats:
  (time, "join", channel, username)
  (time, "part", channel, username)
  (time, "msg", channel, username, message)
  (time, "nick", old_username, new_username)
  (time, "quit", username)

  Need to add support for NickServ
  /msg NickServ IDENTIFY "password"
  As a result this action happens:
  Mode change [+r] for user $me
  Check the change in channels every X time
"""

import codecs
import argparse
import irc.client
import logging
import os
import random
import pickle
import signal
import sys
import time
import thread

import sys
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

def main():
  parser = argparse.ArgumentParser(description="Gathers data for use with "
                                               "AnonymitySimulator")

  parser.add_argument("-s", "--server", default="irc.freenode.org",
                      help="IRC server address to connect to (default: "
                           "irc.freenode.net")
  parser.add_argument("-c", "--channels", default=["#ubuntu"], nargs="+",
                      help="IRC channel names to connect to on the server. "
                           "'all' will join all channels on the server "
                           "(default: #ubuntu)")
  parser.add_argument("-p", "--port", type=int, default=6667,
                      help="port on the server to connect to (default: 6667)")
  parser.add_argument("-u", "--username", default="dedis",
                      help="username we'll show up as on the IRC server "
                           "(default: dedis)")
  parser.add_argument("-w", "--password",
                      help="password to give to NickServ for our username")
  parser.add_argument("-o", "--output", default="data",
                      help="file to write to write the IRC events to. should "
                           "be passed to irc_parse.py")
  parser.add_argument("-n", "--info", dest="log_level", action="store_const",
                      const=logging.INFO,
                      help="sets the logging level to 'info'")
  parser.add_argument("-d", "--debug", dest="log_level", action="store_const",
                      const=logging.DEBUG,
                      help="sets the logging level to 'debug'")
  args = parser.parse_args()

  if hasattr(args, "log_level"):
    logging.basicConfig(level=args.log_level)

  ircs = []
  irc = IrcHelper(args.username, args.server, args.port, args.output,
                  args.password)
  if not irc.login():
    return

  if arg.channels == ["all"]:
    to_join = [channel[0] for channel in irc.get_all_channels()]
  else:
    to_join = arg.channels

  print to_join
  to_join.reverse()
  print to_join
  to_join = irc.follow_channels(to_join)
#  irc.run_forever_in_thread()
#  ircs.append(irc)
#
#  idx = 0
#  while 1:
#    username_n = username + str(idx)
#    output_n = output + str(idx)
#    irc = IrcHelper(username_n, server, port, output_n)
#    if not irc.login():
#      return
#    to_join = irc.follow_channels(to_join)
#    irc.run_forever_in_thread()
#    ircs.append(irc)
#    idx += 1

#  time.sleep(10**10)
  irc.run_forever()

def crawl(username, server, port, output, password, channels = None):
  pass

#  for idx in range(10):
#    channels = [channel[0] for channel in irc.channels[idx * 20:idx * 20 + 19]]
#    thread.start_new_thread(follow_channels, (username + str(idx),
#      server, port, channels, output + "/" + str(idx)))

#  time.sleep(10**10)

#  channels = irc.channels
#  irc = IrcHelper(username, server, port, output)
#  irc.follow_channels([channel[0] for channel in channels[0:19]])
#  idx = 0
#  for channel in irc.channels:
#    print "Connecting to " + channel[0]
#    thread.start_new_thread(follow_channels, (username + str(idx),
#      server, port, channel[0], output + "/" + channel[0][1:]))
#    idx += 1
#    if idx == 40:
#      break

def parse_name(long_name):
  """ Parses the nick out of a long nick string """
  names = long_name.split("!")
  if len(names) == 0:
    return None
  return names[0]

class IrcHelper:
  def __init__(self, username, server, port, output, password = None):
    self.username = username
    self.password = password
    self.server = server
    self.port = port
    self.output = output
    self.started = False
    self.loggedin = False
    self.m_error = False

    self.m_client = irc.client.IRC()
    self.m_client.add_global_handler("disconnect", self.on_disconnect)
    self.m_client.add_global_handler("error", self.on_error)
    self.m_client.add_global_handler("other", self.on_error)

  def _run_task(self, task):
    task.run()
    while not task.is_done():
      try:
        self.m_client.process_once(timeout=1.0)
      except KeyboardInterrupt:
        break
      except TypeError:
        if self.m_error:
          return False
        else:
          raise
    return True

  def login(self):
    self.m_con = self.m_client.server().connect(self.server, self.port, self.username)
    login = Login(self.m_con, self.password)
    self._run_task(login)
    return login.successful()

  def get_all_channels(self):
    channels = GetAllChannels(self.m_con)
    self._run_task(channels)
    return channels.channels

  def follow_channels(self, channels):
    follower = FollowChannels(self.m_con, channels, self.output)
    self._run_task(follower)
    return follower.channels

  def run_forever_in_thread(self):
    thread.start_new_thread(self.run_forever, ())

  def run_forever(self):
    while True:
      try:
        self.m_client.process_forever()
      except KeyboardInterrupt:
        break

  # System events
  def on_disconnect(self, connection, event):
    """ Event handler for when the crawler has been disconnected from the
    server """
    logging.info("We are disconnecting: %s %s %s" % (event.source(), event.target(), event.arguments()))

  def on_error(self, connection, event):
    """ Event handler for errors """
    logging.info("Error %s %s %s" % (event.target(), event.source(), event.arguments()))
    self.m_error = True

class FollowChannels:
  def __init__(self, irc, channels, output):
    self.m_irc = irc
    self.channels = channels
    self.output = output
    self.callbacks = {}
    self.m_is_done = False

    self.joining = {}
    self.joined = {}
    self.rejected = {}
    self.total = len(self.channels)

  def is_done(self):
    return self.m_is_done

  def successful(self):
    return True

  def run(self):
    # Overwrite file
    f = open(self.output, "w+")
    f.close()

    # Create the client and add the handlers defined above
    self.m_irc.add_global_handler("join", self.on_join)
    self.m_irc.add_global_handler("quit", self.on_quit)
    self.m_irc.add_global_handler("part", self.on_part)
    self.m_irc.add_global_handler("pubmsg", self.on_msg)
    self.m_irc.add_global_handler("pubnotice", self.on_msg)
    self.m_irc.add_global_handler("privmsg", self.on_msg)
    self.m_irc.add_global_handler("privnotice", self.on_msg)
    self.m_irc.add_global_handler("namreply", self.on_names)
    self.m_irc.add_global_handler("endofnames", self.on_names_end)
    self.m_irc.add_global_handler("nick", self.on_nick)
    self.m_irc.add_global_handler("topic", self.on_topic)

    self.m_irc.add_global_handler("nochanmodes", self.on_channel_rejected)
    self.m_irc.add_global_handler("needmoreparams", self.on_channel_rejected)
    self.m_irc.add_global_handler("inviteonlychan", self.on_channel_rejected)
    self.m_irc.add_global_handler("channelisfull", self.on_channel_rejected)
    self.m_irc.add_global_handler("nosuchchannel", self.on_channel_rejected)
    self.m_irc.add_global_handler("bannedfromchan", self.on_channel_rejected)
    self.m_irc.add_global_handler("badchannelkey", self.on_channel_rejected)
    self.m_irc.add_global_handler("badchanmask", self.on_channel_rejected)
    self.m_irc.add_global_handler("toomanychannels", self.on_joining_done)

    self.base_time = time.time()
    self.connect_to_next_channel(self.m_irc)

  def finished(self):
    self.m_irc.remove_global_handler("disconnect", self.on_disconnect)
    self.m_irc.remove_global_handler("error", self.on_error)
    self.m_irc.remove_global_handler("other", self.on_error)
    self.m_irc.remove_global_handler("join", self.on_join)
    self.m_irc.remove_global_handler("quit", self.on_quit)
    self.m_irc.remove_global_handler("part", self.on_part)
    self.m_irc.remove_global_handler("pubmsg", self.on_msg)
    self.m_irc.remove_global_handler("pubnotice", self.on_msg)
    self.m_irc.remove_global_handler("privmsg", self.on_msg)
    self.m_irc.remove_global_handler("privnotice", self.on_msg)
    self.m_irc.remove_global_handler("namreply", self.on_names)
    self.m_irc.remove_global_handler("endofnames", self.on_names_end)
    self.m_irc.remove_global_handler("nick", self.on_nick)
    self.m_irc.remove_global_handler("topic", self.on_topic)

    self.m_irc.remove_global_handler("nochanmodes", self.on_channel_rejected)
    self.m_irc.remove_global_handler("needmoreparams", self.on_channel_rejected)
    self.m_irc.remove_global_handler("inviteonlychan", self.on_channel_rejected)
    self.m_irc.remove_global_handler("channelisfull", self.on_channel_rejected)
    self.m_irc.remove_global_handler("nosuchchannel", self.on_channel_rejected)
    self.m_irc.remove_global_handler("bannedfromchan", self.on_channel_rejected)
    self.m_irc.remove_global_handler("badchannelkey", self.on_channel_rejected)
    self.m_irc.remove_global_handler("badchanmask", self.on_channel_rejected)
    self.m_irc.remove_global_handler("toomanychannels", self.on_joining_done)

  # Helper functions

  def write_output(self, msg):
    f = open(self.output, "a")
    f.write(msg)
    f.close()

  def get_ctime(self):
    """ Returns the time since beginning """
    return time.time() - self.base_time

  def delayed_connect(self, connection, channel):
    logging.info("Joining: %s, %s / %s remaining." %
        (channel, len(self.channels), self.total))
    self.joining[channel] = True
    self.current_channel = channel
    connection.join(channel)

    callback = SelfContainedCallback(self._timedout)
    self.callbacks[channel] = callback
    self.m_irc.execute_delayed(1, callback.run)
  
  def connect_to_next_channel(self, connection):
    if len(self.channels):
      channel = self.channels.pop()
      connection.execute_delayed(1, self.delayed_connect, (connection, channel))
    else:
      logging.info("Done joining")
      self.m_is_done = True

  def _timedout(self):
    """ We got here because we neither got rejected from a channel nor got the names..."""
    self.m_irc.names([self.current_channel])

  # Event handlers

  # Channel events
  def on_join(self, connection, event):
    """ Event handler for when a user joins a channel """
    channel = event.target()
    name = parse_name(event.source())
    if name == None:
      return
    self.write_output(pickle.dumps((self.get_ctime(), "join", channel, name)))

  def on_part(self, connection, event):
    """ Event handler for when a user quits a channel or leaves the server """
    name = parse_name(event.source())
    channel = event.target()
    if name == None:
      return
    self.write_output(pickle.dumps((self.get_ctime(), "part", channel, name)))

  def on_names(self, connection, event):
    """ Event handler for querying all the names of users currently with in a
    channel """
    self._running = True
    data = event.arguments()
    if len(data) < 3:
      return

    channel = data[1]
    if channel in self.callbacks:
      self.callbacks[channel].stop()
      del self.callbacks[channel]

    names = data[2]
    for name in names.split(" "):
      self.write_output(pickle.dumps((0, "join", channel, name)))

  def on_names_end(self, connection, event):
    if len(event.arguments()) != 2:
      return
    channel = event.arguments()[0]

    if channel in self.callbacks:
      self.callbacks[channel].stop()
      del self.callbacks[channel]

    if channel in self.joining:
      del self.joining[channel]
      self.joined[channel] = True

    logging.info("Successfully joined: " + channel)
    self.connect_to_next_channel(connection)

  def on_channel_rejected(self, connection, event):
    if len(event.arguments()) != 2:
      return
    channel = event.arguments()[0]
    reason = event.arguments()[1]

    if channel in self.callbacks:
      self.callbacks[channel].stop()
      del self.callbacks[channel]

    if channel in self.joining:
      del self.joining[channel]
      self.rejected[channel] = True

    self.write_output(pickle.dumps((self.get_ctime(), "not_join", channel, reason)))
    logging.info("Rejected from %s, because '%s'" % (channel, reason))
    self.connect_to_next_channel(connection)

  def on_joining_done(self, connection, event):
    if len(event.arguments()) != 2:
      return
    channel = event.arguments()[0]
    reason = event.arguments()[1]

    if channel in self.callbacks:
      self.callbacks[channel].stop()
      del self.callbacks[channel]

    logging.info("Unable to join %s, because '%s'" % (channel, reason))
    self.channels.append(channel)
    self.m_is_done = True

  def on_topic(self, connection, event):
    """ Event handler for topic changes """
    name = parse_name(event.source())
    channel = event.target()
    if name == None:
      return

    if len(event.arguments()) == 0:
      return

    msg = event.arguments()[0]
    self.write_output(pickle.dumps((self.get_ctime(), "topic", channel, name, msg)))

  def on_msg(self, connection, event):
    """ Event handler for incoming messages """
    name = parse_name(event.source())
    channel = event.target()
    if name == None:
      return

    if len(event.arguments()) == 0:
      return

    msg = event.arguments()[0]
    self.write_output(pickle.dumps((self.get_ctime(), "msg", channel, name, msg)))

  # Global events
  def on_nick(self, connection, event):
    """ Event handler for when a user changes their nick """
    oldname = parse_name(event.source())
    if oldname == None:
      return
    self.write_output(pickle.dumps((self.get_ctime(), "nick", oldname, event.target())))

  def on_quit(self, connection, event):
    """ Event handler for when a user quits a channel or leaves the server """
    name = parse_name(event.source())
    if name == None:
      return
    self.write_output(pickle.dumps((self.get_ctime(), "quit", name)))

class GetAllChannels:
  def __init__(self, irc):
    self.m_irc = irc
    self.m_success = False
    self.m_is_done = False
    self.channels = []

  def is_done(self):
    return self.m_is_done

  def successful(self):
    return self.m_success

  def run(self):
    self.m_irc.add_global_handler("list", self.on_channel_list)
    self.m_irc.add_global_handler("listend", self.on_channel_list_end)
    self.m_irc.list()

  def finish(self, success):
    self.m_irc.remove_global_handler("list", self.on_channel_list)
    self.m_irc.remove_global_handler("listend", self.on_channel_list_end)
    self.m_success = success
    self.m_is_done = True

  def on_channel_list(self, connection, event):
    if len(event.arguments()) != 3:
      return
    channel = event.arguments()[0]
    size = event.arguments()[1]
    self.channels.append((channel, int(size)))

  def on_channel_list_end(self, connection, event):
    if len(self.channels) == 0:
      logging.info("No channels")
    else:
      self.channels.sort(key=lambda e: e[1], reverse = True)
      avg = (reduce(lambda x, y: x + y[1], self.channels, 0) * 1.0) \
          / (len(self.channels) * 1.0)

      logging.info("Channels: %s %s" % (len(self.channels), avg))
    self.finish(len(self.channels) != 0)

class Login:
  def __init__(self, irc, password = None):
    self.m_found = False
    self.m_is_done = False
    self.m_irc = irc
    self.m_password = password
    self.m_ran = False
    self.m_success = False

  def is_done(self):
    return self.m_is_done

  def successful(self):
    return self.m_success

  def run(self):
    self.m_irc.add_global_handler("nicknameinuse", self.on_nicknameinuse)
    self.m_irc.add_global_handler("privnotice", self.on_notice)
    self.m_irc.add_global_handler("whoisuser", self.on_whois)
    self.m_irc.add_global_handler("endofwhois", self.on_whois_end)
    self.m_irc.add_global_handler("welcome", self.on_connect)

  def finished(self, success):
    self.m_irc.remove_global_handler("nicknameinuse", self.on_nicknameinuse)
    self.m_irc.remove_global_handler("privnotice", self.on_notice)
    self.m_irc.remove_global_handler("whoisuser", self.on_whois)
    self.m_irc.remove_global_handler("endofwhois", self.on_whois_end)
    self.m_irc.remove_global_handler("welcome", self.on_connect)

    self.m_success = success
    self.m_is_done = True

  def _run(self):
    if self.m_ran:
      return
    self.m_ran = True

    self.m_responded = False
    self.m_irc.whois(["NickServ"])
    self.m_irc.execute_delayed(2, self._timedout)

  def _login(self):
    self.m_responded = False
    self.m_irc.privmsg("NickServ", "IDENTIFY " + self.m_password)
    self.m_irc.execute_delayed(2, self._timedout)

  def _timedout(self):
    if self.is_done():
      return

    if self.m_responded:
      return

    self.m_ran = False
    self._run()

  def on_nicknameinuse(self, connection, event):
    logging.critical("Nickname in use")
    self.finished(False)

  def on_connect(self, connection, event):
    self._run()

  def on_notice(self, connection, event):
    sender = parse_name(event.source())
    msg = event.arguments()[0]

    if sender == "NickServ":
      self.m_responded = True
      if msg.startswith("You are now identified"):
        self.finished(True)
      elif msg.startswith("Invalid password") or \
          msg.startswith("Inusfficient parameters"):
        logging.critical("Invalid password")
        self.finished(False)

  def on_whois(self, connection, event):
    if not self.m_responded:
      self.m_responded = True

    response = event.arguments()
    if len(response) == 0:
      return

    if response[0] == "NickServ" and self.m_password != None:
      self.m_found = True
      self._login()

  def on_whois_end(self, connection, event):
    if not self.m_responded:
      self.m_responded = True

    if self.m_password == None:
      self.finished(True)
    elif not self.m_found:
      logging.critical("Unable to find NickServ")
      self.finished(False)

class SelfContainedCallback:
  def __init__(self, callback):
    self.callback = callback
    self.m_stop = False

  def run(self):
    if not self.m_stop:
      self.callback()

  def stop(self):
    self.m_stop = True

if __name__ == "__main__":
  main()
