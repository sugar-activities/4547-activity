#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007, One Laptop Per Child
#
# License: GPLv2
#
# Usage:
# ./tools2/expandtemplates.py directory 2>expand.log
# Ex:
# ./tools2/expandtemplates.py es_lat

import sys
reload(sys)
# Important! We'll be using stdout and stderr with
# UTF-8 chars. Without this, errors galore.
sys.setdefaultencoding('utf-8')

sys.path.append('.')

import os
import re
import codecs
from server import WPWikiDB
from wikitools_utils import FileListReader

START_HEADING = chr(1)
START_TEXT = chr(2)
END_TEXT = chr(3)

import config

# __main__

only_page = None
start_at = None
stdout = False

if len(sys.argv) > 1:
    directory = sys.argv[1]

    for argn in range(1, len(sys.argv)):
        arg = sys.argv[argn]
        if arg.startswith('--only='):
            only_page = arg[len('--only='):]
            print "Processing only article '%s'" % only_page
        if arg.startswith('--start_at='):
            start_at = arg[len('--start_at='):]
            print "Starting to process at article '%s'" % start_at
        if arg == '--stdout':
            stdout = True
            print "Writing output to stdout"

else:
    print "Use expandtemplates.py directory"
    exit()


xml_file_name = config.input_xml_file_name
if xml_file_name.find('/') > -1:
    xml_file_name = xml_file_name[xml_file_name.find('/') + 1:]
path = os.path.join(directory, xml_file_name)

articles_list = []
if only_page is not None:
    articles_list = [unicode(only_page)]
else:
    if os.path.exists('%s.pages_selected-level-1' % path):
        articles_reader = FileListReader('%s.pages_selected-level-1' % path)
    else:
        articles_reader = FileListReader('%s.pages_selected' % path)

    articles_list = articles_reader.list
    if start_at is not None:
        filtered_list = []
        found = False
        for title in articles_list:
            if title == start_at:
                found = True
            if found:
                filtered_list.append(title)
        articles_list = filtered_list

lang = os.path.basename(path)[0:2]

templateprefix = config.TEMPLATE_NAMESPACES[0]

# load blacklist only once
templateblacklist = set()
templateblacklistpath = os.path.join(os.path.dirname(path),
                                     'template_blacklist')
if os.path.exists(templateblacklistpath):
    with open(templateblacklistpath, 'r') as f:
        for line in f.readlines():
            templateblacklist.add(line.rstrip().decode('utf8'))

wikidb = WPWikiDB(path, lang, templateprefix, templateblacklist)
rx = re.compile('(' + templateprefix + '|Wikipedia:)')

if not stdout:
    file_mode = 'w'
    if os.path.exists('%s.processed_expanded' % path):
        file_mode = 'a'

    _output = codecs.open('%s.processed_expanded' % path,
            encoding='utf-8', mode=file_mode)
else:
    _output = sys.stdout

for title in articles_list:
    if title.find('#') > -1:
        if title.find('#') == 0:
            continue
        else:
            title = title[:title.find('#')]

    if rx.match(title):
        sys.stderr.write('SKIPPING: ' + title + "\n")
        continue

    sys.stderr.write('PROCESSING: ' + title + "\n")

    article_text = wikidb.getExpandedArticle(title)
    if article_text == None:
        sys.stderr.write('ERROR - SKIPPING: ' + title + "\n")
        continue

    _output.write(START_HEADING + '\n')
    _output.write(title + '\n')
    # in Python 2.x, len() over a unicode string
    # gives us the bytecount. Not compat w Python 3.
    _output.write("%s\n" % len(article_text))
    _output.write(START_TEXT + '\n')
    _output.write(article_text + '\n')
    _output.write(END_TEXT + '\n')

_output.close()
