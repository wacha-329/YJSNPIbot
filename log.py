import logging
import inspect
import datetime
import constant as const

LogLevel = logging.CRITICAL
LogLevel_text = 'CRITICAL'
file_exist = const.log_file_exist

logger = logging.getLogger(__name__)
#log_handler = logging.StreamHandler()
#log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
#logger.propagate = False
#logger.addHandler(log_handler)


def setLogLv(lv):
    global logger
    if lv == 'c':
        LogLevel = logging.CRITICAL
        LogLevel_text = 'CRITICAL'
    elif lv == 'e':
        LogLevel = logging.ERROR
        LogLevel_text = 'ERROR'
    elif lv == 'w':
        LogLevel = logging.WARNING
        LogLevel_text = 'WARNING'
    elif lv == 'i':
        LogLevel = logging.INFO
        LogLevel_text = 'INFO'
    elif lv == 'd':
        LogLevel = logging.DEBUG
        LogLevel_text = 'DEBUG'
    else:
        LogLevel = logging.CRITICAL
        LogLevel_text = 'CRITICAL'

    if file_exist:
        now = datetime.datetime.now()
        logging.basicConfig(filename='log/' + now.strftime('%Y%m%d_%H%M%S') + '.log', level=LogLevel, format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',datefmt='%Y-%m-%d:%H:%M:%S')
        log_handler = logging.FileHandler('log/' + now.strftime('%Y%m%d_%H%M%S') + '.log')
        log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
        logger.propagate = False
        logger.addHandler(log_handler)
    else:
        logging.basicConfig(level=LogLevel, format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',datefmt='%Y-%m-%d:%H:%M:%S')
        log_handler = logging.StreamHandler()
        log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
        logger.propagate = False
        logger.addHandler(log_handler)
    logging.info('setLogLv: LogLevel = ' + LogLevel_text)

def c(msg):
    global logger
    info = getCallerData()
    logger.critical('[' + info[0] + ':' + info[1] + ']' + ' ' + str(msg))

def e(msg):
    global logger
    info = getCallerData()
    logger.error('[' + info[0] + ':' + info[1] + ']' + ' ' + str(msg))

def w(msg):
    global logger
    info = getCallerData()
    logger.warning('[' + info[0] + ':' + info[1] + ']' + ' ' + str(msg))

def i(msg):
    global logger
    info = getCallerData()
    logger.info('[' + info[0] + ':' + info[1] + ']' + ' ' + str(msg))

def d(msg):
    global logger
    info = getCallerData()
    logger.debug('[' + info[0] + ':' + info[1] + ']' + ' ' + str(msg))

def getCallerData():
    record = inspect.stack()[2]
    frameinfo = inspect.getframeinfo(record[0])
    callerdatalist = [str(frameinfo.filename).split('\\')[-1],str(frameinfo.lineno)]
    return callerdatalist
