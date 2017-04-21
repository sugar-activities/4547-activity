#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Test to use sax to parse wikimedia xml files

from xml.sax import make_parser, handler
import codecs
import re
import os
import sys

import config


def normalize_title(title):
    return title.strip().replace(' ', '_').capitalize()


class WikimediaXmlPagesProcessor(handler.ContentHandler):

    def __init__(self, file_name):
        handler.ContentHandler.__init__(self)
        self._page_counter = 0
        self._page = None
        self._parsing_element = None
        self._output_links = codecs.open('%s.interwiki_links' % file_name,
                encoding='utf-8', mode='w')
        self._output_links_nm = codecs.open('%s.links_namespaces' % file_name,
                encoding='utf-8', mode='w')
        self.link_re = re.compile('\[\[.*?\]\]')
        self.namespaces = []

    def startElement(self, name, attrs):
        if name == "page":
            self._page = {}
            self._page_counter += 1
        self._text = ""
        self._parsing_element = name

    def characters(self, content):
        if self._parsing_element == 'text':
            if self._text == '':
                self._first_line = content.lstrip().upper()
        if self._parsing_element in ('title', 'text'):
            self._text = self._text + content

    def endElement(self, name):
        if name == "title":
            self._title = self._text
        elif name == "text":
            self._page = self._text
        elif name == "page":

            title = normalize_title(self._title)
            print "Page %d '%s', length %d                   \r" % \
                    (self._page_counter, title, len(self._page)),

            for namespace in config.BLACKLISTED_NAMESPACES:
                if unicode(self._title.upper()).startswith(namespace):
                    return

            is_redirect = False

            for tag in config.REDIRECT_TAGS:
                if self._first_line.startswith(tag):
                    is_redirect = True
                    break

            if not is_redirect:

                # links
                links = self.link_re.findall(unicode(self._page))
                self._output_links.write('%s ' % title)
                for link in links:
                    # remove '[[' and ']]'
                    link = link[2:-2]
                    # Check if have a valid namespace
                    colon_position = link.find(':')
                    interwiki = False
                    if colon_position > -1:
                        namespace = link[:colon_position]
                        interwiki = not namespace in config.LINKS_NAMESPACES
                        if namespace not in self.namespaces:
                            self.namespaces.append(namespace)
                    if interwiki:
                        # if there are a pipe remove the right side
                        pipe_position = link.find('|')
                        if pipe_position > -1:
                            link = link[:pipe_position]
                        link = normalize_title(link)
                        self._output_links.write('%s ' % link)
                self._output_links.write('\n')


        elif name == "mediawiki":
            self._output_links.close()
            # write namespaces
            for namespace in self.namespaces:
                self._output_links_nm.writeln(namespace)
            self._output_links_nm.close()

            print "Processed %d pages." % self._page_counter

# the big data file is in another disk, no more space
input_xml_file_name = '/run/media/gonzalo/TOSHIBA EXT/gonzalo/sugar-devel/honey/wikipedia/wikiserver/en/enwiki-20111201-pages-articles.xml'
parser = make_parser()
parser.setContentHandler(
    WikimediaXmlPagesProcessor('./enwiki-20111201-pages-articles.xml'))
parser.parse(input_xml_file_name)
