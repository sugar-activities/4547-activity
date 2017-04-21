#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Create a file with a list of pages with less than N links pointing to them.
# By default N=5 but can be configured with the param --min_cant_links

import codecs
import sys
from wikitools_utils import FileListReader
import config

if __name__ == '__main__':

    input_xml_file_name = config.input_xml_file_name

    min_cant_links = 5
    if len(sys.argv) > 1:
        if sys.argv[1] == '--min_cant_links':
            min_cant_links = int(sys.argv[2])

    print "Adding articles with less than %d links" % min_cant_links

    # Read favorites list
    favorites_reader = FileListReader(config.favorites_file_name)

    ranking_file = codecs.open('%s.links_counted' % input_xml_file_name,
                            encoding='utf-8', mode='r')

    print "Writing low_rank_pages file"
    output_file = codecs.open('%s.low_rank_pages' % input_xml_file_name,
                    encoding='utf-8', mode='w')

    line = ranking_file.readline()
    while line:
        parts = line.split()
        article = parts[0]
        cant_links = int(parts[1])
        if cant_links < min_cant_links and \
                article not in favorites_reader.list:
            output_file.write('%s\n' % article)

        line = ranking_file.readline()

    output_file.close()
    ranking_file.close()
