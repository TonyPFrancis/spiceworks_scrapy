# -*- coding: utf-8 -*-
from apt.utils import get_maintenance_end_date
import re
import requests
from scrapy.spider import Spider
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from urlparse import urlparse, urljoin, parse_qs
from scrapy.selector import Selector
from time import sleep
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
                model_number = item.get('model', '')
                product_rating = item.get('avg_rating', '')
                number_of_replies = str(item.get('times_rated', ''))
                if _id:
                    meta_data = {'_id': _id,
                                 'model_number': model_number,
                                 'product_rating': product_rating,
                                 'number_of_replies': number_of_replies}
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
        mention_link_fk_list = []
        no_review = 0
        no_mention = 0

        PRODUCT_TITLE_XPATH = '//h1[@class="product-name"]/text()'
        REVIEWS_XPATH = '//ul[@class="activity-filters"]/li[@class="reviews-filter"]//span/text()'
        MENTIONS_XPATH = '//ul[@class="activity-filters"]/li[@class="mentions-filter"]//span/text()'
        PROJECTS_XPATH = '//ul[@class="activity-filters"]/li[contains(@class,"projects-filter")]//span/text()'
        DESCRIPTION_XPATH = '//div[@id="description_body"]/p//text()'

        model_number = meta_data['model_number']
        number_of_replies = meta_data['number_of_replies']
        product_rating = meta_data['product_rating']
        description = sel.xpath(DESCRIPTION_XPATH).extract()
        description = ' '.join(' '.join(description).split()) if description else ''
        title = sel.xpath(PRODUCT_TITLE_XPATH).extract()
        title = title[0].strip() if title else ''
        reviews = sel.xpath(REVIEWS_XPATH).extract()
        reviews = reviews[0].strip() if reviews else ''
        mentions = sel.xpath(MENTIONS_XPATH).extract()
        mentions = mentions[0].strip() if mentions else ''
        projects = sel.xpath(PROJECTS_XPATH).extract()
        projects = projects[0].strip() if projects else ''
        reviews_list = self.parse_reviews(sel)
        mentions_list = self.parse_mentions(sel)

        main_item = MainItem()
        main_item['model_number'] = model_number
        main_item['number_of_replies'] = number_of_replies
        main_item['product_rating'] = product_rating
        main_item['description'] = description
        main_item['reviews'] = reviews
        main_item['mentions'] = mentions
        if reviews_list:
            for review_item in reviews_list:
                main_item['review_by'] = review_item['review_by']
                main_item['review_at'] = review_item['review_at']
                main_item['review'] = review_item['review']
                main_item['review_rating'] = review_item['review_rating']
                if self.EXPORT_ITEM == 'MAIN':
                    yield main_item
            del main_item['review_by'], main_item['review_at'], main_item['review'], main_item['review_rating']
        else:
            no_review = 1
        if mentions_list:
            for mention_item in mentions_list:
                main_item['mention_by'] = mention_item['mention_by']
                main_item['resource'] = mention_item['resource']
                main_item['mention_link_fk'] = mention_item['mention_link_fk']
                if main_item['mention_link_fk']:
                    mention_link_fk_list.append(main_item['mention_link_fk'])
                # yields main items
                if self.EXPORT_ITEM == 'MAIN':
                    yield main_item
        else:
            no_mention = 1

        if no_review == 1 and no_mention == 1:
            if self.EXPORT_ITEM == 'MAIN':
                yield main_item

        mention_link_fk_list = list(set(mention_link_fk_list))
        if mention_link_fk_list:
            for mention_link_fk in mention_link_fk_list:
                # yields topic item
                if self.EXPORT_ITEM == 'TOPIC':
                    yield Request(url=mention_link_fk, dont_filter=True, callback=self.parse_mention_link)

    def parse_reviews(self, sel):
        reviews_list = []
        REVIEW_SEL_XPATH = '//*[contains(@class,"show-reviews show-mentions show-projects")]/li[@class="review "]'

        review_sels = sel.xpath(REVIEW_SEL_XPATH)
        if review_sels:
            REVIEW_RATING_XPATH = './/span[@class="stars"]/meta[@itemprop="ratingValue"]/@content'
            REVIEW_AT_XPATH = './/span[@class="comment_date info"]//time[@itemprop="datePublished"]/text()'
            REVIEW_BY_XPATH = './/div[@class="user-info"]//a[@itemprop="author"]/text()'
            REVIEW_TEXT_XPATH = './/div[@itemprop="reviewBody"]/p//text()'
            for review_sel in review_sels:
                review_rating = review_sel.xpath(REVIEW_RATING_XPATH).extract()
                review_rating = review_rating[0].strip() if review_rating else ''
                review_at = review_sel.xpath(REVIEW_AT_XPATH).extract()
                review_at = review_at[0].strip() if review_at else ''
                review_by = review_sel.xpath(REVIEW_BY_XPATH).extract()
                review_by = review_by[0].strip() if review_by else ''
                review = review_sel.xpath(REVIEW_TEXT_XPATH).extract()
                review = ' '.join(' '.join(review).split()) if review else ''
                reviews_list.append({'review_rating': review_rating,
                                     'review_at': review_at,
                                     'review_by': review_by,
                                     'review': review})

        return reviews_list

    def parse_mentions(self, sel):
        mentions_list = []
        MENTION_SEL_XPATH = '//*[contains(@class,"show-reviews show-mentions show-projects")]/li[@class="activity_feed_post "]'

        mention_sels = sel.xpath(MENTION_SEL_XPATH)
        if MENTION_SEL_XPATH:
            MENTION_BY_XPATH = './/div[@class="user-info"]//a[@class="user profile_link "]/text()'
            MENTION_RESOURCE_XPATH = './/div[@class="user-info"]/span[@class="info"]/text()'
            MENTION_LINK_XPATH = './/a[@class="root_post_title"]/@href'
            for mention_sel in mention_sels:
                mention_by = mention_sel.xpath(MENTION_BY_XPATH).extract()
                mention_by = mention_by[0].strip() if mention_by else ''
                resource = mention_sel.xpath(MENTION_RESOURCE_XPATH).extract()
                resource = resource[0].strip() if resource else ''
                resource = resource.lstrip('posted in').strip()
                mention_link_fk = mention_sel.xpath(MENTION_LINK_XPATH).extract()
                mention_link_fk = (mention_link_fk[0] if mention_link_fk[0].startswith('http') else self.BASE_URL+mention_link_fk[0]) if mention_link_fk else ''
                mentions_list.append({'mention_by': mention_by,
                                      'resource': resource,
                                      'mention_link_fk': mention_link_fk})

        return mentions_list

    def parse_mention_link(self, response):

        TOPIC_BY_XPATH = '//div[@class="title-and-controls"]//a[@class="user"]/text()'
        TOPIC_TIMESTAMP_XPATH = '//div[@class="title-and-controls"]//span[@data-js-postprocess="timestamp"]/text()'
        TITLE_XPATH = '//div[@class="title-and-controls"]/h1/a/text()'
        TOPIC_CONTENT_XPATH = '//div[@id="root_post"]/p//text()'
        TOPIC_RESOURCE_XPATH = '//div[@class="title-and-controls"]//div[@class="classification"]/a/text()'
        REPLY_NUMBER_XPATH = '//section[@class="replies"]/h2/text()'

        topic_sel = Selector(response)
        mention_link_fk = response.url
        topic_by = topic_sel.xpath(TOPIC_BY_XPATH).extract()
        topic_by = topic_by[0].strip() if topic_by else ''
        timestamp = topic_sel.xpath(TOPIC_TIMESTAMP_XPATH).extract()
        timestamp = timestamp[0].strip() if timestamp else ''
        title = topic_sel.xpath(TITLE_XPATH).extract()
        title = title[0].strip() if title else ''
        topic_content = topic_sel.xpath(TOPIC_CONTENT_XPATH).extract()
        topic_content = ' '.join(' '.join(topic_content).split()) if topic_content else ''
        resource = topic_sel.xpath(TOPIC_RESOURCE_XPATH).extract()
        resource = resource[0].strip() if resource else ''
        number_of_replies = topic_sel.xpath(REPLY_NUMBER_XPATH).extract()
        number_of_replies = number_of_replies[0].strip() if number_of_replies else ''

        reply_list = self.parse_mention_reply(topic_sel)
        topic_item = TopicItem()
        topic_item['mention_link_fk'] = mention_link_fk
        topic_item['topic_by'] = topic_by
        topic_item['timestamp'] = timestamp
        topic_item['title'] = title
        topic_item['topic'] = topic_content
        topic_item['resource'] = resource
        topic_item['number_of_replies'] = number_of_replies
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
            REPLY_AT_XPATH = './/span[@class="date"]//span[@data-js-postprocess="timestamp"]/text()'
            REPLY_CONTENT_XPATH = './/div[@class="post-body"]/p//text()'
            for reply_sel in reply_sels:
                reply_by = reply_sel.xpath(REPLY_BY_XPATH).extract()
                reply_by = reply_by[0].strip() if reply_by else ''
                reply_at = reply_sel.xpath(REPLY_AT_XPATH).extract()
                reply_at = reply_at[0].strip() if reply_at else ''
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


