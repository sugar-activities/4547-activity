# -*- coding: utf-8 -*-


def configure():
    confvars = {}
    confvars['comandline'] = False
    confvars['path'] = 'rw/rwwiki-20120127-pages-articles.xml'
    confvars['port'] = 8007
    confvars['home_page'] = '/static/index_rw.html'
    confvars['templateprefix'] = 'Template:'
    confvars['wpheader'] = 'From Wikipedia, The Free Encyclopedia'
    confvars['wpfooter'] = 'Content available under the ' + \
    '<a href="/static/es-gfdl.html">GNU Free Documentation License</a>.' + \
    ' <br/> Wikipedia is a registered trademark of the non-profit ' + \
    'Wikimedia Foundation, Inc.<br/><a href="/static/about_en.html">' + \
    'About Wikipedia</a>'
    confvars['resultstitle'] = "Search results for '%s'."
    return confvars


if __name__ == '__main__':
    import server
    import sys
    conf = configure()
    conf['path'] = sys.argv[1]
    conf['port'] = int(sys.argv[2])
    conf['comandline'] = True

    if len(sys.argv) > 3:
        conf['editdir'] = sys.argv[3]
    if len(sys.argv) > 4:
        conf['giturl'] = sys.argv[4]

    server.run_server(conf)

else:
    import activity

    class WikipediaActivityRW(activity.WikipediaActivity):

        def __init__(self, handle):
            self.confvars = configure()
            activity.WikipediaActivity.__init__(self, handle)
