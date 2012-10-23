#!/usr/bin/python2

""" Monitors a random Twitter user and 4,999 of their followers."""

import getopt
import logging
import oauth2
import pickle
import select
import signal
import sys
import time
import twitter
import urllib
import urllib2

import socket
socket._fileobject.default_bufsize = 0

optlist, args = getopt.getopt(sys.argv[1:], "", ["consumer_key=", \
    "consumer_secret=", "access_token_key=", "access_token_secret=", \
    "min_followers=", "output=", "debug"])
optdict = {}
for k,v in optlist:
  optdict[k] = v

consumer_key = optdict["--consumer_key"]
consumer_secret = optdict["--consumer_secret"]
access_token_key = optdict["--access_token_key"]
access_token_secret = optdict["--access_token_secret"]
output = optdict.get("--output", "data")
min_followers = int(optdict.get("--min_followers", 1000000))
stop = False

if "--debug" in optdict:
  logging.basicConfig(level=logging.INFO)

class StreamingApi(twitter.Api):
  """ This extends the original Python Twitter API with some streaming functionality """

  stream_url = "https://stream.twitter.com/1.1"

  def _GenerateOAuth(self, url, parameters, body):
    """ Creates an OAuth request, the original version was faulty """
    DEFAULT_POST_CONTENT_TYPE = 'application/x-www-form-urlencoded'
    headers ={}

    if body:
      method = "POST"
      headers['Content-Type'] = DEFAULT_POST_CONTENT_TYPE
      is_form_encoded = True
      parameters = body
      body = urllib.urlencode(body)
    else:
      method = "GET"
      is_form_encoded = False
      body = ''

    req = oauth2.Request.from_consumer_and_token(self._oauth_consumer,
        token = self._oauth_token, http_method = method, http_url = url,
        parameters = parameters, body = body,
        is_form_encoded = is_form_encoded)

    req.sign_request(self._signature_method_hmac_sha1,
        self._oauth_consumer, self._oauth_token)

    return req

  def _FollowStream(self, url, parameters = None, post_data = None,
      callback = None, count = -1, attempt = 0):
    """ Follows a Twitter (HTTP) Stream """
    req = self._GenerateOAuth(url, parameters, post_data)

    self._debugHTTP = 0
    opener = urllib2.OpenerDirector()
    opener.add_handler(urllib2.HTTPHandler(debuglevel=self._debugHTTP))
    opener.add_handler(urllib2.HTTPSHandler(debuglevel=self._debugHTTP))

    if post_data:
      response = opener.open(url, req.to_postdata())
    else:
      response =  opener.open(req.to_url())

    if response.info().gettype() != "application/json":
      logging.info("Error: %s" % response.read())
      if attempt == 5:
        return False
      return self._FollowStream(url, parameters, post_data,
          callback, count, attempt + 1)

    itr = 0
    bad_count = 0
    while itr != count and not stop:
      try:
        (rlist, [], xlist) = select.select([response], [], [response], 0.1)
      except:
        rlist = []
        xlist = []

      if len(rlist) == 0 and len(xlist) == 0:
        continue
      if len(xlist) > 0:
        break

      result = response.readline()
      if len(result) == 0:
        bad_count += 1
        if bad_count > 5:
          break
        continue

      bad_count = 0
      itr += 1
      if not callback(result):
        return True
      logging.info("Count: %s Max: %s" % (itr, count))

    return True

  def StreamPublicTimeline(self, callback = None):
    """ Follows the Public Timeline """
    url  = '%s/statuses/sample.json' % self.stream_url
    return self._FollowStream(url, callback = callback)

  def StreamUsers(self, userids, callback = None, count = -1):
    """ Follows a specific set of users """
    url = '%s/statuses/filter.json' % self.stream_url
    post_data = {'follow' : ','.join([str(userid) for userid in userids])}
    return self._FollowStream(url, post_data=post_data,
        callback = callback, count = count)

selected = None

def find_popular_id(response):
  """ Callback for finding a popular user """
  data = api._ParseAndCheckTwitter(response)
  status = twitter.Status.NewFromJsonDict(data)
  try:
    if status.user.followers_count > min_followers:
      logging.info("Found %s with %s followers." % \
          (status.user, status.user.followers_count))
      global selected
      selected = status.user
      return False
  except:
    pass

  return True

def store_status(response):
  """ Callback for storing statuses """
  try:
    data = api._ParseAndCheckTwitter(response)
    status = twitter.Status.NewFromJsonDict(data)
    if status.user.id in userids:
      f = open(output, "ab")
      pickle.dump(status, f)
      f.close()
  except:
    logging.info("Error response: %s" % (response, ))
  return True

api = StreamingApi(consumer_key=consumer_key, \
    consumer_secret = consumer_secret, \
    access_token_key = access_token_key, \
    access_token_secret = access_token_secret)

api.StreamPublicTimeline(callback = find_popular_id)
users = api.GetFollowerIDs(selected.id)
userids = users['ids']
userids.append(selected.id)

if len(userids) > 5000:
  userids = userids[1:]

logging.info("Following %s users" % (len(userids), ))

f = open(output, "wb+")
pickle.dump(userids, f)
f.close()

# Use ctrl-c / sigint to exit and save data to disk
def signal_handler(signal, frame):
  global stop
  stop = True

signal.signal(signal.SIGINT, signal_handler)

try:
  api.StreamUsers(userids, store_status)
except KeyboardInterrupt:
  pass
