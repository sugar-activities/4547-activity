# Copyright (C) 2007, One Laptop Per Child
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

try:
    from sugar3.graphics import iconentry
    # check first sugar3 because in os883 gi.repository is found but not sugar3
    from gi.repository import Gtk
except ImportError:
    import gtk as Gtk
    from sugar.graphics import iconentry


class SearchToolbar(Gtk.Toolbar):
    def __init__(self, activity):
        Gtk.Toolbar.__init__(self)

        self._activity = activity

        label = Gtk.Label(_('Search in the Wiki'))
        label_item = Gtk.ToolItem()
        label_item.add(label)
        label_item.show_all()
        self.insert(label_item, -1)

        self._search_url = 'http://' + activity.confvars['ip'] + ':' + \
                           str(activity.confvars['port']) + '/search?q=%s'

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(False)
        self.insert(separator, -1)
        separator.show()

        self._entry = iconentry.IconEntry()
        self._entry.add_clear_button()
        self._entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                       'entry-search')
        self._entry.connect('activate', self._entry_activate_cb)

        entry_item = Gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(self._entry)
        self._entry.show()

        self.insert(entry_item, -1)
        entry_item.show()

    def _entry_activate_cb(self, entry):

        browser = self._activity._get_browser()
        browser.load_uri(self._search_url % entry.props.text)
        browser.grab_focus()
