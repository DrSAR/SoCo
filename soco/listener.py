#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=W0511

""" The events module contains the Events class for the implementation of
the listening feature. A user-provided handler can be called upon callbacks
from the Sonos Zones
"""

from __future__ import print_function
import sys
import socket
import string
import requests
import circuits # using Component, Debugger
import circuits.web # using Server, Controller
import HTMLParser
import xml.etree.ElementTree as ET
import soco

def _get_local_ip():
    """ Determine local IP in a platform independent way """
    # Not a fan of this, but there isn't a good cross-platform way of
    # determining the local IP.
    # From http://stackoverflow.com/a/7335145
    # pylint: disable=C0103
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 9))
        ip = s.getsockname()[0]  # pylint: disable=C0103
    except socket.error:
        raise
    finally:
        del s
    return ip

class Root(circuits.web.Controller):
    def index(self, *args, **kwargs):
        # retrieve XML from request body sent by zoneplayer
        outer = ET.fromstring(self.request.body.read())
        # TODO: check whether LastChange elements in the XML are really the only
        # thing we could be conceivably interested in
        eventxml_string = outer.findall('.//LastChange')[0].text
        event_tree = ET.fromstring(eventxml_string)
        event_attributes = {}
        # TODO iterate through all InstanceID elements
        # currently this will only look through the first InstanceID (which happens
        # to be a child of 'Event' which happens to be a child of 'LastChange')
        for el in event_tree.getchildren()[0].getchildren():
            localtag = string.split(el.tag[1:], "}", 1)[1]
            event_attributes[localtag] = el.attrib['val']
        self.fire(Notification(event_attributes))
        # if we do not want to get unsubscribed, we send '200 OK'
        return "200 OK"

class Notification(circuits.Event):
    '''used to signal the arrival of UPnP event'''

class CustomHandling(circuits.Component):
    def Notification(self, event_dic):
        print(event_dic)

class App(circuits.Component):
    """An App for creation and subscription to Sonos notifications

    Public functions:
    started -- event fires upon initial running of App (i.e. this
               is where we send the SUBSCRIBE verb to zoneplayer)
    """

    AVTRANSPORT_ENDPOINT = 'http://{0}:1400/MediaRenderer/AVTransport/Event'

    def __init__(self, speaker_ip, host="", port=8080):
        """TODO: check for busy port and choose another one if needed
        """
        super(App, self).__init__()  # Important to properly initialize the Component

        self.speaker_ip = speaker_ip
        self.host = host
        self.port = port
        self.server = None
        self.listeners = set()

    def started(self, manager):
        """ start the server and listen to messages from zoneplayers

        TODO: check if port available and switch to other port if needed
        """

        ip = _get_local_ip()  # pylint: disable=C0103
        headers = {
            'Callback': '<http://{0}:{1}>'.format(ip, self.port),
            'NT': 'upnp:event'
        }
        endpoint = self.AVTRANSPORT_ENDPOINT.format(self.speaker_ip)
        # `SUBSCRIBE` is a custom HTTP/1.1 verb used by Sonos devices.
        # pylint: disable=C0103
        r = requests.request('SUBSCRIBE', endpoint, headers=headers)
        # Raise an exception if we get back a non-200 from the zoneplayer/speaker.
        r.raise_for_status()

        self.server = (circuits.web.Server((ip, self.port)) + Root() +
                       CustomHandling()).register(self)

def main(ip = None):
    app = App(ip)
    circuits.Debugger(events=False).register(app)
    app.run()


if __name__ == "__main__":
    # find the rooms
    ips = soco.SonosDiscovery().get_speaker_ips()
    zone_names = {}
    for ip in ips:
        x = soco.SoCo(ip)
        zone_names[ip] = x.get_speaker_info()['zone_name']

    # identify the room to listen to
    if len(sys.argv) < 2:
        print('specify which zone to listen to')
        for k, v in zone_names.iteritems():
            print(k, v)
    else:
        print(str(sys.argv))
        main(ip = sys.argv[1])
