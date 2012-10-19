#!/usr/bin/python2

"""Monitors a single IRC Channel for all traffic including joins, leaves,
messages, and nick changes as well as a slow way for obtaining hostnames that
does not result in 'peer disconnections' from the server."""

import codecs
import getopt
import irc.client
import logging
import pickle
import signal
import sys
import time

import sys
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

optlist, args = getopt.getopt(sys.argv[1:], "", ["server=", "channel=", "port=", "username=", "output=", "debug"])
optdict = {}
for k,v in optlist:
  optdict[k] = v

channel = optdict.get("--channel", "#ubuntu")
server = optdict.get("--server", "irc.freenode.org")
port = int(optdict.get("--port", 6667))
username = optdict.get("--username", "dedis")
output = optdict.get("--output", "data")
if "--debug" in optdict:
  logging.basicConfig(level=logging.INFO)

events = []
base_time = time.time()
have_who = {}

# Helper functions

def get_ctime():
  """ Returns the time since beginning """
  return time.time() - base_time

def parse_name(long_name):
  """ Parses the nick out of a long nick string """
  names = long_name.split("!")
  if len(names) == 0:
    return None
  return names[0]

def on_join(connection, event):
  """ Event handler for when a user joins a channel """
  name = parse_name(event.source())
  if name == None:
    return
  logging.info("Client joined: %s" % (name, ))
  events.append((get_ctime(), "join", name))
  connection.who(name)

def on_nick(connection, event):
  """ Event handler for when a user changes their nick """
  oldname = parse_name(event.source())
  if oldname == None:
    return
  logging.info("Nickname change: %s : %s" % (oldname, event.target()))
  events.append((get_ctime(), "nick", (oldname, event.target())))

def on_quit(connection, event):
  """ Event handler for when a user quits a channel or leaves the server """
  name = parse_name(event.source())
  if name == None:
    return
  logging.info("Client quit: %s" % (name, ))
  events.append((get_ctime(), "quit", name))
  if name not in have_who:
    connection.whowas(name, "1")

def on_names(connection, event):
  """ Event handler for querying all the names of users currently with in a
  channel """
  data = event.arguments()
  if len(data) < 3:
    return

  names = data[2]
  for name in names.split(" "):
    logging.info("Client online: %s" % (name, ))
    events.append((0, "join", name))

def on_connect(connection, event):
  """ Event handler for when the crawler has connected to the server """
  logging.info("We connected ... joining room")
  connection.join(channel)
  connection.names(channels=[channel])

def on_disconnect(connection, event):
  """ Event handler for when the crawler has been disconnected from the
  server """
  logging.info("We are disconnecting: %s %s %s" % (event.source(), event.target(), event.arguments()))

def on_error(connection, event):
  """ Event handler for errors """
  logging.info("Error %s %s %s" % (event.target(), event.source(), event.arguments(), ))

def on_msg(connection, event):
  """ Event handler for incoming messages """
  name = parse_name(event.source())
  if name == None:
    return

  if len(event.arguments()) == 0:
    return

  msg = event.arguments()[0]
  logging.info("%s: %s" % (name, msg))
  events.append((get_ctime(), "msg", (name, msg)))
  if name not in have_who:
    connection.who(name)

def on_whois(connection, event):
  """ Event handler for whois, who, whowas calls """
  if len(event.arguments()) < 3:
    return
  name = event.arguments()[1]
  host = event.arguments()[2]
  events.append((get_ctime(), "whois", (name, host)))
  have_who[name] = True
  logging.info("Whois: %s : %s" % (name, host))

# Create the client and add the handlers defined above
client = irc.client.IRC()
con = client.server().connect(server, port, username)
con.add_global_handler("welcome", on_connect)
con.add_global_handler("disconnect", on_disconnect)
con.add_global_handler("error", on_error)
con.add_global_handler("other", on_error)
con.add_global_handler("join", on_join)
con.add_global_handler("quit", on_quit)
con.add_global_handler("part", on_quit)
con.add_global_handler("pubmsg", on_msg)
con.add_global_handler("pubnotice", on_msg)
con.add_global_handler("topic", on_msg)
con.add_global_handler("namreply", on_names)
con.add_global_handler("nick", on_nick)
con.add_global_handler("whowasuser", on_whois)
con.add_global_handler("whoreply", on_whois)

# Use ctrl-c / sigint to exit and save data to disk
def signal_handler(signal, frame):
  f = open(output, "wb+")
  pickle.dump(events, f)
  f.close()
  sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Run forever...
client.process_forever()
