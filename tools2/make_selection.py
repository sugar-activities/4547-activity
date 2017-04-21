#!/usr/bin/env python
# -*- coding: utf-8 -*-

# take a list of pages
# select a level default = 1
# prepare a list of links in the pages from the original list
# create a file with the titles of all the selected pages
# create a file with the content of all the selected pages

import codecs
import re
from xml.sax import make_parser, handler
import os
import sys
from operator import itemgetter
import config
from wikitools_utils import normalize_title
from wikitools_utils import FileListReader, RedirectParser, RedirectsUsedWriter
from wikitools_utils import TemplatesCounter, TemplatesCounterWriter
from wikitools_utils import LinksFilter
from wikitools_utils import CountedTemplatesReader, normalize_title

try:
    from hashlib import md5
except ImportError:
    from md5 import md5


class PagesLinksFilter():

    def __init__(self, file_name, redirects_checker):
        """
        Read the list of pages from the .links file
        """
        self.pages = []
        input_links = codecs.open('%s.links' % file_name,
                encoding='utf-8', mode='r')
        line = input_links.readline()
        while line:
            words = line.split()
            if len(words) > 0:
                page = words[0]
                print "Adding page %s" % page
                redirected = redirects_checker.get_redirected(page)
                if redirected is not None:
                    page = redirected
                if not page in self.pages:
                    self.pages.append(page)
            line = input_links.readline()
        input_links.close()


class PagesProcessor(handler.ContentHandler):

    def __init__(self, file_name, selected_pages_list, pages_blacklist):
        handler.ContentHandler.__init__(self)
        self._page_counter = 0
        self._page = None
        self._output = codecs.open('%s.processed' % file_name,
                encoding='utf-8', mode='w')
        self._output_page_images = codecs.open('%s.page_images' % file_name,
                encoding='utf-8', mode='w')

        self.image_re = re.compile('\[\[%s.*?\]\]' % config.FILE_TAG)
        self._selected_pages_list = selected_pages_list
        self._pages_blacklist = pages_blacklist

    def startElement(self, name, attrs):
        if name == "page":
            self._page = {}
            self._page_counter += 1
        self._text = ""

    def characters(self, content):
        self._text = self._text + content

    def _register_page(self, register, title, content):
        register.write('\01\n')
        register.write('%s\n' % normalize_title(title))
        register.write('%d\n' % len(content))
        register.write('\02\n')
        register.write('%s\n' % content)
        register.write('\03\n')

    def _hashpath(self, name):
        name = name.replace(' ', '_')
        name = name[:1].upper() + name[1:]
        d = md5(name.encode('utf-8')).hexdigest()
        return "/".join([d[0], d[:2], name])

    def _get_url_image(self, image_wiki):
        """
        [[Archivo:Johann Sebastian Bach.jpg|thumb|200px|right|[[J. S. Bach]]
        """
        # remove [[ and ]]
        image_wiki = image_wiki[2:-2]
        parts = image_wiki.split('|')

        name = parts[0]
        name = name[len(config.FILE_TAG):]

        image_size = config.MAX_IMAGE_SIZE
        # check if there are a size defined
        for part in parts:
            # this image sizes are copied from server.py
            if part.strip() == 'thumb':
                image_size = 180
                break

            if part.find('px') > -1:
                try:
                    image_size = int(part[:part.find('px')])
                except:
                    pass

        hashed_name = unicode(self._hashpath(name))  # .encode('utf8')
        url = 'http://upload.wikimedia.org/wikipedia/commons/thumb/' \
            + hashed_name + ('/%dpx-' % image_size) + name.replace(' ', '_')
        # the svg files are requested as png
        if re.match(r'.*\.svg$', url, re.IGNORECASE):
            url = url + '.png'
        return url

    def get_images(self, title):
        # find images used in the pages
        images = self.image_re.findall(unicode(self._page))
        images_list = []
        for image in images:
            url = self._get_url_image(image)
            # only add one time by page
            if not url in images_list:
                images_list.append(url)

        if len(images_list) > 0:
            self._output_page_images.write('%s ' % title)
            for image in images_list:
                self._output_page_images.write('%s ' % image)
            self._output_page_images.write('\n')

    def endElement(self, name):
        if name == "title":
            self._title = self._text
        elif name == "text":
            self._page = self._text
        elif name == "page":

            for namespace in config.BLACKLISTED_NAMESPACES:
                if unicode(self._title).startswith(namespace):
                    return

            title = normalize_title(self._title)

            for namespace in config.TEMPLATE_NAMESPACES:
                if unicode(self._title).startswith(namespace):
                    self.get_images(title)
                    return

            for tag in config.REDIRECT_TAGS:
                if unicode(self._page).startswith(tag):
                    return

            if (title not in self._pages_blacklist) and \
                (title in self._selected_pages_list):
                print "%d Page '%s', length %d                   \r" % \
                        (self._page_counter,
                         title.encode('ascii', 'replace'), len(self._page)),
                # processed
                self._register_page(self._output, title, self._page)
                self.get_images(title)

        elif name == "mediawiki":
            self._output.close()
            self._output_page_images.close()
            print "Processed %d pages." % self._page_counter


class TemplatesLoader():

    def __init__(self, file_name, templates_used, select_all=False):
        _file = codecs.open('%s.templates' % file_name,
                                encoding='utf-8', mode='r')
        self._output = codecs.open('%s.processed' % file_name,
                encoding='utf-8', mode='a')
        line = _file.readline()
        while line:
            if len(line) == 2:
                if ord(line[0]) == 1:
                    title = _file.readline()
                    size = _file.readline()
                    separator = _file.readline()
                    finish = False
                    template_content = ''
                    while not finish:
                        line = _file.readline()
                        #print line
                        if len(line) == 2:
                            if ord(line[0]) == 3:
                                finish = True
                                break
                        template_content += line
                    template_namespace = title[:title.find(':')]
                    template_name = title[title.find(':') + 1:]
                    template_name = normalize_title(template_name)
                    #print "checking", template_name,

                    if select_all or template_name in templates_used.keys():
                        #print "Adding Template", template_name.encode('ascii', 'replace'), '\r',
                        title = template_namespace + ":" + template_name
                        self._register_page(title, template_content.strip())

            line = _file.readline()

    def _register_page(self, title, content):
        self._output.write('\01\n')
        self._output.write('%s\n' % normalize_title(title))
        self._output.write('%d\n' % len(content))
        self._output.write('\02\n')
        self._output.write('%s\n' % content)
        self._output.write('\03\n')


if __name__ == '__main__':

    select_all = False
    if len(sys.argv) > 1:
        for argn in range(1, len(sys.argv)):
            arg = sys.argv[argn]
            if arg == '--all':
                select_all = True
                print "Selecting all the pages"

    MAX_LEVELS = 1

    if not select_all:
        fav_reader = FileListReader(config.favorites_file_name)
        print "Loaded %d favorite pages" % len(fav_reader.list)

    if os.path.exists(config.blacklist_file_name):
        pages_blacklisted_reader = FileListReader(config.blacklist_file_name)
        pages_blacklist = pages_blacklisted_reader.list
        print "Loaded %d blacklisted pages" % len(pages_blacklist)
    else:
        pages_blacklist = []

    input_xml_file_name = config.input_xml_file_name

    print "Init redirects checker"
    redirect_checker = RedirectParser(input_xml_file_name)

    level = 1

    if not select_all:
        selected_pages_file_name = '%s.pages_selected-level-%d' % \
                        (input_xml_file_name, MAX_LEVELS)
    else:
        selected_pages_file_name = '%s.pages_selected' % input_xml_file_name

    if not os.path.exists(selected_pages_file_name):
        if not select_all:
            while level <= MAX_LEVELS:
                print "Processing links level %d" % level
                links_filter = LinksFilter(input_xml_file_name,
                        redirect_checker, fav_reader.list)
                fav_reader.list.extend(links_filter.links)
                level += 1

            print "Writing pages_selected-level-%d file" % MAX_LEVELS
            output_file = codecs.open(selected_pages_file_name,
                            encoding='utf-8', mode='w')
            for page  in fav_reader.list:
                output_file.write('%s\n' % page)
            output_file.close()
            selected_pages_list = fav_reader.list
        else:
            print "Processing links"
            links_filter = PagesLinksFilter(input_xml_file_name,
                redirect_checker)

            print "Writing pages_selected file %d pages" % \
                    len(links_filter.pages)
            output_file = codecs.open(selected_pages_file_name,
                         encoding='utf-8', mode='w')
            for page  in links_filter.pages:
                output_file.write('%s\n' % page)
            output_file.close()
            selected_pages_list = links_filter.pages

    else:
        print "Loading selected pages"
        pages_selected_reader = FileListReader(selected_pages_file_name)
        selected_pages_list = pages_selected_reader.list

    if not os.path.exists('%s.processed' % input_xml_file_name):
        print "Writing .processed file"
        parser = make_parser()
        parser.setContentHandler(PagesProcessor(input_xml_file_name,
                selected_pages_list, pages_blacklist))
        parser.parse(input_xml_file_name)

        # if there are a .templates_counted file should be removed
        # because we need recalculate it
        if os.path.exists('%s.templates_counted' % input_xml_file_name):
            os.remove('%s.templates_counted' % input_xml_file_name)

    templates_used_reader = None
    if not os.path.exists('%s.templates_counted' % input_xml_file_name):
        if select_all:
            templates_loader = TemplatesLoader(input_xml_file_name, [], True)
        else:
            print "Processing templates"
            templates_counter = TemplatesCounter(input_xml_file_name,
                    selected_pages_list, redirect_checker)

            print "Sorting counted templates"
            items = templates_counter.templates_to_counter.items()
            items.sort(key=itemgetter(1), reverse=True)

            print "Writing templates_counted file"
            _writer = TemplatesCounterWriter(input_xml_file_name, items)

            print "Loading templates used"
            templates_used_reader = CountedTemplatesReader(input_xml_file_name)
            print "Readed %d templates used" % len(
                    templates_used_reader.templates)

            print "Adding used templates to .processed file"
            templates_loader = TemplatesLoader(input_xml_file_name,
                    templates_used_reader.templates)

    if not os.path.exists('%s.redirects_used' % input_xml_file_name):
        if select_all:
            os.link('%s.redirects' % input_xml_file_name,
                    '%s.redirects_used' % input_xml_file_name)
        else:
            if templates_used_reader is None:
                print "Loading templates used"
                templates_used_reader = \
                        CountedTemplatesReader(input_xml_file_name)
                print "Readed %d templates used" % \
                        len(templates_used_reader.templates)

            redirects_used_writer = RedirectsUsedWriter(input_xml_file_name,
                    selected_pages_list, templates_used_reader.templates,
                    redirect_checker)
