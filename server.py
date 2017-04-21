#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# Web server script for Wikiserver project.
#
# Usage: server.py <dbfile> <port>
#
## Standard libs
from __future__ import with_statement
import logging
import sys
import os
import platform
import select
import codecs
import BaseHTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
import SocketServer

import cgi
import errno
import urllib
import tempfile
import re
try:
    from hashlib import md5
except ImportError:
    from md5 import md5

import dataretriever
import pylru
import simplejson

# to render the svg icons
import StringIO
import cairo
from sugar3.graphics.icon import _IconBuffer
from sugar3 import profile

##
## Libs we ship -- add lib path for
## shared objects
##
_root_path = os.path.dirname(__file__)
# linux32_27" for Linux 32bits Python 2.7
system_id = "%s%s" % (platform.system().lower(),
                      platform.architecture()[0][0:2])
if platform.processor().startswith('arm'):
    system_id = platform.processor()

platform_dir = "%s_%s%s" % (system_id,
                            sys.version_info[0],   # major
                            sys.version_info[1])   # minor

sys.path.append(os.path.join(_root_path, 'binarylibs', platform_dir))

import mwlib.htmlwriter
from mwlib import parser, scanner, expander

# Uncomment to print out a large dump from the template expander.
#os.environ['DEBUG_EXPANDER'] = '1'


class MyHTTPServer(BaseHTTPServer.HTTPServer):
    def serve_forever(self, poll_interval=0.5):
        """Overridden version of BaseServer.serve_forever that does not fail
        to work when EINTR is received.
        """
        self._BaseServer__serving = True
        self._BaseServer__is_shut_down.clear()
        while self._BaseServer__serving:

            # XXX: Consider using another file descriptor or
            # connecting to the socket to wake this up instead of
            # polling. Polling reduces our responsiveness to a
            # shutdown request and wastes cpu at all other times.
            try:
                r, w, e = select.select([self], [], [], poll_interval)
            except select.error, e:
                if e[0] == errno.EINTR:
                    logging.debug("got eintr")
                    continue
                raise
            if r:
                self._handle_request_noblock()
        self._BaseServer__is_shut_down.set()

    def server_bind(self):
        """Override server_bind in HTTPServer to not use
        getfqdn to get the server name because is very slow."""
        SocketServer.TCPServer.server_bind(self)
        host, port = self.socket.getsockname()[:2]
        self.server_name = 'localhost'
        self.server_port = port


class WPWikiDB:
    """Retrieves article contents for mwlib."""

    def __init__(self, path, lang, templateprefix, templateblacklist):
        self.lang = lang
        self.templateprefix = templateprefix
        self.templateblacklist = templateblacklist
        self.dataretriever = dataretriever.DataRetriever(system_id, path)
        self.templates_cache = {'!': '|', u'!': '|'}  # a special case

    def getRawArticle(self, title, followRedirects=True):

        # Retrieve article text, recursively following #redirects.
        if title == '':
            return ''

        article_text = \
            self.dataretriever.get_text_article(title).decode('utf-8')

        # Stripping leading & trailing whitespace fixes template expansion.
        article_text = article_text.lstrip()
        article_text = article_text.rstrip()

        return article_text

    def getTemplate(self, title, followRedirects=False):
        if title in self.templates_cache:
            return self.templates_cache[title]
        else:
            try:
                template_content = self.getRawArticle(title)
                # check recursion in templates
                template_name = title[title.find(':') + 1:]

                # Remove <noinclude>  because expandtemplates doesn't detect it
                # and follow recursions
                lower_content = template_content.lower()
                start_noinclude = lower_content.find('<noinclude>')
                while start_noinclude > -1:
                    end_noinclude = lower_content.find('</noinclude>')
                    content = template_content[:start_noinclude]
                    if end_noinclude > -1:
                        content = content + template_content[
                            end_noinclude + len('</noinclude>'):]
                    template_content = content
                    lower_content = template_content.lower()
                    start_noinclude = lower_content.find('<noinclude>')

                if re.search('{{' + template_name, template_content,
                             re.IGNORECASE) is not None:
                    logging.error("Found recursion template %s" % title)
                    template_content = re.sub(template_name, '_not_found_',
                                              template_content, re.IGNORECASE)

                    # Search again
                    if re.search('{{' + template_name, template_content,
                                 re.IGNORECASE) is not None:
                        template_content = ''

            except:
                template_content = ''

            self.templates_cache[title] = template_content
            return template_content

    def expandArticle(self, article_text, title):
        template_expander = expander.Expander(
            article_text, pagename=title,
            wikidb=self, lang=self.lang,
            templateprefix=self.templateprefix,
            templateblacklist=self.templateblacklist)
        expanded_article = template_expander.expandTemplates()

        return expanded_article

    def getExpandedArticle(self, title):
        return self.expandArticle(self.getRawArticle(title), title)


class WPImageDB:
    """Retrieves images for mwlib."""
    def __init__(self, basepath):
        self.basepath = basepath

    def hashpath(self, name):
        name = name.replace(' ', '_')
        name = name[:1].upper() + name[1:]
        d = md5(name.encode('utf-8')).hexdigest()
        return "/".join([d[0], d[:2], name])

    def hashpath_dir(self, name):
        name = name.replace(' ', '_')
        name = name[:1].upper() + name[1:]
        d = md5(name.encode('utf-8')).hexdigest()
        return "/".join([d[0], d[:2]])

    def getPath(self, name, size=None):
        hashed_name = self.hashpath(name).encode('utf8')
        path = self.basepath + '/%s' % hashed_name
        return path

    def getURL(self, name, size=None):
        hashed_name = self.hashpath(name).encode('utf8')
        if size is not None:
            file_name = self.basepath + self.hashpath_dir(name) + '/' + \
                ('%dpx-' % size) + name.replace(' ', '_')
        else:
            file_name = self.basepath + self.hashpath_dir(name) + '/' + \
                name.replace(' ', '_')

        if os.path.exists(file_name):
            url = '/' + file_name
        else:
            if size is None:
                url = 'http://upload.wikimedia.org/wikipedia/commons/' + \
                    hashed_name
            else:
                url = 'http://upload.wikimedia.org/wikipedia/commons/thumb/' \
                    + hashed_name + ('/%dpx-' % size) + name.replace(' ', '_')
            if re.match(r'.*\.svg$', url, re.IGNORECASE):
                url = url + '.png'

        #print "getUrl: %s -> %s" % (name.encode('utf8'), url.encode('utf8'))
        return url


class HTMLOutputBuffer:
    """Buffers output and converts to utf8 as needed."""

    def __init__(self):
        self.buffer = ''

    def write(self, obj):
        if isinstance(obj, unicode):
            self.buffer += obj.encode('utf8')
        else:
            self.buffer += obj

    def getvalue(self):
        return self.buffer


class WPMathRenderer:

    def __init__(self, html_writer):
        self.writer = html_writer

    def render(self, latex):
        logging.debug("MathRenderer %s" % latex)
        latex = latex.replace('\f', '\\f')
        latex = latex.replace('\t', '\\t')
        # \bold gives a error
        latex = latex.replace('\\bold', '')

        # postpone the process to do it with javascript at client side
        mathml = '<script type="math/tex">' + latex + '</script>'
        self.writer.math_processed = True
        return mathml


class WPHTMLWriter(mwlib.htmlwriter.HTMLWriter):
    """Customizes HTML output from mwlib."""

    def __init__(self, dataretriever, wfile, images=None, lang='en'):
        self.dataretriever = dataretriever
        self.gallerylevel = 0
        self.lang = lang
        self.math_processed = False
        self.links_list = []

        math_renderer = WPMathRenderer(self)
        mwlib.htmlwriter.HTMLWriter.__init__(self, wfile, images,
                                             math_renderer=math_renderer)

    def writeLink(self, obj):
        if obj.target is None:
            return

        article = obj.target
        #print "writeLink", article, obj.caption
        if article.startswith('#'):
            #print "----> <a href='%s'>" % article
            self.out.write("<a href='%s'>" % article)
        else:

            # Parser appending '/' characters to link targets for some reason.
            article = article.rstrip('/')

            title = article
            title = title[0].capitalize() + title[1:]
            title = title.replace("_", " ")
            self.links_list.append(article)

            parts = article.encode('utf-8').split('#')
            parts[0] = parts[0].replace(" ", "_")
            url = ("#".join([x for x in parts]))

            self.out.write("<a href='/wiki/%s'>" % url)

        if obj.children:
            for x in obj.children:
                self.write(x)
        else:
            self._write(obj.target)

        self.out.write("</a>")

    writeInterwikiLink = writeLink

    writeArticleLink = writeLink

    writeNamespaceLink = writeLink

    def writeImageLink(self, obj):
        if self.images is None:
            return

        width = obj.width
        height = obj.height

        is_thumb = obj.thumb or obj.frame or (self.gallerylevel > 0)

        if (width or height) or is_thumb:
            max_length = max(width, height)
            if obj.thumb:
                max_length = 180
            if self.gallerylevel > 0:
                max_length = 120
            url_thumb = self.images.getURL(obj.target, size=max_length)
            url = self.images.getURL(obj.target)
        else:
            url_thumb = self.images.getURL(obj.target)
            url = url_thumb

        if url_thumb is None:
            return

        # The following HTML generation code is copied closely from InstaView,
        # which seems to approximate the nest of <div> tags needed to render
        # images close to right.
        # It's also been extended to support Gallery tags.
        if self.imglevel == 0:
            self.imglevel += 1

            align = obj.align
            thumb = obj.thumb
            try:
                frame = obj.frame
            except:
                frame = False

            caption = obj.caption

            # SVG images must be included using <object data=''> rather than
            # <img src=''>.
            if re.match(r'.*\.svg$', url_thumb, re.IGNORECASE):
                tag = 'object'
                ref = 'data'
            else:
                tag = 'img'
                ref = 'src'

            # Hack to get galleries to look okay, in the absence of image
            # dimensions.
            if self.gallerylevel > 0:
                width = 120

            if thumb and not width:
                width = 180  # FIXME: This should not be hardcoded

            attr = ''
            if width:
                attr += 'width="%d" ' % width

            img = '<%(tag)s %(ref)s="%(url)s" longdesc="%(cap)s" %(att)s>' % \
                {'tag': tag, 'ref': ref, 'url': url_thumb, 'cap': caption,
                 'att': attr} + '</%(tag)s>' % {'tag': tag}

            center = False
            if align == 'center':
                center = True
                align = None

            if center:
                self.out.write('<div class="center">')

            if self.gallerylevel > 0:
                self.out.write('<div class="gallerybox" ' +
                               'style="width: 155px;">')

                self.out.write('<div class="thumb" ' +
                               'style="padding: 13px 0; width: 150px;">')
                self.out.write('<div style="margin-left: auto; ' +
                               'margin-right: auto; width: 120px;">')
                self.out.write('<a href="%s" class="image" title="%s">' %
                               (url, caption))
                self.out.write(img)
                self.out.write('</a>')
                self.out.write('</div>')
                self.out.write('</div>')

                self.out.write('<div class="gallerytext">')
                self.out.write('<p>')
                for x in obj.children:
                    self.write(x)
                self.out.write('</p>')
                self.out.write('</div>')

                self.out.write('</div>')
            elif frame or thumb:
                if not align:
                    align = "right"
                self.out.write('<div class="thumb t%s">' % align)

                if not width:
                    width = 180  # default thumb width
                self.out.write('<div style="width:%dpx;">' % (int(width) + 2))

                if thumb:
                    self.out.write(img)
                    self.out.write('<div class="thumbcaption">')
                    self.out.write('<div class="magnify" style="float:right">')
                    self.out.write('<a href="%s" class="internal" ' % url +
                                   'title="Enlarge">')
                    self.out.write('<img src="/static/magnify-clip.png">' +
                                   '</img>')
                    self.out.write('</a>')
                    self.out.write('</div>')
                    for x in obj.children:
                        self.write(x)
                    self.out.write('</div>')
                else:
                    self.out.write(img)
                    self.out.write('<div class="thumbcaption">')
                    for x in obj.children:
                        self.write(x)
                    self.out.write('</div>')

                self.out.write('</div>')
                self.out.write('</div>')
            elif align:
                self.out.write('<div class="float%s">' % align)
                self.out.write(img)
                self.out.write('</div>')
            else:
                self.out.write(img)

            if center:
                self.out.write('</div>')

            self.imglevel -= 1
        else:
            self.out.write('<a href="%s">' % url.encode('utf8'))

            for x in obj.children:
                self.write(x)

            self.out.write('</a>')

    def writeTagNode(self, t):
        if t.caption == 'gallery':
            self.out.write('<table class="gallery" cellspacing="0" ' +
                           'cellpadding="0">')

            self.gallerylevel += 1

            # TODO: More than one row.
            self.out.write('<tr>')

            for x in t.children:
                self.out.write('<td>')
                self.write(x)
                self.out.write('</td>')

            self.out.write('</tr>')

            self.gallerylevel -= 1

            self.out.write('</table>')
        else:
            # All others handled by base class.
            mwlib.htmlwriter.HTMLWriter.writeTagNode(self, t)


class WikiRequestHandler(SimpleHTTPRequestHandler):

    def __init__(self, wikidb, conf, links_cache, request, client_address,
                 server):
        # pullcord is currently offline
        # self.reporturl = 'pullcord.laptop.org:8000'
        self.reporturl = False
        self.ip = conf['ip']
        self.port = conf['port']
        self.lang = conf['lang']
        self.templateprefix = conf['templateprefix']
        self.templateblacklist = set(conf['templateblacklist'])
        self.wpheader = conf['wpheader']
        self.wpfooter = conf['wpfooter']
        self.resultstitle = conf['resultstitle']
        self.base_path = os.path.dirname(conf['path'])
        self.links_cache = links_cache
        self._xo_color = conf['xocolor']

        if 'editdir' in conf:
            self.editdir = conf['editdir']
        else:
            self.editdir = False
        if 'giturl' in conf:
            self.giturl = conf['giturl']
        else:
            self.giturl = False

        self.wikidb = wikidb

        self.client_address = client_address

        SimpleHTTPRequestHandler.__init__(
            self, request, client_address, server)

    def get_wikitext(self, title):
        article_text = self.wikidb.getRawArticle(title)
        #print article_text
        if self.editdir:
            edited = self.get_editedarticle(title)
            if edited:
                article_text = edited

        # Pass ?override=1 in the url to replace wikitext for testing
        # the renderer.
        if self.params.get('override', 0):
            override = codecs.open('override.txt', 'r', 'utf-8')
            article_text = override.read()
            override.close()

        # Pass ?noexpand=1 in the url to disable template expansion.
        if not self.params.get('noexpand', 0) \
                and not self.params.get('edit', 0):
            article_text = self.wikidb.expandArticle(article_text, title)

        return article_text

    def write_wiki_html(self, htmlout, title, article_text):
        tokens = scanner.tokenize(article_text, title)

        wiki_parsed = parser.Parser(tokens, title).parse()
        wiki_parsed.caption = title

        imagedb = WPImageDB(self.base_path + '/images/')
        writer = WPHTMLWriter(self.wikidb.dataretriever, htmlout,
                              images=imagedb, lang=self.lang)
        writer.write(wiki_parsed)
        self.links_cache[title] = writer.links_list
        return writer.math_processed

    def send_article(self, title):
        article_text = self.get_wikitext(title)

        # Capitalize the first letter of the article -- Trac #6991.
        title = title[0].capitalize() + title[1:]

        # Replace underscores with spaces in title.
        title = title.replace("_", " ")

        # Redirect to Wikipedia if the article text is empty
        # (e.g. an image link)
        if article_text == "":
            self.send_response(301)
            self.send_header("Location",
                             'http://' + self.lang + '.wikipedia.org/wiki/' +
                             title.encode('utf8'))
            self.end_headers()
            return

        # Pass ?raw=1 in the URL to see the raw wikitext (post expansion,
        # unless noexpand=1 is also set).
        if self.params.get('raw', 0):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()

            self.wfile.write(article_text.encode('utf8'))
        elif self.params.get('edit', 0):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            self.wfile.write('<html><body><form method="POST">')
            self.wfile.write('<input type="submit" value="OK"><br />')
            self.wfile.write('<textarea name="wmcontent" rows="40" cols="80">')
            htmlout = HTMLOutputBuffer()
            htmlout.write(article_text.encode('utf8'))
            self.wfile.write(htmlout.getvalue())
            self.wfile.write("</textarea></form></body></html>")
        else:
            htmlout = HTMLOutputBuffer()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            htmlout.write('<html xmlns="http://www.w3.org/1999/xhtml"> ')

            htmlout.write("<head>")
            htmlout.write("<title>%s</title>" % title.encode('utf8'))

            htmlout.write("<style type='text/css' media='screen, projection'>"
                          "@import '/static/common.css';"
                          "@import '/static/monobook.css';"
                          "@import '/static/styles.css';"
                          "@import '/static/shared.css';"
                          "</style>")

            htmlout.write("</head>")

            htmlout.write("<body>")

            htmlout.write("<h1>")
            htmlout.write(title)
            htmlout.write(' <font size="1">&middot; <a class="offsite" ')
            htmlout.write('href="http://' + self.lang + '.wikipedia.org/wiki/')
            htmlout.write(title)
            htmlout.write('">' + self.wpheader + '</a> ')

            if self.reporturl:
                # Report rendering problem.
                htmlout.write('&middot; <a class="offsite" ')
                htmlout.write('href="http://%s/render?q=' % self.reporturl)
                htmlout.write(title)
                htmlout.write('">Haz clic aquí si esta página contiene ' +
                              'errores de presentación</a> ')

                # Report inappropriate content.
                htmlout.write(' &middot; <a class="offsite" ')
                htmlout.write('href="http://%s/report?q=' % self.reporturl)
                htmlout.write(title)
                htmlout.write('">Esta página contiene material inapropiado' +
                              '</a>')

            if self.editdir:
                htmlout.write(' &middot; <a ')
                htmlout.write('href="http://%s:%s/wiki/' % (self.ip,
                                                            self.port))
                htmlout.write(title)
                htmlout.write('?edit=true">[ Editar ]</a>')
                htmlout.write(' &middot; <a ')
                htmlout.write('href="http://%s:%s/wiki/' % (self.ip,
                                                            self.port))
                htmlout.write(title)
                htmlout.write('?edit=true">[ Vista OK ]</a>')
            if self.giturl:
                htmlout.write(' &middot; <a ')
                htmlout.write('href="%s' % self.giturl)
                htmlout.write(title)
                htmlout.write('">[ Historial ]</a>')

            htmlout.write("</font>")
            htmlout.write('</h1>')

            needs_math = self.write_wiki_html(htmlout, title, article_text)

            if needs_math:
                # MathJs config
                htmlout.write('<script type="text/x-mathjax-config">')
                htmlout.write('  MathJax.Hub.Config({')
                htmlout.write('    extensions: [],')
                htmlout.write('    jax: ["input/TeX","output/HTML-CSS"],')
                htmlout.write('    "HTML-CSS": {')
                htmlout.write('      availableFonts:[],')
                htmlout.write('      styles: {".MathJax_Preview": ' +
                              '{visibility: "hidden"}}')
                htmlout.write('    }')
                htmlout.write('  });')
                htmlout.write('</script>')

                htmlout.write("<script type='text/javascript' " +
                              "src='http://%s:%s/static/MathJax/MathJax.js'>"
                              % (self.ip, self.port) + "</script>")

            # validate links
            self.write_process_links_js(htmlout, title)

            htmlout.write('<center>' + self.wpfooter + '</center>')
            htmlout.write("</body>")
            htmlout.write("</html>")

            html = htmlout.getvalue()

            self.wfile.write(html)

    def write_process_links_js(self, htmlout, title):
        """
        write javascript to request a array of external links using ajax
        and compare with the links in the page, if one link is external
        change the url and the className
        """
        htmlout.write("<script type='text/javascript'>\n")
        htmlout.write("  xmlhttp=new XMLHttpRequest();\n")
        htmlout.write("  xmlhttp.onreadystatechange=function() {\n")
        htmlout.write("    if (xmlhttp.readyState==4 && "
                      "xmlhttp.status==200) {\n")
        htmlout.write("      external_links = eval(xmlhttp.responseText);\n")
        htmlout.write("      for (var i = 0; i < document.links.length;"
                      "                                          i++) {\n")
        htmlout.write("        link_url = document.links[i].href;\n")
        htmlout.write("        last_bar = link_url.lastIndexOf('/');\n")
        htmlout.write("        loc_article = link_url.substr(last_bar+1);\n")
        htmlout.write("        external = false;\n")
        htmlout.write("        for (var j = 0; j < external_links.length;"
                      "             j++) {\n")
        htmlout.write("          external_link = external_links[j]\n")

        htmlout.write("          if (loc_article == external_link) {\n")
        htmlout.write("            external = true; break;}\n")
        htmlout.write("        }\n")
        htmlout.write("        if (external) {\n")
        link_baseurl = 'http://' + self.lang + '.wikipedia.org/wiki/'
        htmlout.write(("           href = '%s'" % link_baseurl) +
                      "+ external_links[j];\n")
        htmlout.write("           document.links[i].href = href;\n")
        htmlout.write("           document.links[i].className = 'offsite';\n")
        htmlout.write("        }\n")
        htmlout.write("      }\n")
        htmlout.write("    }\n")
        htmlout.write("  };\n")

        val_links = "http://%s:%s/links/%s" % (self.ip, self.port, title)
        htmlout.write("  xmlhttp.open('GET','%s',true);" % val_links)
        htmlout.write("  xmlhttp.send();")
        htmlout.write("</script>")

    def send_links(self, title):
        """
        send a json array of string with the list of url not availables
        in the local database
        """
        links = self.links_cache[title]
        # validate the links
        external_links = []
        articles_found = self.wikidb.dataretriever.check_existence_list(links)
        for article in links:
            if not dataretriever.normalize_title(article) in articles_found:
                article = article.replace(" ", "_").encode('utf8')
                # needed to have the same format than url in the page
                # when is compared in javascript
                quoted = urllib.quote(article, safe='~@#$&()*!+=:;,.?/\'')
                external_links.append(quoted)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(simplejson.dumps(external_links))

    def do_POST(self):

        real_path = urllib.unquote(self.path)
        real_path = unicode(real_path, 'utf8')

        (real_path, sep, param_text) = real_path.partition('?')

        # Wiki requests return article contents or redirect to Wikipedia.
        m = re.match(r'^/wiki/(.+)$', real_path)
        if self.editdir and m:
            title = m.group(1)

            self._save_page(title)

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            htmlout = HTMLOutputBuffer()
            htmlout.write(title.encode('utf8'))

            self.wfile.write('<html><body>Editado: ')
            self.wfile.write('<a href="')

            self.wfile.write(htmlout.getvalue())
            self.wfile.write('">')
            self.wfile.write(htmlout.getvalue())
            self.wfile.write('</body></html>')

            return

        # Any other request redirects to the index page.
        self.send_response(301)
        self.send_header("Location", "/static/")
        self.end_headers()

    def _save_page(self, title):
        formdata = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers, environ={'REQUEST_METHOD': 'POST'},
            keep_blank_values=1)

        wmcontent = formdata.getfirst('wmcontent')

        # fix newlines
        wmcontent = re.sub('\r', '', wmcontent)

        fpath = self.getfpath('wiki', title)
        # UGLY: racy.
        if not os.path.exists(fpath):
            self._saveorig(title)
        (fh, tmpfpath) = tempfile.mkstemp(dir=os.path.dirname(fpath))
        os.write(fh, wmcontent)
        os.close(fh)
        os.rename(tmpfpath, fpath)

        return True

    def getfpath(self, dir, title):
        # may want to hash it
        fpath = os.path.join(self.editdir, dir, title)
        return fpath

    def _saveorig(self, title):
        article_text = self.wikidb.getRawArticle(title)
        fpath = self.getfpath('wiki.orig', title)
        fh = codecs.open(fpath, 'w', encoding='utf-8')
        fh.write(article_text)
        fh.close()

    def get_editedarticle(self, title):
        buf = None
        fpath = self.getfpath('wiki', title)
        if os.path.exists(fpath):
            buf = codecs.open(fpath, 'r', encoding='utf-8').read()
        return buf

    def send_searchresult(self, title):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        self.wfile.write("<html><head><title>"
                         + (self.resultstitle % title.encode('utf8'))
                         + "</title></head>")

        self.wfile.write("<style type='text/css' media='screen, projection'>"
                         "@import '/static/monobook.css';</style>")

        self.wfile.write("</head>")

        self.wfile.write("<body>")

        self.wfile.write("<h1>" + (self.resultstitle % title.encode('utf8'))
                         + "</h1>")
        self.wfile.write("<ul>")

        articles = self.search(unicode(title))
        for article in articles:
            #if not result.startswith(self.templateprefix):
            self.wfile.write('<li><a href="/wiki/%s">%s</a></li>' %
                             (article.encode('utf8'),
                              article.encode('utf8').replace('_', ' ')))

        self.wfile.write("</ul>")

        self.wfile.write("</body></html>")

    def search(self, article_title):
        return self.wikidb.dataretriever.search(article_title)

    def send_image(self, path):
        if os.path.exists(path.encode('utf8')[1:]):
            # If image exists locally, serve it as normal.
            SimpleHTTPRequestHandler.do_GET(self)
        else:
            # If not, redirect to wikimedia.
            redirect_url = "http://upload.wikimedia.org/wikipedia/commons/%s" \
                % path.encode('utf8')
            self.send_response(301)
            self.send_header("Location", redirect_url.encode('utf8'))
            self.end_headers()

    def send_svg_icon(self, path):
        logging.error('SVG ICON %s', path)

        icon_buffer = _IconBuffer()
        icon_buffer.file_name = path[1:]
        icon_buffer.stroke_color = self._xo_color.get_stroke_color()
        icon_buffer.fill_color = self._xo_color.get_fill_color()
        icon_buffer.width = 90
        icon_buffer.height = 90
        icon_surface = icon_buffer.get_surface()
        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, icon_buffer.width,
                                     icon_buffer.height)
        context = cairo.Context(surface)
        context.set_source_rgba(1, 1, 1, 1)
        context.rectangle(0, 0, icon_buffer.width, icon_buffer.height)
        context.fill()
        context.set_source_surface(icon_surface, 0, 0)
        context.paint()
        out = StringIO.StringIO()
        surface.write_to_png(out)
        self.send_response(200)
        self.send_header("Content-Type", "image/png;")
        self.end_headers()
        self.wfile.write(out.getvalue())

    def handle_feedback(self, feedtype, article):
        with codecs.open("feedback.log", "a", "utf-8") as f:
            f.write(feedtype + "\t" + article + "\t" +
                    self.client_address[0] + "\n")
            f.close()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if feedtype == "render":
            strtype = "un error de presentación"
        elif feedtype == "report":
            strtype = "material inapropriado"

        self.wfile.write(
            "<html><title>Comentario recibido</title>" +
            "Gracias por reportar %s en la pagina <b>%s</b>.</html>" %
            (strtype, article.encode('utf8')))

    def do_GET(self):
        real_path = urllib.unquote(self.path)
        real_path = unicode(real_path, 'utf8')

        (real_path, sep, param_text) = real_path.partition('?')
        self.params = {}
        for p in param_text.split('&'):
            (key, sep, value) = p.partition('=')
            self.params[key] = value

        # Wiki requests return article contents or redirect to Wikipedia.
        m = re.match(r'^/wiki/(.+)$', real_path)
        if m:
            self.send_article(m.group(1))
            return

        # Search requests return search results.
        m = re.match(r'^/search$', real_path)
        if m:
            self.send_searchresult(self.params.get('q', ''))
            return

        # Image requests are handled locally or are referenced from Wikipedia.
        # matches /es_PE/images/, /en_US/images/ etc
        m = re.match(r'^/\w*/images/(.+)$', real_path)
        if m:
            self.send_image(real_path)
            return

        # Svg icons in the home are a special case to apply user colors
        m = re.match(r'^/static/svg/(.*)$', real_path)
        if m:
            self.send_svg_icon(real_path)
            return

        # Static requests handed off to SimpleHTTPServer.
        m = re.match(r'^/(static|generated)/(.*)$', real_path)
        if m:
            SimpleHTTPRequestHandler.do_GET(self)
            return

        # Handle link validation requests
        m = re.match(r'^/links/(.*)$', real_path)
        if m:
            self.send_links(m.group(1))
            return

        # Feedback links.
        m = re.match(r'^/(report|render)$', real_path)
        if m:
            self.handle_feedback(m.group(1), self.params.get('q', ''))
            return

        # Any other request redirects to the index page.
        self.send_response(301)
        self.send_header("Location", "/static/")
        self.end_headers()


def run_server(confvars):

    if 'editdir' in confvars:
        try:
            for dir in ['wiki', 'wiki.orig']:
                fdirpath = os.path.join(confvars['editdir'], dir)
                if not os.path.exists(fdirpath):
                    os.mkdir(fdirpath)
        except:
            logging.error("Error setting up directories:")
            logging.debug("%s must be a writable directory" %
                          confvars['editdir'])

    blacklistpath = os.path.join(os.path.dirname(confvars['path']),
                                 'template_blacklist')
    logging.debug("Reading template_blacklist %s" % blacklistpath)
    blacklist = set()
    if os.path.exists(blacklistpath):
        with open(blacklistpath, 'r') as f:
            for line in f.readlines():
                blacklist.add(line.rstrip().decode('utf8'))
    logging.debug("Read %d blacklisted templates" % len(blacklist))

    confvars['templateblacklist'] = blacklist
    confvars['lang'] = confvars['path'][0:2]
    confvars['flang'] = os.path.basename(confvars['path'])[0:5]

    wikidb = WPWikiDB(confvars['path'], confvars['lang'],
                      confvars['templateprefix'],
                      confvars['templateblacklist'])

    links_cache = pylru.lrucache(10)

    confvars['xocolor'] = profile.get_color()

    httpd = MyHTTPServer(
        ('', confvars['port']),
        lambda *args: WikiRequestHandler(wikidb, confvars, links_cache, *args))

    if confvars['comandline']:
        httpd.serve_forever()
    else:
        from threading import Thread
        server = Thread(target=httpd.serve_forever)
        server.setDaemon(True)
        logging.debug("Before start server")
        server.start()
        logging.debug("After start server")

    # Tell the world that we're ready to accept request.
    logging.debug('Ready')


if __name__ == '__main__':

    logging.error("Execute the starting class for your language wikipedia")
    logging.error("Ex: activity_es.py")
