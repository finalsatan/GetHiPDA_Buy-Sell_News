#!/usr/bin/env python3
# coding=utf-8

__author__ = 'finalsatan'

'''
Define the class HttpRequest to send a http request and get the response
'''

import re
from datetime import datetime
import time
import http.cookiejar
import urllib.request, urllib.parse, urllib.error
from io import StringIO, BytesIO
import gzip
import hashlib


class HttpRequest:
    '''
    The http request class to send a http request and get the response
    '''

    default_headers = {
        'Accept'          : 'text/html, application/xhtml+xml, */*',
        'Accept-Language' : 'zh-CN',
        'User-Agent'      : 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
        'Accept-Encoding' : 'gzip, deflate',
        'Connection'      : 'Keep-Alive',
        'Cache-Control'   : 'no-cache'
    }

    def __init__( self, url, post_data = None, headers = {} ):        
        self._url = url
        self._post_data = None
        self._resp = None
        self._resp_content = None

        if post_data is None:
            pass
        else:
            post_data = urllib.parse.urlencode( post_data )
            self._post_data = post_data.encode()

        d_headers = HttpRequest.default_headers
        for k in headers.keys():
            d_headers[k] = headers[k]
        self._headers = d_headers


    def send_request( self ):
        '''
        Send Http Request
        '''
        fails = 0
        while True:
           try:
              if fails >= 3:
                 raise Exception()
                 return -1
              req = urllib.request.Request( self._url, self._post_data, self._headers )
              resp = urllib.request.urlopen( req, timeout = 3 ) 
              self._resp = resp
              return resp;
           except:
              fails += 1
              print (" Trying connect the network: ", fails)
           else:
               raise Exception()
               return -1

        return self._resp
        
    def get_resp_content( self ):
        '''
        Get Response Content
        '''
        if self._resp.info().get( 'Content-Encoding' ) == 'gzip':
            buf = BytesIO( self._resp.read() )
            f = gzip.GzipFile( fileobj = buf )
            self._resp_content = f.read()
        else:
            self._resp_content = self._resp.read()

        return self._resp_content
