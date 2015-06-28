#!/usr/bin/env python
"""simple_log_consumer.py [options] LOGFILE

A simple console program that monitors HTTP traffic on your machine by
consuming an actively written-to w3c-formatted HTTP access log."""


import re
import operator
import time
import pytz
import sys
import curses
import json
import math
import logging as log
from dateutil import parser
from optparse import OptionParser
from datetime import datetime, timedelta


class SimpleHTTPMonitor:
    # REGEX Patterns
    common = r'(\S+) (\S+) (\S+) \[(.*)\] \"(.*)\" (\d+) (\d+)'
    vhosts = r'(^\S+) {} \"(\S+)\" \"(.*)\"'.format(common)
    extended = r'^{} \"(\S+)\" \"(.*)\"'.format(common)

    # REGEX Pattern Items
    common_labels = ['remotehost', 'rfc931', 'authuser', 'date_utc',
                     'request', 'status', 'bytes']
    vhosts_labels = ['host'] + common_labels + ['referer', 'useragent']
    extended_labels = common_labels + ['referer', 'useragent']

    logfile_type = [(common, common_labels), (vhosts, vhosts_labels),
                    (extended, extended_labels)]

    # Others constants
    TWOMINS = timedelta(minutes=2)
    DOWN = 1
    UP = -1
    KEY_B = ord('b')
    KEY_V = ord('v')
    ESC_KEY = 27

    def __init__(self, options, logfile):
        # Setup Curses Screen
        self.stdscr = curses.initscr()
        self.stdscr.keypad(1)
        self.stdscr.nodelay(1)
        curses.noecho()
        curses.cbreak()

        # Parse Command Line Options
        self.options = options
        self.logfile = logfile
        self.cache_flag = self.options.cache_flag
        log.basicConfig(format='%(asctime)s %(message)s',
                        filename=self.options.logging_filename)

        # Alert Screen Variables
        self.topLineNum = 0

        # Configs
        self.alert_threshold = self.options.threshold
        self.regex, self.log_labels = self.logfile_type[
            self.options.format - 1]

        # Flags
        self.init_flag = True
        self.two_min_traffic_flag = False

        # Statistics
        self.stats = {'master_index': 0,
                      'updated_utc': 0,
                      'average_hits_hour': 0,
                      'peak_hits_hour': 0,
                      'sections': {},
                      'top_5_sections': {},
                      'remotehost_visits': {},
                      'remotehost_data': {},
                      'top_5_remotehost_visits': {},
                      'top_5_remotehost_consumers': {},
                      '2_min_traffic': [],
                      'alert_messages': []}

        self.run()

    def run(self):
        """Handles the main loop of the SimpleHTTPMonitor class."""

        while 1:
            if self.cache_flag:
                # Check for cached json file
                cached_stats = self.check_for_cache()
                if cached_stats != -1:
                    self.stats = cached_stats.copy()
                self.cache_flag = False

            self.renew_stats()
            self.refresh_screen()

            # Init only runs once
            if self.init_flag:
                self.init_flag = False

                # Check if alert page is full, if so, auto scroll down
                if len(self.stats['alert_messages']) > self.alrtscr_height:
                    self.topLineNum = len(self.stats['alert_messages']) - (self.alrtscr_height - 1)

            # Wait for 10 seconds, but allow user input
            start = time.time()
            while (time.time() - start) < 10:
                # Grab User Inputs
                c = self.stdscr.getch()
                if c == curses.KEY_UP:
                    self.pagination(self.UP)
                elif c == curses.KEY_DOWN:
                    self.pagination(self.DOWN)
                elif c == self.KEY_B:
                    self.pagination(self.PAGE_UP)
                elif c == self.KEY_V:
                    self.pagination(self.PAGE_DOWN)
                elif c == self.ESC_KEY:
                    sys.exit()

                self.renew_alerts()

    def init_progress(self, num, length):
        """Prints minimal labels and a progress bar when SimpleHTTPMonitor is
        starting up for the first time."""

        height, width = self.stdscr.getmaxyx()
        ratio = (num / float(length))
        progress = ratio * (width - 24)
        self.stdscr.erase()

        # Print Titles
        self.stdscr.addstr(1, 1, "{0}".format(
            "### Simple HTTP Traffic Monitor ###".center(width - 2, ' ')))

        # Print Basic Info
        self.stdscr.addstr(2, 2, "Monitored Logfile: {0}".format(self.logfile))
        self.stdscr.addstr(3, 2, "Last Status Update: Initializing...")

        # Print Progress Bar
        self.stdscr.addstr(5, 2, "Progress: {0:.2f}% |{1}>".format(
            ratio * 100, "=" * int(progress)))

        self.stdscr.refresh()

    def check_for_cache(self):
        """Checks if there is an existing cache file to read from. Returns -1
        upon error."""

        cache_filename = 'slc_cache_{}.json'.format(
            self.logfile.split('/')[-1])
        stats = {}
        try:
            with open(cache_filename, 'r') as f:
                stats = json.loads(f.read())
                for idx, tmstmp in enumerate(stats['2_min_traffic']):
                    stats['2_min_traffic'][idx] = self.date_to_datetime_utc(tmstmp)
                stats['updated_utc'] = self.date_to_datetime_utc(stats['updated_utc'])
        except Exception as e:
            log.exception("{0}".format(e))
            stats = -1
        return stats

    def refresh_screen(self):
        """Refreshs the main SimpleHTTPMonitor screen, updating various data
        displayed throughout the screen. Also adjusts and calls for a refresh
        of the alert messages screen (alrtscr)."""

        height, width = self.stdscr.getmaxyx()
        self.stdscr.erase()

        # Print Titles
        self.stdscr.addstr(1, 1, "{0}".format(
            "### Simple HTTP Traffic Monitor ###".center(width - 2, ' ')))
        self.stdscr.addstr(5, 2,
            "Summary Statistics".center((width / 2) - 1, ' '))
        self.stdscr.addstr(5, width / 2, "Alerts ({0} total)".format(
            len(self.stats['alert_messages'])).center((width / 2) - 1, ' '))

        # Controls Info
        self.stdscr.addstr(2, (width / 3) * 2, "{0}".format(
                "Alert Controls: arrow keys (up/down), b/v (page up/down)"))
        self.stdscr.addstr(3, (width / 3) * 2, "{0}".format(
                "Basic Controls: ESC (safely exits program)"))

        # Print Boundaries
        self.stdscr.box()
        self.stdscr.hline(6, 2, '-', width - 4)
        self.stdscr.vline(7, width / 2, '|', height - 8)

        # Print Basic Info
        self.stdscr.addstr(2, 2, "Monitored Logfile: {0}".format(self.logfile))
        self.stdscr.addstr(3, 2, "Last Status Update: {0}".format(
            self.stats['updated_utc'].strftime("%m/%d/%Y %H:%M:%S UTC")))

        # Print Summary Statistics
        self.stdscr.addstr(9, 2, "Traffic (hits past 2 minutes): {0}".format(
            len(self.stats['2_min_traffic'])))
        self.stdscr.addstr(
            10, 2, "Threshold (hits): {0}".format(self.alert_threshold))
        self.stdscr.addstr(
            11, 2, "Average Hits/hour: {0}".format(self.stats['average_hits_hour']))
        self.stdscr.addstr(
            12, 2, "Peak Hits/hour: {0}".format(self.stats['peak_hits_hour']))

        self.stdscr.addstr(14, 2, "Top 5...")
        self.stdscr.addstr(15, 2, "Sections (hits from most to least):")
        idx = 16
        for section, hits in self.stats['top_5_sections']:
            self.stdscr.addstr(idx, 2, "\t{0}: {1}".format(section, hits))
            idx += 1
        self.stdscr.addstr(idx + 1, 2, "Remotehosts by hits (most to least):")
        idx = idx + 2
        for remotehost, hits in self.stats['top_5_remotehost_visits']:
            self.stdscr.addstr(idx, 2, "\t{0}: {1}".format(remotehost, hits))
            idx += 1

        # Most Data Hungry Remotehosts (total data)
        self.stdscr.addstr(
            idx + 1, 2, "Remotehosts by data consumption (most to least):")
        idx = idx + 2
        for ip_address, hits in self.stats['top_5_remotehost_consumers']:
            self.stdscr.addstr(idx, 2, "\t{0}: {1}".format(ip_address, hits))
            idx += 1

        # Setup Alerts Pad and Print Alerts (Keeping them persistent)
        self.alrtscr_nrows = height - 9
        self.alrtscr_ncols = (width / 2) - 4
        self.alrtscr_x = 8
        self.alrtscr_y = (width / 2) + 2

        self.alrtscr = self.stdscr.subpad(self.alrtscr_nrows,
            self.alrtscr_ncols, self.alrtscr_x, self.alrtscr_y)
        self.alrtscr.scrollok(True)
        self.alrtscr_height, self.alrtscr_width = self.alrtscr.getmaxyx()

        self.PAGE_DOWN = self.alrtscr_height / 2
        self.PAGE_UP = -1 * (self.alrtscr_height / 2)

        # Make sure that if traffic is high, that another alert is printed
        if len(self.stats['2_min_traffic']) >= self.alert_threshold:
            self.two_min_traffic_flag = False
        self.renew_alerts()

        self.stdscr.refresh()

    def date_to_datetime_utc(self, date):
        """Converts from a common wc3 access log timestamp string of the format
        'dd/mmm/yyyy:hh:mm:ss tz', to a timezone aware datetime object set to
        UTC."""

        # Remove the ':' between dd/mmm/yyyy and hh:mm:ss
        date = re.sub(r'\:(?=\d+\:\d+\:\d+ )', ' ', date)
        date = parser.parse(date)
        return date.astimezone(pytz.utc)

    def datetime_utc_to_string(self, date):
        """Converts from a timezone aware datetime object set to UTC, to a common 
        wc3 access log timestamp string of the format 'dd/mmm/yyyy:hh:mm:ss tz'"""

        return date.strftime("%m/%d/%Y:%H:%M:%S %z")

    def parse_request_for_section(self, request):
        """Parses a common wc3-formatted request string of format 
        'METHOD FILEPATH HTTP/VERSION' and returns the section of the filepath 
        (a section being the content before the second '/' in a URL. i.e. the 
        section for "http://my.site.com/pages/create' is "http://my.site.com/pages")"""

        try:
            method, section, version = request.split(' ')
        except Exception as e:
            log.exception("Request of unexpected format: {}".format(e))
            return request

        # Assumes that URLs with no second '/' will be categorized as '/'
        # signifying the base
        section = section.split('/')
        if len(section) < 3:
            return '/'

        return "/{0}".format(section[1])

    def count_section(self, section):
        """Increments a section counter in a dictionary called sections which
        is stored in the dictionary stats, to keep track of the number of
        requests to each section."""

        if section not in self.stats['sections'].keys():
            self.stats['sections'][section] = 1
        else:
            self.stats['sections'][section] += 1

    def top_5_sections(self):
        """Determines the top 5 most requested sections by iterating over the
        stats['sections'] dictionary."""

        self.stats['top_5_sections'] = []
        sorted_sections = sorted(
            self.stats['sections'].items(), key=operator.itemgetter(1))
        for section, num_hits in reversed(sorted_sections[-5:]):
            self.stats['top_5_sections'].append((section, num_hits))

    def count_remotehost_visit(self, remotehost):
        """Increments a remotehost counter in a dictionary called remotehost_visits
        which is stored in the dictionary stats, to keep track of the number of
        visits from each remotehost."""

        if remotehost not in self.stats['remotehost_visits'].keys():
            self.stats['remotehost_visits'][remotehost] = 1
        else:
            self.stats['remotehost_visits'][remotehost] += 1

    def top_5_remotehost_visitors(self):
        """Determines the top 5 remotehost visitors by iterating over the
        stats['remotehost_visits'] dictionary."""

        self.stats['top_5_remotehost_visits'] = []
        sorted_remotehost_visits = sorted(
            self.stats['remotehost_visits'].items(), key=operator.itemgetter(1))
        for remotehost, num_hits in reversed(sorted_remotehost_visits[-5:]):
            self.stats['top_5_remotehost_visits'].append(
                (remotehost, num_hits))

    def count_remotehost_data(self, info):
        """Increments a remotehost counter in a dictionary called remotehost_data
        which is stored in the dictionary stats, to keep track of the amount of
        data consumption by each remotehost."""

        remotehost = info['remotehost']
        bytes = info['bytes']
        if remotehost not in self.stats['remotehost_data'].keys():
            self.stats['remotehost_data'][remotehost] = int(bytes)
        else:
            self.stats['remotehost_data'][remotehost] += int(bytes)

    def top_5_remotehost_consumers(self):
        """Determines the top 5 remotehost data consumers by iterating over the
        stats['remotehost_data'] dictionary."""

        self.stats['top_5_remotehost_consumers'] = []
        sorted_remotehost_data = sorted(
            self.stats['remotehost_data'].items(), key=operator.itemgetter(1))
        for remotehost, bytes in reversed(sorted_remotehost_data[-5:]):
            self.stats['top_5_remotehost_consumers'].append(
                (remotehost, bytes))

        # Make bytes into human-readable denominations
        # Could be rewritten to use KiB rather than KB
        for index, info in enumerate(self.stats['top_5_remotehost_consumers']):
            remotehost, bytes = info
            data = ''
            kb = bytes / 1000.0
            if kb >= 1000.0:
                mb = kb / 1000.0
                if mb >= 1000.0:
                    gb = mb / 1000.0
                    if gb >= 1000.0:
                        tb = gb / 1000.0
                        data = "{0:.2f} TB".format(tb)
                    else:
                        data = "{0:.2f} GB".format(gb)
                else:
                    data = "{0:.2f} MB".format(mb)
            else:
                data = "{0:.2f} KB".format(kb)
            self.stats['top_5_remotehost_consumers'][
                index] = (remotehost, data)

    def renew_stats(self):
        """Parses data from unread lines in the provided logfile. Data is then
        organized into corresponding keys in the stats dictionary for use by
        other functions."""

        # Only read in unread lines
        data = []
        try:
            with open(self.logfile, 'r') as f:
                for i, line in enumerate(f):
                    if i >= self.stats['master_index']:
                        data.append(line)
        except:
            self.optparser.error(
                "Could not open logfile {}".format(self.logfile))

        # Constants
        self.stats['updated_utc'] = datetime.now(pytz.utc)
        now = self.stats['updated_utc']  # redundant, but helps be explicit

        if data:
            if not data[-1]:
                data.pop(-1)

            for num, line in enumerate(data):
                if self.init_flag:
                    self.init_progress(num, len(data))

                line = re.search(self.regex, line)
                info = {}
                for idx, label in enumerate(self.log_labels):
                    if label == 'date_utc':
                        info[label] = self.date_to_datetime_utc(
                            line.group(idx + 1))
                        if (now - info[label]) <= self.TWOMINS:
                            self.stats['2_min_traffic'].append(info[label])
                    elif label == 'request':
                        info[label] = line.group(idx + 1)
                        info['section'] = self.parse_request_for_section(
                            line.group(idx + 1))
                    else:
                        try:
                            info[label] = line.group(idx + 1)
                        except AttributeError as e:
                            log.error(
                                "Malformed logfile line: {0}\n\t{1}".format(
                                    e, line.group(0)))
                            continue

                self.count_section(info['section'])
                self.count_remotehost_visit(info['remotehost'])
                self.count_remotehost_data(info)

                self.stats['master_index'] += 1

            self.top_5_sections()
            self.top_5_remotehost_visitors()
            self.top_5_remotehost_consumers()

        # Finally check any remaining 2_min_traffic items to see current load
        for idx, hit_utc_tstmp in enumerate(self.stats['2_min_traffic']):
            if (now - hit_utc_tstmp) > self.TWOMINS:
                self.stats['2_min_traffic'].pop(idx)

    def renew_alerts(self):
        """Refreshs the alert messages screen section by first calling
        check_for_new_alerts() and then refreshing the data displayed in the
        alert messages screen."""

        self.check_for_new_alerts()

        self.alrtscr.erase()
        top = self.topLineNum
        bottom = self.topLineNum + (self.alrtscr_height - 1)
        for index, line in enumerate(self.stats['alert_messages'][top:bottom]):
            self.alrtscr.addstr(line + "\n")

        self.alrtscr.refresh()

    def check_for_new_alerts(self):
        """Checks for new alerts by comparing the traffic from the last 2
        minutes to the configured alert_threshold. If a new alert is found,
        an alert message is appended to the stats['alert_messages'] list to be
        displayed by the renew_alerts() function."""

        if len(self.stats['2_min_traffic']) >= self.alert_threshold and \
                self.two_min_traffic_flag is False:
            self.stats['alert_messages'].append(
                "{0}: High traffic generated an alert - hits = {1}, triggered at {2}".format(
                    len(self.stats['alert_messages']) + 1,
                    len(self.stats['2_min_traffic']),
                    self.stats['updated_utc'].strftime("%m/%d/%Y %H:%M:%S UTC")))
            self.two_min_traffic_flag = True

            # Check alert pad height to readjust view
            if len(self.stats['alert_messages']) > self.alrtscr_height:
                self.topLineNum = len(self.stats['alert_messages']) - (self.alrtscr_height - 1)

        elif len(self.stats['2_min_traffic']) < self.alert_threshold and \
                self.two_min_traffic_flag is True:
            self.stats['alert_messages'].append(
                "{0}: Recovered from high traffic - hits = {1}, recovered at {2}".format(
                    len(self.stats['alert_messages']) + 1,
                    len(self.stats['2_min_traffic']),
                    self.stats['updated_utc'].strftime("%m/%d/%Y %H:%M:%S UTC")))
            self.two_min_traffic_flag = False

            # Check alert pad height to readjust view
            if len(self.stats['alert_messages']) > self.alrtscr_height:
                self.topLineNum = len(self.stats['alert_messages']) - (self.alrtscr_height - 1)

    def pagination(self, increment):
        """Handles parsing user input to allow for pagination of the alert
        messages screen section. The alert messages screen section must keep
        alert messages available for historical reasons, and so scrolling
        allows for a more efficient use of screen real estate, while still
        keeping the integrity of the alert messages data."""

        # Redundant for readability
        alert_length = len(self.stats['alert_messages'])

        if increment == self.UP and self.topLineNum != 0:
            self.topLineNum += self.UP
        elif increment == self.DOWN and \
                (self.topLineNum + (self.alrtscr_height - 1)) != alert_length and \
                alert_length > self.alrtscr_height:
            self.topLineNum += self.DOWN
        elif increment == self.PAGE_UP and \
                self.topLineNum >= ((self.alrtscr_height - 1) / 2):
            self.topLineNum += self.PAGE_UP
        elif increment == self.PAGE_UP and self.topLineNum != 0:
            self.topLineNum = 0
        elif increment == self.PAGE_DOWN and \
                (self.topLineNum + (self.alrtscr_height - 1)) <= alert_length - ((self.alrtscr_height - 1) / 2):
            self.topLineNum += self.PAGE_DOWN
        elif increment == self.PAGE_DOWN and \
                (self.topLineNum + (self.alrtscr_height - 1)) != alert_length:
            self.topLineNum = alert_length - (self.alrtscr_height - 1)

    def __del__(self):
        """Cleans up loose ends whenever the program exits by first returning
        the console to its' original state, and then by attempting to cache
        any collected data, if the options.cache_flag is set."""

        try:
            curses.echo()
            curses.nocbreak()
            curses.endwin()

            if self.options.cache_flag:
                for idx, tmstmp in enumerate(self.stats['2_min_traffic']):
                    self.stats['2_min_traffic'][idx] = self.datetime_utc_to_string(tmstmp)
                self.stats['updated_utc'] = self.datetime_utc_to_string(self.stats['updated_utc'])
                cache_filename = 'slc_cache_{}.json'.format(
                    self.logfile.split('/')[-1])
                with open(cache_filename, 'wb') as f:
                    f.write(json.dumps(self.stats))
        except Exception as e:
            log.exception("Failed in __del__: {0}".format(e))

if __name__ == "__main__":
    # Parse Command Line Options
    usage = "usage: %prog [options] LOGFILE"
    optparser = OptionParser(usage=usage)
    optparser.add_option("-f", "--format", type="int", dest="format", default=1,
                         help="format of logfile, as an integer 1 (default), 2, or 3 \
                               (1 - Common, 2 - VirtualHost, 3 - Extended)")
    optparser.add_option("-t", "--threshold", type="int", dest="threshold", 
                         default=100,
                         help="traffic threshold for warnings (defaults to 100)")
    optparser.add_option("-l", "--logging", type="string", dest="logging_filename", 
                         default='simple_log_consumer.log',
                         help="logging file that simple_log_consumer.py prints logs to \
                               (defaults to 'simple_log_consumer.log')")
    optparser.add_option("-c", "--cache", action="store_true", 
                         dest="cache_flag", default=False,
                         help="turn caching off (defaults to on)")
    options = optparser.parse_args()[0]

    try:
        logfile = optparser.parse_args()[1][0]
    except IndexError:
        optparser.error('Logfile is required!')

    shm = SimpleHTTPMonitor(options, logfile)
