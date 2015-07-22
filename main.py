#!/usr/bin/env python
"""climyadmin.py

A simple command line interface that allows for the control of a MySQL
database, in much the same fashion as a program such as phpMyAdmin."""


import re
import operator
import time
import pytz
import sys
import curses
import curses.panel
import curses.textpad
import curses.wrapper
import json
import math
import logging as log
import sqlalchemy
import subprocess
from pipes import quote
from dateutil import parser
from optparse import OptionParser
from datetime import datetime, timedelta


class DBInterface:

    ESC_KEY = 27
    ALT_KEY_ENTER = 10
    protocol = "postgresql"
    driver = "pg8000"

    def __init__(self):
        curses.wrapper(self.fake_init)

    def fake_init(self,stdscr):
        # Setup Curses Screen
        self.stdscr = curses.initscr()
        self.stdscr.keypad(1)
        self.stdscr.nodelay(1)
        curses.noecho()
        curses.cbreak()

        # Variables
        self.sel_cursor = (0, 0)

        self.run()

    def run(self):
        """Initializes the main DBInterface screen, updating various data
        displayed throughout the screen. Also adjusts and calls for a refresh
        of the screen."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        self.stdscr.erase()

        # Print Title
        self.stdscr.addstr(1, 1, "{0}".format("### cliMyAdmin ###".center(width - 2, ' ')))

        # Controls Info
        self.stdscr.addstr(2, (width / 3) * 2, "{0}".format(
                "Controls: arrow keys (up/down), enter (select)"))
        self.stdscr.addstr(3, (width / 3) * 2, "{0}".format(
                "          ESC key (close current window)"))

        # Print Boundaries
        self.stdscr.box()
        self.stdscr.hline(4, 2, '-', width - 4)

        # Update screen
        curses.panel.update_panels()
        self.stdscr.refresh()

        # Enter Main Menu
        self.main_menu()

    def make_panel(self, h, w, y, x, str):
        """Handles the creation of a panel (curses.panel), which is a
        stackable window."""

        # Create a new window, draw a box, and add a title
        win = curses.newwin(h, w, y, x)
        win.erase()
        win.box()
        win.addstr(1, 1, str.center(w - 2, ' '))

        # Instantiate a panel with our new window
        panel = curses.panel.new_panel(win)
        return win, panel

    def set_select_cursor(self, win, new_pos):
        """Handles moving the X selection cursor on the screen"""

        # Remove old cursor
        x, y = self.sel_cursor
        win.addstr(x, y, " ")

        # Add new cursor
        x, y = new_pos
        win.addstr(x, y, "X")

        # Update self.sel_cursor
        self.sel_cursor = new_pos

        return win

    def main_menu(self):
        """Handles the Main Menu loop."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        # Print Menu Tabs
        menu_width = int(width * 0.13)
        win1, panel1 = self.make_panel(9, menu_width, 6, (width / 2) - (menu_width / 2), "Main Menu")
        win1.addstr(first_y, 1, " [ ] Databases")
        win1.addstr(first_y + 1, 1, " [ ] SQL")
        win1.addstr(first_y + 2, 1, " [ ] Export")
        win1.addstr(first_y + 3, 1, " [ ] Import")
        last_y = first_y + 3

        # Initialize select cursor
        self.sel_cursor = (3, 3)
        self.set_select_cursor(win1, self.sel_cursor)
        curses.panel.update_panels()
        self.stdscr.refresh()

        while 1:
            # Check for control movements
            c = self.stdscr.getch()
            if c == curses.KEY_DOWN:
                tmp_x, tmp_y = self.sel_cursor
                if tmp_x < last_y:
                    tmp_cur = (tmp_x + 1, tmp_y)
                    self.set_select_cursor(win1, tmp_cur)
            elif c == curses.KEY_UP:
                tmp_x, tmp_y = self.sel_cursor
                if tmp_x > first_y:
                    tmp_cur = (tmp_x - 1, tmp_y)
                    self.set_select_cursor(win1, tmp_cur)
            elif c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                tmp_y, tmp_x = self.sel_cursor
                if tmp_y == first_y:
                    self.database_select_screen()
                else:
                    pass
            elif c == 27:
                sys.exit()

            # Update Screen
            self.refresh_screen()

    def database_select_screen(self):
        """Handles the database selection loop. Can be removed after we add commandline args"""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        menu_width = int(width * 0.33)
        win1, panel1 = self.make_panel(9, menu_width, 6, (width / 2) - (menu_width / 2), "Connect to Server:")
        win1.addstr(first_y, 1, "Enter [username:password@hostname] Here:")
        panel1.top()
        tmp_height,tmp_width = win1.getmaxyx()
        edit_win = curses.newwin(1, tmp_width - 5, 6 + first_y + 2, (width / 2) - (menu_width / 2) + 2)
        rect = curses.textpad.rectangle(win1, first_y + 1, 1, first_y + 3, tmp_width - 2)

        self.refresh_screen()

        text = curses.textpad.Textbox(edit_win).edit()
        del edit_win

        if self.attempt_connection(win1,text.rstrip()):
            del win1
            del panel1
            self.list_databases_screen()

    def attempt_connection(self,win,input_string):
        """Helper function for attempting to create a engine and connect to a db."""

        try:
            user,host = input_string.split('@')
            username,password = user.split(':')
            db_string=self.create_db_string(username,password,host)
            self.engine = sqlalchemy.create_engine(db_string)
        except Exception as msg:
            self.alert_window("Database does not exist!")
            return False
        else:
            try:
                self.connection = self.engine.connect()
            except Exception as msg:
                self.alert_window("Database could not be connected to!")
                return False
        return True

    def create_db_string(self,username,password,hostname):
        """Helper function for creating and formatting a remote server/db string. Will have to be expanded to support MySQL."""
        return "{}+{}://{}:{}@{}/postgres".format(self.protocol,self.driver,username,password,hostname)

    def list_databases_screen(self):
        """Screen for listing databases. Will have to be expanded to support MySQL"""
        db_names = self.engine.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
        db_names = db_names.fetchall()

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        db_win, panel1 = self.make_panel(len(db_names)+3, menu_width, 6, (width / 2) - (menu_width / 2), "Select Database")
        db_win.box()
        win_pos = 0

        i = 0
        for name in db_names:
            db_win.addstr(i+2,1," [ ] {}".format(name['datname']))
            i+=1

        # Hide Cursor
        curses.curs_set(0)

        x_pos = 3
        self.sel_cursor = (2, x_pos)
        self.set_select_cursor(db_win, self.sel_cursor)
        curses.panel.update_panels()
        self.refresh_screen()
        db_win.refresh()

        while 1:
            c = self.stdscr.getch()
            if c == curses.KEY_DOWN:
                win_pos=min(win_pos+1,len(db_names)-1)
                self.set_select_cursor(db_win, (win_pos+2,x_pos))
            elif c == curses.KEY_UP:
                win_pos=max(win_pos-1,0)
                self.set_select_cursor(db_win, (win_pos+2,x_pos))
            elif c == 27:
                del db_win
                return
            db_win.refresh()
            self.refresh_screen()

    def alert_window(self,msg):
        """Creates a window useful for displaying error messages"""

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        alert_win = curses.newwin(9, menu_width, 6, (width / 2) - (menu_width / 2))
        alert_win.box()
        alert_win.addstr(9 / 2, menu_width / 2 - menu_width / 4, msg)

        self.refresh_screen()
        alert_win.refresh()
        while 1:
            c = self.stdscr.getch()
            if c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                break
        del alert_win

    def refresh_screen(self):
        """Refreshes the main DBInterface screen to readjust proportions."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        self.stdscr.erase()

        # Print Title
        self.stdscr.addstr(1, 1, "{0}".format("### cliMyAdmin ###".center(width - 2, ' ')))

        # Controls Info
        self.stdscr.addstr(2, (width / 3) * 2, "{0}".format(
                "Controls: arrow keys (up/down), enter (select)"))
        self.stdscr.addstr(3, (width / 3) * 2, "{0}".format(
                "          ESC key (close current window)"))

        # Print Boundaries
        self.stdscr.box()
        self.stdscr.hline(4, 2, '-', width - 4)

        # Update Screen
        curses.panel.update_panels()
        self.stdscr.refresh()

    def __del__(self):
        """Cleans up loose ends whenever the program exits by returning
        the console to its' original state."""

        try:
            curses.echo()
            curses.nocbreak()
            curses.endwin()

        except Exception as e:
            log.exception("Failed in __del__: {0}".format(e))

if __name__ == "__main__":
    shm = DBInterface()
