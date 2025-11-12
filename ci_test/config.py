# @Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
# Licensed under the Apache-2.0 License. See LICENSE file for details.

import json
import os
import re
import shutil
import platform
import subprocess
from tomlkit import parse


class ArgConfig:
    CANGJIE_STDX_DOWNLOAD_MAP = {
        "1.0.0":
            {
                "aarch64-linux-ohos": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.0.1/cangjie-stdx-ohos-aarch64-1.0.0.1.zip",
                "aarch64": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.0.1/cangjie-stdx-linux-aarch64-1.0.0.1.zip",
                "x86_64-unknown-linux-gnu": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.0.1/cangjie-stdx-linux-x64-1.0.0.1.zip",
                "x86_64-linux-ohos": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.0.1/cangjie-stdx-ohos-x64-1.0.0.1.zip",
                "windows": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.0.1/cangjie-stdx-windows-x64-1.0.0.1.zip",
            },
        "1.0.1":
            {
                "aarch64-linux-ohos": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-ohos-aarch64-1.0.1.1.zip",
                "aarch64": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-linux-aarch64-1.0.1.1.zip",
                "x86_64-unknown-linux-gnu":"https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-linux-x64-1.0.1.1.zip",
                "x86_64-linux-ohos": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-ohos-x64-1.0.1.1.zip",
                "windows": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-windows-x64-1.0.1.1.zip"
            },
        "1.0.3":
            {
                "aarch64-linux-ohos": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-ohos-aarch64-1.0.1.1.zip",  # TODO 未发现release版本
                "aarch64": "https://gitcode.com/Cangjie/cangjie_stdx/releases/download/v1.0.3.1/cangjie-stdx-linux-aarch64-1.0.3.1.zip",
                "x86_64-unknown-linux-gnu":"https://gitcode.com/Cangjie/cangjie_stdx/releases/download/v1.0.3.1/cangjie-stdx-linux-x64-1.0.3.1.zip",
                "x86_64-linux-ohos": "https://gitcode.com/Cangjie/cangjie-stdx-bin/releases/download/v1.0.1.1/cangjie-stdx-ohos-x64-1.0.1.1.zip",  # TODO 未发现release版本
                "windows": "https://gitcode.com/Cangjie/cangjie_stdx/releases/download/v1.0.3.1/cangjie-stdx-windows-x64-1.0.3.1.zip"
            },
    }
    BUILD_TYPE = None
    LOG = None
    Woff = ""
    CANGJIE_SOURCE_DIR = ""
    CI_TEST_DIR = ""
    TEST_DIR = ""
    UT_TEST_DIR = ""
    BASE_DIR = None
    HOME_DIR = None
    HOME = None
    ENCODING = None
    FILE_ROOT = None
    LIB_DIR = None
    BUILD_BIN = "build"
    CJ_TEST_WORK = "test"
    OS_PLATFORM = "windows"
    LINE_SEPARATOR = "\\r\\n"
    CONFIG_FILE = "module.json"
    MODULE_NAME = None
    EXPECT_CJC_VERSION = None
    REALLY_CJC_VERSION = None
    build_output_dir = None
    BUILD_PARMS = None  # 解析的cjpm.toml参数, 以字典的形式
    BUILD_CI_TEST_CFG = None  #
    BUILD_DEPENDENCIES = []
    BUILD_CJPM_PATH = None
    IMPORT_PATH = ""  # --import-path
    LIBRARY_PATH = ""  # -L
    LIBRARY = ""  # -l
    MODULE_FOREIGN_REQUIRES = None
    WINDOWS_C_LIB_ARR = set()
    CUSTOM_MAP = {}
    LIBRARY_PRIORITY = list()
    OHOS_CANGJIE_PATH = None
    OHOS_COMPILE_OPTION = None
    OHOS_VERSION = None
    CANGJIE_TARGET = None
    CANGJIE_STDX_PATH = None
    CANGJIE_HOME = None
    cj_home = None
    BASE_CJC_VERSION = "0.0.0"
    UPDATE_CJPM_TOML = False

    def __init__(self):
        master_cjc = shutil.which("cjc")
        if master_cjc:
            out = os.popen('{} -v'.format(master_cjc))
            self.REALLY_CJC_VERSION = out.readline().split('Cangjie Compiler: ')[1].split(' (')[0]
        if platform.system() == 'Linux':
            if platform.uname().processor == "x86_64" or platform.uname().machine == "x86_64":
                self.OS_PLATFORM = 'linux_x86_64'
            elif platform.uname().processor == "aarch64" or platform.uname().machine == "aarch64":
                self.OS_PLATFORM = 'linux_aarch64'
            else:
                self.OS_PLATFORM = None
        elif platform.system() == 'Windows':
            self.OS_PLATFORM = "windows"
        else:
            self.OS_PLATFORM = None
        if self.OS_PLATFORM and self.OS_PLATFORM == "windows":
            self.LINE_SEPARATOR = "\r\n"
        elif str(self.OS_PLATFORM).startswith("linux"):
            self.LINE_SEPARATOR = "\n"
        else:
            self.LINE_SEPARATOR = "\r"

    def get_stdx_url(self):
        if self.CANGJIE_TARGET == "aarch64-linux-ohos":
            return self.CANGJIE_STDX_DOWNLOAD_MAP[self.BASE_CJC_VERSION][self.CANGJIE_TARGET]
        elif self.CANGJIE_TARGET == "x86_64-linux-ohos":
            return self.CANGJIE_STDX_DOWNLOAD_MAP[self.BASE_CJC_VERSION][self.CANGJIE_TARGET]
        elif self.CANGJIE_TARGET == "x86_64-unknown-linux-gnu":
            return self.CANGJIE_STDX_DOWNLOAD_MAP[self.BASE_CJC_VERSION][self.CANGJIE_TARGET]
        elif "windows" in self.CANGJIE_TARGET:
            return self.CANGJIE_STDX_DOWNLOAD_MAP[self.BASE_CJC_VERSION]["windows"]
        elif "mingw32" in self.CANGJIE_TARGET:
            return self.CANGJIE_STDX_DOWNLOAD_MAP[self.BASE_CJC_VERSION]["windows"]
        elif "aarch64" in self.CANGJIE_TARGET:
            return self.CANGJIE_STDX_DOWNLOAD_MAP[self.BASE_CJC_VERSION]["aarch64"]
        return None

    def config_init(self):
        if os.path.exists(os.path.join(self.HOME_DIR, "cjpm.toml")):
            self.__handle_toml()
        elif os.path.exists(os.path.join(self.HOME_DIR, "module.json")):
            self.__handle_json()
        else:
            self.LOG.warn("没有项目工程配置文件, 请配置module.json或者cjpm.toml配置文件")

    def set_build_bin(self, new_build):
        self.BUILD_BIN = new_build

    def __handle_toml(self):
        self.CONFIG_FILE = "cjpm.toml"
        cfg_file = os.path.join(self.HOME_DIR, self.CONFIG_FILE)
        self.BUILD_PARMS = parse(open(cfg_file, "r", encoding='UTF-8').read())
        try:
            self.MODULE_NAME = self.BUILD_PARMS['package']['name']
        except:
            self.MODULE_NAME = os.path.basename(self.HOME_DIR)
        try:
            self.EXPECT_CJC_VERSION = self.BUILD_PARMS['package']['cjc-version']
            for key, value in self.BUILD_PARMS['ffi'].items():
                if key == "c":
                    self.MODULE_FOREIGN_REQUIRES = value
        except:
            pass
        try:
            file = open(cfg_file, "r", encoding='UTF-8')
            for line in file.readlines():
                if line.startswith("#"):
                    self.CUSTOM_MAP[re.search(r"\[.*?\]", line).group()[1:-1]] = re.search(r"\{.*?\}", line).group()[
                                                                                 1:-1]
            file.close()
        except:
            self.LOG.warn("toml 配置文件定义出错, 格式 # [key]={value}, 请检查")

    def __handle_json(self):
        try:
            file = open(os.path.join(self.HOME_DIR, self.CONFIG_FILE), "r", encoding='UTF-8')
            self.BUILD_PARMS = json.load(file)
            try:
                self.MODULE_NAME = self.BUILD_PARMS['name']
                self.EXPECT_CJC_VERSION = self.BUILD_PARMS['cjc-version']
                self.MODULE_FOREIGN_REQUIRES = self.BUILD_PARMS['foreign_requires']
            except:
                self.MODULE_NAME = os.path.basename(self.HOME_DIR)
        except FileNotFoundError:
            self.LOG.warn("未发现module.json文件")

    def run_cmd(self, cmd, file_dir="./"):
        encode = 'gbk' if self.OS_PLATFORM == "windows" else "utf-8"
        res = subprocess.Popen(cmd, shell=True, cwd=file_dir, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        try:
            while res.poll() is None:
                for msg in iter(res.stdout.readline, b''):
                    msg = str(msg, encode, errors='ignore').strip()
                    if msg != "":
                        self.LOG.info(msg)
                res.kill()
        finally:
            if res.poll():
                res.kill()
        return res.returncode
