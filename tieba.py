#!/usr/bin/env python3
# 2018/12/05 

import os
import time
import datetime
import random
import sqlalchemy as sql
import sqlalchemy.orm
import sqlalchemy.ext.declarative
import logging
import requests
import html5lib


# settings
PROJECT_NAME = 'tieba'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, 'images')
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11",
    "Mozilla/5.0 (Windows; U; MSIE 9.0; Windows NT 9.0; en-US)",
    "Mozilla/5.0 (Windows; U; Windows NT 5.1; zh-CN) AppleWebKit/523.15 (KHTML, like Gecko, Safari/419.3) Arora/0.3 (Change: 287 c9dfb30)",
    "Mozilla/5.0 (Windows; U; Windows NT 5.1; zh-CN; rv:1.9) Gecko/20080705 Firefox/3.0 Kapiko/3.0",
    "Mozilla/5.0 (Windows; U; Windows NT 5.2) AppleWebKit/525.13 (KHTML, like Gecko) Chrome/0.2.149.27 Safari/525.13",
    "Mozilla/5.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0; WOW64; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; .NET CLR 1.0.3705; .NET CLR 1.1.4322)",
    "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Win64; x64; Trident/5.0; .NET CLR 3.5.30729; .NET CLR 3.0.30729; .NET CLR 2.0.50727; Media Center PC 6.0)",
]

# watch thread list
LIST_FILE = '%s.list' % PROJECT_NAME

# logging
LOG_FILE = '%s.log' % PROJECT_NAME
logger = logging.getLogger()
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_FILE, mode='a+')
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter(
  "%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s"))
logger.addHandler(fh)
fh = logging.StreamHandler()
fh.setFormatter(logging.Formatter(
  "%(asctime)s - %(levelname)s: %(message)s"))
fh.setLevel(logging.INFO)
logger.addHandler(fh)


# database and orm
DB_FILE = '%s.sqlite3' % PROJECT_NAME
DB_URI = 'sqlite:///%s' % DB_FILE

engine = sql.create_engine(DB_URI)
Model = sql.ext.declarative.declarative_base(bind=engine)

class Thread(Model):
    __tablename__ = 'Thread'

    id = sql.Column(sql.INT, primary_key=True, autoincrement=True)
    url = sql.Column(sql.VARCHAR(512))
    last_page = sql.Column(sql.INT, default=1)
    time = sql.Column(sql.TIMESTAMP, server_default=sql.text('CURRENT_TIMESTAMP'),
                      onupdate=datetime.datetime.now)

    def __repr__(self):
        return '<Thread-%r last_page=%r, url=%r>' % (self.id, self.last_page, self.url)

class Image(Model):
    __tablename__ = 'Image'

    id = sql.Column(sql.INT, primary_key=True, autoincrement=True)
    url = sql.Column(sql.VARCHAR(512))
    path = sql.Column(sql.VARCHAR(256))
    status = sql.Column(sql.BOOLEAN(), default=False)
    time = sql.Column(sql.TIMESTAMP, server_default=sql.text('CURRENT_TIMESTAMP'))

    def __repr__(self):
        return '<Image-%r status=%r, path=%r>' % (self.id, self.status, self.path)

Model.metadata.create_all()
DBSession = sql.orm.sessionmaker(bind=engine)
db = DBSession()


# http
def GET(url, timeout=30):
    params = {'User-Agent': random.choice(USER_AGENTS)}
    try:
        resp = requests.get(url=url, params=params, timeout=timeout)
        if resp.status_code == 200:
            return True, resp.content
        elif resp.status_code == 404:
            logger.warning('[Downloader] url %r got 404' % url)
    except (requests.ConnectTimeout, requests.ConnectionError):
        logger.error('[Downloader] connection error for %r' % url)
    except Exception as e:
        logger.error('[Downloader] unknown error %r' % e)
    return False, None

def save_image(img, timeout=30):
    ok, data = GET(img.url, timeout)
    if ok:
        fn = os.path.basename(img.url)
        fp = os.path.join(IMAGE_DIR, fn)
        if os.path.exists(fp):
            logger.error('[Downloader] overwrite file %r', fn)

        with open(fp, 'wb+') as fh:
            fh.write(data)
            fh.flush()

        img.status = True
        img.path = fn
        db.add(img)
        db.commit()
        return True
    else:
        return False

def crawl_page(url, timeout=30):
    ok, data = GET(url, timeout)
    cnt = 0
    if ok:
        html = html5lib.parse(data, namespaceHTMLElements=False)
        for img in html.findall('.//img'):
            src = img.get('src')
            if img.get('class') != 'BDE_Image' or \
                  db.query(Image).filter_by(url=src).count() != 0:
                continue

            img = Image(url=src)
            db.add(img)
            db.commit()
            save_image(img)
            cnt += 1

        logger.info('[Crawler] %d new images found on %r' % (cnt, url))
    return cnt

def crawl_threads():
    for thr in db.query(Thread).all():
        url = '%s?pn=%d' % (thr.url, thr.last_page)
        while crawl_page(url) > 0:
            db.add(thr)
            db.commit()
            thr.last_page += 1
            url = '%s?pn=%d' % (thr.url, thr.last_page)

        time.sleep(1)

def add_threads():
    for url in open(LIST_FILE).read().split():
        if db.query(Thread).filter_by(url=url).count() == 0:
            thr = Thread(url=url)
            db.add(thr)
    db.commit()

def download_retry():
    for img in db.query(Image).filter_by(status=False).all():
        save_image(img)


# main
if __name__ == '__main__':
    try:
        add_threads()
        download_retry()
        crawl_threads()
    except KeyboardInterrupt:
        db.flush()