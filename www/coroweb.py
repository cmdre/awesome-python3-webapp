#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'lzh'

# inspect模块，检查视图函数的参数
import asyncio, os, inspect, logging, functools

from urllib import parse
from aiohttp import web
from apis import APIError

def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator
    
def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# 得到无默认值的命名关键字参数如(def foo(a,*,b):pass)限制了只能传入b=?关键字
def get_required_kw_args(fn):
    args = []
    # inspect用法在底部，得到fn函数的参数名和值
    params = inspect.signature(fn).parameters
    # kind用法详情底部，若视图函数存在命名关键字参数且默认值为空,得到参数名
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    # 将iterable对象转换为元组
    return tuple(args)
    
# 得到命名关键字参数名    
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)
    
# 判断是否有命名关键字参数
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
            
# 判断是否有关键字参数         
def has_var_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
            
# 判断是否含有名为'request'的参数，且其参数位置在最后
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.paramters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        #若找到request的参数，但它是位置参数，其位置肯定不是在最后故报错
        if found and (
            param.kind != inspect.Parameter.VAR_POSITIONAL and 
            param.kind != inspect.Parameter.KEYWORD_ONLY and 
            param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found
    
# 定义RequestHandler从视图函数中分析其需要接受的参数，从web.Request中获取必要的参数    
# 调用视图函数，然后把结果转换为web.Response对象，符合aiohttp框架要求
class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        # 保存视图函数对象
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_args(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)
    
    # __call__可以使对象看作为函数，如p对象，若调用__call__方法则直接执行p(request)    
    # 将获取的参数经处理，使其完全符合视图函数接收的参数形式
    async def __call__(self, request):
        # kw用于保存request的参数
        kw = None
        # 若视图函数存在关键字参数，命名关键字参数，或者无默认值的命名关键字参数
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            # 若客户端传来的方法为'POST'
            if request.method == 'POST':
                # 若没有提交数据的格式(text/html,application/json)
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content-Type.')
                # 转为小写，便于检查
                ct = request.content_type.lower()
                # startswith检查是否以'application/json'开头
                if ct.startswith('application/json'):
                    # 仅解析body字段的json数据，返回dict
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                # 若是form表单请求的编码形式
                elif ct.startswith('application/x-www-form-rulencoded') or ct.startswith('multipart/form-data'):
                    # 返回post的内容中解析后的数据
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content-Type: %s' % request.content_type)                
            if request.method == 'GET':
                # 得到url中？后面的变量及其值，保存在kw,详情底部
                qs = request.query_string
                if qs:  
                    # 解析url中?后面的键值对的内容，parse.parse_qs用法详情下方，True不忽略空格
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        # 如果kw为空（说明request无请求内容），则将match_info列表里的资源映射给kw；若不为空，把命名关键词参数内容给kw
        if kw is None:
            '''
            request.match_info返回dict对象。dict中有可变路由中的可变字段{variable}为key，传入request请求的path为值  
            如：存在可变路由：/a/{name}/c，可匹配urlpath为：/a/jack/c的request  
            则reqwuest.match_info返回{'name' = 'jack'}
            '''
            kw = dict(**request.match_info)
        # 若request有参数
        else:
            # 若有命名关键字参数且没有关键字参数
            if self._named_kw_args and (not self._has_var_kw_arg):
                # 只保留命名关键字参数因为视图函数定义中不需要关键字参数的传递:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # 检查kw中的参数是否和match_info中的重复:
            for k, v in request.match_info.items():
                if name in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        # 若存在request参数
        if self._has_request_arg:
            kw['requset'] = request
        # 若存在默认值为空的命名关键字参数
        if self._required_kw_args:
            for name in self._required_kw_args:
                # 若未传入必须参数值
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            # 将把request请求中的参数，传递给了视图函数
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)
    
    '''
    在app中注册视图函数（添加路由）。
    add_route函数功能：
    1、验证视图函数是否拥有method和path参数
    2、将视图函数转变为协程
    '''
    def add_static(app):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        app.router.add_static('/static/', path)
        logging.info('add static %s => %s' % ('/static/', path))
        
    # 注册视图函数(添加路由)    
    def add_route(app, fn):
        #从fn中得到'__method__'属性值，若无则默认为空
        method = getattr(fn, '__method__', None)
        path = getattr(fn, '__route__', None)
        if path is None or method is None:
            raise ValueError('@get or @post not defined in %s.' % str(fn))
        # 判断URL处理函数(视图函数)是否协程并且是生成器 
        if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
            # 变为协程
            fn = asyncio.coroutine(fn)
        logging.info('add route %s %s =? %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
        # 在app中注册经RequestHandler类封装的视图函数
        app.router.add_route(method, path, RequestHandler(app, fn))
        
    # 导入模块路径以此批量注册视图函数
    def add_routes(app, module_name):
        # rfind()从字符串右侧检测字符串中是否包含子字符串str即'.',若有返回其索引，无返回-1
        n = module_name.rfind('.')
        if n == (-1):
            # __import__ 作用同import语句，但__import__是一个函数，并且只接收字符串作为参数  
            # __import__('os',globals(),locals(),['path','pip'], 0) ,等价于from os import path, pip
            # 由于后续的dir(mod)接收模块对象而不是字符串故需要import
            mod = __import__(module_name, globals(), locals())
        else:
            # 选择从模块名的'.'的下一位开始直到最后的字符
            name = module_name[n+1:]
            # 只获取最终导入的模块名，为后续调用dir(). from (点号前面的字符) import name
            # 得到module_name模块对象中，所需的name模块对象
            mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
        #获取mod模块中所有类，实例及函数等对象(str形式)，返回list
        for attr in dir(mod):
            # 忽略以'_'开头的对象(一些内置属性等)
            if attr.startswith('_'):
                continue
            fn = getattr(mod, attr)
            # 确保是可被调用的(函数)
            if callable(fn):
                method = getattr(fn, '__method__', None)
                path = getattr(fn, '__route__', None)
                if method and path:
                    # 注册视图函数
                    add_route(app, fn)
            
'''
# inspect.Parameter.kind 类型：  
# POSITIONAL_ONLY          位置参数  
# VAR_POSITIONAL           可选参数 *args  
# KEYWORD_ONLY             命名关键词参数  
# VAR_KEYWORD              关键词参数 **kw  
# POSITIONAL_OR_KEYWORD    位置或必选参数

def foo(a, b = 10, *c, d,**kw): pass 
sig = inspect.signature(foo) ==> <Signature (a, b=10, *c, d, **kw)> 
sig.parameters ==>  mappingproxy(OrderedDict([('a', <Parameter "a">), ...])) 
sig.parameters.items() ==> odict_items([('a', <Parameter "a">), ...)]) 
sig.parameters.values() ==>  odict_values([<Parameter "a">, ...]) 
sig.parameters.keys() ==>  odict_keys(['a', 'b', 'c', 'd', 'kw']) 

比如常见的URL网页地址都有 
xxx.asp?pn=123456 
?号后面的就是querystring 
如上URL的querystring参数就是变量pn=123456 
你可以在接受提交的网页里用request("变量")取得数值，如上URL则 
request("pn")=123456

parse.parse_qs解析作为字符串参数给出的查询字符串（application / x-www-form-urlencoded类型的数据 ）。
数据作为字典返回。字典键是唯一的查询变量名称，值是每个名称的值列表，True表示值不能为空
qs = 'first=f,s&second=s' 
parse.parse_qs(qs, True).items() 
>>> dict([('first', ['f,s']), ('second', ['s'])])
'''                      
          