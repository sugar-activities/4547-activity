#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Create a list of pages with a nuber of how many links are directed to them.

from urllib import FancyURLopener
import os
import time
import sys
import shutil
import magic

import config
from wikitools_utils import LinksFilter, RedirectParser


class FileListReader():

    def __init__(self, file_name):
        _file = open(file_name, mode='r')
        self.list = []
        line = _file.readline()
        while line:
            self.list.append(line.strip())
            line = _file.readline()


class CustomUrlOpener(FancyURLopener):

    version = 'Mozilla/5.0 (X11; Linux x86_64; rv:9.0) Gecko/20100101 ' + \
            'Firefox/9.0'


class ImagesDownloader:

    def __init__(self, file_name, pages_selected, base_dir, cache_dir, lang):
        self.base_dir = base_dir
        self.cache_dir = cache_dir
        self.mime_checker = magic.open(magic.MAGIC_MIME)
        self.mime_checker.load()
        input_links = open('%s.page_images' % file_name, mode='r')
        line = input_links.readline()
        while line:
            words = line.split()
            page = words[0]
            if pages_selected is None or (page in pages_selected):
                print "Processing page %s \r" % page,
                for n in range(1, len(words)):
                    image_url = words[n]
                    self.download_image(image_url, lang)

            line = input_links.readline()
        input_links.close()

    def download_image(self, url, lang, dest=None):
        # avoid downloading .ogg files
        if url.lower().endswith('.ogg'):
            return
        overwrite = True
        if dest is None:
            overwrite = False
            sliced_url = url.split('thumb/')
            image_part = sliced_url[1]
            dirs = image_part.split('/')
            destdir = "%s/%s/%s" % (self.base_dir, dirs[0], dirs[1])
            image_name = dirs[len(dirs) - 1]
            try:
                os.makedirs(destdir)
            except:
                pass  # This just means that destdir already exists
            dest = "%s/%s" % (destdir, image_name)
        if not os.path.exists(dest) or overwrite:
            if self.cache_dir is not None and not overwrite:
                # Verify if the file is in the cahce_dir
                cache_file = "%s/%s/%s/%s" % (self.cache_dir, dirs[0], dirs[1],
                        image_name)
                if os.path.exists(cache_file):
                    shutil.copyfile(cache_file, dest)
                    return
            print "Downloading %s" % url
            for intent in range(3):
                try:
                    opener = CustomUrlOpener()
                    opener.retrieve(url, dest)
                    break
                except:
                    print "Trying again, waiting 10 seconds"
                    time.sleep(10)

        # Verify the mime type
        # wikipedia return a html file with a error, if the size requested
        # is small than the real image
        # then if the file is a html we need request the unescaled image
        if url.find('/thumb/')> -1:
            mime_type = str(self.mime_checker.file(dest))
            if mime_type.find('text') > -1:
                url_ori = url
                url = url[0:url.rfind('/')]
                url = url.replace('thumb/', '')
                print 'Wrong mime type, redownloading %s to %s' % (url, dest)
                self.download_image(url, lang, dest)
                mime_type = str(self.mime_checker.file(dest))
                if mime_type.find('text') > -1:
                    # try downloading from the lang instead of commons
                    if url_ori.find('commons') > -1:
                        url_lang = url_ori.replace('commons', lang)
			self.download_image(url_lang, lang, dest)

                mime_type = str(self.mime_checker.file(dest))
                if mime_type.find('text') > -1:
                    # if the file downloaded is html/text remove it
                    os.remove(dest)


downlad_all = False
cache_dir = None
max_level = 0
if len(sys.argv) > 1:
    for argn in range(1, len(sys.argv)):
        arg = sys.argv[argn]
        if arg == '--all':
            downlad_all = True
            print "Downloading all images"
        if arg.startswith('--cache_dir='):
            cache_dir = arg[arg.find('=') + 1:]
            print "Using cache directory", cache_dir
        if arg.startswith('--max_level='):
            max_level = int(arg[arg.find('=') + 1:])
            print "Using max_level ", max_level

input_xml_file_name = config.input_xml_file_name

# TODO: take the lang from the first two letters
# in the xml file, but this is not the best, because does not works
# ever (example simplewiki)
lang = input_xml_file_name
if lang.find('/'):
    lang = lang[lang.find('/') + 1:]
lang = lang[:2]

if input_xml_file_name.find('simplewiki') > -1:
    lang = 'en'

print 'Lang: %s' % lang

selected_pages = None
if not downlad_all:
    print "Loading selected pages"
    favorites_reader = FileListReader(config.favorites_file_name)
    selected_pages = favorites_reader.list

    print "Init redirects checker"
    redirect_checker = RedirectParser(input_xml_file_name)

    level = 1
    while level <= max_level:
        print "Processing links level %d" % level
        links_filter = LinksFilter(input_xml_file_name,
                redirect_checker, selected_pages)
        selected_pages.extend(links_filter.links)
        level += 1

print "Downloading images from %d pages" % len(selected_pages)

print "Downloading images"
templates_counter = ImagesDownloader(input_xml_file_name,
        selected_pages, "./images", cache_dir, lang)
