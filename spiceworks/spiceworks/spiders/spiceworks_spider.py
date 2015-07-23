# -*- coding: utf-8 -*-
from apt.utils import get_maintenance_end_date
import re
import requests
from scrapy.spider import Spider
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from urlparse import urlparse, urljoin, parse_qs
from scrapy.selector import Selector
from time import sleep
from math import ceil
import urllib
from spiceworks.items import MainItem, TopicItem
from scrapy.http import Request
from dateutil import rrule, parser
from dateutil import relativedelta
from datetime import timedelta, datetime
from scrapy.log import ScrapyFileLogObserver
from scrapy import log
from scrapy.shell import inspect_response
import time
import json

class SpiceworksSpider(Spider):
    name = 'spiceworks'
    start_urls = ['http://community.spiceworks.com/networking/product/reviews?selector_query=dell', ]
    allowed_domains = ['spiceworks.com', ]
    TIMEZONE = ''
    BASE_URL = 'http://community.spiceworks.com'
    search_keyword = 'dell'
    EXPORT_ITEM = 'MAIN'    # [MAIN, TOPIC]

    def __init__(self, name=None, **kwargs):
        ScrapyFileLogObserver(open("spider.log", 'w'), level=log.INFO).start()
        ScrapyFileLogObserver(open("spider_error.log", 'w'), level=log.ERROR).start()
        super(SpiceworksSpider, self).__init__(name, **kwargs)

    def parse(self, response):
        sel = Selector(response)

        search_url = 'http://community.spiceworks.com/api/v2/catalog/search.json'
        params = {'q':'{"taxons":"networking","keywords":"%s","facets":["manufacturer","vendor","avg_price","avg_rating"],"filter_variants":true,"index":"products","sort":{"field":"premium_level", "dir":"desc"}}'%(self.search_keyword),
                  'ipp':'10',
                  'p':'0',
                  'callback':''}
        search_url = search_url+'?%s'%(urllib.urlencode(params))
        yield Request(url=search_url, callback=self.parse_product_list)

    def parse_product_list(self, response):
        sel = Selector(response)

        json_data = json.loads(response.body)

        results = json_data.get('results', [])
        if results:
            for item in results:
                product_url = self.BASE_URL+'/product/'
                _id = str(item.get('id',''))
                product_title = item.get('name', '')
                model_number = item.get('model', '')
                product_rating = item.get('avg_rating', '')
                if _id:
                    meta_data = {'_id': _id,
                                 'product_title': product_title,
                                 'model_number': model_number,
                                 'product_rating': product_rating}
                    product_url = product_url+_id
                    yield Request(url=product_url, dont_filter=True, callback=self.parse_product, meta=meta_data)
        else:
            print 'NO REVIEW LIST'

        current_page = json_data.get('cur_page', 0)
        pages = json_data.get('pages', 0)
        if current_page and (current_page < pages):
            search_url = 'http://community.spiceworks.com/api/v2/catalog/search.json'
            params = {'q':'{"taxons":"networking","keywords":"%s","facets":["manufacturer","vendor","avg_price","avg_rating"],"filter_variants":true,"index":"products","sort":{"field":"premium_level", "dir":"desc"}}'%(self.search_keyword),
                      'ipp':'10',
                      'p':'%s'%(current_page),
                      'callback':''}
            search_url = search_url+'?%s'%(urllib.urlencode(params))
            yield Request(url=search_url, callback=self.parse_product_list)

    def parse_product(self, response):
        sel = Selector(response)

        meta_data = response.meta
        if self.EXPORT_ITEM == 'MAIN':
            return self.parse_main(sel, meta_data)
        elif self.EXPORT_ITEM == 'TOPIC':
            return self.parse_topic(sel, meta_data)

    def parse_main(self, sel, meta_data):

        DESCRIPTION_XPATH = '//div[@id="description_body"]/p//text()'
        TOTAL_NUMBER_OF_REVIEWS_XPATH = '//ul[@class="activity-filters"]/li[@class="reviews-filter"]//span/text()'

        product_title = meta_data['product_title']
        model_number = meta_data['model_number']
        product_rating = meta_data['product_rating']
        description = sel.xpath(DESCRIPTION_XPATH).extract()
        description = ' '.join(' '.join(description).split()) if description else ''
        total_number_of_reviews = sel.xpath(TOTAL_NUMBER_OF_REVIEWS_XPATH).extract()
        total_number_of_reviews = total_number_of_reviews[0].strip() if total_number_of_reviews else ''
        reviews_list = self.parse_reviews(meta_data['_id'], total_number_of_reviews)

        main_item = MainItem()
        main_item['product_title'] = product_title
        main_item['model_number'] = model_number
        main_item['product_rating'] = product_rating
        main_item['description'] = description
        main_item['total_number_of_reviews'] = total_number_of_reviews
        if reviews_list:
            for review_item in reviews_list:
                main_item['review_by'] = review_item['review_by']
                main_item['review_at'] = review_item['review_at']
                main_item['review'] = review_item['review']
                main_item['review_rating'] = review_item['review_rating']
                yield main_item
        else:
            yield main_item

    def parse_reviews(self, product_id, total_number_of_reviews):
        reviews_list = []
        if int(total_number_of_reviews) > 0:
            for x in range(int(ceil(float(total_number_of_reviews)/31))):
                fetch_review_url = 'https://community.spiceworks.com/product/%s/activity?offset=%s&type=reviews&sort=new&rating=null'%(product_id, x*31)
                reviews_list = reviews_list + self.fetch_reviews(fetch_review_url)

        return reviews_list

    def fetch_reviews(self, fetch_review_url):
        HEADERS = {'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding':'gzip, deflate, sdch',
                    'Accept-Language':'en-US,en;q=0.8',
                    'Cache-Control':'max-age=0',
                    'Connection':'keep-alive',
                    'Host':'community.spiceworks.com',
                    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.130 Safari/537.36'}
        sel = Selector(text=requests.get(url=fetch_review_url, headers=HEADERS).content)
        reviews_list = []
        REVIEW_SEL_XPATH = '//li[@class="review "]'

        review_sels = sel.xpath(REVIEW_SEL_XPATH)
        if review_sels:
            REVIEW_BY_XPATH = './/div[@class="user-info"]//a[@itemprop="author"]/text()'
            REVIEW_AT_XPATH = './/span[@class="comment_date info"]//time[@itemprop="datePublished"]/@datetime'
            REVIEW_TEXT_XPATH = './/div[@itemprop="reviewBody"]/p//text()'
            REVIEW_RATING_XPATH = './/span[@class="stars"]/meta[@itemprop="ratingValue"]/@content'
            for review_sel in review_sels:
                review_by = review_sel.xpath(REVIEW_BY_XPATH).extract()
                review_by = review_by[0].strip() if review_by else ''
                review_at = review_sel.xpath(REVIEW_AT_XPATH).extract()
                review_at = parser.parse(review_at[0].strip()).replace(tzinfo=None) if review_at else ''
                review = review_sel.xpath(REVIEW_TEXT_XPATH).extract()
                review = ' '.join(' '.join(review).split()) if review else ''
                review_rating = review_sel.xpath(REVIEW_RATING_XPATH).extract()
                review_rating = review_rating[0].strip() if review_rating else ''
                reviews_list.append({'review_rating': review_rating,
                                     'review_at': review_at,
                                     'review_by': review_by,
                                     'review': review})

        return reviews_list

    def parse_topic(self, sel, meta_data):

        TOTAL_NUMBER_OF_MENTION_XPATH = '//ul[@class="activity-filters"]/li[@class="mentions-filter"]//span/text()'

        product_title = meta_data['product_title']
        total_number_of_mentions = sel.xpath(TOTAL_NUMBER_OF_MENTION_XPATH).extract()
        total_number_of_mentions = total_number_of_mentions[0].strip() if total_number_of_mentions else ''
        mentions_list = self.parse_mentions(meta_data['_id'], total_number_of_mentions)

        topic_item = TopicItem()
        topic_item['product_title'] = product_title
        topic_item['total_number_of_mentions'] = total_number_of_mentions
        if mentions_list:
            for mention_item in mentions_list:
                if mention_item['mention_link_fk']:
                    meta_data['total_number_of_mentions'] = total_number_of_mentions
                    yield Request(url=mention_item['mention_link_fk'], dont_filter=True, callback=self.parse_mention_link, meta=meta_data)
        else:
            yield topic_item

    def parse_mentions(self, product_id, total_number_of_mentions):
        mentions_list = []
        if int(total_number_of_mentions) > 0:
            for x in range(int(ceil(float(total_number_of_mentions)/31))):
                fetch_mention_url = 'https://community.spiceworks.com/product/%s/activity?offset=%s&type=mentions&sort=new&rating=null'%(product_id, x*31)
                mentions_list = mentions_list + self.fetch_mentions(fetch_mention_url)

        return mentions_list

    def fetch_mentions(self, fetch_mention_url):
        HEADERS = {'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding':'gzip, deflate, sdch',
                    'Accept-Language':'en-US,en;q=0.8',
                    'Cache-Control':'max-age=0',
                    'Connection':'keep-alive',
                    'Host':'community.spiceworks.com',
                    'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.130 Safari/537.36'}
        sel = Selector(text=requests.get(url=fetch_mention_url, headers=HEADERS).content)
        mentions_list = []
        MENTION_SEL_XPATH = '//li[@class="activity_feed_post "]'

        mention_sels = sel.xpath(MENTION_SEL_XPATH)
        if MENTION_SEL_XPATH:
            MENTION_LINK_XPATH = './/a[@class="root_post_title"]/@href'
            for mention_sel in mention_sels:
                mention_link_fk = mention_sel.xpath(MENTION_LINK_XPATH).extract()
                mention_link_fk = (mention_link_fk[0] if mention_link_fk[0].startswith('http') else self.BASE_URL+mention_link_fk[0]) if mention_link_fk else ''
                mentions_list.append({'mention_link_fk': mention_link_fk})

        return mentions_list

    def parse_mention_link(self, response):
        meta_data = response.meta

        MENTION_TITLE_XPATH = '//div[@class="title-and-controls"]/h1/a/text()'
        MENTION_CONTENT_XPATH = '//div[@id="root_post"]/p//text()'
        MENTION_BY_XPATH = '//div[@class="title-and-controls"]//a[@class="user"]/text()'
        TOTAL_NUMBER_OF_REPLIES = '//section[@class="replies"]/h2/text()'

        topic_sel = Selector(response)
        mention_link_fk = response.url
        mention_title = topic_sel.xpath(MENTION_TITLE_XPATH).extract()
        mention_title = mention_title[0].strip() if mention_title else ''
        mention_content = topic_sel.xpath(MENTION_CONTENT_XPATH).extract()
        mention_content = ' '.join(' '.join(mention_content).split()) if mention_content else ''
        mention_by = topic_sel.xpath(MENTION_BY_XPATH).extract()
        mention_by = mention_by[0].strip() if mention_by else ''
        total_number_of_replies = topic_sel.xpath(TOTAL_NUMBER_OF_REPLIES).extract()
        total_number_of_replies = total_number_of_replies[0].strip() if total_number_of_replies else ''
        total_number_of_replies = total_number_of_replies.strip('Replies').strip('Reply').strip()
        reply_list = self.parse_mention_reply(topic_sel)

        topic_item = TopicItem()
        topic_item['product_title'] = meta_data['product_title']
        topic_item['total_number_of_mentions'] = meta_data['total_number_of_mentions']
        topic_item['mention_link_fk'] = mention_link_fk
        topic_item['mention_title'] = mention_title
        topic_item['mention_content'] = mention_content
        topic_item['mention_by'] = mention_by
        topic_item['total_number_of_replies'] = total_number_of_replies

        if reply_list:
            for reply_item in reply_list:
                topic_item['reply_by'] = reply_item['reply_by']
                topic_item['reply_at'] = reply_item['reply_at']
                topic_item['reply'] = reply_item['reply']
                yield topic_item
        else:
            yield topic_item

    def parse_mention_reply(self, topic_sel):
        reply_list = []

        REPLY_SELS_XPATH = '//section[@class="replies"]/div[@class="posts-wrapper"]/div[@class="post   "]'

        reply_sels = topic_sel.xpath(REPLY_SELS_XPATH)
        if reply_sels:
            REPLY_BY_XPATH = './/span[@class="author"]/a/text()'
            REPLY_AT_XPATH = './/span[@class="date"]//span[@data-js-postprocess="timestamp"]/@datetime'
            REPLY_CONTENT_XPATH = './/div[@class="post-body"]/p//text()'
            for reply_sel in reply_sels:
                reply_by = reply_sel.xpath(REPLY_BY_XPATH).extract()
                reply_by = reply_by[0].strip() if reply_by else ''
                reply_at = reply_sel.xpath(REPLY_AT_XPATH).extract()
                reply_at = parser.parse(reply_at[0].strip()).replace(tzinfo=None) if reply_at else ''
                reply = reply_sel.xpath(REPLY_CONTENT_XPATH).extract()
                reply = ' '.join(' '.join(reply).split()) if reply else ''
                reply_list.append({'reply_by':reply_by,
                                   'reply_at': reply_at,
                                   'reply': reply})

        NEXT_PAGE_XPATH = '//section[@class="replies"]/div[@class="pages"]/a[@class="next "]/@href'
        next_page = topic_sel.xpath(NEXT_PAGE_XPATH).extract()
        next_page = next_page[0].strip() if next_page else ''
        if next_page:
            reply_list = reply_list + self.parse_mention_reply(Selector(text=requests.get(url=next_page).content))

        return reply_list


