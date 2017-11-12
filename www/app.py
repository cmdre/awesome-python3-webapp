#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'lzh'

import logging; logging.basicConfig(level=logging.INFO)
#分号为断开两句话，第二句指定记录信息的级别

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

def index(request): #负责响应http请求并返回一个HTML，后面将与具体的url绑定
    return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')

@asyncio.coroutine #把一个generator标记为coroutine类型即srv
def init(loop):
    app = web.Application(loop=loop) #创建web服务器实例app
    app.router.add_route('GET', '/', index) #将处理函数index（）注册

    #利用协程创建TCP监听服务,loop为传入函数的协程，app.make_handler()得到IP包的编号吧
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...') #输入一段文本
    return srv

loop = asyncio.get_event_loop() #获取EventLoop,一种机制？创建协程
loop.run_until_complete(init(loop)) #运行协程
loop.run_forever() #不断运行协程，直到调用stop()

'''
一、
TCP协议负责在两台计算机之间建立可靠连接，保证数据包按顺序到达。
TCP协议会通过握手建立连接，然后，对每个IP包编号，确保对方按顺序收到，如果包丢掉了，就自动重发。
yield from 返回一个创建好的，绑定IP、端口、HTTP协议簇的监听服务的协程。
yield from的作用是使srv的行为模式和 loop.create_server()一致
总结：
不断利用一个协程来处理一个能监听服务，若监听成功则调用index（）将一个HTML返回给浏览器的协程
监听条件，需注册web服务器和将处理函数index（）注册到路由中
'''