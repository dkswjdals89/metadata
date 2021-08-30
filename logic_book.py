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
from system import SystemLogicTrans
from tool_base import d
# 패키지
from lib_metadata import SiteNaverBook, SiteUtil

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
name = 'book'
#########################################################

class LogicBook(LogicModuleBase):
    db_default = {
        f'{name}_db_version' : '1',
        f'{name}_naver_titl' : '',
        f'{name}_naver_auth' : '',
        f'{name}_naver_cont' : '',
        f'{name}_naver_isbn' : '',
        f'{name}_naver_publ' : '',
        f'{name}_naver_code' : '',
    }

    def __init__(self, P):
        super(LogicBook, self).__init__(P, 'naver')
        self.name = name

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        try:
            return render_template(f'{package_name}_{self.name}_{sub}.html', arg=arg)
        except Exception as exception: 
            logger.error(f'Exception : {exception}')
            logger.error(traceback.format_exc()) 
            return render_template('sample.html', title=f'{P.package_nam}/{self.name}/{sub}')


    def process_ajax(self, sub, req):
        try:
            ret = {}
            if sub == 'command':
                command = req.form['command']
                if command == 'search_naver':
                    tmp = req.form['arg1'].split('|')
                    ModelSetting.set(f'{name}_naver_titl', tmp[0])
                    ModelSetting.set(f'{name}_naver_auth', tmp[1])
                    ModelSetting.set(f'{name}_naver_cont', tmp[2])
                    ModelSetting.set(f'{name}_naver_isbn', tmp[3])
                    ModelSetting.set(f'{name}_naver_publ', tmp[4])
                    mode = req.form['arg2']
                    if mode == 'api':
                        data = SiteNaverBook.search_api(*tmp)
                    else:
                        data = SiteNaverBook.search(*tmp)
                    ret['modal'] = d(data)
                elif command == 'info_naver':
                    code = req.form['arg1']
                    ModelSetting.set(f'{name}_naver_code', code)
                    data = SiteNaverBook.info(code)
                    ret['modal'] = d(data)
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
            data = SiteNaverBook.info(req.args.get('code'))
            if call == 'plex':
                try:
                    data['poster'] = SiteUtil.process_image_book(data['poster'])
                except:
                    pass

            return jsonify(data)
        
        elif sub == 'top_image':
            url = req.args.get('url')
            ret = SiteUtil.process_image_book(url)
            return jsonify(ret)
            
    #########################################################

    def search(self, keyword, manual=False):
        ret = {}
        tmp = keyword.split('|')
        logger.debug(tmp)
        if len(tmp) == 2:
            data = SiteNaverBook.search(tmp[0], tmp[1], '', '', '')
        elif len(tmp) == 1:
            data = SiteNaverBook.search(tmp[0], '', '', '', '')
        if data['ret'] == 'success':
            return data['data']
