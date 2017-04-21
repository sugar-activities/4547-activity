#!/usr/bin/env python
#
# Copyright (C) 2011, One Laptop Per Child
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
#
import sys
import os
import shutil
import zipfile
from fnmatch import fnmatch
from sugar.activity import bundlebuilder

INCLUDE_DIRS = ['activity', 'binarylibs', 'icons', 'locale', 'bin',
                'mwlib', 'po', 'seek-bzip2', 'static', 'tools2']
IGNORE_FILES = ['.gitignore', 'MANIFEST', '*.pyc', '*~', '*.bak', 'pseudo.po']


class WikiXOPackager(bundlebuilder.XOPackager):

    def __init__(self, builder, data_file):
        bundlebuilder.XOPackager.__init__(self, builder)
        self.data_file = data_file

    def package(self):
        bundle_zip = zipfile.ZipFile(self.package_path, 'w',
                                     zipfile.ZIP_DEFLATED)

        for f in self.list_files(self.config.source_dir, True):
            if os.path.exists(os.path.join(self.config.source_dir, f)):
                bundle_zip.write(os.path.join(self.config.source_dir, f),
                                 os.path.join(self.config.bundle_root_dir, f))

        if self.data_file is not None:
            # Add the data files
            needed_sufix = ['.processed.bz2', '.processed.bz2t']
            for sufix in needed_sufix:
                data_file = self.data_file + sufix
                print "Add %s" % data_file
                bundle_zip.write(data_file,
                                 os.path.join(self.config.bundle_root_dir,
                                              data_file))

            data_path = os.path.dirname(self.data_file)

            index_file = os.path.join(data_path, 'search.db')
            print "Add %s" % index_file
            bundle_zip.write(index_file,
                         os.path.join(self.config.bundle_root_dir, index_file))

            # add images
            images_path = os.path.join(data_path, 'images')
            if os.path.exists(images_path):
                print "Adding images"
                for f in self.list_files(images_path):
                    bundle_zip.write(os.path.join(images_path, f),
                        os.path.join(self.config.bundle_root_dir,
                            images_path, f))

        bundle_zip.close()

    def list_files(self, base_dir, filter_directories=False):
        if filter_directories:
            include_dirs = INCLUDE_DIRS
        else:
            include_dirs = None

        ignore_files = IGNORE_FILES
        result = []

        base_dir = os.path.abspath(base_dir)

        for root, dirs, files in os.walk(base_dir):

            if ignore_files:
                for pattern in ignore_files:
                    files = [f for f in files if not fnmatch(f, pattern)]

            rel_path = root[len(base_dir) + 1:]
            for f in files:
                result.append(os.path.join(rel_path, f))

            if root == base_dir:
                n = 0
                while n < len(dirs):
                    directory = dirs[n]
                    if include_dirs is not None and \
                        not directory in include_dirs:
                        print "** Ignoring directory", directory
                        dirs.remove(directory)
                    else:
                        n = n + 1
        return result


if __name__ == '__main__':

    if len(sys.argv) < 2:
        data_file = None
        lang = 'base'
    else:
        data_file = sys.argv[1]

        lang = data_file[:data_file.find('/')]

    print "Lang:", lang
    # copy activty/activity.info.lang as activty/activity.info
    f = 'activity/activity.info.' + lang
    if os.path.exists(f):
        shutil.copyfile(f, 'activity/activity.info')

    config = bundlebuilder.Config()
    packager = WikiXOPackager(bundlebuilder.Builder(config), data_file)
    packager.package()
