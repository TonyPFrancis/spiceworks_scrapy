Pending tasks:
-------------

1. Fetching of "storeage" and "server" categories are remaining
2. CSV file is created with native scrapy "-o out.csv" command
    To get files, use following method


Running spider:
--------------

1. Output items are fetched using variable
    EXPORT_ITEM = 'TOPIC'    # [MAIN, TOPIC]

    * to get main item
        EXPORT_ITEM = 'MAIN'
        spider command : 'scrapy crawl spiceworks -o main_items.csv'

    * to get topic item
        EXPORT_ITEM = 'TOPIC'
        spider command : 'scrapy crawl spiceworks -o topic_items.csv'