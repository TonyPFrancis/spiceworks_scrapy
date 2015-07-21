# -*- coding: utf-8 -*-

# Scrapy settings for spiceworks project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'spiceworks'

SPIDER_MODULES = ['spiceworks.spiders']
NEWSPIDER_MODULE = 'spiceworks.spiders'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'spiceworks (+http://www.yourdomain.com)'

AUTOTHROTTLE_ENABLED = True