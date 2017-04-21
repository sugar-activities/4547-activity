# -*- coding: utf-8 -*-


def configure():
    confvars = {}
    confvars['comandline'] = False
    confvars['path'] = 'fr/frwiki-20111231-pages-articles.xml'
    confvars['port'] = 8005
    confvars['home_page'] = '/static/index_fr.html'
    confvars['templateprefix'] = u'Modèle:'
    confvars['wpheader'] = 'Un article de Wikipédia, l\'encyclopédie libre'
    confvars['wpfooter'] = 'Contenu disponible sous '+ \
    'Conditions de l\'<a licence href="/static/es-gfdl.html"> '+ \
    'GNU Free Documentation </a>. Wikipedia est une marque déposée <br/> '+ \
    'organisme enregistré à but non lucratif Wikimedia '+ \
    'Foundation, Inc <br/> href="/static/about_fr.html"> <a propos '+ \
    'Wikipedia </a>'
    confvars['resultstitle'] = "Résultats de recherche pour '%s'."
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

    class WikipediaActivityFR(activity.WikipediaActivity):

        def __init__(self, handle):
            self.confvars = configure()
            activity.WikipediaActivity.__init__(self, handle)
