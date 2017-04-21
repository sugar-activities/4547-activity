#!/usr/bin/env python
# -*- coding: utf-8 -*-

from BeautifulSoup import BeautifulSoup
import codecs

soup = BeautifulSoup(open('./top.html'))

output = codecs.open('top.txt', encoding='utf-8', mode='w')

for link in soup('a'):
    output.write(link.text.replace(' ','_') + '\n')

output.close()

