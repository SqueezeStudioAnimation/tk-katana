# coding: utf-8
#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
import os
import sys
import unicodedata

from Katana import QtGui, QtCore


class MenuGenerator(object):
    """
    A Katana specific menu generator.
    """

    def __init__(self, engine, menu_name):
        """
        Initializes a new menu generator.

        :param engine: The currently-running engine.
        :type engine: :class:`tank.platform.Engine`
        :param menu_name: The name of the menu to be created.
        """
        self._engine = engine
        self._menu_name = menu_name
        self.root_menu = None

    @property
    def engine(self):
        """The currently-running engine."""
        return self._engine

    @property
    def menu_name(self):
        """The name of the menu to be generated."""
        return self._menu_name

    def create_menu(self):
        """
        Create the Shotgun Menu.
        """
        # Get the shotgun menu
        self.root_menu = self.get_or_create_root_menu(self.menu_name)

        # 'surfacing, Assets chair' menu
        menu_handle = self.root_menu

        # now add the context item on top of the main menu
        self._context_menu = self._add_context_menu(menu_handle)
        menu_handle.addSeparator()

        # now enumerate all items and create menu objects for them
        menu_items = []
        for (cmd_name, cmd_details) in self.engine.commands.items():
             menu_items.append(AppCommand(cmd_name, cmd_details))

        # sort list of commands in name order
        menu_items.sort(key=lambda x: x.name)

        # now add favourites
        for fav in self.engine.get_setting("menu_favourites"):
            app_instance_name = fav["app_instance"]
            menu_name = fav["name"]

            # scan through all menu items
            for cmd in menu_items:
                 if cmd.get_app_instance_name() == app_instance_name and cmd.name == menu_name:
                     # found our match!
                     cmd.add_command_to_menu(menu_handle)
                     # mark as a favourite item
                     cmd.favourite = True

        menu_handle.addSeparator()

        # now go through all of the menu items.
        # separate them out into various sections
        commands_by_app = {}

        for cmd in menu_items:
            if cmd.get_type() == "context_menu":
                # context menu!
                cmd.add_command_to_menu(self._context_menu)

            else:
                # normal menu
                app_name = cmd.get_app_name()
                if app_name is None:
                    # un-parented app
                    app_name = "Other Items"
                if not app_name in commands_by_app:
                    commands_by_app[app_name] = []
                commands_by_app[app_name].append(cmd)

        # now add all apps to main menu
        self._add_app_menu(commands_by_app, menu_handle)

    @classmethod
    def get_or_create_root_menu(cls, menu_name):
        """
        Attempts to find an existing menu of the specified title. If it can't be
        found, it creates one.
        """
        # Get the "main menu" (the bar of menus)
        main_menu = cls.__get_katana_main_menu()
        if not main_menu:
            return

        # Attempt to find existing menu
        for menu in main_menu.children():
            if type(menu).__name__ == "QMenu" and menu.title() == menu_name:
                return menu

        # Otherwise, create a new menu
        menu = QtGui.QMenu(menu_name, main_menu)
        main_menu.addMenu(menu)
        return menu

    @classmethod
    def __get_katana_main_menu(cls):
        layoutsMenus = [x for x in QtGui.qApp.topLevelWidgets() if type(x).__name__ == 'LayoutsMenu']
        if len(layoutsMenus) != 1:
            return

        mainMenu = layoutsMenus[0].parent()
        return mainMenu

    def destroy_menu(self):
        """
        Destroys the Shotgun menu.
        """
        if self.root_menu is not None:
            self.root_menu.clear()

    ##########################################################################################
    # context menu and UI

    def _add_context_menu(self, menu_handle):
        """
        Adds a context menu which displays the current context.
        """
        ctx = self.engine.context
        ctx_name = str(ctx)

        # create the menu object
        ctx_menu = menu_handle.addMenu(ctx_name)

        action = QtGui.QAction('Jump to Shotgun', self.root_menu, triggered=self._jump_to_sg)
        ctx_menu.addAction(action)

        action = QtGui.QAction('Jump to File System', self.root_menu, triggered=self._jump_to_fs)
        ctx_menu.addAction(action)

        ctx_menu.addSeparator()

        return ctx_menu

    def _jump_to_sg(self):
        """
        Jump to Shotgun, launch web browser.
        """
        url = self.engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _jump_to_fs(self):
        """
        Jump from context to FS.
        """
        # launch one window for each location on disk
        paths = self.engine.context.filesystem_locations
        for disk_location in paths:

            # get the setting
            system = sys.platform

            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)

            exit_code = os.system(cmd)
            if exit_code != 0:
                self.engine.log_error("Failed to launch '%s'!" % cmd)

    ##########################################################################################
    # app menus

    def _add_app_menu(self, commands_by_app, menu_handle):
        """
        Add all apps to the main menu, process them one by one.
        """
        for app_name in sorted(commands_by_app.keys()):

            if len(commands_by_app[app_name]) > 1:
                # more than one menu entry fort his app
                # make a sub menu and put all items in the sub menu
                app_menu = menu_handle.addMenu(app_name)

                # get the list of menu cmds for this app
                cmds = commands_by_app[app_name]
                # make sure it is in alphabetical order
                cmds.sort(key=lambda x: x.name)

                for cmd in cmds:
                    cmd.add_command_to_menu(app_menu)

            else:
                # this app only has a single entry.
                # display that on the menu
                # todo: Should this be labelled with the name of the app
                # or the name of the menu item? Not sure.
                cmd_obj = commands_by_app[app_name][0]
                if not cmd_obj.favourite:
                    # skip favourites since they are alreay on the menu
                    cmd_obj.add_command_to_menu(menu_handle)


class AppCommand(object):
    """
    Wraps around a single command that you get from engine.commands
    """

    def __init__(self, name, command_dict):
        self.name = name
        self.properties = command_dict["properties"]
        self.callback = command_dict["callback"]
        self.favourite = False

    def get_app_name(self):
        """
        Returns the name of the app that this command belongs to
        """
        if "app" in self.properties:
            return self.properties["app"].display_name
        return None

    def get_app_instance_name(self):
        """
        Returns the name of the app instance, as defined in the environment.
        Returns None if not found.
        """
        if "app" not in self.properties:
            return None

        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                # found our app!
                return app_instance_name

        return None

    def get_documentation_url_str(self):
        """
        Returns the documentation as a str.
        """
        if "app" in self.properties:
            app = self.properties["app"]
            doc_url = app.documentation_url
            # deal with nuke's inability to handle unicode. #fail
            if doc_url.__class__ == unicode:
                doc_url = unicodedata.normalize('NFKD', doc_url).encode('ascii', 'ignore')
            return doc_url

        return None

    def get_type(self):
        """
        Returns the command type (node, custom_pane or default).
        """
        return self.properties.get("type", "default")

    def do_add_command(self, menu, name, cmd, hot_key=None, icon=None):
        # TODO add hot key

        # From the PyQt documentation:
        # PySide.QtGui.QAction.triggered([checked = false])
        # Parameters:    checked – PySide.QtCore.bool
        # If your callback signature is cmd(*args), the signal sent will have an arg, False, which corresponds
        # to the checked state of the menu item. But if it's cmd(), then it won't.
        # since the apps registered commands are defined as wrappers, callback_wrapper(*args, **kwargs)
        #  (see /rdo/rodeo/repositories/tank/studio/install/core/python/tank/platform/engine.py,
        # register_command function), they will pass the False argument to the callbacks registered by the
        # apps, for example for tk-multi-contextSwitcher:
        # menu_callback = lambda : app_payload.contextSwitcher.show_dialog(self)
        # this will fail since the callback does not take any arguments.
        # By "wrapping the wrapper" with this lambda, the function attached to triggered has no args and
        # everything works.
        cb = lambda: cmd()
        if hot_key:
            action = QtGui.QAction(name, menu, triggered=cb, icon=icon)
        else:
            if icon:
                new_icon = QtGui.QIcon(icon)
                action = QtGui.QAction(name, menu, triggered=cb, icon=new_icon)
            else:
                action = QtGui.QAction(name, menu, triggered=cb)
        menu.addAction(action)

    def add_command_to_menu(self, menu):
        """
        Adds an app command to the menu.
        """
        # std shotgun menu
        icon = self.properties.get("icon")
        hotkey = self.properties.get("hotkey")
        self.do_add_command(menu,self.name, self.callback, hot_key=hotkey, icon=icon)