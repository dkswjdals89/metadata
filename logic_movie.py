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
from lib_metadata import SiteNaverMovie, SiteTmdbMovie, SiteWatchaMovie, SiteUtil, SiteDaumMovie

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
        'movie_use_tmdb' : 'True',
        'movie_use_watcha' : 'True',
        'movie_use_watcha_collection_like_count' : '100',

        'movie_total_test_search' : '',
        'movie_total_test_info' : '',

        'movie_naver_test_search' : '',
        'movie_naver_test_info' : '',

        'movie_daum_test_search' : '',
        'movie_daum_test_info' : '',

        'movie_tmdb_test_search' : '',
        'movie_tmdb_test_info' : '',

        'movie_watcha_test_search' : '',
        'movie_watcha_test_info' : '',
        'movie_watcha_cookies' : '',

    }

    module_map = {'naver':SiteNaverMovie, 'daum':SiteDaumMovie, 'tmdb':SiteTmdbMovie}

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
                elif call == 'daum':
                    if mode == 'search':
                        ret = SiteDaumMovie.search(keyword, year=year)
                    elif mode == 'info':
                        ret = SiteDaumMovie.info(param)
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
                elif call == 'watcha':
                    if mode == 'search':
                        ret = SiteWatchaMovie.search(keyword, year=year)
                    elif mode == 'info':
                        ret = SiteWatchaMovie.info(keyword)
                    elif mode == 'search_api':
                        ret = SiteWatchaMovie.search_api(keyword)
                    elif mode == 'info_api':
                        ret = SiteWatchaMovie.info_api(param)                    

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
            
            if call == 'plex' or call == 'kodi':
                return jsonify(self.search(req.args.get('keyword'), year, manual=manual))
        elif sub == 'info':
            call = req.args.get('call')
            data = self.info(req.args.get('code'))
            if call == 'kodi':
                data = SiteUtil.info_to_kodi(data)
            return jsonify(data)
        elif sub == 'stream':
            ret = self.stream(req.args.get('code'))
            mode = req.args.get('mode')
            if mode == 'redirect':
                if 'hls' in ret:
                    return redirect(ret['hls'])
            

            #logger.debug(json.dumps(ret, indent=4))
            return jsonify(ret)

            logger.debug(ret)
            return redirect(ret['url'])
            import time
            from tool_base import ToolBaseFile
            #return ToolBaseFile.write(text, savepath)

            filename = os.path.join(path_data, 'tmp', '%s.strm' % str(time.time()))
            ToolBaseFile.write(ret['url'], filename)
            #return send_file(filename)
            tmp = 'https://sjva-dev.soju6jan.com/file/data/tmp/%s?apikey=0005298000' % os.path.basename(filename)
            logger.debug(tmp)
            return redirect(tmp)


            if ret['site'] == 'tving':

                return ret['url']
                return redirect(ret['url'])
            else:
                return jsonify(ret)

    #########################################################

    def search(self, keyword, year, manual=False):
        ret = []
        site_list = ModelSetting.get_list('movie_first_order', ',')
        #site_list = ['naver']

        # 한글 영문 분리
        split_index = -1
        is_include_kor = False
        for index, c in enumerate(keyword):
            if ord(u'가') <= ord(c) <= ord(u'힣'):
                is_include_kor = True
                split_index = -1
            elif ord('a') <= ord(c.lower()) <= ord('z'):
                is_include_eng = True
                if split_index == -1:
                    split_index = index
            elif ord('0') <= ord(c.lower()) <= ord('9') or ord(' '):
                pass
            else:
                split_index = -1

        if is_include_kor and split_index != -1:
            kor = keyword[:split_index].strip()
            eng = keyword[split_index:].strip()
        else:
            kor = None
            eng = None

        
        for key in [keyword, kor, eng]:
            logger.debug('key : %s', key)
            if key is None:
                continue

            for idx, site in enumerate(site_list):
                logger.debug(site)
                if site == 'daum':
                    continue
                if year is None:
                    year = 1900
                else:
                    try: year = int(year)
                    except: year = 1900
                site_data = self.module_map[site].search(key, year=year)
                
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
            if len(ret) > 0 and ret[0]['score'] > 85:
                break
        ret = sorted(ret, key=lambda k: k['score'], reverse=True)  
        return ret




    def info(self, code):
        try:
            info = None
            is_tmdb = False
            if code[1] == 'N':
                tmp = SiteNaverMovie.info(code)
                if tmp['ret'] == 'success':
                    info = tmp['data']
                
            elif code[1] == 'T':
                tmp = SiteTmdbMovie.info(code)
                if tmp['ret'] == 'success':
                    info = tmp['data']
                is_tmdb = True

            if is_tmdb == False and ModelSetting.get_bool('movie_use_tmdb'):
                tmdb_info = None
                if info['country'][0] == u'한국':
                    tmdb_search = SiteTmdbMovie.search(info['title'], year=info['year'])
                else:
                    tmdb_search = SiteTmdbMovie.search(info['title'], year=info['year'])
                    #tmdb_search = SiteTmdbMovie.search(info['originaltitle'], year=info['year'])
                if tmdb_search['ret'] == 'success' and len(tmdb_search['data'])>0:
                    #logger.debug(tmdb_search['data'][0]['title'])
                    if tmdb_search['data'][0]['score'] > 85 or ('title_en' in info['extra_info'] and SiteUtil.compare(info['extra_info']['title_en'], tmdb_search['data'][0]['originaltitle'])):
                        tmdb_data = SiteTmdbMovie.info(tmdb_search['data'][0]['code'])
                        if tmdb_data['ret'] == 'success':
                            tmdb_info = tmdb_data['data']
                
                if tmdb_info is not None:
                    #logger.debug(json.dumps(tmdb_info, indent=4))
                    logger.debug('tmdb_info : %s', tmdb_info['title'])
                    info['extras'] += tmdb_info['extras']
                    self.change_tmdb_actor_info(tmdb_info['actor'], info['actor'])
                    info['actor'] = tmdb_info['actor']
                    info['art'] += tmdb_info['art']
                    info['code_list'] += tmdb_info['code_list']
                    if info['plot'] == '':
                        info['plot'] = tmdb_info['plot']


            if ModelSetting.get_bool('movie_use_watcha'):
                watcha_info = None
                watcha_search = SiteWatchaMovie.search(info['title'], year=info['year'])
                
                if watcha_search['ret'] == 'success' and len(watcha_search['data'])>0:
                    if watcha_search['data'][0]['score'] > 85:
                        watcha_data = SiteWatchaMovie.info(watcha_search['data'][0]['code'])
                        if watcha_data['ret'] == 'success':
                            watcha_info = watcha_data['data']
                
                if watcha_info is not None:
                    info['review'] = watcha_info['review']
                    info['code_list'] += watcha_info['code_list']
                    info['code_list'].append(['google_search', u'영화 ' + info['title']])
                    
                    for idx, review in enumerate(info['review']):
                        if idx >= len(info['code_list']):
                            break
                        if info['code_list'][idx][0] == 'naver_id':
                            review['source'] = u'네이버'
                            review['link'] = 'https://movie.naver.com/movie/bi/mi/basic.nhn?code=%s' % info['code_list'][idx][1]
                        elif info['code_list'][idx][0] == 'tmdb_id':
                            review['source'] = u'TMDB'
                            review['link'] = 'https://www.themoviedb.org/movie/%s?language=ko' % info['code_list'][idx][1]
                        elif info['code_list'][idx][0] == 'imdb_id':
                            review['source'] = u'IMDB'
                            review['link'] = 'https://www.imdb.com/title/%s/' % info['code_list'][idx][1]
                        elif info['code_list'][idx][0] == 'watcha_id':
                            review['source'] = u'왓챠 피디아'
                            review['link'] = 'https://pedia.watcha.com/ko-KR/contents/%s' % info['code_list'][idx][1]
                        elif info['code_list'][idx][0] == 'google_search':
                            review['source'] = u'구글 검색'
                            review['link'] = 'https://www.google.com/search?q=%s' % info['code_list'][idx][1]
                    info['tag'] += watcha_info['tag']
            return info                    


        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    

    def change_tmdb_actor_info(self, tmdb_info, portal_info):
        if len(portal_info) == 0:
            return
        for tmdb in tmdb_info:
            #logger.debug(tmdb['name'])
            for portal in portal_info:
                #logger.debug(portal['originalname'])
                if tmdb['name'] == portal['originalname']:
                    tmdb['name'] = portal['name']
                    tmdb['role'] = portal['role']
                    break


    def stream(self, code):
        try:
            logger.debug('code : %s', code)
            if code[1] == 'V': 
                import framework.tving.api as Tving
                data = Tving.get_stream_info_by_web('movie', code[2:], 'stream50')
                #logger.debug(data)
                return data['play_info']
            elif code[1] == 'W': 
                import framework.wavve.api as Wavve
                data = {'wavve_url':Wavve.streaming2('movie', code[2:], 'FHD', return_url=True)}
                return data
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

