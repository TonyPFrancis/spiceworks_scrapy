# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy.item import Field, Item


class MainItem(Item):
    # define the fields for your Main item here like:
    model_number = Field()
    number_of_replies = Field()
    product_rating = Field()
    description = Field()
    reviews = Field()
    mentions = Field()
    review_by = Field()
    review_at = Field()
    review = Field()
    review_rating = Field()
    mention_link_fk = Field()
    mention_by = Field()
    resource = Field()

class TopicItem(Item):
    # define the fields for your Topic item here like:
    mention_link_fk = Field()
    topic_by = Field()
    timestamp = Field()
    title = Field()
    topic = Field()
    resource = Field()
    reply_by = Field()
    reply_at = Field()
    reply = Field()
    number_of_replies = Field()








