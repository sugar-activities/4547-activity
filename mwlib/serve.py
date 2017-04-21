#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""

import os
import re
import shutil
import signal
import StringIO
import subprocess
import time
import urllib2
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import filequeue, log, podclient, utils, wsgi, _version

# ==============================================================================

log = log.Log('mwlib.serve')

# ==============================================================================

def no_job_queue(job_type, collection_id, args):
    """Just spawn a new process for the given job"""
    
    if os.name == 'nt':
        kwargs = {}
    else:
        kwargs = {'close_fds': True}
    try:
        log.info('queueing %r' % args)
        subprocess.Popen(args, **kwargs)
    except OSError, exc:
        raise RuntimeError('Could not execute command %r: %s' % (
            args[0], exc,
        ))


# ==============================================================================

collection_id_rex = re.compile(r'^[a-z0-9]{16}$')

def make_collection_id(data):
    sio = StringIO.StringIO()
    for key in (
        _version.version,
        'metabook',
        'base_url',
        'script_extension',
        'template_blacklist',
        'template_exclusion_category',
        'login_credentials',
    ):
        sio.write(repr(data.get(key)))
    return md5(sio.getvalue()).hexdigest()[:16]

# ==============================================================================

def json_response(fn):
    """Decorator wrapping result of decorated function in JSON response"""
    
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if isinstance(result, wsgi.Response):
            return result
        return wsgi.Response(
            content=json.dumps(result),
            headers={'Content-Type': 'application/json'},
        )
    return wrapper

# ==============================================================================

class Application(wsgi.Application):
    metabook_filename = 'metabook.json'
    error_filename = 'errors'
    status_filename = 'status'
    output_filename = 'output'
    pid_filename = 'pid'
    zip_filename = 'collection.zip'
    mwpostlog_filename = 'mw-post.log'
    mwziplog_filename = 'mw-zip.log'
    mwrenderlog_filename = 'mw-render.log'
    
    def __init__(self, cache_dir,
        mwrender_cmd, mwrender_logfile,
        mwzip_cmd, mwzip_logfile,
        mwpost_cmd, mwpost_logfile,
        queue_dir,
        default_writer='rl',
        report_from_mail=None,
        report_recipients=None,
    ):
        self.cache_dir = utils.ensure_dir(cache_dir)
        self.mwrender_cmd = mwrender_cmd
        self.mwrender_logfile = mwrender_logfile
        self.mwzip_cmd = mwzip_cmd
        self.mwzip_logfile = mwzip_logfile
        self.mwpost_cmd = mwpost_cmd
        self.mwpost_logfile = mwpost_logfile
        if queue_dir:
            self.queue_job = filequeue.FileJobQueuer(utils.ensure_dir(queue_dir))
        else:
            self.queue_job = no_job_queue
        self.default_writer = default_writer
        self.report_from_mail = report_from_mail
        self.report_recipients = report_recipients
    
    def dispatch(self, request):
        try:
            command = request.post_data['command']
        except KeyError:
            return self.error_response('no command given')
        try:
            method = getattr(self, 'do_%s' % command)
        except AttributeError:
            return self.error_response('invalid command %r' % command)
        try:
            return method(request.post_data)
        except Exception, exc:
            return self.error_response('error executing command %r: %s' % (
                command, exc,
            ))
    
    @json_response
    def error_response(self, error):
        if isinstance(error, str):
            error = unicode(error, 'utf-8', 'ignore')
        elif not isinstance(error, unicode):
            error = unicode(repr(error), 'ascii')
        self.send_report_mail('error response', error=error)
        return {'error': error}
    
    def send_report_mail(self, subject, **kwargs):
        if not (self.report_from_mail and self.report_recipients):
            return
        utils.report(
            system='mwlib.serve',
            subject=subject,
            from_email=self.report_from_mail,
            mail_recipients=self.report_recipients,
            write_file=False,
            **kwargs
        )
    
    def get_collection_dir(self, collection_id):
        return os.path.join(self.cache_dir, collection_id)
    
    def check_collection_id(self, collection_id):
        if not collection_id or not collection_id_rex.match(collection_id):
            raise RuntimeError('invalid collection ID %r' % collection_id)
        collection_dir = self.get_collection_dir(collection_id)
        if not os.path.exists(collection_dir):
            raise RuntimeError('no such collection: %r' % collection_id)
    
    def new_collection(self, post_data):
        collection_id = make_collection_id(post_data)
        collection_dir = self.get_collection_dir(collection_id)
        if not os.path.isdir(collection_dir):
            log.info('Creating new collection dir %r' % collection_dir)
            os.makedirs(collection_dir)
        return collection_id
    
    def get_path(self, collection_id, filename, ext=None):
        p = os.path.join(self.get_collection_dir(collection_id), filename)
        if ext is not None:
            p += '.' + ext[:10]
        return p
    
    @json_response
    def do_render(self, post_data):
        metabook_data = post_data.get('metabook')
        collection_id = post_data.get('collection_id')
        if not (metabook_data or collection_id):
            return self.error_response('POST argument metabook or collection_id required')
        if metabook_data and collection_id:
            return self.error_response('Specify either metabook or collection_id, not both')
        try:
            base_url = post_data['base_url']
            writer = post_data.get('writer', self.default_writer)
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
        writer_options = post_data.get('writer_options', '')
        template_blacklist = post_data.get('template_blacklist', '')
        template_exclusion_category = post_data.get('template_exclusion_category', '')
        login_credentials = post_data.get('login_credentials', '')
        force_render = bool(post_data.get('force_render'))
        script_extension = post_data.get('script_extension', '')
        
        if not collection_id:
            collection_id = self.new_collection(post_data)
        
        log.info('render %s %s' % (collection_id, writer))
        
        response = {
            'collection_id': collection_id,
            'writer': writer,
            'is_cached': False,
        }
        
        pid_path = self.get_path(collection_id, self.pid_filename, writer)
        if os.path.exists(pid_path):
            log.info('mw-render already running for collection %r' % collection_id)
            return response
        
        output_path = self.get_path(collection_id, self.output_filename, writer)
        if os.path.exists(output_path):
            if force_render:
                log.info('removing rendered file %r (forced rendering)' % output_path)
                utils.safe_unlink(output_path)
            else:
                log.info('re-using rendered file %r' % output_path)
                response['is_cached'] = True
                return response
        
        status_path = self.get_path(collection_id, self.status_filename, writer)
        if os.path.exists(status_path):
            if force_render:
                log.info('removing status file %r (forced rendering)' % status_path)
                utils.safe_unlink(status_path)
            else:
                log.info('status file exists %r' % status_path)
                return response
        
        error_path = self.get_path(collection_id, self.error_filename, writer)
        if os.path.exists(error_path):
            if force_render:
                log.info('removing error file %r (forced rendering)' % error_path)
                utils.safe_unlink(error_path)
            else:
                log.info('error file exists %r' % error_path)
                return response
        
        if self.mwrender_logfile:
            logfile = self.mwrender_logfile
        else:
            logfile = self.get_path(collection_id, self.mwrenderlog_filename, writer)
        
        args = [
            self.mwrender_cmd,
            '--logfile', logfile,
            '--error-file', error_path,
            '--status-file', status_path,
            '--writer', writer,
            '--output', output_path,
            '--pid-file', pid_path,
        ]
        
        zip_path = self.get_path(collection_id, self.zip_filename)
        if os.path.exists(zip_path):
            log.info('using existing ZIP file to render %r' % output_path)
            args.extend(['--config', zip_path])
            if writer_options:
                args.extend(['--writer-options', writer_options])
            if template_blacklist:
                args.extend(['--template-blacklist', template_blacklist])
            if template_exclusion_category:
                args.extend(['--template-exclusion-category', template_exclusion_category])
        else:
            if force_render:
                return self.error_response('Forced to render document which has not been previously rendered.')
            log.info('rendering %r' % output_path)
            metabook_path = self.get_path(collection_id, self.metabook_filename)
            f = open(metabook_path, 'wb')
            f.write(metabook_data)
            f.close()
            args.extend([
                '--metabook', metabook_path,
                '--config', base_url,
                '--keep-zip', zip_path,
            ])
            if writer_options:
                args.extend(['--writer-options', writer_options])
            if template_blacklist:
                args.extend(['--template-blacklist', template_blacklist])
            if template_exclusion_category:
                args.extend(['--template-exclusion-category', template_exclusion_category])
            if login_credentials:
                args.extend(['--login', login_credentials])
            if script_extension:
                args.extend(['--script-extension', script_extension])
        
        self.queue_job('render', collection_id, args)
        
        return response
    
    def read_status_file(self, collection_id, writer):
        status_path = self.get_path(collection_id, self.status_filename, writer)
        try:
            f = open(status_path, 'rb')
            return json.loads(f.read())
            f.close()
        except (IOError, ValueError):
            return {'progress': 0}
    
    @json_response
    def do_render_status(self, post_data):
        try:
            collection_id = post_data['collection_id']
            writer = post_data.get('writer', self.default_writer)
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
            
        self.check_collection_id(collection_id)
        
        log.info('render_status %s %s' % (collection_id, writer))
        
        output_path = self.get_path(collection_id, self.output_filename, writer)
        if os.path.exists(output_path):
            return {
                'collection_id': collection_id,
                'writer': writer,
                'state': 'finished',
            }
        
        error_path = self.get_path(collection_id, self.error_filename, writer)
        if os.path.exists(error_path):
            text = unicode(open(error_path, 'rb').read(), 'utf-8', 'ignore')
            self.send_report_mail('rendering failed',
                collection_id=collection_id,
                writer=writer,
                error=text,
            )
            return {
                'collection_id': collection_id,
                'writer': writer,
                'state': 'failed',
                'error': text,
            }
        
        return {
            'collection_id': collection_id,
            'writer': writer,
            'state': 'progress',
            'status': self.read_status_file(collection_id, writer),
        }
    
    @json_response
    def do_render_kill(self, post_data):
        try:
            collection_id = post_data['collection_id']
            writer = post_data.get('writer', self.default_writer)
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
        
        self.check_collection_id(collection_id)
        
        log.info('render_kill %s %s' % (collection_id, writer))
        
        pid_path = self.get_path(collection_id, self.pid_filename, writer)
        killed = False
        try:
            pid = int(open(pid_path, 'rb').read())
            os.kill(pid, signal.SIGINT)
            killed = True
        except (OSError, ValueError, IOError):
            pass
        return {
            'collection_id': collection_id,
            'writer': writer,
            'killed': killed,
        }
    
    def do_download(self, post_data):
        try:
            collection_id = post_data['collection_id']
            writer = post_data.get('writer', self.default_writer)
        except KeyError, exc:
            log.ERROR('POST argument required: %s' % exc)
            return self.http500()
        
        try:
            self.check_collection_id(collection_id)
        
            log.info('download %s %s' % (collection_id, writer))
        
            output_path = self.get_path(collection_id, self.output_filename, writer)
            status = self.read_status_file(collection_id, writer)
            response = wsgi.Response(content=open(output_path, 'rb'))
            os.utime(output_path, None)
            if 'content_type' in status:
                response.headers['Content-Type'] = status['content_type'].encode('utf-8', 'ignore')
            else:
                log.warn('no content type in status file')
            if 'file_extension' in status:
                response.headers['Content-Disposition'] = 'inline;filename="collection.%s"' %  (
                    status['file_extension'].encode('utf-8', 'ignore'),
                )
            else:
                log.warn('no file extension in status file')
            return response
        except Exception, exc:
            log.ERROR('exception in do_download(): %r' % exc)
            return self.http500()
    
    @json_response
    def do_zip_post(self, post_data):
        try:
            metabook_data = post_data['metabook']
            base_url = post_data['base_url']
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
        template_blacklist = post_data.get('template_blacklist', '')
        template_exclusion_category = post_data.get('template_exclusion_category', '')
        login_credentials = post_data.get('login_credentials', '')
        script_extension = post_data.get('script_extension', '')
        
        pod_api_url = post_data.get('pod_api_url', '')
        if pod_api_url:
            result = json.loads(urllib2.urlopen(pod_api_url, data="any").read())
            post_url = result['post_url']
            response = {
                'state': 'ok',
                'redirect_url': result['redirect_url'],
            }
        else:
            try:
                post_url = post_data['post_url']
            except KeyError:
                return self.error_response('POST argument required: post_url')
            response = {'state': 'ok'}
        
        collection_id = self.new_collection(post_data)
        
        log.info('zip_post %s %s' % (collection_id, pod_api_url))
        
        pid_path = self.get_path(collection_id, self.pid_filename, 'zip')
        if os.path.exists(pid_path):
            log.info('mw-zip/mw-post already running for collection %r' % collection_id)
            return response
        
        zip_path = self.get_path(collection_id, self.zip_filename)
        if os.path.exists(zip_path):
            log.info('POSTing ZIP file %r' % zip_path)
            if self.mwpost_logfile:
                logfile = self.mwpost_logfile
            else:
                logfile = self.get_path(collection_id, self.mwpostlog_filename)
            args = [
                self.mwpost_cmd,
                '--logfile', logfile,
                '--posturl', post_url,
                '--input', zip_path,
                '--pid-file', pid_path,
            ]
        else:
            log.info('Creating and POSting ZIP file %r' % zip_path)
            if self.mwzip_logfile:
                logfile = self.mwzip_logfile
            else:
                logfile = self.get_path(collection_id, self.mwziplog_filename)
            metabook_path = self.get_path(collection_id, self.metabook_filename)
            f = open(metabook_path, 'wb')
            f.write(metabook_data)
            f.close()
            args = [
                self.mwzip_cmd,
                '--logfile', logfile,
                '--metabook', metabook_path,
                '--config', base_url,
                '--posturl', post_url,
                '--output', zip_path,
                '--pid-file', pid_path,
            ]
            if template_blacklist:
                args.extend(['--template-blacklist', template_blacklist])
            if template_exclusion_category:
                args.extend(['--template-exclusion-category', template_exclusion_category])
            if login_credentials:
                args.extend(['--login', login_credentials])
            if script_extension:
                args.extend(['--script-extension', script_extension])
        
        self.queue_job('post', collection_id, args)
        
        return response
    

# ==============================================================================

def clean_cache(max_age, cache_dir):
    """Clean all subdirectories of cache_dir whose mtime is before now-max_age
    
    @param max_age: max age of directories in seconds
    @type max_age: int
    
    @param cache_dir: cache directory
    @type cache_dir: basestring
    """
    
    now = time.time()
    for d in os.listdir(cache_dir):
        path = os.path.join(cache_dir, d)
        if not os.path.isdir(path) or not collection_id_rex.match(d):
            log.warn('unknown item in cache dir %r: %r' % (cache_dir, d))
            continue
        if now - os.stat(path).st_mtime < max_age:
            continue
        try:
            log.info('removing directory %r' % path)
            shutil.rmtree(path)
        except Exception, exc:
            log.ERROR('could not remove directory %r: %s' % (path, exc))
