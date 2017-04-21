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
import StringIO

try:
    from hashlib import md5
except ImportError:
    from md5 import md5


def normalize_title(title):
    return title.strip().replace(' ', '_').capitalize()


class FileListReader():

    def __init__(self, file_name):
        _file = codecs.open(file_name,
                                encoding='utf-8', mode='r')
        self.list = []
        line = _file.readline()
        while line:
            self.list.append(normalize_title(line))
            line = _file.readline()


class RedirectParser:

    def __init__(self, file_name, postfix='redirects'):
        self.link_re = re.compile('\[\[.*?\]\]')
        # Load redirects
        input_redirects = codecs.open('%s.%s' % (file_name, postfix),
                encoding='utf-8', mode='r')

        self.redirects = {}
        self.reversed_index = {}
        count = 0
        for line in input_redirects.readlines():
            links = links = self.link_re.findall(unicode(line))
            if len(links) == 2:
                origin = links[0][2:-2]
                destination = links[1][2:-2]
                self.redirects[normalize_title(origin)] = \
                        normalize_title(destination)
                # add to the reversed index
                if destination in self.reversed_index:
                    self.reversed_index[destination].append(origin)
                else:
                    self.reversed_index[destination] = [origin]

            count += 1
            #print "Processing %s" % normalize_title(origin)
        input_redirects.close()

    def get_redirected(self, article_title):
        try:
            article_title = article_title.capitalize()
            redirect = self.redirects[article_title]
        except:
            redirect = None
        return redirect


class PagesLinksFilter():

    def __init__(self, file_name, redirects_checker, select_all=False):
        """
        Read the list of pages from the .links file
        If check is False, add all the pages, without check
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
                if select_all:
                    self.pages.append(page)
                else:
                    redirected = redirects_checker.get_redirected(page)
                    if redirected is not None:
                        page = redirected
                    self.pages.append(page)
            line = input_links.readline()
        input_links.close()


class LinksFilter():

    def __init__(self, file_name, redirects_checker, favorites):
        self.links = []
        input_links = codecs.open('%s.links' % file_name,
                encoding='utf-8', mode='r')
        line = input_links.readline()
        while line:
            words = line.split()
            if len(words) > 0:
                page = words[0]
                #print "Processing page %s \r" % page,
                if page in favorites:
                    print "Adding page %s" % page
                    for n in range(1, len(words) - 1):
                        link = words[n]
                        link = normalize_title(link)

                        if link.find('#') > -1:
                            # don't count links in the same page
                            if link.find('#') == 0:
                                continue
                            else:
                                # use only the article part of the link
                                link = link[:link.find('#')]

                        # check if is a redirect
                        redirected = redirects_checker.get_redirected(link)
                        if redirected is not None:
                            link = redirected

                        if not link in self.links and \
                            not link in favorites:
                            self.links.append(link)
            line = input_links.readline()
        input_links.close()


class PagesProcessorWiktionary(handler.ContentHandler):

    def __init__(self, file_name):
        handler.ContentHandler.__init__(self)
        self._page_counter = 0
        self._page = None
        self._base_file_name = file_name
        self._output_files = {}
        self._title_files = {}
        self._output_page_images = codecs.open('%s.page_images' % file_name,
                encoding='utf-8', mode='w')

        self.image_re = re.compile('\[\[%s.*?\]\]' % config.FILE_TAG)
        self.template_re = re.compile('{{.*?}}')
        self.lang_re = re.compile('==.*?==')

    def startElement(self, name, attrs):
        if name == "page":
            self._page = {}
            self._page_counter += 1
        self._text = ""

    def characters(self, content):
        self._text = self._text + content

    def _register_page(self, title, content, language):
        if language is not None:
            language = language.replace(' ', '_')
            language = language.replace('/', '')
        else:
            language = 'UNDEFINED'
        if language in self._output_files.keys():
            register = self._output_files[language]
        else:
            register = codecs.open('%s.processed_%s' % \
                    (self._base_file_name, language), encoding='utf-8',
                    mode='w')
            self._output_files[language] = register

        register.write('\01\n')
        register.write('%s\n' % normalize_title(title))
        register.write('%d\n' % len(content))
        register.write('\02\n')
        register.write('%s\n' % content)
        register.write('\03\n')

    def _register_title(self, title, language):
        if language is not None:
            language = language.replace(' ', '_')
            language = language.replace('/', '')
        else:
            language = 'UNDEFINED'
        if language in self._title_files.keys():
            register = self._title_files[language]
        else:
            register = codecs.open('%s.title_%s' % \
                    (self._base_file_name, language),
                    encoding='utf-8', mode='w')
            self._title_files[language] = register
        register.write('%s\n' % normalize_title(title))

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

            print "%d Page '%s', length %d                   \r" % \
                    (self._page_counter, title, len(self._page)),
            # processed
            content = StringIO.StringIO(self._page)
            line = content.readline()
            language = None
            count = 0
            while language is None and count < 5:
                found = self.lang_re.search(line)
                if found is not None:
                    language = found.group()
                    language = language[2:-2]
                count = count + 1

            self._register_page(title, self._page, language)
            self._register_title(title, language)
            self.get_images(title)

        elif name == "mediawiki":
            self._output.close()
            self._output_page_images.close()
            print "Processed %d pages." % self._page_counter


class TemplatesCounter:

    def __init__(self, file_name, pages_selected, redirect_checker):
        self.templates_to_counter = {}
        input_links = codecs.open('%s.page_templates' % file_name,
                encoding='utf-8', mode='r')
        line = input_links.readline()
        while line:
            words = line.split()
            page = words[0]
            if page in pages_selected:
                print "Processing page %s \r" % page,
                for n in range(1, len(words) - 1):
                    template = words[n]
                    try:
                        self.templates_to_counter[template] = \
                                self.templates_to_counter[template] + 1
                    except:
                        self.templates_to_counter[template] = 1
            line = input_links.readline()
        input_links.close()

        # Verify redirects
        print "Verifying redirects"
        for template in self.templates_to_counter.keys():
            redirected = redirect_checker.get_redirected(template)
            if redirected is not None:
                if redirected in self.templates_to_counter:
                    self.templates_to_counter[redirected] = \
                        self.templates_to_counter[redirected] + \
                        self.templates_to_counter[template]
                    self.templates_to_counter[template] = 0
                else:
                    self.templates_to_counter[redirected] = \
                        self.templates_to_counter[template]
                    self.templates_to_counter[template] = 0


class CountedTemplatesReader():

    def __init__(self, file_name):
        _file = codecs.open('%s.templates_counted' % file_name,
                                encoding='utf-8', mode='r')
        self.templates = {}
        line = _file.readline()
        while line:
            words = line.split()
            template_name = words[0]
            cant_used = int(words[1])
            self.templates[normalize_title(template_name)] = \
                    {'cant': cant_used}
            line = _file.readline()


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
                        #print "Adding", template_name,
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


class RedirectsUsedWriter():

    def __init__(self, file_name, selected_pages_list, templates_used,
            redirect_checker, postfix='redirects_used'):
        _output_redirects = codecs.open('%s.%s' % (file_name, postfix),
                encoding='utf-8', mode='w')

        counter = 0
        # check pages in redirects
        for title in selected_pages_list:
            title = normalize_title(title)
            if title in redirect_checker.reversed_index:
                for origin in redirect_checker.reversed_index[title]:
                    _output_redirects.write('[[%s]]\t[[%s]]\n' %
                            (origin, title))
                    counter += 1
        print "Found %d redirected pages" % counter

        templates_redirects = {}
        # check pages in redirects
        counter = 0
        for title in templates_used.keys():
            title = normalize_title(title)
            if title in redirect_checker.reversed_index:
                for origin in redirect_checker.reversed_index[title]:
                    _output_redirects.write('[[%s]]\t[[%s]]\n' %
                            (origin, title))
                    counter += 1

        print "Found %d redirected templates" % counter

        _output_redirects.close()


if __name__ == '__main__':

    select_all = True
    """
    if len(sys.argv) > 1:
        for argn in range(1, len(sys.argv)):
            arg = sys.argv[argn]
            if arg == '--all':
                select_all = True
                print "Selecting all the pages"
    """
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
                redirect_checker, select_all)

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
        parser.setContentHandler(PagesProcessorWiktionary(input_xml_file_name))
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
            output_file = codecs.open('%s.templates_counted' % \
                    input_xml_file_name, encoding='utf-8', mode='w')
            for n  in range(len(items)):
                if int(items[n][1]) > 0:
                    output_file.write('%s %d\n' % (items[n][0], items[n][1]))
            output_file.close()

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
