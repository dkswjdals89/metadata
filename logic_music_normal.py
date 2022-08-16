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
from lib_metadata import SiteVibe, SiteUtil, SiteMelon, SiteLastfm

from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

from lib_metadata.server_util import MetadataServerUtil
from support.base import d
#########################################################

name = 'music_normal'

class LogicMusicNormal(LogicModuleBase):
    db_default = {
        f'{name}_db_version' : '1',
        f'{name}_test_artist_search' : '',
        f'{name}_test_artist_info' : '',
        f'{name}_test_album_search' : '',
        f'{name}_test_album_info' : '',
        f'{name}_test_song' : '',

        f'{name}_artist_poster_count' : '1',
        f'{name}_artist_art_count' : '1',

        f'{name}_use_lastfm' : 'True',
        f'{name}_use_lastfm_artist_youtube' : 'True',
        f'{name}_use_lastfm_artist_image' : 'True',

    }

    def __init__(self, P):
        super(LogicMusicNormal, self).__init__(P, 'test')
        self.name = name

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
                    what, site, mode, return_format = arg1.split('|')
                    ret = {'ret':'success', 'modal':None}
                    if what == 'artist':
                        if mode == 'search':
                            ModelSetting.set(f'{name}_test_artist_search', keyword)
                            ret['json'] = self.search_artist(keyword, return_format)
                        elif mode == 'info':
                            ModelSetting.set(f'{name}_test_artist_info', keyword)
                            ret['json'] = self.info_artist(keyword)
                    elif what == 'album':
                        if mode == 'search':
                            ModelSetting.set(f'{name}_test_album_search', keyword)
                            #tmp = keyword.split('|')
                            #if len(tmp) == 1:
                            #    ret['json'] = self.album_search(None, keyword, return_format)
                            #elif len(tmp) == 2:
                            #    ret['json'] = self.album_search(tmp[0], tmp[1], return_format)
                            ret['json'] = self.search_album(keyword, return_format)
                        elif mode == 'info':
                            ModelSetting.set(f'{name}_test_album_info', keyword)
                            ret['json'] = self.info_album(keyword)
                    elif what == 'song':
                        ModelSetting.set(f'{name}_test_song', keyword)
                        ret['json'] = self.song(keyword)

                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})
        


    def process_api(self, sub, req):
        if sub == 'search':
            call = req.args.get('call')
            manual = bool(req.args.get('manual'))
            param = req.args.get('param')
            if call == 'plex' or call == 'kodi':
                return jsonify(self.search(req.args.get('keyword'), param, manual=manual))
        elif sub == 'info':
            call = req.args.get('call')
            param = req.args.get('param')
            data = self.info(req.args.get('code'), param, req.args.get('title'))
            if call == 'kodi':
                data = SiteUtil.info_to_kodi(data)
            return jsonify(data)
        elif sub == 'song':
            call = req.args.get('call')
            param = req.args.get('param')
            ret = self.song(req.args.get('song_id'), mode=req.args.get('mode'), artist=req.args.get('artist'), track_title=req.args.get('track'), filename=req.args.get('filename'))
            return jsonify(ret)

    #########################################################


    def search(self, keyword, param, manual=False):
        logger.info(f"param:{param} keyword:{keyword}")
        if param == 'artist':
            return self.search_artist(keyword)
        elif param == 'album':
            return self.search_album(keyword)

    def info(self, code, param, title):
        if param == 'artist':
            return self.info_artist(code)
        elif param == 'album':
            return self.info_album(code)

    # 아티스트
    def search_artist(self, keyword, return_format='normal'):
        keyword = keyword.split('|')[0]
        data = SiteMelon.search_artist(keyword, return_format)
        return data['data']
    
    def info_artist(self, code):
        data = SiteMelon.info_artist(code)
        if ModelSetting.get_bool(f'{name}_use_lastfm'):
            try:
                data = SiteLastfm.info_artist(data, photo=ModelSetting.get_bool(f'{name}_use_lastfm_artist_image'), youtube=ModelSetting.get_bool(f'{name}_use_lastfm_artist_youtube'))
            except Exception as e:
                logger.debug(f'Exception:{e}')
                logger.debug(traceback.format_exc())

        data['poster'] = []
        data['art'] = []
        
        poster_count = ModelSetting.get_int(f'{name}_artist_poster_count')
        if poster_count > 0:
            if 'photo_lastfm' not in data:
                data['poster'].append(data['image'])
            else:
                try:
                    for i in range(poster_count):
                        data['poster'].append(data['photo_lastfm'][0])
                        del data['photo_lastfm'][0]
                except:
                    pass

        art_count = ModelSetting.get_int(f'{name}_artist_art_count')
        if art_count > 0:
            if 'photo_lastfm' not in data:
                for i in range(art_count):
                    if len(data['photo']) == 0:
                        break
                    data['art'].append(data['photo'][0])
                    del data['photo'][0]
            else:
                for i in range(art_count):
                    if len(data['photo_lastfm']) == 0:
                        break
                    data['art'].append(data['photo_lastfm'][0])
                    del data['photo_lastfm'][0]
        data['photo'] = []
        data['photo_lastfm'] = []
        return data

    # 앨범
    def search_album(self, keyword, return_format='normal'):
        data = SiteMelon.search_album(keyword, return_format)
        return data['data']

    def info_album(self, code):
        data = SiteMelon.info_album(code)
        return data


    def song(self, song_id, mode='txt', artist=None, track_title=None, filename=None):
        data = SiteMelon.info_song(song_id)
        #logger.debug(d(data))
        if data['ret'] == 'success':
            tmp = ''
            if '작사' in data['producer']:
                tmp += f"작사: {' '.join(data['producer']['작사'])}" + '\n'
            if '작곡' in data['producer']:
                tmp += f"작곡: {' '.join(data['producer']['작곡'])}" + '\n'
            if '편곡' in data['producer']:
                tmp += f"편곡: {' '.join(data['producer']['편곡'])}" + '\n'
            data['lyric'] = f"{tmp}\n{data['lyric']}".strip()
            return data
        

        data = self.vibe_get_lyric(mode, artist, track_title, filename, song_id)


        

    def vibe_get_lyric(self, mode, artist, track_title, filename, song_id):
        try:
            logger.warning(f"{artist} - {track_title} - {filename} - {song_id} - {mode}")
            ret = {}
            url = f"https://apis.naver.com/vibeWeb/musicapiweb/v4/searchall?query={py_urllib.quote(artist.replace('&', ','))}%20{py_urllib.quote(track_title)}"
            data = requests.get(url, headers={'accept' : 'application/json'}).json()
            logger.warning(url)
            tracks = data['response']['result']['trackResult']['tracks']
            logger.warning(self.dump(tracks))
            track = None
            for item in tracks:

                if item['trackTitle'].replace(' ', '').strip() == track_title.replace(' ', '').strip():
                    track = item
                    break
                if track_title in item['trackTitle']:
                    track = item
                    break
            if track is None:
                logger.warning('정확히 일치하는 제목이 없음')
                #if len(tracks) > 0:
                #    track = tracks[0]
                return None
     
            #logger.warning(d(track))
            if track['hasLyric']:
                url = f"https://apis.naver.com/vibeWeb/musicapiweb/track/{track['trackId']}/info"
                tmp = requests.get(url, headers={'accept' : 'application/json'}).json()
                logger.warning(url)
                
                track_data = tmp['response']['result']['trackInformation']
                info= [
                    f"작사  {','.join([x['lyricWriterName'] for x in track_data['lyricWriters']])}",
                    f"작곡  {','.join([x['composerName'] for x in track_data['composers']])}",
                    f"편곡  {','.join([x['arrangerName'] for x in track_data['arrangers']])}", ""]
                if mode == 'lrc' and track_data['hasSyncLyric'] == 'Y':
                    ret['ret'] = 'success'
                    ret['lyric'] = '\n\n'.join([f"[00:00:01]{x}" for x in info]) + "\n\n" + self.change_to_lrc(track_data['syncLyric'])
                elif mode == 'txt' and track_data['hasLyric'] == 'Y':
                    ret['ret'] = 'success'
                    ret['lyric'] = '\n'.join([x for x in info]) + "\n" + track_data['lyric']
                else:
                    ret['ret'] = 'fail'
                    ret['log'] = '가사가 없습니다.'
            else:
                logger.warning("track['hasLyric'] is false!!")
                ret['ret'] = 'fail'
                ret['log'] = '가사가 없습니다.'
            logger.debug(f"get_lyric return is {ret['ret']}")
        except Exception as exception:
            logger.debug('Exception:%s', exception)
            logger.debug(traceback.format_exc())
            ret['ret'] = 'fail'
            if mode == 'lrc':
                ret['log'] = f'[00:00:01]에러가 발생했습니다.\n[00:00:02]{exception}'
            else:
                ret['log'] = f'에러가 발생했습니다.\n{exception}'
        return ret

    def change_to_lrc(self, data):
        logger.error(data)
        def tt(t1):
            tmps = t1.split('.')
            t1 = int(tmps[0])
            t3 = '00' if len(tmps) == 1 else tmps[1].zfill(2)
            return f"[{str(int(t1/60)).zfill(2)}:{str(t1%60).zfill(2)}:{t3}]"

        ret = ''
        for line in data.split('#'):
            tmp = line.split('|')
            if len(tmp) == 2 and not tmp[0].startswith('@'):
                ret += f"{tt(tmp[0])}{tmp[1]}\n\n"

        return ret