#!/usr/bin/python

import glob, os, sys, signal, pwd, time
import pymysql, requests
from StringIO import StringIO


history_keyquerydict={
    'mysql.query.%s.usage':['INNODB_MEM_TOTAL','TABLE_LOCKS_WAITED', 'INNODB_ROW_LOCK_CURRENT_WAITS'],
    'mysql.query.%s.bytes.ps':['INNODB_DATA_READ', 'INNODB_DATA_WRITTEN', 'BYTES_SENT', 'BYTES_RECEIVED'],
    'mysql.query.%s.counts.ps':['INNODB_ROWS_DELETED', 'INNODB_ROWS_INSERTED', 'INNODB_ROWS_UPDATED',
                                'INNODB_ROWS_READ', 'ROWS_SENT', 'ROWS_READ', 'SLOW_QUERIES'],
    'mysql.slave.%s.usage':['Seconds_Behind_Master'],
}

history_sum={
    'mysql.query.read.ps':['COM_SELECT'],
    'mysql.query.write.ps':['COM_INSERT','COM_UPDATE','COM_DELETE','COM_REPLACE'],
}


def printHistory(name, key, value, buf):
    buf.write('H ')
    buf.write(name)
    buf.write(' ')
    buf.write(key)
    buf.write(' ')
    buf.write(str(value))
    buf.write('\n')

def printMeta(name, key, value, buf):
    buf.write('M ')
    buf.write(name)
    buf.write(' ')
    buf.write(key)
    buf.write(' ')
    buf.write(str(value).strip())
    buf.write('\n')

def measurePerformance(name=None, host=None, port=3306, username=None, password=None, buf=None ):
    if not name:
        name = '%s:%d'%(host, port)
    conn = None
    try:
        conn = pymysql.connect(host=host, port=int(port),
                               user=username,
                               password=password,
                               charset='utf8mb4',
                               cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        sql = 'select 1 as one'
        cursor.execute(sql)
        result = cursor.fetchone()
        if 1 != result['one']:
            raise Exception('select 1 returned %s' % (str(result)))
        printHistory(name, 'mysql.ping', 1, buf)
        cursor.close()
    except Exception, e:
        printHistory(name, 'mysql.ping', 0, buf)
        exc_info = sys.exc_info()
        import traceback
        error = traceback.format_exception(*(exc_info))[-1]
        printMeta(name, 'mysql.ping.error', error, buf)

    if conn:
        cursor = conn.cursor()
        databases = {}
        kvdict={}
        variable_dict={}
        sql = 'select VARIABLE_NAME, VARIABLE_VALUE from information_schema.GLOBAL_STATUS '
        cursor.execute(sql)
        while True:
            result = cursor.fetchone()
            if not result:
                break
            key =result['VARIABLE_NAME']
            value = result['VARIABLE_VALUE']
            kvdict[key] = value
        sql = 'show databases'
        cursor.execute(sql)
        while True:
            result = cursor.fetchone()
            if not result:
                break

            databases[result['Database']] = 0

        for db in databases.keys():
            sql = "select table_schema, IFNULL(sum((data_length+index_length)),0) AS Byte from information_schema.tables where table_schema='%s'"%(db)
            cursor.execute(sql)
            result = cursor.fetchone()

            databases[result['table_schema']] = result['Byte']

        sql = 'show global variables'
        cursor.execute(sql)
        while True:
            result = cursor.fetchone()
            if not result:
                break

            variable_dict[result['Variable_name']] = result['Value']

        try:
            sql = 'show slave status'
            cursor.execute(sql)
            result = cursor.fetchone()
            if result:
                variable_dict.update(result)
                if 'Seconds_Behind_Master' in result and result['Seconds_Behind_Master'] != None:
                    kvdict['Seconds_Behind_Master'] = result['Seconds_Behind_Master']
        except pymysql.err.InternalError, e:
            exc_info = sys.exc_info()
            import traceback
            error = traceback.format_exception(*(exc_info))[-1]
            printMeta(name, 'mysql.slave.error', error, buf)

        conn.close()
        # from pprint import pprint
        # pprint(kvdict)

        printHistory(name, 'mysql.connection.usage',  kvdict['THREADS_CONNECTED'], buf)
        printHistory(name, 'mysql.bufferpool.usage', 100.0 - float(kvdict['INNODB_BUFFER_POOL_PAGES_FREE'])*100.0/float(kvdict['INNODB_BUFFER_POOL_PAGES_TOTAL']), buf)
        if 'INNODB_MEM_TOTAL' in kvdict:
            printHistory(name, 'mysql.query.INNODB_MEM_TOTAL.usage', kvdict['INNODB_MEM_TOTAL'], buf)
        printHistory(name, 'mysql.query.INNODB_ROW_LOCK_CURRENT_WAITS.usage',
                     kvdict['INNODB_ROW_LOCK_CURRENT_WAITS'], buf)
        for k, v in history_sum.items():
            printHistory(name, k, sum([int(kvdict[kk]) for kk in v]), buf)
        for db, size in databases.items():
            printHistory(name, 'mysql.db.%s.used.byte'%(db),size , buf)
        for k, v in history_keyquerydict.items():
            for vv in v:
                if vv in kvdict:
                    printHistory(name, k % (vv), kvdict[vv], buf)
        for k, v in variable_dict.items():
            printMeta(name, 'mysql.variables.%s'%(k), v, buf)

        return

def listdir(prefix=os.path.split(os.path.realpath(__file__))[0]):
    buf = StringIO()
    for filepath in glob.glob('%s/config/*.conf'%(prefix)):
        f= open(filepath,'r')
        if f:
            arg_dict = {}
            for line in f.readlines():
                if '=' in line:
                    k, v = line.strip().split('=')
                    arg_dict[k] = v
            try:
                measurePerformance(buf=buf, **arg_dict)
            except :
                pass
    return buf.getvalue()


def serve(host = '127.0.0.1', port=54000):
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    import os
    import re
    class MyHandler(BaseHTTPRequestHandler):
        def _doSend(self, response_text):
            self.send_response(200)
            self.send_header('Content-type', 'plain/text')
            self.end_headers()

            self.wfile.write(response_text)

        def do_GET(self):
            self._doSend(listdir())

            return
    try:
        server = HTTPServer((host, port), MyHandler)

        server.serve_forever()

    except KeyboardInterrupt:
        print('^C received, shutting down the web server')
        server.socket.close()

def redirectstdouterror( logfileprefix ):
    sys.stdout = open ( logfileprefix+'.out', 'a+' )
    sys.stderr = open ( logfileprefix+'.err', 'a+' )


def daemonize(uid = os.getuid(), log_prefix = None):
    if not hasattr ( os, 'fork'):
        return
    if os.fork():
        # os._exit(0)
        return

    os.setsid()
    os.setuid( uid )
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    if os.fork():
        os._exit(0)

    sys.stdin = open("/dev/null", "r")
    if log_prefix:
        redirectstdouterror ( log_prefix )
    else:
        sys.stdout = open("/dev/null", "w")
        sys.stderr = open("/dev/null", "w")
    serve()

def remotemeasure(host='127.0.0.1', port=54000):
    try:
        r = requests.get('http://%s:%d'%(host, port), timeout=3)
        sys.stdout.write(r.text)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        daemonize()
        time.sleep(3)
        r = requests.get('http://%s:%d' % (host, port), timeout=3)
        sys.stdout.write(r.text)


if __name__ == '__main__':
    remotemeasure()
    # print listdir()
