import logging
from datetime import datetime
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
timestr = datetime.now().strftime("%Y%m%d%H%M%S")
file_handler = logging.FileHandler('backup_' + datetime.now().strftime("%Y%m%d%H%M%S") + '.log', encoding="utf-8")
# formatter = logging.Formatter('%(asctime)s%(message)s')
# console_handler.setFormatter(formatter)
# file_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.addHandler(file_handler)
