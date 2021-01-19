# -*- coding: utf-8 -*-
# python
import os, traceback, time, json

# third-party
import requests
from flask import Blueprint, request, send_file, redirect, jsonify

# sjva 공용
from framework import app, path_data, check_api, py_urllib, SystemModelSetting
from framework.logger import get_logger
from framework.util import Util
from framework.common.plugin import get_model_setting, Logic, default_route
# 패키지
#########################################################

class P(object):
    package_name = __name__.split('.')[0]
    logger = get_logger(package_name)
    blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
    menu = {
        'main' : [package_name, u'메타데이터'],
        'sub' : [
            ['ktv', u'국내 방송'], ['movie', u'영화 (개발중)'], ['jav_censored', u'JavCensored'], ['jav_censored_ama', u'JavCensored AMA'], ['log', u'로그']
        ], 
        'category' : 'tool',
        'sub2' : {
            'ktv' : [
                ['setting', u'설정'], ['daum', 'Daum'], ['wavve', '웨이브'], ['tving', '티빙'], 
            ],
            'movie' : [
                ['setting', u'설정'], ['test', '테스트'], #['naver', '네이버'], ['daum', 'Daum'], ['tmdb', 'TMDB'], ['watcha', '왓챠'],  ['tmdb', 'TMDB'], ['wavve', '웨이브'], ['tving', '티빙'], 
            ],
            'jav_censored' : [
                ['setting', u'설정'], ['dmm', 'DMM'], ['javbus', 'Javbus'],
            ],
            'jav_censored_ama' : [
                ['setting', u'설정'], ['jav321', 'Jav321'], 
            ],
        }
    }  

    plugin_info = {
        'version' : '0.2.0.0',
        'name' : package_name,
        'category_name' : 'tool',
        'icon' : '',
        'developer' : u'soju6jan',
        'description' : u'Metadata',
        'home' : 'https://github.com/soju6jan/%s' % package_name,
        'more' : '',
    }
    ModelSetting = get_model_setting(package_name, logger)
    logic = None
    module_list = None
    home_module = 'setting'

    
def initialize():
    try:
        app.config['SQLALCHEMY_BINDS'][P.package_name] = 'sqlite:///%s' % (os.path.join(path_data, 'db', '{package_name}.db'.format(package_name=P.package_name)))
        from framework.util import Util
        Util.save_from_dict_to_json(P.plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

        from .logic_ktv import LogicKtv
        from .logic_jav_censored import LogicJavCensored
        from .logic_jav_censored_ama import LogicJavCensoredAma
        from .logic_ott_show import LogicOttShow
        from .logic_movie import LogicMovie
        P.module_list = [LogicKtv(P), LogicJavCensored(P), LogicJavCensoredAma(P), LogicOttShow(P), LogicMovie(P)]
        P.logic = Logic(P)
        default_route(P)
    except Exception as e: 
        P.logger.error('Exception:%s', e)
        P.logger.error(traceback.format_exc())

logger = P.logger

initialize()





#########################################################
# API - 외부
#########################################################
@P.blueprint.route('/api/<sub>', methods=['GET', 'POST'])
@check_api
def baseapi(sub):
    try:
        if sub == 'image':
            from PIL import Image
            # 2020-06-02 proxy 사용시 포스터처리
            image_url = request.args.get('url')
            logger.debug(image_url)
            method = ModelSetting.get('javdb_landscape_poster')
            if method == '0':
                if FileProcess.Vars.proxies is None:
                    return redirect(image_url)
                else:
                    im = Image.open(requests.get(image_url, stream=True, proxies=FileProcess.Vars.proxies).raw)
                    filename = os.path.join(path_data, 'tmp', 'rotate.jpg')
                    im.save(filename)
                    return send_file(filename, mimetype='image/jpeg')
            
            im = Image.open(requests.get(image_url, stream=True, proxies=FileProcess.Vars.proxies).raw)
            width,height = im.size
            logger.debug(width)
            logger.debug(height)
            if height > width * 1.5:
                return redirect(image_url)
            if method == '1':
                if width > height:
                    im = im.rotate(-90, expand=True)
            elif method == '2':
                if width > height:
                    im = im.rotate(90, expand=True)
            elif method == '3':
                new_height = int(width * 1.5)
                new_im = Image.new('RGB', (width, new_height))
                new_im.paste(im, (0, int((new_height-height)/2)))
                im = new_im

            filename = os.path.join(path_data, 'tmp', 'rotate.jpg')
            im.save(filename)
            return send_file(filename, mimetype='image/jpeg')

        elif sub == 'image_proxy':
            from PIL import Image
            image_url = py_urllib.unquote_plus(request.args.get('url'))
            proxy_url = request.args.get('proxy_url')
            if proxy_url is not None:
                proxy_url = py_urllib.unquote_plus()

            logger.debug('image_url : %s', image_url)
            #2020-09-21 핸드쉐이크 에러
            from system.logic_command import SystemLogicCommand
            filename = os.path.join(path_data, 'tmp', 'proxy_%s.jpg' % str(time.time()) )

            #im = Image.open(requests.get(image_url, stream=True, verify=False, proxies=FileProcess.Vars.proxies).raw)
            #im.save(filename)
            if proxy_url is not None and proxy_url != '':
                # 알파인 도커 wget 에 -e 옵션 안먹음
                #tmp = image_url.split('//')
                #if len(tmp) == 2:
                #    image_url = tmp[1]
                #command = ['wget', '-O', filename, image_url, '-e', 'use_proxy=yes', '-e', 'http_proxy=%s' % ModelSetting.get('proxy_url').replace('https://', '').replace('http://', '')]
                #command = ['curl', '-o', filename, image_url, '-x', proxy_url.replace('https://', '').replace('http://', '')]
                command = ['curl', '-o', filename, image_url, '-x', proxy_url]
                logger.debug(' '.join(command))
                ret = SystemLogicCommand.execute_command_return(command)
            else:
                #tmp = image_url.split('//')
                #if len(tmp) == 2:
                #    image_url = tmp[1]
                ret = SystemLogicCommand.execute_command_return(['curl', '-o', filename, image_url])
            
            return send_file(filename, mimetype='image/jpeg')
        elif sub == 'discord_proxy':
            from tool_expand import ToolExpandDiscord
            image_url = py_urllib.unquote_plus(request.args.get('url'))
            ret = ToolExpandDiscord.discord_proxy_image(image_url)
            #logger.debug(ret)
            return redirect(ret)
            from PIL import Image
            
            im = Image.open(requests.get(ret, stream=True, verify=False).raw)
            filename = os.path.join(path_data, 'tmp', 'proxy.jpg')
            im.save(filename)
            return send_file(filename, mimetype='image/jpeg')
        
        elif sub == 'youtube':
            command = ['youtube-dl', '-f', 'best', '-g', 'https://www.youtube.com/watch?v=%s' % request.args.get('youtube_id')]
            from system.logic_command import SystemLogicCommand
            ret = SystemLogicCommand.execute_command_return(command).strip()
            return jsonify({'ret':'success', 'url':ret})

        elif sub == 'video':
            site = request.args.get('site')
            param = request.args.get('param')
            if site == 'naver':
                from lib_metadata import SiteNaverMovie
                ret = SiteNaverMovie.get_video_url(param)
                #return redirect(ret)
            #return jsonify({'ret':'success', 'url':ret, 'site':site})
            return redirect(ret)

        """
        elif sub == 'image_process':
            mode = request.args.get('mode')
            if mode == 'landscape_to_poster':
                from PIL import Image
                image_url = py_urllib.unquote_plus(request.args.get('url'))
                im = Image.open(requests.get(image_url, stream=True).raw)
                width, height = im.size
                left = width/1.895734597
                top = 0
                right = width
                bottom = height
                filename = os.path.join(path_data, 'tmp', 'proxy_%s.jpg' % str(time.time()) )
                poster = im.crop((left, top, right, bottom))
                poster.save(filename)
                return send_file(filename, mimetype='image/jpeg')
        """

    except Exception as e:
        logger.debug('Exception:%s', e)
        logger.debug(traceback.format_exc())


@P.blueprint.route('/normal/<sub>', methods=['GET', 'POST'])
def basenormal(sub):
    try:
        if sub == 'image_process.jpg':
            mode = request.args.get('mode')
            if mode == 'landscape_to_poster':
                from PIL import Image
                image_url = py_urllib.unquote_plus(request.args.get('url'))
                im = Image.open(requests.get(image_url, stream=True).raw)
                width, height = im.size
                left = width/1.895734597
                top = 0
                right = width
                bottom = height
                filename = os.path.join(path_data, 'tmp', 'proxy_%s.jpg' % str(time.time()) )
                poster = im.crop((left, top, right, bottom))
                poster.save(filename)
                return send_file(filename, mimetype='image/jpeg')
                    
    except Exception as e:
        logger.debug('Exception:%s', e)
        logger.debug(traceback.format_exc())




