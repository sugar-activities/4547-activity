#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import sqlite3

search_word = ''
if len(sys.argv) > 1:
    search_word = sys.argv[1]
else:
    print "Use ../tools2/test_sql_search.py topic"
    exit()

print "Opening index"
dbpath = './search.db'
conn = sqlite3.connect(dbpath)

print "Searching %s" % search_word
search_word = '%' + search_word + '%'
results = conn.execute("SELECT * from articles where title like'%s'" %
            search_word)
print "arraysize", results.arraysize
row = results.next()
while row:
    print row
    row = results.next()
