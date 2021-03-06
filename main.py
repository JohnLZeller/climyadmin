#!/usr/bin/env python
from __future__ import division
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
import os
import subprocess
import argparse
from pipes import quote
from dateutil import parser
from datetime import datetime, timedelta
from sqlalchemy.exc import ProgrammingError

class DBInterface:

    ESC_KEY = 27
    ALT_KEY_ENTER = 10
    db = None

    def __init__(self, args):
        self.args = args
        self.win_list = []
        curses.wrapper(self.fake_init, args)

    def fake_init(self, stdscr, args):
        """Initialize the application."""

        if args.dbms == 'postgres':
            self.db = db.PostgresDatabase(args.username, args.password, args.server)
        elif args.dbms == 'mysql':
            self.db = db.MySQLDatabase(args.username, args.password, args.server)
        else:
            raise ValueError('dbms should be postgres or mysql')

        self.db.setup()

        # Setup Curses Screen
        self.stdscr = curses.initscr()
        self.stdscr.keypad(1)
        self.stdscr.nodelay(1)
        curses.start_color()
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
        self.stdscr.addstr(2, (width // 3) * 2, "{0}".format(
                "Controls: arrow keys (up/down), enter (select)"))
        self.stdscr.addstr(3, (width // 3) * 2, "{0}".format(
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

    def init_main_menu_select_cursor(self, win):
        """Initializes the main menu cursor to the first position"""

        self.sel_cursor = (3, 3)
        self.set_select_cursor(win, self.sel_cursor)
        curses.panel.update_panels()
        self.stdscr.refresh()

    def main_menu(self):
        """Handles the Main Menu loop."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        # Print Menu Tabs
        menu_width = int(width * 0.13)
        win1, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Main Menu")
        win1.addstr(first_y, 1, " [ ] Databases")
        win1.addstr(first_y + 1, 1, " [ ] SQL")
        win1.addstr(first_y + 2, 1, " [ ] Export")
        win1.addstr(first_y + 3, 1, " [ ] Import")
        last_y = first_y + 3

        self.init_main_menu_select_cursor(win1)

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
                    self.init_main_menu_select_cursor(win1)
                elif tmp_y == (first_y + 1):
                    self.sql_select_screen()
                    self.init_main_menu_select_cursor(win1)
                elif tmp_y == (first_y + 2):
                    self.export_select_screen()
                    self.init_main_menu_select_cursor(win1)
                elif tmp_y == (first_y + 3):
                    self.import_select_screen()
                    self.init_main_menu_select_cursor(win1)
                else:
                    pass
            elif c == self.ESC_KEY:
                sys.exit()

            # Update Screen
            self.refresh_screen()

    def list_databases_screen(self):
        """Screen for listing databases."""
        db_names = self.db.list_databases()

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        db_win, panel1 = self.make_panel(len(db_names)+6, menu_width, 6, (width // 2) - (menu_width // 2), "Select Database")
        db_win.box()
        win_pos = 0

        db_win.addstr(len(db_names)+3, 1, "a: add a new database")
        db_win.addstr(len(db_names)+4, 1, "d: delete a database")
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
                self.db.database_connect(db_names[win_pos])
                self.list_tables_screen()
            elif c == ord('a'):
                text = self.text_window('Add new database title')
                try:
                    self.db.create_database(text)
                except ProgrammingError:
                    self.alert_window('Invalid Query!')
                # lazily kick user back once
                del db_win
                return
            elif c == ord('d'):
                self.stdscr.nodelay(0)
                self.alert_window('PRESSING d AGAIN WILL DELETE THIS DATABASE!')
                c = self.stdscr.getch()
                if c == ord('d'):
                    # lazily kick user back once
                    try:
                        self.db.delete_database(db_names[win_pos])
                    except ProgrammingError:
                        self.alert_window('Invalid Query!')
                    self.stdscr.nodelay(1)
                    del db_win
                    return
                self.stdscr.nodelay(1)
                self.init_main_menu_select_cursor(db_win)
            elif c == self.ESC_KEY:
                del db_win
                return
            db_win.refresh()
            self.refresh_screen()


    def list_tables_screen(self):
        """Screen for listing tables."""

        table_names = self.db.list_table_names()

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        displayable_height = 10
        window_top_margin = 6
        inner_top_margin = 3
        inner_bottom_margin = 3
        start_x = (width // 2) - (menu_width // 2)
        table_win, panel1 = self.make_panel( \
                displayable_height+inner_top_margin+inner_bottom_margin, \
                menu_width, window_top_margin, start_x, "Select Table")
        length = len(table_names) if len(table_names) > 0 else 1
        table_pad = curses.newpad(length, menu_width)
        table_win.box()
        win_pos = 0

        table_win.addstr(inner_top_margin+displayable_height, 1, "a: add a new table")
        table_win.addstr(inner_top_margin+displayable_height+1, 1,"d: delete a table")
        i = 0
        for name in table_names:
            table_pad.addstr(i,1," [ ] {}".format(name))
            i+=1

        # Hide Cursor
        curses.curs_set(0)

        x_pos = 3
        self.sel_cursor = (0, x_pos)
        self.set_select_cursor(table_pad, self.sel_cursor)
        curses.panel.update_panels()
        self.refresh_screen()
        # table_pad.refresh(0,0, start_y, start_x, displayable_height, menu_width)
        current_page = 1
        while 1:
            c = self.stdscr.getch()
            if c == curses.KEY_DOWN:
                if len(table_names) == 0:
                    self.alert_window('No tables to select')
                    continue
                win_pos=min(win_pos+1,len(table_names)-1)
                self.set_select_cursor(table_pad, (win_pos,x_pos))
                self.refresh_screen()
            elif c == curses.KEY_UP:
                if len(table_names) == 0:
                    self.alert_window('No tables to select')
                    continue
                win_pos=max(win_pos-1,0)
                self.set_select_cursor(table_pad, (win_pos,x_pos))
                self.refresh_screen()
            if win_pos > (current_page * displayable_height) - 1:
                current_page += 1
                self.refresh_screen()
            elif win_pos < (current_page - 1) * displayable_height:
                current_page -= 1
                self.refresh_screen()
            elif c == self.ALT_KEY_ENTER or c == curses.KEY_ENTER:
                if len(table_names) == 0:
                    self.alert_window('No tables to select')
                    continue
                self.list_rows_screen(table_names[win_pos])
                self.refresh_screen()
            elif c == ord('a'):
                text = self.text_window('Add New Table')
                try:
                    self.db.create_table(text)
                except ProgrammingError:
                    self.alert_window('Invalid Query!')
                del table_win
                return
            elif c == ord('d'):
                if len(table_names) == 0:
                    self.alert_window('No tables to delete')
                    continue

                self.stdscr.nodelay(0)
                self.alert_window('PRESSING d AGAIN WILL DELETE THIS TABLE!')
                c = self.stdscr.getch()
                if c == ord('d'):
                    try:
                        self.db.delete_table(table_names[win_pos])
                    except ProgrammingError:
                        self.alert_window('Invalid Query!')
                    self.stdscr.nodelay(1)
                    # lazily kick user back once
                    del table_win
                    return
                self.init_main_menu_select_cursor(table_win)
            elif c == self.ESC_KEY:
                del table_pad
                del table_win
                del panel1
                return
            table_pad.refresh((current_page - 1) * displayable_height, 1, \
                    inner_top_margin+window_top_margin, start_x+1, \
                    inner_top_margin+window_top_margin+displayable_height-1, \
                    start_x+menu_width-3)

    def list_rows_screen(self,table_name):
        """Creates a menu with the rows of a table"""

        try:
            column_names = self.db.list_column_names(table_name)
        except KeyError:
            self.alert_window("Failed to access table. Ensure that '{0}' has a primary key.".format(table_name))
            return False

        rows = self.db.list_rows(table_name)

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.77)
        displayable_height = 10
        window_top_margin = 6
        inner_top_margin = 4
        inner_bottom_margin = 4
        start_x = (width // 2) - (menu_width // 2)
        table_win, panel1 = self.make_panel( \
                displayable_height+inner_top_margin+inner_bottom_margin, \
                menu_width, window_top_margin, start_x, "Select Row")
        max_pages = int( math.ceil( (len(rows) + 2) / displayable_height ) )
        table_pad = curses.newpad(max_pages*displayable_height, menu_width)
        table_win.box()

        start_col = ' # '
        stcol_len = len(start_col)
        column_width = (menu_width-stcol_len)//len(column_names)
        win_pos = 0

        #TODO: put multiple things in a row
        table_win.addstr(2,1,start_col)
        table_win.addstr(inner_top_margin+displayable_height, 1, "a: add a new row")
        table_win.addstr(inner_top_margin+displayable_height+1, 1,"d: delete a row")
        table_win.addstr(inner_top_margin+displayable_height+2, 1,"m: modify a row")

        for idx, name in enumerate(column_names):
            table_win.addstr(2,1+idx*column_width+stcol_len,"| {}".format(name))
        table_win.addstr(3,1,'-' * ( menu_width - 2 ) )
        for idx,row in enumerate(rows):
            table_pad.addstr(idx,0,"{}".format(str(idx)))
            for j,name in enumerate(column_names):
                table_pad.addstr(idx,j*column_width+stcol_len,"| {}".format(row[name]))

        # Hide Cursor
        curses.curs_set(0)

        x_pos = 3
        self.sel_cursor = (0, x_pos)
        curses.panel.update_panels()
        self.refresh_screen()
        # table_pad.refresh(0,0, start_y, start_x, displayable_height, menu_width)
        current_page = 1
        while 1:
            c = self.stdscr.getch()
            if c == self.ESC_KEY:
                del table_pad
                del table_win
                del panel1
                return
            elif c == curses.KEY_UP:
                current_page = max(0,current_page-1)
            elif c == curses.KEY_DOWN:
                current_page = min(max_pages,current_page+1)
            elif c == ord('d'):
                text = self.text_window(title='Please input the row you would like to delete')
                try:
                    num = int(text)
                except ValueError:
                    self.alert_window('Row must be an integer!')
                    continue
                if num >= len(rows):
                    self.alert_window('That row does not exist!')
                    continue
                try:
                    self.db.delete_row(table_name, rows[num])
                except ProgrammingError:
                    self.alert_window('Invalid Query!')
                del table_pad
                del table_win
                del panel1
                return
            elif c == ord('a'):
                self.add_window(table_name, column_names)
                del table_win
                del panel1
                return
            elif c == ord('m'):
                text = self.text_window(title='Please input the row you would like to modify')
                try:
                    num = int(text)
                except ValueError:
                    self.alert_window('Row must be an integer!')
                    continue
                if num >= len(rows):
                    self.alert_window('That row does not exist!')
                    continue
                self.modify_window(table_name, column_names, rows[num])
            table_pad.refresh((current_page - 1) * displayable_height, 0, \
                    inner_top_margin+window_top_margin, start_x+1, \
                    inner_top_margin+window_top_margin+displayable_height-1, \
                    start_x+menu_width-2)

    def sql_select_screen(self):
        """Allows the user to enter a SQL query to be submitted to the server."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        menu_width = int(width * 0.33)
        win1, panel1 = self.make_panel(12, int(menu_width), 6, int((width / 2) - (menu_width / 2)), "SQL Query")
        win1.addstr(first_y, 1, "Enter SQL Query Here:")
        win1.addstr(first_y + 5, 1, "CTRL-H: Backspace")
        win1.addstr(first_y + 6, 1, "CTRL-G: Exit text entry window")
        win1.addstr(first_y + 7, 1, "ENTER: Submit")
        panel1.top()
        tmp_height, tmp_width = win1.getmaxyx()
        edit_win = curses.newwin(1, int(tmp_width - 5), int(6 + first_y + 2), int((width / 2) - (menu_width / 2) + 2))
        rect = curses.textpad.rectangle(win1, int(first_y + 1), 1, int(first_y + 3), int(tmp_width - 2))

        self.refresh_screen()

        text = curses.textpad.Textbox(edit_win).edit()
        del edit_win

        # TODO: Retrieve whatever the query gives back, and display it
        try:
            self.db.execute(text)
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Executed SQL!")
        except Exception:
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Failed to execute SQL!")

        curses.panel.update_panels()
        self.stdscr.refresh()

        while 1:
            # Check for control movements
            c = self.stdscr.getch()
            if c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                del alert_win
                break
        return

    def export_select_screen(self):
        """Allows the user to enter a file to export SQL to."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        menu_width = int(width * 0.33)
        win1, panel1 = self.make_panel(12, int(menu_width), 6, int((width / 2) - (menu_width / 2)), "Export SQL to a File")
        win1.addstr(first_y, 1, "Enter Absolute Path of File to Export to:")
        win1.addstr(first_y + 5, 1, "CTRL-H: Backspace")
        win1.addstr(first_y + 6, 1, "CTRL-G: Exit text entry window")
        win1.addstr(first_y + 7, 1, "ENTER: Submit")
        panel1.top()
        tmp_height,tmp_width = win1.getmaxyx()
        edit_win = curses.newwin(1, int(tmp_width - 5), int(6 + first_y + 2), int((width / 2) - (menu_width / 2) + 2))
        rect = curses.textpad.rectangle(win1, int(first_y + 1), 1, int(first_y + 3), int(tmp_width - 2))

        self.refresh_screen()

        text = curses.textpad.Textbox(edit_win).edit()
        del edit_win
        filename = text.rstrip()

        self.export_main_menu(filename)

    def export_main_menu(self, filename):
        """Screen for displaying the export main menu."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        # Print Menu Tabs
        menu_width = int(width * 0.33)
        choice_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "How would you like to export?")
        choice_win.addstr(first_y, 1, " [ ] All Databases")
        choice_win.addstr(first_y + 1, 1, " [ ] Select a Database")
        last_y = first_y + 1

        self.init_main_menu_select_cursor(choice_win)

        while 1:
            # Check for control movements
            c = self.stdscr.getch()
            if c == curses.KEY_DOWN:
                tmp_x, tmp_y = self.sel_cursor
                if tmp_x < last_y:
                    tmp_cur = (tmp_x + 1, tmp_y)
                    self.set_select_cursor(choice_win, tmp_cur)
            elif c == curses.KEY_UP:
                tmp_x, tmp_y = self.sel_cursor
                if tmp_x > first_y:
                    tmp_cur = (tmp_x - 1, tmp_y)
                    self.set_select_cursor(choice_win, tmp_cur)
            elif c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                tmp_y, tmp_x = self.sel_cursor
                if tmp_y == first_y:
                    self.export_all_databases(filename)
                    del choice_win
                    return
                elif tmp_y == (first_y + 1):
                    self.export_list_databases_screen(filename)
                    del choice_win
                    return
                else:
                    pass
            elif c == self.ESC_KEY:
                del choice_win
                return

            # Update Screen
            choice_win.refresh()
            self.refresh_screen()

    def export_all_databases(self, filename):
        """Exports all databases on the server to a specified filename."""

        height, width = self.stdscr.getmaxyx()

        mysql_command = "mysqldump --all-databases -u{0} -p{1} -h{2} > {3} 2>/dev/null".format(args.username, args.password, args.server, filename)

        # TODO: Test this!
        postgres_command = "pg_dumpall --username={0} --host={1} > {2} 2>/dev/null".format(args.username, args.server, filename)

        if self.args.dbms == 'postgres':
            # TODO: Test this!
            # You can use a .pgpass in the home dir of the account that this will run to supply the password
            os.system("echo {0}:*:*:{1}:{2} > ~/.pgpass".format(args.server, args.username, args.password))
            os.system("chmod 600 ~/.pgpass")
            ret = os.system(postgres_command)
            os.system("rm ~/.pgpass")
        elif self.args.dbms == 'mysql':
            ret = os.system(mysql_command)

        menu_width = int(width * 0.33)

        if ret == 0:
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Exported all databases!")
        else:
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Failed to export all databases!")

        curses.panel.update_panels()
        self.stdscr.refresh()

        while 1:
            # Check for control movements
            c = self.stdscr.getch()
            if c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                del alert_win
                break
        return

    def export_list_databases_screen(self, filename):
        """Screen for listing all databases and allowing the user to select one for exporting."""

        db_names = self.db.list_databases()

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.33)
        db_win, panel1 = self.make_panel(len(db_names) + 6, menu_width, 6, (width // 2) - (menu_width // 2), "Select Database")
        db_win.box()
        win_pos = 0

        i = 0
        for name in db_names:
            db_win.addstr(i+2,1," [ ] {}".format(name))
            i += 1
        db_win.addstr(i + 3, 1, "Press ENTER to export selection")

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
                self.export_database_selection(db_names[win_pos], filename)
                del db_win
                return
            elif c == self.ESC_KEY:
                del db_win
                return
            db_win.refresh()
            self.refresh_screen()

    def export_database_selection(self, selection, filename):
        height, width = self.stdscr.getmaxyx()

        mysql_command = "mysqldump {0} -u{1} -p{2} -h{3} > {4} 2>/dev/null".format(selection, args.username, args.password, args.server, filename)
        postgres_command = "pg_dump --username={0} --host={1} {2} > {3} 2>/dev/null".format(args.username, args.server, selection, filename)
        
        self.alert_window("Attempting Export!")

        if self.args.dbms == 'postgres':
            # TODO: Test this!
            # You can use a .pgpass in the home dir of the account that this will run to supply the password
            os.system("echo {0}:*:*:{1}:{2} > ~/.pgpass".format(args.server, args.username, args.password))
            os.system("chmod 600 ~/.pgpass")
            ret = os.system(postgres_command)
            os.system("rm ~/.pgpass")
        elif self.args.dbms == 'mysql':
            ret = os.system(mysql_command)

        menu_width = int(width * 0.33)

        if ret == 0:
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Exported database '{0}'!".format(selection))
        else:
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Failed to export database '{0}'!".format(selection))

        curses.panel.update_panels()
        self.stdscr.refresh()

        while 1:
            # Check for control movements
            c = self.stdscr.getch()
            if c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                del alert_win
                break
        return

    def import_select_screen(self):
        """Allows the user to enter a file to be imported and submitted to the server."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        first_y = 3

        menu_width = int(width * 0.33)
        win1, panel1 = self.make_panel(12, int(menu_width), 6, int((width / 2) - (menu_width / 2)), "Import SQL from a File")
        win1.addstr(first_y, 1, "Enter Absolute Path of File to Import from:")
        win1.addstr(first_y + 5, 1, "CTRL-H: Backspace")
        win1.addstr(first_y + 6, 1, "CTRL-G: Exit text entry window")
        win1.addstr(first_y + 7, 1, "ENTER: Submit")
        panel1.top()
        tmp_height,tmp_width = win1.getmaxyx()
        edit_win = curses.newwin(1, int(tmp_width - 5), int(6 + first_y + 2), int((width / 2) - (menu_width / 2) + 2))
        rect = curses.textpad.rectangle(win1, int(first_y + 1), 1, int(first_y + 3), int(tmp_width - 2))

        self.refresh_screen()

        text = curses.textpad.Textbox(edit_win).edit()
        del edit_win

        self.import_sql(text.rstrip())
        del win1
        return

    def import_sql(self, filename):
        """Imports a SQL file and submits it to the server."""

        try:
            f = open(filename, "r")
            data = f.read()
            f.close()
        except Exception as e:
            self.alert_window(str(e))
            return

        height, width = self.stdscr.getmaxyx()

        menu_width = int(width * 0.33)

        try:
            self.alert_window("Attempting Import!")
            self.db.execute(data)
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Imported SQL from '{0}'!".format(filename))
        except Exception as e:
            alert_win, panel1 = self.make_panel(9, menu_width, 6, (width // 2) - (menu_width // 2), "Failed to import SQL from '{0}'!".format(filename))

        curses.panel.update_panels()
        self.stdscr.refresh()

        while 1:
            # Check for control movements
            c = self.stdscr.getch()
            if c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                del alert_win
                break
        return

    def add_window(self, table_name, column_names):
        _, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.77)
        start_x = (width // 2) - (menu_width // 2)
        height = 5
        window_top_margin = 6
        table_win, panel1 = self.make_panel( \
                height+4, menu_width, window_top_margin, start_x, "Change Row:")
        column_width = (menu_width-2)//len(column_names)
        table_win.box()

        table_win.addstr(height,1, "\\t: move field")
        table_win.addstr(height+1,1, "Enter: change field")
        table_win.addstr(height+2,1, "s: save row")
        row = {}
        for idx, name in enumerate(column_names):
            table_win.addstr(1,idx*column_width,"| {}".format(name))
        table_win.addstr(2,1,'-' * (menu_width-2))
        for j,name in enumerate(column_names):
            table_win.addstr(3,j*column_width+1,"|")

        #set initial selection
        col_pos = 0
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        while 1:
            c = self.stdscr.getch()
            if c == ord('\t'):
                table_win.chgat(3, col_pos*column_width+2, column_width-1, curses.color_pair(0))
                col_pos = col_pos+1 if col_pos+1 < len(column_names) else 0
            elif c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                text = self.text_window(title='Type new value')
                table_win.refresh()
                self.refresh_screen()
                table_win.addstr(3,col_pos*column_width+2, ' ' * (column_width-1))
                table_win.addstr(3,col_pos*column_width+2, text)
                col_name = column_names[col_pos]
                row[col_name] = text
            elif c == ord('s'):
                self.db.add_row(table_name, row)
                del table_win
                del panel1
                return
            elif c == 27:
                del table_win
                del panel1
                return

            table_win.chgat(3, col_pos*column_width+2, column_width-1, curses.color_pair(1))
            table_win.refresh()

    def modify_window(self, table_name, column_names, row):
        _, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.77)
        start_x = (width // 2) - (menu_width // 2)
        height = 5
        window_top_margin = 6
        table_win, panel1 = self.make_panel( \
                height+4, menu_width, window_top_margin, start_x, "Change Row:")
        column_width = (menu_width-2)//len(column_names)
        table_win.box()

        table_win.addstr(height,1, "\\t: move field")
        table_win.addstr(height+1,1, "Enter: change field")
        table_win.addstr(height+2,1, "s: save row")
        for idx, name in enumerate(column_names):
            table_win.addstr(1,idx*column_width,"| {}".format(name))
        table_win.addstr(2,1,'-' * (menu_width-2))
        for j,name in enumerate(column_names):
            table_win.addstr(3,j*column_width+1,"| {}".format(row[name]))

        #set initial selection
        col_pos = 0
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        while 1:
            c = self.stdscr.getch()
            if c == ord('\t'):
                table_win.chgat(3, col_pos*column_width+2, column_width-1, curses.color_pair(0))
                col_pos = col_pos+1 if col_pos+1 < len(column_names) else 0
            elif c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                text = self.text_window(title='Type new value')
                table_win.refresh()
                self.refresh_screen()
                table_win.addstr(3,col_pos*column_width+2, ' ' * (column_width-1))
                table_win.addstr(3,col_pos*column_width+2, text)
                col_name = column_names[col_pos]
                row[col_name] = text
            elif c == ord('s'):
                try:
                    self.db.update_row(table_name, row)
                except Exception:
                    self.alert_window('This is not a valid value, please change it.')
                del table_win
                del panel1
                return
            elif c == 27:
                del table_win
                del panel1
                return

            table_win.chgat(3, col_pos*column_width+2, column_width-1, curses.color_pair(1))
            table_win.refresh()

    def alert_window(self,msg):
        """Creates a window useful for displaying error messages"""

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.5)
        alert_win, panel1 = self.make_panel(9, int(menu_width), 6, int((width / 2) - (menu_width / 2)), "")
        alert_win.box()

        half_menu = menu_width / 2
        alert_win.addstr(1, 1, msg)
        alert_win.addstr(2, 1, "Press ENTER to dismiss this message.")
        panel1.top()

        self.refresh_screen()
        alert_win.refresh()
        while 1:
            c = self.stdscr.getch()
            if c == curses.KEY_ENTER or c == self.ALT_KEY_ENTER:
                break
        del alert_win
        self.refresh_screen()

    def text_window(self,title='Enter Text Here:'):
        first_y = 3
        win_height = 6

        height, width = self.stdscr.getmaxyx()
        menu_width = int(width * 0.66)
        win1, panel1 = self.make_panel(9, menu_width, win_height, (width // 2) - (menu_width // 2), "Connect to Server:")
        win1.addstr(first_y, 1, title)
        panel1.top()
        tmp_height,tmp_width = win1.getmaxyx()
        edit_win = curses.newwin(win_height-3, tmp_width - 5, win_height + first_y + 2, (width // 2) - (menu_width // 2) + 2)
        self.refresh_screen()
        # fuck tmux: ITS CONTROL G to exit
        text = curses.textpad.Textbox(edit_win).edit().rstrip()
        del edit_win
        return text

    def refresh_screen(self):
        """Refreshes the main DBInterface screen to readjust proportions."""

        # Set variables
        height, width = self.stdscr.getmaxyx()
        self.stdscr.erase()

        # Print Title
        self.stdscr.addstr(1, 1, "{0}".format("### cliMyAdmin ###".center(width - 2, ' ')))

        # Controls Info
        self.stdscr.addstr(2, (width // 3) * 2, "{0}".format(
                "Controls: arrow keys (up/down), enter (select)"))
        self.stdscr.addstr(3, (width // 3) * 2, "{0}".format(
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
    parser = argparse.ArgumentParser(prog='climyadmin')
    parser.add_argument('-u', '--username', required=True, metavar='USER', help='username for accessing your database server')
    parser.add_argument('-p', '--password', required=True, metavar='PASS', help='password for accessing your database server')
    parser.add_argument('-s', '--server', default='localhost', metavar='HOST', help='hostname for your database server')
    parser.add_argument('-dbms', '--dbms', choices=['postgres', 'mysql'], \
            required=True, metavar='DBTYPE', help='dbms chooses your database')
    args = parser.parse_args()

    shm = DBInterface(args)
