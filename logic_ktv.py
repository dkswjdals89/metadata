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
from lib_metadata import SiteDaumTv, SiteTmdbTv, SiteTvingTv, SiteWavveTv

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicKtv(LogicModuleBase):
    db_default = {
        'ktv_db_version' : '1',
        'ktv_use_kakaotv' : 'True',
        'ktv_use_kakaotv_episode' : 'False',

        'ktv_daum_keyword' : '',

        'ktv_wavve_search' : '',
        'ktv_wavve_program' : '',

        'ktv_tving_search' : '',
        'ktv_tving_program' : '',
    }

    module_map = {'daum':SiteDaumTv, 'tving':SiteTvingTv, 'wavve':SiteWavveTv, 'tmdb':SiteTmdbTv}

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
                    ModelSetting.set('ktv_daum_keyword', keyword)
                    ret = {}
                    ret['search'] = SiteDaumTv.search(keyword)
                    if ret['search']['ret'] == 'success':
                        ret['info'] = self.info(ret['search']['data']['code'], ret['search']['data']['title'])
                return jsonify(ret)
            elif sub == 'wavve_test':
                import  framework.wavve.api as Wavve
                keyword = req.form['keyword']
                mode = req.form['mode']
                ModelSetting.set('ktv_wavve_%s' % mode, keyword)
                if mode == 'search':
                    ret = Wavve.search_tv(keyword)
                elif mode == 'program':
                    ret = {}
                    ret['program'] = Wavve.vod_programs_programid(keyword)
                    ret['episodes'] = []
                    page = 1
                    while True:
                        episode_data = Wavve.vod_program_contents_programid(keyword, page=page)
                        ret['episodes'] += episode_data['list']
                        page += 1
                        if episode_data['pagecount'] == episode_data['count']:# or page == 6:
                            break
                return jsonify(ret)
            elif sub == 'tving_test':
                import  framework.tving.api as Tving
                keyword = req.form['keyword']
                mode = req.form['mode']
                ModelSetting.set('ktv_tving_%s' % mode, keyword)
                if mode == 'search':
                    ret = Tving.search_tv(keyword)
                elif mode == 'program':
                    ret = {}
                    ret['program'] = Tving.get_program_programid(keyword)
                    ret['episodes'] = []
                    page = 1
                    while True:
                        episode_data = Tving.get_frequency_programid(keyword, page=page)
                        for epi in episode_data['body']['result']:
                            ret['episodes'].append(epi['episode'])
                        page += 1
                        if episode_data['body']['has_more'] == 'N':
                            break
                return jsonify(ret) 
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})

    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            manual = bool(req.args.get('manual'))
            if call == 'plex':
                return jsonify(self.search(req.args.get('keyword'), manual=manual))
        elif sub == 'info':
            return jsonify(self.info(req.args.get('code'), req.args.get('title')))
        elif sub == 'episode_info':
            return jsonify(self.episode_info(req.args.get('code')))
            #return jsonify(self.episode_info(req.args.get('code'), req.args.get('no'), req.args.get('premiered'), req.args.get('param')))
            #return jsonify(self.episode_info(req.args.get('code'), req.args.get('no'), py_urllib.unquote(req.args.get('param'))))

    #########################################################

    def search(self, keyword, manual=False):
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

                if show['extra_info']['kakao_id'] is not None and ModelSetting.get_bool('ktv_use_kakaotv'):
                    show['extras'] = SiteDaumTv.get_kakao_video(show['extra_info']['kakao_id'])

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
                show['plex_is_proxy_preview'] = ModelSetting.get_bool('ktv_plex_is_proxy_preview')
                show['plex_is_landscape_to_art'] = ModelSetting.get_bool('ktv_plex_landscape_to_art')
                show['plex_art_count'] = ModelSetting.get_int('ktv_censored_plex_art_count')
                show['plex_episode_art'] = ['daum', 'wavve', 'tving']
                return show

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    
    
    def episode_info(self, code):
        try:
            logger.debug('code : %s', code)
            if code[1] == 'D':
                from lib_metadata import SiteDaumTv
                data = SiteDaumTv.episode_info(code, include_kakao=ModelSetting.get_bool('ktv_use_kakaotv_episode'))
                if data['ret'] == 'success':
                    return data['data']

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())