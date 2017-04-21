import os
import sys
from urllib import urlopen
from urllib import FancyURLopener
import codecs
from BeautifulSoup import BeautifulSoup, Tag, NavigableString
# NOTE: this script use BeutifulSoup 3. Is deprecated and the api 
# is incopatible with the last version
# docs are here:
# http://www.crummy.com/software/BeautifulSoup/bs3/documentation.html
import shutil
import json

# read the list of articles


def normalize_title(title):
    s = title.strip().replace(' ', '_')
    return s[0].capitalize() + s[1:]


class FileListReader():

    def __init__(self, file_name):
        _file = codecs.open(file_name,
                                encoding='utf-8', mode='r')
        self.list = []
        line = _file.readline()
        while line:
            self.list.append(normalize_title(line))
            line = _file.readline()


class CustomUrlOpener(FancyURLopener):

    version = 'Mozilla/5.0 (X11; Linux x86_64; rv:9.0) Gecko/20100101 ' + \
            'Firefox/9.0'

if len(sys.argv) < 2:
    print "Use as ../translate_index.py lang"
    exit()
else:
    translate_to = sys.argv[1]
    print "Translating to", translate_to

favorites_reader = FileListReader('../en/favorites_en.txt')

new_favorites_name = './favorites_%s.txt' % translate_to

trans_dict = {}
dictionary_file_name = 'en_to_%s_dictionary.json' % translate_to

if not os.path.exists(new_favorites_name):
    new_favorites = codecs.open(new_favorites_name,
                                    encoding='utf-8', mode='w')

    for article in favorites_reader.list:
        url_article = "http://en.wikipedia.org/wiki/%s" % article
        print article,
        opener = CustomUrlOpener()
        html = opener.open(url_article)
        #print html
        soup = BeautifulSoup(html)
        li = soup.findAll('li', {'class': 'interwiki-%s' % translate_to})
        if li:
            for attr in li[0].contents[0].attrs:
                if attr[0] == 'title':
                    translation = attr[1]
                    trans_dict[article] = translation
                    print '=', translation.encode('utf8')
                    new_favorites.write('%s\n' % translation)
        else:
            print
    new_favorites.close()

    # save the translation dictionary
    # the dictionary is saved to be able to process the index.html
    # at a later stage without need do the slow download from wikipedia
    # every time
    print "saving translations as dictionary"
    dictionary_file = codecs.open(dictionary_file_name,
                                    encoding='utf-8', mode='w')
    json.dump(trans_dict, dictionary_file)
    dictionary_file.close()

print "Opening index_en.html"

if not trans_dict:
    # read the translation dictionary
    try:
        dictionary_file = codecs.open(dictionary_file_name,
                                        encoding='utf-8', mode='r')
        trans_dict = json.load(dictionary_file)
        dictionary_file.close()
    except:
        print "Can't read the dictionary file", dictionary_file_name
        exit()

html_index_data = open('../static/index_en.html').read()
#shutil.copyfile(, './index_%s.html' % translate_to)

index_soup = BeautifulSoup(html_index_data)
for link in index_soup.findAll('a'):
    article_link = unicode(normalize_title(link['href'][6:]))

    if article_link in trans_dict:
        #try:
        link['href'] = '/wiki/%s' % trans_dict[article_link]
        link['title'] = trans_dict[article_link]
        link.find(text=link.text).replaceWith(trans_dict[article_link])
        #except:
        #    print "translation not found"
        #    pass
    else:
        link['class'] = 'TRANS_PENDING'

style = Tag(index_soup, "style")
index_soup.html.head.insert(1, style)
style_text = NavigableString('.TRANS_PENDING {background-color:red;}')
style.insert(0, style_text)

translated_index = open('./index_%s.html' % translate_to, 'w')
translated_index.write(str(index_soup))
translated_index.close()


