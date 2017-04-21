# -*- coding: utf-8 -*-


def configure():
    confvars = {}
    confvars['comandline'] = False
    confvars['path'] = 'qu/quwiki-20111228-pages-articles.xml'
    confvars['port'] = 8002
    confvars['home_page'] = '/static/index_qu.html'
    confvars['templateprefix'] = 'Plantilla:'
    confvars['wpheader'] = 'De Wikipedia, la enciclopedia libre'
    confvars['wpfooter'] = 'Contenido disponible bajo los ' + \
    'términos de la <a href="/static/es-gfdl.html">Licencia de ' + \
    'documentación libre de GNU</a>. <br/> Wikipedia es una marca ' + \
    'registrada de la organización sin ánimo de lucro Wikimedia ' + \
    'Foundation, Inc.<br/><a href="/static/about_es.html">Acerca de ' + \
    'Wikipedia</a>'
    confvars['resultstitle'] = "Resultados de la búsqueda sobre '%s'."
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

    class WikipediaActivityQU(activity.WikipediaActivity):

        def __init__(self, handle):
            self.confvars = configure()
            activity.WikipediaActivity.__init__(self, handle)
