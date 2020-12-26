# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect
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

class LogicJavCensored(LogicModuleBase):
    db_default = {
        'db_version' : '1',
        'jav_censored_use_sjva' : 'False',
        'jav_censored_order' : 'dmm, javbus',
        'jav_censored_plex_title_format' : '[{title}] {tagline}',
        'jav_censored_plex_is_proxy_preview' : 'True',
        'jav_censored_plex_landscape_to_art' : 'True',
        'jav_censored_plex_art_count' : '0',
        'jav_censored_actor_order' : 'javdbs, hentaku',
        'jav_censored_plex_manual_mode' : 'True',

        'jav_censored_avdbs_use_proxy' : 'False',
        'jav_censored_avdbs_proxy_url' : '',

        'jav_censored_javbus_code' : 'ssni-900',
        'jav_censored_javbus_use_proxy' : 'False',
        'jav_censored_javbus_proxy_url' : '',
        'jav_censored_javbus_image_mode' : '0',

        'jav_censored_dmm_code' : 'ssni-900',
        'jav_censored_dmm_use_proxy' : 'False',
        'jav_censored_dmm_proxy_url' : '',
        'jav_censored_dmm_image_mode' : '0',
        'jav_censored_dmm_cookie' : 'age_check_done=1',
    }

    def __init__(self, P):
        super(LogicJavCensored, self).__init__(P, 'setting')
        self.name = 'jav_censored'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        #if sub in ['setting']:
        return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        return render_template('sample.html', title='%s - %s' % (P.package_name, sub))

    def process_ajax(self, sub, req):
        try:
            if sub == 'test':
                code = req.form['code']
                call = req.form['call']
                if call == 'javbus':
                    from lib_metadata.site_javbus import SiteJavbus
                    ModelSetting.set('jav_censored_javbus_code', code)
                    ret = {}
                    ret['search'] = SiteJavbus.search(code, proxy_url=ModelSetting.get('jav_censored_javbus_proxy_url') if ModelSetting.get_bool('jav_censored_javbus_use_proxy') else None, image_mode=ModelSetting.get('jav_censored_javbus_image_mode'))
                    if ret['search']['ret'] == 'success':
                        if len(ret['search']['ret']) > 0:
                            ret['info'] = self.info(ret['search']['data'][0]['code'])
                elif call == 'dmm':
                    from lib_metadata.site_dmm import SiteDmm
                    ModelSetting.set('jav_censored_dmm_code', code)
                    ret = {}
                    ret['search'] = SiteDmm.search(code, proxy_url=ModelSetting.get('jav_censored_dmm_proxy_url') if ModelSetting.get_bool('jav_censored_dmm_use_proxy') else None, image_mode=ModelSetting.get('jav_censored_dmm_image_mode'))
                    if ret['search']['ret'] == 'success':
                        if len(ret['search']['ret']) > 0:
                            ret['info'] = self.info(ret['search']['data'][0]['code'])
                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})

    def process_api(self, sub, req):
        if sub == 'search':
            return jsonify(self.search(req.args.get('keyword'), bool(req.args.get('manual'))))
        elif sub == 'info':
            return jsonify(self.info(req.args.get('code')))

    def setting_save_after(self):
        from lib_metadata.site_dmm import SiteDmm
        SiteDmm.dmm_headers['Cookie'] = ModelSetting.get('jav_censored_dmm_cookie')

    def plugin_load(self):
        from lib_metadata.site_dmm import SiteDmm
        SiteDmm.dmm_headers['Cookie'] = ModelSetting.get('jav_censored_dmm_cookie')
    #########################################################


    def search(self, keyword, manual):
        ret = []
        logger.debug(manual)
        logger.debug(type(manual))
        site_list = ModelSetting.get_list('jav_censored_order', ',')
        logger.debug(site_list)
        for idx, site in enumerate(site_list):
            if site == 'javbus':
                from lib_metadata.site_javbus import SiteJavbus
                data = SiteJavbus.search(
                    keyword, 
                    proxy_url=ModelSetting.get('jav_censored_javbus_proxy_url') if ModelSetting.get_bool('jav_censored_javbus_use_proxy') else None, 
                    image_mode=ModelSetting.get('jav_censored_javbus_image_mode'))
                if data['ret'] == 'success':
                    if idx != 0:
                        for item in data['data']:
                            item['score'] += -1
                    ret += data['data']
                    ret = sorted(ret, key=lambda k: k['score'], reverse=True)  
            elif site == 'dmm':
                from lib_metadata.site_dmm import SiteDmm
                data = SiteDmm.search(
                    keyword, 
                    proxy_url=ModelSetting.get('jav_censored_dmm_proxy_url') if ModelSetting.get_bool('jav_censored_dmm_use_proxy') else None, 
                    image_mode=ModelSetting.get('jav_censored_dmm_image_mode'))
                if data['ret'] == 'success':
                    if idx != 0:
                        for item in data['data']:
                            item['score'] += -1
                    ret += data['data']
                    ret = sorted(ret, key=lambda k: k['score'], reverse=True)  
            if manual:
                if ModelSetting.get_bool('jav_censored_plex_manual_mode'):
                    continue
                else:
                    if len(ret) > 0 and ret[0]['score'] == 100:
                        break
            else:
                if len(ret) > 0 and ret[0]['score'] == 100:
                    break
        return ret
    

    def info(self, code):
        ret = None
        if ModelSetting.get_bool('jav_censored_use_sjva'):
            ret = MetadataServerUtil.get_metadata(code)
        if ret is None:
            if code[1] == 'B':
                from lib_metadata.site_javbus import SiteJavbus
                ret = self.info2(code, SiteJavbus, 'javbus')
            elif code[1] == 'D':
                from lib_metadata.site_dmm import SiteDmm
                ret = self.info2(code, SiteDmm, 'dmm')
        
        if ret is not None:
            ret['plex_is_proxy_preview'] = ModelSetting.get_bool('jav_censored_plex_is_proxy_preview')
            ret['plex_is_landscape_to_art'] = ModelSetting.get_bool('jav_censored_plex_landscape_to_art')
            ret['plex_art_count'] = ModelSetting.get_int('jav_censored_plex_art_count')

            if ret['actor'] is not None:
                for item in ret['actor']:
                    self.process_actor(item)

            ret['title'] = ModelSetting.get('jav_censored_plex_title_format').format(
                originaltitle=ret['originaltitle'], 
                plot=ret['plot'],
                title=ret['title'],
                sorttitle=ret['sorttitle'],
                runtime=ret['runtime'],
                country=ret['country'],
                premiered=ret['premiered'],
                year=ret['year'],
                actor=ret['actor'][0]['name'] if ret['actor'] is not None and len(ret['actor']) > 0 else '',
                tagline=ret['tagline']
            )
            return ret

    def info2(self, code, site_class, site_name):
        from lib_metadata.site_javbus import SiteJavbus
        image_mode = ModelSetting.get('jav_censored_{site_name}_image_mode'.format(site_name=site_name))
        data = site_class.info(
            code,
            proxy_url=ModelSetting.get('jav_censored_{site_name}_proxy_url'.format(site_name=site_name)) if ModelSetting.get_bool('jav_censored_{site_name}_use_proxy'.format(site_name=site_name)) else None, 
            image_mode=image_mode)
        if data['ret'] == 'success':
            ret = data['data']
            if ModelSetting.get_bool('jav_censored_use_sjva') and image_mode == '3' and SystemModelSetting.get('trans_type') == '1' and SystemModelSetting.get('trans_google_api_key') != '' and len(ret['thumb']) == 2 and ret['thumb'][0]['value'].find('discordapp.net') != -1 and ret['thumb'][1]['value'].find('discordapp.net') != -1:
                MetadataServerUtil.set_metadata(code, ret, ret['title'].lower())
        return ret

    def process_actor(self, entity_actor):
        actor_site_list = ModelSetting.get_list('jav_censored_actor_order', ',')
        for site in actor_site_list:
            if site == 'hentaku':
                from lib_metadata.site_hentaku import SiteHentaku
                self.process_actor2(entity_actor, SiteHentaku, 'H', None)
            elif site == 'javdbs':
                from lib_metadata.site_avdbs import SiteAvdbs
                self.process_actor2(entity_actor, SiteAvdbs, 'A', ModelSetting.get('jav_censored_avdbs_proxy_url') if ModelSetting.get_bool('jav_censored_avdbs_use_proxy') else None)
            if entity_actor['name'] is not None:
                return
        if entity_actor['name'] is None:
            entity_actor['name'] = entity_actor['originalname'] 


    def process_actor2(self, entity_actor, site_class, site_char, proxy_url):
        if ModelSetting.get_bool('jav_censored_use_sjva'):
            data = MetadataServerUtil.get_metadata('A' + site_char + entity_actor['originalname'])
            if data is not None:
                entity_actor['name'] = data['name']
                entity_actor['name2'] = data['name2']
                entity_actor['thumb'] = data['thumb']
                return
        from lib_metadata.site_hentaku import SiteHentaku
        site_class.get_actor_info(entity_actor, proxy_url=proxy_url)
        if entity_actor['name'] is not None and entity_actor['thumb'] is not None and entity_actor['thumb'].find('discordapp.net') != -1:
            MetadataServerUtil.set_metadata('A'+ site_char + entity_actor['originalname'], entity_actor, entity_actor['originalname'])
            return
