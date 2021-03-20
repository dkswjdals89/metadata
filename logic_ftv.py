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
from collections import OrderedDict

# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, py_urllib
from framework.util import Util
from framework.common.util import headers, get_json_with_auth_session
from framework.common.plugin import LogicModuleBase, default_route_socketio
from system import SystemLogicTrans

# 패키지
from lib_metadata import SiteDaumTv, SiteTmdbTv, SiteTvdbTv, SiteUtil, SiteWatchaTv, SiteTmdbFtv, SiteWavveTv, SiteTvingTv

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicFtv(LogicModuleBase):
    db_default = {
        'ftv_db_version' : '1',
        'ftv_total_test_search' : '',
        'ftv_total_test_info' : '',

        'ftv_tvdb_test_search' : '',
        'ftv_tvdb_test_info' : '',

        'ftv_tmdb_test_search' : '',
        'ftv_tmdb_test_info' : '',
        'ftv_tmdb_test_info_season' : '',
        
        'ftv_daum_test_search' : '',
        'ftv_daum_test_info' : '',

        'ftv_watcha_test_search' : '',
        'ftv_watcha_test_info' : '',

        'ftv_use_extra_match' : 'True',
        'ftv_use_extra_season' : 'True',
        'ftv_use_extra_video' : 'True',

        'ftv_use_meta_server' : 'True',
        'ftv_season_order' : 'wavve, tving, daum',
        
        'ftv_translate_option' : '1',
        'ftv_use_theme' : 'True',
        'ftv_option_actor' : '0', # tmdb 이미지 유지후 매칭된 배우만 한글적용, 국내 사이트 정보도 전체 대체, 

    }

    module_map = {'daum':SiteDaumTv, 'tvdb':SiteTvdbTv, 'tmdb':SiteTmdbTv, 'watcha':SiteWatchaTv, 'tmdb':SiteTmdbFtv}

    


    def __init__(self, P):
        super(LogicFtv, self).__init__(P, 'setting')
        self.name = 'ftv'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        try:
            if sub == 'setting':
                arg['cache_info'] = self.get_cache_info()
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except:
            return render_template('sample.html', title='%s - %s' % (P.package_name, sub))

    def process_ajax(self, sub, req):
        try:
            if sub == 'test':
                keyword = req.form['keyword'].strip()
                call = req.form['call']
                mode = req.form['mode']
                ModelSetting.set('ftv_%s_test_%s' % (call, mode), keyword)
                tmps = keyword.split('|')
                year = None
                if len(tmps) == 2:
                    keyword = tmps[0].strip()
                    try: year = int(tmps[1].strip())
                    except: year = None
                if call == 'total':
                    if mode == 'search':
                        manual = (req.form['manual'] == 'manual')
                        ret = self.search(keyword, year=year, manual=manual)
                    elif mode == 'info':
                        ret = self.info(keyword)
                else:
                    SiteClass = self.module_map[call]
                    if mode == 'search':
                        ret = SiteClass.search(keyword, year=year)
                    elif mode == 'info':
                        ret = SiteClass.info(keyword)
                    elif mode == 'search_api':
                        ret = SiteClass.search_api(keyword)
                    elif mode == 'info_api':
                        ret = SiteClass.info_api(keyword)
                    elif mode == 'info_season':
                        ret = SiteClass.info_season(keyword)
                    elif mode == 'info_season_api':
                        ret = SiteClass.info_season_api(keyword)
                return jsonify(ret)
            elif sub == 'reset_cache':
                self.reset_cache()
                return jsonify(self.get_cache_info())
            
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})
        


    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            try: year = int(req.args.get('year'))
            except: year = None
            manual = bool(req.args.get('manual'))
            if call == 'plex' or call == 'kodi':
                return jsonify(self.search(req.args.get('keyword'), manual=manual, year=year))
        elif sub == 'info':
            call = req.args.get('call')
            data = self.info(req.args.get('code'))
            if call == 'kodi':
                data = SiteUtil.info_to_kodi(data)
            return jsonify(data)

    #########################################################

    def search(self, keyword, year=None, manual=False):
        keyword = keyword.split(u'시즌')[0]
        logger.debug('FTV search keyword:[%s] year:[%s] manual:[%s]', keyword, year, manual)
        tmdb_ret = SiteTmdbFtv.search(keyword, year=year)
        #logger.debug(json.dumps(tmdb_ret, indent=4))
        ret = []
        if tmdb_ret['ret'] == 'success':
            if tmdb_ret['data'][0]['score'] >= 95:
                return tmdb_ret['data']
            else:
                ret += tmdb_ret['data']

        if SiteUtil.is_include_hangul(keyword):
            watcha_ret = SiteWatchaTv.search(keyword, year=year)
            if watcha_ret['ret'] == 'success':
                #logger.debug(json.dumps(watcha_ret, indent=4))
                en_keyword = watcha_ret['data'][0]['title_en']
                logger.debug(en_keyword)
                logger.debug(en_keyword)
                logger.debug(en_keyword)
                if en_keyword is not None:
                    tmdb_ret = SiteTmdbFtv.search(en_keyword, year=year)
                    #logger.debug(json.dumps(tmdb_ret, indent=4))
                    
                    if tmdb_ret['ret'] == 'success': #and tmdb_ret['data'][0]['score'] >= 95:
                        #    return tmdb_ret['data']
                        #return tmdb_ret['data']
                        ret += tmdb_ret['data']

        return ret


    def info(self, code):
        logger.debug('FTV info [%s]', code)
        try:
            tmp = code.split('_')
            if len(tmp) == 1:
                if code[1] == 'T':
                    tmdb_info = SiteTmdbFtv.info(code)
                    if tmdb_info['ret'] != 'success':
                        return
                    data = tmdb_info['data']
                    if ModelSetting.get_bool('ftv_use_meta_server'):
                        self.info_use_metaserver(data)

                    if ModelSetting.get_bool('ftv_use_extra_match'):
                        self.info_extra_match(data)
                    data['use_theme'] = ModelSetting.get_bool('ftv_use_theme')
                    self.set_cache('my', code, data)
                    return data
            elif len(tmp) == 2:
                if code[1] == 'T':
                    tmdb_info = SiteTmdbFtv.info_season(code)
                    if tmdb_info['ret'] != 'success':
                        return
                    data = tmdb_info['data']
                    if ModelSetting.get_bool('ftv_use_extra_match') and ModelSetting.get_bool('ftv_use_extra_season'):
                        self.info_extra_season(data)
                    self.process_trans(data)
                    return data
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    def process_trans(self, data):
        mode = ModelSetting.get('ftv_translate_option')
        if mode == '0':
            return data
        elif mode == '1':
            function = SystemLogicTrans.trans_google
        elif mode == '2':
            function = SystemLogicTrans.trans_papago

        for key, tmdb_epi in data['episodes'].items():
            try:
                if tmdb_epi['is_title_kor'] == False:
                    tmdb_epi['title'] = function(tmdb_epi['title'], source='en')
                if tmdb_epi['is_plot_kor'] == False:
                    tmdb_epi['plot'] = function(tmdb_epi['plot'], source='en')
            except:
                pass
        return data


    def info_use_metaserver(self, data, season_no=-1):
        if season_no == -1:
            pass
        else:
            pass

    
        


    # 시즌정보 
    def info_extra_season(self, data):
        try:
            trash, series_info = self.get_cache('my', data['parent_code'])
            
            meta_server_season_dict = None
            
            if ModelSetting.get_bool('ftv_use_meta_server'):
                extra = self.get_meta_extra(series_info['code'])
                if extra is not None:
                    if 'seasons' in extra:
                        if str(data['season_no']) in extra['seasons']:
                            meta_server_season_dict = extra['seasons'][str(data['season_no'])]

                if meta_server_season_dict:
                    logger.debug(meta_server_season_dict)
                    for site in ModelSetting.get_list('ftv_season_order', ','):
                        if site in meta_server_season_dict:
                            value = meta_server_season_dict[site]
                            if site == 'daum':
                                tmp = value.split('|')
                                daum_season_info = SiteDaumTv.info('KD' + tmp[0], tmp[1])
                                if daum_season_info is not None and daum_season_info['ret'] == 'success':
                                    daum_season_info = daum_season_info['data']
                                    if len(daum_season_info['extra_info']['episodes'].keys()) > 0:
                                        #logger.debug(json.dumps(daum_season_info, indent=4))
                                        self.apply_season_info_by_daum(data, daum_season_info)
                                        return
                            elif site in ['wavve', 'tving']:
                                if self.apply_season_info(data, value, site):
                                    return

                            
                
          
            tmp = self.get_daum_search(series_info)
            #tmp = self.get_daum_search(data['series_title'], data['series_year'], data['series_season_count'])
            if tmp is None:
                return data
            title = tmp[0]
            daum_search_data = tmp[1]['data']
            if True or data['studio'].lower().find(daum_search_data['studio'].lower()) != -1 or daum_search_data['studio'].lower().find(data['studio'].lower()) != -1:
                
                daum_season_info = None
                for season_no, season in enumerate(daum_search_data['series']):
                    season_no += 1
                    if data['season_no'] == season_no:
                        logger.debug('daum on ftv code:[%s], title:[%s]', season['code'], season['title'])
                        daum_season_info = SiteDaumTv.info(season['code'], season['title'])
                        if daum_season_info is not None and daum_season_info['ret'] == 'success':
                            daum_season_info = daum_season_info['data']
                        else:
                            logger.debug('Daum fail : %s', title)
                        break
  
                if daum_season_info:
                    self.apply_season_info_by_daum(data, daum_season_info)

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        
        return data



    def apply_season_info(self, tmdb_info, code, site):
        try:
            if site == 'wavve':
                tmp = SiteWavveTv.info('XX'+code)
            elif site == 'tving':
                tmp = SiteTvingTv.info('XX'+code)
            #logger.debug(json.dumps(tmp, indent=4))
            if tmp['ret'] == 'success':
                source_episodes = tmp['data']['extra_info']['episodes']
                for key, tmdb_epi in tmdb_info['episodes'].items():
                    if int(key) in source_episodes:
                        src_epi = source_episodes[int(key)][site]
                        if src_epi['title'] != '':
                            tmdb_epi['title'] = src_epi['title']
                            tmdb_epi['is_title_kor'] = True
                        if src_epi['plot'] != '':
                            tmdb_epi['plot'] = src_epi['plot']
                            tmdb_epi['is_plot_kor'] = True
                        if src_epi['thumb'] != '':
                            tmdb_epi['art'].append(src_epi['thumb'])
                return True
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        return False       



    def apply_season_info_by_daum(self, tmdb_info, daum_info):
        daum_episodes = daum_info['extra_info']['episodes']

        for key, tmdb_epi in tmdb_info['episodes'].items():
            if int(key) in daum_episodes:
                #logger.debug('apply_season_info_by_daum..')
                daum_epi = SiteDaumTv.episode_info(daum_episodes[int(key)]['daum']['code'], is_ktv=False)['data']
                tmdb_epi['title'] = daum_epi['title'] if daum_epi['title'] != '' else tmdb_epi['title']
                if daum_epi['title'] != '':
                    tmdb_epi['title'] = daum_epi['title']
                    tmdb_epi['is_title_kor'] = True

                if daum_epi['plot'] != '':
                    tmdb_epi['plot'] = daum_epi['plot'].replace(daum_epi['title'], '').strip()
                    tmdb_epi['is_plot_kor'] = True
                #logger.debug(json.dumps(daum_epi, indent=4))




    def info_extra_match(self, data):
        try:
            daum_list = []
            if ModelSetting.get_bool('ftv_use_meta_server'):
                extra = self.get_meta_extra(data['code'])

                logger.debug('FTV Extra : %s', extra)
                if extra is not None:
                    if 'themes' in extra:
                        data['extra_info']['themes'] = extra['themes']
                    if 'seasons' in extra:
                        keys = extra['seasons'].keys()
                        keys = [int(x) for x in keys]
                        keys = sorted(keys)
                        for key in keys:
                            if 'daum' in extra['seasons'][str(key)]:
                                tmp = extra['seasons'][str(key)]['daum'].split('|')
                                daum_list.append(['KD'+tmp[0], tmp[1]])

            if len(daum_list) == 0:
                tmp = self.get_daum_search(data)
                #logger.debug('get_daum_search ret : %s', tmp)
                if tmp is not None:
                    title = tmp[0]
                    daum_search_data = tmp[1]['data']
                    if SiteUtil.is_include_hangul(data['title']) == False:
                        data['title'] = title.split(u'시즌')[0].split(u'1기')[0].strip()
                    for season_no, season in enumerate(daum_search_data['series'][:len(data['seasons'])]):        
                        daum_list.append([season['code'], season['title']])


            logger.debug('탐색 : %s', daum_list)
            daum_actor_list = OrderedDict()
            for daum_one_of_list in daum_list:
                #logger.debug('222222222222')
                #logger.debug(daum_one_of_list[0])
                #logger.debug(daum_one_of_list[1])
                daum_season_info = SiteDaumTv.info(daum_one_of_list[0], daum_one_of_list[1])
                if daum_season_info['ret'] == 'success':
                    daum_season_info = daum_season_info['data']
                if data['plot'] == '': #화이트퀸
                    data['plot'] = daum_season_info['plot']
                for actor in daum_season_info['actor']:
                    if actor['name'] not in daum_actor_list:
                        daum_actor_list[actor['name']] = actor
                #logger.debug(daum_season_info['extras'])
                if ModelSetting.get_bool('ftv_use_extra_video'):
                    data['extras'] += daum_season_info['extras']
                if len(daum_actor_list.keys()) > 30:
                    break
                #logger.debug(json.dumps(season_info, indent=4))
            # end of each season
            #logger.debug(daum_actor_list)

            option_actor = ModelSetting.get('ftv_option_actor')
            if option_actor == '1': # daum 대체
                data['actor'] = []
                for key, value in daum_actor_list.items():
                    data['actor'].append({'name':value['name'], 'role':value['role'], 'image':value['thumb']})
            else:
                for key, value in daum_actor_list.items():
                    tmp = SiteDaumTv.get_actor_eng_name(key)
                    if tmp is not None:
                        value['eng_name'] = tmp 
                        logger.debug('[%s] [%s]', key, value['eng_name'])
                    else:
                        value['eng_name'] = None

                for actor in data['actor']:
                    actor['is_kor_name'] = False
                    for key, value in daum_actor_list.items():
                        if value['eng_name'] is None:
                            continue
                        for tmp_name in value['eng_name']:
                            if actor['name_original'].lower().replace(' ', '') == tmp_name.lower().replace(' ', ''):
                                actor['name'] = actor['name_ko'] = value['name']
                                actor['role'] = value['role']
                                actor['is_kor_name']= True
                                del daum_actor_list[key]
                                break
                        if actor['is_kor_name']:
                            break
                    actor['role'] = actor['role'].replace('&#39;', '\"')
                if option_actor == '2' or option_actor == '3':
                    tmp1 = []
                    tmp2 = []
                    for actor in data['actor']:
                        if actor['is_kor_name']:
                            tmp1.append(actor)
                        else:
                            tmp2.append(actor)
                    data['actor'] = tmp1 + tmp2
                if option_actor == '3':
                    for key, value in daum_actor_list.items():
                        logger.debug('22 [%s] [%s]', key, value['eng_name'])
                        value['image'] = value['thumb']
                        del value['eng_name']
                        del value['thumb']
                        data['actor'].append(value)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    #####################################################################################
    # 매칭 유틸

    def __get_daum_search(self, tmdb_title, series_year, season_count):
        logger.debug('get_daum_search title:[%s], year:[%s], season_count:[%s]', tmdb_title, series_year, season_count)
        title = re.sub(r'\(\d{4}\)', '', tmdb_title).strip()
        
        search_title = []
        if SiteUtil.is_include_hangul(title):
            if season_count == 1:
                search_title = [title]
            else:
                search_title = [u'%s 시즌 1' % title, u'%s 1기' % title]
        else:
            watcha_search = SiteWatchaTv.search(title, year=series_year, season_count=season_count)
            if watcha_search['ret'] != 'success':
                #logger.debug(json.dumps(watcha_search, indent=4))
                logger.debug('watcha search fail : %s %s %s', title, series_year, season_count)
                return
            tmp = watcha_search['data'][0]['title'] 
            if season_count == 1:
                search_title = [tmp]
            else:
                search_title = [u'%s 시즌 1' % tmp, u'%s 1기' % tmp]
        
        for title in search_title:
            daum_search = SiteDaumTv.search(title, year=series_year)
            if daum_search['ret'] == 'success':
                logger.debug('title : %s', title)
                return [title, daum_search]


    #####################################################################################
    # 캐시 활용
    def get_daum_search(self, series_info):
        unique = series_info['code']+'_daum'
        cache_ret = self.get_cache('my', unique)
        if cache_ret[0]:
            data = cache_ret[1]
        else:
            data = self.__get_daum_search(series_info['title'], series_info['year'], len(series_info['seasons']))
            self.set_cache('server', unique, data)
        return data



    def get_meta_extra(self, code):
        cache_ret = self.get_cache('server', code)
        if cache_ret[0]:
            extra = cache_ret[1]
        else:
            extra = MetadataServerUtil.get_meta_extra(code)
            self.set_cache('server', code, extra)
        return extra


    #####################################################################################
    #  캐시 유틸

    memory_cache = {'my':{}, 'server':{}}
    def get_cache(self, mode, code):
        if code in self.memory_cache[mode]:
            return [True, self.memory_cache[mode][code]]
        else:
            return [False]

    def set_cache(self, mode, code, data):
        if len(self.memory_cache[mode].keys()) > 100:
            self.memory_cache[mode] = {}
        self.memory_cache[mode][code] = data

    def reset_cache(self):
        self.memory_cache = {'my':{}, 'server':{}}
    
    def get_cache_info(self):
        return 'my : %s / server : %s' % (len(self.memory_cache['my'].keys()), len(self.memory_cache['server'].keys()) )



        
