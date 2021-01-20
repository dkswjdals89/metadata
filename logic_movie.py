# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect, Response, send_file
from sqlalchemy import or_, and_, func, not_, desc
import lxml.html
from lxml import etree as ET


# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, py_urllib
from framework.util import Util
from framework.common.util import headers, get_json_with_auth_session
from framework.common.plugin import LogicModuleBase, default_route_socketio

# 패키지
#from lib_metadata import SiteDaumTv, SiteTmdbTv, SiteTvingTv, SiteWavveTv
from lib_metadata import SiteNaverMovie, SiteTmdbMovie

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicMovie(LogicModuleBase):
    db_default = {
        'movie_db_version' : '1',
        'movie_first_order' : 'naver, daum, tmdb',
        'movie_use_tmdb_image' : 'False',

        'movie_total_test_search' : '',
        'movie_total_test_info' : '',

        'movie_naver_test_search' : '',
        'movie_naver_test_info' : '',

        'movie_tmdb_test_search' : '',
        'movie_tmdb_test_info' : '',

    }

    module_map = {'naver':SiteNaverMovie, 'tmdb':SiteTmdbMovie}

    def __init__(self, P):
        super(LogicMovie, self).__init__(P, 'setting')
        self.name = 'movie'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name

        try: return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except: return render_template('sample.html', title='%s - %s' % (P.package_name, sub))

    def process_ajax(self, sub, req):
        try:
            ret = {}
            if sub == 'test':
                param = req.form['param'].strip()
                call = req.form['call']
                mode = req.form['mode']
                tmps = param.split('|')
                year = 1900
                logger.debug(param)
                logger.debug(call)
                logger.debug(mode)
                ModelSetting.set('movie_%s_test_%s' % (call, mode), param)
                if len(tmps) == 2:
                    keyword = tmps[0].strip()
                    try: year = int(tmps[1].strip())
                    except: year = None
                else:
                    keyword = param
                if call == 'naver':
                    if mode == 'search':
                        ret = SiteNaverMovie.search(keyword, year=year)
                    elif mode == 'info':
                        ret = SiteNaverMovie.info(param)
                elif call == 'tmdb':
                    if mode == 'search':
                        ret = SiteTmdbMovie.search(keyword, year=year)
                    elif mode == 'info':
                        ret = SiteTmdbMovie.info(param)
                    elif mode == 'search_api':
                        ret = SiteTmdbMovie.search_api(keyword)
                    elif mode == 'info_api':
                        ret = SiteTmdbMovie.info_api(param)
                elif call == 'total':
                    if mode == 'search':
                        manual = (req.form['manual'] == 'manual')
                        ret = self.search(keyword, year=year, manual=manual)
                    elif mode == 'info':
                        ret = self.info(param)
                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})

    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            manual = bool(req.args.get('manual'))
            try: year = int(req.args.get('year'))
            except: year = 1900

            logger.debug(req.args.get('year'))
            logger.debug(year)
            
            if call == 'plex':
                return jsonify(self.search(req.args.get('keyword'), year, manual=manual))
        elif sub == 'info':
            return jsonify(self.info(req.args.get('code')))

    #########################################################

    def search(self, keyword, year, manual=False):
        ret = []
        site_list = ModelSetting.get_list('movie_first_order', ',')
        #site_list = ['naver']

        for idx, site in enumerate(site_list):
            logger.debug(site)
            if site == 'daum':
                continue
            if year is None:
                year = 1900
            else:
                try: year = int(year)
                except: year = 1900
            site_data = self.module_map[site].search(keyword, year=year)
            
            if site_data['ret'] == 'success':
                for item in site_data['data']:
                    item['score'] -= idx
                    #logger.debug(item)
                ret += site_data['data']
                if manual:
                    continue
                else:
                    if len(site_data['data']) and site_data['data'][0]['score'] > 85:
                        break

        ret = sorted(ret, key=lambda k: k['score'], reverse=True)  
        return ret




    def info(self, code):
        try:
            info = None
            if code[1] == 'N':
                tmp = SiteNaverMovie.info(code)
                if tmp['ret'] == 'success':
                    info = tmp['data']

                tmdb_info = None
                if info['country'][0] == u'한국':
                    tmdb_search = SiteTmdbMovie.search(info['title'], year=info['year'])
                else:
                    tmdb_search = SiteTmdbMovie.search(info['title'], year=info['year'])
                    #tmdb_search = SiteTmdbMovie.search(info['originaltitle'], year=info['year'])
                if tmdb_search['ret'] == 'success' and len(tmdb_search['data'])>0:
                    logger.debug(tmdb_search['data'][0])
                    if tmdb_search['data'][0]['score'] > 85:
                        tmdb_data = SiteTmdbMovie.info(tmdb_search['data'][0]['code'])
                        if tmdb_data['ret'] == 'success':
                            tmdb_info = tmdb_data['data']
                
                if tmdb_info is not None:
                    info['extras'] += tmdb_info['extras']
                    self.change_tmdb_actor_info(tmdb_info['actor'], info['actor'])
                    info['actor'] = tmdb_info['actor']
                    info['art'] += tmdb_info['art']


            elif code[1] == 'T':
                tmp = SiteTmdbMovie.info(code)
                if tmp['ret'] == 'success':
                    info = tmp['data']
            return info                    


        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    

    def change_tmdb_actor_info(self, tmdb_info, portal_info):
        if len(portal_info) == 0:
            return
        for tmdb in tmdb_info:
            logger.debug(tmdb['name'])
            for portal in portal_info:
                logger.debug(portal['originalname'])
                if tmdb['name'] == portal['originalname']:
                    tmdb['name'] = portal['name']
                    tmdb['role'] = portal['role']
                    break
            