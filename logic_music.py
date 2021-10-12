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
from framework.common.util import headers
from plugin import LogicModuleBase, default_route_socketio

# 패키지
from lib_metadata import SiteVibe, SiteUtil

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicMusic(LogicModuleBase):
    db_default = {
        'music_db_version' : '1',
        'music_test_artist_search' : '',
        'music_test_artist_info' : '',

        'music_test_album_search' : '',
        'music_test_album_info' : '',

    }

    def __init__(self, P):
        super(LogicMusic, self).__init__(P, 'test')
        self.name = 'music'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        arg['sub2'] = sub
        try:
            return render_template(f'{P.package_name}_{self.name}_{sub}.html', arg=arg)
        except:
            return render_template('sample.html', title=f'{P.package_name}/{self.name}/{sub}')

    def process_ajax(self, sub, req):
        try:
            if sub == 'command':
                command = req.form['command'].strip()
                if command == 'test':
                    arg1 = req.form['arg1'].strip()
                    keyword = req.form['arg2'].strip()
                    logger.debug(f"[{command}] [{arg1}] [{keyword}]")
                    what, site, mode, json_mode = arg1.split('|')
                    ret = {'ret':'success', 'modal':None}
                    if what == 'artist':
                        if mode == 'search':
                            ModelSetting.set('music_test_artist_search', keyword)
                            ret['json'] = self.artist_search(keyword, json_mode)
                        elif mode == 'info':
                            ModelSetting.set('music_test_artist_info', keyword)
                            ret['json'] = self.artist_info(keyword, json_mode)
                    elif what == 'album':
                        if mode == 'search':
                            ModelSetting.set('music_test_album_search', keyword)
                            tmp = keyword.split('|')
                            if len(tmp) == 0:
                                ret['json'] = self.album_search(None, keyword, json_mode)
                            elif len(tmp) == 1:
                                ret['modal'] = self.album_search(tmp[0], tmp[1], json_mode)
                        elif mode == 'info':
                            ModelSetting.set('music_test_album_info', keyword)
                            ret['json'] = self.album_info(keyword, json_mode)
                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})
        


    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            manual = bool(req.args.get('manual'))
            if call == 'plex' or call == 'kodi':
                return jsonify(self.search(req.args.get('keyword'), manual=manual))
        elif sub == 'info':
            call = req.args.get('call')
            data = self.info(req.args.get('code'), req.args.get('title'))
            if call == 'kodi':
                data = SiteUtil.info_to_kodi(data)
            return jsonify(data)
        elif sub == 'episode_info':
            return jsonify(self.episode_info(req.args.get('code')))
            #return jsonify(self.episode_info(req.args.get('code'), req.args.get('no'), req.args.get('premiered'), req.args.get('param')))
            #return jsonify(self.episode_info(req.args.get('code'), req.args.get('no'), py_urllib.unquote(req.args.get('param'))))

    #########################################################

    def artist_search(self, keyword, mode):
        data = SiteVibe.search_artist(keyword, mode)
        return data
        

        ret = {}

        #site_list = ModelSetting.get_list('jav_censored_order', ',')
        site_list = ['daum', 'tving', 'wavve']
        for idx, site in enumerate(site_list):
            logger.debug(site)
            site_data = self.module_map[site].search(keyword)
            #logger.debug(data)

            if site_data['ret'] == 'success':
                ret[site] = site_data['data']
                logger.info(u'KTV 검색어 : %s site : %s 매칭', keyword, site)
                if manual:
                    continue
                return ret
        return ret

    def info(self, code, title):
        try:
            show = None
            if code[1] == 'D':
                tmp = SiteDaumTv.info(code, title)
                if tmp['ret'] == 'success':
                    show = tmp['data']

                if 'kakao_id' in show['extra_info'] and show['extra_info']['kakao_id'] is not None and ModelSetting.get_bool('ktv_use_kakaotv'):
                    show['extras'] = SiteDaumTv.get_kakao_video(show['extra_info']['kakao_id'])

                if ModelSetting.get_bool('ktv_use_tmdb'):
                    from lib_metadata import SiteTmdbTv
                    tmdb_id = SiteTmdbTv.search_tv(show['title'], show['premiered'])
                    show['extra_info']['tmdb_id'] = tmdb_id
                    if tmdb_id is not None:
                        show['tmdb'] = {}
                        show['tmdb']['tmdb_id'] = tmdb_id
                        SiteTmdbTv.apply(tmdb_id, show, apply_image=True, apply_actor_image=True)

                if 'tving_episode_id' in show['extra_info']:
                    SiteTvingTv.apply_tv_by_episode_code(show, show['extra_info']['tving_episode_id'], apply_plot=True, apply_image=True )
                else: #use_tving 정도
                    SiteTvingTv.apply_tv_by_search(show, apply_plot=True, apply_image=True)

                SiteWavveTv.apply_tv_by_search(show)
                #extra
                if ModelSetting.get_bool('ktv_use_theme'):
                    extra = MetadataServerUtil.get_meta_extra(code)
                    if extra is not None:
                        if 'themes' in extra:
                            show['extra_info']['themes'] = extra['themes']

            elif code[1] == 'V': 
                tmp = SiteTvingTv.info(code)
                if tmp['ret'] == 'success':
                    show = tmp['data']
            elif code[1] == 'W': 
                tmp = SiteWavveTv.info(code)
                if tmp['ret'] == 'success':
                    show = tmp['data']

            logger.info('KTV info title:%s code:%s tving:%s wavve:%s', title, code, show['extra_info']['tving_id'] if 'tving_id' in show['extra_info'] else None, show['extra_info']['wavve_id'] if 'wavve_id' in show['extra_info'] else None)

            if show is not None:
                show['ktv_episode_info_order'] = ModelSetting.get_list('ktv_episode_info_order', ',')
                return show

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    
    
    def episode_info(self, code):
        try:
            if code[1] == 'D':
                from lib_metadata import SiteDaumTv
                data = SiteDaumTv.episode_info(code, include_kakao=ModelSetting.get_bool('ktv_use_kakaotv_episode'))
                if data['ret'] == 'success':
                    return data['data']

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())