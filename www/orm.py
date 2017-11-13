#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'lzh'

#import sys, random

import asyncio, logging
import aiomysql 

# 打印用户所使用的sql语句
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

# 创建连接池会事先限定连接数量，不必频繁地打开和关闭数据库连接，**kw任意个关键字参数即dict
async def create_pool(loop, **kw): 
	logging.info('create database connection pool...')
    # 加了两个下划线能使变量不被外部访问
	global __pool 
	# 以下都是连接数据库所需的参数
	__pool = await aiomysql.create_pool( 
		# get(a,b)在dict中找出与a对应的值，若找不到则默认b
		host=kw.get('host', 'localhost'),
		port=kw.get('port', 3306),
		user=kw['user'],
		password=kw['password'],
        # 数据库文件.db
		db=kw['db'],
		charset=kw.get('charset', 'utf8'),
        # 是否自动提交事务
		autocommit=kw.get('autocommit', True),
        # 最大连接数:连接池能申请的最大连接数,如果数据库连接请求超过次数,后面的数据库连接请求将被加入到等待队列中
		maxsize=kw.get('maxsize', 10), 
        # 最小连接数:连接池一直保持的数据库连接,所以如果应用程序对数据库连接的使用量不大,将会有大量的数据库连接资源被浪费.
		minsize=kw.get('minsize', 1),
        # Eventloop协程，即异步事件
		loop=loop
	)
    
'''关闭数据库在测试时需要
async def destory_pool():
    global __pool
    if __pool is not None :
        __pool.close()
        await __pool.wait_closed()    
'''
  
# 返回元类中创建sql_insert语句中的占位符
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    # '_'.join('abc'); 'a_b_c'，可以将[]转换为字符串'?, ?'
    return ', '.join(L) 
    
# 封装select语句，返回选择的结果集，结果集是一个list，其中每个元素都是一个dict
async def select(sql, args, size=None):
    # 打印查询语句
    log(sql, args) 
    global __pool
    # 把__pool.get()调用__enter__()后的返回值赋值给conn
    # 类似conn = mysql.connector.connect(user='root', password='password', database='test')
    async with __pool.get() as conn:
        # 创建cursor(游标)对象，数据库的操作由它执行,aiomysql.DictCursor将查询后的返回值变为dict格式，
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 执行查询语句，将sql的占位符'?'由MySQL的占位符'%s'替代，替换的参数为args或空
            await cur.execute(sql.replace('?', '%s'), args or ())
            # 将查询后的结果集按照size的数量返回或全部返回
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('row returned: %s' % len(rs))
        return rs
        
# 封装insert，update，delete操作，返回影响的行数，autocommit自动提交事务默认为True
async def execute(sql, args, autocommit=True): 
    log(sql)
    async with __pool.get() as conn: 
        # 若不是自动提交事务则开始执行事务
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                # cur.rowcount是execute()影响的行数
                affected = cur.rowcount 
            # 如果不是自动提交事务则需commit()
            if not autocommit:
                await conn.commit() 
        except BaseException as e:
            if not autocommit:
                # 回滚到事务开始前，事务占用资源被释放
                await conn.rollback() 
            # 抛出本身的错误即BaseException
            raise 
        return affected
    
# user定义每一列的名字，类型，是否为主键，默认值
class Field(object):
	def __init__(self, name, column_type, primary_key, default):
			self.name = name
			self.column_type = column_type
			self.primary_key = primary_key
			self.default = default

    # 打印类名(表名)，数据类型，属性名        
	def __str__(self):
			return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)
            
# 定义字符类型
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
    	super().__init__(name, ddl, primary_key, default)
        
# 定义逻辑类型，逻辑类型不能为主键
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)
    
# 定义整形
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)
   
# 定义浮点型   
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)
        
# 定义文本类型，文本类型不能为主键，使用文本型数据，你可以存放超过二十亿个字符的字符串。当你需要存储大串的字符时，应该使用文本型数据。
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

# 作用：首先，拦截类的创建，然后，修改类，最后，返回修改后的类
# 继承继承了type类，类似于int类，type类用于创建类对象，int类用于创建int对象
class ModelMetaclass(type):
    '''
    重点：采集应用元类的子类属性信息，把Model看作它的实例好理解
    将采集的信息作为参数传入__new__方法
    应用__new__方法修改类
    指向将要通过元类创建的类对象即后文中的(User)，类似于self，类的名字，类继承的父类集合()，类的方法集合{}
    attr是指类对象的属性和值，方法名和值(方法名)
    '''
    # 当创建类时自动传入参数
    def __new__(cls, name, bases, attrs): 
        # 不对Model类应用元类，而是对Model的子类应用元类
        if name == 'Model':
            # 返回按默认创建的类
            return type.__new__(cls, name, bases, attrs) 
        
        # 获取表的名字，or从左到右返回第一个真值，当取默认值None时为假，采用类名
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        
        # 根据user设置的属性信息，在此映射为主键和非主键，并把其数据类型保存
        # 将映射变为dict(映射指列名和数据类型)
        mappings = dict() 
        # 保存非主键的属性名
        fields = [] 
        primaryKey = None
        # k：属性名(列名)；v：数据库中对应的数据类型，items()得到键值对，详请最下方
        for k, v in attrs.items():
            # 判断是否为自己编写的Filed（数据类型）
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                # 将属性名和与之对应的数据类型保存在mappings
                mappings[k] = v 
                # 根据user设置的主键，在此映射为主键
                if v.primary_key:
                    # 若重复主键则抛出错误
                    if primaryKey: 
                        raise StandardError('Duplicate primary key for field: %s' % k)
                    # 否则将该k(属性名)设为主键，k字符串也属于True,故需增加primaryKey标志
                    primaryKey = k 
                # 若不是主键则都放在fields
                else:
                    fields.append(k) 
                    
        # 若user在建表过程中没有设置主键则出错
        if not primaryKey: 
            raise RuntimeError('Primary key not found')
            
        # 从类属性中删除Field属性,否则，容易造成运行时错误（实例的属性会遮盖类的同名属性）？？？
        # keys()得到mappings的所有key,返回方式为list
        for k in mappings.keys(): 
            # pop()根据key删除相应的键值对，并返回该值
            attrs.pop(k) 
            
        # 将非主键名如id转换为`id`这种形式, ('`%s`' % f)这个是函数，map从fields中遍历，返回惰性序列，需要list()计算出返回list
        # 使用反单引号" ` "区别MySQL保留字，提高兼容性
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        
        # 重写属性
        attrs['__mappings__'] = mappings # 保存属性名和对应的数据类型
        attrs['__table__'] = tableName # 表名
        attrs['__primary_key__'] = primaryKey # 主键名
        attrs['__fields__'] = fields # 非主键名
        # 构建默认的增删改查sql语句形式，真正的操作在上面封装好的select和excute
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields),
        primaryKey, create_args_string(len(escaped_fields) + 1)) # len(escaped_fields) + 1非主键数加主键数1
        attrs['__update__'] = 'update `%s` set %s where `%s` =?' % (tableName, ', '.join(map(lambda f: '`%s`=?' %
        (mappings.get(f).name or f),fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs) # 返回修改后的类

'''
定义ORM所有映射的父类：Model
Model类的任意子类可以映射一个数据库表
Model类可以看做是对所有数据库表操作的基本定义的映射
基于字典查询形式
Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__,能够实现属性操作
实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
'''
class Model(dict, metaclass=ModelMetaclass):
    # 创建子类对象前(即__init__前)必定经过了__new__
    def __init__(self, **kw):
        # 调用父类dict初始化
        super(Model, self).__init__(**kw) 

    # 前后有双下划线重写python内置函数
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    # 前后有双下划线重写python内置函数
    def __setattr__(self, key, value):
        self[key] = value

    # 用于更新和插入操作
    def getValue(self, key):
        #直接调用重写的getattr方法即(__getattr__)
        return getattr(self, key, None)

    # 得到属性的值或默认值，用于插入操作必须有值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        # 如果用户没赋值给属性则去得到该属性的默认值
        if value is None:
            # self指的是Model子类对象，它应用了元类故有__mappings__
            field = self.__mappings__[key]
            if field.default is not None:
                # callable用来检测对象是否可被调用，可被调用指的是对象能否使用()括号的方法调用(可调用值select函数)
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                # 调用重写的setattr方法
                setattr(self, key, value) 
        return value
        
    # 按WHERE子句查找对象    
    # 针对于整张表所以需类方法，classmethod修饰的方法需要通过cls参数(即子类对象)传递当前类对象
    @classmethod 
    async def findAll(cls, where=None, args=None, **kw): 
        # cls指的是Model的子类，可以直接调用attrs的方法和属性
        sql = [cls.__select__] 
        if where: # 若where查询条件存在
            sql.append('where') # 在sql语句中添加where关键字
            sql.append(where) # 添加where查询条件
        if args is None:
            args = []
        
        orderBy = kw.get('orderBy', None) # 得到orderBy中的查询条件
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        
        limit = kw.get('limit', None) # 得到limit的查询条件
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                # extend() 函数用于在列表末尾一次性追加另一个序列中的多个值（用新列表扩展原来的列表）
                # 将limit添加进参数列表，之所以添加参数列表之后再进行整合是为了防止sql注入
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        # 将args参数列表注入sql语句之后，传递给select函数进行查询并返回查询结果
        rs = await select(' '.join(sql), args)  
        # 装订成结果集，构成了一个cls类的列表，其实就是每一条记录对应的类实例
        return [cls(**r) for r in rs] 
    
    # 查询某个字段的数量
    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        # rs是结果集dict包含tuple
        return rs[0]['_num_'] 
        
    # 按主键查找对象
    @classmethod
    async def find(cls, pk): # 实例查询操作
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])
        
    async def save(self): # 实例插入操作
        # 将__fields__保存的除主键外的所有属性一次传递到getValueOrDefault函数中获取值
        args = list(map(self.getValueOrDefault, self.__fields__)) # map用法，详情下方
        # 增加主键名
        args.append(self.getValueOrDefault(self.__primary_key__))
        # 执行插入语句
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
    
    async def update(self): # 实例更新操作
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)
            
    async def remove(self): # 实例删除操作
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)

'''test            
if __name__ == '__main__':
    class User(Model):
        # 定义类的属性到列的映射：
        id = IntegerField('id',primary_key = True)
        name = StringField('name')
        email = StringField('email')
        password = StringField('password')
        
    # 创建异步事件的句柄
    loop = asyncio.get_event_loop()

    # 创建test表实例
    async def test():
        # test必须是数据库中已存在的库
        await create_pool(loop=loop, host='localhost', port=3306, user='root', password='password', db='test')
        # 随机id为了防止重复插入相同id导致出错
        user = User(id = random.randint(5,100), name='lzh', email='lzh@python.com', password='lzh')
        await user.save()
        print(user)  
        # 这里可以使用User.findAll()是因为：用@classmethod修饰了Model类里面的findAll()
        # 一般来说，要使用某个类的方法，需要先实例化一个对象再调用方法
        # 而使用@staticmethod或@classmethod，就可以不需要实例化，直接类名.方法名()来调用
        # 查询所有记录：测试按条件查询
        r = await User.findAll(name='lzh') 
        print(r)
        # user1是数据库中id已经存在的一行的新数据，使用update必须已存在数据
        user1 = User(id=3, name='py', email='py@qq.com', password='py') 
        u = await user1.update()
        print(user1)
        user1 = User(id = 3,name='py',email='py@qq.com',password='py')
        d = await user1.remove() 
        print(d)
        # 测试find by primary key
        s = await User.find(49) 
        print(s)
        # 必须再次关闭连接池，否则出错
        await destory_pool()

    loop.run_until_complete(test())
    loop.close()
    # 有些人说需要此语句，否则出错，但我测试时不需要也可
    if loop.is_closed():
        sys.exit(0)            

将数据库表的每条记录映射为对象，每条记录的字段和对象的属性相应；同时透过对象方法执行SQL命令。
website = {1:"google","second":"baidu",3:"facebook","twitter":4}
>>> website.items()
[(1, 'google'), ('second', 'baidu'), (3, 'facebook'), ('twitter', 4)]
>>> def f(x):
...     return x * x
...
>>> r = map(f, [1, 2, 3, 4, 5, 6, 7, 8, 9])
>>> list(r)
[1, 4, 9, 16, 25, 36, 49, 64, 81]
连接池：
创建数据库连接是一个很耗时的操作，也容易对数据库造成安全隐患。
所以，在程序初始化的时候，集中创建多个数据库连接，并把他们集中管理，供程序使用，
可以保证较快的数据库读写速度，还更加安全可靠
>>> def echo_bar(self):
…       print self.bar
…
>>> FooChild = type('FooChild', (Foo,), {'echo_bar': echo_bar})
总结：
前期准备：
首先，建立连接池，避免频繁打开数据库，封装select和excute(insert,update,delete)操作，封装过程中用参数形式
构建sql语句防止sql注入，注意将sql语句的占位符替换成相应数据库的占位符，这时计算占位符的数量则需要create_args_string，
属性的数据类型也要分装定义。
开始：
把每张表作为一个类，此时，用元类修改这个表类，让其拥有主键，非主键，表名，数据库操作(相应的sql语句形式)的属性，
再让表类作为Model类的子类，让其继承设置属性值，得到属性值操作和数据库操作的具体方法。
'''

