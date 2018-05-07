#!/usr/bin/env python

import json
import locale
import logging
import logging.handlers
import os
import re
import requests
import sys
import urllib2

locale.setlocale(locale.LC_ALL, 'en_US.utf8')
app_dir = os.path.dirname(os.path.realpath(sys.argv[0]))

# Logging
log_format = logging.Formatter('%(asctime)s: %(message)s')
log_file = logging.handlers.RotatingFileHandler(app_dir + '/check-price.log', maxBytes=100000, backupCount=5)
log_file.setFormatter(log_format)
log = logging.getLogger('check-price')
log.setLevel(logging.DEBUG)
log.addHandler(log_file)

url = 'https://www.homedepot.com/p/Rheem-Performance-Platinum-65-gal-10-Year-Hybrid-High-Efficiency-Smart-Tank-Electric-Water-Heater-XE65T10HD50U1/303419586'

class Config:
    def __init__(self):
        self.config = {} 
        config_file = app_dir + '/config.json'
        if os.path.isfile(config_file):
            self.config = json.loads(open(config_file).read())

    def get(self, key):
        return self.config[key]

class ProductList:
    def __init__(self):
        self.sites = [] 
        list_file = app_dir + '/product-list.json'
        if os.path.isfile(list_file):
            product_list = json.loads(open(list_file).read())
            if "sites" in product_list:
                self.sites = product_list["sites"]

class SavedState:
    def __init__(self):
       self.cache_file = app_dir + '/state.json'
       self.state = {}
       if os.path.isfile(self.cache_file):
           log.debug("Loading state data from cache")
           self.state = json.loads(open(self.cache_file).read())
                
    def save(self):
        with open(self.cache_file, 'w') as fp:
            json.dump(self.state, fp)
            
    def get(self, name):
        if name in self.state:
            return self.state[name]
        return None

    def set(self, name, state):
        self.state[name] = state

class Slack:
    def __init__(self, config):
        self.config = config

    def send(self, msg):
        try:
            log.debug('Sending message: ' + msg)
            data = 'payload={{"username": "{0}", "text": "{1}"}}'.format(config.get('slack.user'), msg)
            r = urllib2.Request(config.get('slack.url'))
            urllib2.urlopen(r, data)
            log.debug('Message sent ')
        except Exception as e:
            log.exception("Error sending message.")

config = Config()
state = SavedState()
product_list = ProductList()
for site in product_list.sites:
    headers = {}
    if "user-agent" in site:
        headers["User-Agent"] = site["user-agent"]

    for product in site["products"]:
        log.debug("Checking product {0}".format(product["name"]))
        r = requests.get(product["url"], headers=headers, stream=True)
        for line in r.iter_lines():
            match = re.search(site["regex"], line)
            if match:
                old_price = state.get("price")
                if old_price is not None:
                    log.info("Old price is {0}".format(locale.currency(old_price, grouping=True)))
        
                try:
                    price = float(match.group(1))
                except ValueError:
                    price = None
        
                if price is None:
                    log.info("Cound not find price")
                else:
                    log.info("Price: " + locale.currency(price, grouping=True))
                    state.set("price", price)
        
                    if old_price is not None and price != old_price:
                        log.info("Price has changed")
                        slack = Slack(config)
                        slack.send("Price has changed from {0} to {1}".format(locale.currency(old_price, grouping=True), locale.currency(price, grouping=True)))

state.save()