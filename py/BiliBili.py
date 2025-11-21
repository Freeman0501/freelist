# -*- coding: utf-8 -*-
# @Author  : Doubebly
# @Time    : 2025/7/15 12:10
# @Function:

import time
from urllib.parse import quote
import requests
import re
import sys
import base64
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return self.vod.name

    def init(self, extend):
        self.vod = BiliBili()

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        return self.vod.homeContent(filter)

    def homeVideoContent(self):
        return self.vod.homeVideoContent()

    def categoryContent(self, cid, page, filter, ext):
        return self.vod.categoryContent(cid, page, filter, ext)

    def detailContent(self, did):
        return self.vod.detailContent(did)

    def searchContent(self, key, quick, page='1'):
        return self.vod.searchContent(key, quick, page='1')

    def playerContent(self, flag, pid, vipFlags):
        return self.vod.playerContent(flag, pid, vipFlags)

    def localProxy(self, params):
        if params['type'] == "mpd":
            return self.vod.get_mpd(params)
        if params['type'] == "media":
            return self.vod.get_media(params)
        return None

    def destroy(self):
        return '正在Destroy'


class BiliBili:
    def __init__(self):
        self.name = "哔哩哔哩"
        self.get_proxy_url = 'http://127.0.0.1:9978/proxy?do=py'
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Cookie': 'SESSDATA=ecb71422%2C1774019345%2Cdfcbc%2A91CjBdRNtey6jQOQf53YSGkeyisr9LJSQueBZIJXqpccANoHdH9vILqgRmkF654a9k8GASVmJUODFSZTdmR05UME9yNEFoWTVKaGs2U19LZjUwTTFOcWlhSEk0NXd3YUhQbURnZlBRSFFvd2VmSEhHVjZ6bExCNTVoT0wzWGxBdlZ5c0pfUEg3YVRRIIEC;bili_jct=668300dcfde99120d47e3a0084c05cd1;DedeUserID=1647569046;DedeUserID__ckMd5=9ceb1acdcfded2be;sid=q8pjvqa2'
        }
        self.cache = {}

    def homeContent(self, filter):
        return {
            'class': [
                {'type_id': '1', 'type_name': '番剧'},
                {'type_id': '4', 'type_name': '国创'},
                {'type_id': '2', 'type_name': '电影'},  # 修正：电影应该是2
                {'type_id': '7', 'type_name': '综艺'},
                {'type_id': '5', 'type_name': '电视剧'},
                {'type_id': '3', 'type_name': '纪录片'},  # 可选：添加纪录片分类
            ],
            'filters': {
                "1": [  # 番剧
                    {"key":"season_version","name":"类型","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"正片"},{"v":'2',"n":"电影"},{"v":'3',"n":"其他"}
                    ]},
                    {"key":"area","name":"地区","value":[
                        {"v":'-1',"n":"全部"},{"v":'2',"n":"日本"},{"v":'3',"n":"美国"},
                        {"v":"1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70","n":"其他"}
                    ]},
                    {"key":"is_finish","name":"状态","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"完结"},{"v":'0',"n":"连载"}
                    ]},
                    {"key":"copyright","name":"版权","value":[
                        {"v":'-1',"n":"全部"},{"v":'3',"n":"独家"},{"v":"1,2,4","n":"其他"}
                    ]},
                    {"key":"season_status","name":"付费","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"免费"},{"v":"2,6","n":"付费"},{"v":"4,6","n":"大会员"}
                    ]},
                    {"key":"season_month","name":"季度","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"1月"},{"v":'4',"n":"4月"},{"v":'7',"n":"7月"},{"v":'10',"n":"10月"}
                    ]},
                    {"key":"year","name":"年份","value":[
                        {"v":'-1',"n":"全部"},{"v":"[2025,2026)","n":"2025"},{"v":"[2024,2025)","n":"2024"},
                        {"v":"[2023,2024)","n":"2023"},{"v":"[2022,2023)","n":"2022"},{"v":"[2021,2022)","n":"2021"},
                        {"v":"[2020,2021)","n":"2020"},{"v":"[2019,2020)","n":"2019"},{"v":"[2018,2019)","n":"2018"},
                        {"v":"[2017,2018)","n":"2017"},{"v":"[2016,2017)","n":"2016"},{"v":"[2015,2016)","n":"2015"},
                        {"v":"[2010,2015)","n":"2014-2010"},{"v":"[2005,2010)","n":"2009-2005"},
                        {"v":"[2000,2005)","n":"2004-2000"},{"v":"[1990,2000)","n":"90年代"},
                        {"v":"[1980,1990)","n":"80年代"},{"v":"[,1980)","n":"更早"}
                    ]},
                    {"key":"style_id","name":"风格","value":[
                        {"v":'-1',"n":"全部"},{"v":'10010',"n":"原创"},{"v":'10011',"n":"漫画改"},{"v":'10012',"n":"小说改"},
                        {"v":'10013',"n":"游戏改"},{"v":'10102',"n":"特摄"},{"v":'10015',"n":"布袋戏"},{"v":'10016',"n":"热血"},
                        {"v":'10017',"n":"穿越"},{"v":'10018',"n":"奇幻"},{"v":'10020',"n":"战斗"},{"v":'10021',"n":"搞笑"},
                        {"v":'10022',"n":"日常"},{"v":'10023',"n":"科幻"},{"v":'10024',"n":"萌系"},{"v":'10025',"n":"治愈"},
                        {"v":'10026',"n":"校园"},{"v":'10027',"n":"少儿"},{"v":'10028',"n":"泡面"},{"v":'10029',"n":"恋爱"},
                        {"v":'10030',"n":"少女"},{"v":'10031',"n":"魔法"},{"v":'10032',"n":"冒险"},{"v":'10033',"n":"历史"},
                        {"v":'10034',"n":"架空"},{"v":'10035',"n":"机战"},{"v":'10036',"n":"神魔"},{"v":'10037',"n":"声控"},
                        {"v":'10038',"n":"运动"},{"v":'10039',"n":"励志"},{"v":'10040',"n":"音乐"},{"v":'10041',"n":"推理"},
                        {"v":'10042',"n":"社团"},{"v":'10043',"n":"智斗"},{"v":'10044',"n":"催泪"},{"v":'10045',"n":"美食"},
                        {"v":'10046',"n":"偶像"},{"v":'10047',"n":"乙女"},{"v":'10048',"n":"职场"}
                    ]}
                ],
                "4": [  # 国创
                    {"key":"season_version","name":"类型","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"正片"},{"v":'2',"n":"电影"},{"v":'3',"n":"其他"}
                    ]},
                    {"key":"area","name":"地区","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"中国大陆"},{"v":"6,7","n":"中国港台"}
                    ]},
                    {"key":"is_finish","name":"状态","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"完结"},{"v":'0',"n":"连载"}
                    ]},
                    {"key":"copyright","name":"版权","value":[
                        {"v":'-1',"n":"全部"},{"v":'3',"n":"独家"},{"v":"1,2,4","n":"其他"}
                    ]},
                    {"key":"season_status","name":"付费","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"免费"},{"v":"2,6","n":"付费"},{"v":"4,6","n":"大会员"}
                    ]},
                    {"key":"year","name":"年份","value":[
                        {"v":'-1',"n":"全部"},{"v":"[2025,2026)","n":"2025"},{"v":"[2024,2025)","n":"2024"},
                        {"v":"[2023,2024)","n":"2023"},{"v":"[2022,2023)","n":"2022"},{"v":"[2021,2022)","n":"2021"},
                        {"v":"[2020,2021)","n":"2020"},{"v":"[2019,2020)","n":"2019"},{"v":"[2018,2019)","n":"2018"},
                        {"v":"[2017,2018)","n":"2017"},{"v":"[2016,2017)","n":"2016"},{"v":"[2015,2016)","n":"2015"},
                        {"v":"[2010,2015)","n":"2014-2010"}
                    ]},
                    {"key":"style_id","name":"风格","value":[
                        {"v":'-1',"n":"全部"},{"v":'10010',"n":"原创"},{"v":'10011',"n":"漫画改"},{"v":'10012',"n":"小说改"},
                        {"v":'10013',"n":"游戏改"},{"v":'10014',"n":"动态漫"},{"v":'10015',"n":"布袋戏"},{"v":'10016',"n":"热血"},
                        {"v":'10018',"n":"奇幻"},{"v":'10019',"n":"玄幻"},{"v":'10020',"n":"战斗"},{"v":'10021',"n":"搞笑"},
                        {"v":'10078',"n":"武侠"},{"v":'10022',"n":"日常"},{"v":'10023',"n":"科幻"},{"v":'10024',"n":"萌系"},
                        {"v":'10025',"n":"治愈"},{"v":'10057',"n":"悬疑"},{"v":'10026',"n":"校园"},{"v":'10027',"n":"少儿"},
                        {"v":'10028',"n":"泡面"},{"v":'10029',"n":"恋爱"},{"v":'10030',"n":"少女"},{"v":'10031',"n":"魔法"},
                        {"v":'10033',"n":"历史"},{"v":'10035',"n":"机战"},{"v":'10036',"n":"神魔"},{"v":'10037',"n":"声控"},
                        {"v":'10038',"n":"运动"},{"v":'10039',"n":"励志"},{"v":'10040',"n":"音乐"},{"v":'10041',"n":"推理"},
                        {"v":'10042',"n":"社团"},{"v":'10043',"n":"智斗"},{"v":'10044',"n":"催泪"},{"v":'10045',"n":"美食"},
                        {"v":'10046',"n":"偶像"},{"v":'10047',"n":"乙女"},{"v":'10048',"n":"职场"},{"v":'10049',"n":"古风"}
                    ]}
                ],
                "2": [  # 电影
                    {"key":"area","name":"地区","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"中国大陆"},{"v":"6,7","n":"中国港台"},
                        {"v":'3',"n":"美国"},{"v":'2',"n":"日本"},{"v":'8',"n":"韩国"},
                        {"v":'9',"n":"法国"},{"v":'4',"n":"英国"},{"v":'15',"n":"德国"},
                        {"v":'10',"n":"泰国"},{"v":'35',"n":"意大利"},{"v":'13',"n":"西班牙"},
                        {"v":"5,11,12,14,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70","n":"其他"}
                    ]},
                    {"key":"season_status","name":"付费","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"免费"},{"v":"2,6","n":"付费"},{"v":"4,6","n":"大会员"}
                    ]},
                    {"key":"style_id","name":"风格","value":[
                        {"v":'-1',"n":"全部"},{"v":'10104',"n":"短片"},{"v":'10050',"n":"剧情"},{"v":'10051',"n":"喜剧"},
                        {"v":'10052',"n":"爱情"},{"v":'10053',"n":"动作"},{"v":'10054',"n":"恐怖"},{"v":'10023',"n":"科幻"},
                        {"v":'10055',"n":"犯罪"},{"v":'10056',"n":"惊悚"},{"v":'10057',"n":"悬疑"},{"v":'10018',"n":"奇幻"},
                        {"v":'10058',"n":"战争"},{"v":'10059',"n":"动画"},{"v":'10060',"n":"传记"},{"v":'10061',"n":"家庭"},
                        {"v":'10062',"n":"歌舞"},{"v":'10033',"n":"历史"},{"v":'10032',"n":"冒险"},{"v":'10063',"n":"纪实"},
                        {"v":'10064',"n":"灾难"},{"v":'10011',"n":"漫画改"},{"v":'10012',"n":"小说改"}
                    ]},
                    {"key":"release_date","name":"年份","value":[
                        {"v":'-1',"n":"全部"},{"v":"[2025-01-01 00:00:00,2026-01-01 00:00:00)","n":"2025"},
                        {"v":"[2024-01-01 00:00:00,2025-01-01 00:00:00)","n":"2024"},
                        {"v":"[2023-01-01 00:00:00,2024-01-01 00:00:00)","n":"2023"},
                        {"v":"[2022-01-01 00:00:00,2023-01-01 00:00:00)","n":"2022"},
                        {"v":"[2021-01-01 00:00:00,2022-01-01 00:00:00)","n":"2021"},
                        {"v":"[2020-01-01 00:00:00,2021-01-01 00:00:00)","n":"2020"},
                        {"v":"[2019-01-01 00:00:00,2020-01-01 00:00:00)","n":"2019"},
                        {"v":"[2018-01-01 00:00:00,2019-01-01 00:00:00)","n":"2018"},
                        {"v":"[2017-01-01 00:00:00,2018-01-01 00:00:00)","n":"2017"},
                        {"v":"[2016-01-01 00:00:00,2017-01-01 00:00:00)","n":"2016"},
                        {"v":"[2010-01-01 00:00:00,2016-01-01 00:00:00)","n":"2015-2010"},
                        {"v":"[2005-01-01 00:00:00,2010-01-01 00:00:00)","n":"2009-2005"},
                        {"v":"[2000-01-01 00:00:00,2005-01-01 00:00:00)","n":"2004-2000"},
                        {"v":"[1990-01-01 00:00:00,2000-01-01 00:00:00)","n":"90年代"},
                        {"v":"[1980-01-01 00:00:00,1990-01-01 00:00:00)","n":"80年代"},
                        {"v":"[,1980-01-01 00:00:00)","n":"更早"}
                    ]}
                ],
                "5": [  # 电视剧
                    {"key":"area","name":"地区","value":[
                        {"v":'-1',"n":"全部"},{"v":"1,6,7","n":"中国"},{"v":'2',"n":"日本"},
                        {"v":'3',"n":"美国"},{"v":'4',"n":"英国"},{"v":'10',"n":"泰国"},
                        {"v":"5,8,9,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70","n":"其他"}
                    ]},
                    {"key":"season_status","name":"付费","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"免费"},{"v":"2,6","n":"付费"},{"v":"4,6","n":"大会员"}
                    ]},
                    {"key":"style_id","name":"风格","value":[
                        {"v":'-1',"n":"全部"},{"v":'10021',"n":"搞笑"},{"v":'10018',"n":"奇幻"},{"v":'10058',"n":"战争"},
                        {"v":'10078',"n":"武侠"},{"v":'10079',"n":"青春"},{"v":'10103',"n":"短剧"},{"v":'10080',"n":"都市"},
                        {"v":'10081',"n":"古装"},{"v":'10082',"n":"谍战"},{"v":'10083',"n":"经典"},{"v":'10084',"n":"情感"},
                        {"v":'10057',"n":"悬疑"},{"v":'10039',"n":"励志"},{"v":'10085',"n":"神话"},{"v":'10017',"n":"穿越"},
                        {"v":'10086',"n":"年代"},{"v":'10087',"n":"农村"},{"v":'10088',"n":"刑侦"},{"v":'10050',"n":"剧情"},
                        {"v":'10061',"n":"家庭"},{"v":'10033',"n":"历史"},{"v":'10089',"n":"军旅"},{"v":'10023',"n":"科幻"}
                    ]},
                    {"key":"release_date","name":"年份","value":[
                        {"v":'-1',"n":"全部"},{"v":"[2025-01-01 00:00:00,2026-01-01 00:00:00)","n":"2025"},
                        {"v":"[2024-01-01 00:00:00,2025-01-01 00:00:00)","n":"2024"},
                        {"v":"[2023-01-01 00:00:00,2024-01-01 00:00:00)","n":"2023"},
                        {"v":"[2022-01-01 00:00:00,2023-01-01 00:00:00)","n":"2022"},
                        {"v":"[2021-01-01 00:00:00,2022-01-01 00:00:00)","n":"2021"},
                        {"v":"[2020-01-01 00:00:00,2021-01-01 00:00:00)","n":"2020"},
                        {"v":"[2019-01-01 00:00:00,2020-01-01 00:00:00)","n":"2019"},
                        {"v":"[2018-01-01 00:00:00,2019-01-01 00:00:00)","n":"2018"},
                        {"v":"[2017-01-01 00:00:00,2018-01-01 00:00:00)","n":"2017"},
                        {"v":"[2016-01-01 00:00:00,2017-01-01 00:00:00)","n":"2016"},
                        {"v":"[2010-01-01 00:00:00,2016-01-01 00:00:00)","n":"2015-2010"},
                        {"v":"[2005-01-01 00:00:00,2010-01-01 00:00:00)","n":"2009-2005"},
                        {"v":"[2000-01-01 00:00:00,2005-01-01 00:00:00)","n":"2004-2000"},
                        {"v":"[1990-01-01 00:00:00,2000-01-01 00:00:00)","n":"90年代"},
                        {"v":"[1980-01-01 00:00:00,1990-01-01 00:00:00)","n":"80年代"},
                        {"v":"[,1980-01-01 00:00:00)","n":"更早"}
                    ]}
                ],
                "7": [  # 综艺
                    {"key":"season_status","name":"付费","value":[
                        {"v":'-1',"n":"全部"},{"v":'1',"n":"免费"},{"v":"2,6","n":"付费"},{"v":"4,6","n":"大会员"}
                    ]},
                    {"key":"style_id","name":"风格","value":[
                        {"v":'-1',"n":"全部"},{"v":'10040',"n":"音乐"},{"v":'10090',"n":"访谈"},{"v":'10091',"n":"脱口秀"},
                        {"v":'10092',"n":"真人秀"},{"v":'10094',"n":"选秀"},{"v":'10045',"n":"美食"},{"v":'10095',"n":"旅游"},
                        {"v":'10098',"n":"晚会"},{"v":'10096',"n":"演唱会"},{"v":'10084',"n":"情感"},{"v":'10051',"n":"喜剧"},
                        {"v":'10097',"n":"亲子"},{"v":'10100',"n":"文化"},{"v":'10048',"n":"职场"},{"v":'10069',"n":"萌宠"},
                        {"v":'10099',"n":"养成"}
                    ]},
                    {"key":"release_date","name":"年份","value":[
                        {"v":'-1',"n":"全部"},{"v":"[2025-01-01 00:00:00,2026-01-01 00:00:00)","n":"2025"},
                        {"v":"[2024-01-01 00:00:00,2025-01-01 00:00:00)","n":"2024"},
                        {"v":"[2023-01-01 00:00:00,2024-01-01 00:00:00)","n":"2023"},
                        {"v":"[2022-01-01 00:00:00,2023-01-01 00:00:00)","n":"2022"},
                        {"v":"[2021-01-01 00:00:00,2022-01-01 00:00:00)","n":"2021"},
                        {"v":"[2020-01-01 00:00:00,2021-01-01 00:00:00)","n":"2020"},
                        {"v":"[2019-01-01 00:00:00,2020-01-01 00:00:00)","n":"2019"},
                        {"v":"[2018-01-01 00:00:00,2019-01-01 00:00:00)","n":"2018"},
                        {"v":"[2017-01-01 00:00:00,2018-01-01 00:00:00)","n":"2017"},
                        {"v":"[2016-01-01 00:00:00,2017-01-01 00:00:00)","n":"2016"},
                        {"v":"[2010-01-01 00:00:00,2016-01-01 00:00:00)","n":"2015-2010"}
                    ]}
                ]
            }
        }

    def homeVideoContent(self):
        return {'list': [], 'parse': 0, 'jx': 0}

    def categoryContent(self, cid, page, filter, ext):
        video_list = []
        url = f"https://api.bilibili.com/pgc/season/index/result?order=2&sort=2&pagesize=20&type=1&st={cid}&season_type={cid}&page={page}"
        if len(list(ext.keys())) > 0:
            key = list(ext.keys())[0]
            url += f'&{key}={quote(ext[key])}'
        response = requests.get(url, headers=self.headers, timeout=5)
        data_list = response.json()['data']['list']
        for vod in data_list:
            aid = str(vod['season_id']).strip()
            title = self.remove_html_tags(vod['title'])
            img = vod['cover'].strip()
            remark = vod['index_show'].strip()
            video_list.append({
                "vod_id": aid,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": remark
            })
        return {'list': video_list, 'parse': 0, 'jx': 0}

    def detailContent(self, did):
        ids = did[0]
        url = f"https://api.bilibili.com/pgc/view/web/season?season_id={ids}"
        response = requests.get(url, headers=self.headers, timeout=10)
        data = response.json()
        vod = {
            "vod_id": ids,
            "vod_name": self.remove_html_tags(data['result']['title']),
            "vod_pic": data['result']['cover'],
            "type_name": data['result']['share_sub_title'],
            "vod_actor": data['result']['actors'].replace('\n', '，'),
            "vod_content": self.remove_html_tags(data['result']['evaluate'])
        }
        data_list = data['result']['episodes']
        play_url_list = []
        for video in data_list:
            eid = video['id']
            cid = video['cid']
            name = self.remove_html_tags(video['share_copy']).replace("#", "-").replace('$', '*')
            remark = time.strftime('%H:%M:%S', time.gmtime(video['duration'] / 1000))
            if remark.startswith('00:'):
                remark = remark[3:]
            play_url_list.append(
                f"[{remark}]{name}${eid}_{cid}"
            )
        vod['vod_play_from'] = self.name
        vod['vod_play_url'] = '#'.join(play_url_list)
        return {"list": [vod], 'parse': 0, 'jx': 0}

    def searchContent(self, key, quick, page='1'):
        video_list = []
        url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=media_bangumi&keyword={key}&page={page}"
        response = requests.get(url, headers=self.headers)
        data = response.json()['data']
        if 'result' in data:
            for vod in data['result']:
                sid = str(vod['season_id']).strip()
                title = self.remove_html_tags(vod['title'])
                img = vod['eps'][0]['cover'].strip()
                remark = self.remove_html_tags(vod['index_show']).strip()
                video_list.append({
                    "vod_id": sid,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": remark
                })

        return {'list': video_list, 'parse': 0, 'jx': 0}

    def playerContent(self, flag, pid, vipFlags):
        pid_list = pid.split("_")
        aid = pid_list[0]
        cid = pid_list[1]
        return {
            'url': f'{self.get_proxy_url}&type=mpd&aid={aid}&cid={cid}',
            'parse': 0,
            'jx': 0,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.headers['Referer']
            }
        }

    def get_mpd(self, params):
        aid = params['aid']
        cid = params['cid']
        cache_key = f'Bili_{aid}_{cid}'
        cache_data = self.cache.get(cache_key, None)
        if cache_data:
            dash_infos = cache_data
        else:
            url = f'https://api.bilibili.com/pgc/player/web/playurl?ep_id={aid}&cid={cid}&qn=120&fnval=4048&fnver=0&fourk=1'
            response = requests.get(url, headers=self.headers, timeout=5)
            data = response.json()
            if data['result']['type'] == 'DASH':
                dash_infos = data['result']['dash']
                # 缓存dash数据
                self.cache[cache_key] = dash_infos

            elif data['result']['type'] == 'MP4':
                url = data['result']['durl'][0]['url']
                # base_url = f"{self.get_proxy_url}&type=media&url=" + base64.b64encode(url.encode()).decode()
                return [302, "text/plain", None, {'Location': url}]

            else:
                return [302, "text/plain", None, {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}]

        duration = dash_infos['duration']
        minBufferTime = dash_infos['minBufferTime']
        videoinfo_list = []
        for video in dash_infos['video']:
            codecs = video['codecs']
            bandwidth = video['bandwidth']
            frameRate = video['frameRate']
            height = video['height']
            width = video['width']
            void = video['id']
            base_url = f"{self.get_proxy_url}&type=media&url=".replace('&', '&amp;') + base64.b64encode(video['baseUrl'].encode()).decode()

            index_range = video['SegmentBase']['indexRange']
            initialization = video['SegmentBase']['Initialization']

            videoinfo_list.append(f'<Representation bandwidth="{bandwidth}" codecs="{codecs}" frameRate="{frameRate}" height="{height}" id="{void}" width="{width}">')
            videoinfo_list.append(f'<BaseURL>{base_url}</BaseURL>')
            videoinfo_list.append(f'<SegmentBase indexRange="{index_range}"><Initialization range="{initialization}"/></SegmentBase>')
            videoinfo_list.append('</Representation>')
        audioinfo_list = []
        for audio in dash_infos['audio']:
            bandwidth = audio['bandwidth']
            codecs = audio['codecs']
            audio_id = audio['id']

            base_url = f"{self.get_proxy_url}&type=media&url=".replace('&', '&amp;') + base64.b64encode(audio['baseUrl'].encode()).decode()

            index_range = audio['SegmentBase']['indexRange']
            initialization = audio['SegmentBase']['Initialization']

            audioinfo_list.append(f'<Representation audioSamplingRate="44100" bandwidth="{bandwidth}" codecs="{codecs}" id="{audio_id}">')
            audioinfo_list.append(f'<BaseURL>{base_url}</BaseURL>')
            audioinfo_list.append(f'<SegmentBase indexRange="{index_range}"><Initialization range="{initialization}"/></SegmentBase>')
            audioinfo_list.append('</Representation>')
        mpd_list = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011" type="static" mediaPresentationDuration="PT{duration}S" minBufferTime="PT{minBufferTime}S">',
            '<Period>',
            '<AdaptationSet mimeType="video/mp4" startWithSAP="1" scanType="progressive" segmentAlignment="true">',
            '\n'.join(videoinfo_list),
            '</AdaptationSet>',
            '<AdaptationSet mimeType="audio/mp4" startWithSAP="1" segmentAlignment="true" lang="und">',
            '\n'.join(audioinfo_list),
            '</AdaptationSet>',
            '</Period>',
            '</MPD>'
        ]
        return [200, "application/dash+xml", '\n'.join(mpd_list)]

    def get_media(self, params):
        uri = params['url']
        url = base64.b64decode(uri.encode()).decode()
        Range = params.get('range', None)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.54 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
        }
        if Range:
            headers['Range'] = Range
        return [206, "application/octet-stream", requests.get(url, headers=headers, stream=True).content]

    @staticmethod
    def remove_html_tags(text):
        return re.sub('(<.*?>)', '', text)


if __name__ == '__main__':
    pass