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
import db
import sqlalchemy
import subprocess
import argparse
from pipes import quote
from dateutil import parser
from datetime import datetime, timedelta


class DBInterface:

    ESC_KEY = 27
    ALT_KEY_ENTER = 10
    db = None

    def __init__(self):
        curses.wrapper(self.fake_init)

    def fake_init(self,stdscr):
        parser = argparse.ArgumentParser(add_help=False) #we need -h switch
        parser.add_argument('-dbms', '--dbms', choices=['postgres', 'mysql'], \
                required=True, metavar='DBTYPE')
        parser.add_argument('-u', '--username', required=True, metavar='USER')
        parser.add_argument('-p', '--password', required=True, metavar='PASS')
        parser.add_argument('-h', '--hostname', default='localhost', metavar='HOST')
        args = parser.parse_args()
        if args.dbms == 'postgres':
            self.db = db.PostgresDatabase(args.username, args.password, args.hostname)
        elif args.dbms == 'mysql':
            self.db = db.MySQLDatabase(args.username, args.password, args.hostname)
        else:
            raise ValueError('dbms should be postgres or mysql')
        self.db.setup()

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
                    self.list_databases_screen()
                else:
                    pass
            elif c == 27:
                sys.exit()

            # Update Screen
            self.refresh_screen()

    def list_databases_screen(self):
        """Screen for listing databases. Will have to be expanded to support MySQL"""
        db_names = self.db.list_databases()

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        db_win, panel1 = self.make_panel(len(db_names)+3, menu_width, 6, (width / 2) - (menu_width / 2), "Select Database")
        db_win.box()
        win_pos = 0

        i = 0
        for name in db_names:
            db_win.addstr(i+2,1," [ ] {}".format(name))
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
            elif c == self.ALT_KEY_ENTER or c == curses.KEY_ENTER:
                try:
                    self.db.database_connect(db_names[win_pos])
                except Exception:
                    del db_win
                    return
                self.list_tables_screen()
            elif c == 27:
                del db_win
                return
            db_win.refresh()
            self.refresh_screen()

    def list_tables_screen(self):
        """Screen for listing tables. Will have to be expanded to support MySQL"""
        table_names = self.db.list_table_names()
        if not len(table_names):
            self.alert_window('Database is empty!')
            return

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        table_win, panel1 = self.make_panel(len(table_names)+3, menu_width, 6, (width / 2) - (menu_width / 2), "Select Table")
        table_win.box()
        win_pos = 0

        i = 0
        for name in table_names:
            table_win.addstr(i+2,1," [ ] {}".format(name))
            i+=1

        # Hide Cursor
        curses.curs_set(0)

        x_pos = 3
        self.sel_cursor = (2, x_pos)
        self.set_select_cursor(table_win, self.sel_cursor)
        curses.panel.update_panels()
        self.refresh_screen()
        table_win.refresh()

        while 1:
            c = self.stdscr.getch()
            if c == curses.KEY_DOWN:
                win_pos=min(win_pos+1,len(table_names)-1)
                self.set_select_cursor(table_win, (win_pos+2,x_pos))
            elif c == curses.KEY_UP:
                win_pos=max(win_pos-1,0)
                self.set_select_cursor(table_win, (win_pos+2,x_pos))
            # elif c == self.ALT_KEY_ENTER or c == curses.KEY_ENTER:
            #     if self.attempt_connection(input_string, table_names[win_pos]['datname']):
            #         self.list_tables_screen()
            #     else:
            #         del table_win
            #         return
            elif c == 27:
                del table_win
                return
            table_win.refresh()
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
        self.refresh_screen()

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
