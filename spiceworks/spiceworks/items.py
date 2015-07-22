# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy.item import Field, Item


class MainItem(Item):
    # define the fields for your Main item here like:
    product_title = Field()
    model_number = Field()
    product_rating = Field()
    description = Field()
    total_number_of_reviews = Field()
    review_by = Field()
    review_at = Field()
    review = Field()
    review_rating = Field()

class TopicItem(Item):
    # define the fields for your Topic item here like:
    product_title = Field()
    total_number_of_mentions = Field()
    mention_link_fk = Field()
    mention_title = Field()
    mention_content = Field()
    mention_by = Field()
    total_number_of_replies = Field()
    reply_by = Field()
    reply_at = Field()
    reply = Field()