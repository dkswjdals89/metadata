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
from lib_metadata import SiteNaverMovie

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicMovie(LogicModuleBase):
    db_default = {
        'movie_db_version' : '1',

        'movie_naver_test_search' : '',
        'movie_naver_test_info' : '',
    }

    module_map = {'naver':SiteNaverMovie}

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
                param = req.form['param']
                call = req.form['call']
                mode = req.form['mode']
                if call == 'naver':
                    ModelSetting.set('movie_%s_test_%s' % (call, mode), param)
                    if mode == 'search':
                        ret = SiteNaverMovie.search(param)
                    elif mode == 'info':
                        ret = SiteNaverMovie.info(param)
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
        #site_list = ModelSetting.get_list('jav_censored_order', ',')
        site_list = ['naver']
        for idx, site in enumerate(site_list):
            logger.debug(site)
            if year is None:
                year = 1900
            else:
                try: year = int(year)
                except: year = 1900
            site_data = self.module_map[site].search(keyword, year=year)
            
            if site_data['ret'] == 'success':
                ret += site_data['data']
                #logger.info(u'Movie 검색어 : %s site : %s 매칭', keyword, site)
                if manual:
                    continue
                else:
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

            return info                    


        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    