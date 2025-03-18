#!/usr/bin/python3
# encoding= utf-8
import locale
import os
from pathlib import Path
from ci import main
from config import ArgConfig


if __name__ == '__main__':
    cof = ArgConfig()
    cof.BUILD_TYPE = os.path.basename(__file__)
    cof.BASE_DIR = os.path.join(Path(__file__).parent.absolute())
    cof.HOME_DIR = os.path.dirname(cof.BASE_DIR)
    cof.LIB_DIR = None
    cof.TEST_DIR = os.path.join(cof.HOME_DIR, 'test')
    cof.ENCODING = locale.getpreferredencoding(False)
    cof.CANGJIE_SOURCE_DIR = os.path.join(cof.HOME_DIR, 'src')
    cof.CI_TEST_DIR = os.path.join(cof.HOME_DIR, 'ci_test')
    cof.UT_TEST_DIR = os.path.join(cof.TEST_DIR, 'UT')
    main(cof)


