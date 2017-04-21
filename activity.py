# Copyright (C) 2007, One Laptop Per Child
# -*- coding: utf-8 -*-
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from gettext import gettext as _

import os
import sys
import server
import logging

USE_GTK2 = False
try:
    from sugar3.graphics.toolbarbox import ToolbarBox, ToolbarButton
except ImportError:
    from sugar.graphics.toolbarbox import ToolbarBox, ToolbarButton
    USE_GTK2 = True

#from sugar.activity import registry
#activity_info = registry.get_registry().get_activity('org.laptop.WebActivity')

#sys.path.append(activity_info.path)
if os.path.exists('../Browse.activity'):
    sys.path.append('../Browse.activity')
elif os.path.exists('/usr/share/sugar/activities/Browse.activity'):
    sys.path.append('/usr/share/sugar/activities/Browse.activity')
else:
    print 'This activity need a Browser activity installed to run'

import webactivity

from searchtoolbar import SearchToolbar


# Activity class, extends WebActivity.
class WikipediaActivity(webactivity.WebActivity):
    def __init__(self, handle):

        logging.error("Starting server database: %s port: %s" %
                (self.confvars['path'], self.confvars['port']))

        os.chdir(os.environ['SUGAR_BUNDLE_PATH'])

        self.confvars['ip'] = '0.0.0.0'

        server.run_server(self.confvars)

        handle.uri = 'http://%s:%s%s' % (self.confvars['ip'],
                self.confvars['port'], self.confvars['home_page'])

        webactivity.WebActivity.__init__(self, handle)

        if USE_GTK2:
            # Use xpcom to set a RAM cache limit.  (Trac #7081.)
            from xpcom import components
            from xpcom.components import interfaces
            cls = components.classes['@mozilla.org/preferences-service;1']
            pref_service = cls.getService(interfaces.nsIPrefService)
            branch = pref_service.getBranch("browser.cache.memory.")
            branch.setIntPref("capacity", "5000")

            # Use xpcom to turn off "offline mode" detection, which disables
            # access to localhost for no good reason.  (Trac #6250.)
            ios_class = components.classes["@mozilla.org/network/io-service;1"]
            io_service = ios_class.getService(interfaces.nsIIOService2)
            io_service.manageOfflineStatus = False

        self.searchtoolbar = SearchToolbar(self)
        search_toolbar_button = ToolbarButton()
        search_toolbar_button.set_page(self.searchtoolbar)
        search_toolbar_button.props.icon_name = 'search-wiki'
        search_toolbar_button.props.label = _('Search')
        self.get_toolbar_box().toolbar.insert(search_toolbar_button, 1)
        search_toolbar_button.show()
        # Hide add-tabs button
        if hasattr(self._primary_toolbar, '_add_tab'):
            self._primary_toolbar._add_tab.hide()

        self.searchtoolbar.show()

    def _get_browser(self):
        if hasattr(self, '_browser'):
            # Browse < 109
            return self._browser
        else:
            return self._tabbed_view.props.current_browser

    def _go_home_button_cb(self, button):
        home_url = 'http://%s:%s%s' % (self.confvars['ip'],
                self.confvars['port'], self.confvars['home_page'])
        browser = self._get_browser()
        browser.load_uri(home_url)
