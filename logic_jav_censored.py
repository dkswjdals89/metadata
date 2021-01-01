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
        'jav_censored_db_version' : '1',
        'jav_censored_use_sjva' : 'False',
        'jav_censored_order' : 'dmm, javbus',
        'jav_censored_plex_title_format' : '[{title}] {tagline}',
        'jav_censored_plex_is_proxy_preview' : 'True',
        'jav_censored_plex_landscape_to_art' : 'True',
        'jav_censored_plex_art_count' : '0',
        'jav_censored_actor_order' : 'hentaku, avdbs',
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
        'jav_censored_actor_test_name' : '',
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
            elif sub == 'actor_test':
                ModelSetting.set('jav_censored_actor_test_name', req.form['name'])
                entity_actor = {'originalname' : req.form['name']}
                call = req.form['call']
                if call == 'avdbs':
                    from lib_metadata.site_avdbs import SiteAvdbs
                    self.process_actor2(entity_actor, SiteAvdbs, ModelSetting.get('jav_censored_avdbs_proxy_url') if ModelSetting.get_bool('jav_censored_avdbs_use_proxy') else None)
                elif call == 'hentaku':
                    from lib_metadata.site_hentaku import SiteHentaku
                    self.process_actor2(entity_actor, SiteHentaku, None)
                return jsonify(entity_actor)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})

    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            if call == 'plex':
                manual = bool(req.args.get('manual'))
                all_find = ModelSetting.get_bool('jav_censored_plex_manual_mode') if manual else False
                return jsonify(self.search(req.args.get('keyword'), all_find=all_find, do_trans=manual))
        elif sub == 'info':
            return jsonify(self.info(req.args.get('code')))

    def setting_save_after(self):
        from lib_metadata.site_dmm import SiteDmm
        SiteDmm.dmm_headers['Cookie'] = ModelSetting.get('jav_censored_dmm_cookie')

    def plugin_load(self):
        from lib_metadata.site_dmm import SiteDmm
        SiteDmm.dmm_headers['Cookie'] = ModelSetting.get('jav_censored_dmm_cookie')
    #########################################################


    def search(self, keyword, all_find=False, do_trans=True):
        ret = []
        site_list = ModelSetting.get_list('jav_censored_order', ',')
        for idx, site in enumerate(site_list):
            if site == 'javbus':
                from lib_metadata.site_javbus import SiteJavbus as SiteClass
            elif site == 'dmm':
                from lib_metadata.site_dmm import SiteDmm as SiteClass

            data = SiteClass.search(
                keyword, 
                do_trans=do_trans,
                proxy_url=ModelSetting.get('jav_censored_{site_name}_proxy_url'.format(site_name=SiteClass.site_name)) if ModelSetting.get_bool('jav_censored_{site_name}_use_proxy'.format(site_name=SiteClass.site_name)) else None, 
                image_mode=ModelSetting.get('jav_censored_{site_name}_image_mode'.format(site_name=SiteClass.site_name)))
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
    

    def info(self, code):
        ret = None
        if ModelSetting.get_bool('jav_censored_use_sjva'):
            #logger.debug('aaaaaaaaaaaaaaa')
            ret = MetadataServerUtil.get_metadata(code)
            #logger.debug(ret)
        if ret is None:
            if code[1] == 'B':
                from lib_metadata.site_javbus import SiteJavbus
                ret = self.info2(code, SiteJavbus)
            elif code[1] == 'D':
                from lib_metadata.site_dmm import SiteDmm
                ret = self.info2(code, SiteDmm)
        
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

    def info2(self, code, SiteClass):
        image_mode = ModelSetting.get('jav_censored_{site_name}_image_mode'.format(site_name=SiteClass.site_name))
        data = SiteClass.info(
            code,
            proxy_url=ModelSetting.get('jav_censored_{site_name}_proxy_url'.format(site_name=SiteClass.site_name)) if ModelSetting.get_bool('jav_censored_{site_name}_use_proxy'.format(site_name=SiteClass.site_name)) else None, 
            image_mode=image_mode)
        if data['ret'] == 'success':
            ret = data['data']
            if ModelSetting.get_bool('jav_censored_use_sjva') and image_mode == '3' and SystemModelSetting.get('trans_type') == '1' and SystemModelSetting.get('trans_google_api_key') != '' and len(ret['thumb']) == 2 and ret['thumb'][0]['value'].find('discordapp.net') != -1 and ret['thumb'][1]['value'].find('discordapp.net') != -1:
                MetadataServerUtil.set_metadata(code, ret, ret['title'].lower())
        return ret

    def process_actor(self, entity_actor):
        actor_site_list = ModelSetting.get_list('jav_censored_actor_order', ',')
        logger.debug('actor_site_list : %s', actor_site_list)
        for site in actor_site_list:
            if site == 'hentaku':
                from lib_metadata.site_hentaku import SiteHentaku
                self.process_actor2(entity_actor, SiteHentaku, None)
            elif site == 'avdbs':
                from lib_metadata.site_avdbs import SiteAvdbs
                self.process_actor2(entity_actor, SiteAvdbs, ModelSetting.get('jav_censored_avdbs_proxy_url') if ModelSetting.get_bool('jav_censored_avdbs_use_proxy') else None)
            if entity_actor['name'] is not None:
                return
        if entity_actor['name'] is None:
            entity_actor['name'] = entity_actor['originalname'] 


    def process_actor2(self, entity_actor, SiteClass, proxy_url):
        
        if ModelSetting.get_bool('jav_censored_use_sjva'):
            logger.debug('A' + SiteClass.site_char + entity_actor['originalname'])
            data = MetadataServerUtil.get_metadata('A' + SiteClass.site_char + entity_actor['originalname'])
            if data is not None and data['name'] is not None and data['name'] != '' and data['name'] != data['originalname'] and data['thumb'] is not None and data['thumb'].find('discordapp.net') != -1:
                logger.info('Get actor info by server : %s %s', entity_actor['originalname'], SiteClass)
                logger.debug(data)
                entity_actor['name'] = data['name']
                entity_actor['name2'] = data['name2']
                entity_actor['thumb'] = data['thumb']
                entity_actor['site'] = data['site']
                return
        logger.debug('Get actor... :%s', SiteClass)
        SiteClass.get_actor_info(entity_actor, proxy_url=proxy_url)
        #logger.debug('direct actor info : %s %s', entity_actor['name'], entity_actor['originalname'])
        logger.debug(entity_actor)
        if 'name' in entity_actor and entity_actor['name'] is not None and entity_actor['name'] != '' and 'thumb' in entity_actor and entity_actor['thumb'] is not None and entity_actor['thumb'].find('discordapp.net') != -1:
            MetadataServerUtil.set_metadata('A'+ SiteClass.site_char + entity_actor['originalname'], entity_actor, entity_actor['originalname'])
            return
        

