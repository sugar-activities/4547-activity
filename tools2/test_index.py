#!/usr/bin/env python
# -*- coding: utf-8 -*-
# create index

import codecs
import os
from subprocess import Popen, PIPE, STDOUT
import re
import sys
import config

input_xml_file_name = config.input_xml_file_name


def normalize_title(title):
    s = title.strip().replace(' ', '_')
    return s[0].capitalize() + s[1:]


class RedirectParser:

    def __init__(self, file_name):
        self.link_re = re.compile('\[\[.*?\]\]')
        # Load redirects
        input_redirects = codecs.open('%s.redirects_used' % file_name,
                encoding='utf-8', mode='r')

        line = input_redirects.readline()
        self.redirects = {}
        count = 0
        while line:
            links = self.link_re.findall(unicode(line))
            if len(links) == 2:
                origin = normalize_title(links[0][2:-2])
                destination = normalize_title(links[1][2:-2])
                self.redirects[origin] = destination
            line = input_redirects.readline()
            count += 1
            print "Processing %d\r" % count,
        input_redirects.close()

    def get_redirected(self, article_title):
        try:
            redirect = self.redirects[normalize_title(article_title)]
        except:
            redirect = None
        return redirect


class DataRetriever():

    def __init__(self, data_files_base, redirects_checker):
        self._bzip_file_name = '%s.processed.bz2' % data_files_base
        self._bzip_table_file_name = '%s.processed.bz2t' % data_files_base
        self._index_file_name = '%s.processed.idx' % data_files_base
        self.template_re = re.compile('({{.*?}})')
        self.redirects_checker = redirects_checker

    def _get_article_position(self, article_title):
        article_title = normalize_title(article_title)
        #index_file = codecs.open(self._index_file_name, encoding='utf-8',
        #        mode='r')
        index_file = open(self._index_file_name, mode='r')

        index_line = index_file.readline()
        num_block = -1
        position = -1
        while index_line:
            words = index_line.split()
            article = words[0]
            if article == article_title:
                num_block = int(words[1])
                position = int(words[2])
                break
            index_line = index_file.readline()
        index_file.close()

        if num_block == -1:
            # look at redirects
            redirect = self.redirects_checker.get_redirected(article_title)
            print "Searching redirect from %s to %s" % (article_title,
                    redirect)
            if redirect is not None:
                return self._get_article_position(redirect)

        print "Numblock %d, position %d" % (num_block, position)
        return num_block, position

    def _get_block_start(self, num_block):
        bzip_table_file = open(self._bzip_table_file_name, mode='r')
        n = num_block
        table_line = ''
        while n > 0:
            table_line = bzip_table_file.readline()
            n -= 1
        if table_line == '':
            return -1
        parts = table_line.split()
        block_start = int(parts[0])
        bzip_table_file.close()
        return block_start

    def get_expanded_article(self, article_title):
        """
        This method does not do real template expansion
        is only used to test all the needed templates and redirects are
        available.
        """
        text_article = self.get_text_article(article_title)
        templates_cache = {}
        expanded_article = ''
        parts = self.template_re.split(text_article)
        for part in parts:
            if part.startswith('{{'):
                part = part[2:-2]
                #print "TEMPLATE: %s" % part
                if part.find('|') > -1:
                    template_name = part[:part.find('|')]
                else:
                    template_name = part
                # TODO: Plantilla should be a parameter
                template_name = normalize_title('Plantilla:%s' % template_name)
                if template_name in templates_cache:
                    expanded_article += templates_cache[template_name]
                else:
                    templates_content = self.get_text_article(template_name)
                    expanded_article += templates_content
                    templates_cache[template_name] = templates_content
            else:
                expanded_article += part
        return expanded_article

    def get_text_article(self, article_title):
        output = ''
        print "Looking for article %s" % article_title
        num_block, position = self._get_article_position(article_title)
        if num_block == -1:
            print "Article not found"
        else:
            print "Found at block %d position %d" % (num_block, position)

        block_start = self._get_block_start(num_block)
        #print "Block %d starts at %d" % (num_block, block_start)
        if block_start == -1:
            return ""

        # extract the block
        bzip_file = open(self._bzip_file_name, mode='r')
        cmd = ['../bin/%s/seek-bunzip' % config.system_id, str(block_start)]
        p = Popen(cmd, stdin=bzip_file, stdout=PIPE, stderr=STDOUT,
                close_fds=True)

        while position > 0:
            line = p.stdout.readline()
            position -= len(line)

        finish = False
        while not finish:
            line = p.stdout.readline()
            if len(line) == 2:
                if ord(line[0]) == 3:
                    finish = True
                    break
            output += line
        return output


if __name__ == '__main__':

    page_title = ''
    if len(sys.argv) > 1:
        page_title = sys.argv[1]
    else:
        print "Use ../tools2/test_index.py page_title"
        exit()

    redirects_checker = RedirectParser(input_xml_file_name)
    data_retriever = DataRetriever(input_xml_file_name, redirects_checker)
    print data_retriever.get_expanded_article(page_title)
