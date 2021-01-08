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
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app
from framework.util import Util
from framework.common.util import headers, get_json_with_auth_session
from framework.common.plugin import LogicModuleBase, default_route_socketio
# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicKtv(LogicModuleBase):
    db_default = {
        'ktv_db_version' : '1',
        'ktv_daum_keyword' : u'나의 아저씨',
        'ktv_plex_is_proxy_preview' : u'True',
        'ktv_plex_landscape_to_art' : u'True',
        'ktv_censored_plex_art_count' : u'3',
    }

    def __init__(self, P):
        super(LogicKtv, self).__init__(P, 'setting')
        self.name = 'ktv'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name

        try:
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except:
            return render_template('sample.html', title='%s - %s' % (P.package_name, sub))

    def process_ajax(self, sub, req):
        try:
            if sub == 'test':
                keyword = req.form['keyword']
                call = req.form['call']
                if call == 'daum':
                    from lib_metadata import SiteDaumTv
                    ModelSetting.set('jav_ktv_daum_keyword', keyword)
                    ret = {}
                    ret['search'] = SiteDaumTv.search(keyword)
                    if ret['search']['ret'] == 'success':
                        ret['info'] = self.info(ret['search']['data']['code'], ret['search']['data']['title'])


                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})

    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            if call == 'plex':
                return jsonify(self.search(req.args.get('keyword')))
        elif sub == 'info':
            return jsonify(self.info(req.args.get('code'), req.args.get('title')))

    #########################################################

    def search(self, keyword):
        ret = []
        #site_list = ModelSetting.get_list('jav_censored_order', ',')
        site_list = ['daum']
        for idx, site in enumerate(site_list):
            from lib_metadata import SiteDaumTv 

            data = SiteDaumTv.search(keyword)
            if data['ret'] == 'success':
                ret = data['data']
           
            return ret


            if data['ret'] == 'success':
                if idx != 0:
                    for item in data['data']:
                        item['score'] += -1
                ret += data['data']
                ret = sorted(ret, key=lambda k: k['score'], reverse=True)  
            if all_find:
                continue
            else:
                if len(ret) > 0 and ret[0]['score'] > 95:
                    break
        return ret
    

    def info(self, code, title):
        ret = None
        if ret is None:
            if code[1] == 'D':
                from lib_metadata import SiteDaumTv
                tmp = SiteDaumTv.info(code, title)
                if tmp['ret'] == 'success':
                    ret = tmp['data']
         
                logger.debug(ret['extra_info']['kakao_id'])
                ret['extras'] = SiteDaumTv.get_kakao_video(ret['extra_info']['kakao_id'])



                import tmdbsimple
                tmdbsimple.API_KEY = 'f090bb54758cabf231fb605d3e3e0468'

                tmdb_search = tmdbsimple.Search().tv(query =ret['title'], language='ko')
                #match_ret = self.match_tmdb(ret, tmdb)

                ret['tmdb'] = {}
                ret['tmdb']['tmdb_search'] = tmdb_search
                for t in tmdb_search['results']:
                    if ret['premiered'] == t['first_air_date']:
                        ret['tmdb']['tmdb_id'] = t['id']
                        break
                if 'tmdb_id' in ret['tmdb']:
                    tmdb = tmdbsimple.TV(ret['tmdb']['tmdb_id'])
                    ret['tmdb']['info'] = tmdb.info()
                    ret['tmdb']['images'] = tmdb.images()
                    ret['tmdb']['info'] = tmdb.credits()

                logger.debug(tmdb_search)


        if ret is not None:
            ret['plex_is_proxy_preview'] = ModelSetting.get_bool('ktv_plex_is_proxy_preview')
            ret['plex_is_landscape_to_art'] = ModelSetting.get_bool('ktv_plex_landscape_to_art')
            ret['plex_art_count'] = ModelSetting.get_int('ktv_censored_plex_art_count')

            return ret

