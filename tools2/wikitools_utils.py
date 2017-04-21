#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import re


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
            links = self.link_re.findall(unicode(line))
            if len(links) == 2:
                origin = normalize_title(links[0][2:-2])
                destination = normalize_title(links[1][2:-2])
                self.redirects[origin] = destination
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
            redirect = self.redirects[normalize_title(article_title)]
        except:
            redirect = None
        return redirect


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
                print "Processing page %s \r" % page.encode('ascii', 'replace'),
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


class TemplatesCounterWriter:

    def __init__(self, file_name, items):
        print "Writing templates_counted file"
        output_file = codecs.open('%s.templates_counted' % \
                file_name, encoding='utf-8', mode='w')
        for n  in range(len(items)):
            if int(items[n][1]) > 0:
                output_file.write('%s %d\n' % (items[n][0], items[n][1]))
        output_file.close()


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
                            if '#' in link:
                                # use only the article part of the link
                                link = link[:link.find('#')]

                        if not link in self.links and \
                            not link in favorites:
                            self.links.append(link)
            line = input_links.readline()
        input_links.close()


def normalize_title(title):
    if len(title) == 0:
        return ''
    s = title.strip().replace(' ', '_')
    if len(s) > 1:
        return s[0].capitalize() + s[1:]
    else:
        return s.capitalize()
