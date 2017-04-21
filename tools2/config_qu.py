#!/usr/bin/env python
# -*- coding: utf-8 -*-
# These configuration params are used in the process to create
# a new wikipedia activity

input_xml_file_name = './quwiki-20111228-pages-articles.xml'
favorites_file_name = 'favorites_qu.txt'
blacklist_file_name = './blacklist_qu.txt'

REDIRECT_TAGS = [u'#REDIRECT', u'#REDIRECCIÓN']

BLACKLISTED_NAMESPACES = ['WIKIPEDIA:', 'MEDIAWIKI:']

TEMPLATE_NAMESPACES = ['Plantilla:']

LINKS_NAMESPACES = [u'Categoría']

FILE_TAG = 'Rikcha:'

MAX_IMAGE_SIZE = 300

# This part should not be changed
import platform

system_id = "%s%s" % (platform.system().lower(),
                          platform.architecture()[0][0:2])
if platform.processor().startswith('arm'):
    system_id = platform.processor()
