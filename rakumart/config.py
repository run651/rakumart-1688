import os

# Credentials
APP_KEY = os.getenv("APP_KEY", "56832_68d09f0d2a2c6")
APP_SECRET = os.getenv("APP_SECRET", "eEtXGkyf9HFIsZ2i!ZOv")

# Search/Detail/Image APIs
API_URL = os.getenv("API_URL", "https://apiwww.rakumart.com/open/goods/keywordsSearch")
DETAIL_API_URL = os.getenv("DETAIL_API_URL", "https://apiwww.rakumart.com/open/goods/detail")
IMAGE_ID_API_URL = os.getenv("IMAGE_ID_API_URL", "https://apiwww.rakumart.com/open/goods/getImageId")

# Logistics/Tags
LOGISTICS_API_URL = os.getenv("LOGISTICS_API_URL", "https://apiwww.rakumart.com/open/currentUsefulLogistics")
TAGS_API_URL = os.getenv("TAGS_API_URL", "https://apiwww.rakumart.com/open/currentUsefulTags")
LOGISTICS_TRACK_API_URL = os.getenv("LOGISTICS_TRACK_API_URL", "https://apiwww.rakumart.com/open/logisticsTrack")

# Orders
CREATE_ORDER_API_URL = os.getenv("CREATE_ORDER_API_URL", "https://apiwww.rakumart.com/open/createOrder")
UPDATE_ORDER_STATUS_API_URL = os.getenv("UPDATE_ORDER_STATUS_API_URL", "https://apiwww.rakumart.com/open/updateOrderStatus")
CANCEL_ORDER_API_URL = os.getenv("CANCEL_ORDER_API_URL", "https://apiwww.rakumart.com/open/cancelOrder")
ORDER_LIST_API_URL = os.getenv("ORDER_LIST_API_URL", "https://apiwww.rakumart.com/open/orderList")
ORDER_DETAIL_API_URL = os.getenv("ORDER_DETAIL_API_URL", "https://apiwww.rakumart.com/open/orderDetail")
STOCK_LIST_API_URL = os.getenv("STOCK_LIST_API_URL", "https://apiwww.rakumart.com/open/stockList")

# Porders
CREATE_PORDER_API_URL = os.getenv("CREATE_PORDER_API_URL", "https://apiwww.rakumart.com/open/createPorder")
UPDATE_PORDER_STATUS_API_URL = os.getenv("UPDATE_PORDER_STATUS_API_URL", "https://apiwww.rakumart.com/open/updatePorderStatus")
CANCEL_PORDER_API_URL = os.getenv("CANCEL_PORDER_API_URL", "https://apiwww.rakumart.com/open/cancelPorder")
PORDER_LIST_API_URL = os.getenv("PORDER_LIST_API_URL", "https://apiwww.rakumart.com/open/porderList")
PORDER_DETAIL_API_URL = os.getenv("PORDER_DETAIL_API_URL", "https://apiwww.rakumart.com/open/porderDetail")


