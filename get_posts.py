#!/usr/bin/env python3
# coding=utf-8

__author__ = 'finalsatan'

'''
Get the Hi-Pda Buy&Sell new posts, then save in db and send emails
'''

import re, time, gzip, hashlib, smtplib, logging, uuid
import mysql.connector
import http.cookiejar
import urllib.request, urllib.parse, urllib.error
from io import StringIO, BytesIO
from datetime import datetime
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr

# 导入本地模块
from httprequest import HttpRequest

#配置logging模块，日志内容的格式
logging.basicConfig( level = logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d][%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S' )

#爬取时间间隔（分钟）
time_interval = 5

#配置数据库参数
db_user = 'user_name'
db_passwd = 'user_passwd'
db_name = 'db_name'


class Post( object ):
    def __init__( self, id, post_type, post_title, post_owner, post_content, post_link, post_time, created_at ):
        self.id = id
        self.post_type = post_type
        self.post_title = post_title
        self.post_owner = post_owner
        self.post_content = post_content
        self.post_link = post_link
        self.post_time = post_time
        self.created_at = created_at


#生成帖子id的函数
def next_id():
    return '%015d%s000' % ( int( time.time() * 1000 ), uuid.uuid4().hex )

#格式化email地址函数
def _format_addr(s):
    name, addr = parseaddr(s)
    return formataddr((Header(name, 'utf-8').encode(), addr))

#根据url获取帖子的标题，创建或更新时间，以及摘要内容
def get_post_content_and_time( post_url, post_type, post_name, time_last_time ):
    post_full_url = 'http://www.hi-pda.com/forum/' + post_url
    post_headers = {
        'Referer' : 'http://www.hi-pda.com/forum/',
        'Host'    : 'www.hi-pda.com'
    }
    
    logging.info( 'Get post[%s] by url[%s].' % ( post_name, post_url ) )

    #根据url请求帖子内容
    post_request = HttpRequest( post_full_url, None, post_headers )
    post_request.send_request()
    post_resp_content = post_request.get_resp_content()
    try:
        post_resp_content = post_resp_content.decode('gbk')
    except UnicodeDecodeError as e:
        logging.error( 'Decode post response content failed.' )
        logging.exception( e )
    
    #从帖子内容中解析帖子的摘要
    re_pattern_content = re.compile( r'''<meta name="description" content="(.*)" />''' )
    result_content = re_pattern_content.search( post_resp_content )

    post_content = None
    post_update_time = None
    post_create_time = None

    if result_content is None:
        logging.warn( 'Request failed.' )
    else:
        post_content = result_content.groups()[0]

    if post_content is None:
        logging.warn( 'Get post conetent failed.' )
    else:
        #从帖子内容中解析帖子更新时间
        re_pattern_update_time = re.compile( r'''于 (.*) 编辑''' )
        result_update_time = re_pattern_update_time.search( post_content )
        if result_update_time is None:
            pass
        else:
            post_update_time = result_update_time.groups()[0]

    if post_update_time is None:
        #从帖子内容中解析帖子发表时间
        re_pattern_create_time = re.compile( r'''<em id=".+">发表于 (.+)</em>''' )
        result_create_time = re_pattern_create_time.search( post_resp_content )
        
        if result_create_time is None:
            logging.warn( 'Get post time failed.' )
        else:
            post_create_time = result_create_time.groups()[0]
    else:
        post_create_time = post_update_time

    
    post_create_time_datetime = datetime.strptime(post_create_time, '%Y-%m-%d %H:%M')
    post_create_time_stamp = post_create_time_datetime.timestamp()


    post = None

    #比较帖子时间和上次爬取时间，如果大于上次爬取时间，则视为本次爬取目标
    if ( post_create_time_stamp - time_last_time ) > 0:

        conn = mysql.connector.connect(user = db_user, password = db_passwd, database = db_name)
        cursor = conn.cursor()
        logging.info( 'post_type:' + post_type )
        logging.info( 'post_name:' + post_name )
        logging.info( 'post_url:' + post_full_url )
        logging.info( 'post_create_time:' + post_create_time )
        logging.info( 'post_content:' + post_content )
        
        post_id = next_id()
        post = Post( id = post_id, post_type = post_type, post_title = post_name, post_owner = 'hipda', post_content = post_content, post_link = post_full_url, post_time = post_create_time )
        # post.save()
        cursor.execute('insert into posts (id, post_type, post_title, post_owner, post_content, post_link, post_time, created_at ) values (%s, %s, %s, %s, %s, %s, %s, %s)', [post_id, post_type, post_name, 'hipda', post_content, post_full_url, post_create_time_stamp, post_create_time_stamp])
        conn.commit()
        cursor.close()
        conn.close()
        time.sleep( 1 )
    else:
        logging.info( 'Post time[%s] is not after last time.' % post_create_time_datetime )

    return post

if __name__ == '__main__':

    while True:

        # read get_post_time last time from file
        get_post_time_last_time = None
        get_post_time_last_time_stamp = None
        with open('config_get_post_time', 'r') as f:
            get_post_time_last_time = f.read()
        if get_post_time_last_time == '':
            get_post_time_last_time = 0
            get_post_time_last_time_stamp = 0
        else:
            get_post_time_last_time = datetime.strptime( get_post_time_last_time, '%Y-%m-%d %H:%M:%S' )
            get_post_time_last_time_stamp = get_post_time_last_time.timestamp()

        logging.info( '************last time: %s************' % get_post_time_last_time )

        #using cookieJar & HTTPCookieProcessor to automatically handle cookies
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        urllib.request.install_opener(opener)

        pda_url = 'http://www.hi-pda.com/'
        pda_request = HttpRequest( pda_url )
        pda_request.send_request()
        pda_resp_content = pda_request.get_resp_content()

        formhash_url = 'http://www.hi-pda.com/forum/logging.php?action=login&referer=http%3A//www.hi-pda.com/forum/'
        formhash_request = HttpRequest( formhash_url, None, { 'Host' : 'www.hi-pda.com' } )
        formhash_request.send_request()
        formhash_resp_content = formhash_request.get_resp_content()
        try:
            formhash_resp_content = formhash_resp_content.decode('gbk')
        except UnicodeDecodeError as e:
            logging.error( 'Decode formhash response content failed.' )
            logging.exception( e )

        # print( formhash_resp_content )
        # <input type="hidden" name="formhash" value="2f68efff" />
        re_formhash = re.compile( r'''<input type="hidden" name="formhash" value="(.+)" />''' )
        formhash = re_formhash.search( formhash_resp_content )
        if formhash is None:
            logging.warn('Not found the formhash.')
            pass
        else:
            formhash_content = formhash.groups()[0] 

        username = 'username'
        md5 = hashlib.md5()
        password = 'password'
        md5.update( password.encode('utf-8') )
        password = md5.hexdigest()
        
        login_url = 'http://www.hi-pda.com/forum/logging.php?action=login&loginsubmit=yes&inajax=1'
        login_data = {
            'formhash'     : formhash_content,
            'referer'      : 'http://www.hi-pda.com/forum/',
            'loginfield'   : 'username',
            'username'     : username,
            'password'     : password,
            'questionid'   : '0',
            'answer'       : ''
        }
        login_headers = {
            'Referer' : 'http://www.hi-pda.com/forum/logging.php?action=login&referer=http%3A//www.hi-pda.com/forum/',
            'Host'    : 'www.hi-pda.com'
        }
        login_request = HttpRequest( login_url, login_data, login_headers )
        login_request.send_request()
        login_resp_content = login_request.get_resp_content()

        now = datetime.now()
        get_post_time = now.strftime('%Y-%m-%d %H:%M:%S')

        posts_url = 'http://www.hi-pda.com/forum/forumdisplay.php?fid=6'
        posts_headers = {
            'Referer' : 'http://www.hi-pda.com/forum/',
            'Host'    : 'www.hi-pda.com'
        }
        posts_request = HttpRequest( posts_url, None, posts_headers )
        posts_request.send_request()
        posts_resp_content = posts_request.get_resp_content()
        try:
            posts_resp_content = posts_resp_content.decode('gbk')
        except UnicodeDecodeError as e:
            logging.error( 'Decode posts response content failed.' )
            logging.exception( e )

        #<em>[<a href="forumdisplay.php?fid=6&amp;filter=type&amp;typeid=8">其他好玩的</a>]</em><span id="thread_1746307"><a href="viewthread.php?tid=1746307&amp;extra=page%3D1" style="font-weight: bold;color: #3C9D40">【马来西亚国宝】强肾固元的东革阿里！“三高”克星-向天果！纯天然无副作用！</a></span>
        
        re_pattern = re.compile( r'''<em>\[<a href="forumdisplay\.php\?fid=6&amp;filter=type&amp;typeid=.{1}">(.*)</a>]</em><span id=".*"><a href="(.+?)".*>(.*)</a></span>''' )
        m = re_pattern.findall( posts_resp_content )

        email_content = ''
        for x in m:
            #print( x )
            post = get_post_content_and_time( x[1], x[0], x[2], get_post_time_last_time_stamp )
            if post is None:
                logging.warn('Get post content failed.')
                pass
            else:
                single_post_content = '''<h3><a target="_blank" href=%s>%s</a></h3><p>发表于%s</p><p>%s</p>''' % ( post.post_link, post.post_title, post.post_time, post.post_content )
                email_content += single_post_content

        with open('config_get_post_time', 'w') as f:
            f.write( get_post_time )

        if email_content != '':

            conn = mysql.connector.connect( user = db_user, password = db_passwd, database = db_name )
            cursor = conn.cursor()
            cursor.execute( 'select email from users' )
            result_emails = cursor.fetchall()
            cursor.close()
            conn.close()

            emails = list( email[0] for email in result_emails )
                      
            sender = 'xxxxx@gmail.com'
            receiver = emails
            subject = 'HiPda Buy & Sell News'  
            smtpserver = 'smtp.gmail.com'
            smtpport = 587
            username = 'xxxxx@gmail.com'
            password = 'xxxxxxx'
      
            #生成邮件内容
            msg = MIMEText( email_content,'html','utf-8' )   
            msg['Subject'] = subject  
            msg['From'] = _format_addr('笑然一生 <%s>' % sender)
            #msg['To'] = _format_addr('HiPDAer <%s>' % receiver)
            msg['Subject'] = Header('', 'utf-8').encode()

            try:
                smtp = smtplib.SMTP( smtpserver, smtpport )
                smtp.ehlo()
                smtp.starttls()
                smtp.login(username, password)  
                smtp.sendmail(sender, receiver, msg.as_string())  
                smtp.quit()  
            except Exception as e:
                logging.error( 'Send email failed.' )
                logging.exception( e )
        else:
            logging.info( 'Email content is none.' )

        time.sleep( time_interval * 60 )


