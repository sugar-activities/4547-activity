#!/usr/bin/env python
# -*- coding: utf-8 -*-
# These configuration params are used in the process to create
# a new wikipedia activity

input_xml_file_name = './frwiki-20111231-pages-articles.xml'
favorites_file_name = './favorites_fr.txt'
blacklist_file_name = './blacklist_fr.txt'

REDIRECT_TAGS = [u'#REDIRECT']

BLACKLISTED_NAMESPACES = [u'WIKIPÉDIA:', 'MEDIAWIKI:']

TEMPLATE_NAMESPACES = [u'Modèle:']

LINKS_NAMESPACES = [u'Catégorie']

FILE_TAG = 'Fichier:'

MAX_IMAGE_SIZE = 300

# This part should not be changed
import platform

system_id = "%s%s" % (platform.system().lower(),
                          platform.architecture()[0][0:2])
if platform.processor().startswith('arm'):
    system_id = platform.processor()
