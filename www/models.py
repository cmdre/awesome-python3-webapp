#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'lzh'

import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
    # uuid生成机器唯一标识,uuid4()由伪随机数得到,有一定的重复概率,该概率可以计算出来。hex得到十六进制数
    # time.time()返回1970纪元后经过的浮点秒数，%015d指15位数，不足则前面补0
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)
    
class User(Model):
    __table__ = 'users'
    
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)
    
class Blog(Model):
    __table__ = 'blogs'
    
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)
    
class Comment(Model):
    __table__ = 'comments'
    
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
    
'''
创建博客所需的三个数据库
'''   
    
    
    
    
    