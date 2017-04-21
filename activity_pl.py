# -*- coding: utf-8 -*-


def configure():
    confvars = {}
    confvars['comandline'] = False
    confvars['path'] = 'pl/plwiki-20111227-pages-articles.xml'
    confvars['port'] = 8003
    confvars['home_page'] = '/static/index_pl.html'
    confvars['templateprefix'] = 'Szablon:'
    confvars['wpheader'] = 'Z Wikipedii, Wolnej Encyklopedii'

    confvars['wpfooter'] = 'Materiały dostępne na licencji ' + \
    '<a href="/static/es-gfdl.html">GNU Licencja Wolnej Dokumentacji</a>' + \
    '<br/>Wikipedia to zarejestrowany znak towarowy organizacji non-profit' + \
    'Wikimedia Foundation, Inc.<br/><a href="/static/about_pl.html">' + \
    'O Wikipedii</a>'
    confvars['resultstitle'] = "Rezultat wyszukiwania dla '%s."
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

    class WikipediaActivityPL(activity.WikipediaActivity):

        def __init__(self, handle):
            self.confvars = configure()
            activity.WikipediaActivity.__init__(self, handle)
