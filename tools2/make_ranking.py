#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Create a list of pages with a nuber of how many links are directed to them.

import codecs
import re
import os
from operator import itemgetter
from wikitools_utils import RedirectParser, FileListReader
import config

class LinksCounter:

    def __init__(self, file_name, redirects, selected_pages): 
        self.links_to_counter = {}
        input_links  = codecs.open('%s.links' % file_name,
                encoding='utf-8', mode='r')
        line = input_links.readline()
        while line:
            words = line.split()
            if len(words) > 0:
                page = words[0]
                if page in selected_pages:
                    print "Processing page %s \r" % page,
                    for n in range(1, len(words) - 1):
                        link = words[n]
                        # check if is a redirect
                        try:
                            link = redirects[link]
                        except:
                            pass
                        if link in selected_pages:
                            try:
                                self.links_to_counter[link] += 1
                            except:                                
                                self.links_to_counter[link] = 0
            line = input_links.readline()
        input_links.close()


input_xml_file_name = config.input_xml_file_name
print "Loading redirects"
redirect_parser = RedirectParser(input_xml_file_name)
print "Processed %d redirects" % len(redirect_parser.redirects)

print "Loading selected pages"
if os.path.exists('%s.pages_selected-level-1' % input_xml_file_name):
    selected_pages_reader = FileListReader('%s.pages_selected-level-1' %
                                           input_xml_file_name)
else:
    selected_pages_reader = FileListReader('%s.pages_selected' %
                                           input_xml_file_name)

print "Processing links"
links_counter = LinksCounter(input_xml_file_name, redirect_parser.redirects,
        selected_pages_reader.list)

print "Sorting counted links"
items = links_counter.links_to_counter.items()
items.sort(key = itemgetter(1), reverse=True)

print "Writing links_counted file"
output_file = codecs.open('%s.links_counted' % input_xml_file_name,
                encoding='utf-8', mode='w')
for n  in range(len(items)):
    output_file.write('%s %d\n' % (items[n][0], items[n][1]))
output_file.close()
