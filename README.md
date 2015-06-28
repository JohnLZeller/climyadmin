# cliMyAdmin
This project is a CLI Python Curses version of a program similar to phpMyAdmin. The purpose is to interface with and control a MySQL server, at a very basic level.

## Overview of Operation
Upon startup, the DBInterface class is instantiated, which then initializes our Python Curses screen and some class variables to use throughout operation. Next, the main screen is setup with title and control information, before giving control to the Main Menu function. From here, the main menu panel is initialized and drops into a loop looking for key presses. As selections are made, new functions will be called in a sort of state machine configuration, ensuring that the current panel has the active key press loop.

## Moving Forward
The operation of the program should be a chain of sorts, beginning with the main menu. As each panel is added, it creates a sort of stack. When ESC is pressed, it'll close down the current panel, and return, bringing operation back to the previous panel.

## To Dos
* Make ESC either bring up a new main_menu, or close all panels except for the main_menu.