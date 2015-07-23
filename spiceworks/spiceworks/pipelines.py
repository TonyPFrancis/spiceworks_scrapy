# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html
from items import MainItem
from pymongo import MongoClient


class SpiceworksPipeline(object):

    def __init__(self, *args, **kwargs):
        self.client = MongoClient()
        self.db = self.client['spiceworks']
        self.flag_dict = {
                            '0': self.db['main_item'],
                            '1': self.db['topic_item']
                        }

    def process_item(self, item, spider):
        if isinstance(item, MainItem):
            collection = 'main_item'
            if self.is_unique(item, '0'):
                'data inserting to Mian Item'
                self.db[collection].insert(dict(item))
        else:
            collection = 'topic_item'
            if self.is_unique(item, '1'):
                'data inserting to Topic Item'
                self.db[collection].insert(dict(item))
        return item

    def is_unique(self, data, flag):
        return self.flag_dict[flag].find(dict(data)).count() == 0
